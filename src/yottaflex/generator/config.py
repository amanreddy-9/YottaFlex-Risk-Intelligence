"""Scale and simulation configuration for deterministic synthetic generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

SIM_START = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
SIM_END = datetime(2026, 10, 28, 23, 59, 59, tzinfo=timezone.utc)
REVIEW_ANCHOR = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class ScaleConfig:
    name: str
    num_customers: int
    num_accounts: int
    num_merchants: int
    num_devices: int
    target_transactions: int
    velocity_scenarios: int
    new_device_scenarios: int
    circular_rings: int
    dormant_scenarios: int
    shared_device_clusters: int
    false_positive_scenarios: int
    closed_accounts: int
    dormant_accounts_pool: int
    edge_case_repeats: int


SCALE_PRESETS: dict[str, ScaleConfig] = {
    "starter": ScaleConfig(
        name="starter",
        num_customers=500,
        num_accounts=700,
        num_merchants=80,
        num_devices=620,
        target_transactions=10_000,
        velocity_scenarios=4,
        new_device_scenarios=5,
        circular_rings=3,
        dormant_scenarios=4,
        shared_device_clusters=2,
        false_positive_scenarios=12,
        closed_accounts=15,
        dormant_accounts_pool=25,
        edge_case_repeats=1,
    ),
    "full": ScaleConfig(
        name="full",
        num_customers=5_000,
        num_accounts=7_000,
        num_merchants=400,
        num_devices=6_200,
        target_transactions=100_000,
        velocity_scenarios=36,
        new_device_scenarios=45,
        circular_rings=26,
        dormant_scenarios=40,
        shared_device_clusters=20,
        false_positive_scenarios=115,
        closed_accounts=150,
        dormant_accounts_pool=250,
        edge_case_repeats=2,
    ),
}
