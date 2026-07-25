"""
Core valuation engine for ReclaimIQ (American Express India).

Computes, in rupees, how much benefit value each member has *realized* vs. *left on the
table* across six families:

  credit      realized = max(0, min(cap, qualifying spend NET OF REFUNDS)) per cycle
  lounge      visits detected from (a) in-lounge card transactions and (b) pass swipes;
              potential = reachable travel days x value/visit (capped by visit allotment)
  protection  expected recoverable value = coverage_rate x eligible spend, net of claims
  offer       targeted Amex Offers: spent-at-merchant-but-not-activated = missed value
  milestone   spend-threshold rewards: achieved / near-miss / lost-to-non-enrolment
  points      Membership Rewards balance valued across a redemption range (credit->transfer)

Design goal: every rupee traces to an explicit, explainable rule.

Key assumptions (documented in docs/PROJECT_DESCRIPTION.md):
  * A trailing 12-month window is used as a proxy for the cardmembership year.
  * Lounge "reachable" visits apply an attach rate (not every travel day allows a visit).
  * Protection value is a probabilistic "value at risk", reported separately in the UI.
  * Milestone eligible spend excludes non-earning categories (fuel/utilities).
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from functools import cached_property
from pathlib import Path

import pandas as pd

from app.engine import catalog
from app.engine.catalog import (
    CYCLES_PER_YEAR, BENEFITS, MR_POINT_VALUE, MR_EXCLUDED_CATEGORIES,
    TRANSFER_PARTNERS, product_milestones,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "generated"

LOUNGE_ATTACH_RATE = 0.6            # not every travel day realistically allows a lounge visit
MILESTONE_NEAR_MISS_FRAC = 0.15     # within 15% of a threshold = a "recoverable" near-miss


def _month_add(y: int, m: int, delta: int) -> tuple[int, int]:
    idx = (y * 12 + (m - 1)) + delta
    return idx // 12, idx % 12 + 1


def _cycle_windows(cadence: str, ref: date) -> list[tuple[date, date]]:
    """Calendar-aligned cycle windows over the trailing 12 months; last = current cycle."""
    w: list[tuple[date, date]] = []
    if cadence == "monthly":
        for back in range(11, -1, -1):
            y, m = _month_add(ref.year, ref.month, -back)
            w.append((date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])))
    elif cadence == "quarterly":
        cur_q = (ref.month - 1) // 3
        for back in range(3, -1, -1):
            qi = (ref.year * 4 + cur_q) - back
            y, q = qi // 4, qi % 4
            sm = q * 3 + 1
            ey, em = _month_add(y, sm, 2)
            w.append((date(y, sm, 1), date(ey, em, calendar.monthrange(ey, em)[1])))
    elif cadence == "semiannual":
        cur_h = 0 if ref.month <= 6 else 1
        for back in range(1, -1, -1):
            hi = (ref.year * 2 + cur_h) - back
            y, h = hi // 2, hi % 2
            sm = 1 if h == 0 else 7
            w.append((date(y, sm, 1), date(y, sm + 5, calendar.monthrange(y, sm + 5)[1])))
    else:
        w.append((date(ref.year, 1, 1), date(ref.year, 12, 31)))
    return w


@dataclass
class BenefitResult:
    benefit_id: str
    name: str
    family: str
    cadence: str
    entitlement_value: float
    realized_value: float
    unclaimed_value: float
    utilization: float
    status: str
    eligible_spend: float
    detail: str
    current_cycle_days_left: int | None = None
    current_cycle_remaining: float | None = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return self.__dict__


class Engine:
    def __init__(self, data_dir: Path = DATA_DIR):
        import json
        self.data_dir = data_dir
        self.members = pd.read_csv(data_dir / "members.csv")
        self.txns = pd.read_csv(data_dir / "transactions.csv", parse_dates=["date"])
        self.lounge = pd.read_csv(data_dir / "lounge_visits.csv", parse_dates=["date"])
        self.claims = pd.read_csv(data_dir / "claims.csv", parse_dates=["date"])
        self.offers = pd.read_csv(data_dir / "offers.csv", parse_dates=["start_date", "end_date"])
        self.meta = json.loads((data_dir / "meta.json").read_text())
        self.ref_date = date.fromisoformat(self.meta["reference_date"])
        self.currency_symbol = catalog.CURRENCY_SYMBOL
        self._window_start = pd.Timestamp(self.ref_date) - pd.DateOffset(months=12)
        self._txn_by_member = {m: g for m, g in self.txns.groupby("member_id")}
        self._lounge_by_member = {m: g for m, g in self.lounge.groupby("member_id")} if not self.lounge.empty else {}
        self._claims_by_member = {m: g for m, g in self.claims.groupby("member_id")} if not self.claims.empty else {}
        self._offers_by_member = {m: g for m, g in self.offers.groupby("member_id")} if not self.offers.empty else {}

    # ------------------------------------------------------------------ members
    def member_ids(self) -> list[str]:
        return self.members["member_id"].tolist()

    def member_row(self, member_id: str) -> dict:
        row = self.members.loc[self.members["member_id"] == member_id]
        if row.empty:
            raise KeyError(member_id)
        return row.iloc[0].to_dict()

    def _member_txns(self, member_id: str) -> pd.DataFrame:
        g = self._txn_by_member.get(member_id)
        if g is None:
            return self.txns.iloc[0:0]
        return g[g["date"] >= self._window_start]

    # ----------------------------------------------------------------- credit
    def _value_credit(self, b, txns: pd.DataFrame) -> BenefitResult:
        windows = _cycle_windows(b.cadence, self.ref_date)
        cat_txns = txns[txns["category"].isin(b.categories)]
        qual = cat_txns[cat_txns["merchant"].isin(b.merchants)] if b.merchants else cat_txns
        entitlement = realized = 0.0
        cur_remaining = cur_days_left = None
        for i, (start, end) in enumerate(windows):
            mask = (qual["date"] >= pd.Timestamp(start)) & (qual["date"] <= pd.Timestamp(end))
            # NET OF REFUNDS: negative reversal rows are included in the sum.
            spend = float(qual.loc[mask, "amount"].sum()) * b.qualifying_fraction
            used = max(0.0, min(b.value, spend))
            entitlement += b.value
            realized += used
            if i == len(windows) - 1:
                cur_remaining = round(max(0.0, b.value - used), 2)
                cur_days_left = (end - self.ref_date).days
        unclaimed = max(0.0, entitlement - realized)
        util = realized / entitlement if entitlement else 0.0
        status = "on_track" if util >= 0.8 else ("partial" if util > 0.15 else "unused")
        detail = f"{self.currency_symbol}{realized:,.0f} of {self.currency_symbol}{entitlement:,.0f} used across {len(windows)} {b.cadence} cycle(s) ({util*100:.0f}%)."
        return BenefitResult(b.id, b.name, "credit", b.cadence, round(entitlement, 2), round(realized, 2),
                             round(unclaimed, 2), round(util, 3), status,
                             round(float(cat_txns["amount"].sum()), 2), detail,
                             cur_days_left, cur_remaining)

    # ----------------------------------------------------------------- lounge
    def _detect_lounge_visits(self, member_id: str, txns: pd.DataFrame) -> tuple[int, int, int]:
        """Return (total_visits, from_txn, from_pass) as distinct visit-days."""
        lounge_txn = txns[txns["category"] == "lounge"]
        txn_days = set(lounge_txn["date"].dt.normalize().tolist())
        pass_days = set()
        pv = self._lounge_by_member.get(member_id)
        if pv is not None:
            pv = pv[pv["date"] >= self._window_start]
            pass_days = set(pv["date"].dt.normalize().tolist())
        all_days = txn_days | pass_days
        return len(all_days), len(txn_days), len(pass_days - txn_days)

    def _value_lounge(self, b, txns: pd.DataFrame, member_id: str) -> BenefitResult:
        air = txns[(txns["category"] == "airline") & (txns["amount"] > 0)]
        eligible_trips = int(air["date"].dt.normalize().nunique())
        visits, from_txn, from_pass = self._detect_lounge_visits(member_id, txns)
        vpv = b.value_per_visit or b.value
        reachable = eligible_trips * LOUNGE_ATTACH_RATE
        if b.annual_visit_cap:
            reachable = min(reachable, b.annual_visit_cap)
        potential = reachable * vpv
        realized_value = visits * vpv
        entitlement = max(potential, realized_value)
        unclaimed = max(0.0, potential - realized_value)
        util = min(1.0, realized_value / entitlement) if entitlement else 0.0
        status = "on_track" if util >= 0.8 else ("partial" if util > 0.15 else "unused")
        cap_txt = "unlimited" if not b.annual_visit_cap else f"up to {b.annual_visit_cap}/yr"
        detail = (f"{visits} visit(s) detected ({from_txn} via in-lounge spend, {from_pass} via pass) "
                  f"vs ~{reachable:.0f} reachable on {eligible_trips} travel day(s); {cap_txt}.")
        return BenefitResult(b.id, b.name, "lounge", "per_event", round(entitlement, 2),
                             round(realized_value, 2), round(unclaimed, 2), round(util, 3),
                             status, round(float(air["amount"].sum()), 2), detail,
                             extra={"eligible_trips": eligible_trips, "visits": visits,
                                    "from_txn": from_txn, "from_pass": from_pass, "value_per_visit": vpv})

    # ----------------------------------------------------------------- protection
    def _value_protection(self, b, txns: pd.DataFrame, member_id: str) -> BenefitResult:
        elig = txns[txns["category"].isin(b.categories)]
        eligible_spend = float(elig["amount"].sum())  # net of refunds
        expected = b.coverage_rate * max(0.0, eligible_spend)
        claimed = 0.0
        cdf = self._claims_by_member.get(member_id)
        if cdf is not None:
            m = (cdf["benefit_id"] == b.id) & (cdf["date"] >= self._window_start)
            claimed = float(cdf.loc[m, "amount"].sum())
        unclaimed = max(0.0, expected - claimed)
        entitlement = max(expected, claimed)
        util = claimed / entitlement if entitlement else 0.0
        status = "on_track" if util >= 0.5 else ("partial" if util > 0.05 else "unused")
        detail = (f"{self.currency_symbol}{max(0.0,eligible_spend):,.0f} eligible protected spend; "
                  f"~{self.currency_symbol}{expected:,.0f} expected recoverable, {self.currency_symbol}{claimed:,.0f} claimed.")
        return BenefitResult(b.id, b.name, "protection", b.cadence, round(entitlement, 2), round(claimed, 2),
                             round(unclaimed, 2), round(util, 3), status, round(max(0.0, eligible_spend), 2),
                             detail, extra={"coverage_rate": b.coverage_rate, "expected_recoverable": round(expected, 2)})

    # ----------------------------------------------------------------- offers
    def _value_offers(self, member_id: str, txns: pd.DataFrame) -> dict:
        odf = self._offers_by_member.get(member_id)
        realized = missed = at_risk_val = 0.0
        missed_list, at_risk_list, captured_list = [], [], []
        if odf is not None:
            for _, o in odf.iterrows():
                start, end = o["start_date"], o["end_date"]
                m = ((txns["merchant"] == o["merchant"]) & (txns["date"] >= start) & (txns["date"] <= end))
                spend = float(txns.loc[m, "amount"].sum())  # net of refunds
                reward_inr = float(o["reward_value"]) if o["reward_type"] in ("statement_credit", "voucher") \
                    else float(o["reward_value"]) * MR_POINT_VALUE["hotel_transfer"]
                met = spend >= o["min_spend"]
                saved = bool(o["saved"])
                open_now = pd.Timestamp(self.ref_date) <= end
                item = {"offer_id": o["offer_id"], "merchant": o["merchant"], "category": o["category"],
                        "min_spend": float(o["min_spend"]), "reward_type": o["reward_type"],
                        "reward_value_inr": round(reward_inr, 2), "spend_in_window": round(spend, 2),
                        "saved": saved, "end_date": end.date().isoformat()}
                if saved and met:
                    realized += reward_inr
                    captured_list.append(item)
                elif (not saved) and met:
                    # spent enough at the merchant but never activated the offer -> missed
                    missed += reward_inr
                    missed_list.append(item)
                elif saved and (not met) and open_now:
                    item["remaining_spend"] = round(max(0.0, o["min_spend"] - spend), 2)
                    item["days_left"] = (end.date() - self.ref_date).days
                    at_risk_val += reward_inr
                    at_risk_list.append(item)
        missed_list.sort(key=lambda x: x["reward_value_inr"], reverse=True)
        return {"realized_value": round(realized, 2), "missed_value": round(missed, 2),
                "at_risk_value": round(at_risk_val, 2), "missed": missed_list,
                "at_risk": at_risk_list, "captured": captured_list}

    # ----------------------------------------------------------------- milestones
    def _eligible_spend_series(self, txns: pd.DataFrame) -> pd.DataFrame:
        return txns[(~txns["category"].isin(MR_EXCLUDED_CATEGORIES))]

    def _value_milestones(self, member_id: str, txns: pd.DataFrame, product_id: str, enrolled: bool) -> dict:
        results = []
        realized = unclaimed = 0.0
        elig = self._eligible_spend_series(txns)
        for m in product_milestones(product_id):
            reward = m.reward_value()
            if m.cadence == "annual":
                spend = float(elig["amount"].sum())
                achieved = spend >= m.threshold
                shortfall = max(0.0, m.threshold - spend)
                near = shortfall <= m.threshold * MILESTONE_NEAR_MISS_FRAC
                if achieved and (enrolled or not m.enrollment_required):
                    realized += reward
                    status, unc = "achieved", 0.0
                elif achieved and m.enrollment_required and not enrolled:
                    unc = reward; unclaimed += reward; status = "lost_not_enrolled"
                elif near:
                    unc = reward; unclaimed += reward; status = "near_miss"
                else:
                    unc = 0.0; status = "locked"
                results.append({"milestone_id": m.id, "name": m.name, "cadence": "annual",
                                "threshold": m.threshold, "spend": round(spend, 2),
                                "shortfall": round(shortfall, 2), "reward_value": reward,
                                "reward_points": m.reward_points, "reward_voucher_value": m.reward_voucher_value,
                                "enrollment_required": m.enrollment_required, "enrolled": enrolled,
                                "status": status, "unclaimed_value": round(unc, 2)})
            else:  # monthly
                windows = _cycle_windows("monthly", self.ref_date)
                achieved_months = near_months = lost_months = 0
                for start, end in windows:
                    mmask = (elig["date"] >= pd.Timestamp(start)) & (elig["date"] <= pd.Timestamp(end))
                    mt = elig.loc[mmask]
                    if m.min_transactions:
                        qtx = int((mt["amount"] >= m.min_txn_amount).sum())
                        hit = qtx >= m.min_transactions
                        close = (not hit) and qtx >= m.min_transactions - 1
                    else:
                        s = float(mt["amount"].sum())
                        hit = s >= m.threshold
                        close = (not hit) and s >= m.threshold * (1 - MILESTONE_NEAR_MISS_FRAC)
                    if hit and (enrolled or not m.enrollment_required):
                        achieved_months += 1
                    elif hit and m.enrollment_required and not enrolled:
                        lost_months += 1
                    elif close:
                        near_months += 1
                realized += achieved_months * reward
                unc = (lost_months + near_months) * reward
                unclaimed += unc
                status = "on_track" if achieved_months >= 8 else ("partial" if achieved_months >= 3 else "unused")
                results.append({"milestone_id": m.id, "name": m.name, "cadence": "monthly",
                                "reward_value": reward, "reward_points": m.reward_points,
                                "enrollment_required": m.enrollment_required, "enrolled": enrolled,
                                "achieved_months": achieved_months, "near_miss_months": near_months,
                                "lost_months": lost_months, "status": status, "unclaimed_value": round(unc, 2)})
        return {"realized_value": round(realized, 2), "unclaimed_value": round(unclaimed, 2), "items": results}

    # ----------------------------------------------------------------- points
    def _value_points(self, member_id: str, txns: pd.DataFrame, product_id: str, row: dict) -> dict:
        prod = catalog.PRODUCTS[product_id]
        pos = txns[txns["amount"] > 0]
        eligible = pos[~pos["category"].isin(MR_EXCLUDED_CATEGORIES)]
        base_earned = float(eligible["amount"].sum()) / prod.rupees_per_point
        accel_extra = 0.0
        if prod.accelerators:
            windows = _cycle_windows("monthly", self.ref_date)
            for start, end in windows:
                cap10 = prod.accelerator_monthly_point_caps.get("10x", 1e9)
                cap5 = prod.accelerator_monthly_point_caps.get("5x", 1e9)
                b10 = b5 = 0.0
                mm = eligible[(eligible["date"] >= pd.Timestamp(start)) & (eligible["date"] <= pd.Timestamp(end))]
                for _, t in mm.iterrows():
                    mult = prod.accelerators.get(t["merchant"])
                    if not mult:
                        continue
                    extra = (t["amount"] / prod.rupees_per_point) * (mult - 1)
                    if mult >= 10:
                        b10 += extra
                    else:
                        b5 += extra
                accel_extra += min(b10, cap10) + min(b5, cap5)
        earned_12m = base_earned + accel_extra
        balance = int(row.get("points_balance", 0) or 0)
        mode = row.get("redemption_mode", "none")
        floor = balance * MR_POINT_VALUE["statement_credit"]
        smart = balance * MR_POINT_VALUE["hotel_transfer"]
        ceiling = balance * MR_POINT_VALUE["airline_premium"]
        current_rate = {"none": 0.0, "statement_credit": MR_POINT_VALUE["statement_credit"],
                        "hotel_transfer": MR_POINT_VALUE["hotel_transfer"],
                        "airline_premium": MR_POINT_VALUE["airline_premium"]}.get(mode, 0.0)
        # value being forgone vs. a smart (hotel-transfer) redemption
        under_redemption_gap = max(0.0, balance * (MR_POINT_VALUE["hotel_transfer"] - current_rate))
        if mode == "none":
            msg = f"{balance:,} points sitting unredeemed \u2014 worth {self.currency_symbol}{floor:,.0f} as statement credit, up to {self.currency_symbol}{ceiling:,.0f} via {TRANSFER_PARTNERS[1]}."
        elif mode == "statement_credit":
            msg = f"You redeem as statement credit ({self.currency_symbol}{floor:,.0f}). Transferring to partners could be worth up to {self.currency_symbol}{ceiling:,.0f}."
        else:
            msg = f"You redeem via transfers \u2014 good. Balance worth {self.currency_symbol}{smart:,.0f}\u2013{self.currency_symbol}{ceiling:,.0f}."
        return {"balance": balance, "earned_12m": round(earned_12m, 0), "redemption_mode": mode,
                "value": {"statement_credit": round(floor, 2), "hotel_transfer": round(smart, 2),
                          "airline_premium": round(ceiling, 2)},
                "under_redemption_gap": round(under_redemption_gap, 2),
                "transfer_partners": TRANSFER_PARTNERS, "message": msg}

    # ----------------------------------------------------------------- assemble
    def member_benefits(self, member_id: str) -> list[BenefitResult]:
        row = self.member_row(member_id)
        txns = self._member_txns(member_id)
        out = []
        for b in catalog.product_entitlements(row["product_id"]):
            if b.family == "credit":
                out.append(self._value_credit(b, txns))
            elif b.family == "lounge":
                out.append(self._value_lounge(b, txns, member_id))
            elif b.family == "protection":
                out.append(self._value_protection(b, txns, member_id))
        return out

    def member_summary(self, member_id: str) -> dict:
        row = self.member_row(member_id)
        txns = self._member_txns(member_id)
        product = catalog.PRODUCTS[row["product_id"]]
        benefits = self.member_benefits(member_id)
        offers = self._value_offers(member_id, txns)
        milestones = self._value_milestones(member_id, txns, product.id, bool(row.get("enrolled_milestone")))
        points = self._value_points(member_id, txns, product.id, row)

        unclaimed_by_family = {"credit": 0.0, "lounge": 0.0, "protection": 0.0,
                                "offer": offers["missed_value"], "milestone": milestones["unclaimed_value"]}
        realized_by_family = {"credit": 0.0, "lounge": 0.0, "protection": 0.0,
                               "offer": offers["realized_value"], "milestone": milestones["realized_value"]}
        entitlement_by_family = {"credit": 0.0, "lounge": 0.0, "protection": 0.0}
        for br in benefits:
            unclaimed_by_family[br.family] += br.unclaimed_value
            realized_by_family[br.family] += br.realized_value
            entitlement_by_family[br.family] += br.entitlement_value

        total_unclaimed = round(sum(unclaimed_by_family.values()), 2)
        total_realized = round(sum(realized_by_family.values()), 2)
        total_entitlement = round(sum(entitlement_by_family.values())
                                  + offers["realized_value"] + offers["missed_value"]
                                  + milestones["realized_value"] + milestones["unclaimed_value"], 2)

        # unified opportunity list for nudges / display
        opps = []
        for br in benefits:
            if br.unclaimed_value > 1:
                opps.append({"kind": br.family, "id": br.benefit_id, "name": br.name, "family": br.family,
                             "unclaimed_value": br.unclaimed_value, "detail": br.detail,
                             "current_cycle_days_left": br.current_cycle_days_left, "extra": br.extra})
        for it in offers["missed"]:
            opps.append({"kind": "offer", "id": it["offer_id"], "name": f"Amex Offer · {it['merchant']}",
                         "family": "offer", "unclaimed_value": it["reward_value_inr"],
                         "detail": f"Spent {self.currency_symbol}{it['spend_in_window']:,.0f} at {it['merchant']} but the offer wasn't activated.",
                         "extra": it})
        for it in offers["at_risk"]:
            opps.append({"kind": "offer_at_risk", "id": it["offer_id"], "name": f"Amex Offer · {it['merchant']}",
                         "family": "offer", "unclaimed_value": it["reward_value_inr"],
                         "detail": f"Activated: spend {self.currency_symbol}{it.get('remaining_spend',0):,.0f} more by {it['end_date']} ({it.get('days_left','?')} days).",
                         "extra": it})
        for it in milestones["items"]:
            if it["unclaimed_value"] > 1:
                if it["cadence"] == "annual":
                    det = (f"{self.currency_symbol}{it['shortfall']:,.0f} more spend unlocks {self.currency_symbol}{it['reward_value']:,.0f}"
                           + (" (enrolment needed)" if it["enrollment_required"] and not it["enrolled"] else "")) if it["status"] in ("near_miss", "lost_not_enrolled") else it["name"]
                else:
                    det = f"{it.get('near_miss_months',0)+it.get('lost_months',0)} month(s) narrowly missed this monthly bonus."
                opps.append({"kind": "milestone", "id": it["milestone_id"], "name": it["name"],
                             "family": "milestone", "unclaimed_value": it["unclaimed_value"], "detail": det, "extra": it})
        opps.sort(key=lambda x: x["unclaimed_value"], reverse=True)

        return {
            "member_id": member_id, "name": row["name"], "segment": row["segment"],
            "currency_symbol": self.currency_symbol,
            "product": {"id": product.id, "name": product.name, "tier": product.tier,
                         "annual_fee": product.annual_fee, "color": product.color},
            "total_unclaimed": total_unclaimed, "total_realized": total_realized,
            "total_entitlement": total_entitlement,
            "utilization": round(total_realized / total_entitlement, 3) if total_entitlement else 0.0,
            "unclaimed_by_family": {k: round(v, 2) for k, v in unclaimed_by_family.items()},
            "realized_by_family": {k: round(v, 2) for k, v in realized_by_family.items()},
            "annual_fee_offset": round((total_realized / product.annual_fee) if product.annual_fee else 0.0, 2),
            "benefits": [b.to_dict() for b in benefits],
            "offers": offers, "milestones": milestones, "points": points,
            "top_opportunities": opps[:6],
        }

    @cached_property
    def all_summaries(self) -> dict[str, dict]:
        return {mid: self.member_summary(mid) for mid in self.member_ids()}

    # ---------------------------------------------------------------- portfolio
    def portfolio(self) -> dict:
        s = self.all_summaries
        n = len(s)
        fam = {"credit": 0.0, "lounge": 0.0, "protection": 0.0, "offer": 0.0, "milestone": 0.0}
        total_unclaimed = total_realized = total_entitlement = 0.0
        points_value_locked = 0.0
        for v in s.values():
            total_unclaimed += v["total_unclaimed"]
            total_realized += v["total_realized"]
            total_entitlement += v["total_entitlement"]
            points_value_locked += v["points"]["value"]["hotel_transfer"]
            for k, x in v["unclaimed_by_family"].items():
                fam[k] += x
        by_product: dict[str, dict] = {}
        for v in s.values():
            pid = v["product"]["id"]
            d = by_product.setdefault(pid, {"product": v["product"]["name"], "members": 0,
                                             "unclaimed": 0.0, "realized": 0.0, "entitlement": 0.0})
            d["members"] += 1
            d["unclaimed"] += v["total_unclaimed"]
            d["realized"] += v["total_realized"]
            d["entitlement"] += v["total_entitlement"]
        for d in by_product.values():
            d["unclaimed"] = round(d["unclaimed"], 2); d["realized"] = round(d["realized"], 2)
            d["entitlement"] = round(d["entitlement"], 2)
            d["utilization"] = round(d["realized"] / d["entitlement"], 3) if d["entitlement"] else 0.0
        buckets = {"0-25%": 0, "25-50%": 0, "50-75%": 0, "75-100%": 0}
        for v in s.values():
            u = v["utilization"]
            key = "0-25%" if u < .25 else "25-50%" if u < .5 else "50-75%" if u < .75 else "75-100%"
            buckets[key] += 1
        return {
            "currency_symbol": self.currency_symbol, "n_members": n,
            "total_unclaimed": round(total_unclaimed, 2), "total_realized": round(total_realized, 2),
            "total_entitlement": round(total_entitlement, 2),
            "avg_unclaimed_per_member": round(total_unclaimed / n, 2) if n else 0.0,
            "portfolio_utilization": round(total_realized / total_entitlement, 3) if total_entitlement else 0.0,
            "unclaimed_by_family": {k: round(v, 2) for k, v in fam.items()},
            "points_value_locked": round(points_value_locked, 2),
            "by_product": list(by_product.values()),
            "utilization_distribution": buckets, "reference_date": self.ref_date.isoformat(),
        }
