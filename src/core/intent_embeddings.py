import asyncio
from dataclasses import dataclass
from typing import Optional
from enum import Enum

import numpy as np
import logfire

from src.config.settings import get_settings

settings = get_settings()


class EmbeddingProvider(Enum):
    LOCAL     = "local"       # sentence-transformers, free, offline
    OPENAI    = "openai"      # text-embedding-3-small, best quality


# ── Change this one line to switch providers ──────────────────────────────────
ACTIVE_PROVIDER = EmbeddingProvider.LOCAL


# ── Example utterances per intent ─────────────────────────────────────────────
INTENT_EXAMPLES = {
    "reservation": [
        "I want to book a table",
        "Can I make a reservation for tonight",
        "I need to reserve a table for four people",
        "Do you have availability this Saturday",
        "I want to book for two people at 7pm",
        "Can we get a table for dinner",
        "I want to make a booking for Sunday lunch",
        "Is there space for six people on Friday night",
        "I need a table reservation",
        "We want to come in for dinner, can you fit us in",
        "Book a table for my anniversary",
        "I want to change my reservation",
        "Can I move my booking to 8pm instead",
        "I need to cancel my reservation",
        "Table for three please",
    ],
    "takeaway": [
        "I want to order some food",
        "Can I get a takeaway",
        "I want two pizzas please",
        "What is on the menu",
        "I would like to place an order",
        "Can I order for collection",
        "I want to order delivery",
        "Give me a margherita pizza and a salad",
        "I am hungry and want to order",
        "Can I get some food to go",
        "I want to order a takeaway for pickup",
        "What pizzas do you have",
        "I want to order food for the office",
        "Can I add garlic bread to my order",
        "I want to order dessert",
    ],
    "checkout": [
        "I want to pay for my order",
        "How do I pay",
        "Can I give you my card details",
        "I am ready to checkout",
        "What is the total",
        "I want to complete my order",
        "Let me pay now",
        "Can I pay by card",
        "I want to finish my order",
        "What do I owe you",
        "Ready to pay",
        "Take my payment please",
        "Charge my card",
        "How much is it",
        "Let us wrap this up",
    ],
    "unknown": [
        "Hello",
        "Hi there",
        "I have a question",
        "Can you help me",
        "I am not sure",
        "What are your opening hours",
        "Where are you located",
        "Do you have parking",
        "Are you open on Sunday",
        "I want to speak to a manager",
    ],
}

INTENT_HINTS = {
    "reservation": "The caller likely wants to make or update a reservation.",
    "takeaway":    "The caller likely wants to place a food order.",
    "checkout":    "The caller likely wants to pay for their order.",
    "unknown":     "",
}


# ── Embedding backends ────────────────────────────────────────────────────────

class LocalEmbedder:
    """
    Uses sentence-transformers running entirely on your machine.
    Free, offline, no API key needed.
    Model: all-MiniLM-L6-v2 — small, fast, good quality.
    """
    def __init__(self):
        from sentence_transformers import SentenceTransformer
        logfire.info("embedder.loading_local_model", model="all-MiniLM-L6-v2")
        self._model = SentenceTransformer("all-MiniLM-L6-v2")
        logfire.info("embedder.local_model_ready")

    def embed(self, text: str) -> np.ndarray:
        return self._model.encode(text, convert_to_numpy=True)

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        return list(self._model.encode(texts, convert_to_numpy=True))


class OpenAIEmbedder:
    """
    Uses OpenAI text-embedding-3-small.
    Higher quality than local, costs ~$0.000002 per call.
    Requires OPENAI_API_KEY with embedding access.
    """
    def __init__(self):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = "text-embedding-3-small"
        logfire.info("embedder.openai_ready", model=self._model)

    async def embed(self, text: str) -> np.ndarray:
        response = await self._client.embeddings.create(
            model=self._model,
            input=text,
        )
        return np.array(response.data[0].embedding)

    async def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        response = await self._client.embeddings.create(
            model=self._model,
            input=texts,
        )
        return [np.array(item.embedding) for item in response.data]


def _build_embedder(provider: EmbeddingProvider):
    """Factory — returns the right embedder based on active provider."""
    if provider == EmbeddingProvider.LOCAL:
        return LocalEmbedder()
    elif provider == EmbeddingProvider.OPENAI:
        return OpenAIEmbedder()
    else:
        raise ValueError(f"Unknown provider: {provider}")


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class EmbeddingIntentResult:
    intent: str
    confidence: float
    hint: str
    method: str = "embedding"
    provider: str = "local"


# ── Cosine similarity ─────────────────────────────────────────────────────────

def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


# ── Main classifier ───────────────────────────────────────────────────────────

class EmbeddingIntentClassifier:
    """
    Semantic intent classifier.
    Supports two backends — local (free) and OpenAI (higher quality).
    Switch by changing ACTIVE_PROVIDER at the top of this file.
    """

    def __init__(self, provider: EmbeddingProvider = ACTIVE_PROVIDER):
        self._provider = provider
        self._embedder = None
        self._example_embeddings: dict[str, list[np.ndarray]] = {}
        self._intent_centroids: dict[str, np.ndarray] = {}
        self._ready = False

    async def initialize(self) -> None:
        """
        Pre-embed all example utterances once at startup.
        Local model: runs synchronously in a thread pool
        OpenAI model: runs async API calls
        """
        logfire.info(
            "intent_classifier.initializing",
            provider=self._provider.value,
        )

        self._embedder = _build_embedder(self._provider)

        for intent, examples in INTENT_EXAMPLES.items():
            # Local model is synchronous — run in thread pool
            # so we don't block the async event loop
            if self._provider == EmbeddingProvider.LOCAL:
                embeddings = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._embedder.embed_batch,
                    examples,
                )
            else:
                # OpenAI is already async
                embeddings = await self._embedder.embed_batch(examples)

            self._example_embeddings[intent] = embeddings
            self._intent_centroids[intent] = np.mean(embeddings, axis=0)

        self._ready = True
        logfire.info(
            "intent_classifier.ready",
            provider=self._provider.value,
            intents=list(self._intent_centroids.keys()),
            total_examples=sum(
                len(v) for v in self._example_embeddings.values()
            ),
        )

    async def classify(self, utterance: str) -> EmbeddingIntentResult:
        if not self._ready:
            logfire.warning("intent_classifier.not_ready")
            return EmbeddingIntentResult(
                intent="unknown",
                confidence=0.0,
                hint="",
                provider=self._provider.value,
            )

        if not utterance or not utterance.strip():
            return EmbeddingIntentResult(
                intent="unknown",
                confidence=0.0,
                hint="",
                provider=self._provider.value,
            )

        with logfire.span("intent_classifier.classify", utterance=utterance):

            # Embed the caller's utterance
            if self._provider == EmbeddingProvider.LOCAL:
                utterance_embedding = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._embedder.embed,
                    utterance,
                )
            else:
                utterance_embedding = await self._embedder.embed(utterance)

            # Compare against centroids
            similarities: dict[str, float] = {}
            for intent, centroid in self._intent_centroids.items():
                similarities[intent] = _cosine_similarity(
                    utterance_embedding, centroid
                )

            # Blend with max individual example similarity
            for intent, embeddings in self._example_embeddings.items():
                max_sim = max(
                    _cosine_similarity(utterance_embedding, ex)
                    for ex in embeddings
                )
                similarities[intent] = (
                    similarities[intent] * 0.4 + max_sim * 0.6
                )

            # Route only to known intents — unknown is a fallback
            routable = {
                k: v for k, v in similarities.items()
                if k != "unknown"
            }
            top_intent = max(routable, key=routable.get)
            top_confidence = round(routable[top_intent], 3)

            # If top intent is not significantly better than unknown
            # treat it as unknown
            unknown_sim = similarities.get("unknown", 0.0)
            if top_confidence < unknown_sim + 0.02:
                top_intent = "unknown"
                top_confidence = 0.0

            logfire.info(
                "intent_classifier.result",
                utterance=utterance,
                intent=top_intent,
                confidence=top_confidence,
                provider=self._provider.value,
                scores={k: round(v, 3) for k, v in similarities.items()},
            )

            return EmbeddingIntentResult(
                intent=top_intent,
                confidence=top_confidence,
                hint=INTENT_HINTS.get(top_intent, ""),
                provider=self._provider.value,
            )

    def switch_provider(self, provider: EmbeddingProvider) -> None:
        """
        Switch embedding provider at runtime.
        Requires re-initialization after switching.
        """
        logfire.info(
            "intent_classifier.switching_provider",
            from_provider=self._provider.value,
            to_provider=provider.value,
        )
        self._provider = provider
        self._ready = False
        self._embedder = None
        self._example_embeddings = {}
        self._intent_centroids = {}


# ── Singleton ─────────────────────────────────────────────────────────────────

_classifier: Optional[EmbeddingIntentClassifier] = None


def get_classifier() -> EmbeddingIntentClassifier:
    global _classifier
    if _classifier is None:
        _classifier = EmbeddingIntentClassifier(provider=ACTIVE_PROVIDER)
    return _classifier