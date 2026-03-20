import json
import logfire
from datetime import datetime, timezone
from pathlib import Path
from src.core.pii import mask_pii


class TranscriptService:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.turns: list[dict] = []

    def record_turn(
        self,
        role: str,           # "agent" or "user"
        agent_name: str,
        text: str,
    ) -> None:
        self.turns.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role":       role,
            "agent":      agent_name,
            "text":       mask_pii(text),   # never store raw PII
        })

    def save(self, output_dir: str = "transcripts") -> str:
        """Save transcript to disk — in production write to S3/GCS instead."""
        Path(output_dir).mkdir(exist_ok=True)
        filename = f"{output_dir}/{self.session_id}.json"
        with open(filename, "w") as f:
            json.dump({
                "session_id": self.session_id,
                "turns":      self.turns,
                "total_turns": len(self.turns),
            }, f, indent=2)

        logfire.info(
            "transcript.saved",
            session_id=self.session_id,
            turns=len(self.turns),
            path=filename,
        )
        return filename