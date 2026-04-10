---
title: "Session & Context Management"
description: "How a session starts and ends, how context is kept tight across long calls, and how costs are controlled in real time"
---

# Session & Context Management

A session is one phone call — from the moment LiveKit dispatches the agent to the moment
the caller hangs up or a limit is hit. Everything the system knows about that call lives
in a single shared object for its entire duration.

---

## Session Startup

When a call arrives, `src/main.py` runs the following in order before any agent speaks:

1. **Generate a session ID** — a UUID that identifies this call in every log, audit event,
   and transcript file for its lifetime
2. **Initialise `UserData`** — creates fresh `Order`, `Reservation`, `PaymentInfo`,
   `CustomerInfo`, `SessionMetrics`, `AuditLogger`, and `TranscriptService` objects all
   bound to that session ID
3. **Build the agent registry** — instantiates all four agents (Neema, Baraka, Zawadi,
   Luchetu) and stores them in `UserData.agents`
4. **Classify intent** — runs the first utterance through the intent router before any
   agent responds (see [Intent Routing](./03-intent-routing))
5. **Start Neema** — the greeter agent always takes the first turn unless the intent
   classifier is confident enough to direct-route

---

## Provider Fallbacks

Every component has a fallback configured in `src/core/resilience.py`. If a primary
provider fails, the system switches silently — the caller hears no gap.

| Component | Primary | Fallback |
|---|---|---|
| Speech-to-text | Deepgram Nova-2 | OpenAI Whisper |
| Greeter LLM | Groq Llama 3.1 | OpenAI GPT-4o-mini |
| Reservation / Takeaway LLM | Haiku 3.5 | OpenAI GPT-4o-mini |
| Checkout LLM | Sonnet 3.5 | OpenAI GPT-4o-mini |
| Text-to-speech | Cartesia Sonic-2 | OpenAI TTS |
| Intent embeddings | Local `all-MiniLM-L6-v2` | OpenAI `text-embedding-3-small` |
| Voice activity detection | Silero | **None — required** |

VAD has no fallback. The system cannot determine when the caller has stopped speaking
without it, so the session cannot continue. All other components degrade gracefully.

Fallbacks use `tenacity` for retry logic with exponential backoff before switching provider.

---

## Context Window Management

LLM context windows are finite. On a long call — especially one with menu browsing, order
changes, and a return to Neema — the chat history can grow large enough to threaten the
model's context limit. `src/core/context_manager.py` monitors this and intervenes before
it becomes a problem.

### Token tracking

`src/core/token_counter.py` estimates token usage using a fast approximation:

```
tokens ≈ character_count / 4
```

This runs on every message without any API call. Context usage is tracked as a percentage
of the model's safe limit, which reserves 20% headroom below the hard context ceiling.

| Model | Context limit | Safe limit (80%) |
|---|---|---|
| Haiku 3.5 | 200,000 tokens | 160,000 tokens |
| Sonnet 3.5 | 200,000 tokens | 160,000 tokens |
| OpenAI GPT-4o-mini | 128,000 tokens | 102,400 tokens |
| Groq Llama 3.1 | 8,000 tokens | 6,400 tokens |

Groq's context window is the tightest. Neema is intentionally a short-lived agent —
she greets, classifies, and transfers — so this limit is rarely a concern in practice.

### When context management triggers

At **≥ 70% of the safe limit**, the context manager intervenes. It tries compression
first. If compression itself fails (e.g. the LLM is unavailable), it falls back to
truncation.

### Compression

The LLM is asked to summarise everything except the most recent 4 messages. The summary
replaces the old messages as a single `system` turn. Rules:

- The last 4 messages are always kept verbatim and uncompressed
- Tool call and tool result pairs are never split across the compression boundary
- The resulting summary is prepended as a `system` message the agent can read

The caller notices nothing. The agent retains the semantic content of the conversation
without carrying every raw message forward.

### Truncation

Used as a fallback when compression fails, and also on every agent transfer. The last
**6 messages** are kept. Everything older is dropped. Tool call / tool result pairs are
preserved intact.

Truncation is fast and lossy — it discards wording but not state. Session state
(`UserData`) is separate from chat history and is never truncated. The order, reservation,
and customer details are always complete regardless of how much history was dropped.

---

## Cost Controls

Every LLM call is costed in real time using `src/core/metrics.py`. Costs are estimated
from token counts and per-model pricing:

| Model | Input | Output |
|---|---|---|
| Groq Llama 3.1 | $0.05 / M tokens | $0.08 / M tokens |
| Haiku 3.5 | $0.80 / M tokens | $4.00 / M tokens |
| Sonnet 3.5 | $3.00 / M tokens | $15.00 / M tokens |
| OpenAI GPT-4o-mini | $0.15 / M tokens | $0.60 / M tokens |

Three thresholds trigger automatic actions as the running total climbs:

| Threshold | Action |
|---|---|
| **$0.10** | Model downgrade — remaining turns use GPT-4o-mini instead of the assigned model |
| **$0.25** | Alert — a warning event is emitted to Logfire |
| **$0.50** | Hard limit — the session ends gracefully; the caller is thanked and disconnected |

The downgrade at $0.10 is the most important. A session that reaches it has already
spent more than a typical call costs in full. Switching to GPT-4o-mini lets the call
complete without compounding the overspend.

`build_llm_cost_aware()` in `src/core/resilience.py` checks the session cost before
every LLM call and returns the appropriate model.

---

## Session End

A session ends in one of four ways — see [Conversation Flow](./02-conversation-flow) for
the full breakdown. In all cases the shutdown sequence is the same:

1. `SessionMetrics.finalize()` — computes total cost, token counts, per-agent durations,
   transfer count, and error counts
2. `TranscriptService.save()` — writes the PII-masked transcript to
   `transcripts/{session_id}.json`
3. Audit log — a `SESSION_END` event with the final cost summary is published to Logfire

Nothing is written to a database in the current implementation. Orders, reservations, and
customer details exist only in the transcript and audit log until the backend service
integrations are completed.
