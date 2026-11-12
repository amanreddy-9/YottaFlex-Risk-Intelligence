"""Bottom-up deterministic synthetic financial world generator.

Execution order strictly follows domain causality:
  1. Master entities: Customers, Merchants, Devices, Accounts (+ Ownership, DeviceLinks, StateEvents)
  2. Baseline ledger: Normal traffic + planted typologies + planted false positives (in exact cents)
  3. Chronological ledger sort & exact running balance reconciliation
  4. Rule evaluation & graph-clustered Cases + historical AnalystActions (derived, never random)
  5. Post-baseline labeled negative edge-case injection (5 mandatory integrity scenarios)
  6. Separate ground_truth generation (strictly isolated from input tables)
"""

from __future__ import annotations

import hashlib
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from yottaflex.engine.case_builder import compute_alert_and_case_priorities
from yottaflex.engine.rule_evaluator import evaluate_rules_on_ledger
from yottaflex.generator.config import REVIEW_ANCHOR, SCALE_PRESETS, SIM_END, SIM_START, ScaleConfig
from yottaflex.generator.rules_catalog import RISK_RULES

FIRST_NAMES = [
    "Liam", "Olivia", "Noah", "Emma", "Ethan", "Ava", "Sophia", "Mason", "Isabella", "Lucas",
    "Mia", "Amelia", "Harper", "Elijah", "James", "Benjamin", "Evelyn", "Charlotte", "Daniel", "Aiden",
    "Priya", "Arjun", "Rohan", "Ananya", "Mei", "Kenji", "Carlos", "Sofia", "Mateo", "Elena",
    "Nadia", "Tariq", "Chloe", "Gabriel", "Hannah", "Samuel", "Zoe", "Victor", "Layla", "Julian",
]
LAST_NAMES = [
    "Patel", "Smith", "Johnson", "Garcia", "Chen", "Kim", "Williams", "Brown", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore",
    "Jackson", "Martin", "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez",
    "Lewis", "Robinson", "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen",
]
MERCHANT_SECTORS = [
    ("GROCERY", "5411", "LOW", 0, ["FreshMart", "GreenBasket", "ValleyFoods", "UrbanGrocer", "MetroMarket"]),
    ("UTILITIES", "4900", "LOW", 0, ["CityPower", "MetroWater", "ClearGrid", "SummitEnergy", "FiberLink"]),
    ("RETAIL", "5311", "LOW", 0, ["NorthStar Goods", "PrimeDepot", "HarborOutlet", "ApexRetail", "OakridgeStore"]),
    ("HEALTHCARE", "8099", "LOW", 0, ["CarePlus Clinic", "BeaconHealth", "VitalPharmacy", "MedCore Lab"]),
    ("EDUCATION", "8220", "LOW", 0, ["State University", "TechInstitute", "Global Academy", "Westfield College"]),
    ("TRAVEL", "4511", "MEDIUM", 0, ["SkyBridge Air", "Horizon Hotels", "EuroRail Pass", "Pacific Resorts"]),
    ("ELECTRONICS", "5732", "MEDIUM", 0, ["CircuitHub", "ByteWorks", "QuantumGear", "NanoTech Store"]),
    ("LUXURY", "5944", "HIGH", 1, ["Aurelia Watches", "Maison Royale", "Crown Jewelers", "Velvet Atelier"]),
    ("GAMING", "7995", "HIGH", 1, ["ApexBet Gaming", "LuckySpin Arena", "VortexPlay", "RoyalOdds"]),
    ("CRYPTO_EXCHANGE", "6051", "HIGH", 1, ["CoinBridge Exchange", "BitVault Desk", "NovaSwap", "LedgerDirect"]),
]
COUNTRIES_WEIGHTED = (["US"] * 76) + (["CA"] * 6) + (["GB"] * 6) + (["DE"] * 3) + (["SG"] * 3) + (["IN"] * 3) + (["MX"] * 2) + (["AE"] * 1)
FOREIGN_COUNTRIES = ["GB", "DE", "SG", "AE", "MX", "CA"]
OS_FAMILIES = ["iOS", "Android", "Windows", "macOS", "Linux"]


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


def _usd(cents: int) -> float:
    return round(cents / 100.0, 2)


@dataclass
class _DraftTxn:
    account_id: str
    txn_type: str
    direction: str
    amount_cents: int
    channel: str
    merchant_id: str | None
    device_id: str | None
    counterparty_country: str
    status: str
    occurred_at: datetime
    reference_note: str
    seq_hint: int
    # Filled during ledger reconciliation:
    transaction_id: str = ""
    balance_before_cents: int = 0
    balance_after_cents: int = 0


@dataclass
class _DraftTransfer:
    debit_txn: _DraftTxn
    credit_txn: _DraftTxn | None
    source_account_id: str
    dest_account_id: str
    transfer_amount_cents: int
    is_same_customer: int
    status: str
    initiated_at: datetime
    settled_at: datetime | None


def generate_world(seed: int = 20261022, scale_name: str = "starter") -> dict[str, Any]:
    """Generate the complete deterministic synthetic dataset."""
    if scale_name not in SCALE_PRESETS:
        raise ValueError(f"Unknown scale '{scale_name}'. Expected one of {list(SCALE_PRESETS)}")

    cfg: ScaleConfig = SCALE_PRESETS[scale_name]
    rng = random.Random(seed)

    # ------------------------------------------------------------------
    # 1. MASTER ENTITIES: Customers, Merchants, Devices, Accounts
    # ------------------------------------------------------------------
    customers: list[dict[str, Any]] = []
    cust_by_id: dict[str, dict[str, Any]] = {}
    for i in range(1, cfg.num_customers + 1):
        cid = f"CUS-{i:06d}"
        seg_roll = rng.random()
        if seg_roll < 0.72:
            segment = "RETAIL"
            annual_inc = rng.randint(48_000, 96_000) * 100
        elif seg_roll < 0.90:
            segment = "AFFLUENT"
            annual_inc = rng.randint(140_000, 360_000) * 100
        else:
            segment = "SMB"
            annual_inc = rng.randint(95_000, 280_000) * 100

        kyc_roll = rng.random()
        kyc_tier = "LOW" if kyc_roll < 0.15 else ("STANDARD" if kyc_roll < 0.80 else "ENHANCED")
        risk_rating = "HIGH" if kyc_tier == "LOW" and rng.random() < 0.35 else ("MEDIUM" if rng.random() < 0.25 else "LOW")
        created_dt = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(
            days=rng.randint(0, 450), seconds=rng.randint(0, 86000)
        )
        kyc_dt = created_dt + timedelta(hours=rng.randint(1, 48))
        first_n = rng.choice(FIRST_NAMES)
        last_n = rng.choice(LAST_NAMES)
        email = f"{first_n.lower()}.{last_n.lower()}.{i:04d}@yottaflex.io"
        phone = f"+1-555-{(100 + (i // 10000)):03d}-{i % 10000:04d}"
        cust = {
            "customer_id": cid,
            "full_name": f"{first_n} {last_n}",
            "email": email,
            "phone": phone,
            "segment": segment,
            "kyc_tier": kyc_tier,
            "kyc_verified_at": _iso(kyc_dt),
            "declared_annual_income": _usd(annual_inc),
            "home_country": rng.choice(COUNTRIES_WEIGHTED),
            "risk_rating": risk_rating,
            "status": "ACTIVE",
            "created_at": _iso(created_dt),
        }
        customers.append(cust)
        cust_by_id[cid] = cust

    merchants: list[dict[str, Any]] = []
    merchants_by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for i in range(1, cfg.num_merchants + 1):
        mid = f"MER-{i:06d}"
        cat, mcc, r_tier, hi_mcc, names = MERCHANT_SECTORS[(i - 1) % len(MERCHANT_SECTORS)]
        country = "US" if rng.random() < 0.78 else rng.choice(FOREIGN_COUNTRIES)
        reg_dt = datetime(2024, 6, 1, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 500))
        m = {
            "merchant_id": mid,
            "merchant_name": f"{rng.choice(names)} #{(i % 97) + 1}",
            "mcc": mcc,
            "category": cat,
            "country": country,
            "risk_tier": r_tier,
            "is_high_risk_mcc": hi_mcc,
            "registered_at": _iso(reg_dt),
        }
        merchants.append(m)
        merchants_by_cat[cat].append(m)

    devices: list[dict[str, Any]] = []
    dev_by_id: dict[str, dict[str, Any]] = {}
    for i in range(1, cfg.num_devices + 1):
        did = f"DEV-{i:06d}"
        fp = hashlib.md5(f"{seed}:DEVICE:{i}".encode()).hexdigest()
        first_dt = datetime(2025, 1, 15, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 460))
        d = {
            "device_id": did,
            "device_fingerprint": fp,
            "os_family": rng.choice(OS_FAMILIES),
            "is_emulator": 0,
            "ip_country": rng.choice(COUNTRIES_WEIGHTED),
            "risk_tier": "LOW",
            "first_observed_at": _iso(first_dt),
        }
        devices.append(d)
        dev_by_id[did] = d

    # Reserve extra typology devices (new devices + shared mule emulators)
    extra_dev_seq = cfg.num_devices + 1

    def make_special_device(is_emulator: int, risk_tier: str, ip_country: str, first_dt: datetime) -> dict[str, Any]:
        nonlocal extra_dev_seq
        did = f"DEV-{extra_dev_seq:06d}"
        fp = hashlib.md5(f"{seed}:DEVICE:{extra_dev_seq}".encode()).hexdigest()
        extra_dev_seq += 1
        d = {
            "device_id": did,
            "device_fingerprint": fp,
            "os_family": "Android" if is_emulator else rng.choice(["iOS", "Android", "macOS"]),
            "is_emulator": is_emulator,
            "ip_country": ip_country,
            "risk_tier": risk_tier,
            "first_observed_at": _iso(first_dt),
        }
        devices.append(d)
        dev_by_id[did] = d
        return d

    # Accounts + AccountOwnership + AccountDeviceLink + AccountStateEvent
    accounts: list[dict[str, Any]] = []
    acct_by_id: dict[str, dict[str, Any]] = {}
    account_ownerships: list[dict[str, Any]] = []
    account_device_links: list[dict[str, Any]] = []
    account_state_events: list[dict[str, Any]] = []

    own_seq = 1
    adl_seq = 1
    ase_seq = 1
    accts_by_cust: dict[str, list[str]] = defaultdict(list)
    cust_primary_device: dict[str, str] = {}
    acct_primary_device: dict[str, str] = {}

    def next_ase(aid: str, prev_st: str | None, new_st: str, dt: datetime, reason: str, actor: str) -> None:
        nonlocal ase_seq
        account_state_events.append({
            "event_id": f"ASE-2026-{ase_seq:06d}",
            "account_id": aid,
            "prev_status": prev_st,
            "new_status": new_st,
            "effective_at": _iso(dt),
            "reason": reason,
            "actor_id": actor,
        })
        ase_seq += 1

    # Assign 1 personal device per customer (first num_customers devices)
    for idx, cust in enumerate(customers):
        cust_primary_device[cust["customer_id"]] = devices[idx]["device_id"]

    # Create primary (-01) accounts then secondary (-02) accounts
    extra_accts_needed = cfg.num_accounts - cfg.num_customers
    acct_specs: list[tuple[dict[str, Any], int]] = [(c, 1) for c in customers]
    for i in range(extra_accts_needed):
        acct_specs.append((customers[i], 2))

    for cust, sub_idx in acct_specs:
        cid = cust["customer_id"]
        aid = f"ACC-{cid}-{sub_idx:02d}"
        if sub_idx == 1:
            acct_type = "BUSINESS" if cust["segment"] == "SMB" else "CHECKING"
        else:
            acct_type = "SAVINGS" if rng.random() < 0.7 else "CHECKING"

        cust_dt = _parse(cust["created_at"])
        opened_dt = max(cust_dt + timedelta(hours=1), datetime(2025, 2, 1, tzinfo=timezone.utc))
        if opened_dt > SIM_START - timedelta(days=3):
            opened_dt = SIM_START - timedelta(days=rng.randint(5, 60))

        od_allowed = 1 if (acct_type != "SAVINGS" and rng.random() < 0.30) else 0
        od_limit_cents = rng.choice([50_000, 100_000]) if od_allowed else 0
        open_bal_cents = rng.randint(250_000, 1_400_000)  # $2,500 .. $14,000

        acct = {
            "account_id": aid,
            "primary_customer_id": cid,
            "account_type": acct_type,
            "currency": "USD",
            "status": "ACTIVE",
            "overdraft_allowed": od_allowed,
            "overdraft_limit": _usd(od_limit_cents),
            "opening_balance": _usd(open_bal_cents),
            "current_balance": _usd(open_bal_cents),  # Derived after ledger sort
            "opened_at": _iso(opened_dt),
            "closed_at": None,
            "_open_bal_cents": open_bal_cents,
            "_od_limit_cents": od_limit_cents,
        }
        accounts.append(acct)
        acct_by_id[aid] = acct
        accts_by_cust[cid].append(aid)

        # Primary ownership (joint owners added post-cohort on normal accounts)
        account_ownerships.append({
            "ownership_id": f"OWN-{own_seq:06d}",
            "account_id": aid,
            "customer_id": cid,
            "ownership_role": "PRIMARY",
            "ownership_pct": 100.0,
            "effective_from": _iso(opened_dt),
            "effective_to": None,
        })
        own_seq += 1

        # Link customer's primary trusted device
        dev_id = cust_primary_device[cid]
        acct_primary_device[aid] = dev_id
        account_device_links.append({
            "link_id": f"ADL-{adl_seq:06d}",
            "account_id": aid,
            "device_id": dev_id,
            "first_seen_at": _iso(opened_dt + timedelta(minutes=15)),
            "last_seen_at": _iso(REVIEW_ANCHOR),
            "is_trusted": 1,
        })
        adl_seq += 1

        next_ase(aid, None, "ACTIVE", opened_dt, "ACCOUNT_OPENING", "SYSTEM")

    # ------------------------------------------------------------------
    # 2. ALLOCATE CUSTOMER-DISJOINT COHORTS FOR LIFECYCLE & TYPOLOGIES
    # ------------------------------------------------------------------
    shuffled_cids = [c["customer_id"] for c in customers]
    rng.shuffle(shuffled_cids)
    c_cursor = 0

    def take_cust_primary_accts(n: int) -> list[str]:
        nonlocal c_cursor
        chosen_cids = shuffled_cids[c_cursor : c_cursor + n]
        c_cursor += n
        return [accts_by_cust[cid][0] for cid in chosen_cids]

    closed_aids = take_cust_primary_accts(cfg.closed_accounts)
    dormant_pool_aids = take_cust_primary_accts(cfg.dormant_accounts_pool)
    dormant_react_aids = dormant_pool_aids[: cfg.dormant_scenarios]
    dormant_stay_aids = dormant_pool_aids[cfg.dormant_scenarios :]

    velocity_aids = take_cust_primary_accts(cfg.velocity_scenarios)
    new_device_aids = take_cust_primary_accts(cfg.new_device_scenarios)
    ring_aids = take_cust_primary_accts(cfg.circular_rings * 4)
    shared_dev_aids = take_cust_primary_accts(cfg.shared_device_clusters * 4)

    remaining_cids = shuffled_cids[c_cursor:]
    multi_cust_pool = [cid for cid in remaining_cids if len(accts_by_cust[cid]) >= 2]
    fp_sweep_count = min(len(multi_cust_pool), max(2, cfg.false_positive_scenarios // 3))
    fp_sweep_custs = multi_cust_pool[:fp_sweep_count]
    fp_sweep_cid_set = set(fp_sweep_custs)

    rem_single_cids = [cid for cid in remaining_cids if cid not in fp_sweep_cid_set]
    fp_other_needed = cfg.false_positive_scenarios - fp_sweep_count
    fp_travel_count = fp_other_needed // 2
    fp_bonus_count = fp_other_needed - fp_travel_count
    fp_travel_aids = [accts_by_cust[cid][0] for cid in rem_single_cids[:fp_travel_count]]
    fp_bonus_aids = [accts_by_cust[cid][0] for cid in rem_single_cids[fp_travel_count : fp_travel_count + fp_bonus_count]]

    used_cids = set(shuffled_cids[:c_cursor]) | fp_sweep_cid_set | set(rem_single_cids[: fp_travel_count + fp_bonus_count])
    normal_cids = [cid for cid in shuffled_cids if cid not in used_cids]
    normal_aids = [aid for cid in normal_cids for aid in accts_by_cust[cid]]

    # Add joint ownership (~10% of normal accounts) to exercise N:M Customer <-> Account
    own_by_acct = {o["account_id"]: o for o in account_ownerships}
    for idx, aid in enumerate(normal_aids):
        if idx % 10 == 0 and len(normal_cids) > 2:
            prim_cid = acct_by_id[aid]["primary_customer_id"]
            joint_cid = normal_cids[(idx + 3) % len(normal_cids)]
            if joint_cid != prim_cid:
                own_by_acct[aid]["ownership_pct"] = 50.0
                account_ownerships.append({
                    "ownership_id": f"OWN-{own_seq:06d}",
                    "account_id": aid,
                    "customer_id": joint_cid,
                    "ownership_role": "JOINT",
                    "ownership_pct": 50.0,
                    "effective_from": acct_by_id[aid]["opened_at"],
                    "effective_to": None,
                })
                own_seq += 1

    # Apply lifecycle transitions for closed and dormant pools
    closed_at_map: dict[str, datetime] = {}
    for aid in closed_aids:
        c_dt = datetime(2026, 8, 5, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 40), hours=rng.randint(1, 20))
        next_ase(aid, "ACTIVE", "CLOSED", c_dt, "CUSTOMER_CLOSURE", acct_by_id[aid]["primary_customer_id"])
        acct_by_id[aid]["status"] = "CLOSED"
        acct_by_id[aid]["closed_at"] = _iso(c_dt)
        closed_at_map[aid] = c_dt

    dormant_since_map: dict[str, datetime] = {}
    for aid in dormant_pool_aids:
        d_dt = datetime(2026, 5, 10, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 10))
        next_ase(aid, "ACTIVE", "DORMANT", d_dt, "INACTIVITY_90D", "SYSTEM")
        acct_by_id[aid]["status"] = "DORMANT"
        dormant_since_map[aid] = d_dt

    # ------------------------------------------------------------------
    # 3. GENERATE TRANSACTIONS & TRANSFER LINKS
    # ------------------------------------------------------------------
    draft_txns: list[_DraftTxn] = []
    draft_transfers: list[_DraftTransfer] = []
    txn_seq_hint = 0

    def add_txn(
        aid: str,
        txn_type: str,
        direction: str,
        amount_cents: int,
        channel: str,
        occurred_at: datetime,
        note: str,
        merchant_id: str | None = None,
        device_id: str | None = None,
        country: str | None = None,
        status: str = "POSTED",
    ) -> _DraftTxn:
        nonlocal txn_seq_hint
        txn_seq_hint += 1
        c_country = country or cust_by_id[acct_by_id[aid]["primary_customer_id"]]["home_country"]
        dt_obj = _DraftTxn(
            account_id=aid,
            txn_type=txn_type,
            direction=direction,
            amount_cents=amount_cents,
            channel=channel,
            merchant_id=merchant_id,
            device_id=device_id,
            counterparty_country=c_country,
            status=status,
            occurred_at=occurred_at,
            reference_note=note,
            seq_hint=txn_seq_hint,
        )
        draft_txns.append(dt_obj)
        return dt_obj

    def add_transfer_pair(
        src_aid: str,
        dst_aid: str,
        amount_cents: int,
        initiated_at: datetime,
        channel: str = "MOBILE_APP",
        device_id: str | None = None,
        note: str = "Account transfer",
        is_internal: bool = False,
    ) -> _DraftTransfer:
        src_cust = acct_by_id[src_aid]["primary_customer_id"]
        dst_cust = acct_by_id[dst_aid]["primary_customer_id"]
        same_cust = 1 if src_cust == dst_cust else 0
        out_type = "INTERNAL_TRANSFER_OUT" if is_internal else "P2P_TRANSFER_OUT"
        in_type = "INTERNAL_TRANSFER_IN" if is_internal else "P2P_TRANSFER_IN"
        settled_at = initiated_at + timedelta(seconds=rng.randint(3, 45))
        d_txn = add_txn(
            src_aid, out_type, "DEBIT", amount_cents, channel, initiated_at,
            f"{note} -> {dst_aid}", device_id=device_id or acct_primary_device[src_aid]
        )
        c_txn = add_txn(
            dst_aid, in_type, "CREDIT", amount_cents, channel, settled_at,
            f"{note} <- {src_aid}", device_id=None
        )
        trl = _DraftTransfer(
            debit_txn=d_txn,
            credit_txn=c_txn,
            source_account_id=src_aid,
            dest_account_id=dst_aid,
            transfer_amount_cents=amount_cents,
            is_same_customer=same_cust,
            status="SETTLED",
            initiated_at=initiated_at,
            settled_at=settled_at,
        )
        draft_transfers.append(trl)
        return trl

    # Make sure edge-case repeats also stay cleanly separated from already-alerted or joint confusion
    # (joint owners on normal accounts don't alter primary_customer_id)
    planted_blueprints: list[dict[str, Any]] = []

    def prefund(aid: str, dt: datetime, amount_cents: int, note: str = "Verified funding credit") -> None:
        # Increase opening liquidity cleanly so baseline debits reconcile without artificial WIRE_IN noise
        acct_by_id[aid]["_open_bal_cents"] += amount_cents
        acct_by_id[aid]["opening_balance"] = _usd(acct_by_id[aid]["_open_bal_cents"])

    # 3A. Velocity Spike Scenarios (RULE-001 + optional RULE-006)
    low_risk_merchants = [m for m in merchants if m["risk_tier"] == "LOW"]
    retail_elec_merchants = [m for m in merchants if m["category"] in ("RETAIL", "ELECTRONICS")]
    high_risk_merchants = [m for m in merchants if m["risk_tier"] == "HIGH"]
    travel_merchants = merchants_by_cat["TRAVEL"]
    edu_merchants = merchants_by_cat["EDUCATION"]

    for idx, aid in enumerate(velocity_aids):
        # Place some older for historical review and most in mid/late Oct 2026
        base_day = datetime(2026, 9, 20, tzinfo=timezone.utc) if idx < cfg.velocity_scenarios // 4 else datetime(2026, 10, 12, tzinfo=timezone.utc)
        t0 = base_day + timedelta(days=rng.randint(0, 10), hours=rng.randint(9, 20))
        prefund(aid, t0 - timedelta(days=4), 2_200_000, "Pre-burst liquidity")
        burst_count = rng.randint(6, 8)
        for b in range(burst_count):
            # Mix structured amounts on half of them
            amt = rng.randint(210_000, 275_000) if (idx % 2 == 0 and b < 3) else rng.randint(85_000, 165_000)
            m = rng.choice(retail_elec_merchants or low_risk_merchants)
            add_txn(
                aid, "MERCHANT_PURCHASE", "DEBIT", amt, "WEB",
                t0 + timedelta(minutes=b * 6), f"Rapid velocity purchase #{b+1}",
                merchant_id=m["merchant_id"], device_id=acct_primary_device[aid],
            )
        planted_blueprints.append({
            "scenario_id": f"SCN-VEL-{idx+1:04d}",
            "typology": "VELOCITY_SPIKE",
            "accounts": {aid},
            "is_true_positive_risk": True,
            "expected_decision": "CONFIRM_FRAUD",
            "notes": f"Planted {burst_count}-txn 60m velocity burst on {aid}",
        })

    # 3B. New Device High-Value Outflows (RULE-002 + RULE-005/008)
    for idx, aid in enumerate(new_device_aids):
        base_day = datetime(2026, 9, 22, tzinfo=timezone.utc) if idx < cfg.new_device_scenarios // 4 else datetime(2026, 10, 13, tzinfo=timezone.utc)
        t0 = base_day + timedelta(days=rng.randint(0, 11), hours=rng.randint(8, 21))
        prefund(aid, t0 - timedelta(days=3), 2_000_000, "Account balance top-up")
        new_dev = make_special_device(is_emulator=1 if idx % 3 == 0 else 0, risk_tier="HIGH", ip_country=rng.choice(FOREIGN_COUNTRIES), first_dt=t0 - timedelta(hours=3))
        account_device_links.append({
            "link_id": f"ADL-{adl_seq:06d}",
            "account_id": aid,
            "device_id": new_dev["device_id"],
            "first_seen_at": _iso(t0 - timedelta(hours=2)),
            "last_seen_at": _iso(t0 + timedelta(minutes=15)),
            "is_trusted": 0,
        })
        adl_seq += 1
        amt = rng.randint(280_000, 680_000)
        m = rng.choice(high_risk_merchants)
        add_txn(
            aid, "MERCHANT_PURCHASE", "DEBIT", amt, "MOBILE_APP", t0,
            "High-value outflow from newly linked device",
            merchant_id=m["merchant_id"], device_id=new_dev["device_id"], country=m["country"],
        )
        planted_blueprints.append({
            "scenario_id": f"SCN-NDEV-{idx+1:04d}",
            "typology": "NEW_DEVICE",
            "accounts": {aid},
            "is_true_positive_risk": True,
            "expected_decision": "ESCALATE",
            "notes": f"New untrusted device {new_dev['device_id']} linked 2h before ${amt/100:,.2f} outflow on {aid}",
        })

    # 3C. Circular Transfer Rings (RULE-003: 4-hop loops A->B->C->D->A within 48h)
    for r_idx in range(cfg.circular_rings):
        ring_accts = ring_aids[r_idx * 4 : (r_idx + 1) * 4]
        if len(ring_accts) < 4:
            break
        base_day = datetime(2026, 9, 18, tzinfo=timezone.utc) if r_idx < cfg.circular_rings // 5 else datetime(2026, 10, 14, tzinfo=timezone.utc)
        t0 = base_day + timedelta(days=rng.randint(0, 9), hours=rng.randint(7, 16))
        principal = rng.randint(450_000, 1_200_000)  # $4,500 .. $12,000
        for ra in ring_accts:
            prefund(ra, t0 - timedelta(days=3), principal + 400_000, "Pre-layering liquidity")
        cur_amt = principal
        for hop in range(4):
            src = ring_accts[hop]
            dst = ring_accts[(hop + 1) % 4]
            hop_dt = t0 + timedelta(hours=hop * 3, minutes=rng.randint(5, 30))
            add_transfer_pair(src, dst, cur_amt, hop_dt, channel="MOBILE_APP", note=f"Layering hop {hop+1}/4")
            cur_amt = int(cur_amt * 0.96)  # small fee decay (~88% return on 4th hop >= 75%)
        planted_blueprints.append({
            "scenario_id": f"SCN-RING-{r_idx+1:04d}",
            "typology": "CIRCULAR_TRANSFER",
            "accounts": set(ring_accts),
            "is_true_positive_risk": True,
            "expected_decision": "FILE_SAR",
            "notes": f"4-hop circular layering ring across {', '.join(ring_accts)}",
        })

    # 3D. Dormant Account Sudden Reactivation (RULE-004)
    for idx, aid in enumerate(dormant_react_aids):
        react_dt = datetime(2026, 10, 10, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 12), hours=rng.randint(9, 18))
        next_ase(aid, "DORMANT", "ACTIVE", react_dt, "REACTIVATION_ACTIVITY", acct_by_id[aid]["primary_customer_id"])
        acct_by_id[aid]["status"] = "ACTIVE"
        in_amt = rng.randint(550_000, 1_400_000)
        add_txn(aid, "WIRE_IN", "CREDIT", in_amt, "WIRE", react_dt + timedelta(minutes=5), "Sudden reactivation wire inflow")
        out_amt = int(in_amt * 0.85)
        m = rng.choice(high_risk_merchants)
        add_txn(
            aid, "MERCHANT_PURCHASE", "DEBIT", out_amt, "WEB", react_dt + timedelta(hours=4),
            "Rapid post-dormancy cash-out", merchant_id=m["merchant_id"], device_id=acct_primary_device[aid], country=m["country"],
        )
        planted_blueprints.append({
            "scenario_id": f"SCN-DORM-{idx+1:04d}",
            "typology": "DORMANT_REACTIVATION",
            "accounts": {aid},
            "is_true_positive_risk": True,
            "expected_decision": "ESCALATE",
            "notes": f"Dormant account {aid} reactivated after ~150d with ${in_amt/100:,.2f} wire & outflow",
        })

    # 3E. Shared Mule Device Clusters (RULE-007: 4 unrelated customers sharing 1 emulator)
    for c_idx in range(cfg.shared_device_clusters):
        cluster_accts = shared_dev_aids[c_idx * 4 : (c_idx + 1) * 4]
        if len(cluster_accts) < 4:
            break
        t0 = datetime(2026, 10, 15, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 7), hours=rng.randint(8, 18))
        mule_dev = make_special_device(is_emulator=1, risk_tier="HIGH", ip_country="US", first_dt=t0 - timedelta(hours=4))
        for k, aid in enumerate(cluster_accts):
            prefund(aid, t0 - timedelta(days=2), 1_000_000, "Mule cluster pre-funding")
            use_dt = t0 + timedelta(hours=k * 2)
            account_device_links.append({
                "link_id": f"ADL-{adl_seq:06d}",
                "account_id": aid,
                "device_id": mule_dev["device_id"],
                "first_seen_at": _iso(use_dt - timedelta(minutes=10)),
                "last_seen_at": _iso(use_dt + timedelta(minutes=30)),
                "is_trusted": 0,
            })
            adl_seq += 1
            m = rng.choice(high_risk_merchants)
            add_txn(
                aid, "MERCHANT_PURCHASE", "DEBIT", rng.randint(180_000, 320_000), "MOBILE_APP",
                use_dt, f"Shared mule device outbound txn #{k+1}",
                merchant_id=m["merchant_id"], device_id=mule_dev["device_id"], country=m["country"],
            )
        planted_blueprints.append({
            "scenario_id": f"SCN-MULE-{c_idx+1:04d}",
            "typology": "NEW_DEVICE",
            "accounts": set(cluster_accts),
            "is_true_positive_risk": True,
            "expected_decision": "FILE_SAR",
            "notes": f"Shared emulator device {mule_dev['device_id']} across 4 distinct accounts",
        })

    # 3F. Deliberate False Positives (3 benign archetypes that intentionally fire rules)
    # Archetype 1: Own-account treasury sweep (fires RULE-001/006, benign same-customer)
    for idx, cid in enumerate(fp_sweep_custs):
        a1, a2 = accts_by_cust[cid][0], accts_by_cust[cid][1]
        t0 = datetime(2026, 10, 8, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 14), hours=10)
        prefund(a1, t0 - timedelta(days=3), 2_200_000, "Verified business/personal balance")
        for b in range(5):
            add_transfer_pair(
                a1, a2, rng.randint(205_000, 265_000), t0 + timedelta(minutes=b * 8),
                channel="WEB", note="Internal savings sweep", is_internal=True,
            )
        planted_blueprints.append({
            "scenario_id": f"SCN-FP-SWEEP-{idx+1:04d}",
            "typology": "FALSE_POSITIVE",
            "accounts": {a1, a2},
            "is_true_positive_risk": False,
            "expected_decision": "MARK_FALSE_POSITIVE",
            "notes": f"Benign own-account sweep between {a1} and {a2} for customer {cid}",
        })

    # Archetype 2: Authorized Travel on Enhanced/Affluent profile (fires RULE-005)
    for idx, aid in enumerate(fp_travel_aids):
        cust = cust_by_id[acct_by_id[aid]["primary_customer_id"]]
        cust["kyc_tier"] = "ENHANCED"
        cust["segment"] = "AFFLUENT"
        t0 = datetime(2026, 10, 6, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 15), hours=14)
        prefund(aid, t0 - timedelta(days=5), 1_500_000, "Authorized travel reserve")
        foreign_travel = [tm for tm in travel_merchants if tm["country"] != cust["home_country"]]
        if not foreign_travel:
            cust["home_country"] = "US"
            foreign_travel = [tm for tm in travel_merchants if tm["country"] != "US"] or travel_merchants
        m = rng.choice(foreign_travel)
        add_txn(
            aid, "MERCHANT_PURCHASE", "DEBIT", rng.randint(150_000, 320_000), "POS", t0,
            "Authorized international airline/hotel booking",
            merchant_id=m["merchant_id"], device_id=acct_primary_device[aid], country=m["country"],
        )
        planted_blueprints.append({
            "scenario_id": f"SCN-FP-TRVL-{idx+1:04d}",
            "typology": "FALSE_POSITIVE",
            "accounts": {aid},
            "is_true_positive_risk": False,
            "expected_decision": "MARK_FALSE_POSITIVE",
            "notes": f"Authorized international travel spend on Enhanced KYC account {aid}",
        })

    # Archetype 3: Large Payroll Bonus + Education/Tuition Bill Pay (fires RULE-008)
    for idx, aid in enumerate(fp_bonus_aids):
        cust = cust_by_id[acct_by_id[aid]["primary_customer_id"]]
        cust["kyc_tier"] = "STANDARD"
        t0 = datetime(2026, 10, 5, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 16), hours=11)
        min_tuition = int((cust["declared_annual_income"] / 12.0) * 0.60 * 100)
        tuition_amt = max(350_000, min_tuition)
        bonus_amt = int(tuition_amt * 1.45)
        add_txn(aid, "PAYROLL_CREDIT", "CREDIT", bonus_amt, "ACH", t0 - timedelta(hours=12), "Annual employer performance bonus")
        m = rng.choice(edu_merchants)
        add_txn(
            aid, "MERCHANT_PURCHASE", "DEBIT", tuition_amt, "WEB", t0,
            "University tuition & verified bill payment",
            merchant_id=m["merchant_id"], device_id=acct_primary_device[aid],
        )
        planted_blueprints.append({
            "scenario_id": f"SCN-FP-BON-{idx+1:04d}",
            "typology": "FALSE_POSITIVE",
            "accounts": {aid},
            "is_true_positive_risk": False,
            "expected_decision": "MARK_FALSE_POSITIVE",
            "notes": f"Verified annual payroll bonus followed by university tuition payment on {aid}",
        })

    # 3G. Normal Background Ledger Traffic up to Exact Target Volume
    reserved_edge_txns = 4 if cfg.edge_case_repeats == 1 else 7
    baseline_target = cfg.target_transactions - reserved_edge_txns

    # First give closed accounts 2-4 normal txns strictly BEFORE closed_at
    for aid in closed_aids:
        c_dt = closed_at_map[aid]
        open_dt = max(SIM_START, _parse(acct_by_id[aid]["opened_at"]))
        if c_dt > open_dt + timedelta(days=5):
            for k in range(3):
                if len(draft_txns) >= baseline_target:
                    break
                t_dt = open_dt + timedelta(days=10 * (k + 1), hours=rng.randint(9, 17))
                if t_dt < c_dt - timedelta(hours=2):
                    m = rng.choice(low_risk_merchants)
                    add_txn(
                        aid, "MERCHANT_PURCHASE", "DEBIT", rng.randint(2_500, 14_000), "POS",
                        t_dt, "Normal pre-closure purchase", merchant_id=m["merchant_id"],
                    )

    # Give every active normal account biweekly payroll credits so balances stay healthy
    active_normal_pool = [aid for aid in normal_aids if acct_by_id[aid]["status"] == "ACTIVE"]
    if not active_normal_pool:
        active_normal_pool = [a["account_id"] for a in accounts if a["status"] == "ACTIVE"]

    for aid in active_normal_pool:
        if len(draft_txns) >= baseline_target - 500:
            break
        cust = cust_by_id[acct_by_id[aid]["primary_customer_id"]]
        # Biweekly paycheck = annual / 26 (~38% of monthly income -> never fires RULE-008)
        pay_cents = int((cust["declared_annual_income"] * 100) / 26)
        for p_idx in range(4):
            if len(draft_txns) >= baseline_target:
                break
            p_dt = SIM_START + timedelta(days=14 * (p_idx + 1) + rng.randint(0, 2), hours=8)
            add_txn(aid, "PAYROLL_CREDIT", "CREDIT", pay_cents, "ACH", p_dt, "Biweekly direct deposit payroll")

    # Fill remaining transaction budget with safe, realistic normal purchases, ATM, and P2P
    # Keep amounts <= $280 and spacing >= 3h per account to avoid accidental rule triggers
    last_normal_dt: dict[str, datetime] = {}
    pool_len = len(active_normal_pool)
    idx_ptr = 0
    while len(draft_txns) < baseline_target:
        aid = active_normal_pool[idx_ptr % pool_len]
        idx_ptr += 1
        prev = last_normal_dt.get(aid, SIM_START + timedelta(days=rng.randint(1, 5)))
        t_dt = prev + timedelta(hours=rng.randint(18, 52), minutes=rng.randint(1, 55))
        if t_dt > SIM_END - timedelta(days=2):
            t_dt = SIM_START + timedelta(days=rng.randint(2, 165), hours=rng.randint(8, 21), minutes=rng.randint(0, 59))
        last_normal_dt[aid] = t_dt

        roll = rng.random()
        if roll < 0.80:
            m = rng.choice(low_risk_merchants)
            add_txn(
                aid, "MERCHANT_PURCHASE", "DEBIT", rng.randint(1_200, 24_000), rng.choice(["POS", "WEB", "MOBILE_APP"]),
                t_dt, f"Purchase at {m['merchant_name']}", merchant_id=m["merchant_id"],
                device_id=acct_primary_device[aid],
            )
        elif roll < 0.90:
            add_txn(
                aid, "ATM_WITHDRAWAL", "DEBIT", rng.choice([4_000, 6_000, 10_000, 14_000]), "ATM",
                t_dt, "ATM cash withdrawal",
            )
        elif roll < 0.96 and len(draft_txns) + 2 <= baseline_target:
            dst_aid = active_normal_pool[(idx_ptr + 7) % pool_len]
            if dst_aid != aid:
                add_transfer_pair(
                    aid, dst_aid, rng.randint(3_500, 22_000), t_dt,
                    channel="MOBILE_APP", note="Routine P2P split", is_internal=False,
                )
        else:
            add_txn(
                aid, "PAYROLL_CREDIT", "CREDIT", rng.randint(120_000, 220_000), "ACH",
                t_dt, "Direct deposit payroll",
            )

    # ------------------------------------------------------------------
    # 4. CHRONOLOGICAL RECONCILIATION & DETERMINISTIC ID ASSIGNMENT
    # ------------------------------------------------------------------
    txns_by_acct: dict[str, list[_DraftTxn]] = defaultdict(list)
    for dt_obj in draft_txns:
        txns_by_acct[dt_obj.account_id].append(dt_obj)

    for aid, acct_txns in txns_by_acct.items():
        acct = acct_by_id[aid]
        acct_txns.sort(key=lambda x: (x.occurred_at, x.seq_hint))
        bal_cents = acct["_open_bal_cents"]
        min_allowed = -acct["_od_limit_cents"]
        for t in acct_txns:
            t.balance_before_cents = bal_cents
            if t.direction == "CREDIT":
                bal_cents += t.amount_cents
            else:
                # Guarantee baseline never violates overdraft limit
                if bal_cents - t.amount_cents < min_allowed:
                    # Only scale normal low-value debits; planted typologies are generously pre-funded
                    avail = max(100, bal_cents - min_allowed)
                    t.amount_cents = min(t.amount_cents, avail)
                bal_cents -= t.amount_cents
            t.balance_after_cents = bal_cents
        acct["current_balance"] = _usd(bal_cents)

    # Global sort & immutable TXN-2026-XXXXXXXX assignment
    draft_txns.sort(key=lambda x: (x.occurred_at, x.account_id, x.seq_hint))
    transactions: list[dict[str, Any]] = []
    for t_idx, t in enumerate(draft_txns, start=1):
        t.transaction_id = f"TXN-2026-{t_idx:08d}"
        transactions.append({
            "transaction_id": t.transaction_id,
            "account_id": t.account_id,
            "txn_type": t.txn_type,
            "direction": t.direction,
            "amount": _usd(t.amount_cents),
            "currency": "USD",
            "balance_before": _usd(t.balance_before_cents),
            "balance_after": _usd(t.balance_after_cents),
            "channel": t.channel,
            "merchant_id": t.merchant_id,
            "device_id": t.device_id,
            "counterparty_country": t.counterparty_country,
            "status": t.status,
            "occurred_at": _iso(t.occurred_at),
            "reference_note": t.reference_note,
        })

    draft_transfers.sort(key=lambda tr: (tr.initiated_at, tr.debit_txn.transaction_id))
    transfer_links: list[dict[str, Any]] = []
    for tr_idx, tr in enumerate(draft_transfers, start=1):
        transfer_links.append({
            "transfer_id": f"TRL-2026-{tr_idx:06d}",
            "debit_txn_id": tr.debit_txn.transaction_id,
            "credit_txn_id": tr.credit_txn.transaction_id if tr.credit_txn else None,
            "source_account_id": tr.source_account_id,
            "dest_account_id": tr.dest_account_id,
            "transfer_amount": _usd(tr.transfer_amount_cents),
            "is_same_customer": tr.is_same_customer,
            "status": tr.status,
            "initiated_at": _iso(tr.initiated_at),
            "settled_at": _iso(tr.settled_at) if tr.settled_at else None,
        })

    # Clean private helper keys from accounts before rule evaluation
    clean_accounts: list[dict[str, Any]] = []
    for a in accounts:
        clean_accounts.append({k: v for k, v in a.items() if not k.startswith("_")})

    # ------------------------------------------------------------------
    # 5. RULE-DRIVEN ALERTS, CASES & BASELINE ANALYST DISPOSITIONS
    # ------------------------------------------------------------------
    alerts, alert_trigger_facts = evaluate_rules_on_ledger(
        customers=customers,
        accounts=clean_accounts,
        account_ownerships=account_ownerships,
        merchants=merchants,
        devices=devices,
        account_device_links=account_device_links,
        account_state_events=account_state_events,
        transactions=transactions,
        transfer_links=transfer_links,
    )

    cases, case_alert_links, case_state_events, _ = compute_alert_and_case_priorities(
        alerts=alerts,
        alert_trigger_facts=alert_trigger_facts,
        accounts=clean_accounts,
        customers=customers,
        account_ownerships=account_ownerships,
        account_device_links=account_device_links,
        devices=devices,
        merchants=merchants,
        transactions=transactions,
        transfer_links=transfer_links,
        account_state_events=account_state_events,
    )

    # Map accounts -> blueprint for ground_truth labeling (isolated!)
    acct_to_blueprint: dict[str, dict[str, Any]] = {}
    for bp in planted_blueprints:
        for aid in bp["accounts"]:
            acct_to_blueprint[aid] = bp

    case_alerts_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    alert_by_id = {a["alert_id"]: a for a in alerts}
    for cal in case_alert_links:
        case_alerts_map[cal["case_id"]].append(alert_by_id[cal["alert_id"]])

    # Add baseline historical AnalystActions on ~20% of older cases (created before 2026-10-08)
    analyst_actions: list[dict[str, Any]] = []
    act_seq = 1
    cse_seq = len(case_state_events) + 1
    analysts = [("ANL-001", "OPS_ANALYST"), ("ANL-002", "OPS_ANALYST"), ("ANL-003", "RISK_REVIEWER"), ("ANL-004", "COMPLIANCE_OFFICER")]

    for c in cases:
        c_dt = _parse(c["created_at"])
        if c_dt < datetime(2026, 10, 8, tzinfo=timezone.utc):
            c_alerts = case_alerts_map[c["case_id"]]
            max_alert_dt = max(_parse(a["created_at"]) for a in c_alerts)
            bp = acct_to_blueprint.get(c["primary_account_id"])
            anl_id, anl_role = rng.choice(analysts)

            # First claim review
            claim_dt = max_alert_dt + timedelta(hours=rng.randint(1, 6))
            act1_id = f"ACT-2026-{act_seq:06d}"
            act_seq += 1
            analyst_actions.append({
                "action_id": act1_id,
                "case_id": c["case_id"],
                "analyst_id": anl_id,
                "analyst_role": anl_role,
                "action_type": "CLAIM_REVIEW",
                "rationale": "Claimed case from prioritized compliance queue for initial evidence review.",
                "acted_at": _iso(claim_dt),
            })
            case_state_events.append({
                "case_event_id": f"CSE-2026-{cse_seq:06d}",
                "case_id": c["case_id"],
                "prev_status": "OPEN",
                "new_status": "IN_REVIEW",
                "analyst_action_id": act1_id,
                "effective_at": _iso(claim_dt),
            })
            cse_seq += 1

            # Final disposition derived from rule evidence
            disp_dt = claim_dt + timedelta(hours=rng.randint(2, 12))
            if bp and not bp["is_true_positive_risk"]:
                act_type, new_st = "MARK_FALSE_POSITIVE", "CLOSED_FALSE_POSITIVE"
                rationale = "Verified benign activity supported by payroll/own-account/KYC context."
            else:
                act_type, new_st = "CONFIRM_FRAUD", "CLOSED_CONFIRMED_FRAUD"
                rationale = "Confirmed anomalous pattern corroborated by transaction facts and entity linkage."

            act2_id = f"ACT-2026-{act_seq:06d}"
            act_seq += 1
            analyst_actions.append({
                "action_id": act2_id,
                "case_id": c["case_id"],
                "analyst_id": anl_id,
                "analyst_role": anl_role,
                "action_type": act_type,
                "rationale": rationale,
                "acted_at": _iso(disp_dt),
            })
            case_state_events.append({
                "case_event_id": f"CSE-2026-{cse_seq:06d}",
                "case_id": c["case_id"],
                "prev_status": "IN_REVIEW",
                "new_status": new_st,
                "analyst_action_id": act2_id,
                "effective_at": _iso(disp_dt),
            })
            cse_seq += 1
            c["status"] = new_st
            c["updated_at"] = _iso(disp_dt)
            for a in c_alerts:
                a["status"] = "DISMISSED" if new_st == "CLOSED_FALSE_POSITIVE" else "RESOLVED"

    # Build baseline ground_truth rows (isolated!)
    ground_truth: list[dict[str, Any]] = []
    for c in cases:
        c_alerts = case_alerts_map[c["case_id"]]
        matched_bp = None
        for a in c_alerts:
            if a["account_id"] in acct_to_blueprint:
                matched_bp = acct_to_blueprint[a["account_id"]]
                break
        if matched_bp:
            ground_truth.append({
                "scenario_id": matched_bp["scenario_id"],
                "entity_type": "CASE",
                "entity_id": c["case_id"],
                "typology": matched_bp["typology"],
                "issue_type": "NONE",
                "is_true_positive_risk": matched_bp["is_true_positive_risk"],
                "expected_decision": matched_bp["expected_decision"],
                "notes": matched_bp["notes"],
            })
        else:
            ground_truth.append({
                "scenario_id": f"SCN-BG-{c['case_id']}",
                "entity_type": "CASE",
                "entity_id": c["case_id"],
                "typology": "FALSE_POSITIVE",
                "issue_type": "NONE",
                "is_true_positive_risk": False,
                "expected_decision": "MARK_FALSE_POSITIVE",
                "notes": "Incidental background rule trigger on normal activity",
            })

    # Also include ground truth for sample normal accounts for full population evaluation
    for idx, aid in enumerate(normal_aids[: min(200, len(normal_aids))], start=1):
        ground_truth.append({
            "scenario_id": f"SCN-NORM-{idx:04d}",
            "entity_type": "ACCOUNT",
            "entity_id": aid,
            "typology": "NORMAL",
            "issue_type": "NONE",
            "is_true_positive_risk": False,
            "expected_decision": "NO_ALERT",
            "notes": "Normal baseline account activity",
        })

    # ------------------------------------------------------------------
    # 6. POST-BASELINE LABELED NEGATIVE EDGE-CASE INJECTION (5 SCENARIOS)
    # ------------------------------------------------------------------
    acct_row_by_id = {a["account_id"]: a for a in clean_accounts}
    next_txn_num = len(transactions) + 1
    next_trl_num = len(transfer_links) + 1
    next_alt_num = len(alerts) + 1
    next_case_num = len(cases) + 1
    next_cal_num = len(case_alert_links) + 1

    # Pick open cases for scenario 5 (DISPOSITION_PRECEDES_ALERT)
    open_cases = [c for c in cases if c["status"] == "OPEN"]
    # Pick non-negative-balance active accounts with overdraft_allowed=0
    no_od_active_aids = [
        a["account_id"] for a in clean_accounts
        if a["status"] == "ACTIVE" and a["overdraft_allowed"] == 0 and a["account_id"] in normal_aids
    ]

    for rep in range(cfg.edge_case_repeats):
        # Edge 1: TXN_ON_CLOSED_ACCOUNT
        c_aid = closed_aids[rep % len(closed_aids)]
        c_acct = acct_row_by_id[c_aid]
        closed_dt = _parse(c_acct["closed_at"])
        bad_dt = closed_dt + timedelta(days=5 + rep)
        bal_b = float(c_acct["current_balance"])
        amt = 185.00
        bad_txn_id = f"TXN-2026-{next_txn_num:08d}"
        next_txn_num += 1
        transactions.append({
            "transaction_id": bad_txn_id,
            "account_id": c_aid,
            "txn_type": "MERCHANT_PURCHASE",
            "direction": "DEBIT",
            "amount": amt,
            "currency": "USD",
            "balance_before": bal_b,
            "balance_after": round(bal_b - amt, 2),
            "channel": "WEB",
            "merchant_id": low_risk_merchants[0]["merchant_id"],
            "device_id": acct_primary_device[c_aid],
            "counterparty_country": "US",
            "status": "POSTED",
            "occurred_at": _iso(bad_dt),
            "reference_note": "Injected post-closure transaction",
        })
        c_acct["current_balance"] = round(bal_b - amt, 2)
        ground_truth.append({
            "scenario_id": f"EDGE-CLOSED-{rep+1:02d}",
            "entity_type": "TRANSACTION",
            "entity_id": bad_txn_id,
            "typology": "NEGATIVE_EDGE_CASE",
            "issue_type": "TXN_ON_CLOSED_ACCOUNT",
            "is_true_positive_risk": False,
            "expected_decision": "QUARANTINE_EXCEPTION",
            "notes": f"Transaction {bad_txn_id} occurred 5+ days after {c_aid} closed at {c_acct['closed_at']}",
        })

        # Edge 2: NEGATIVE_BALANCE_NO_OVERDRAFT
        nod_aid = no_od_active_aids[(rep * 3) % len(no_od_active_aids)]
        nod_acct = acct_row_by_id[nod_aid]
        nod_bal = float(nod_acct["current_balance"])
        overdraw_amt = round(nod_bal + 1250.00, 2)
        nod_txn_id = f"TXN-2026-{next_txn_num:08d}"
        next_txn_num += 1
        nod_dt = datetime(2026, 10, 20, 14, 10, tzinfo=timezone.utc) + timedelta(hours=rep)
        transactions.append({
            "transaction_id": nod_txn_id,
            "account_id": nod_aid,
            "txn_type": "WIRE_OUT",
            "direction": "DEBIT",
            "amount": overdraw_amt,
            "currency": "USD",
            "balance_before": nod_bal,
            "balance_after": round(nod_bal - overdraw_amt, 2),
            "channel": "WIRE",
            "merchant_id": None,
            "device_id": acct_primary_device[nod_aid],
            "counterparty_country": "US",
            "status": "POSTED",
            "occurred_at": _iso(nod_dt),
            "reference_note": "Injected negative balance without overdraft",
        })
        nod_acct["current_balance"] = round(nod_bal - overdraw_amt, 2)
        ground_truth.append({
            "scenario_id": f"EDGE-NEGOD-{rep+1:02d}",
            "entity_type": "TRANSACTION",
            "entity_id": nod_txn_id,
            "typology": "NEGATIVE_EDGE_CASE",
            "issue_type": "NEGATIVE_BALANCE_NO_OVERDRAFT",
            "is_true_positive_risk": False,
            "expected_decision": "QUARANTINE_EXCEPTION",
            "notes": f"Debit on {nod_aid} (overdraft_allowed=0) caused negative balance {nod_acct['current_balance']}",
        })

        # Edge 3: UNRECONCILED_TRANSFER_LEG (rep 0: amount mismatch; rep 1: missing credit leg)
        src_aid = no_od_active_aids[(rep * 3 + 1) % len(no_od_active_aids)]
        dst_aid = no_od_active_aids[(rep * 3 + 2) % len(no_od_active_aids)]
        t_dt = datetime(2026, 10, 21, 11, 0, tzinfo=timezone.utc) + timedelta(hours=rep)
        src_bal = float(acct_row_by_id[src_aid]["current_balance"])
        deb_amt = 1400.00
        deb_id = f"TXN-2026-{next_txn_num:08d}"
        next_txn_num += 1
        transactions.append({
            "transaction_id": deb_id,
            "account_id": src_aid,
            "txn_type": "P2P_TRANSFER_OUT",
            "direction": "DEBIT",
            "amount": deb_amt,
            "currency": "USD",
            "balance_before": src_bal,
            "balance_after": round(src_bal - deb_amt, 2),
            "channel": "MOBILE_APP",
            "merchant_id": None,
            "device_id": acct_primary_device[src_aid],
            "counterparty_country": "US",
            "status": "POSTED",
            "occurred_at": _iso(t_dt),
            "reference_note": "Injected unreconciled transfer debit leg",
        })
        acct_row_by_id[src_aid]["current_balance"] = round(src_bal - deb_amt, 2)

        trl_id = f"TRL-2026-{next_trl_num:06d}"
        next_trl_num += 1
        if rep == 0:
            cred_amt = 1120.00  # mismatched!
            dst_bal = float(acct_row_by_id[dst_aid]["current_balance"])
            cred_id = f"TXN-2026-{next_txn_num:08d}"
            next_txn_num += 1
            transactions.append({
                "transaction_id": cred_id,
                "account_id": dst_aid,
                "txn_type": "P2P_TRANSFER_IN",
                "direction": "CREDIT",
                "amount": cred_amt,
                "currency": "USD",
                "balance_before": dst_bal,
                "balance_after": round(dst_bal + cred_amt, 2),
                "channel": "MOBILE_APP",
                "merchant_id": None,
                "device_id": None,
                "counterparty_country": "US",
                "status": "POSTED",
                "occurred_at": _iso(t_dt + timedelta(seconds=15)),
                "reference_note": "Injected mismatched credit leg",
            })
            acct_row_by_id[dst_aid]["current_balance"] = round(dst_bal + cred_amt, 2)
            transfer_links.append({
                "transfer_id": trl_id,
                "debit_txn_id": deb_id,
                "credit_txn_id": cred_id,
                "source_account_id": src_aid,
                "dest_account_id": dst_aid,
                "transfer_amount": deb_amt,
                "is_same_customer": 0,
                "status": "MISMATCHED",
                "initiated_at": _iso(t_dt),
                "settled_at": _iso(t_dt + timedelta(seconds=15)),
            })
        else:
            transfer_links.append({
                "transfer_id": trl_id,
                "debit_txn_id": deb_id,
                "credit_txn_id": None,
                "source_account_id": src_aid,
                "dest_account_id": dst_aid,
                "transfer_amount": deb_amt,
                "is_same_customer": 0,
                "status": "INCOMPLETE",
                "initiated_at": _iso(t_dt),
                "settled_at": None,
            })
        ground_truth.append({
            "scenario_id": f"EDGE-TRL-{rep+1:02d}",
            "entity_type": "TRANSFER_LINK",
            "entity_id": trl_id,
            "typology": "NEGATIVE_EDGE_CASE",
            "issue_type": "UNRECONCILED_TRANSFER_LEG",
            "is_true_positive_risk": False,
            "expected_decision": "QUARANTINE_EXCEPTION",
            "notes": f"TransferLink {trl_id} legs do not reconcile (debit={deb_amt}, rep={rep})",
        })

        # Edge 4: ORPHAN_ALERT_NO_TRIGGER
        orp_aid = normal_aids[(rep * 5 + 10) % len(normal_aids)]
        orp_cid = acct_row_by_id[orp_aid]["primary_customer_id"]
        orp_alt_id = f"ALT-2026-{next_alt_num:06d}"
        next_alt_num += 1
        orp_dt = datetime(2026, 10, 21, 16, 0, tzinfo=timezone.utc) + timedelta(hours=rep)
        alerts.append({
            "alert_id": orp_alt_id,
            "rule_id": "RULE-001",
            "account_id": orp_aid,
            "customer_id": orp_cid,
            "primary_txn_id": None,
            "severity": "HIGH",
            "risk_score": 45.00,
            "trigger_txn_count": 0,
            "trigger_total_amount": 0.00,
            "explanation_summary": "Injected orphan alert without supporting triggering transaction",
            "status": "GROUPED",
            "created_at": _iso(orp_dt),
        })
        orp_case_id = f"CASE-2026-{next_case_num:06d}"
        next_case_num += 1
        cases.append({
            "case_id": orp_case_id,
            "primary_account_id": orp_aid,
            "primary_customer_id": orp_cid,
            "linkage_summary": "SINGLE_ACCOUNT_BURST",
            "linked_account_count": 1,
            "alert_count": 1,
            "total_exposure_amount": 0.00,
            "priority_score": 25.00,
            "priority_tier": "LOW",
            "status": "OPEN",
            "created_at": _iso(orp_dt),
            "updated_at": _iso(orp_dt),
        })
        case_alert_links.append({
            "case_alert_id": f"CAL-2026-{next_cal_num:06d}",
            "case_id": orp_case_id,
            "alert_id": orp_alt_id,
            "linkage_reason": "SINGLE_ACCOUNT_BURST",
            "linkage_key": orp_aid,
            "linked_at": _iso(orp_dt),
        })
        next_cal_num += 1
        case_state_events.append({
            "case_event_id": f"CSE-2026-{cse_seq:06d}",
            "case_id": orp_case_id,
            "prev_status": None,
            "new_status": "OPEN",
            "analyst_action_id": None,
            "effective_at": _iso(orp_dt),
        })
        cse_seq += 1
        ground_truth.append({
            "scenario_id": f"EDGE-ORPHAN-{rep+1:02d}",
            "entity_type": "ALERT",
            "entity_id": orp_alt_id,
            "typology": "NEGATIVE_EDGE_CASE",
            "issue_type": "ORPHAN_ALERT_NO_TRIGGER",
            "is_true_positive_risk": False,
            "expected_decision": "QUARANTINE_EXCEPTION",
            "notes": f"Alert {orp_alt_id} has primary_txn_id=NULL and zero AlertTriggerFact rows",
        })

        # Edge 5: DISPOSITION_PRECEDES_ALERT
        if open_cases:
            target_case = open_cases[-(rep + 1)]
            early_dt = _parse(target_case["created_at"]) - timedelta(hours=6)
            bad_act_id = f"ACT-2026-{act_seq:06d}"
            act_seq += 1
            analyst_actions.append({
                "action_id": bad_act_id,
                "case_id": target_case["case_id"],
                "analyst_id": "ANL-002",
                "analyst_role": "OPS_ANALYST",
                "action_type": "MARK_FALSE_POSITIVE",
                "rationale": "Injected invalid premature disposition preceding alert creation.",
                "acted_at": _iso(early_dt),
            })
            case_state_events.append({
                "case_event_id": f"CSE-2026-{cse_seq:06d}",
                "case_id": target_case["case_id"],
                "prev_status": "OPEN",
                "new_status": "CLOSED_FALSE_POSITIVE",
                "analyst_action_id": bad_act_id,
                "effective_at": _iso(early_dt),
            })
            cse_seq += 1
            target_case["status"] = "CLOSED_FALSE_POSITIVE"
            ground_truth.append({
                "scenario_id": f"EDGE-PRECEDE-{rep+1:02d}",
                "entity_type": "ANALYST_ACTION",
                "entity_id": bad_act_id,
                "typology": "NEGATIVE_EDGE_CASE",
                "issue_type": "DISPOSITION_PRECEDES_ALERT",
                "is_true_positive_risk": False,
                "expected_decision": "QUARANTINE_EXCEPTION",
                "notes": f"AnalystAction {bad_act_id} on {target_case['case_id']} at {_iso(early_dt)} precedes alert created_at {target_case['created_at']}",
            })

    return {
        "customers": customers,
        "accounts": clean_accounts,
        "account_ownerships": account_ownerships,
        "merchants": merchants,
        "devices": devices,
        "account_device_links": account_device_links,
        "account_state_events": account_state_events,
        "transactions": transactions,
        "transfer_links": transfer_links,
        "risk_rules": RISK_RULES,
        "alerts": alerts,
        "alert_trigger_facts": alert_trigger_facts,
        "cases": cases,
        "case_alert_links": case_alert_links,
        "analyst_actions": analyst_actions,
        "case_state_events": case_state_events,
        "ground_truth": ground_truth,
    }
