import logfire
from dotenv import load_dotenv

from livekit.agents import JobContext, cli
from livekit.agents.voice import AgentSession
from livekit.agents import AgentServer

from src.config.settings import get_settings
from src.core.audit import AuditLogger, AuditAction
from src.core.resilience import build_stt, build_llm, build_tts, build_vad
from src.models.session import UserData
from src.agents.greeter import GreeterAgent
from src.agents.reservation import ReservationAgent
from src.agents.takeaway import TakeawayAgent
from src.agents.checkout import CheckoutAgent
from src.utils.logging import setup_logging
from src.core.metrics import SessionMetrics
from src.services.transcript_service import TranscriptService

load_dotenv(".env.local")
setup_logging()

settings = get_settings()
server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session_id = ctx.room.name

    # ── Audit ──────────────────────────────────────────────
    audit = AuditLogger(session_id=session_id)

    # ── Build UserData ─────────────────────────────────────
    userdata = UserData(
        session_id=session_id,
        ctx=ctx,
        audit=audit,
        metrics=SessionMetrics(session_id=session_id),
        transcript=TranscriptService(session_id=session_id),
    )

    # ── Instantiate all agents ─────────────────────────────
    greeter     = GreeterAgent()
    reservation = ReservationAgent()
    takeaway    = TakeawayAgent()
    checkout    = CheckoutAgent()

    # ── Register agents in the shared registry ─────────────
    userdata.agents.update({
        "greeter":     greeter,
        "reservation": reservation,
        "takeaway":    takeaway,
        "checkout":    checkout,
    })

    # ── Build session ──────────────────────────────────────
    session = AgentSession[UserData](
        userdata=userdata,
        stt=build_stt(),
        llm=build_llm(),
        tts=build_tts("greeter"),
        vad=build_vad(),
        max_tool_steps=settings.max_tool_steps,
    )

    audit.log(
        action=AuditAction.SESSION_START,
        agent="system",
        detail=f"room={ctx.room.name}",
    )
    logfire.info(
        "session.start",
        session_id=session_id,
        room=ctx.room.name,
    )

    # ── Start with the greeter ─────────────────────────────
    await session.start(
        agent=greeter,
        room=ctx.room,
    )
    userdata.metrics.finalize()
    userdata.transcript.save()


if __name__ == "__main__":
    cli.run_app(server)