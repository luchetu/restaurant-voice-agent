---
title: "Restaurant Voice Agent"
description: "A multi-agent voice assistant that handles restaurant calls — reservations, takeaway orders, and payment — over a live phone line"
---

# Restaurant Voice Agent

Wingu's voice assistant answers the phone so staff don't have to. Callers speak
naturally — no button menus, no hold music, no scripted trees. The system understands
what they want and routes them to the right specialist agent automatically.

Three things a caller can do on a single number:

- **Book a table** — date, time, party size, confirmed in under a minute
- **Place a takeaway order** — browse the menu by voice, add or remove items, hear the total
- **Pay for their order** — card details collected securely, order reference issued before they hang up

---

## How It Works

The system is built on **four specialist agents**, each powered by a different language model
chosen for the demands of its role. Calls always start with Neema. She listens to the first
thing the caller says, works out their intent, and hands them to the right agent — or goes
straight there if she is confident enough.

| Agent | Model | Role |
|---|---|---|
| **Neema** | Groq Llama 3.1 8B | Answers the call, classifies intent, routes to the right agent |
| **Baraka** | Haiku 3.5 | Collects reservation details — date, time, party size |
| **Zawadi** | Haiku 3.5 | Takes the food order, upsells naturally, confirms before checkout |
| **Luchetu** | Sonnet 3.5 | Collects payment, masks card details, issues the order reference |

When a caller is done with one thing and wants another — say, they booked a table and now
want to add a takeaway — any agent can hand back to Neema. Context travels with every
transfer so the caller never has to repeat themselves.

---

## A Call From Start to Finish

1. **The phone rings.** Neema greets the caller. If the first thing they say makes their
   intent clear (e.g. "I'd like to book a table for two"), she transfers immediately without
   asking follow-up questions.

2. **Reservation path.** Baraka takes over. He asks for the date, time, and number of guests.
   Once all three are confirmed he reads the booking back, and the call can end or return to Neema.

3. **Takeaway path.** Zawadi takes over. She presents the menu conversationally, adds items as
   the caller requests them, suggests drinks or dessert if appropriate, then reads back the
   full order with the total before asking to confirm.

4. **Checkout.** Luchetu takes over from Zawadi. He confirms the caller's name and phone, then
   collects the card number, expiry, and CVV — one field at a time. He reads back only the
   last four digits for confirmation, issues an order reference, and closes the call.

---

## What Makes It Production-Ready

**Cost-aware routing.** Every LLM call is costed in real time. If a session is running
expensive, the system quietly downgrades to a cheaper model mid-call. There is a hard
spending limit per session — the call ends gracefully if it is hit.

**Prompt variants.** Neema's greeting changes automatically by time of day (lunch, dinner,
default) and whether the caller's name is already known (returning customer). No code change
needed — it is all YAML.

**PII never reaches the logs.** Phone numbers, card numbers, CVVs, and emails are scrubbed
before anything is written to disk or sent to an external service. Card details are stored as
`SecretStr` and only the last four digits are ever spoken back.

**Resilient by default.** Every provider has a fallback. If Deepgram is down, OpenAI Whisper
takes over. If Groq is down, OpenAI handles the greeter. The only hard dependency with no
fallback is voice activity detection — the call cannot work without knowing when the caller
stops speaking.

---

## Tech Stack

| Layer | Primary | Fallback |
|---|---|---|
| Agent framework | LiveKit Agents 1.4.6 | — |
| Speech-to-text | Deepgram Nova-2 | OpenAI Whisper |
| Greeter LLM | Groq Llama 3.1 8B | OpenAI GPT-4o-mini |
| Reservation / Takeaway LLM | Haiku 3.5 | OpenAI GPT-4o-mini |
| Checkout LLM | Sonnet 3.5 | OpenAI GPT-4o-mini |
| Text-to-speech | Cartesia Sonic-2 | OpenAI TTS |
| Voice activity detection | Silero | *(none — required)* |
| Intent embeddings | Sentence Transformers (local) | OpenAI text-embedding-3-small |
| Observability | Logfire | — |

---

## Documentation

| | |
|---|---|
| [The Four Agents](./01-agents) | What each agent does, which model it uses, and why |
| [Conversation Flow](./02-conversation-flow) | How a call moves through the system, with routing diagram |
| [Intent Routing](./03-intent-routing) | How Neema classifies intent and when she skips herself entirely |
| [Session & Context](./04-session-and-context) | Session lifecycle, context compression, cost controls |
| [Data Models](./05-data-models) | Order, reservation, payment, and session state schemas |
| [Privacy & Compliance](./06-privacy-and-compliance) | PII masking, SecretStr, audit trail, transcript service |
| [Deployment](./07-deployment) | Local setup, environment variables, production checklist |
