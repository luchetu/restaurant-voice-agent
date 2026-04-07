---
title: "Deployment"
description: "Local development setup, environment variables, Kubernetes manifests, and the production readiness checklist"
---

# Deployment

---

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.local .env   # fill in your API keys
python src/main.py dev
```

Once running, open [agents-playground.livekit.io](https://agents-playground.livekit.io)
and connect using your LiveKit project credentials to test the agent via browser microphone.

---

## Environment Variables

All configuration is loaded from `.env` via `src/config/settings.py` (pydantic-settings).

### LiveKit

| Variable | Description |
|---|---|
| `LIVEKIT_URL` | WebSocket URL for the agent — e.g. `wss://your-project.livekit.cloud` |
| `LIVEKIT_API_KEY` | LiveKit API key |
| `LIVEKIT_API_SECRET` | LiveKit API secret |
| `LIVEKIT_SIP_URL` | SIP trunk URL for inbound phone calls |

### Language Models

| Variable | Used by |
|---|---|
| `GROQ_API_KEY` | Neema (Groq Llama 3.1) |
| `ANTHROPIC_API_KEY` | Baraka and Zawadi (Haiku), Luchetu (Sonnet) |
| `OPENAI_API_KEY` | LLM fallback for all agents, embedding fallback, Whisper STT fallback |

### Voice Pipeline

| Variable | Description |
|---|---|
| `DEEPGRAM_API_KEY` | Deepgram Nova-2 speech-to-text |
| `CARTESIA_API_KEY` | Cartesia Sonic-2 text-to-speech |

### Observability

| Variable | Description |
|---|---|
| `LOGFIRE_TOKEN` | Logfire token for audit trail, metrics, and tracing |

### Behaviour

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | Set to `production` for live deployments |
| `LOG_LEVEL` | `INFO` | Python log level |
| `MAX_SESSION_MINUTES` | `20` | Hard time limit per call |
| `MAX_TOOL_STEPS` | `5` | Max LLM tool calls per conversation turn |
| `LLM_TIMEOUT_SECONDS` | `8.0` | Per-request LLM timeout before fallback |
| `ENABLE_CALL_RECORDING` | `false` | LiveKit room recording on/off |

---

## Production — Kubernetes

Manifests are in `deploy/k8s/`:

| File | Purpose |
|---|---|
| `deployment.yaml` | Agent deployment with resource requests and limits |
| `hpa.yaml` | Horizontal Pod Autoscaler — scales on CPU and memory |
| `secret.yaml` | Kubernetes Secret for all API credentials |

The LiveKit agent configuration (worker pool, concurrency, dispatch rules) is in
`deploy/agent.livekit.yaml`.

CI/CD is configured in `deploy/ci/github-actions.yml`.

---

## Production Readiness Checklist

### Security — do before go-live

- [ ] **Rotate all API keys** — the keys in `.env.local` were committed to the repository
      and must be considered compromised. Rotate them in every provider dashboard before
      any production traffic is sent.
- [ ] Move secrets to Kubernetes Secrets or a secrets manager — do not ship `.env` files
      inside containers.
- [ ] Confirm `ENABLE_CALL_RECORDING=false` unless a recording consent flow is in place.

### Backend integrations — required for a working product

- [ ] `src/services/payment_service.py` — integrate Stripe. Card details are currently
      collected but no charge is made.
- [ ] `src/services/order_service.py` — persist confirmed orders to a database.
- [ ] `src/services/reservation_service.py` — check availability and save bookings.
- [ ] `src/services/notification_service.py` — send SMS order confirmation to the caller
      (Twilio or equivalent).

### Core stubs — required before production

- [ ] `src/core/escalation.py` — define escalation paths for complaints, payment failures,
      or calls the system cannot handle.
- [ ] `src/core/guardrails.py` — add content safety checks on agent output beyond the
      existing `OutputValidator`.

### Compliance

- [ ] PCI DSS scoping for card number collection over a voice channel.
- [ ] Data retention policy for `transcripts/` JSON files.
- [ ] Logfire audit log retention period and access control review.
- [ ] Confirm PII masking patterns cover all phone number formats expected from callers
      (current patterns target Kenyan `+254` / `0` prefixes).
