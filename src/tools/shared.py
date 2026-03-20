from typing import Annotated
from pydantic import Field
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext
from src.models.session import UserData

RunContext_T = RunContext[UserData]


@function_tool()
async def update_name(
    name: Annotated[str, Field(description="The customer's full name")],
    context: RunContext_T,
) -> str:
    """Called when the customer provides their name. Confirm spelling first."""
    context.userdata.customer.name = name
    return f"Name updated to {name}"


@function_tool()
async def update_phone(
    phone: Annotated[str, Field(description="The customer's phone number")],
    context: RunContext_T,
) -> str:
    """Called when the customer provides their phone number. Confirm it first."""
    context.userdata.customer.phone = phone
    return f"Phone updated to {phone}"


@function_tool()
async def to_greeter(context: RunContext_T) -> tuple:
    """Called when the customer asks for something outside your role."""
    current = context.session.current_agent
    userdata = context.userdata
    userdata.prev_agent = current
    userdata.last_handoff_reason = "returned to greeter"
    return userdata.agents["greeter"], "Transferring you back to our receptionist."