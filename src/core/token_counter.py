from functools import lru_cache
from typing import Final

# Approximate token counts per model family
# Based on tiktoken cl100k_base encoding (GPT-4, Claude, Llama all similar)
AVG_CHARS_PER_TOKEN: Final[int] = 4


MODEL_CONTEXT_LIMITS = {
    "llama-3.1-8b-instant": 8_192,
    "claude-haiku-3-5": 200_000,
    "claude-sonnet-3-5": 200_000,
    "gpt-4o-mini": 128_000,
    "gpt-4o": 128_000,
    "gpt-3.5-turbo": 16_385,
}

# How much of the context window we actually use
# Leave 20% headroom for the response
SAFE_CONTEXT_RATIO: Final[float] = 0.80


def estimate_tokens(text: str) -> int:
    """
    Estimate token count from character count.
    Not perfectly accurate but fast and dependency-free
    Rule of thumb: 1 token = 4 characters in English
    """

    if not text:
        return 0

    return max(1, len(text) // AVG_CHARS_PER_TOKEN)


def estimate_tokens_for_messages(messages: list) -> int:
    """
    Estimate total tokens across a list of chat messages.
    Each message adds ~4 tokens of overhead for role/formatting.
    """
    total = 0
    for msg in messages:
        total += 4  # message overhead
        content = getattr(msg, "content", "") or ""
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    total += estimate_tokens(block.get("text", ""))
    return total


def get_context_limit(model: str) -> int:
    """Return the context window size for a given model."""
    return MODEL_CONTEXT_LIMITS.get(model, 8_192)


def get_safe_context_limit(model: str) -> int:
    """Return the safe context limit with headroom for response."""
    return int(get_context_limit(model) * SAFE_CONTEXT_RATIO)


def context_usage_percent(messages: list, model: str) -> float:
    """
    Return what percentage of the safe context window is used.
    Above 80% means we should compress.
    """
    used = estimate_tokens_for_messages(messages)
    limit = get_safe_context_limit(model)
    return round((used / limit) * 100, 1)


def should_compress(messages: list, model: str, threshold: float = 70.0) -> bool:
    """
    Returns True when context usage exceeds threshold.
    Default threshold is 70% — compress before hitting the limit.
    """
    return context_usage_percent(messages, model) >= threshold
