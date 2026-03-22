import logfire
from src.config.settings import get_settings
from src.config.voices import VOICES

settings = get_settings()


def build_llm_groq():
    """Greeter — ultra-low latency, simple routing task."""
    from livekit.plugins import groq, openai
    try:
        return groq.LLM(
            model=settings.groq_model,
        )
    except Exception as e:
        logfire.warning("llm.groq_failed", error=str(e), fallback="openai")
        return openai.LLM(model=settings.openai_fallback_model)


def build_llm_haiku():
    """Reservation + Takeaway — structured data collection."""
    from livekit.plugins import anthropic, openai
    try:
        return anthropic.LLM(
            model=settings.anthropic_haiku_model,
        )
    except Exception as e:
        logfire.warning("llm.haiku_failed", error=str(e), fallback="openai")
        return openai.LLM(model=settings.openai_fallback_model)


def build_llm_sonnet():
    """Checkout — high stakes payment handling."""
    from livekit.plugins import anthropic, openai
    try:
        return anthropic.LLM(
            model=settings.anthropic_sonnet_model,
        )
    except Exception as e:
        logfire.warning("llm.sonnet_failed", error=str(e), fallback="openai")
        return openai.LLM(model=settings.openai_fallback_model)


def build_llm_openai():
    """OpenAI fallback — used when primary provider fails."""
    from livekit.plugins import openai
    return openai.LLM(model=settings.openai_fallback_model)


def build_stt():
    """Deepgram STT with OpenAI fallback."""
    from livekit.plugins import deepgram, openai
    try:
        return deepgram.STT(model=settings.deepgram_model)
    except Exception as e:
        logfire.warning("stt.deepgram_failed", error=str(e), fallback="openai")
        return openai.STT()


def build_tts(role: str = "greeter"):
    """Cartesia TTS with OpenAI fallback."""
    from livekit.plugins import cartesia, openai
    voice_id = VOICES.get(role, VOICES["greeter"])
    try:
        return cartesia.TTS(
            model=settings.cartesia_model,
            voice=voice_id,
        )
    except Exception as e:
        logfire.warning("tts.cartesia_failed", error=str(e), fallback="openai")
        return openai.TTS(voice="alloy")


def build_vad():
    """Silero VAD — no fallback, required for session."""
    from livekit.plugins import silero
    try:
        return silero.VAD.load()
    except Exception as e:
        logfire.error("vad.load_failed", error=str(e))
        raise RuntimeError("VAD failed to load — cannot start session") from e


def build_llm_cost_aware(userdata=None):
    """
    Checks session cost before selecting a model.
    If cost threshold exceeded — downgrade to cheapest model.
    Falls back to openai if no userdata provided.
    """
    from livekit.plugins import openai

    if userdata and userdata.metrics and userdata.metrics.should_downgrade():
        logfire.warning(
            "resilience.cost_downgrade",
            total_cost=round(userdata.metrics.total_cost_usd, 4),
        )
        return openai.LLM(model=settings.openai_fallback_model)

    return openai.LLM(model=settings.openai_fallback_model)