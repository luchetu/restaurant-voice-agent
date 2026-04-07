---
title: "Privacy & Compliance"
description: "How the system protects caller data — PII masking, SecretStr, the audit trail, and the transcript service"
---

# Privacy & Compliance

The system handles two categories of sensitive caller data: personal information (name,
phone, email) and payment data (card number, expiry, CVV). Both are protected at the
storage and logging layers before anything touches disk or an external service.

---

## PII Masking

**Defined in:** `src/core/pii.py`

Every string that passes through the transcript service or audit logger is run through
`mask_pii()` first. It applies regex substitutions in a fixed order:

| Data type | Pattern | Replacement |
|---|---|---|
| Phone (Kenyan format) | `\b(\+?254\|0)\d{9}\b` | `[PHONE]` |
| Payment card | 13–19 digit sequences with optional spaces or dashes | `[CARD]` |
| CVV | 3–4 digit sequences in payment context | `[CVV]` |
| Email address | Standard email format | `[EMAIL]` |
| Date of birth | `DD/MM/YYYY` | `[DOB]` |

Masking runs before any write. Raw PII never reaches a log file, audit record, or
transcript — even if the caller speaks their card number out loud.

`mask_card()` is a separate helper used specifically for Luchetu's confirmation read-back.
It returns the masked format `**** **** **** XXXX` given a full card number.

---

## SecretStr for Payment Fields

Card number, expiry, and CVV are stored in `PaymentInfo` as Pydantic `SecretStr`:

```python
class PaymentInfo(BaseModel):
    card_number: SecretStr = SecretStr("")
    expiry:      SecretStr = SecretStr("")
    cvv:         SecretStr = SecretStr("")
```

`SecretStr` enforces three protections automatically:

- `str(field)` returns `**********` — the value cannot be accidentally logged
- `.model_dump()` excludes `SecretStr` fields from serialisation by default
- The raw value requires an explicit `.get_secret_value()` call, making accidental
  exposure visible in code review

Luchetu's `update_payment()` tool stores the three fields. It logs only the masked card
ending (last 4 digits) to the audit trail — never the full number or CVV. No other agent
reads or writes `PaymentInfo`.

---

## Audit Trail

**Defined in:** `src/core/audit.py`

The audit log is a compliance record of what the **system did** during a call, not what
was said. It is separate from the conversation transcript.

Events logged:

| Event | When it is recorded |
|---|---|
| `SESSION_START` | Session object created |
| `SESSION_END` | Session ends — includes final cost summary |
| `AGENT_ENTER` | An agent becomes active |
| `AGENT_EXIT` | An agent transfers or the call ends |
| `TRANSFER` | Handoff between agents — includes destination and reason |
| `TOOL_CALL` | A function tool is invoked |
| `ORDER_PLACED` | `confirm_order()` is called |
| `PAYMENT` | `confirm_payment()` is called — includes masked card ending |
| `ESCALATE` | Escalation path triggered *(stub — not yet implemented)* |

Each record contains: `timestamp · session_id · event · agent · detail`.

All `detail` strings are run through `mask_pii()` before being stored. The audit log also
captures the `method` and `provider` fields from the intent classifier result on every
call, which makes it possible to monitor classification quality over time.

Audit events are published to **Logfire** for dashboards, alerting, and retention.

---

## Transcript Service

**Defined in:** `src/services/transcript_service.py`

The transcript service records every conversation turn and saves the full transcript to
disk when the session ends.

**How it works:**

1. `attach()` hooks into LiveKit's `conversation_item_added` event at session start
2. Each turn (role + text + timestamp) is run through `mask_pii()` before being stored
3. On session end, `save()` writes the masked transcript to `transcripts/{session_id}.json`

**Transcript file format:**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_turns": 22,
  "saved_at": "2026-04-06T14:30:00Z",
  "turns": [
    {
      "timestamp": "2026-04-06T14:28:01Z",
      "role": "agent",
      "text": "Good evening, welcome to Wingu. How can I help you tonight?"
    },
    {
      "timestamp": "2026-04-06T14:28:05Z",
      "role": "user",
      "text": "I'd like to order a takeaway."
    }
  ]
}
```

If the caller spoke their card number or phone number during the call, those values appear
as `[CARD]` and `[PHONE]` in the transcript — the masking is applied before the turn is
stored, not after.

---

## Output Validation

**Defined in:** `src/core/output_validator.py`

Every agent response is validated before it is sent to text-to-speech. This catches errors
before the caller hears them.

| Check | What it catches |
|---|---|
| Empty response | LLM returned nothing |
| Too short | Fewer than 10 characters — likely a malformed output |
| Too long | More than 300 words — agent rambling on a phone call |
| Hallucinated price | A price mentioned that does not match `data/menu.json` |
| Invalid menu item | An item name spoken that does not exist on the menu |

Price validation uses regex to find monetary values in the response and checks each one
against the menu. Item validation checks mentioned food names against `get_all_item_names()`.

Failed responses are not sent to TTS. The agent is prompted to regenerate the turn.
The failure reason and severity are logged to Logfire.

---

## What Is Not Yet Implemented

The following integrations are stubs. The compliance posture of the system changes
significantly when they are completed.

| Gap | File | What is needed |
|---|---|---|
| No database | `src/services/order_service.py` | Orders and reservations are not persisted beyond the transcript |
| No payment processing | `src/services/payment_service.py` | Card details are collected but no charge is made — Stripe integration required |
| No SMS confirmation | `src/services/notification_service.py` | Order reference is spoken but not sent — Twilio or equivalent needed |
| No escalation paths | `src/core/escalation.py` | Human handoff for complaints or failures is not defined |
| No content guardrails | `src/core/guardrails.py` | No content safety filter on agent output beyond `OutputValidator` |

Completing the payment integration will require PCI DSS scoping. Completing the database
integration will require a data retention policy for order and customer records.
