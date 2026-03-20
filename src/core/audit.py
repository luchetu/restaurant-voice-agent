import logfire
from datetime import datetime, timezone
from enum import Enum
from src.core.pii import mask_pii


class AuditAction(Enum):
    SESSION_START  = "session_start"
    SESSION_END    = "session_end"
    AGENT_ENTER    = "agent_enter"
    AGENT_EXIT     = "agent_exit"
    TRANSFER       = "transfer"
    TOOL_CALL      = "tool_call"
    ESCALATE       = "escalate"
    ORDER_PLACED   = "order_placed"
    PAYMENT        = "payment"


class AuditLogger:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._events: list[dict] = []

    def log(
        self,
        action: AuditAction,
        agent: str,
        detail: str = "",
        customer_phone: str = "",
    ) -> None:
        event = {
            "timestamp":      datetime.now(timezone.utc).isoformat(),
            "session_id":     self.session_id,
            "action":         action.value,
            "agent":          agent,
            "detail":         mask_pii(detail),
            "customer_phone": mask_pii(customer_phone),
        }
        self._events.append(event)

        # Logfire span — shows up in dashboard with all fields
        logfire.info(
            "audit.{action}",
            action=action.value,
            session_id=self.session_id,
            agent=agent,
            detail=mask_pii(detail),
        )

    def all_events(self) -> list[dict]:
        return list(self._events)

    def session_summary(self) -> dict:
        return {
            "session_id":   self.session_id,
            "total_events": len(self._events),
            "actions":      [e["action"] for e in self._events],
        }