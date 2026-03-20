from livekit.agents.voice import RunContext
from src.agents.base import BaseAgent
from src.core.resilience import build_llm, build_tts
from src.models.session import UserData
from src.utils.prompt_loader import load_prompt
from src.tools.shared import update_name, update_phone, to_greeter
from src.tools.reservation_tools import (
    update_reservation_date,
    update_reservation_time,
    update_party_size,
    confirm_reservation,
)

RunContext_T = RunContext[UserData]


class ReservationAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            instructions=load_prompt("reservation"),
            llm=build_llm(),
            tts=build_tts("reservation"),
            tools=[
                update_name,
                update_phone,
                update_reservation_date,
                update_reservation_time,
                update_party_size,
                confirm_reservation,
                to_greeter,
            ],
        )