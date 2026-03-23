import logfire
from livekit.agents.voice import Agent, RunContext

from src.core.audit import AuditAction, AuditLogger
from src.core.token_counter import context_usage_percent
from src.models.session import UserData

RunContext_T = RunContext[UserData]


# What each agent needs from the session — agent-specific context injection
AGENT_CONTEXT_FIELDS = {
    "GreeterAgent": [
        "customer_name",
        "customer_phone",
    ],
    "ReservationAgent": [
        "customer_name",
        "customer_phone",
        "reservation",
    ],
    "TakeawayAgent": [
        "customer_name",
        "order",
    ],
    "CheckoutAgent": [
        "customer_name",
        "customer_phone",
        "order",
        "payment_status",
    ],
}


class BaseAgent(Agent):
    async def on_enter(self) -> None:
        agent_name = self.__class__.__name__
        userdata: UserData = self.session.userdata

        # Update room attributes safely
        try:
            if userdata.ctx and userdata.ctx.room:
                await userdata.ctx.room.local_participant.set_attributes({"agent": agent_name})
        except Exception:
            pass

        # Track agent duration
        if userdata.metrics:
            userdata.metrics.agent_started(agent_name)

        # Build context
        chat_ctx = self.chat_ctx.copy()

        if userdata.prev_agent:
            items_copy = self._truncate_chat_ctx(
                userdata.prev_agent.chat_ctx.items,
                keep_function_call=True,
            )
            existing_ids = {item.id for item in chat_ctx.items}
            chat_ctx.items.extend([i for i in items_copy if i.id not in existing_ids])

        # Log context usage
        usage = context_usage_percent(chat_ctx.items, self._get_model_name())
        logfire.info(
            "context.usage",
            agent=agent_name,
            usage_percent=usage,
            session_id=userdata.session_id,
        )

        # Warn if context is getting full
        if usage > 70:
            logfire.warning(
                "context.high_usage",
                agent=agent_name,
                usage_percent=usage,
                session_id=userdata.session_id,
            )

        # Inject agent-specific context — only what this agent needs
        handoff_note = ""
        if userdata.last_handoff_reason:
            handoff_note = f"Transfer reason: {userdata.last_handoff_reason}. "

        relevant_context = self._build_relevant_context(agent_name, userdata)

        chat_ctx.add_message(
            role="system",
            content=(f"You are the {agent_name}. {handoff_note}{relevant_context}"),
        )
        await self.update_chat_ctx(chat_ctx)
        self.session.generate_reply()

        # Audit
        if userdata.audit:
            userdata.audit.log(
                action=AuditAction.AGENT_ENTER,
                agent=agent_name,
                detail=f"prev={userdata.prev_agent.__class__.__name__ if userdata.prev_agent else 'none'} context={usage}%",
            )
        logfire.info(
            "agent.enter",
            agent=agent_name,
            session_id=userdata.session_id,
            context_usage=usage,
        )

    async def on_exit(self) -> None:
        agent_name = self.__class__.__name__
        userdata: UserData = self.session.userdata
        if userdata.metrics:
            userdata.metrics.agent_ended(agent_name)
        logfire.info("agent.exit", agent=agent_name)

    def _build_relevant_context(self, agent_name: str, userdata: UserData) -> str:
        """
        Inject only the session fields relevant to this agent.
        Greeter does not need payment info.
        Checkout does not need reservation details.
        Smaller context = lower cost + less confusion.
        """
        fields = AGENT_CONTEXT_FIELDS.get(agent_name, [])
        lines = []

        if "customer_name" in fields and userdata.customer.name:
            lines.append(f"Customer name: {userdata.customer.name}")

        if "customer_phone" in fields and userdata.customer.phone:
            lines.append(f"Customer phone: {userdata.customer.phone}")

        if "reservation" in fields:
            lines.append(f"Reservation: {userdata.reservation.summary()}")

        if "order" in fields:
            lines.append(f"Order: {userdata.order.summary()}")

        if "payment_status" in fields:
            lines.append(f"Payment: {'complete' if userdata.payment.is_complete else 'pending'}")

        if not lines:
            return userdata.summarize()

        return "\n".join(lines)

    def _get_model_name(self) -> str:
        """Get the model name from the agent's LLM for token counting."""
        try:
            return self._llm.model or "gpt-4o-mini"
        except Exception:
            return "gpt-4o-mini"

    def _truncate_chat_ctx(
        self,
        items: list,
        keep_last_n: int = 6,
        keep_function_call: bool = False,
    ) -> list:
        def _valid(item) -> bool:
            if item.type == "message" and item.role == "system":
                return False
            if not keep_function_call and item.type in ["function_call", "function_call_output"]:
                return False
            return True

        result = []
        for item in reversed(items):
            if _valid(item):
                result.append(item)
            if len(result) >= keep_last_n:
                break

        result = result[::-1]

        while result and result[0].type in ["function_call", "function_call_output"]:
            result.pop(0)

        return result

    def _validate_response(self, response: str) -> bool:
        from src.core.output_validator import get_validator

        validator = get_validator()
        result = validator.validate(response, self.__class__.__name__)
        if not result.valid:
            logfire.warning(
                "output_validator.failed",
                agent=self.__class__.__name__,
                reason=result.reason,
                severity=result.severity,
            )
            return False
        return True

    async def _transfer_to_agent(
        self,
        name: str,
        context: RunContext_T,
        reason: str = "",
    ) -> tuple:
        userdata = context.userdata
        userdata.prev_agent = context.session.current_agent
        userdata.last_handoff_reason = reason

        if userdata.metrics:
            userdata.metrics.record_transfer(
                from_agent=self.__class__.__name__,
                to_agent=name,
            )
        if userdata.audit:
            userdata.audit.log(
                action=AuditAction.TRANSFER,
                agent=self.__class__.__name__,
                detail=f"→ {name}: {reason}",
            )
        logfire.info(
            "agent.transfer",
            from_agent=self.__class__.__name__,
            to_agent=name,
            reason=reason,
            session_id=userdata.session_id,
        )
        return userdata.agents[name], "One moment, transferring you now."
