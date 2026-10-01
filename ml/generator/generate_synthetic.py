"""Synthetic Nigerian bank transaction generator (Section 4.3 of the spec).

Produces, under ``--out``:
    customers.csv, accounts.csv, transactions.csv, security_events.csv, summary.json

Usage
-----
    python -m generator.generate_synthetic --out data/synthetic/train \\
        --customers 5000 --days 90 --seed 42 --fraud-rate 0.005 --label-noise-rate 0.02
    python -m generator.generate_synthetic --out data/synthetic/demo \\
        --customers 1000 --days 60 --seed 7 --fraud-rate 0.02

All randomness goes through ``numpy.random.default_rng(seed)`` so runs are
reproducible: the same seed and arguments always produce byte-identical CSVs.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import deque
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from fraud_core.constants import (
    CHANNELS,
    FRAUD_TYPES,
    GLOBAL_LEGIT_AMOUNT_CAP,
    SECURITY_EVENT_TYPES,
    TIMEZONE,
)
from fraud_core.names import FIRST_NAMES, LAST_NAMES

LAGOS = ZoneInfo(TIMEZONE)

# --------------------------------------------------------------------------- #
# Configuration (Section 4.3 tables)
# --------------------------------------------------------------------------- #

SEGMENTS: dict[str, dict] = {
    "student": {
        "share": 0.20, "lambda": 1.0, "median": 3000.0,
        "channels": {"MOBILE": 0.4, "USSD": 0.3, "POS": 0.2, "ATM": 0.1},
    },
    "salaried": {
        "share": 0.40, "lambda": 1.8, "median": 15000.0,
        "channels": {"MOBILE": 0.35, "NIP": 0.25, "POS": 0.2, "INTERNET": 0.1, "ATM": 0.1},
    },
    "trader": {
        "share": 0.25, "lambda": 3.0, "median": 40000.0,
        "channels": {"NIP": 0.35, "MOBILE": 0.3, "USSD": 0.15, "POS": 0.1, "ATM": 0.1},
    },
    "business": {
        "share": 0.15, "lambda": 4.0, "median": 150000.0,
        "channels": {"NIP": 0.45, "INTERNET": 0.35, "MOBILE": 0.2},
    },
}
LOGNORMAL_SIGMA = 1.0

LOCATION_WEIGHTS: dict[str, float] = {
    "Lagos": 0.45, "Abuja": 0.12, "Rivers": 0.08, "Kano": 0.07, "Oyo": 0.07,
    "Kaduna": 0.021, "Enugu": 0.021, "Delta": 0.021, "Edo": 0.021, "Anambra": 0.021,
    "Ogun": 0.021, "Plateau": 0.021, "Borno": 0.021, "Sokoto": 0.021, "Cross River": 0.021,
}
_loc_total = sum(LOCATION_WEIGHTS.values())
LOCATION_NAMES = list(LOCATION_WEIGHTS.keys())
LOCATION_PROBS = [w / _loc_total for w in LOCATION_WEIGHTS.values()]

BANK_CODES = ["058", "044", "011", "033", "057", "050", "070", "232", "221", "214"]

# Hour-of-day distribution: peak 09:00-20:00, 3% between 00:00-05:00 (Section 4.3).
HOUR_WEIGHTS = np.zeros(24)
HOUR_WEIGHTS[0:5] = 0.03 / 5          # 00:00-04:59 -> 3% total
HOUR_WEIGHTS[5:9] = 0.07 / 4          # 05:00-08:59 morning ramp -> 7%
HOUR_WEIGHTS[9:21] = 0.75 / 12        # 09:00-20:59 peak -> 75%
HOUR_WEIGHTS[21:24] = 0.15 / 3        # 21:00-23:59 evening wind-down -> 15%
HOUR_WEIGHTS = HOUR_WEIGHTS / HOUR_WEIGHTS.sum()

FRAUD_SCENARIO_WEIGHTS = {
    "SOCIAL_ENGINEERING": 0.35,
    "ACCOUNT_TAKEOVER": 0.25,
    "SIM_SWAP": 0.20,
    "CARD_FRAUD": 0.20,
}

NEW_ACCOUNT_WINDOW_DAYS = 30
MULE_TARGET_RATE = 0.20  # ~20% of fraud targets new accounts / mule beneficiaries

# Channel -> txn_type mapping. The spec does not define this explicitly; this
# is a documented decision (docs/DECISIONS.md D11).
CHANNEL_TXN_TYPE_CHOICES = {
    "NIP": (["TRANSFER"], [1.0]),
    "INTERNET": (["TRANSFER", "BILL_PAYMENT"], [0.7, 0.3]),
    "MOBILE": (["TRANSFER", "BILL_PAYMENT", "AIRTIME"], [0.5, 0.25, 0.25]),
    "USSD": (["TRANSFER", "AIRTIME", "BILL_PAYMENT"], [0.4, 0.4, 0.2]),
    "POS": (["CARD_PAYMENT"], [1.0]),
    "ATM": (["WITHDRAWAL"], [1.0]),
}


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

def _rand_digits(rng: np.random.Generator, n: int) -> str:
    return "".join(str(d) for d in rng.integers(0, 10, size=n))


def _rand_hex(rng: np.random.Generator, n: int) -> str:
    alphabet = "0123456789abcdef"
    idx = rng.integers(0, len(alphabet), size=n)
    return "".join(alphabet[i] for i in idx)


def _sample_hour_minute_second(rng: np.random.Generator) -> tuple[int, int, int]:
    hour = int(rng.choice(24, p=HOUR_WEIGHTS))
    minute = int(rng.integers(0, 60))
    second = int(rng.integers(0, 60))
    return hour, minute, second


def _combine(day: date, hour: int, minute: int, second: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=LAGOS)


def _lognormal_amount(rng: np.random.Generator, median: float, cap: float = GLOBAL_LEGIT_AMOUNT_CAP) -> float:
    mu = math.log(median)
    amount = float(rng.lognormal(mean=mu, sigma=LOGNORMAL_SIGMA))
    return round(min(amount, cap), 2)


def _weighted_choice(rng: np.random.Generator, options: dict[str, float]) -> str:
    keys = list(options.keys())
    probs = list(options.values())
    return keys[int(rng.choice(len(keys), p=probs))]


# --------------------------------------------------------------------------- #
# Data holders
# --------------------------------------------------------------------------- #

@dataclass
class Customer:
    customer_id: str
    full_name: str
    bvn: str
    phone: str
    date_joined: date
    segment: str


@dataclass
class Account:
    account_id: str
    customer_id: str
    account_number: str
    account_type: str
    opened_on: date
    segment: str
    home_location: str
    known_devices: list[str]
    known_beneficiaries: list[str]
    balance: float
    recent_amounts: deque = field(default_factory=lambda: deque(maxlen=20))
    channel_weights: dict[str, float] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Customers and accounts
# --------------------------------------------------------------------------- #

def generate_customers(rng: np.random.Generator, n: int, start_date: date) -> list[Customer]:
    segment_names = list(SEGMENTS.keys())
    segment_probs = [SEGMENTS[s]["share"] for s in segment_names]
    first_idx = rng.integers(0, len(FIRST_NAMES), size=n)
    last_idx = rng.integers(0, len(LAST_NAMES), size=n)
    segments = rng.choice(segment_names, size=n, p=segment_probs)
    customers = []
    for i in range(n):
        days_before = int(rng.integers(7, 5 * 365 + 1))
        date_joined = start_date - timedelta(days=days_before)
        phone_prefix = rng.choice(["080", "081", "070", "090", "091"])
        customers.append(
            Customer(
                customer_id=f"CUST{i + 1:06d}",
                full_name=f"{FIRST_NAMES[first_idx[i]]} {LAST_NAMES[last_idx[i]]}",
                bvn=_rand_digits(rng, 11),
                phone=f"{phone_prefix}{_rand_digits(rng, 8)}",
                date_joined=date_joined,
                segment=str(segments[i]),
            )
        )
    return customers


def generate_accounts(rng: np.random.Generator, customers: list[Customer], start_date: date, end_date: date) -> list[Account]:
    accounts: list[Account] = []
    account_counter = 0
    for customer in customers:
        n_accounts = 2 if rng.random() < 0.2 else 1
        for _ in range(n_accounts):
            account_counter += 1
            account_number = f"2{account_counter:09d}"  # guaranteed unique, 10 digits
            segment = SEGMENTS[customer.segment]
            median = segment["median"]

            account_type = "CURRENT" if customer.segment == "business" else rng.choice(
                ["SAVINGS", "CURRENT"], p=[0.7, 0.3]
            )
            opened_on = customer.date_joined
            # second accounts open sometime between joining and the window start
            if n_accounts == 2:
                span_days = max((start_date - customer.date_joined).days, 1)
                opened_on = customer.date_joined + timedelta(days=int(rng.integers(0, span_days)))

            n_devices = int(rng.integers(1, 3))
            known_devices = [f"dev-{account_number}-{_rand_hex(rng, 6)}" for _ in range(n_devices)]
            n_benefs = int(rng.integers(5, 31))
            known_beneficiaries = [f"5{int(rng.integers(0, 10**9)):09d}" for _ in range(n_benefs)]

            home_location = _weighted_choice(rng, dict(zip(LOCATION_NAMES, LOCATION_PROBS)))
            starting_balance = float(rng.uniform(5, 60)) * median

            accounts.append(
                Account(
                    account_id=f"ACC{account_counter:07d}",
                    customer_id=customer.customer_id,
                    account_number=account_number,
                    account_type=str(account_type),
                    opened_on=opened_on,
                    segment=customer.segment,
                    home_location=home_location,
                    known_devices=known_devices,
                    known_beneficiaries=known_beneficiaries,
                    balance=starting_balance,
                    channel_weights=segment["channels"],
                )
            )

    # 5% of accounts opened in the last 30 days of the whole window
    n_new = max(1, int(round(0.05 * len(accounts))))
    new_idx = rng.choice(len(accounts), size=n_new, replace=False)
    for i in new_idx:
        offset = int(rng.integers(0, NEW_ACCOUNT_WINDOW_DAYS))
        accounts[i].opened_on = end_date - timedelta(days=offset)

    return accounts


# --------------------------------------------------------------------------- #
# Legitimate transaction simulation
# --------------------------------------------------------------------------- #

def simulate_legitimate(
    rng: np.random.Generator,
    accounts: list[Account],
    start_date: date,
    days: int,
) -> tuple[list[dict], list[dict]]:
    transactions: list[dict] = []
    security_events: list[dict] = []
    txn_seq = 0

    for account in accounts:
        lam = SEGMENTS[account.segment]["lambda"]
        median = SEGMENTS[account.segment]["median"]
        daily_counts = rng.poisson(lam, size=days)

        # legitimate PIN/password resets (~1/year) and a one-off SIM swap for 0.5% of accounts
        will_sim_swap = rng.random() < 0.005
        sim_swap_day = int(rng.integers(0, days)) if will_sim_swap else -1

        for day_offset in range(days):
            current_day = start_date + timedelta(days=day_offset)
            if current_day < account.opened_on:
                continue  # account does not exist yet

            if day_offset == sim_swap_day:
                hour, minute, second = _sample_hour_minute_second(rng)
                security_events.append({
                    "account_number": account.account_number,
                    "event_type": "SIM_SWAP",
                    "event_time": _combine(current_day, hour, minute, second),
                })
            if rng.random() < (1.0 / 365.0):
                hour, minute, second = _sample_hour_minute_second(rng)
                event_type = rng.choice(["PIN_RESET", "PASSWORD_RESET"])
                security_events.append({
                    "account_number": account.account_number,
                    "event_type": str(event_type),
                    "event_time": _combine(current_day, hour, minute, second),
                })

            # Salary / credit inflow, not scored, keeps balances positive.
            # Sized relative to lambda*median so it can plausibly cover the
            # segment's expected spend rate (docs/DECISIONS.md D17); a fixed
            # small top-up left most accounts unable to keep up with their
            # own transaction volume.
            low_water_mark = 10.0 * median
            if account.segment == "salaried" and current_day.day == 25:
                account.balance += lam * median * float(rng.uniform(20, 35))
            elif account.segment != "salaried" and (
                account.balance < low_water_mark or rng.random() < 0.05
            ):
                account.balance += lam * median * float(rng.uniform(10, 25))

            n_txns = int(daily_counts[day_offset])
            if n_txns == 0:
                continue

            hours = sorted(_sample_hour_minute_second(rng) for _ in range(n_txns))
            for (hour, minute, second) in hours:
                txn_time = _combine(current_day, hour, minute, second)
                txn_seq += 1

                is_hard_negative_transfer = rng.random() < 0.01
                is_travelling = rng.random() < 0.02

                channel = _weighted_choice(rng, account.channel_weights)
                type_names, type_probs = CHANNEL_TXN_TYPE_CHOICES[channel]
                txn_type = str(rng.choice(type_names, p=type_probs))

                # device
                if rng.random() < 0.90 or not account.known_devices:
                    device_id = rng.choice(account.known_devices) if account.known_devices else f"dev-{_rand_hex(rng, 8)}"
                else:
                    device_id = f"dev-{_rand_hex(rng, 8)}"
                    account.known_devices.append(device_id)

                # location
                if is_travelling:
                    others = [l for l in LOCATION_NAMES if l != account.home_location]
                    location = str(rng.choice(others))
                elif rng.random() < 0.95:
                    location = account.home_location
                else:
                    others = [l for l in LOCATION_NAMES if l != account.home_location]
                    location = str(rng.choice(others))

                beneficiary_account = None
                beneficiary_bank = None
                if txn_type == "TRANSFER":
                    if is_hard_negative_transfer:
                        beneficiary_account = f"5{int(rng.integers(0, 10**9)):09d}"
                    elif rng.random() < 0.85 and account.known_beneficiaries:
                        beneficiary_account = rng.choice(account.known_beneficiaries)
                    else:
                        beneficiary_account = f"5{int(rng.integers(0, 10**9)):09d}"
                        account.known_beneficiaries.append(beneficiary_account)
                    beneficiary_bank = str(rng.choice(BANK_CODES))

                avg_amount = (
                    sum(account.recent_amounts) / len(account.recent_amounts)
                    if account.recent_amounts else median
                )
                if is_hard_negative_transfer:
                    amount = round(avg_amount * float(rng.uniform(3, 10)), 2)
                else:
                    amount = _lognormal_amount(rng, median)

                balance_before = max(account.balance, 0.0)
                max_spendable = round(balance_before * 0.95, 2)
                if max_spendable < 50.0:
                    # Not enough funds for a meaningful transaction today;
                    # skip it rather than manufacturing an overdraft.
                    continue
                amount = min(amount, max_spendable)
                amount = max(amount, min(50.0, max_spendable))

                account.balance = balance_before - amount
                account.recent_amounts.append(amount)

                transactions.append({
                    "txn_ref": f"SYN-{txn_seq:09d}",
                    "account_number": account.account_number,
                    "amount": amount,
                    "channel": channel,
                    "txn_type": txn_type,
                    "txn_time": txn_time,
                    "beneficiary_account": beneficiary_account,
                    "beneficiary_bank": beneficiary_bank,
                    "device_id": device_id,
                    "location": location,
                    "balance_before": balance_before,
                    "is_fraud": 0,
                    "fraud_type": None,
                })

    return transactions, security_events


# --------------------------------------------------------------------------- #
# Fraud injection
# --------------------------------------------------------------------------- #

def _random_timestamp(rng: np.random.Generator, start_date: date, end_date: date) -> datetime:
    span = (end_date - start_date).days
    day = start_date + timedelta(days=int(rng.integers(0, max(span, 1))))
    hour, minute, second = _sample_hour_minute_second(rng)
    return _combine(day, hour, minute, second)


def _pick_victim(rng: np.random.Generator, accounts: list[Account], new_accounts: list[Account], want_new: bool) -> Account:
    if want_new and new_accounts:
        return rng.choice(new_accounts)
    return rng.choice(accounts)


def _mule_or_new_beneficiary(rng: np.random.Generator, new_accounts: list[Account]) -> str:
    if new_accounts and rng.random() < 0.7:
        return rng.choice(new_accounts).account_number
    return f"5{int(rng.integers(0, 10**9)):09d}"


def _new_beneficiary(rng: np.random.Generator) -> str:
    return f"5{int(rng.integers(0, 10**9)):09d}"


def _txn_seq_counter():
    n = 0
    while True:
        n += 1
        yield n


def generate_fraud(
    rng: np.random.Generator,
    accounts: list[Account],
    start_date: date,
    end_date: date,
    n_legit: int,
    fraud_rate: float,
) -> tuple[list[dict], list[dict]]:
    new_accounts = [a for a in accounts if (end_date - a.opened_on).days <= NEW_ACCOUNT_WINDOW_DAYS]
    target_fraud_txns = max(1, round(fraud_rate / max(1 - fraud_rate, 1e-9) * n_legit))
    scenario_targets = {
        name: max(1, round(target_fraud_txns * weight))
        for name, weight in FRAUD_SCENARIO_WEIGHTS.items()
    }

    fraud_txns: list[dict] = []
    fraud_events: list[dict] = []
    seq = _txn_seq_counter()

    for scenario, target in scenario_targets.items():
        produced = 0
        guard = 0
        while produced < target and guard < target * 20 + 100:
            guard += 1
            want_new = rng.random() < MULE_TARGET_RATE
            victim = _pick_victim(rng, accounts, new_accounts, want_new and scenario == "CARD_FRAUD")
            incident_txns, incident_events = _generate_incident(
                rng, scenario, victim, new_accounts, start_date, end_date, want_new, seq
            )
            if not incident_txns:
                continue
            fraud_txns.extend(incident_txns)
            fraud_events.extend(incident_events)
            produced += len(incident_txns)

    return fraud_txns, fraud_events


def _generate_incident(
    rng: np.random.Generator,
    scenario: str,
    victim: Account,
    new_accounts: list[Account],
    start_date: date,
    end_date: date,
    want_new: bool,
    seq,
) -> tuple[list[dict], list[dict]]:
    balance = max(victim.balance, 1000.0)
    txns: list[dict] = []
    events: list[dict] = []

    if scenario == "SOCIAL_ENGINEERING":
        base_time = _random_timestamp(rng, start_date, end_date)
        if rng.random() < 0.40:
            base_time = base_time.replace(hour=int(rng.integers(19, 24)))
        n = int(rng.integers(1, 3))
        pct_total = float(rng.uniform(0.40, 0.95))
        channel = str(rng.choice(["NIP", "MOBILE"]))
        beneficiary = _mule_or_new_beneficiary(rng, new_accounts) if want_new else _new_beneficiary(rng)
        remaining = balance
        for i in range(n):
            share = pct_total / n
            amount = round(remaining * share, 2) if i < n - 1 else round(balance * pct_total - sum(t["amount"] for t in txns), 2)
            amount = max(amount, 500.0)
            t_time = base_time + timedelta(minutes=5 * i)
            txns.append({
                "txn_ref": f"FRD-{scenario}-{next(seq):09d}",
                "account_number": victim.account_number,
                "amount": amount,
                "channel": channel,
                "txn_type": "TRANSFER",
                "txn_time": t_time,
                "beneficiary_account": beneficiary,
                "beneficiary_bank": str(rng.choice(BANK_CODES)),
                "device_id": rng.choice(victim.known_devices) if victim.known_devices else f"dev-{_rand_hex(rng, 8)}",
                "location": victim.home_location,
                "balance_before": remaining,
                "is_fraud": 1,
                "fraud_type": scenario,
            })
            remaining -= amount

    elif scenario == "ACCOUNT_TAKEOVER":
        event_type = str(rng.choice(["PASSWORD_RESET", "NEW_DEVICE_ENROLLED"]))
        event_time = _random_timestamp(rng, start_date, end_date)
        events.append({"account_number": victim.account_number, "event_type": event_type, "event_time": event_time})
        offset_minutes = float(rng.uniform(10, 24 * 60))
        base_time = event_time + timedelta(minutes=offset_minutes)
        n = int(rng.integers(2, 7))
        pct_total = float(rng.uniform(0.60, 1.00))
        new_device = f"dev-{_rand_hex(rng, 8)}"
        others = [l for l in LOCATION_NAMES if l != victim.home_location]
        location = str(rng.choice(others))
        remaining = balance
        window_minutes = 60
        for i in range(n):
            share = pct_total / n
            amount = round(remaining * share, 2) if i < n - 1 else round(balance * pct_total - sum(t["amount"] for t in txns), 2)
            amount = max(amount, 500.0)
            t_time = base_time + timedelta(minutes=rng.uniform(0, window_minutes))
            beneficiary = _mule_or_new_beneficiary(rng, new_accounts) if want_new else _new_beneficiary(rng)
            txns.append({
                "txn_ref": f"FRD-{scenario}-{next(seq):09d}",
                "account_number": victim.account_number,
                "amount": amount,
                "channel": str(rng.choice(["NIP", "MOBILE", "INTERNET"])),
                "txn_type": "TRANSFER",
                "txn_time": t_time,
                "beneficiary_account": beneficiary,
                "beneficiary_bank": str(rng.choice(BANK_CODES)),
                "device_id": new_device,
                "location": location,
                "balance_before": remaining,
                "is_fraud": 1,
                "fraud_type": scenario,
            })
            remaining -= amount
        txns.sort(key=lambda t: t["txn_time"])

    elif scenario == "SIM_SWAP":
        event_time = _random_timestamp(rng, start_date, end_date)
        events.append({"account_number": victim.account_number, "event_type": "SIM_SWAP", "event_time": event_time})
        offset_minutes = float(rng.uniform(30, 48 * 60))
        base_time = event_time + timedelta(minutes=offset_minutes)
        n = int(rng.integers(2, 6))
        pct_total = float(rng.uniform(0.50, 1.00))
        new_device = f"dev-{_rand_hex(rng, 8)}"
        remaining = balance
        window_minutes = 120
        for i in range(n):
            share = pct_total / n
            amount = round(remaining * share, 2) if i < n - 1 else round(balance * pct_total - sum(t["amount"] for t in txns), 2)
            amount = max(amount, 500.0)
            t_time = base_time + timedelta(minutes=rng.uniform(0, window_minutes))
            beneficiary = _mule_or_new_beneficiary(rng, new_accounts) if want_new else _new_beneficiary(rng)
            txns.append({
                "txn_ref": f"FRD-{scenario}-{next(seq):09d}",
                "account_number": victim.account_number,
                "amount": amount,
                "channel": str(rng.choice(["USSD", "MOBILE"])),
                "txn_type": "TRANSFER",
                "txn_time": t_time,
                "beneficiary_account": beneficiary,
                "beneficiary_bank": str(rng.choice(BANK_CODES)),
                "device_id": new_device,
                "location": victim.home_location,
                "balance_before": remaining,
                "is_fraud": 1,
                "fraud_type": scenario,
            })
            remaining -= amount
        txns.sort(key=lambda t: t["txn_time"])

    elif scenario == "CARD_FRAUD":
        base_time = _random_timestamp(rng, start_date, end_date)
        others = [l for l in LOCATION_NAMES if l != victim.home_location]
        location = str(rng.choice(others))
        new_terminal = f"term-{_rand_hex(rng, 8)}"
        n = int(rng.integers(3, 9))
        window_minutes = 180
        remaining = balance
        for i in range(n):
            channel = str(rng.choice(["POS", "ATM", "INTERNET"]))
            txn_type = {"POS": "CARD_PAYMENT", "ATM": "WITHDRAWAL", "INTERNET": "CARD_PAYMENT"}[channel]
            amount = round(float(rng.uniform(5_000, 200_000)), 2)
            amount = min(amount, max(remaining, 500.0))
            t_time = base_time + timedelta(minutes=rng.uniform(0, window_minutes))
            txns.append({
                "txn_ref": f"FRD-{scenario}-{next(seq):09d}",
                "account_number": victim.account_number,
                "amount": amount,
                "channel": channel,
                "txn_type": txn_type,
                "txn_time": t_time,
                "beneficiary_account": None,
                "beneficiary_bank": None,
                "device_id": new_terminal,
                "location": location,
                "balance_before": remaining,
                "is_fraud": 1,
                "fraud_type": scenario,
            })
            remaining = max(remaining - amount, 0.0)
        txns.sort(key=lambda t: t["txn_time"])

    return txns, events


# --------------------------------------------------------------------------- #
# Label noise
# --------------------------------------------------------------------------- #

def apply_label_noise(rng: np.random.Generator, transactions: list[dict], rate: float) -> int:
    if rate <= 0:
        return 0
    fraud_idx = [i for i, t in enumerate(transactions) if t["is_fraud"] == 1]
    n_flip = int(round(len(fraud_idx) * rate))
    if n_flip == 0:
        return 0
    flip_idx = rng.choice(fraud_idx, size=n_flip, replace=False)
    for i in flip_idx:
        transactions[i]["is_fraud"] = 0
    return n_flip


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def run(out_dir: Path, n_customers: int, days: int, seed: int, fraud_rate: float, label_noise_rate: float) -> None:
    rng = np.random.default_rng(seed)
    start_date = date(2026, 1, 1)
    end_date = start_date + timedelta(days=days - 1)

    customers = generate_customers(rng, n_customers, start_date)
    accounts = generate_accounts(rng, customers, start_date, end_date)

    legit_txns, legit_events = simulate_legitimate(rng, accounts, start_date, days)
    fraud_txns, fraud_events = generate_fraud(rng, accounts, start_date, end_date, len(legit_txns), fraud_rate)

    all_txns = legit_txns + fraud_txns
    all_txns.sort(key=lambda t: (t["account_number"], t["txn_time"]))
    noise_flipped = apply_label_noise(rng, all_txns, label_noise_rate)

    all_events = legit_events + fraud_events
    all_events.sort(key=lambda e: (e["account_number"], e["event_time"]))

    out_dir.mkdir(parents=True, exist_ok=True)

    customers_df = pd.DataFrame([{
        "customer_id": c.customer_id, "full_name": c.full_name, "bvn": c.bvn,
        "phone": c.phone, "date_joined": c.date_joined.isoformat(), "segment": c.segment,
    } for c in customers])
    customers_df.to_csv(out_dir / "customers.csv", index=False)

    accounts_df = pd.DataFrame([{
        "account_id": a.account_id, "customer_id": a.customer_id, "account_number": a.account_number,
        "account_type": a.account_type, "opened_on": a.opened_on.isoformat(), "home_location": a.home_location,
    } for a in accounts])
    accounts_df.to_csv(out_dir / "accounts.csv", index=False)

    txns_df = pd.DataFrame(all_txns)
    txns_df["txn_time"] = txns_df["txn_time"].apply(lambda d: d.isoformat())
    txns_df.to_csv(out_dir / "transactions.csv", index=False)

    events_df = pd.DataFrame(all_events)
    if len(events_df):
        events_df["event_time"] = events_df["event_time"].apply(lambda d: d.isoformat())
    else:
        events_df = pd.DataFrame(columns=["account_number", "event_type", "event_time"])
    events_df.to_csv(out_dir / "security_events.csv", index=False)

    n_fraud = int(sum(t["is_fraud"] for t in all_txns))
    fraud_by_scenario: dict[str, int] = {}
    for t in all_txns:
        if t.get("fraud_type"):
            fraud_by_scenario[t["fraud_type"]] = fraud_by_scenario.get(t["fraud_type"], 0) + 1
    fraud_by_channel: dict[str, int] = {}
    for t in all_txns:
        if t["is_fraud"] == 1:
            fraud_by_channel[t["channel"]] = fraud_by_channel.get(t["channel"], 0) + 1

    summary = {
        "seed": seed,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "days": days,
        "n_customers": len(customers),
        "n_accounts": len(accounts),
        "n_transactions": len(all_txns),
        "n_fraud_labelled": n_fraud,
        "fraud_share_labelled": n_fraud / len(all_txns) if all_txns else 0.0,
        "requested_fraud_rate": fraud_rate,
        "label_noise_rate_requested": label_noise_rate,
        "label_noise_flipped_count": noise_flipped,
        "true_fraud_count_before_noise": n_fraud + noise_flipped,
        "fraud_scenario_counts": fraud_by_scenario,
        "fraud_scenario_weights_config": FRAUD_SCENARIO_WEIGHTS,
        "fraud_by_channel": fraud_by_channel,
        "segment_counts": {s: sum(1 for c in customers if c.segment == s) for s in SEGMENTS},
        "n_security_events": len(all_events),
    }
    with open(out_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Wrote {len(all_txns)} transactions ({n_fraud} labelled fraud, "
          f"{summary['fraud_share_labelled']:.4%}) to {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic Nigerian bank transaction world")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--customers", required=True, type=int)
    parser.add_argument("--days", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--fraud-rate", required=True, type=float)
    parser.add_argument("--label-noise-rate", default=0.0, type=float,
                         help="Share of fraud labels to flip to 0 (train world only; default 0)")
    args = parser.parse_args()
    run(args.out, args.customers, args.days, args.seed, args.fraud_rate, args.label_noise_rate)


if __name__ == "__main__":
    main()
