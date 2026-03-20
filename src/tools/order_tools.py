from typing import Annotated
from pydantic import Field
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext
from src.models.session import UserData
from src.models.order import OrderItem, OrderStatus
from src.config.menu import get_all_item_names

RunContext_T = RunContext[UserData]


@function_tool()
async def add_item(
    item_name: Annotated[str, Field(description="Name of the menu item to add")],
    quantity: Annotated[int, Field(description="Quantity to add", ge=1)] = 1,
    context: RunContext_T = None,
) -> str:
    """Add an item to the customer's order. Only call with items that exist on the menu."""
    valid_items = get_all_item_names()

    # Case-insensitive match
    match = next(
        (i for i in valid_items if i.lower() == item_name.lower()), None
    )
    if not match:
        return (
            f"Sorry, '{item_name}' is not on our menu. "
            f"Available items: {', '.join(valid_items)}"
        )

    # Get price from menu
    from src.config.menu import get_menu
    menu = get_menu()
    price = next(
        item["price"]
        for category in menu["categories"]
        for item in category["items"]
        if item["name"] == match
    )

    order = context.userdata.order
    # Check if item already in order — increase quantity instead
    existing = next((i for i in order.items if i.name == match), None)
    if existing:
        existing.quantity += quantity
    else:
        order.items.append(OrderItem(name=match, price=price, quantity=quantity))

    order.status = OrderStatus.BUILDING
    return f"Added {quantity}x {match} (${price:.2f} each). {order.summary()}"


@function_tool()
async def remove_item(
    item_name: Annotated[str, Field(description="Name of the menu item to remove")],
    context: RunContext_T = None,
) -> str:
    """Remove an item from the customer's order."""
    order = context.userdata.order
    match = next(
        (i for i in order.items if i.name.lower() == item_name.lower()), None
    )
    if not match:
        return f"'{item_name}' is not in the current order."

    order.items.remove(match)
    if order.is_empty:
        order.status = OrderStatus.EMPTY
    return f"Removed {match.name}. {order.summary()}"


@function_tool()
async def get_order_summary(context: RunContext_T = None) -> str:
    """Get the current order summary with total."""
    return context.userdata.order.summary()


@function_tool()
async def confirm_order(context: RunContext_T = None) -> str:
    """Called when customer confirms they are happy with the order."""
    order = context.userdata.order
    if order.is_empty:
        return "The order is empty. Please add items before confirming."
    order.status = OrderStatus.CONFIRMED
    return f"Order confirmed. {order.summary()}"