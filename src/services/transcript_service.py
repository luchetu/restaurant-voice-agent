import json
from datetime import datetime, timezone
from pathlib import Path

import logfire
from livekit.agents.voice import AgentSession

from src.core.pii import mask_pii


class TranscriptService:
    """
    Listens to LiveKit's built-in transcription events
    and saves a PII-masked copy when the session ends.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._turns: list[dict] = []

    def attach(self, session: AgentSession) -> None:
        """
        Hook into LiveKit's conversation_item_added event.
        Fires every time a turn is committed to chat history —
        both user speech and agent responses.
        """
        @session.on("conversation_item_added")
        def on_item_added(item) -> None:
            # item has role ("user" or "assistant") and content
            role = getattr(item, "role", "unknown")
            content = getattr(item, "text_content", "") or ""

            if not content:
                return

            self._turns.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "role":      role,
                "text":      mask_pii(content),
            })

            logfire.info(
                "transcript.turn",
                session_id=self.session_id,
                role=role,
                length=len(content),
            )

    @property
    def total_turns(self) -> int:
        return len(self._turns)

    def save(self, output_dir: str = "transcripts") -> str:
        """Save full transcript to disk as JSON."""
        Path(output_dir).mkdir(exist_ok=True)
        filename = f"{output_dir}/{self.session_id}.json"

        payload = {
            "session_id":  self.session_id,
            "total_turns": self.total_turns,
            "saved_at":    datetime.now(timezone.utc).isoformat(),
            "turns":       self._turns,
        }

        with open(filename, "w") as f:
            json.dump(payload, f, indent=2)

        logfire.info(
            "transcript.saved",
            session_id=self.session_id,
            turns=self.total_turns,
            path=filename,
        )
        return filename