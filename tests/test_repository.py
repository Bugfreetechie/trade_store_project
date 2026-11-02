"""Unit tests for TradeRepository layer."""

import unittest
from datetime import date
from trade_store.database import DatabaseManager
from trade_store.models import TradeRecord
from trade_store.repository import TradeRepository


class TestTradeRepository(unittest.TestCase):
    """Test suite for repository SQLite operations."""

    def setUp(self):
        # Use isolated in-memory SQLite database for each test
        self.db_manager = DatabaseManager(db_path=":memory:")
        self.repo = TradeRepository(self.db_manager)

    def tearDown(self):
        self.db_manager.close()

    def test_save_and_find_by_id_and_version(self):
        """Should save a trade record and retrieve it by id and version."""
        record = TradeRecord(
            trade_id="T1",
            version=1,
            counter_party_id="CP-1",
            portfolio_id="B1",
            maturity_date=date(2028, 5, 20),
            created_date=date(2026, 1, 1),
            expired="N",
        )
        self.repo.save(record)
        fetched = self.repo.find_by_id_and_version("T1", 1)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.trade_id, "T1")
        self.assertEqual(fetched.version, 1)
        self.assertEqual(fetched.counter_party_id, "CP-1")
        self.assertEqual(fetched.portfolio_id, "B1")
        self.assertEqual(fetched.maturity_date, date(2028, 5, 20))
        self.assertEqual(fetched.expired, "N")

    def test_get_max_version(self):
        """Should return the maximum version for a given trade_id."""
        self.assertIsNone(self.repo.get_max_version("T2"))

        self.repo.save(TradeRecord("T2", 1, "CP-1", "B1", date(2028, 5, 20)))
        self.assertEqual(self.repo.get_max_version("T2"), 1)

        self.repo.save(TradeRecord("T2", 2, "CP-2", "B1", date(2028, 5, 20)))
        self.assertEqual(self.repo.get_max_version("T2"), 2)

    def test_save_replaces_same_version(self):
        """Saving with identical (trade_id, version) should update existing record."""
        initial = TradeRecord("T1", 1, "CP-1", "B1", date(2028, 5, 20), expired="N")
        self.repo.save(initial)

        # Update counterparty and portfolio with same version
        updated = TradeRecord("T1", 1, "CP-UPDATED", "B2", date(2028, 5, 20), expired="N")
        self.repo.save(updated)

        self.assertEqual(self.repo.count(), 1)
        fetched = self.repo.find_by_id_and_version("T1", 1)
        self.assertEqual(fetched.counter_party_id, "CP-UPDATED")
        self.assertEqual(fetched.portfolio_id, "B2")

    def test_mark_expired_trades(self):
        """Should update expired flag to 'Y' when maturity date is before reference date."""
        self.repo.save(TradeRecord("T1", 1, "CP-1", "B1", date(2026, 5, 10), expired="N"))
        self.repo.save(TradeRecord("T2", 1, "CP-2", "B1", date(2026, 5, 25), expired="N"))

        # As of 2026-05-20, T1 is matured and should expire, T2 should remain 'N'
        updated_count = self.repo.mark_expired_trades(as_of_date=date(2026, 5, 20))
        self.assertEqual(updated_count, 1)

        t1 = self.repo.find_by_id_and_version("T1", 1)
        t2 = self.repo.find_by_id_and_version("T2", 1)
        self.assertEqual(t1.expired, "Y")
        self.assertEqual(t2.expired, "N")


if __name__ == "__main__":
    unittest.main()
