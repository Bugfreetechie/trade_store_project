"""Unit tests for background TradeExpiryScheduler."""

import time
import unittest
from datetime import date
from trade_store.database import DatabaseManager
from trade_store.models import TradeRecord
from trade_store.repository import TradeRepository
from trade_store.scheduler import TradeExpiryScheduler
from trade_store.services import TradeService
from trade_store.validators import TradeValidator


class TestTradeScheduler(unittest.TestCase):
    """Test suite for background TradeExpiryScheduler."""

    def setUp(self):
        self.today = date(2026, 5, 20)
        self.db_manager = DatabaseManager(db_path=":memory:")
        self.repo = TradeRepository(self.db_manager)
        self.validator = TradeValidator(current_date_provider=lambda: self.today)
        self.service = TradeService(repository=self.repo, validator=self.validator)
        # 1-second interval for test responsiveness
        self.scheduler = TradeExpiryScheduler(trade_service=self.service, interval_seconds=1)

    def tearDown(self):
        self.scheduler.stop()
        self.db_manager.close()

    def test_scheduler_lifecycle(self):
        """Scheduler should start, report running, and stop cleanly."""
        self.assertFalse(self.scheduler.is_running())
        self.scheduler.start()
        self.assertTrue(self.scheduler.is_running())
        self.scheduler.stop()
        self.assertFalse(self.scheduler.is_running())

    def test_scheduler_trigger_now(self):
        """Manual trigger should immediately execute expiry check."""
        # Insert a matured trade
        self.repo.save(TradeRecord("T1", 1, "CP-1", "B1", date(2026, 5, 10), expired="N"))
        self.assertEqual(self.repo.find_by_id_and_version("T1", 1).expired, "N")

        updated = self.scheduler.trigger_now()
        self.assertEqual(updated, 1)
        self.assertEqual(self.repo.find_by_id_and_version("T1", 1).expired, "Y")


if __name__ == "__main__":
    unittest.main()
