import logfire
from livekit.agents.voice import Agent, RunContext
from src.models.session import UserData
from src.core.audit import AuditLogger, AuditAction

RunContext_T = RunContext[UserData]


class BaseAgent(Agent):
    async def on_enter(self) -> None:
        agent_name = self.__class__.__name__
        userdata: UserData = self.session.userdata

        # Update room attributes — wrapped safely, room may not be ready yet
        try:
            if userdata.ctx and userdata.ctx.room:
                await userdata.ctx.room.local_participant.set_attributes(
                    {"agent": agent_name}
                )
        except Exception:
            pass  # room not connected yet — non-critical, skip silently

        # Carry over last 6 messages from previous agent
        chat_ctx = self.chat_ctx.copy()
        if userdata.prev_agent:
            items_copy = self._truncate_chat_ctx(
                userdata.prev_agent.chat_ctx.items,
                keep_function_call=True,
            )
            existing_ids = {item.id for item in chat_ctx.items}
            chat_ctx.items.extend(
                [i for i in items_copy if i.id not in existing_ids]
            )

        # Inject agent identity + current session state
        handoff_note = ""
        if userdata.last_handoff_reason:
            handoff_note = f"Transfer reason: {userdata.last_handoff_reason}. "

        chat_ctx.add_message(
            role="system",
            content=(
                f"You are the {agent_name}. {handoff_note}"
                f"Current session:\n{userdata.summarize()}"
            ),
        )
        await self.update_chat_ctx(chat_ctx)
        self.session.generate_reply()

        # Audit
        if userdata.audit:
            userdata.audit.log(
                action=AuditAction.AGENT_ENTER,
                agent=agent_name,
                detail=f"prev={userdata.prev_agent.__class__.__name__ if userdata.prev_agent else 'none'}",
            )
        logfire.info("agent.enter", agent=agent_name, session_id=userdata.session_id)

    def _truncate_chat_ctx(
        self,
        items: list,
        keep_last_n: int = 6,
        keep_function_call: bool = False,
    ) -> list:
        def _valid(item) -> bool:
            if item.type == "message" and item.role == "system":
                return False
            if not keep_function_call and item.type in [
                "function_call", "function_call_output"
            ]:
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

    async def _transfer_to_agent(
        self,
        name: str,
        context: RunContext_T,
        reason: str = "",
    ) -> tuple:
        userdata = context.userdata
        userdata.prev_agent = context.session.current_agent
        userdata.last_handoff_reason = reason

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
        
    def _validate_response(self, response: str) -> bool:
            """
            Validate LLM response before it reaches the caller.
           Returns True if valid, False if agent should retry.
          """
    from src.core.output_validator import get_validator
    validator = get_validator()
    agent_name = self.__class__.__name__
    result = validator.validate(response, agent_name)

    if not result.valid:
        logfire.warning(
            "output_validator.failed",
            agent=agent_name,
            reason=result.reason,
            severity=result.severity,
        )
        return False

    return True



    

     