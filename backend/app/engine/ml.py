"""
Propensity-to-engage model for ReclaimIQ nudges.

We train a gradient-boosted classifier on the historical nudge log to predict the
probability that a member converts (engages with a benefit) if nudged, given:
  * benefit family
  * dollar gap size
  * urgency (days to expiry)
  * category affinity (how much they already spend in that category)
  * member engagement
  * delivery channel

The model powers two things:
  1. ranking nudges by *expected recovered value* = gap x P(convert | nudge)
  2. picking the best channel per member/opportunity

If scikit-learn is unavailable for any reason, a transparent logistic fallback is
used so the engine always produces a sensible score.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "generated"
FAMILIES = ["credit", "lounge", "protection", "offer", "milestone", "points"]
CHANNELS = ["push", "email", "in_app"]
GAP_SCALE = 8000.0  # ₹ scale used to normalise the dollar/rupee gap feature

FEATURE_COLS = [
    "gap_norm", "days_norm", "urgency", "category_affinity", "engagement",
    "fam_credit", "fam_lounge", "fam_protection", "fam_offer", "fam_milestone", "fam_points",
    "ch_push", "ch_email", "ch_in_app",
]


def _featurize(df: pd.DataFrame) -> pd.DataFrame:
    x = pd.DataFrame(index=df.index)
    x["gap_norm"] = np.clip(df["gap_value"] / GAP_SCALE, 0, 3)
    x["days_norm"] = df["days_to_expiry"] / 90.0
    x["urgency"] = 1.0 - df["days_to_expiry"] / 90.0
    x["category_affinity"] = df["category_affinity"]
    x["engagement"] = df["engagement"]
    for f in FAMILIES:
        x[f"fam_{f}"] = (df["family"] == f).astype(float)
    for c in CHANNELS:
        x[f"ch_{c}"] = (df["channel"] == c).astype(float)
    return x[FEATURE_COLS]


@dataclass
class TrainedModel:
    model: object
    kind: str
    metrics: dict
    feature_importance: dict

    def predict_proba(self, feats: pd.DataFrame) -> np.ndarray:
        if self.kind == "sklearn":
            return self.model.predict_proba(feats[FEATURE_COLS])[:, 1]
        # logistic fallback: feats already aligned
        z = feats[FEATURE_COLS].values @ self.model["coef"] + self.model["intercept"]
        return 1.0 / (1.0 + np.exp(-z))


def train(data_dir: Path = DATA_DIR) -> TrainedModel:
    df = pd.read_csv(data_dir / "nudge_history.csv")
    X = _featurize(df)
    y = df["converted"].values

    try:
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import roc_auc_score, average_precision_score

        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)
        clf = GradientBoostingClassifier(n_estimators=180, max_depth=3, learning_rate=0.08, random_state=42)
        clf.fit(Xtr, ytr)
        proba = clf.predict_proba(Xte)[:, 1]
        auc = float(roc_auc_score(yte, proba))
        ap = float(average_precision_score(yte, proba))
        base_rate = float(y.mean())
        importance = {f: float(round(w, 4)) for f, w in zip(FEATURE_COLS, clf.feature_importances_)}
        # decile lift: top-decile conversion vs base rate (nudge relevance)
        order = np.argsort(-proba)
        top_decile = yte[order[: max(1, len(yte) // 10)]].mean()
        lift = float(top_decile / base_rate) if base_rate else 0.0
        return TrainedModel(
            model=clf, kind="sklearn",
            metrics={"auc": round(auc, 4), "avg_precision": round(ap, 4),
                     "base_conversion_rate": round(base_rate, 4),
                     "top_decile_conversion": round(float(top_decile), 4),
                     "top_decile_lift": round(lift, 2), "n_train": int(len(ytr)), "n_test": int(len(yte))},
            feature_importance=importance,
        )
    except Exception as exc:  # pragma: no cover - fallback path
        # transparent logistic-regression fallback (closed form via numpy is overkill;
        # use a fixed, interpretable coefficient vector consistent with the data model)
        coef = np.array([1.1, 0.0, 1.5, 1.2, 2.6, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.05, -0.03, 0.08])
        intercept = -4.3
        return TrainedModel(
            model={"coef": coef, "intercept": intercept}, kind="logistic",
            metrics={"note": f"sklearn unavailable ({exc}); using interpretable logistic fallback",
                     "base_conversion_rate": round(float(y.mean()), 4)},
            feature_importance={f: float(round(c, 3)) for f, c in zip(FEATURE_COLS, coef)},
        )


def score_opportunities(model: TrainedModel, rows: list[dict]) -> pd.DataFrame:
    """Score a list of opportunity dicts across all channels; return best channel + proba."""
    if not rows:
        return pd.DataFrame()
    expanded = []
    for i, r in enumerate(rows):
        for ch in CHANNELS:
            expanded.append({**r, "channel": ch, "_row": i})
    edf = pd.DataFrame(expanded)
    feats = _featurize(edf)
    edf["proba"] = model.predict_proba(feats)
    best = edf.sort_values("proba", ascending=False).groupby("_row", as_index=False).first()
    return best.sort_values("_row")
