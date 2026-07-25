"""
Synthetic data generator for the ReclaimIQ analytics engine (American Express India).

All data is synthetic and privacy-safe. It is engineered so that many members
under-utilise their benefits, giving the engine a meaningful "value left on the table".

Outputs (backend/app/data/generated/):
  members.csv        card members, product, segment, tenure, engagement, enrolment &
                     points-redemption behaviour, points balance
  transactions.csv   ~12 months of categorised spend IN RUPEES, including refunds/reversals
                     (negative rows) and airport-lounge spend rows
  lounge_visits.csv  lounge visits recorded via a pass swipe (an upstream source, no txn)
  claims.csv         protection/insurance claims actually filed
  offers.csv         targeted Amex Offers per member, with activation (saved) state
  nudge_history.csv  historical nudges + engagement label (propensity-model training)
  meta.json          reference "today" + generation parameters
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from app.engine.catalog import PRODUCTS, BENEFITS, product_milestones, MR_EXCLUDED_CATEGORIES, LOUNGE_MERCHANTS

OUT_DIR = Path(__file__).resolve().parent / "generated"
REFERENCE_DATE = date(2026, 7, 15)
HISTORY_MONTHS = 12
SEED = 42

FIRST = ["Aarav", "Diya", "Vivaan", "Ananya", "Aditya", "Isha", "Kabir", "Meera", "Rohan",
         "Sara", "Arjun", "Nisha", "Ved", "Tara", "Krishna", "Priya", "Dev", "Anika",
         "Ishaan", "Riya", "Yash", "Kavya", "Aryan", "Zoya", "Reyansh", "Aisha", "Kian",
         "Naina", "Ayaan", "Mira", "Rehan", "Sanya", "Vihaan", "Pooja", "Neel", "Ira"]
LAST = ["Sharma", "Iyer", "Nair", "Reddy", "Mehta", "Gupta", "Rao", "Kapoor", "Bose",
        "Menon", "Verma", "Singh", "Patel", "Chopra", "Das", "Malhotra", "Pillai",
        "Banerjee", "Joshi", "Kulkarni", "Shah", "Agarwal", "Fernandes", "Khanna"]

AIRPORTS = ["BOM", "DEL", "BLR", "MAA", "HYD", "CCU", "GOI", "PNQ"]

# Category MIX (proportions) per behavioural segment; normalised at runtime.
# Spend LEVEL is set separately by the product band (below) so members straddle milestones.
SEGMENTS = {
    "affluent_traveller": {
        "dining": 12, "groceries": 10, "online_shopping": 12, "apparel": 7, "electronics": 6,
        "airline": 22, "hotel": 20, "rideshare": 3, "streaming": 1, "entertainment": 2,
        "wireless": 1, "utilities": 4, "fuel": 4, "wellness": 3, "flights_per_year": (12, 26),
    },
    "points_maximiser": {
        "dining": 16, "groceries": 14, "online_shopping": 18, "apparel": 8, "electronics": 6,
        "airline": 10, "hotel": 7, "rideshare": 4, "streaming": 1, "entertainment": 3,
        "wireless": 1, "utilities": 5, "fuel": 4, "wellness": 3, "flights_per_year": (3, 9),
    },
    "online_shopper": {
        "dining": 12, "groceries": 14, "online_shopping": 26, "apparel": 12, "electronics": 8,
        "airline": 3, "hotel": 2, "rideshare": 5, "streaming": 2, "entertainment": 3,
        "wireless": 2, "utilities": 5, "fuel": 2, "wellness": 3, "flights_per_year": (0, 3),
    },
    "family_spender": {
        "dining": 9, "groceries": 26, "online_shopping": 14, "apparel": 10, "electronics": 7,
        "airline": 6, "hotel": 5, "rideshare": 2, "streaming": 2, "entertainment": 4,
        "wireless": 3, "utilities": 9, "fuel": 6, "wellness": 3, "flights_per_year": (1, 5),
    },
    "young_professional": {
        "dining": 18, "groceries": 10, "online_shopping": 16, "apparel": 9, "electronics": 6,
        "airline": 5, "hotel": 4, "rideshare": 10, "streaming": 3, "entertainment": 5,
        "wireless": 2, "utilities": 3, "fuel": 2, "wellness": 5, "flights_per_year": (1, 5),
    },
}

# Realistic TOTAL monthly spend band (₹) per product, chosen so annual spend straddles the
# real milestone thresholds (PT: ₹1.9L/₹4L/₹7L; SmartEarn: ₹1.2-2.4L; PC: ₹20L renewal).
PRODUCT_MONTHLY_SPEND = {
    "platinum_charge": (60000, 320000),
    "platinum_travel": (14000, 78000),
    "mrcc": (6000, 26000),
    "smartearn": (3500, 20000),
}
# Which segments plausibly hold which product.
PRODUCT_SEGMENTS = {
    "platinum_charge": ["affluent_traveller", "points_maximiser"],
    "platinum_travel": ["points_maximiser", "affluent_traveller", "family_spender"],
    "mrcc": ["family_spender", "young_professional", "points_maximiser"],
    "smartearn": ["online_shopper", "young_professional", "family_spender"],
}

MERCHANTS = {
    "dining": ["Swiggy", "Zomato", "EazyDiner", "Social", "Barbeque Nation", "Taj"],
    "groceries": ["BigBasket", "Blinkit", "Zepto", "DMart", "Nature's Basket"],
    "online_shopping": ["Amazon", "Flipkart", "Reliance Digital", "Tata Cliq"],
    "apparel": ["Myntra", "Ajio", "Nykaa", "Zara"],
    "electronics": ["Croma", "Reliance Digital", "Apple Store", "Vijay Sales"],
    "airline": ["IndiGo", "Vistara", "Air India", "MakeMyTrip", "Amex Travel"],
    "hotel": ["Taj", "Marriott", "MakeMyTrip", "Amex Travel", "FHR"],
    "rideshare": ["Uber", "Ola", "Rapido"],
    "streaming": ["Netflix", "Prime Video", "Hotstar", "Spotify"],
    "entertainment": ["BookMyShow", "PVR"],
    "wireless": ["Airtel", "Jio", "Vi"],
    "utilities": ["Tata Power", "Adani Gas", "BESCOM"],
    "fuel": ["HPCL", "IOCL", "BPCL"],
    "wellness": ["Cult.fit", "HealthifyMe", "Tata 1mg"],
    "lounge": LOUNGE_MERCHANTS,
    "general": ["Misc Merchant"],
}
CATEGORY_ORDER = [c for c in MERCHANTS if c != "lounge"]

# Amex Offers pool: (merchant, category, min_spend, reward_type, reward_value)
OFFER_POOL = [
    ("Swiggy", "dining", 2500, "statement_credit", 500),
    ("Zomato", "dining", 2000, "statement_credit", 400),
    ("Amazon", "online_shopping", 5000, "statement_credit", 750),
    ("Flipkart", "online_shopping", 5000, "points", 1000),
    ("MakeMyTrip", "hotel", 15000, "statement_credit", 3000),
    ("Uber", "rideshare", 1500, "statement_credit", 250),
    ("Myntra", "apparel", 3000, "statement_credit", 600),
    ("Reliance Digital", "electronics", 20000, "statement_credit", 2000),
    ("Taj", "hotel", 20000, "voucher", 4000),
    ("BigBasket", "groceries", 3000, "statement_credit", 400),
]


def _month_starts(end: date, months: int) -> list[date]:
    out, y, m = [], end.year, end.month
    for _ in range(months):
        out.append(date(y, m, 1))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return sorted(out)


def generate(n_members: int = 400) -> dict:
    random.seed(SEED)
    np.random.seed(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    product_ids = list(PRODUCTS.keys())
    product_weights = [0.18, 0.30, 0.30, 0.22]
    month_starts = _month_starts(REFERENCE_DATE, HISTORY_MONTHS)

    members, txns, lounge_visits, claims, offers = [], [], [], [], []
    tx_counter = 0

    for i in range(n_members):
        mid = f"M{i+1:04d}"
        name = f"{random.choice(FIRST)} {random.choice(LAST)}"
        product_id = random.choices(product_ids, weights=product_weights)[0]
        segment = random.choice(PRODUCT_SEGMENTS[product_id])
        tenure = random.randint(4, 96)
        engagement = float(np.clip(np.random.beta(2.2, 3.0), 0.02, 0.98))
        airport = random.choice(AIRPORTS)
        enrolled_milestone = random.random() < (0.25 + 0.6 * engagement)
        # redemption behaviour: low-engagement hoard or take statement credit (poor value)
        redemption_mode = random.choices(
            ["none", "statement_credit", "hotel_transfer", "airline_premium"],
            weights=[0.30, 0.34 - 0.2 * engagement, 0.20 + 0.1 * engagement, 0.16 + 0.1 * engagement],
        )[0]

        seg = SEGMENTS[segment]
        prod = PRODUCTS[product_id]
        # category mix (normalised proportions) for this segment
        weights = {c: seg.get(c, 0) for c in CATEGORY_ORDER}
        wsum = sum(weights.values()) or 1.0
        weights = {c: w / wsum for c, w in weights.items()}
        lo, hi = PRODUCT_MONTHLY_SPEND[product_id]
        monthly_total = random.uniform(lo, hi)
        cat_month_base = {c: monthly_total * w for c, w in weights.items()}

        annual_spend_est = 0.0
        # ---- transactions ----
        for ms in month_starts:
            for cat in CATEGORY_ORDER:
                base = cat_month_base.get(cat, 0)
                if base <= 0:
                    continue
                spend = max(0.0, np.random.normal(base, base * 0.4))
                if spend < 100:
                    continue
                annual_spend_est += spend
                n_tx = random.randint(1, 5)
                for amt in (np.random.dirichlet(np.ones(n_tx)) * spend):
                    if amt < 50:
                        continue
                    tx_counter += 1
                    d = ms + timedelta(days=random.randint(0, 27))
                    merchant = random.choice(MERCHANTS[cat])
                    txns.append({"txn_id": f"T{tx_counter:07d}", "member_id": mid, "date": d.isoformat(),
                                 "category": cat, "merchant": merchant, "amount": round(float(amt), 2)})
                    # ~3% of purchases are later partially refunded (reversal / return)
                    if random.random() < 0.03:
                        tx_counter += 1
                        rd = d + timedelta(days=random.randint(2, 20))
                        if rd <= REFERENCE_DATE:
                            refund = -round(float(amt) * random.uniform(0.4, 1.0), 2)
                            txns.append({"txn_id": f"T{tx_counter:07d}", "member_id": mid,
                                         "date": rd.isoformat(), "category": cat,
                                         "merchant": merchant, "amount": refund})

        # ---- flights, lounge visits (as txn OR pass swipe) ----
        lo, hi = seg["flights_per_year"]
        flights = random.randint(lo, hi)
        has_lounge = any(BENEFITS[b].family == "lounge" for b in prod.benefit_ids)
        for _ in range(flights):
            if has_lounge and random.random() < (0.12 + 0.75 * engagement):
                d = REFERENCE_DATE - timedelta(days=random.randint(0, 360))
                lounge = random.choice(LOUNGE_MERCHANTS)
                if random.random() < 0.6:
                    # recorded as a spend inside the lounge (food/coffee) -> detectable from txns
                    tx_counter += 1
                    txns.append({"txn_id": f"T{tx_counter:07d}", "member_id": mid, "date": d.isoformat(),
                                 "category": "lounge", "merchant": f"{lounge} {airport}",
                                 "amount": round(random.uniform(150, 900), 2)})
                else:
                    # recorded only as a pass swipe in an upstream system (no card txn)
                    lounge_visits.append({"member_id": mid, "date": d.isoformat(),
                                          "airport": airport, "lounge": lounge})

        # ---- protection claims ----
        for b_id in prod.benefit_ids:
            b = BENEFITS[b_id]
            if b.family != "protection":
                continue
            for _ in range(np.random.poisson(0.3)):
                if random.random() < (0.08 + 0.6 * engagement):
                    d = REFERENCE_DATE - timedelta(days=random.randint(0, 360))
                    payout = round(min(b.per_claim_cap or 20000, random.uniform(2000, b.per_claim_cap or 20000)), 2)
                    claims.append({"member_id": mid, "date": d.isoformat(), "benefit_id": b.id, "amount": payout})

        # ---- targeted Amex Offers (per member) ----
        active_cats = [c for c in CATEGORY_ORDER if cat_month_base.get(c, 0) > 1500]
        pool = [o for o in OFFER_POOL if o[1] in active_cats] or OFFER_POOL
        n_offers = random.randint(3, 7)
        for j, off in enumerate(random.sample(pool, min(n_offers, len(pool)))):
            merch, cat, min_spend, rtype, rval = off
            start = REFERENCE_DATE - timedelta(days=random.randint(40, 150))
            end = start + timedelta(days=random.randint(30, 75))
            saved = random.random() < (0.15 + 0.7 * engagement)
            offers.append({"member_id": mid, "offer_id": f"{mid}-O{j+1}", "merchant": merch,
                           "category": cat, "min_spend": min_spend, "reward_type": rtype,
                           "reward_value": rval, "saved": saved,
                           "start_date": start.isoformat(), "end_date": end.isoformat()})

        # rough annual MR earn (excl. non-earning cats) -> plausible points balance
        earn_est = annual_spend_est * 0.7 / prod.rupees_per_point
        points_balance = int(max(0, earn_est * random.uniform(0.6, 3.2)))

        members.append({"member_id": mid, "name": name, "product_id": product_id, "segment": segment,
                        "tenure_months": tenure, "engagement": round(engagement, 3), "home_airport": airport,
                        "enrolled_milestone": enrolled_milestone, "redemption_mode": redemption_mode,
                        "points_balance": points_balance})

    members_df = pd.DataFrame(members)
    txns_df = pd.DataFrame(txns)
    lounge_df = pd.DataFrame(lounge_visits) if lounge_visits else pd.DataFrame(
        columns=["member_id", "date", "airport", "lounge"])
    claims_df = pd.DataFrame(claims) if claims else pd.DataFrame(columns=["member_id", "date", "benefit_id", "amount"])
    offers_df = pd.DataFrame(offers)
    nudge_df = _generate_nudge_history(members_df, txns_df)

    members_df.to_csv(OUT_DIR / "members.csv", index=False)
    txns_df.to_csv(OUT_DIR / "transactions.csv", index=False)
    lounge_df.to_csv(OUT_DIR / "lounge_visits.csv", index=False)
    claims_df.to_csv(OUT_DIR / "claims.csv", index=False)
    offers_df.to_csv(OUT_DIR / "offers.csv", index=False)
    nudge_df.to_csv(OUT_DIR / "nudge_history.csv", index=False)

    meta = {
        "currency": "INR", "reference_date": REFERENCE_DATE.isoformat(), "history_months": HISTORY_MONTHS,
        "n_members": int(len(members_df)), "n_transactions": int(len(txns_df)),
        "n_refunds": int((txns_df["amount"] < 0).sum()), "n_lounge_pass_visits": int(len(lounge_df)),
        "n_claims": int(len(claims_df)), "n_offers": int(len(offers_df)),
        "n_nudge_records": int(len(nudge_df)), "seed": SEED,
    }
    (OUT_DIR / "meta.json").write_text(json.dumps(meta, indent=2))
    return meta


def _generate_nudge_history(members_df: pd.DataFrame, txns_df: pd.DataFrame) -> pd.DataFrame:
    """Labelled past-nudge table for propensity training. Conversion is a noisy function
    of interpretable drivers so the model learns a genuine, explainable signal."""
    rng = np.random.default_rng(SEED)
    pos = txns_df[txns_df["amount"] > 0]
    spend_by_cat = pos.groupby(["member_id", "category"])["amount"].sum().unstack(fill_value=0.0)
    families = ["credit", "lounge", "protection", "offer", "milestone", "points"]
    cats = ["dining", "rideshare", "airline", "online_shopping", "hotel", "apparel"]
    rows = []
    for _, m in members_df.iterrows():
        eng = m["engagement"]
        for _ in range(rng.integers(5, 11)):
            family = rng.choice(families)
            gap = float(rng.uniform(200, 8000))
            days_to_expiry = int(rng.integers(1, 90))
            urgency = 1.0 - days_to_expiry / 90.0
            cat = rng.choice(cats)
            aff = float(spend_by_cat.loc[m["member_id"], cat]) if (m["member_id"] in spend_by_cat.index and cat in spend_by_cat.columns) else 0.0
            aff_norm = float(np.tanh(aff / 60000.0))
            channel = rng.choice(["push", "email", "in_app"])
            ch_lift = {"push": 0.05, "email": -0.03, "in_app": 0.08}[channel]
            logit = (-4.3 + 2.6 * eng + 1.1 * (gap / 8000.0) + 1.5 * urgency
                     + 1.2 * aff_norm + ch_lift + float(rng.normal(0, 0.4)))
            p = 1.0 / (1.0 + np.exp(-logit))
            rows.append({"member_id": m["member_id"], "family": family, "gap_value": round(gap, 2),
                         "days_to_expiry": days_to_expiry, "category_affinity": round(aff_norm, 4),
                         "engagement": eng, "channel": channel, "converted": int(rng.random() < p)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    print(json.dumps(generate(n), indent=2))
