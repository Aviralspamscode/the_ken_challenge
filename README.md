# Ghar Pass — teammate recording playbook

Read this before you press record. Ken wants a **≤5 minute** screen recording of the agent thinking for itself. We do not explain APIs. We show one Saturday in Patna.

**Due:** Sunday 4 October 2026, 11:59 PM IST  
**Open:** http://127.0.0.1:8000  
**Model to declare:** whatever the red chip says in the header (today: `openai · gpt-4o-mini`)  
**System prompt:** http://127.0.0.1:8000/api/prompt → copy `system`

---

## What we are showing (say this in 20 seconds)

> Packages come home, but the OTP goes to the person in the meeting. Ghar Pass is a WhatsApp household agent. It sends the delivery code to whoever is actually at the door, pays COD from the buyer’s phone, and refunds a return the minute it is picked up. The buyer is interrupted last, never first.

Then shut up and let the screen work.

---

## The story (≤100 words — paste this in the submission)

On Saturday 3 October, Ritika Sinha is stuck in a client workshop in Patna while two parcels head home to Kankarbagh. At 9 am Ghar Pass tells her mother, in Hindi, that the headphones’ code will come to Maa’s phone, and sends Ritika a payment link so Maa needs no cash for the kurta. Ritika pays in a tea break. When Maa doesn’t reply at noon, Ghar Pass calls her — not Ritika. Both parcels arrive by 1 pm. Ritika hears nothing until one message: delivered, to Maa, 12:58. Sunday’s wrong-size shoes are refunded the minute they are picked up.

---

## Cast — three seats, no extras

| Seat | Who they play | What they touch | What they never do |
| --- | --- | --- | --- |
| **Operator** | The world + the clock | Right rail buttons (D1–D11), Reset, +10 min | Never type advice to the agent |
| **Curtain** | Delhivery + Pine Labs | Only the **Curtain** modal | Never add a sentence. JSON only |
| **Maa / Ritika** | Sunita on calls, Ritika on D8 | Hold-to-talk on the call; type in the three chats | Never tell the agent the next step |

One laptop is enough. Operator and curtain can be the same person if you are short. Maa must be a real voice on D6 and D9.

**Household (already seeded)**

- **Ritika Sinha**, 28, buyer, workshop all Saturday — do not call her.
- **Sunita Sinha**, 59, Maa, Hindi, full delegate, cap ₹5,000.
- **Ramesh**, building guard, approve-each (standby only).

---

## How to start the machine

On the project laptop:

```powershell
cd "C:\Users\naksh\OneDrive - Indian Institute of Technology Patna\Desktop\Projects\gnani"
python -m app
```

Browser: **http://127.0.0.1:8000**  
Hard refresh (Ctrl+Shift+R). Click **Reset day**. Confirm the clock says Saturday 3 Oct, 09:00.

If the page does not load, someone else is already using port 8000 — close that terminal and run `python -m app` again.

---

## How to frame the recording

Split the screen. **Do not record your face.**

```
┌──────────────────────────┬─────────────────────────┐
│  LEFT — Agent            │  RIGHT — three chats    │
│  decisions, tool calls,  │  Ritika / सुनीता / Ramesh│
│  Delhivery / Pine Labs   │                         │
│  curtain + live call     │                         │
└──────────────────────────┴─────────────────────────┘
                         RAIL (D1–D11) can stay visible
```

- Fast-forward whenever the header chip says **thinking**.
- Every WhatsApp line is spoken by **Gnani TTS** (Nalini / Poorvi / Deepak / Kaveri). Wait for the voice to finish before the next D-click if you want it on the tape. Click ▶ on a bubble to replay.
- Keep the **REC** pill in frame.
- If you go over 5 minutes: drop D4, and run D8–D11 as one burst.

---

## The one rule Ken will fail you on

The curtain person **plays the world**. They never help the agent think.

When a cream/white **Curtain** card opens:

1. Read the red partner line (`delhivery POST /api/p/edit`).
2. Click **Load sample**.
3. Click **Submit**.
4. If another curtain opens immediately, repeat. Morning will do this two or three times.

Do **not** type “route to Maa” or “refund now” in that box. If you do, the tape is invalid.

The three chat boxes are people, not the agent. Type only what that person would actually send.

---

## Click list (do this in order)

Allow the microphone the first time the call window asks. Rehearse once with Reset, then record a clean take.

### Saturday morning

**1. Click `D1+D2 · 09:05 both parcels arrive`**

What just happened: Delhivery says two parcels are pending at Patna DC — prepaid headphones ₹3,499 (OTP), COD kurta ₹899.

What the agent should do (do not say this to it):

- Edit the headphones consignee to **Sunita**.
- Send Ritika a **₹899 payment link** so Maa touches no cash.

**Curtain:** Load sample → Submit, for every pause.

**Voiceover, one line:**  
“Ritika is in a workshop. The agent sends the OTP to Maa, and the bill to Ritika.”

Watch the **सुनीता** and **Ritika** chats. If a Hindi line appears for Maa and a pay link for Ritika, keep rolling.

---

**2. Click `D3 · 09:21 Ritika paid the COD link`**

Ritika paid in a tea break. Agent should convert the kurta to prepaid and point it at Sunita. **Curtain** again.

**Voiceover:**  
“She pays from the meeting. Maa will not be asked for cash.”

---

**3. D4 — Maa’s voice note (optional if you are tight on time)**

Either:

- In **सुनीता**, upload a short Hindi voice note, **or**
- Type in her chat: `बेटा, एक से दो बजे मंदिर जाऊँगी`

Agent should park 1–2 pm as a gap and ping **Ramesh** to stand by.

**Voiceover:**  
“Maa will be at the temple. The agent covers the gap with the guard — it does not call Ritika.”

---

### Saturday noon

**4. Click `D5 · 12:10 A & B Dispatched`**

Out for delivery. Agent should warn Maa now: both parcels today, code on her phone.

---

**5. Click `D6 · 12:20 no reply (10 min)`**

Maa did not reply. **A live call window opens.** You are Sunita.

1. Let Gnani TTS speak first (Hindi).
2. **Hold to talk.** Say clearly: `हाँ, घर पे हूँ।`
3. Wait for her to speak back.
4. Click **Hang up**.

**Voiceover:**  
“Ten minutes, no text. It calls the person at the door — not the buyer in the workshop.”

If the mic fails, type `haan ghar pe hoon` in Sunita’s chat and move on. Prefer the call; Ken asked for live Gnani audio.

---

**6. Click `D7 · 12:58 A & B Delivered`**

Both scans: Delivered. Agent should send Ritika **one** message: who, when, both items. That is the first time she is interrupted about these parcels.

**Voiceover:**  
“Done. One message. Delivered to Maa, 12:58.”

Pause half a second on Ritika’s chat so the line is readable.

---

### Saturday evening → Sunday

**7. In Ritika’s chat, type exactly:**

```
Shoes size galat, return karna hai
```

(The rail button `D8` does the same thing if you prefer.)

Agent should book a **Sunday** reverse pickup — the sheet says everyone is home — and tell Maa.

**Curtain** for Delhivery create-pickup.

---

**8. Click `D9 · Sun 11:40 pickup 'not available'`**

Courier marked her unavailable. The sheet says she was home. **Call window again.** You are Sunita.

Say: `नहीं आए। कोई नहीं आया।`

Hang up. Agent should **not** believe the scan. It reschedules and attaches the transcript. Ritika gets one line, not three chatbots.

**Voiceover:**  
“The scan is wrong. It checks with Maa, then reschedules with evidence. Ritika does not have to fight a bot.”

---

**9. Click `D11 · Sun 15:10 Picked Up`**

Pickup scan landed. Agent refunds ₹2,199 now — not after warehouse QC. **Curtain** for Pine Labs refund.

**Voiceover:**  
“Picked up. Refund starts. That is the whole return.”

**Stop recording.**

---

## What “good” looks like on camera

You are fine if the tape shows, in this order:

1. An incoming event (you clicked a D-button).
2. A **DECISION | RULE | ACTION** line in the agent log.
3. A partner call (Delhivery / Pine Labs / Gnani) and the response (live or curtain-pasted).
4. A message landing in one of the three people.

You are **not** fine if:

- Someone typed the next step to the model.
- Curtain pasted English instructions instead of JSON.
- You narrate every tool. Let the log speak.
- The buyer gets a phone call. That is the opposite of the product.

---

## How to explain if someone asks mid-tape

| They ask | You say |
| --- | --- |
| Why is there still an OTP? | Platforms need proof against fake “not received”. We keep the code, we just send it to the person at the door. |
| Why not replace OTP with a grant? | That needs a new Delhivery + Pine Labs capability. We listed it as imagined. Today we re-route the real consignee phone. |
| Why Delhivery, not Flipkart? | Delhivery already has the consignee record, the edit/NDR levers, and it pays for every failed attempt. |
| What is the curtain? | Ken’s Wizard of Oz. Delhivery and Pine Labs replies are exactly what their docs return. The agent still chose the call. |
| Why call Maa in Hindi? | She does not live in the shopping app. She lives on WhatsApp and on voice. |

Do **not** start a sentence with “the architecture is…”.

---

## After the take — save these four things

1. **The video** (unlisted YouTube / Drive), first event to last refund, ≤5 min.
2. **Model name** from the header chip.
3. **System prompt** from `/api/prompt`.
4. **Decision log** — screenshot the agent log, or copy each `DECISION | RULE | ACTION` into the table below. Fill “exact message” from the three chats.

| # | When | What arrived | From | Decision | Rule | Exact message / action | Through |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D1 | Sat 09:05 | Headphones pending, OTP | Delhivery scan | Route to Sunita | R2 | *(copy from tape)* | Delhivery edit + WhatsApp |
| D2 | Sat 09:05 | Kurta COD ₹899 | Delhivery scan | Buyer pays remotely | R4 | | Pine Labs link + WhatsApp |
| D3 | Sat 09:21 | Payment PROCESSED | Pine Labs | Prepaid + route to Maa | R4+R2 | | Delhivery edit + WhatsApp |
| D4 | Sat 09:34 | Voice note, mandir 1–2 | WhatsApp / STT | Cover gap with Ramesh | R6 | | WhatsApp |
| D5 | Sat 12:10 | Dispatched | Delhivery | Warn receiver | R7 | | WhatsApp |
| D6 | Sat 12:20 | 10 min silence | Clock | Call Sunita, not Ritika | R3 | | Gnani STT+TTS |
| D7 | Sat 12:58 | Delivered | Delhivery | Close + one proof text | R5 | | WhatsApp |
| D8 | Sat 18:30 | “Shoes size galat…” | Ritika WhatsApp | Sunday pickup | R8 | | Delhivery create |
| D9 | Sun 11:40 | “Customer not available” | Delhivery | Call Maa first | R9 | | Gnani |
| D10 | Sun 11:46 | “Nahi aaye” | Call transcript | Reschedule + evidence | R9 | | Delhivery update |
| D11 | Sun 15:10 | Picked Up | Delhivery | Refund now | R10 | | Pine Labs refund |

D10 has no rail button. It should fire on its own after you hang up the D9 call.

---

## If something breaks

| Symptom | Fix |
| --- | --- |
| Blank page | `python -m app`, then Ctrl+Shift+R |
| Chip says `idle` forever after a click | Wait 10 seconds. Then Reset and redo that one step |
| Curtain never opens | It only opens for Delhivery / Pine Labs. Gnani is the live call window instead |
| Call window, no sound | Allow mic. Hold the red button down, don’t tap |
| Agent messages Ritika too much | Reset. On D1+D2 wait until both curtains are submitted before clicking D3 |
| You said the next step out loud on tape | That take is still OK if you did not type it into the agent. Re-record if you typed it |
| Over 5 minutes | Cut D4. Jump D8→D11 |

Do not debug Meta, Pine Labs dashboards, or Delhivery tokens on recording day. Those are optional. The curtain and the in-page chats are the demo.

---

## Written pack (after the tape, not during)

Already drafted in `Ghar Pass — Round 3 Blueprint (Madam, OTP ).md`. Copy, don’t rewrite:

- Day-one knowledge (circle, rules, who is home)
- Imagined capabilities (3) — household mandate, handoff token, near-doorstep ping
- Rail scores: Voice 7, Payments 7, Logistics 5
- Part 2: Delhivery builds it, ₹2–4 per enrolled shipment, first 1,000 via Patna SMS + hostels
- Landing line: *Aap meeting mein. Maa darwaze par. Parcel phir bhi aayega.*

Mockups T1–T6 = screenshots from this console (onboarding copy is in the blueprint if you need stills).

---

## One-line jobs on the call

- **Operator:** “I only press the next D-button when the last decision has landed in a chat.”
- **Curtain:** “I only click Load sample and Submit.”
- **Maa:** “I only speak two lines: *haan ghar pe hoon*, then *nahi aaye*.”
