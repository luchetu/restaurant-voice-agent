---
title: "Data Models"
description: "Every schema in the system — session state, order, reservation, payment, and menu"
---

# Data Models

All session data is modelled with Pydantic. Every field is validated on write. Computed
fields derive their values from other fields rather than being stored separately.

---

## UserData — The Session Object

**Defined in:** `src/models/session.py`

`UserData` is created once at session start and shared across all four agents for the
lifetime of the call. Every tool call mutates it in place.

| Field | Type | Description |
|---|---|---|
| `session_id` | `str` (UUID) | Unique call identifier — appears in all logs, audit events, and the transcript filename |
| `customer` | `CustomerInfo` | Caller's name and phone number |
| `order` | `Order` | Live takeaway order |
| `reservation` | `Reservation` | Booking details |
| `payment` | `PaymentInfo` | Card details stored as `SecretStr` |
| `metrics` | `SessionMetrics` | Running cost, token counts, transfer count, per-agent durations |
| `transcript` | `TranscriptService` | Writes PII-masked turns to disk on session end |
| `audit` | `AuditLogger` | Compliance log of significant session events |
| `agents` | `dict[str, Agent]` | Registry of all four agent instances |
| `prev_agent` | `str \| None` | Name of the agent that last held the call |
| `last_handoff_reason` | `str \| None` | Reason string passed at the last transfer |

`summarize()` on `UserData` returns a human-readable session summary used in context
injection when an agent takes over.

---

## CustomerInfo

| Field | Type | Description |
|---|---|---|
| `name` | `str \| None` | Caller's name — collected by any agent |
| `phone` | `str \| None` | Caller's phone number — collected by any agent |
| `is_complete` | `bool` (computed) | `True` when both name and phone are set |

Any of the four agents can collect name and phone via the shared `update_name()` and
`update_phone()` tools. Whichever agent collects them first, all subsequent agents see them.

---

## Order

**Defined in:** `src/models/order.py`

```
OrderStatus:  EMPTY → BUILDING → CONFIRMED → PAID
```

| Field | Type | Description |
|---|---|---|
| `items` | `list[OrderItem]` | All items currently in the order |
| `status` | `OrderStatus` | Lifecycle state |
| `special_requests` | `str \| None` | Free-text dietary or preparation notes |
| `total` | `float` (computed) | Sum of all `item.subtotal` values |
| `is_empty` | `bool` (computed) | `True` when `items` is empty |

`confirm_order()` can only be called when `is_empty` is `False`. Luchetu cannot be reached
with an empty order — the `to_checkout()` tool validates this before allowing the transfer.

`summary()` on `Order` returns a spoken-friendly string Zawadi uses when reading the order
back to the caller.

### OrderItem

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Menu item name (validated against `data/menu.json` on add) |
| `price` | `float` | Unit price at time of ordering (must be > 0) |
| `quantity` | `int` | Number of units (must be > 0) |
| `subtotal` | `float` (computed) | `price × quantity` |

`add_item()` performs a case-insensitive lookup against the menu before creating an
`OrderItem`. If the item does not exist on the menu, the tool returns an error string and
no item is added.

---

## Reservation

**Defined in:** `src/models/reservation.py`

```
ReservationStatus:  PENDING → CONFIRMED → CANCELLED
```

| Field | Type | Description |
|---|---|---|
| `date` | `str \| None` | Requested date |
| `time` | `str \| None` | Requested time |
| `party_size` | `int \| None` | Number of guests — validated between 0 and 20 |
| `status` | `ReservationStatus` | Lifecycle state |
| `is_complete` | `bool` (computed) | `True` when all three fields are set |

`confirm_reservation()` checks `is_complete` before proceeding. If any field is missing
it returns an error and Baraka asks the caller for the gap rather than confirming an
incomplete booking.

`summary()` on `Reservation` returns a spoken-friendly booking summary Baraka reads back
before asking for confirmation.

---

## PaymentInfo

| Field | Type | Description |
|---|---|---|
| `card_number` | `SecretStr` | Full card number — never logged or serialised |
| `expiry` | `SecretStr` | Card expiry date — never logged or serialised |
| `cvv` | `SecretStr` | CVV — never logged or serialised |
| `is_complete` | `bool` (computed) | `True` when all three fields are non-empty |
| `masked_card()` | `str` | Returns `**** **** **** XXXX` — last 4 digits only |

All three fields use Pydantic `SecretStr`. Calling `str()` on any of them returns
`**********`. The raw value requires an explicit `.get_secret_value()` call. They are
excluded from `.model_dump()` serialisation by default and never appear in logs.

Luchetu is the only agent that reads or writes `PaymentInfo`. `update_payment()` stores
the three fields. `confirm_payment()` checks `is_complete` before marking the order as
`PAID`.

---

## Menu

**Loaded from:** `data/menu.json` via `src/config/menu.py`

The menu is loaded once at startup and cached. It is not reloaded between calls.

Each item has the following structure:

```json
{
  "name": "Margherita Pizza",
  "price": 10.00,
  "allergens": ["gluten", "dairy"],
  "category": "Mains"
}
```

**Categories:** Mains · Sides · Drinks · Desserts

**Current menu:**

| Item | Price | Category | Allergens |
|---|---|---|---|
| Margherita Pizza | $10.00 | Mains | gluten, dairy |
| Pepperoni Pizza | $12.00 | Mains | gluten, dairy |
| Caesar Salad | $7.00 | Mains | gluten, dairy, egg |
| Garden Salad | $5.00 | Mains | — |
| Garlic Bread | $3.50 | Sides | gluten, dairy |
| French Fries | $3.00 | Sides | — |
| Coffee | $2.50 | Drinks | dairy |
| Orange Juice | $3.00 | Drinks | — |
| Water | $1.00 | Drinks | — |
| Ice Cream | $3.50 | Desserts | dairy |
| Cheesecake | $5.00 | Desserts | gluten, dairy, egg |

`get_menu_summary()` in `src/config/menu.py` returns a plain-text version of this table
that is injected into agent prompts via the `{menu}` placeholder in the YAML files.

`get_all_item_names()` returns the list of item names used by `OutputValidator` to catch
hallucinated menu items before they reach the caller.
