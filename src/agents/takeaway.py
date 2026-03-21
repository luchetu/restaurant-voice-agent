from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext
from src.agents.base import BaseAgent
from src.core.resilience import build_llm_haiku, build_tts
from src.models.session import UserData
from src.utils.prompt_loader import load_prompt
from src.tools.shared import update_name, update_phone, to_greeter
from src.tools.order_tools import (
    add_item,
    remove_item,
    get_order_summary,
    confirm_order,
)

RunContext_T = RunContext[UserData]


class TakeawayAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            instructions=load_prompt("takeaway"),
            llm=build_llm_haiku(), # ← Claude Haiku for natural conversation
            tts=build_tts("takeaway"),
            tools=[
                update_name,
                update_phone,
                add_item,
                remove_item,
                get_order_summary,
                confirm_order,
                to_greeter,
            ],
        )

    @function_tool()
    async def to_checkout(self, context: RunContext_T) -> tuple:
        """Called when the customer confirms the order and is ready to pay."""
        order = context.userdata.order
        if order.is_empty:
            return None, "You have no items in your order yet. What would you like to add?"
        return await self._transfer_to_agent(
            "checkout", context, reason=f"order confirmed: {order.summary()}"
        )