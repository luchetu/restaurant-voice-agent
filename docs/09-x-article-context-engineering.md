---
title: "Context Engineering for Voice Agents"
description: "How to manage memory, state, retrieval, and prompts in a live phone call — with examples from Wingu"
---

# Context Engineering for Voice Agents

Context engineering is the discipline of deciding what information the model has access to,
when it gets it, and in what form. In a chat application, getting this wrong produces a
confusing conversation. In a voice agent, it produces a broken call.

A voice call has constraints chat does not. The model must respond in under two seconds or
the silence feels like a dropped line. Every token in the context costs latency and money.
The caller cannot scroll up. There is no retry button. What goes into the context window on
every turn is one of the most consequential decisions in a voice agent system.

This article breaks down every layer of context engineering for voice, with examples from
Wingu Restaurant's four-agent system.

---

## 1. Short-Term Memory

Short-term memory is the conversation the model can currently see — the live chat history
in the context window. It is finite, it degrades with age, and it is lost when the call ends.

### The problem

As a call grows, the context window fills. Older messages become noise. The model starts
confusing what the caller said five minutes ago with what they said just now. On a phone
call, this sounds like the agent forgetting things the caller already said — one of the
fastest ways to lose trust.

### Truncation — fast, lossy

The simplest fix is dropping the oldest messages when the window gets full. Keep the last
N turns and discard the rest.

```python
def _truncate_chat_ctx(self, items, keep_last_n=6):
    result = []
    for item in reversed(items):
        if item.type == "message" and item.role == "system":
            continue  # never keep old system messages
        result.append(item)
        if len(result) >= keep_last_n:
            break
    result = result[::-1]

    # never start on a dangling function call
    while result and result[0].type in ["function_call", "function_call_output"]:
        result.pop(0)

    return result
```

Truncation is used on every agent transfer in Wingu. The incoming agent gets the last 6
messages — enough to continue the conversation without dragging the full history forward.

The key rule: **never split a tool call from its result**. If message 6 is a function call
and message 7 is its output, they must travel together or the model will see a call with
no response, which breaks its reasoning.

### Compression — slower, lossless

When the context reaches 70% of the model's safe limit mid-conversation, truncation is
too lossy. The LLM has collected facts across many turns that cannot be dropped. Instead,
compress: ask the model to summarise everything except the most recent messages, then
replace the old turns with that summary.

```python
prompt = (
    "Summarize the following conversation in 3-5 sentences. "
    "Preserve all important facts: customer name, phone number, "
    "order details, reservation details, and any decisions made. "
    "Be concise — this summary will be used as context for continuing "
    "the conversation.\n\n"
    f"{conversation_text}"
)
```

The result is prepended as a system message:

```
[Conversation summary — earlier turns compressed]
Caller gave their name as Amara. She ordered a Margherita Pizza and a water.
She asked to remove the garlic bread. Running total is KES 1,100.
```

The agent continues without re-asking for anything in the summary.

**Rule for compression in voice:** keep the last 4 messages verbatim, always. The most
recent turn is what the caller is currently responding to — summarising it creates
a mismatch between what was just said and what the model thinks it said.

### Context window sizes matter per model

Different models in the same call have different limits. In Wingu:

| Agent | Model | Context limit |
|---|---|---|
| Neema | Groq Llama 3.1 | 8,000 tokens |
| Baraka | Claude Haiku 3.5 | 200,000 tokens |
| Zawadi | Claude Haiku 3.5 | 200,000 tokens |
| Luchetu | Claude Sonnet 3.5 | 200,000 tokens |

Neema's window is the tightest by a factor of 25. She should receive the leanest context
possible — no menu, no order history, no payment state. Her job is routing, and routing
takes three or four turns.

---

## 2. Long-Term Memory

Long-term memory is anything that persists beyond the current call. It is not in the
context window — it is retrieved and injected at the right moment.

### What belongs in long-term memory for a restaurant

- Past orders (caller's usual order)
- Reservation history (how often they book, average party size)
- Known preferences (allergens, seating preference)
- Name and phone number (so Neema can greet them by name)

### How to inject it

Long-term memory should not be dumped into the system prompt wholesale. Inject only what
is relevant to the current call, as a compact context note at session start:

```
Returning caller. Name: Amara. Last order: Pepperoni Pizza, Coffee (3 weeks ago).
Known allergen: gluten. Usual party size: 2.
```

Seven words of long-term memory are worth more than seven paragraphs of instructions.
The model uses the specific fact. It ignores the generic rule.

### What Wingu currently does

Wingu does not yet have long-term memory. The `greeter_returning.yaml` prompt variant
is loaded when the caller's name is already in session state — but that only works within
a session, not across calls. A database lookup at call start is the missing piece.

### The latency rule

Long-term memory retrieval must complete before the first agent speaks. A caller who dials
in and waits three seconds before hearing a greeting has already had a bad experience.

Retrieval budget: **under 300ms**. If your database query or vector search takes longer
than that, pre-fetch on the SIP event before the audio session opens.

---

## 3. State Management

State is different from memory. Memory is what was said. State is what was decided.

In a multi-agent voice system, state is the single most important thing to get right. When
Zawadi hands off to Luchetu, Luchetu does not read the conversation — she reads the state.

### Session state as the source of truth

Every fact the system cares about — customer name, order items, reservation date, payment
status — lives in one validated object. Tool calls write to it. Agent context reads from it.
The conversation is just the mechanism for collecting it.

```python
class UserData(BaseModel):
    session_id: str
    customer: CustomerInfo       # name, phone
    order: Order                 # items, total, status
    reservation: Reservation     # date, time, party_size, status
    payment: PaymentInfo         # card (SecretStr), expiry, cvv
    metrics: SessionMetrics
    audit: AuditLogger
```

This object is mutated by tool calls and never reconstructed from the conversation. If the
context is compressed or truncated, the state is unaffected. The facts survive.

### Tool calls as the write interface

The model does not update state by writing text — it calls a function. The function
validates the value and writes it to the state object.

```python
@function_tool
async def update_party_size(size: int, context: RunContext_T) -> str:
    if not 1 <= size <= 20:
        return f"Party size must be between 1 and 20. You said {size}."
    context.userdata.reservation.party_size = size
    return f"Got it — party of {size}."
```

This matters for two reasons. First, invalid values never reach the state. Second, the
state is always inspectable — you can read `userdata.reservation.party_size` at any point
and trust it is a valid integer between 1 and 20.

### Agent-scoped context injection

When an agent enters, it receives only the state fields it needs. Neema does not see payment
status. Baraka does not see order items. This is not just a privacy measure — it prevents
the model from reasoning about things outside its scope.

```python
AGENT_CONTEXT_FIELDS = {
    "GreeterAgent":     ["customer_name", "customer_phone"],
    "ReservationAgent": ["customer_name", "customer_phone", "reservation"],
    "TakeawayAgent":    ["customer_name", "order"],
    "CheckoutAgent":    ["customer_name", "customer_phone", "order", "payment_status"],
}
```

The state is injected as a system message at `on_enter`:

```
Customer name: Amara
Order: Margherita Pizza x1 (KES 1,000), Water x1 (KES 100). Total: KES 1,100. Status: CONFIRMED.
Payment: pending
```

Luchetu reads this and knows exactly where she is picking up. She does not need to ask
what the order is. She does not need to re-read the conversation.

### Handoff reason as micro-context

Every transfer carries a reason string:

```python
await self._transfer_to_agent(
    "CheckoutAgent",
    context,
    reason="Order confirmed. Caller ready to pay.",
)
```

This is injected at the top of the incoming agent's context:

```
Transfer reason: Order confirmed. Caller ready to pay.
```

Three seconds after picking up, the model knows why it is there. Without this, the agent
has to infer intent from the conversation history — which may have been truncated.

---

## 4. RAG for Voice Agents

Retrieval-Augmented Generation (RAG) is the practice of fetching external knowledge and
injecting it into the context before the model responds. In voice, RAG has one hard
constraint: **it must complete before the model starts generating**.

A retrieval step that takes 800ms is fine in chat. In voice, it means 800ms of silence —
which sounds like a dropped call.

### Static RAG — inject once, reuse

Some knowledge does not change during a call. The menu is the clearest example. Retrieve
it once at session start (or at server startup), inject it into the relevant agent's
context, and never fetch it again.

```python
@lru_cache()
def get_menu_summary() -> str:
    with open("data/menu.json") as f:
        menu = json.load(f)
    lines = []
    for item in menu:
        allergens = ", ".join(item["allergens"]) or "none"
        lines.append(f"{item['name']} — KES {item['price']:.0f} (allergens: {allergens})")
    return "\n".join(lines)
```

Inject only into agents that need it. Zawadi needs the menu. Baraka and Neema do not.
Every token injected into Neema's 8K window is a token she cannot use for conversation.

### Dynamic RAG — fetch per query

Some knowledge changes between turns. Available time slots, daily specials, table
availability. These cannot be cached at session start — they must be fetched when the
caller asks.

The pattern for dynamic RAG in voice:

1. The model detects the intent (caller asks for available times)
2. A function tool fires — **not** the model itself making an API call
3. The tool fetches the data and returns it as a short string
4. The model reads the string and speaks the answer

```python
@function_tool
async def check_availability(date: str, context: RunContext_T) -> str:
    slots = await reservation_service.get_available_slots(date)
    if not slots:
        return f"No availability on {date}. Nearest available: {slots.next_date}."
    return f"Available times on {date}: {', '.join(slots)}."
```

The tool result is the RAG. It lands in the context as a function output message. The
model reads it and answers. Total added latency: one database query.

### Retrieval latency budget for voice

| Operation | Max latency | Strategy |
|---|---|---|
| Long-term caller profile | 300ms | Pre-fetch on SIP event |
| Static knowledge (menu) | 0ms | Cache at startup |
| Dynamic lookup (availability) | 500ms | Tool call mid-turn |
| Vector search (FAQ, policy) | 400ms | Tool call, not system prompt |

If a retrieval step cannot meet its budget, move it earlier or cache it. Never block the
model's first response on a slow fetch.

### What not to RAG

Do not inject documents, policy text, or FAQs into the system prompt. The model will
treat them as instructions and may read them aloud or let them shape its persona in
unexpected ways. If a caller asks something that requires document lookup, use a tool
call to fetch the specific answer and return it as a short string.

---

## 5. Prompt Engineering for Context

The system prompt is not just instructions — it is the first item in the context window on
every turn. How it is written determines how much room is left for everything else.

### Keep prompts short

A long system prompt has two costs: tokens and attention. Every token in the system prompt
is a token not available for conversation history. And a model reading a 2,000-token
system prompt before every turn gives less attention to the recent conversation.

Wingu's prompts average under 100 tokens each. That leaves the vast majority of even
Neema's 8K window for the conversation.

### Separate stable instructions from runtime context

The system prompt should contain only things that are true for every call this agent
handles. Everything else — caller name, current order, time of day — is injected at
runtime as a separate system message.

```
# System prompt (stable — loaded once)
You are Baraka, the reservations specialist at Wingu Restaurant. Your job is
to book a table for the caller...

# Runtime context (injected at on_enter — changes every call)
Customer name: Amara
Reservation: date=Saturday 12 April, time=not set, party_size=not set. Status: PENDING.
Transfer reason: Caller wants to book a table for this weekend.
```

The model reads both. The first shapes who it is. The second tells it where it is.

### Prompt variants as context signals

A prompt variant is a lightweight form of context injection at the prompt level. Instead
of a conditional block inside one prompt, you load a different prompt entirely.

```python
if customer_name:
    return load_prompt("greeter_returning")   # "Welcome back, Amara..."
elif 11 <= hour < 15:
    return load_prompt("greeter_lunch")       # "Quick lunch order today?"
elif 18 <= hour < 22:
    return load_prompt("greeter_dinner")      # "Good evening..."
else:
    return load_prompt("greeter")             # Default
```

Each variant is a short, focused brief for a specific context. No branching logic inside
the prompt. No conditionals the model has to interpret.

---

## 6. Context Drift and Persona Stability

On long calls, models drift. The agent starts strong and gradually shifts tone, forgets
constraints, or begins improvising outside its scope. This is a context problem — the
early instructions are diluted by the volume of conversation that follows.

### Signs of drift in a voice call

- The agent starts taking details it was told to transfer to a specialist
- Responses get longer as the call progresses
- The agent breaks a guardrail it followed at the start of the call

### How to prevent it

**Short calls are the best defence.** Each Wingu agent owns a narrow slice of the call.
Neema routes in two or three turns. Baraka collects three fields. No single agent runs
long enough to drift significantly.

**Re-inject identity on every turn if needed.** For agents that run longer (Zawadi,
Luchetu), a brief identity note in the system message on `on_enter` anchors the model:

```
You are Zawadi, the takeaway order taker at Wingu Restaurant.
```

This fires every time the agent enters — not just at session start.

**Watch response length as a drift signal.** An agent whose responses are getting longer
over the course of a call is usually drifting. `OutputValidator` catches responses over
300 words, but rising average length before that threshold is worth monitoring in Logfire.

---

## 7. PII in Context

Sensitive data in the context window is sensitive data the model can repeat. Voice agents
collect more PII than most chat applications — names, phone numbers, card details.

### Rules for Wingu

- Card number, expiry, and CVV are stored as `SecretStr` — they cannot be serialised or
  logged without an explicit `.get_secret_value()` call
- PII is masked before any string is written to the transcript or audit log
- Luchetu is the only agent whose `AGENT_CONTEXT_FIELDS` includes payment — and even she
  only receives `payment_status: pending/complete`, not the card details themselves
- The model is instructed never to repeat the full card number — only the last four digits

### What the model should never see in context

- Full card numbers in conversation history
- CVV at any point after collection
- Any PII in a compressed summary (the compression prompt explicitly excludes PII fields
  by design — they live in `PaymentInfo`, not in the chat messages)

---

## Summary

| Layer | What it manages | Key principle |
|---|---|---|
| Short-term memory | Live chat history | Truncate on transfer, compress at 70% |
| Long-term memory | Cross-call caller knowledge | Pre-fetch before first agent speaks |
| State management | Facts collected during the call | Write via tools, read via scoped injection |
| RAG | External knowledge on demand | Static at startup, dynamic via tool calls |
| Prompt engineering | Model instructions and identity | Short, stable, runtime context separate |
| Drift prevention | Persona and guardrail stability | Narrow agent scope, re-inject identity |
| PII handling | Sensitive data in context | SecretStr, mask before log, scope by agent |

The throughline across all of these is the same: **give the model exactly what it needs
for this turn, nothing more, and trust the state object to hold everything else.**
