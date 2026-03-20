from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext
from src.agents.base import BaseAgent
from src.core.resilience import build_llm, build_tts
from src.models.session import UserData
from src.utils.prompt_loader import load_prompt

RunContext_T = RunContext[UserData]


class GreeterAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            instructions=load_prompt("greeter"),
            llm=build_llm(),
            tts=build_tts("greeter"),
        )

    @function_tool()
    async def to_reservation(self, context: RunContext_T) -> tuple:
        """Called when the customer wants to make or update a reservation."""
        return await self._transfer_to_agent(
            "reservation", context, reason="customer wants a reservation"
        )

    @function_tool()
    async def to_takeaway(self, context: RunContext_T) -> tuple:
        """Called when the customer wants to place a takeaway or delivery order."""
        return await self._transfer_to_agent(
            "takeaway", context, reason="customer wants to order food"
        )