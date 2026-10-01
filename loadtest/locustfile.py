"""Load test: post random demo transactions to /transactions/score (Section
15.4). 20 concurrent users for 5 minutes is the target scenario, run via:

    locust -f loadtest/locustfile.py --host http://localhost:8000 \\
        --headless -u 20 -r 5 -t 5m --csv reports/loadtest

Set SIM_API_KEY and, optionally, SIM_ACCOUNT_NUMBERS (comma-separated,
existing account numbers from a seeded demo database) via environment
variables before running.
"""
from __future__ import annotations

import os
import random
import uuid
from datetime import datetime, timezone

from locust import HttpUser, between, task

API_KEY = os.environ.get("SIM_API_KEY", "sim-key-change-me")
ACCOUNT_NUMBERS = [
    a.strip() for a in os.environ.get("SIM_ACCOUNT_NUMBERS", "").split(",") if a.strip()
] or [f"2{i:09d}" for i in range(1, 51)]  # falls back to a plausible-looking range

CHANNELS = ["NIP", "MOBILE", "USSD", "INTERNET", "POS", "ATM"]
CHANNEL_TXN_TYPES = {
    "NIP": "TRANSFER", "MOBILE": "TRANSFER", "USSD": "AIRTIME",
    "INTERNET": "BILL_PAYMENT", "POS": "CARD_PAYMENT", "ATM": "WITHDRAWAL",
}
LOCATIONS = ["Lagos", "Abuja", "Rivers", "Kano", "Oyo"]


class ScoringUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def score_transaction(self):
        channel = random.choice(CHANNELS)
        txn_type = CHANNEL_TXN_TYPES[channel]
        payload = {
            "txn_ref": f"LOAD-{uuid.uuid4().hex}",
            "account_number": random.choice(ACCOUNT_NUMBERS),
            "amount": str(round(random.uniform(500, 500_000), 2)),
            "channel": channel,
            "txn_type": txn_type,
            "txn_time": datetime.now(timezone.utc).isoformat(),
            "beneficiary_account": f"5{random.randint(0, 10**9):09d}" if txn_type == "TRANSFER" else None,
            "beneficiary_bank": "058" if txn_type == "TRANSFER" else None,
            "device_id": f"dev-{random.randint(0, 10**6)}",
            "location": random.choice(LOCATIONS),
            "balance_before": str(round(random.uniform(10_000, 5_000_000), 2)),
        }
        self.client.post(
            "/api/v1/transactions/score",
            json=payload,
            headers={"X-API-Key": API_KEY},
            name="/api/v1/transactions/score",
        )
