import logfire

from src.core.token_counter import (
    context_usage_percent,
    should_compress,
)

COMPRESSION_THRESHOLD = 70.0  # compress when context is 70% full
KEEP_RECENT_MESSAGES = 4  # always keep last 4 messages uncompressed


class ContextManager:
    """
    Manages conversation context across agent turns.

    Two strategies:
    1. Truncation  — drop oldest messages (fast, lossy)
    2. Compression — summarize oldest messages (slower, lossless)

    Compression requires an LLM call but preserves semantic content.
    Truncation is the fallback when compression is not available.
    """

    def __init__(self, model: str, session_id: str):
        self.model = model
        self.session_id = session_id
        self._compressions_done = 0

    def should_compress(self, messages: list) -> bool:
        return should_compress(messages, self.model, COMPRESSION_THRESHOLD)

    def get_usage(self, messages: list) -> float:
        return context_usage_percent(messages, self.model)

    async def compress(self, messages: list, llm) -> list:
        """
        Summarize old messages and replace them with a summary message.
        Always keeps the most recent KEEP_RECENT_MESSAGES intact.

        Before compression:
          [msg1, msg2, msg3, msg4, msg5, msg6, msg7, msg8]

        After compression:
          [summary_of_1_to_4, msg5, msg6, msg7, msg8]
        """
        if len(messages) <= KEEP_RECENT_MESSAGES:
            return messages

        # Split into old (to summarize) and recent (to keep)
        split_point = len(messages) - KEEP_RECENT_MESSAGES
        old_messages = messages[:split_point]
        recent_messages = messages[split_point:]

        usage_before = self.get_usage(messages)

        logfire.info(
            "context_manager.compressing",
            session_id=self.session_id,
            messages_total=len(messages),
            messages_to_compress=len(old_messages),
            usage_before=usage_before,
            model=self.model,
        )

        # Build summary prompt from old messages
        conversation_text = self._messages_to_text(old_messages)
        summary = await self._summarize(conversation_text, llm)

        # Replace old messages with summary
        from livekit.agents.llm import ChatMessage

        summary_message = ChatMessage.create(
            role="system",
            text=f"[Conversation summary — earlier turns compressed]\n{summary}",
        )

        compressed = [summary_message] + recent_messages
        usage_after = self.get_usage(compressed)
        self._compressions_done += 1

        logfire.info(
            "context_manager.compressed",
            session_id=self.session_id,
            messages_before=len(messages),
            messages_after=len(compressed),
            usage_before=usage_before,
            usage_after=usage_after,
            compressions_done=self._compressions_done,
        )

        return compressed

    def truncate(self, messages: list, keep_last_n: int = 6) -> list:
        """
        Simple truncation — drop oldest messages.
        Fast but lossy — older context is gone.
        Use when compression is not available or context is not too full.
        """
        if len(messages) <= keep_last_n:
            return messages

        truncated = messages[-keep_last_n:]

        # Never start with a dangling function call
        while truncated and truncated[0].type in ["function_call", "function_call_output"]:
            truncated.pop(0)

        logfire.info(
            "context_manager.truncated",
            session_id=self.session_id,
            messages_before=len(messages),
            messages_after=len(truncated),
        )

        return truncated

    async def maybe_compress(self, messages: list, llm=None) -> list:
        """
        Check if compression is needed and compress if so.
        Falls back to truncation if no LLM provided.
        """
        if not self.should_compress(messages):
            return messages

        if llm is not None:
            try:
                return await self.compress(messages, llm)
            except Exception as e:
                logfire.warning(
                    "context_manager.compression_failed",
                    error=str(e),
                    fallback="truncation",
                )

        # Fallback to truncation
        return self.truncate(messages)

    def _messages_to_text(self, messages: list) -> str:
        """Convert message objects to plain text for summarization."""
        lines = []
        for msg in messages:
            role = getattr(msg, "role", "unknown")
            content = getattr(msg, "content", "") or ""
            if isinstance(content, str) and content.strip():
                # Skip system messages — they are instructions not conversation
                if role != "system":
                    lines.append(f"{role.upper()}: {content.strip()}")
        return "\n".join(lines)

    async def _summarize(self, conversation_text: str, llm) -> str:
        """
        Use the LLM to summarize a block of conversation.
        Returns a concise summary preserving key facts.
        """
        prompt = (
            "Summarize the following conversation in 3-5 sentences. "
            "Preserve all important facts: customer name, phone number, "
            "order details, reservation details, and any decisions made. "
            "Be concise — this summary will be used as context for continuing "
            "the conversation.\n\n"
            f"{conversation_text}"
        )

        # Use a simple completion — not a full chat turn
        messages = [{"role": "user", "content": prompt}]

        try:
            response = await llm.chat(messages=messages)
            return response.choices[0].message.content or "No summary available."
        except Exception as e:
            logfire.warning("context_manager.summarize_failed", error=str(e))
            return f"Earlier conversation compressed. Key points may be lost."
