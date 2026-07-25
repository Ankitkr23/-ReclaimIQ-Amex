# ReclaimIQ — Benefit-Underutilization Analytics

> CodeStreet 2026 (American Express) · Theme: **Benefit-Underutilization Analytics**

ReclaimIQ is an analytics engine + dashboard that quantifies, **in rupees**, how much
benefit value each American Express India card member leaves unclaimed — across **statement
credits, airport lounge access, protection coverage, targeted Amex Offers, spend-unlocked
milestone rewards, and Membership Rewards points** — then converts that gap into a
prioritized, personalized, and *measurable* engagement opportunity.

On a synthetic portfolio of **400 members / ~200K transactions**, ReclaimIQ surfaces
**~₹50.1 L** of annualized unclaimed value (**avg ₹12,519 per member**, portfolio benefit
utilization **≈63%**), plus **₹42.0 L** of idle Membership Rewards value, and a
nudge-targeting model that recovers **4.29× more value** than a blanket campaign of the
same size.

The benefit catalog models **real Amex India products** (Platinum Charge, Platinum Travel,
MRCC, SmartEarn) with sources cited inline in `catalog.py`. All member/transaction data is
synthetic and privacy-safe.

---

## What it does (maps to the 5 problem-statement tasks)

| # | Task | Where it lives |
|---|------|----------------|
| 1 | Map each member's transactions to their full benefit entitlements | `backend/app/engine/catalog.py`, `valuation.py` |
| 2 | Calculate the rupee value of unclaimed benefits (6 families) | `backend/app/engine/valuation.py` |
| 3 | Dashboard surfacing top unclaimed benefits in personalized terms | `frontend/` (Member view) |
| 4 | Nudge logic triggered by spending patterns, at the right moment | `backend/app/engine/nudges.py` |
| 5 | Test & optimize for mapping accuracy, nudge relevance, measurable uplift | `ml.py` (propensity model + uplift study), Issuer view |

## Architecture

```
Transactions ─┐   ┌────────────────────┐   ┌──────────────────────────┐   ┌──────────────┐
(refunds,     │   │  Benefit Catalog   │   │  Valuation (6 families)  │   │  FastAPI API │
 lounge spend)├──▶│ products→benefits, │──▶│ credit·lounge·protection │──▶│   /api/*     │──▶ React dashboard
Members/Offers│   │ milestones, MR cfg │   │ offer·milestone·points   │   │              │    (member + issuer)
Claims/Passes ┘   └────────────────────┘   └───────────┬──────────────┘   └──────┬───────┘
                                                        │                          │
                                     Nudge engine ◀─────┴──── Propensity model ────┘
                                (trigger → rank by expected recovered value → route)
```

See `docs/PROJECT_DESCRIPTION.md` for a Mermaid architecture diagram, assumptions, required
inputs and dependencies.

## Quick start

**1. Backend (FastAPI) — Python 3.11+**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.data.generate 400          # generate the synthetic dataset (once)
uvicorn app.main:app --reload --port 8000 # API at http://127.0.0.1:8000
```

**2. Frontend (React + Vite) — Node 18+**

```bash
cd frontend
npm install
npm run dev        # dashboard at http://localhost:5173 (proxies /api → :8000)
```

Open the dashboard and toggle between the **Card Member** and **Issuer Portfolio** views.
API docs are auto-generated at `http://127.0.0.1:8000/docs`.

## How the rupee value is computed (transparent by design)

- **Credits** — `max(0, min(cap, qualifying spend NET OF REFUNDS))` per cadence cycle. Only
  qualifying merchants/categories count, and refunds/reversals (negative rows) are netted so
  a returned purchase never counts a credit as used.
- **Lounge** — visits are **detected from in-lounge card transactions** *and* pass-swipe
  records; potential = `reachable travel days × value/visit` (attach rate 0.6, capped);
  unclaimed = potential − detected visits.
- **Protection** — expected recoverable = `coverage rate × eligible protected spend`, net of
  filed claims (a probabilistic "value at risk", reported separately).
- **Amex Offers** — per-member targeted offers with **activation state**; spending past the
  threshold at the merchant *without saving the offer* = missed value; activated-but-unmet
  offers near expiry = at-risk nudges.
- **Milestones** — spend-threshold rewards: achieved / **near-miss** (recoverable) /
  **lost-to-non-enrolment** / locked; powers *"you're ₹X away from unlocking ₹Y"*.
- **Points** — Membership Rewards balance valued across a redemption **range** (statement
  credit ₹0.25 → hotel ₹0.50 → premium airline ₹1.50 per point); the under-redemption gap
  becomes a nudge.

Every figure traces back to an explicit rule, so it is defensible to both members and
stakeholders.

## Nudge engine

Each gap becomes a nudge that is (a) **triggered** by an observable spending pattern
(un-activated offer, near-miss milestone, unused lounge on travel days, idle points,
expiring credit), (b) **ranked** by *expected recovered value = ₹ gap × P(convert | nudge)*
from a gradient-boosted propensity model (with a transparent logistic-regression fallback),
and (c) routed by intent (urgent → push · transactional → in-app · awareness → email) with a
recommended send window.

## Repo layout

```
backend/    FastAPI service + analytics engine + synthetic data generator
frontend/   React + Vite dashboard (member + issuer views)
docs/       Round-1 project description, presentation deck, architecture notes
PS.pdf      Original problem statement
```

## Scope notes

- The problem statement is **per card member** across credits / lounge / protection; we
  extend it with Offers, milestones and points (all "value left on the table").
- **Not built (documented as future work):** partner-vs-non-partner price comparison (needs
  historical real-time pricing) and cross-card portfolio optimization (out of PS scope). See
  `docs/PROJECT_DESCRIPTION.md` §10.

See `docs/PROJECT_DESCRIPTION.md` and `docs/PRESENTATION.md` for the Round-1 submission.
