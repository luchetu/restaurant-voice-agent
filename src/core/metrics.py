import time
from dataclasses import dataclass, field

import logfire


# Cost per 1M tokens as of 2025
MODEL_PRICING = {
    "llama-3.1-8b-instant":  {"input": 0.05,  "output": 0.08},
    "claude-haiku-3-5":      {"input": 0.80,  "output": 4.00},
    "claude-sonnet-3-5":     {"input": 3.00,  "output": 15.00},
    "gpt-4o-mini":           {"input": 0.15,  "output": 0.60},
    "gpt-4o":                {"input": 5.00,  "output": 15.00},
    "gpt-3.5-turbo":         {"input": 0.50,  "output": 1.50},
}

# Budget thresholds per session
DOWNGRADE_THRESHOLD_USD = 0.10   # downgrade models above this cost
ALERT_THRESHOLD_USD     = 0.25   # log warning above this cost
MAX_SESSION_COST_USD    = 0.50   # hard limit — end session above this


@dataclass
class SessionMetrics:
    session_id: str
    start_time: float = field(default_factory=time.monotonic)

    # Counters
    total_turns:      int   = 0
    total_transfers:  int   = 0
    total_tool_calls: int   = 0
    llm_errors:       int   = 0
    tts_errors:       int   = 0

    # Cost tracking
    total_cost_usd:       float = 0.0
    total_input_tokens:   int   = 0
    total_output_tokens:  int   = 0
    cost_downgraded:      bool  = False

    # Agent time tracking
    agent_durations: dict[str, float] = field(default_factory=dict)
    _agent_start:    float            = 0.0

    def record_llm_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        agent_name: str,
    ) -> None:
        """Track token usage and cost after every LLM call."""
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["gpt-4o-mini"])
        cost = (
            input_tokens  * pricing["input"]  / 1_000_000 +
            output_tokens * pricing["output"] / 1_000_000
        )

        self.total_cost_usd      += cost
        self.total_input_tokens  += input_tokens
        self.total_output_tokens += output_tokens

        logfire.info(
            "metric.llm_usage",
            model=model,
            agent=agent_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost, 6),
            total_cost_usd=round(self.total_cost_usd, 6),
            session_id=self.session_id,
        )

        # Check thresholds
        self._check_cost_thresholds()

    def _check_cost_thresholds(self) -> None:
        if self.total_cost_usd >= ALERT_THRESHOLD_USD:
            logfire.warning(
                "metric.cost_alert",
                total_cost_usd=round(self.total_cost_usd, 4),
                session_id=self.session_id,
            )

    def should_downgrade(self) -> bool:
        """
        Returns True when session cost exceeds downgrade threshold.
        Once downgraded, stays downgraded for the rest of the session.
        """
        if self.cost_downgraded:
            return True
        if self.total_cost_usd >= DOWNGRADE_THRESHOLD_USD:
            self.cost_downgraded = True
            logfire.warning(
                "metric.cost_downgrade",
                total_cost_usd=round(self.total_cost_usd, 4),
                threshold=DOWNGRADE_THRESHOLD_USD,
                session_id=self.session_id,
            )
            return True
        return False

    def should_end_session(self) -> bool:
        """Hard limit — session has exceeded maximum allowed cost."""
        return self.total_cost_usd >= MAX_SESSION_COST_USD

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
            total=self.total_transfers,
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

    def finalize(self) -> dict:
        total_duration = time.monotonic() - self.start_time
        summary = {
            "session_id":         self.session_id,
            "duration_seconds":   round(total_duration, 2),
            "total_turns":        self.total_turns,
            "total_transfers":    self.total_transfers,
            "total_tool_calls":   self.total_tool_calls,
            "llm_errors":         self.llm_errors,
            "total_cost_usd":     round(self.total_cost_usd, 6),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens":self.total_output_tokens,
            "cost_downgraded":    self.cost_downgraded,
            "agent_durations":    self.agent_durations,
        }
        logfire.info("metric.session_end", **summary)
        return summary