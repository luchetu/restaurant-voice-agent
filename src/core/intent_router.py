import asyncio
from dataclasses import dataclass
from typing import Optional

import logfire


@dataclass
class IntentResult:
    intent: str
    confidence: float
    hint: str
    method: str = "keyword"
    provider: str = "keyword"



INTENT_PATTERNS = {
    "reservation": [
        "book", "reserve", "table", "booking",
        "reservation", "seat", "seats", "tonight",
        "saturday", "sunday", "friday", "dinner",
        "lunch", "party", "people", "guests",
        "available", "availability", "slot",
    ],
    "takeaway": [
        "order", "takeaway", "delivery", "pizza",
        "food", "hungry", "menu", "eat", "burger",
        "collect", "pickup", "pick up", "salad",
        "pasta", "drink", "coffee", "dessert",
        "ice cream", "garlic bread", "fries",
    ],
    "checkout": [
        "pay", "payment", "card", "checkout",
        "bill", "total", "charge", "credit",
        "debit", "finish", "complete", "done",
    ],
}

INTENT_HINTS = {
    "reservation": "The caller likely wants to make or update a reservation.",
    "takeaway":    "The caller likely wants to place a food order.",
    "checkout":    "The caller likely wants to pay for their order.",
    "unknown":     "",
}

DIRECT_ROUTE_CONFIDENCE = 0.08
HINT_CONFIDENCE = 0.03

# Embedding thresholds — higher bar because embeddings are more accurate
EMBEDDING_DIRECT_ROUTE = 0.75
EMBEDDING_HINT = 0.60


def classify_intent_keywords(utterance: str) -> IntentResult:
    """Fast keyword-based classification — zero cost, zero latency."""
    if not utterance or not utterance.strip():
        return IntentResult(intent="unknown", confidence=0.0, hint="")

    utterance_lower = utterance.lower().strip()
    scores: dict[str, float] = {}

    for intent, keywords in INTENT_PATTERNS.items():
        matches = sum(1 for kw in keywords if kw in utterance_lower)
        scores[intent] = matches / len(keywords)

    if not any(scores.values()):
        return IntentResult(intent="unknown", confidence=0.0, hint="")

    top_intent = max(scores, key=scores.get)
    confidence = round(scores[top_intent], 3)

    return IntentResult(
        intent=top_intent,
        confidence=confidence,
        hint=INTENT_HINTS.get(top_intent, ""),
        method="keyword",
    )


async def classify_intent(utterance: str) -> IntentResult:
    """
    Full classification pipeline:
    1. Try embedding classifier first (semantic, accurate)
    2. Fall back to keyword classifier if embeddings fail
    """
    from src.core.intent_embeddings import get_classifier

    try:
        classifier = get_classifier()
        if classifier._ready:
            result = await classifier.classify(utterance)
            return IntentResult(
                intent=result.intent,
                confidence=result.confidence,
                hint=result.hint,
                method="embedding",
                provider=result.provider,
            )
    except Exception as e:
        logfire.warning(
            "intent_router.embedding_failed",
            error=str(e),
            fallback="keyword",
        )

    # Fallback to keyword matching
    return classify_intent_keywords(utterance)


def should_direct_route(result: IntentResult) -> bool:
    """High confidence — skip greeter, route directly."""
    if result.method == "embedding":
        return result.confidence >= EMBEDDING_DIRECT_ROUTE
    return result.confidence >= DIRECT_ROUTE_CONFIDENCE


def should_hint(result: IntentResult) -> bool:
    """Medium confidence — let greeter handle but inject hint."""
    if result.method == "embedding":
        return EMBEDDING_HINT <= result.confidence < EMBEDDING_DIRECT_ROUTE
    return HINT_CONFIDENCE <= result.confidence < DIRECT_ROUTE_CONFIDENCE