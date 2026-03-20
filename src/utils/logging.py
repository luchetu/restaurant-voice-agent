import logfire
from src.config.settings import get_settings


def setup_logging() -> None:
    settings = get_settings()
    logfire.configure(
        service_name="restaurant-voice-agent",
        environment=settings.environment,
        token=settings.logfire_token if settings.logfire_token else None,
        send_to_logfire="if-token-present",
    )
    logfire.instrument_pydantic()


def get_logger(name: str):
    return logfire