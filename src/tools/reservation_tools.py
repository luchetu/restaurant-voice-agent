from typing import Annotated
from pydantic import Field
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext
from src.models.session import UserData
from src.models.reservation import ReservationStatus

RunContext_T = RunContext[UserData]


@function_tool()
async def update_reservation_date(
    date: Annotated[str, Field(description="Reservation date e.g. 'March 25th' or 'this Saturday'")],
    context: RunContext_T = None,
) -> str:
    """Called when the customer provides their preferred reservation date."""
    context.userdata.reservation.date = date
    return f"Reservation date set to {date}"


@function_tool()
async def update_reservation_time(
    time: Annotated[str, Field(description="Reservation time e.g. '7pm' or '19:00'")],
    context: RunContext_T = None,
) -> str:
    """Called when the customer provides their preferred reservation time."""
    context.userdata.reservation.time = time
    return f"Reservation time set to {time}"


@function_tool()
async def update_party_size(
    size: Annotated[int, Field(description="Number of guests", ge=1, le=20)],
    context: RunContext_T = None,
) -> str:
    """Called when the customer provides their party size."""
    context.userdata.reservation.party_size = size
    return f"Party size set to {size}"


@function_tool()
async def confirm_reservation(context: RunContext_T = None) -> str:
    """Called when the customer confirms all reservation details are correct."""
    reservation = context.userdata.reservation
    customer = context.userdata.customer

    if not reservation.is_complete:
        missing = []
        if not reservation.date:
            missing.append("date")
        if not reservation.time:
            missing.append("time")
        if not reservation.party_size:
            missing.append("party size")
        return f"Missing details: {', '.join(missing)}. Please provide these first."

    if not customer.is_complete:
        missing = []
        if not customer.name:
            missing.append("name")
        if not customer.phone:
            missing.append("phone number")
        return f"Missing customer details: {', '.join(missing)}."

    reservation.status = ReservationStatus.CONFIRMED
    return (
        f"Reservation confirmed for {customer.name}! "
        f"{reservation.summary()} "
        f"Confirmation will be sent to {customer.phone}."
    )