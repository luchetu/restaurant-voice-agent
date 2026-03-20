import logfire
from src.config.settings import get_settings
from src.config.voices import VOICES


def build_stt():
    from livekit.plugins import deepgram, openai
    settings = get_settings()
    try:
        return deepgram.STT(model=settings.deepgram_model)
    except Exception as e:
        logfire.warning("stt.primary_failed", error=str(e))
        return openai.STT()


def build_llm(model: str | None = None):
    from livekit.plugins import openai
    settings = get_settings()
    try:
        return openai.LLM(
            model=model or settings.openai_model,
            temperature=0.3,
        )
    except Exception as e:
        logfire.warning("llm.primary_failed", error=str(e))
        return openai.LLM(model="gpt-3.5-turbo", temperature=0.3)


def build_tts(role: str = "greeter"):
    from livekit.plugins import cartesia, openai
    settings = get_settings()
    voice_id = VOICES.get(role, VOICES["greeter"])
    try:
        return cartesia.TTS(
            model=settings.cartesia_model,
            voice=voice_id,
        )
    except Exception as e:
        logfire.warning("tts.primary_failed", error=str(e))
        return openai.TTS(voice="alloy")


def build_vad():
    from livekit.plugins import silero
    try:
        return silero.VAD.load()
    except Exception as e:
        logfire.error("vad.load_failed", error=str(e))
        raise RuntimeError("VAD failed to load") from e