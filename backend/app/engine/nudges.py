"""
Nudge engine for ReclaimIQ (American Express India).

Turns each member's unclaimed-benefit gaps (across all six families) into prioritized,
personalized engagement prompts. Each nudge is:
  * triggered by an observable spending pattern (unused credit, un-activated Amex Offer,
    near-miss milestone, unused lounge on travel days, protected spend, idle points)
  * ranked by EXPECTED RECOVERED VALUE = rupee gap x P(convert | nudge)  [propensity model]
  * routed to the best channel and given a recommended send window.

Also simulates portfolio-level uplift of model-targeted nudging vs. a blanket campaign.
"""
from __future__ import annotations

from datetime import date
from math import tanh

import numpy as np
import pandas as pd

from app.engine.valuation import Engine
from app.engine import ml

CHANNEL_LABEL = {"push": "Push notification", "email": "Email", "in_app": "In-app card"}
MIN_GAP = 50.0            # ₹ - ignore trivial gaps
POINTS_MIN_GAP = 2000.0   # ₹ - only nudge idle-points when the forgone value is material


def _days_to_year_end(ref: date) -> int:
    return (date(ref.year, 12, 31) - ref).days


class NudgeEngine:
    def __init__(self, engine: Engine, model: ml.TrainedModel | None = None):
        self.engine = engine
        self.model = model or ml.train()
        self.sym = engine.currency_symbol

    def _cat_spend(self, member_id: str) -> dict:
        txns = self.engine._member_txns(member_id)
        pos = txns[txns["amount"] > 0]
        return pos.groupby("category")["amount"].sum().to_dict() if not pos.empty else {}

    def _channel(self, family: str, kind: str, urgent: bool) -> str:
        """Transparent channel routing (the model's channel signal is weak, so we route
        by intent: urgent/time-boxed -> push, transactional -> in-app, awareness -> email)."""
        if urgent or kind == "offer_at_risk":
            return "push"
        return {"offer": "in_app", "credit": "in_app", "milestone": "in_app",
                "lounge": "push", "protection": "email", "points": "email"}.get(family, "in_app")

    def _action(self, family: str, opp: dict) -> tuple[str, str]:
        """Return (action, recommended_timing) for an opportunity."""
        extra = opp.get("extra", {})
        if family == "credit":
            return ("Route an eligible purchase to a qualifying partner before the cycle resets.",
                    "Send mid-cycle if still unused")
        if family == "offer":
            if opp["kind"] == "offer_at_risk":
                return (f"Spend {self.sym}{extra.get('remaining_spend',0):,.0f} more at {extra.get('merchant','the merchant')} before it expires.",
                        "Send now — offer expiring")
            return (f"Save the {extra.get('merchant','')} offer to your card before you shop there next.",
                    "Send before the next likely purchase")
        if family == "milestone":
            need_enrol = extra.get("enrollment_required") and not extra.get("enrolled")
            if need_enrol:
                return ("Enrol for the milestone in the app, then route spend to cross the threshold.",
                        "Send now — enrolment required")
            return ("Route upcoming planned spend to this card to cross the milestone in time.",
                    "Send in the final months of the card year")
        if family == "lounge":
            return ("Add the lounge finder to your wallet and check in on your next trip.",
                    "Send around the next detected travel date")
        if family == "protection":
            return ("Keep receipts — you can file a covered claim in minutes if something goes wrong.",
                    "Send after a large eligible purchase")
        if family == "points":
            return ("Transfer points to a partner (e.g. KrisFlyer/Marriott) instead of statement credit.",
                    "Send when a redemption window is live")
        return ("Review this benefit.", "Send mid-cycle")

    def member_nudges(self, member_id: str, top_k: int = 6) -> dict:
        row = self.engine.member_row(member_id)
        summary = self.engine.member_summary(member_id)
        engagement = float(row.get("engagement", 0.5))
        cat_spend = self._cat_spend(member_id)
        ref = self.engine.ref_date

        opps = list(summary["top_opportunities"])
        # add idle-points as an opportunity when the forgone value is material
        pts = summary["points"]
        if pts["under_redemption_gap"] >= POINTS_MIN_GAP:
            opps.append({"kind": "points", "id": "points", "name": "Membership Rewards points",
                         "family": "points", "unclaimed_value": pts["under_redemption_gap"],
                         "detail": pts["message"], "extra": {}})

        rows, meta = [], []
        for opp in opps:
            gap = opp["unclaimed_value"]
            if gap < MIN_GAP:
                continue
            fam = opp["family"]
            extra = opp.get("extra", {})
            # days to expiry
            if fam == "credit" and opp.get("current_cycle_days_left") is not None:
                days = max(1, int(opp["current_cycle_days_left"]))
            elif opp["kind"] == "offer_at_risk" and extra.get("days_left") is not None:
                days = max(1, int(extra["days_left"]))
            else:
                days = max(1, _days_to_year_end(ref))
            # category affinity
            cat = extra.get("category")
            if cat:
                aff = tanh(cat_spend.get(cat, 0.0) / 60000.0)
            else:
                aff = tanh(sum(cat_spend.values()) / 300000.0)
            rows.append({"family": fam, "gap_value": gap, "days_to_expiry": days,
                         "category_affinity": aff, "engagement": engagement})
            meta.append(opp)

        if not rows:
            return {"member_id": member_id, "name": row["name"], "total_expected_recoverable": 0.0, "nudges": []}

        scored = ml.score_opportunities(self.model, rows)
        nudges = []
        for opp, (_, s) in zip(meta, scored.iterrows()):
            proba = float(s["proba"])
            gap = opp["unclaimed_value"]
            fam = opp["family"]
            action, timing = self._action(fam, opp)
            urgent = opp["kind"] == "offer_at_risk" or (fam == "credit" and (opp.get("current_cycle_days_left") or 99) <= 12)
            urgency = 1.4 if urgent else 1.0
            channel = self._channel(fam, opp["kind"], urgent)
            exp = round(gap * proba, 2)
            nudges.append({
                "kind": opp["kind"], "family": fam, "benefit_name": opp["name"],
                "gap_value": round(gap, 2), "convert_probability": round(proba, 3),
                "expected_recovered_value": exp, "priority_score": round(exp * urgency, 2),
                "channel": channel, "channel_label": CHANNEL_LABEL[channel],
                "headline": opp["detail"], "action": action, "recommended_timing": timing,
            })
        nudges.sort(key=lambda n: n["priority_score"], reverse=True)
        return {"member_id": member_id, "name": row["name"],
                "total_expected_recoverable": round(sum(n["expected_recovered_value"] for n in nudges), 2),
                "nudges": nudges[:top_k]}

    # ------------------------------------------------------------- uplift study
    def uplift_report(self, budget_fraction: float = 0.2) -> dict:
        gaps, probas = [], []
        for mid in self.engine.member_ids():
            for n in self.member_nudges(mid, top_k=100)["nudges"]:
                gaps.append(n["gap_value"]); probas.append(n["convert_probability"])
        gaps = np.array(gaps); probas = np.array(probas)
        exp_val = gaps * probas
        n = len(exp_val)
        k = max(1, int(n * budget_fraction))
        target_idx = np.argsort(-exp_val)[:k]
        targeted_recovered = float(exp_val[target_idx].sum())
        targeted_conv = float(probas[target_idx].mean())
        rng = np.random.default_rng(7)
        rr, rc = [], []
        for _ in range(50):
            idx = rng.choice(n, size=k, replace=False)
            rr.append(float(exp_val[idx].sum())); rc.append(float(probas[idx].mean()))
        random_recovered = float(np.mean(rr)); random_conv = float(np.mean(rc))
        return {
            "currency_symbol": self.sym, "total_opportunities": int(n),
            "budget_fraction": budget_fraction, "nudges_sent": int(k),
            "targeted": {"expected_recovered": round(targeted_recovered, 2),
                          "avg_convert_probability": round(targeted_conv, 3)},
            "random_baseline": {"expected_recovered": round(random_recovered, 2),
                                 "avg_convert_probability": round(random_conv, 3)},
            "recovered_value_uplift_x": round(targeted_recovered / random_recovered, 2) if random_recovered else None,
            "conversion_uplift_x": round(targeted_conv / random_conv, 2) if random_conv else None,
            "model": {"kind": self.model.kind, "metrics": self.model.metrics,
                       "feature_importance": self.model.feature_importance},
        }
