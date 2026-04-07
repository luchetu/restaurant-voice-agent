---
title: "Restaurant Prompts"
description: "The principles behind Wingu's agent prompts and how to write or update them"
---

# Restaurant Prompts

Wingu's four agents — Neema, Baraka, Zawadi, and Luchetu — are each driven by a YAML prompt
file in `src/prompts/`. This document explains the principles behind how those prompts are
written and what to follow when updating or adding new ones.

The short version: **write for a person on a phone call, not for a document reader.**

---

## The Core Principles

### 1. Give the agent a real identity and a narrow job

The first thing a prompt does is tell the model who it is and exactly what it owns. A vague
description like "be helpful and professional" gives the model too much room to drift. On a
voice call, drift sounds like confusion.

Name the agent. State the restaurant. Define the job in one sentence. Say what is out of
bounds.

**Wrong:**
```
You are a professional receptionist. Be helpful, warm, and concise.
Handle customer queries about reservations and food orders.
```

**Right:**
```
You are Neema, the receptionist at Wingu Restaurant. Your job is to welcome
the caller and find out whether they need a reservation or a takeaway order,
then get them to the right person.
```

The second version gives the model a clear role, a specific restaurant, and a single
measurable outcome. There is nothing left to interpret.

---

### 2. Write for audio, not text

Voice prompts are instructions for someone about to pick up a phone — not a policy document.
Write in short, natural sentences. If a sentence sounds strange when spoken aloud, rewrite it.

Never use bullet points. Never use numbered lists. Never use markdown headers inside the
instructions block. These do not translate to speech — they either leak into the model's
phrasing or create structure that disrupts conversational flow.

**Wrong:**
```
Rules:
- Keep responses short — this is a phone call, not a chat
- Never take orders or reservation details yourself — always transfer
- If the caller is rude or abusive, calmly end the call
```

**Right:**
```
Keep everything short — this is a phone call. One or two sentences at most per turn.
Never take order or reservation details yourself — that belongs to the specialists.
```

The second version says the same thing in a form the model can follow conversationally.

---

### 3. Put guardrails inside the flow

Guardrails work best when they sit alongside the behaviour they are guarding, not in a
separate section. A standalone `Rules:` block at the bottom of a prompt is easy to
overlook — by the model and by the person maintaining the file.

**Wrong:**
```
Your job:
1. Help the customer build their order from the menu
2. Upsell naturally

Rules:
- Only take orders for items on the menu
- Never transfer without a confirmed order
```

**Right:**
```
Only take items that are on the menu. If something is not on the menu, let them
know and suggest something close. Once the caller confirms, transfer them to
checkout.
```

The constraint and the behaviour live in the same sentence. The model reads them together
because they belong together.

---

### 4. Add director notes

For voice, how the agent sounds matters as much as what it does. A short note on tone,
pace, and energy at the end of the prompt changes call quality noticeably.

These are not rules — they are delivery instructions, the same way a director briefs an actor.

**Examples from Wingu's prompts:**

```
Speak in a warm, calm, and welcoming tone.
```
*(Neema — default)*

```
Speak in a warm, energetic, and efficient tone.
```
*(Neema — lunch variant, callers are on a break)*

```
Speak in a warm, calm, and welcoming tone. Never take order or reservation
details yourself.
```
*(Neema — dinner variant, unhurried)*

```
Speak in a calm, reassuring, and professional tone.
```
*(Luchetu — payment collection, callers need to feel safe)*

The tone note changes with context. Lunch callers are in a hurry. Dinner callers want an
experience. A caller handing over card details needs to feel secure. Match the note to the
moment.

---

### 5. Mention tools by intent, not by documentation

Do not paste tool signatures or parameter lists into the prompt. The model already knows
the tools from the function definitions. Describing them in the prompt wastes tokens and
can make the model speak like a technical manual.

Describe what the tool is for and when to use it — not how it works.

**Wrong:**
```
Use update_reservation_date(date: str) to save the date.
Use confirm_reservation() once all fields are complete.
```

**Right:**
```
Before you finalise anything, read all the details back and get a clear yes
from the caller.
```

The second version tells the model the behaviour. The tool call follows from that naturally.

---

### 6. Use runtime context for things that change

The system prompt should contain stable behaviour — who the agent is, how it speaks, what
it can and cannot do. It should not contain facts that change between calls.

The menu is injected at runtime via the `{menu}` placeholder. Caller name, order details,
and session state are passed through `UserData`. Do not hardcode any of these into the
prompt.

**Wrong:**
```
Today's specials are Margherita Pizza and Caesar Salad.
The caller's name is James.
```

**Right:**
```
Our menu: {menu}
```

Hardcoded facts go stale and create contradictions mid-call. Runtime injection keeps the
prompt clean and the facts accurate.

---

## Wingu's Prompt Files

| File | Agent | Variant |
|---|---|---|
| `greeter.yaml` | Neema | Default |
| `greeter_lunch.yaml` | Neema | 11:00–15:00 |
| `greeter_dinner.yaml` | Neema | 18:00–22:00 |
| `greeter_returning.yaml` | Neema | Returning caller |
| `reservation.yaml` | Baraka | — |
| `takeaway.yaml` | Zawadi | — |
| `checkout.yaml` | Luchetu | — |

The system loads the right greeter variant automatically based on time of day and whether
the caller's name is already in session state. Returning-caller takes priority over
time-of-day variants.

---

## Checklist Before Updating a Prompt

Before committing a change to any prompt file, read through it and confirm:

- The agent has a name and a single clearly stated job
- There are no bullet points, numbered lists, or markdown headers
- Guardrails are part of the flow, not a separate section
- There is a director note on tone at the end
- No tool parameters or return values are mentioned
- No hardcoded facts that belong in runtime context
- It reads naturally when spoken aloud
