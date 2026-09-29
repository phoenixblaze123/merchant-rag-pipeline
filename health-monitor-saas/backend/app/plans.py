"""Monthly subscription plans offered to customers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    price_cents: int  # per month, USD
    max_devices: int
    retention_days: int
    irregular_rhythm_alerts: bool
    features: tuple[str, ...]


PLANS: dict[str, Plan] = {
    "basic": Plan(
        code="basic",
        name="Basic",
        price_cents=999,
        max_devices=1,
        retention_days=30,
        irregular_rhythm_alerts=False,
        features=("1 wrist device", "30 days of pulse history", "High/low heart-rate alerts"),
    ),
    "pro": Plan(
        code="pro",
        name="Pro",
        price_cents=1999,
        max_devices=5,
        retention_days=365,
        irregular_rhythm_alerts=True,
        features=(
            "Up to 5 wrist devices",
            "12 months of pulse history",
            "High/low heart-rate + irregular-rhythm alerts",
        ),
    ),
}
