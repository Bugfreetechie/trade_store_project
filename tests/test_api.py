"""Integration tests for Trade Store FastAPI REST endpoints."""

import unittest
from datetime import date
from fastapi.testclient import TestClient
from trade_store.api import create_app


class TestTradeApi(unittest.TestCase):
    """End-to-end HTTP test suite using FastAPI TestClient."""

    def setUp(self):
        self.simulated_today = date(2026, 5, 20)
        # Create app with in-memory database and simulated date
        self.app = create_app(
            db_path=":memory:",
            start_scheduler=False,
            current_date_provider=lambda: self.simulated_today,
        )
        self.client = TestClient(self.app)

    def test_health_check(self):
        """GET /health should return system status."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("total_trades", data)

    def test_submit_valid_trade(self):
        """POST /trades should accept valid trade with 201 Created."""
        payload = {
            "trade_id": "T1",
            "version": 1,
            "counter_party_id": "CP-1",
            "portfolio_id": "B1",
            "maturity_date": "20/05/2028",
            "created_date": "20/05/2026",
            "expired": "N",
        }
        response = self.client.post("/trades", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["trade_id"], "T1")
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["maturity_date_formatted"], "20/05/2028")

    def test_submit_trade_rejects_past_maturity_date(self):
        """POST /trades should return 400 Bad Request if maturity date < today."""
        payload = {
            "trade_id": "T3",
            "version": 1,
            "counter_party_id": "CP-3",
            "portfolio_id": "B2",
            "maturity_date": "10/05/2026",  # 10 days before simulated today
        }
        response = self.client.post("/trades", json=payload)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"], "PastMaturityDateException")
        self.assertIn("cannot be earlier than current date", data["message"])

    def test_submit_trade_rejects_lower_version(self):
        """POST /trades should return 400 Bad Request if incoming version < max store version."""
        # Submit Version 2 first
        self.client.post("/trades", json={
            "trade_id": "T2",
            "version": 2,
            "counter_party_id": "CP-2",
            "portfolio_id": "B1",
            "maturity_date": "20/05/2028",
        })

        # Attempt to submit Version 1
        response = self.client.post("/trades", json={
            "trade_id": "T2",
            "version": 1,
            "counter_party_id": "CP-1",
            "portfolio_id": "B1",
            "maturity_date": "20/05/2028",
        })
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"], "LowerVersionException")
        self.assertEqual(data["incoming_version"], 1)
        self.assertEqual(data["current_version"], 2)

    def test_submit_trade_replaces_same_version(self):
        """POST /trades should replace record if incoming version == current store version."""
        # Initial submission
        self.client.post("/trades", json={
            "trade_id": "T2",
            "version": 1,
            "counter_party_id": "CP-1",
            "portfolio_id": "B1",
            "maturity_date": "20/05/2028",
        })

        # Submit same trade_id and version with updated portfolio
        response = self.client.post("/trades", json={
            "trade_id": "T2",
            "version": 1,
            "counter_party_id": "CP-1",
            "portfolio_id": "PORTFOLIO-UPDATED",
            "maturity_date": "20/05/2028",
        })
        self.assertEqual(response.status_code, 201)

        # Retrieve and verify replacement
        get_res = self.client.get("/trades/T2")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["portfolio_id"], "PORTFOLIO-UPDATED")

    def test_list_and_filter_trades(self):
        """GET /trades should support filtering by latest_only and expired."""
        # Seed T1 (v1) and T2 (v1, v2)
        self.client.post("/trades", json={
            "trade_id": "T1", "version": 1, "counter_party_id": "CP-1",
            "portfolio_id": "B1", "maturity_date": "20/05/2028",
        })
        self.client.post("/trades", json={
            "trade_id": "T2", "version": 1, "counter_party_id": "CP-1",
            "portfolio_id": "B1", "maturity_date": "20/05/2028",
        })
        self.client.post("/trades", json={
            "trade_id": "T2", "version": 2, "counter_party_id": "CP-2",
            "portfolio_id": "B1", "maturity_date": "20/05/2028",
        })

        # All trades
        all_res = self.client.get("/trades")
        self.assertEqual(len(all_res.json()), 3)

        # Latest only
        latest_res = self.client.get("/trades?latest_only=true")
        self.assertEqual(len(latest_res.json()), 2)
        trade_ids = [t["trade_id"] for t in latest_res.json()]
        self.assertIn("T1", trade_ids)
        self.assertIn("T2", trade_ids)

    def test_get_trade_history(self):
        """GET /trades/{trade_id}/history should return audit history."""
        self.client.post("/trades", json={
            "trade_id": "T2", "version": 1, "counter_party_id": "CP-1",
            "portfolio_id": "B1", "maturity_date": "20/05/2028",
        })
        self.client.post("/trades", json={
            "trade_id": "T2", "version": 2, "counter_party_id": "CP-2",
            "portfolio_id": "B1", "maturity_date": "20/05/2028",
        })
        res = self.client.get("/trades/T2/history")
        self.assertEqual(res.status_code, 200)
        history = res.json()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["version"], 1)
        self.assertEqual(history[1]["version"], 2)

    def test_process_expiry_endpoint(self):
        """POST /trades/process-expiry should update expired trades."""
        # Insert trade with maturity 2026-05-20
        self.client.post("/trades", json={
            "trade_id": "T1", "version": 1, "counter_party_id": "CP-1",
            "portfolio_id": "B1", "maturity_date": "20/05/2026",
        })
        # Advance as_of_date to 2026-05-21
        res = self.client.post("/trades/process-expiry?as_of_date=21/05/2026")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["updated_count"], 1)

        # Verify trade is now expired
        t1_res = self.client.get("/trades/T1")
        self.assertEqual(t1_res.json()["expired"], "Y")


if __name__ == "__main__":
    unittest.main()
