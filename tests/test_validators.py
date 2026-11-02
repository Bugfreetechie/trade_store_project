"""Unit tests for Trade business rules and validators."""

import unittest
from datetime import date
from trade_store.exceptions import LowerVersionException, PastMaturityDateException
from trade_store.models import TradeCreate
from trade_store.validators import TradeValidator


class TestTradeValidators(unittest.TestCase):
    """Test suite for domain validation rules."""

    def setUp(self):
        self.today = date(2026, 5, 20)
        self.validator = TradeValidator(current_date_provider=lambda: self.today)

    def test_validation_2_reject_past_maturity_date(self):
        """Rule 2: The store must reject any trade that has a maturity date earlier than today's date."""
        past_trade = TradeCreate(
            trade_id="T3",
            version=1,
            counter_party_id="CP-3",
            portfolio_id="B2",
            maturity_date=date(2026, 5, 19),  # 1 day before today
        )
        with self.assertRaises(PastMaturityDateException) as ctx:
            self.validator.validate_maturity_date(past_trade, current_date=self.today)
        self.assertIn("T3", str(ctx.exception))
        self.assertIn("19/05/2026", str(ctx.exception))

    def test_validation_2_allow_today_maturity_date(self):
        """Rule 2: A trade with maturity date equal to today's date should be accepted."""
        today_trade = TradeCreate(
            trade_id="T1",
            version=1,
            counter_party_id="CP-1",
            portfolio_id="B1",
            maturity_date=self.today,
        )
        # Should not raise
        self.validator.validate_maturity_date(today_trade, current_date=self.today)

    def test_validation_2_allow_future_maturity_date(self):
        """Rule 2: A trade with maturity date in the future should be accepted."""
        future_trade = TradeCreate(
            trade_id="T1",
            version=1,
            counter_party_id="CP-1",
            portfolio_id="B1",
            maturity_date=date(2028, 5, 20),
        )
        # Should not raise
        self.validator.validate_maturity_date(future_trade, current_date=self.today)

    def test_validation_1_reject_lower_version(self):
        """Rule 1: If a trade with a lower version is received, reject and generate an exception."""
        lower_trade = TradeCreate(
            trade_id="T2",
            version=1,
            counter_party_id="CP-1",
            portfolio_id="B1",
            maturity_date=date(2028, 5, 20),
        )
        # Existing max version is 2
        with self.assertRaises(LowerVersionException) as ctx:
            self.validator.validate_version(lower_trade, current_max_version=2)
        self.assertIn("Incoming version 1 is lower than current version 2", str(ctx.exception))

    def test_validation_1_same_version_replaces_record(self):
        """Rule 1: Trades with the same version will replace the current record."""
        same_version_trade = TradeCreate(
            trade_id="T2",
            version=2,
            counter_party_id="CP-2",
            portfolio_id="B1",
            maturity_date=date(2028, 5, 20),
        )
        is_replacement = self.validator.validate_version(same_version_trade, current_max_version=2)
        self.assertTrue(is_replacement)

    def test_validation_1_higher_version_accepted(self):
        """Rule 1: Higher version should be accepted without raising."""
        higher_version_trade = TradeCreate(
            trade_id="T2",
            version=3,
            counter_party_id="CP-3",
            portfolio_id="B1",
            maturity_date=date(2028, 5, 20),
        )
        is_replacement = self.validator.validate_version(higher_version_trade, current_max_version=2)
        self.assertFalse(is_replacement)

    def test_validation_1_first_version_accepted(self):
        """When no trade exists (max_version=None), version 1 is accepted."""
        new_trade = TradeCreate(
            trade_id="T1",
            version=1,
            counter_party_id="CP-1",
            portfolio_id="B1",
            maturity_date=date(2028, 5, 20),
        )
        is_replacement = self.validator.validate_version(new_trade, current_max_version=None)
        self.assertFalse(is_replacement)


if __name__ == "__main__":
    unittest.main()
