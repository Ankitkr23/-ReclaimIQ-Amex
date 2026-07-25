---
marp: true
theme: default
paginate: true
size: 16:9
style: |
  section { font-family: 'Inter', system-ui, sans-serif; background: #ffffff; color: #12233b; padding: 56px 64px; }
  h1 { color: #00175a; font-size: 46px; letter-spacing: -1px; }
  h2 { color: #006fcf; font-size: 30px; }
  section.lead { background: linear-gradient(125deg,#00175a,#006fcf); color:#fff; }
  section.lead h1, section.lead h2 { color: #fff; }
  strong { color: #006fcf; }
  section.lead strong { color: #ffd77a; }
  table { font-size: 21px; }
  .big { font-size: 64px; font-weight: 800; color:#00175a; letter-spacing:-2px; }
  ul { line-height: 1.5; }
---

<!-- _class: lead -->

# ReclaimIQ
## Benefit-Underutilization Analytics

Putting a **rupee figure** on unclaimed card benefits — and turning it into
**measurable** engagement.

CodeStreet 2026 · American Express India

---

## The problem

- Amex India cards bundle **₹1,000s** of value: credits, lounge, protection, **Offers**,
  **milestones**, **reward points**.
- **Issuers** can't measure how much value goes **unclaimed** → benefit ROI is a guess.
- **Members** don't see what they're missing → perceived value drops → **churn**.

> The value is already paid for. The gap is **visibility + activation**, not entitlement.

---

## Grounded in real Amex India products

| Card | Fee | What we model |
|------|-----|---------------|
| **Platinum Charge** | ₹66,000 | Unlimited lounge · ₹40K credits · protection · ₹20L voucher |
| **Platinum Travel** | ₹5,000 | Milestones ₹1.9L/₹4L/₹7L → MR + Taj voucher (2026 structure) |
| **MRCC** | ₹4,500 | Monthly milestones (4×₹1,500 · ₹20K spend, enrolment) |
| **SmartEarn** | ₹495 | 10X/5X online accelerators · ₹500 voucher milestones |

*Real products; synthetic, privacy-safe member data.*

---

## The opportunity (synthetic book: 400 members, ~200K transactions)

<div class="big">₹50.1 L</div>

annualized **unclaimed** value · **₹12,519 / member** · portfolio utilization **≈63%**

- **114** members below **25%** utilization — the priority segment.
- Leakage concentrates in **lounge (₹33.5L)**, then **milestones (₹10.6L)**,
  **protection (₹2.2L)**, **credits (₹2.2L)**, **offers (₹1.6L)**.
- **₹42.0 L** of Membership Rewards value sits idle in accounts.

---

## How we quantify the gap — six families, transparent by design

| Family | Unclaimed logic |
|--------|-----------------|
| **Credits** | `min(cap, qualifying spend NET OF REFUNDS)` per cycle |
| **Lounge** | reachable travel days − visits *(detected from in-lounge spend + passes)* |
| **Protection** | `coverage × protected spend` − claims (value-at-risk) |
| **Offers** | spent at merchant but **offer not activated** = missed |
| **Milestones** | **near-miss** / lost-to-non-enrolment vs. spend threshold |
| **Points** | balance × redemption **range** (₹0.25 → ₹1.50 / pt) |

Every rupee traces to an **explicit rule** → defensible to members *and* stakeholders.

---

## Solution: ReclaimIQ — one engine, two audiences

- **Card Member view** — *"You're **₹54,647** away from unlocking a ₹5,000 milestone."*
  *"You spent ₹5,358 at Zomato — the Amex Offer was never activated."*
- **Issuer Portfolio view** — book-level unclaimed value, utilization, points at stake,
  and nudge ROI.

Same **defensible math** powers the member nudge *and* the business case.

---

## Architecture

```
Transactions ┐   Benefit Catalog       Valuation (6 families)     FastAPI     React dashboard
(refunds,    │   (products→benefits,  ┌─▶ credit·lounge·protect ─▶  /api/* ─▶  member + issuer
 lounge spend)┼─▶ milestones, MR cfg) │   offer·milestone·points     ▲
Members/Offers│                        │                             │
Claims/Passes ┘                        └──▶ Nudge engine ── Propensity model ┘
                                    (trigger → rank by expected recovered value → route)
```

Stack: **Python (FastAPI, pandas, scikit-learn)** + **React**. Warehouse/stream ready.

---

## Nudge engine — right message, right moment

1. **Trigger** on patterns: un-activated **offer**, **near-miss milestone**, unused
   **lounge** on travel days, idle **points**, **expiring** credit.
2. **Rank** by **expected recovered value = ₹ gap × P(convert | nudge)**.
3. **Route** by intent (urgent → push · transactional → in-app · awareness → email) + timing.

Optimizes for **recovered rupees**, not clicks.

---

## The model & measurable uplift (Task 5)

- Gradient-boosted **propensity model** (+ transparent logistic fallback) on a labelled log.
- **AUC ≈ 0.64**, **top-decile lift ≈ 1.54×** over a **25.6%** base conversion rate.

<div class="big">4.29×</div>

more value recovered vs. a random/blanket campaign of the same size.

*(Synthetic label is drawn from a known formula the model re-learns — demonstrates the pipeline, not a real effect size.)*

---

## Why it wins

- **Rupee-denominated & explainable** gap across **six** benefit families.
- **Activation-aware** Offers & **near-miss** milestones — models the *state* that causes leakage.
- **Points as a value range** — surfaces the 6× statement-credit-vs-transfer gap.
- **Expected-value targeting** — spends nudge budget where it recovers most.
- **Dual-audience, single engine** — member value = issuer ROI, always consistent.

---

## Scope & future work

- **Built:** refund netting, lounge-from-transactions, Amex Offers activation, milestones,
  points valuation — all grounded in real Amex India products.
- **Future (documented, not built):** partner-vs-non-partner **price comparison** (needs
  historical real-time pricing); **cross-card** optimization (out of PS scope — PS is
  per-member across credits/lounge/protection).

---

## Feasibility · Scalability · Impact

- **Feasible:** standard stack; engine is a pure fn of (transactions, entitlements).
- **Scalable:** O(transactions), per-member parallel → Spark / Snowflake / BigQuery;
  catalog is *config, not code*.
- **Impact:** retention lift, benefit-ROI clarity, efficient engagement spend.

---

<!-- _class: lead -->

# Thank you

**ReclaimIQ** — the value is already there. We help members **reclaim** it, and issuers
**prove** it.

*Working prototype + code in the repo. All member data synthetic & privacy-safe.*
