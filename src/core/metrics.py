import time
import logfire
from dataclasses import dataclass, field
from src.core.pii import mask_pii


@dataclass
class SessionMetrics:
    session_id: str
    start_time: float = field(default_factory=time.monotonic)

    # Counters
    total_turns: int = 0
    total_transfers: int = 0
    total_tool_calls: int = 0
    llm_errors: int = 0
    tts_errors: int = 0

    # Agent time tracking
    agent_durations: dict[str, float] = field(default_factory=dict)
    _agent_start: float = 0.0

    def agent_started(self, agent_name: str) -> None:
        self._agent_start = time.monotonic()

    def agent_ended(self, agent_name: str) -> None:
        if self._agent_start:
            duration = time.monotonic() - self._agent_start
            self.agent_durations[agent_name] = round(duration, 2)
            logfire.info(
                "metric.agent_duration",
                agent=agent_name,
                duration_seconds=duration,
                session_id=self.session_id,
            )

    def record_transfer(self, from_agent: str, to_agent: str) -> None:
        self.total_transfers += 1
        logfire.info(
            "metric.transfer",
            from_agent=from_agent,
            to_agent=to_agent,
            total_transfers=self.total_transfers,
            session_id=self.session_id,
        )

    def record_turn(self) -> None:
        self.total_turns += 1

    def record_tool_call(self, tool_name: str) -> None:
        self.total_tool_calls += 1
        logfire.info(
            "metric.tool_call",
            tool=tool_name,
            session_id=self.session_id,
        )

    def record_llm_error(self, error: str) -> None:
        self.llm_errors += 1
        logfire.error(
            "metric.llm_error",
            error=mask_pii(error),
            session_id=self.session_id,
        )

    def finalize(self) -> dict:
        total_duration = time.monotonic() - self.start_time
        summary = {
            "session_id":       self.session_id,
            "duration_seconds": round(total_duration, 2),
            "total_turns":      self.total_turns,
            "total_transfers":  self.total_transfers,
            "total_tool_calls": self.total_tool_calls,
            "llm_errors":       self.llm_errors,
            "tts_errors":       self.tts_errors,
            "agent_durations":  self.agent_durations,
        }
        logfire.info("metric.session_end", **summary)
        return summary