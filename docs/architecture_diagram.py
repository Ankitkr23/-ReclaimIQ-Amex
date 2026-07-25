"""
Renders the ReclaimIQ system architecture to docs/architecture.png.

Usage (from repo root, with the backend venv active or matplotlib installed):
    python docs/architecture_diagram.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

NAVY = "#00175a"
BLUE = "#006fcf"
LBLUE = "#e7f1fc"
INK = "#12233b"
MUTED = "#6b7c93"
GREEN = "#1e9e6a"
PURPLE = "#7b5cff"
AMBER = "#c8901a"
ORANGE = "#c25618"
LINE = "#cfd8e3"

fig, ax = plt.subplots(figsize=(15, 8.6), dpi=200)
ax.set_xlim(0, 15)
ax.set_ylim(0, 8.6)
ax.axis("off")
fig.patch.set_facecolor("white")


def box(x, y, w, h, title, lines=None, fc="white", ec=LINE, tc=INK, title_size=11.5,
        line_size=9.2, bold=True, radius=0.10):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.02,rounding_size={radius}",
                                linewidth=1.4, edgecolor=ec, facecolor=fc, mutation_aspect=1))
    cy = y + h - 0.30 if lines else y + h / 2
    ax.text(x + w / 2, cy, title, ha="center", va="center", fontsize=title_size,
            fontweight="bold" if bold else "normal", color=tc)
    if lines:
        ax.text(x + w / 2, cy - 0.30, "\n".join(lines), ha="center", va="top",
                fontsize=line_size, color=MUTED, linespacing=1.5)


def group(x, y, w, h, label, ec):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                linewidth=1.6, edgecolor=ec, facecolor="none", linestyle=(0, (5, 3))))
    ax.text(x + 0.18, y + h - 0.22, label, ha="left", va="center", fontsize=10.5,
            fontweight="bold", color=ec)


def arrow(x1, y1, x2, y2, color=BLUE, lw=1.8, style="-|>"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=15,
                                 linewidth=lw, color=color, shrinkA=2, shrinkB=2))


# ---- Title ----
ax.text(0.2, 8.35, "ReclaimIQ — System Architecture", fontsize=20, fontweight="bold", color=NAVY)
ax.text(0.2, 7.98, "Benefit-Underutilization Analytics · one engine, two audiences",
        fontsize=11, color=MUTED)

# ---- Column 1: Upstream data sources ----
group(0.2, 1.15, 3.5, 6.35, "UPSTREAM DATA  (synthetic in prototype)", MUTED)
srcs = [
    ("Transactions", ["incl. refunds (neg. rows)", "& in-lounge spend"]),
    ("Members", ["enrolment · redemption", "mode · points balance"]),
    ("Amex Offers", ["merchant · threshold", "· activation (saved)"]),
    ("Lounge pass visits", ["partner / Priority Pass"]),
    ("Protection claims", ["insurance administrator"]),
]
sy = 6.30
for name, sub in srcs:
    box(0.45, sy, 3.0, 0.84, name, sub, fc="#f7f9fc", ec=LINE, title_size=10.5, line_size=8.4)
    sy -= 1.03

# ---- Catalog ----
box(4.2, 5.35, 2.7, 1.5, "Benefit Catalog", ["(configuration, not code)", "", "Products · Benefits",
    "Milestones · MR earn/value"], fc=LBLUE, ec=BLUE, title_size=11.5, line_size=8.8)

# ---- Column 2: Analytics Engine ----
group(7.3, 1.15, 4.35, 6.35, "RECLAIMIQ ANALYTICS ENGINE  (Python)", BLUE)

box(7.55, 4.35, 3.85, 2.9, "Valuation Engine",
    ["realized vs. unclaimed, in \u20b9", "", "credit    lounge    protection",
     "offer    milestone    points", "", "refund-aware · lounge-from-txn",
     "offer activation · near-miss"],
    fc="white", ec=GREEN, tc=GREEN, title_size=12, line_size=8.8)

box(7.55, 2.75, 1.85, 1.35, "Propensity", ["model", "GradBoost", "+ LR fallback"],
    fc="white", ec=PURPLE, tc=PURPLE, title_size=10.5, line_size=8.4)
box(9.55, 2.75, 1.85, 1.35, "Nudge Engine", ["expected-value", "rank + channel", "routing"],
    fc="white", ec=ORANGE, tc=ORANGE, title_size=10.5, line_size=8.4)

# ---- FastAPI ----
box(12.05, 4.5, 2.7, 1.5, "FastAPI service", ["/api/members  /summary", "/nudges  /portfolio",
    "/uplift  /catalog"], fc=NAVY, ec=NAVY, tc="white", title_size=12, line_size=8.8)

# ---- React dashboard ----
box(12.05, 2.35, 2.7, 1.5, "React Dashboard", ["Recharts", "", "Card-Member view",
    "Issuer-Portfolio view"], fc=LBLUE, ec=BLUE, title_size=12, line_size=8.8)

# ---- Arrows: sources -> valuation ----
for i in range(5):
    yy = 6.72 - i * 1.03
    arrow(3.45, yy, 7.55, 5.8 - i * 0.12, color=LINE, lw=1.3)
arrow(6.9, 6.05, 7.55, 5.9, color=BLUE)                 # catalog -> valuation
arrow(2.0, 1.15, 2.0, 0.0 + 5.35, color="none", lw=0)   # (spacer, no-op visual)

# ---- Arrows inside engine ----
arrow(8.47, 4.35, 8.47, 4.10, color=PURPLE)             # valuation -> model region
arrow(9.4, 3.42, 9.55, 3.42, color=PURPLE)              # model -> nudge
arrow(9.9, 4.35, 10.3, 4.10, color=GREEN)               # valuation -> nudge

# ---- Engine -> API ----
arrow(11.4, 5.6, 12.05, 5.4, color=BLUE, lw=2)          # valuation aggregates -> API
arrow(11.4, 3.3, 12.05, 4.7, color=ORANGE, lw=2)        # nudges -> API

# ---- API -> Dashboard ----
arrow(13.4, 4.5, 13.4, 3.85, color=BLUE, lw=2)

# ---- Footnote ----
ax.text(0.2, 0.55,
        "Valuation is O(transactions) and parallel per member \u2192 drops into batch (Snowflake/BigQuery/Spark) "
        "or streaming (Kafka) pipelines unchanged.",
        fontsize=9.2, color=MUTED)
ax.text(0.2, 0.24,
        "Every unclaimed-value figure traces to an explicit, auditable rule. All member/transaction data is "
        "synthetic; card products are real (sources cited in catalog.py).",
        fontsize=9.2, color=MUTED)

out = Path(__file__).resolve().parent / "architecture.png"
fig.savefig(out, bbox_inches="tight", facecolor="white")
print(f"wrote {out}")
