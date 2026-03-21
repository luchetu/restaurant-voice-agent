from typing import Annotated
from pydantic import Field
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext
from src.agents.base import BaseAgent
from src.core.resilience import build_llm_sonnet, build_tts
from src.core.audit import AuditAction
from src.core.pii import mask_card
from src.models.session import UserData, PaymentInfo
from src.utils.prompt_loader import load_prompt
from src.tools.shared import update_name, update_phone, to_greeter

RunContext_T = RunContext[UserData]


class CheckoutAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            instructions=load_prompt("checkout"),
            llm=build_llm_sonnet(), # ← Claude Sonnet for high stakes payment
            tts=build_tts("checkout"),
            tools=[update_name, update_phone, to_greeter],
        )

    @function_tool()
    async def update_payment(
        self,
        card_number: Annotated[str, Field(description="16 digit card number")],
        expiry: Annotated[str, Field(description="Expiry date MM/YY")],
        cvv: Annotated[str, Field(description="3 digit CVV")],
        context: RunContext_T = None,
    ) -> str:
        """Called after customer provides all card details. Confirm last 4 digits first."""
        from pydantic import SecretStr
        context.userdata.payment = PaymentInfo(
            card_number=SecretStr(card_number),
            expiry=SecretStr(expiry),
            cvv=SecretStr(cvv),
        )
        context.userdata.audit.log(
            action=AuditAction.PAYMENT,
            agent="CheckoutAgent",
            detail=f"card ending {mask_card(card_number)}",
        )
        return f"Card ending {mask_card(card_number)} saved. Shall I confirm the payment?"

    @function_tool()
    async def confirm_payment(self, context: RunContext_T = None) -> str:
        """Called when customer confirms they want to proceed with payment."""
        userdata = context.userdata
        if not userdata.payment.is_complete:
            return "Please provide your card details first."
        if userdata.order.is_empty:
            return "No order found. Please place an order first."

        # In production: call payment_service.py here to charge via Stripe
        userdata.audit.log(
            action=AuditAction.ORDER_PLACED,
            agent="CheckoutAgent",
            detail=f"total=${userdata.order.total:.2f}",
            customer_phone=userdata.customer.phone,
        )
        return (
            f"Payment confirmed! Your order total is ${userdata.order.total:.2f}. "
            f"Your order reference is {userdata.session_id[:8].upper()}. "
            f"Estimated preparation time is 20-30 minutes. Thank you!"
        )

    @function_tool()
    async def to_takeaway(self, context: RunContext_T) -> tuple:
        """Called when the customer wants to change their order."""
        return await self._transfer_to_agent(
            "takeaway", context, reason="customer wants to modify order"
        )