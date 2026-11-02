"""Unit tests for TradeService business logic."""

import unittest
from datetime import date
from trade_store.database import DatabaseManager
from trade_store.exceptions import LowerVersionException, PastMaturityDateException, TradeNotFoundException
from trade_store.models import TradeCreate
from trade_store.repository import TradeRepository
from trade_store.services import TradeService
from trade_store.validators import TradeValidator


class TestTradeService(unittest.TestCase):
    """Test suite for TradeService."""

    def setUp(self):
        self.today = date(2026, 5, 20)
        self.db_manager = DatabaseManager(db_path=":memory:")
        self.repo = TradeRepository(self.db_manager)
        self.validator = TradeValidator(current_date_provider=lambda: self.today)
        self.service = TradeService(repository=self.repo, validator=self.validator)

    def tearDown(self):
        self.db_manager.close()

    def test_process_valid_new_trade(self):
        """Should accept and persist valid new trade."""
        trade_in = TradeCreate(
            trade_id="T1",
            version=1,
            counter_party_id="CP-1",
            portfolio_id="B1",
            maturity_date="20/05/2028",
        )
        saved = self.service.process_incoming_trade(trade_in, current_date=self.today)
        self.assertEqual(saved.trade_id, "T1")
        self.assertEqual(saved.version, 1)
        self.assertEqual(saved.expired, "N")

    def test_process_trade_rejects_lower_version(self):
        """Should raise LowerVersionException when receiving version lower than existing."""
        # Initial version 2
        trade_v2 = TradeCreate(
            trade_id="T2",
            version=2,
            counter_party_id="CP-2",
            portfolio_id="B1",
            maturity_date="20/05/2028",
        )
        self.service.process_incoming_trade(trade_v2, current_date=self.today)

        # Incoming version 1 for same trade_id
        trade_v1 = TradeCreate(
            trade_id="T2",
            version=1,
            counter_party_id="CP-1",
            portfolio_id="B1",
            maturity_date="20/05/2028",
        )
        with self.assertRaises(LowerVersionException):
            self.service.process_incoming_trade(trade_v1, current_date=self.today)

    def test_process_trade_replaces_same_version(self):
        """Should replace record when receiving identical version."""
        trade_v1 = TradeCreate(
            trade_id="T1",
            version=1,
            counter_party_id="CP-1",
            portfolio_id="B1",
            maturity_date="20/05/2028",
        )
        self.service.process_incoming_trade(trade_v1, current_date=self.today)

        # Update counterparty with same version
        trade_v1_updated = TradeCreate(
            trade_id="T1",
            version=1,
            counter_party_id="CP-1-REVISED",
            portfolio_id="B1",
            maturity_date="20/05/2028",
        )
        self.service.process_incoming_trade(trade_v1_updated, current_date=self.today)

        stored = self.service.get_trade("T1", version=1)
        self.assertEqual(stored.counter_party_id, "CP-1-REVISED")

    def test_process_trade_rejects_past_maturity_date(self):
        """Should raise PastMaturityDateException when maturity date < today."""
        trade_past = TradeCreate(
            trade_id="T3",
            version=1,
            counter_party_id="CP-3",
            portfolio_id="B2",
            maturity_date="19/05/2026",  # 1 day before self.today
        )
        with self.assertRaises(PastMaturityDateException):
            self.service.process_incoming_trade(trade_past, current_date=self.today)

    def test_process_expired_trades(self):
        """Should mark past maturity trades as expired."""
        trade = TradeCreate(
            trade_id="T1",
            version=1,
            counter_party_id="CP-1",
            portfolio_id="B1",
            maturity_date="20/05/2026",  # Mature today
        )
        self.service.process_incoming_trade(trade, current_date=self.today)
        self.assertEqual(self.service.get_trade("T1").expired, "N")

        # Advance current date by 1 day to 2026-05-21
        updated = self.service.process_expired_trades(as_of_date=date(2026, 5, 21))
        self.assertEqual(updated, 1)
        self.assertEqual(self.service.get_trade("T1").expired, "Y")

    def test_get_trade_not_found(self):
        """Should raise TradeNotFoundException if trade does not exist."""
        with self.assertRaises(TradeNotFoundException):
            self.service.get_trade("UNKNOWN")


if __name__ == "__main__":
    unittest.main()
