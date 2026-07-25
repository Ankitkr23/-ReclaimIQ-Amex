"""Process-wide singletons: load the dataset, train the model, and cache heavy results."""
from __future__ import annotations

from functools import lru_cache

from app.engine.valuation import Engine
from app.engine.nudges import NudgeEngine
from app.engine import ml, catalog


class Store:
    def __init__(self):
        self.engine = Engine()
        self.model = ml.train()
        self.nudges = NudgeEngine(self.engine, self.model)
        self._portfolio = None
        self._uplift = None
        self._members = None

    def portfolio(self):
        if self._portfolio is None:
            self._portfolio = self.engine.portfolio()
        return self._portfolio

    def uplift(self):
        if self._uplift is None:
            self._uplift = self.nudges.uplift_report()
        return self._uplift

    def members_list(self):
        if self._members is None:
            rows = []
            for mid, s in self.engine.all_summaries.items():
                rows.append({
                    "member_id": mid, "name": s["name"], "segment": s["segment"],
                    "product": s["product"]["name"], "product_id": s["product"]["id"],
                    "product_color": s["product"]["color"],
                    "total_unclaimed": s["total_unclaimed"],
                    "total_realized": s["total_realized"],
                    "utilization": s["utilization"],
                })
            rows.sort(key=lambda r: r["total_unclaimed"], reverse=True)
            self._members = rows
        return self._members


@lru_cache(maxsize=1)
def get_store() -> Store:
    return Store()
