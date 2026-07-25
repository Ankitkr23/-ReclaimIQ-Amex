"""
Benefit entitlement catalog for the ReclaimIQ analytics engine (American Express India).

This is the single source of truth that maps card *products* to their full set of
*benefit entitlements*. It is grounded in the real, current (2026) American Express India
line-up. Figures are taken from public product pages / reviews and are captured here as
configuration; every card and benefit cites its source inline.

Sources (accessed Jul 2026):
  * Platinum Charge      americanexpress.com/in/charge-cards/platinum-card/ ; cardadvisor.in;
                         captaintorch.in/articles/amex-platinum-charge
  * Platinum Travel      americanexpress.com/in/credit-cards/platinum-travel-credit-card/ ;
                         milestone devaluation eff. 09-Mar-2026 (pickmycard.in, rightonpoints.com)
  * MRCC                 americanexpress.com/in/credit-cards/membership-rewards-card/
  * SmartEarn            americanexpress.com/in/credit-cards/smart-earn-credit-card/
  * MR point value       cardadvisor.in/articles/amex-membership-rewards-guide-2026 ; rivo.pe
  * Amex Offers          americanexpress.com/in/network/amex-offers-faqs.html

Benefit families modelled (problem statement core = credit / lounge / protection; the
other three extend "the full set of benefit entitlements"):
  credit      recurring statement credits (Platinum Charge travel/hotel/dining credits)
  lounge      airport lounge access entitlements
  protection  purchase / travel insurance coverage
  offer       targeted, activation-gated Amex Offers (per member)
  milestone   spend-threshold-unlocked rewards (points + vouchers)
  points      Membership Rewards earned and their redemption-value range

NOTE: All member/transaction data in this project is synthetic. Card products are real,
but no real cardmember data is used.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

CURRENCY = "INR"
CURRENCY_SYMBOL = "\u20b9"  # ₹

# ---------------------------------------------------------------------------
# Spend categories used to match transactions to benefits (proxy for MCC groups).
# ---------------------------------------------------------------------------
CATEGORIES = [
    "dining",
    "groceries",
    "online_shopping",
    "apparel",
    "electronics",
    "airline",
    "hotel",
    "rideshare",
    "streaming",
    "entertainment",
    "wireless",
    "utilities",
    "fuel",
    "wellness",
    "lounge",
    "general",
]

# Membership Rewards points are NOT earned on these categories in India.
# Source: Amex India card T&Cs (fuel, insurance, utilities excluded).
MR_EXCLUDED_CATEGORIES = {"fuel", "utilities"}

# Realistic per-point redemption value range for MR points in India (₹ per point).
# Source: cardadvisor.in / rivo.pe / cardtrail.in (2026).
MR_POINT_VALUE = {
    "statement_credit": 0.25,   # floor: 1 MR = ₹0.25 (INR 1 = 4 MR)
    "hotel_transfer": 0.50,     # Marriott Bonvoy 1:1, economy redemptions
    "airline_premium": 1.50,    # airline 2:1 transfer, premium-cabin sweet spots
}

# Named transfer partners for member-facing messaging.
TRANSFER_PARTNERS = ["Marriott Bonvoy (1:1)", "Singapore KrisFlyer (2:1)", "British Airways Avios (2:1)"]

CYCLES_PER_YEAR = {"monthly": 12, "quarterly": 4, "semiannual": 2, "annual": 1, "per_event": 1}


# ---------------------------------------------------------------------------
# Benefit definition (credit / lounge / protection)
# ---------------------------------------------------------------------------
@dataclass
class Benefit:
    id: str
    name: str
    family: str            # credit | lounge | protection
    cadence: str           # monthly | quarterly | semiannual | annual | per_event
    value: float           # ₹: credit cap per cycle / lounge value per visit / protection annual ceiling
    categories: list[str] = field(default_factory=list)
    description: str = ""
    merchants: list[str] = field(default_factory=list)   # credit: only these merchants qualify
    qualifying_fraction: float = 1.0                     # credit: fraction of eligible spend that qualifies
    coverage_rate: float = 0.0                           # protection: expected recoverable fraction of spend
    per_claim_cap: Optional[float] = None                # protection
    value_per_visit: Optional[float] = None              # lounge
    annual_visit_cap: Optional[int] = None               # lounge: max complimentary visits / year (None = unlimited)
    lounge_merchants: list[str] = field(default_factory=list)  # lounge: merchant strings that signal a visit

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Milestone definition (spend-threshold-unlocked rewards)
# ---------------------------------------------------------------------------
@dataclass
class Milestone:
    id: str
    name: str
    cadence: str                 # annual | monthly
    threshold: float             # ₹ spend needed in the period
    reward_points: int = 0       # Membership Rewards points awarded
    reward_voucher_value: float = 0.0   # ₹ face value of any voucher
    enrollment_required: bool = False
    # some monthly milestones also need a minimum number of transactions
    min_transactions: int = 0
    min_txn_amount: float = 0.0
    description: str = ""

    def reward_value(self) -> float:
        """₹ value of the reward (points valued at the 'hotel_transfer' mid rate)."""
        return round(self.reward_points * MR_POINT_VALUE["hotel_transfer"] + self.reward_voucher_value, 2)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["reward_value"] = self.reward_value()
        return d


LOUNGE_MERCHANTS = ["Centurion Lounge", "Priority Pass Lounge", "Adani Lounge", "Travel Club Lounge", "Encalm Lounge"]

# ---------------------------------------------------------------------------
# Benefit catalog
# ---------------------------------------------------------------------------
BENEFITS: dict[str, Benefit] = {
    # ---- Platinum Charge statement credits (~₹40k/yr). Source: cardadvisor.in ----
    "travel_credit": Benefit(
        id="travel_credit", name="Annual Travel Credit", family="credit", cadence="annual",
        value=25000.0, categories=["airline", "hotel"], merchants=["Amex Travel"],
        description="Up to \u20b925,000/yr on flights & hotels booked via Amex Travel.",
    ),
    "hotel_fhr_credit": Benefit(
        id="hotel_fhr_credit", name="Fine Hotels & Resorts Credit", family="credit", cadence="annual",
        value=10000.0, categories=["hotel"], merchants=["Taj", "Marriott", "FHR"],
        description="Up to \u20b910,000/yr Fine Hotels + Resorts stay credit.",
    ),
    "dining_credit": Benefit(
        id="dining_credit", name="Premium Dining Credit", family="credit", cadence="semiannual",
        value=2500.0, categories=["dining"], merchants=["Taj", "EazyDiner", "Social"],
        description="Up to \u20b92,500 twice a year at select premium dining partners.",
    ),
    # ---- Lounge access ----
    "lounge_unlimited": Benefit(
        id="lounge_unlimited", name="Global Lounge Collection", family="lounge", cadence="per_event",
        value=2500.0, value_per_visit=2500.0, annual_visit_cap=None, categories=["airline"],
        lounge_merchants=LOUNGE_MERCHANTS,
        description="Unlimited access to 1,400+ lounges worldwide (Priority Pass, Centurion, Amex).",
    ),
    "lounge_domestic": Benefit(
        id="lounge_domestic", name="Complimentary Domestic Lounge Access", family="lounge", cadence="per_event",
        value=1000.0, value_per_visit=1000.0, annual_visit_cap=8, categories=["airline"],
        lounge_merchants=LOUNGE_MERCHANTS,
        description="Up to 8 complimentary domestic airport lounge visits per year.",
    ),
    # ---- Protection / insurance ----
    "purchase_protection": Benefit(
        id="purchase_protection", name="Purchase Protection", family="protection", cadence="annual",
        value=500000.0, categories=["electronics", "online_shopping", "apparel"],
        coverage_rate=0.0015, per_claim_cap=50000.0,
        description="Covers eligible purchases against damage or theft for up to 90 days.",
    ),
    "travel_insurance": Benefit(
        id="travel_insurance", name="Travel Insurance (delay/baggage)", family="protection", cadence="annual",
        value=300000.0, categories=["airline"], coverage_rate=0.004, per_claim_cap=30000.0,
        description="Trip delay, baggage loss and travel accident cover on flights charged to the card.",
    ),
    "credit_shield": Benefit(
        id="credit_shield", name="Credit Shield / Emergency Cover", family="protection", cadence="annual",
        value=100000.0, categories=["general"], coverage_rate=0.0008, per_claim_cap=20000.0,
        description="Emergency medical and card-liability protection.",
    ),
}


# ---------------------------------------------------------------------------
# Milestone catalog
# ---------------------------------------------------------------------------
MILESTONES: dict[str, list[Milestone]] = {
    # Platinum Travel, effective 09-Mar-2026. Source: pickmycard.in, rightonpoints.com, Amex T&C
    "platinum_travel": [
        Milestone("pt_190k", "\u20b91.9L Spend Milestone", "annual", 190000, reward_points=7500,
                  description="7,500 MR points at \u20b91.9L annual spend."),
        Milestone("pt_400k", "\u20b94L Spend Milestone", "annual", 400000, reward_points=10000,
                  description="Additional 10,000 MR points at \u20b94L annual spend."),
        Milestone("pt_700k", "\u20b97L Spend Milestone", "annual", 700000, reward_points=22500,
                  reward_voucher_value=10000.0,
                  description="22,500 MR points + \u20b910,000 Taj Stay voucher at \u20b97L annual spend."),
    ],
    # MRCC monthly milestones. Source: americanexpress.com/in membership-rewards-card
    "mrcc": [
        Milestone("mrcc_4txn", "4 Transactions / Month", "monthly", 0, reward_points=1000,
                  min_transactions=4, min_txn_amount=1500.0,
                  description="1,000 MR points for 4 transactions of \u20b91,500+ in a calendar month."),
        Milestone("mrcc_20k", "\u20b920,000 Monthly Spend", "monthly", 20000, reward_points=1000,
                  enrollment_required=True,
                  description="1,000 MR points for \u20b920,000 spend in a month (enrollment required)."),
    ],
    # SmartEarn annual voucher milestones. Source: americanexpress.com/in smart-earn-credit-card
    "smartearn": [
        Milestone("se_120k", "\u20b91.2L Spend Milestone", "annual", 120000, reward_voucher_value=500.0,
                  description="\u20b9500 voucher at \u20b91.2L annual spend."),
        Milestone("se_180k", "\u20b91.8L Spend Milestone", "annual", 180000, reward_voucher_value=500.0,
                  description="\u20b9500 voucher at \u20b91.8L annual spend."),
        Milestone("se_240k", "\u20b92.4L Spend Milestone", "annual", 240000, reward_voucher_value=500.0,
                  description="\u20b9500 voucher at \u20b92.4L annual spend."),
    ],
    # Platinum Charge renewal voucher. Source: americanexpress.com/in charge-cards/platinum-card
    "platinum_charge": [
        Milestone("pc_2000k", "\u20b920L Renewal Milestone", "annual", 2000000, reward_voucher_value=35000.0,
                  description="\u20b935,000 renewal voucher on \u20b920L annual spend."),
    ],
}


# ---------------------------------------------------------------------------
# Card products
# ---------------------------------------------------------------------------
@dataclass
class CardProduct:
    id: str
    name: str
    tier: str
    annual_fee: float
    rupees_per_point: float          # ₹ spend per 1 MR point (base earn rate)
    benefit_ids: list[str]
    milestone_key: Optional[str] = None
    accelerators: dict = field(default_factory=dict)  # merchant -> multiplier (with monthly point caps)
    accelerator_monthly_point_caps: dict = field(default_factory=dict)
    color: str = "#006FCF"

    def to_dict(self) -> dict:
        return asdict(self)


PRODUCTS: dict[str, CardProduct] = {
    # Platinum Charge: ₹66,000 fee, 1 MR/₹40, unlimited lounge, ~₹40k credits, ₹20L renewal voucher.
    "platinum_charge": CardProduct(
        id="platinum_charge", name="Platinum Charge", tier="ultra-premium",
        annual_fee=66000.0, rupees_per_point=40.0, color="#2E3B4E",
        benefit_ids=["travel_credit", "hotel_fhr_credit", "dining_credit", "lounge_unlimited",
                     "purchase_protection", "travel_insurance", "credit_shield"],
        milestone_key="platinum_charge",
    ),
    # Platinum Travel: ₹5,000 fee, 1 MR/₹50, domestic lounge, milestone-led.
    "platinum_travel": CardProduct(
        id="platinum_travel", name="Platinum Travel", tier="premium-travel",
        annual_fee=5000.0, rupees_per_point=50.0, color="#C8102E",
        benefit_ids=["lounge_domestic", "travel_insurance", "purchase_protection"],
        milestone_key="platinum_travel",
    ),
    # MRCC: ₹4,500 fee, 1 MR/₹50, monthly milestones.
    "mrcc": CardProduct(
        id="mrcc", name="Membership Rewards Card (MRCC)", tier="core",
        annual_fee=4500.0, rupees_per_point=50.0, color="#B8860B",
        benefit_ids=["purchase_protection"],
        milestone_key="mrcc",
    ),
    # SmartEarn: ₹495 fee, 1 MR/₹50 base, 10X/5X online accelerators (capped), voucher milestones.
    "smartearn": CardProduct(
        id="smartearn", name="SmartEarn", tier="entry",
        annual_fee=495.0, rupees_per_point=50.0, color="#1E7A46",
        benefit_ids=["purchase_protection"],
        milestone_key="smartearn",
        accelerators={
            "Zomato": 10, "EaseMyTrip": 10, "Flipkart": 10, "Uber": 10, "Myntra": 10,
            "Nykaa": 10, "Ajio": 10, "PVR": 10, "BookMyShow": 10, "Blinkit": 10, "Amazon": 5,
        },
        # 10X bucket capped 500 pts/mo (approx), 5X Amazon 250 pts/mo.
        accelerator_monthly_point_caps={"10x": 500, "5x": 250},
    ),
}


def product_entitlements(product_id: str) -> list[Benefit]:
    return [BENEFITS[bid] for bid in PRODUCTS[product_id].benefit_ids]


def product_milestones(product_id: str) -> list[Milestone]:
    key = PRODUCTS[product_id].milestone_key
    return MILESTONES.get(key, []) if key else []


def annual_face_value(product_id: str) -> float:
    """Advertised annual ₹ value of credits + lounge (headline only)."""
    total = 0.0
    for b in product_entitlements(product_id):
        if b.family == "credit":
            total += b.value * CYCLES_PER_YEAR[b.cadence]
        elif b.family == "lounge":
            visits = b.annual_visit_cap or 12
            total += (b.value_per_visit or b.value) * visits
    for m in product_milestones(product_id):
        total += m.reward_value() * (12 if m.cadence == "monthly" else 1)
    return round(total, 2)


def catalog_as_dict() -> dict:
    return {
        "currency": CURRENCY,
        "currency_symbol": CURRENCY_SYMBOL,
        "categories": CATEGORIES,
        "mr_point_value": MR_POINT_VALUE,
        "transfer_partners": TRANSFER_PARTNERS,
        "benefits": {bid: b.to_dict() for bid, b in BENEFITS.items()},
        "milestones": {k: [m.to_dict() for m in v] for k, v in MILESTONES.items()},
        "products": {
            pid: {**p.to_dict(), "annual_face_value": annual_face_value(pid),
                   "milestones": [m.to_dict() for m in product_milestones(pid)]}
            for pid, p in PRODUCTS.items()
        },
    }
