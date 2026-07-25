# ReclaimIQ — Demo Script & Talking Points
### ~5-minute walkthrough for the CodeStreet 2026 submission video

> **Before you record**
> 1. Backend: `cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8000`
> 2. Frontend: `cd frontend && npm run dev` → open `http://localhost:5173`
> 3. Have two members ready to select (the member picker is sorted by highest unclaimed):
>    - A **Platinum Charge** member (big lounge + milestone + large points range) — the hero demo.
>    - A **SmartEarn / MRCC** member (Amex Offer leakage + monthly milestone) — the "even small cards leak" beat.
> 4. Keep the **Issuer Portfolio** tab a click away.

---

## 0:00 — Hook (the problem) · 25s

> "Every American Express card bundles thousands of rupees of value — statement credits,
> lounge access, protection, Amex Offers, milestone rewards, reward points. But two people
> are flying blind: the **issuer**, who can't put a number on how much of that value goes
> unclaimed, and the **member**, who has no idea what they're missing. The value is already
> paid for. The gap is **visibility and activation** — and that's exactly what ReclaimIQ closes."

## 0:25 — Solution in one line · 15s

> "ReclaimIQ puts a **defensible rupee figure** on every member's unclaimed benefits across
> six families, and turns that gap into propensity-ranked nudges — through one engine that
> serves both a **member view** and an **issuer view**."

---

## 0:40 — Member view: the hero moment · ~1m50s

*(Select the Platinum Charge member.)*

- **Hero number** — "Right away, this member has left **₹50K+** on the table this year, and
  we can tell them they've only captured ~58% of what they're entitled to."
- **Where the value sits (donut)** — "It's not a vague score. We break it down by family:
  lounge, milestones, protection, credits, offers — each an auditable rupee figure."
- **Membership Rewards points panel** — *(the standout)*
  > "This member has **81,406 points**. Most cardholders think that's ₹20,000 of statement
  > credit. We show the full **range**: ₹20K if you burn it as credit, but up to **₹1.2 lakh**
  > if you transfer to KrisFlyer or Marriott. That 6× gap is invisible today — we surface it."
- **Milestone progress** — "They're **₹54,647 away** from unlocking a ₹5,000 milestone reward.
  That's not a generic reminder — it's a specific, timed, high-value nudge."
- **Amex Offers panel** — "Here's real leakage the industry misses: they **spent ₹5,358 at
  Zomato but never activated the offer**, so a ₹400 reward evaporated. We detect exactly that."
- **Personalized nudges** — "Each gap becomes a nudge **ranked by expected recovered value —
  the rupee gap times the model's predicted probability the member acts** — and routed to the
  right channel with a send window. We optimize for recovered rupees, not clicks."

*(Optional: switch to the SmartEarn/MRCC member for 15s.)*
> "Even on a ₹495 card, the engine finds a missed Amex Offer and near-miss monthly milestones.
> The same math scales across the whole product ladder."

---

## 2:30 — Issuer / Portfolio view · ~1m15s

*(Switch to the Issuer Portfolio tab.)*

- **Headline KPIs** — "Across 400 members: **₹50.1 lakh** of annualized unclaimed value,
  **₹12,519 per member**, and **114 members under 25% utilization** — that's the priority
  outreach segment. Plus **₹42 lakh** of reward-points value sitting idle."
- **Leakage by family** — "The book's leakage concentrates in **lounge and milestones** —
  that tells product exactly where benefit spend isn't landing."
- **By product** — "Realized vs. unclaimed per card, so you can see which products
  under-deliver on paper value."
- **Nudge-targeting uplift** — *(the ROI proof)*
  > "For a fixed nudge budget, targeting by our model recovers **4.29× more value** than a
  > blanket campaign of the same size. The propensity model is a gradient-boosted classifier —
  > AUC 0.64, top-decile lift 1.54× — with a transparent logistic fallback."
- **Feature importances** — "And it's explainable: engagement, gap size, urgency and category
  affinity drive conversion — no black box."

---

## 3:45 — Under the hood (credibility) · ~45s

- "The catalog models **real Amex India products** — Platinum Charge, Platinum Travel, MRCC,
  SmartEarn — including the **March 2026 Platinum Travel milestone change** (₹1.9L/₹4L/₹7L).
  Every figure cites its source in the code."
- "The valuation is **transparent and refund-aware** — a returned purchase never counts a
  credit as used. Lounge visits are **detected from in-lounge card spend** *and* pass records.
  Offers are modelled with **activation state**, milestones with **enrolment and near-miss**
  logic."
- "It's a pure function of transactions + entitlements, so it drops into a Snowflake/BigQuery
  batch or a Kafka stream unchanged."

## 4:30 — Scope, honesty & future · ~20s

> "We were disciplined about scope. Two things we deliberately **did not** fake: a
> partner-vs-non-partner **price comparison** — it needs historical real-time pricing we
> can't reconstruct — and **cross-card optimization**, which the problem statement doesn't
> ask for. Both are documented as future work, alongside all our assumptions and required
> data inputs."

## 4:50 — Close · 10s

> "ReclaimIQ: the value is already there. We help members **reclaim** it — and issuers
> **prove** it. Thank you."

---

## Rapid-fire numbers (memorize these)

| Metric | Value |
|---|---|
| Portfolio unclaimed (annualized) | **₹50.1 L** |
| Avg unclaimed / member | **₹12,519** |
| Portfolio utilization | **63.5%** |
| Members < 25% utilized | **114 / 400** |
| Idle Membership Rewards value | **₹42.0 L** |
| Leakage: lounge / milestones | **₹33.5 L / ₹10.6 L** |
| Nudge model | GradBoost · **AUC 0.64** · top-decile lift **1.54×** · base conv **25.6%** |
| Recovered-value uplift vs. random | **4.29×** |

## Likely judge questions — crisp answers

- **"Is the data real?"** — Card *products* are real (sources cited in `catalog.py`); all
  member/transaction data is synthetic and privacy-safe.
- **"Isn't the ML just re-learning your formula?"** — Yes, and we say so. The synthetic
  `converted` label comes from a known logistic formula; the model re-learns it. It proves
  the **pipeline and ranking mechanics**; on real data you'd retrain and measure true uplift
  with a treatment/holdout.
- **"Why a trailing 12 months?"** — We don't have each member's exact anniversary, so we use a
  rolling 12-month window as a proxy for the cardmembership year (documented assumption).
- **"How does protection avoid overstating?"** — It's a probabilistic *expected recoverable*
  (coverage rate × eligible spend), reported separately from guaranteed credit/lounge value.
- **"How does this scale?"** — Valuation is O(transactions), parallel per member; the catalog
  is config, not code; the API is stateless and cache-friendly.
