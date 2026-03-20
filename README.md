# Restaurant Voice Agent

A production-grade multiagent voice assistant for restaurants built with LiveKit Agents.
Handles reservations, takeaway orders, and checkout over a phone call.

## Agents

| Agent       | Name    | Role                                              |
| ----------- | ------- | ------------------------------------------------- |
| Greeter     | Sofia   | Welcomes caller, routes to correct agent          |
| Reservation | Marco   | Collects date, time, party size, confirms booking |
| Takeaway    | Lucia   | Takes food orders, upsells, confirms order        |
| Checkout    | Roberto | Collects payment, confirms order reference        |

## Stack

- **LiveKit Agents** — voice session management and agent framework
- **OpenAI** — LLM (gpt-4o-mini)
- **Deepgram** — Speech to text
- **Cartesia** — Text to speech
- **Silero** — Voice activity detection
- **Pydantic** — Data validation
- **Logfire** — Observability and tracing

## Project Structure

```
src/
├── agents/          # One file per agent
├── config/          # Settings, voices, menu
├── core/            # PII masking, audit, resilience, guardrails
├── models/          # Pydantic models: session, order, reservation
├── prompts/         # YAML instructions per agent
├── services/        # Order, payment, notification integrations
├── tools/           # Shared and agent-specific function tools
└── utils/           # Logging, prompt loader
```

## Setup

**1. Clone and create virtual environment**

```bash
git clone https://github.com/yourname/restaurant-voice-agent.git
cd restaurant-voice-agent
python -m venv .venv
source .venv/bin/activate
```

**2. Install dependencies**

```bash
pip install -e ".[dev]"
```

**3. Configure environment**

```bash
cp .env.example .env.local
```

Fill in your API keys in `.env.local`.

**4. Download VAD model**

```bash
python scripts/download_models.py
```

**5. Run**

```bash
python src/main.py dev
```

## Test

Open [agents-playground.livekit.io](https://agents-playground.livekit.io), connect
with your LiveKit credentials, and start a session.

## Environment Variables

| Variable             | Description                     |
| -------------------- | ------------------------------- |
| `LIVEKIT_URL`        | Your LiveKit Cloud project URL  |
| `LIVEKIT_API_KEY`    | LiveKit API key                 |
| `LIVEKIT_API_SECRET` | LiveKit API secret              |
| `OPENAI_API_KEY`     | OpenAI API key                  |
| `DEEPGRAM_API_KEY`   | Deepgram API key                |
| `CARTESIA_API_KEY`   | Cartesia API key                |
| `LOGFIRE_TOKEN`      | Logfire token for observability |

## Agent Flow

```
Caller
  └── Sofia (Greeter)
        ├── Marco (Reservation) ──→ Sofia
        └── Lucia (Takeaway)
              └── Roberto (Checkout) ──→ Lucia
                                     └──→ Sofia
```

## Production Checklist

- [ ] Logfire token configured
- [ ] All API keys set in environment
- [ ] `ENVIRONMENT=production` in env
- [ ] Stripe integration in `payment_service.py`
- [ ] SMS confirmation in `notification_service.py`
- [ ] DB connection in `order_service.py`
