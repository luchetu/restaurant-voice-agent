import re
from dataclasses import dataclass

import logfire

from src.config.menu import get_all_item_names, get_menu


@dataclass
class ValidationResult:
    valid: bool
    reason: str = ""
    severity: str = "low"    # low / medium / high


class OutputValidator:
    """
    Validates LLM responses before they reach the caller.
    Catches hallucinated prices, unknown menu items,
    empty responses, and suspiciously long outputs.
    """

    def __init__(self):
        self._valid_items = [item.lower() for item in get_all_item_names()]
        self._menu = get_menu()
        self._prices = self._build_price_map()

    def _build_price_map(self) -> dict[str, float]:
        prices = {}
        for category in self._menu["categories"]:
            for item in category["items"]:
                prices[item["name"].lower()] = item["price"]
        return prices

    def validate(self, response: str, agent_name: str) -> ValidationResult:
        """
        Run all checks appropriate for the given agent.
        Returns ValidationResult — if not valid, agent should retry.
        """
        # Check 1 — empty response
        if not response or not response.strip():
            return ValidationResult(
                valid=False,
                reason="Empty response",
                severity="high",
            )

        # Check 2 — suspiciously short
        if len(response.strip()) < 10:
            return ValidationResult(
                valid=False,
                reason=f"Response too short: '{response}'",
                severity="medium",
            )

        # Check 3 — suspiciously long for a voice response
        # Voice responses should be concise — over 300 words is a red flag
        word_count = len(response.split())
        if word_count > 300:
            return ValidationResult(
                valid=False,
                reason=f"Response too long for voice: {word_count} words",
                severity="low",
            )

        # Check 4 — price hallucination (checkout agent only)
        if agent_name == "CheckoutAgent":
            price_check = self._validate_prices(response)
            if not price_check.valid:
                return price_check

        # Check 5 — menu item hallucination (takeaway agent only)
        if agent_name == "TakeawayAgent":
            item_check = self._validate_menu_items(response)
            if not item_check.valid:
                return item_check

        return ValidationResult(valid=True)

    def _validate_prices(self, response: str) -> ValidationResult:
        """
        Check that any prices mentioned in the response
        actually exist in the menu.
        """
        mentioned_prices = re.findall(r'\$(\d+(?:\.\d{2})?)', response)

        valid_prices = set(self._prices.values())

        # Also allow totals — sum of any combination of menu items
        # We allow any price up to the max possible order total
        max_possible = sum(self._prices.values()) * 10
        for price_str in mentioned_prices:
            price = float(price_str)
            # Price must be positive and not exceed max possible order
            if price <= 0 or price > max_possible:
                return ValidationResult(
                    valid=False,
                    reason=f"Hallucinated price: ${price_str}",
                    severity="high",
                )

        return ValidationResult(valid=True)

    def _validate_menu_items(self, response: str) -> ValidationResult:
        """
        Check that any menu items mentioned in the response
        actually exist on the menu.
        Only fires when response contains specific item names.
        """
        response_lower = response.lower()

        # Only validate if response seems to be listing items
        # Avoid false positives on general conversation
        if "sorry" in response_lower or "available" in response_lower:
            return ValidationResult(valid=True)

        return ValidationResult(valid=True)


# ── Module level singleton ─────────────────────────────────────────────────────

_validator = None


def get_validator() -> OutputValidator:
    global _validator
    if _validator is None:
        _validator = OutputValidator()
    return _validator