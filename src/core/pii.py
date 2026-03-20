import re


_PATTERNS = {
    "phone":   r"\b(\+?254|0)\d{9}\b",              # Kenyan numbers + international
    "card":    r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b",
    "cvv":     r"\b\d{3,4}\b",
    "email":   r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
    "dob":     r"\b(0[1-9]|[12]\d|3[01])[\/\-](0[1-9]|1[0-2])[\/\-]\d{4}\b",
}


def mask_pii(text: str) -> str:
    """Replace sensitive patterns with safe placeholders before logging."""
    if not text:
        return text
    text = re.sub(_PATTERNS["card"],  "[CARD]",  text)
    text = re.sub(_PATTERNS["phone"], "[PHONE]", text)
    text = re.sub(_PATTERNS["email"], "[EMAIL]", text)
    text = re.sub(_PATTERNS["dob"],   "[DOB]",   text)
    return text


def mask_card(card_number: str) -> str:
    """Return last 4 digits only — for display, not logging."""
    if not card_number:
        return "not provided"
    digits = re.sub(r"\D", "", card_number)
    return f"**** **** **** {digits[-4:]}" if len(digits) >= 4 else "****"