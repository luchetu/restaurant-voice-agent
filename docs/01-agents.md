---
title: "The Four Agents"
description: "What each agent does, which model it uses, why, and how they share a common foundation"
---

# The Four Agents

Every call is handled by one or more of four specialist agents. Each agent has a single,
clearly bounded responsibility. They share session state, but they never overlap — a caller
speaking to Baraka about a reservation is not also being handled by Zawadi.

---

## Neema — Greeter

**Model:** Groq Llama 3.1 8B Instant
**Prompt:** `src/prompts/greeter.yaml` (with variants)
**Defined in:** `src/agents/greeter.py`

Neema is the first voice a caller hears. Her only job is to understand what the caller wants
and get them to the right place as fast as possible. She never collects order details,
reservation fields, or payment information — that belongs to the specialists.

Groq Llama is used here deliberately. It is the fastest and cheapest model in the stack.
Neema's task is classification and a short greeting, not deep reasoning, so paying for a
larger model would waste money and add latency on every single call.

**What Neema does:**

- Greets the caller using one of four prompt variants (see below)
- Listens to the caller's opening statement
- Calls `to_reservation()` or `to_takeaway()` as a function tool to trigger the transfer

**Prompt variants** — loaded automatically based on runtime conditions:

| Variant file | When it loads |
|---|---|
| `greeter_returning.yaml` | Customer name is already in session state (returning caller) |
| `greeter_lunch.yaml` | Current time is between 11:00 and 15:00 |
| `greeter_dinner.yaml` | Current time is between 18:00 and 22:00 |
| `greeter.yaml` | Default — all other times |

The returning-customer variant takes priority over time-of-day variants. If Neema already
knows the caller's name, she greets them by name regardless of the hour.

**Tools:**

| Tool | What it does |
|---|---|
| `to_reservation()` | Transfers the call to Baraka |
| `to_takeaway()` | Transfers the call to Zawadi |

---

## Baraka — Reservation Agent

**Model:** Haiku 3.5
**Prompt:** `src/prompts/reservation.yaml`
**Defined in:** `src/agents/reservation.py`

Baraka handles table bookings. He collects three required fields — date, time, and party size —
and will not confirm a reservation until all three are present and valid. Each field is written
into session state via a dedicated function tool as soon as the caller provides it, so nothing
is lost if the call drops or the context is compressed.

Haiku is used for structured data collection tasks like this. It is fast, accurate at
following instructions, and cheap enough to run across the full conversation without pressure
on the session cost budget.

**What Baraka does:**

- Asks for date, time, and party size one at a time or together if the caller volunteers them
- Validates party size (must be between 1 and 20)
- Reads the booking back to the caller before confirming
- Returns to Neema via `to_greeter()` if the caller wants to do something else

**Tools:**

| Tool | What it does |
|---|---|
| `update_name()` | Saves the caller's name to session state |
| `update_phone()` | Saves the caller's phone number |
| `update_reservation_date()` | Saves the requested date |
| `update_reservation_time()` | Saves the requested time |
| `update_party_size()` | Saves party size (validated: 1–20) |
| `confirm_reservation()` | Checks all fields are set, sets status to `CONFIRMED` |
| `to_greeter()` | Returns control to Neema |

`confirm_reservation()` checks that `reservation.is_complete` is `True` before proceeding.
If any field is missing it returns an error string and Baraka asks the caller for the gap.

---

## Zawadi — Takeaway Agent

**Model:** Haiku 3.5
**Prompt:** `src/prompts/takeaway.yaml`
**Defined in:** `src/agents/takeaway.py`

Zawadi builds the caller's food order. She presents menu items conversationally, adds and
removes items on request, keeps a running total, and upsells naturally — suggesting a drink
with a main course, or a dessert when the order looks like a meal. She does not push.

Like Baraka, Zawadi uses Haiku. The task is structured but conversational — following
the menu, tracking quantities, reading totals — and Haiku handles it cleanly at a cost that
does not pressure the session budget.

**What Zawadi does:**

- Presents menu items and prices when asked
- Adds items to the order, validating each one against `data/menu.json`
- Removes items on request and reads back the updated total
- Upsells contextually (drinks with mains, desserts after a meal)
- Reads back the full order with the total before the caller confirms
- Transfers to Luchetu for payment once the order is confirmed
- Returns to Neema via `to_greeter()` if the caller changes intent

**Tools:**

| Tool | What it does |
|---|---|
| `update_name()` | Saves the caller's name |
| `update_phone()` | Saves the caller's phone number |
| `add_item()` | Validates item against menu, adds to order or increments quantity |
| `remove_item()` | Removes item from order by name |
| `get_order_summary()` | Returns a spoken-friendly order summary with total |
| `confirm_order()` | Validates order is not empty, sets status to `CONFIRMED` |
| `to_checkout()` | Transfers to Luchetu (only callable after `confirm_order`) |
| `to_greeter()` | Returns control to Neema |

`add_item()` performs a case-insensitive lookup against the menu. If the item does not exist,
it returns an error and Zawadi tells the caller it is not on the menu.

`to_checkout()` checks that the order is confirmed before allowing the transfer. An agent
cannot send a caller to Luchetu with an empty or unconfirmed order.

---

## Luchetu — Checkout Agent

**Model:** Sonnet 3.5
**Prompt:** `src/prompts/checkout.yaml`
**Defined in:** `src/agents/checkout.py`

Luchetu is the only agent that handles money. He collects the caller's card number, expiry,
and CVV — one field at a time — then reads back only the last four digits of the card for
confirmation. He issues an order reference and closes the call.

Sonnet is used here and nowhere else. Payment collection demands the most capable
model in the stack: it must stay on-script under pressure, never repeat sensitive details
back to the caller, handle corrections gracefully, and resist any attempt to extract card
data in a non-standard way. The additional cost of Sonnet at this stage of the call is
justified by the stakes.

**What Luchetu does:**

- Confirms the order total from Zawadi
- Collects the caller's name and phone number if not already known
- Collects card number, expiry date, and CVV one field at a time
- Reads back only the last four digits of the card — never the full number or CVV
- Confirms payment and issues an order reference (first 8 characters of the session UUID)
- Quotes an estimated prep time (20–30 minutes)
- Allows the caller to go back to Zawadi if they want to change the order before paying

**Tools:**

| Tool | What it does |
|---|---|
| `update_name()` | Saves the caller's name |
| `update_phone()` | Saves the caller's phone number |
| `update_payment()` | Stores card number, expiry, CVV as `SecretStr`; logs masked card ending |
| `confirm_payment()` | Validates all payment fields are present, sets order status to `PAID` |
| `to_takeaway()` | Returns to Zawadi if the caller wants to modify the order |
| `to_greeter()` | Returns to Neema |

`update_payment()` stores all three card fields as Pydantic `SecretStr`. They are never
written to logs, never included in serialised output, and never repeated back in full.
The audit log records only that a payment was collected and which card ending was used.

---

## What All Agents Share

All four agents extend `BaseAgent` (`src/agents/base.py`), which provides:

**Context injection on entry.** When an agent becomes active, it receives only the session
fields relevant to its role. Luchetu does not see the full reservation. Baraka does not see
payment fields. This is enforced by `AGENT_CONTEXT_FIELDS` — a mapping of agent name to the
subset of `UserData` it is allowed to read on entry.

**Response validation.** Every response is checked by `OutputValidator` before it is sent
to text-to-speech. Checks include: empty response, response too short or too long (>300
words), prices that do not match the menu, and menu items that do not exist. Failed responses
are regenerated.

**Transfer logging.** Every `_transfer_to_agent()` call writes a `TRANSFER` event to the
audit log with the destination agent and the reason string the LLM provided.

**Chat history truncation.** On every transfer, the chat history is trimmed to the last
6 messages. Tool call / tool result pairs are never split. This keeps the incoming agent's
context tight without losing the most recent conversational context.

**Lifecycle metrics.** `on_enter()` and `on_exit()` track how long each agent held the
call. These per-agent durations are included in the session summary written at the end of
every call.
