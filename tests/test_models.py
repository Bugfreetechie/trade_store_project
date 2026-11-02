"""Unit tests for Trade models and data parsing."""

import unittest
from datetime import date
from trade_store.models import TradeCreate, TradeRecord, TradeResponse, parse_flexible_date


class TestTradeModels(unittest.TestCase):
    """Test suite for domain models and date parsing."""

    def test_parse_flexible_date_formats(self):
        """Should parse DD/MM/YYYY, YYYY-MM-DD, and DD-MM-YYYY correctly."""
        self.assertEqual(parse_flexible_date("20/05/2025"), date(2025, 5, 20))
        self.assertEqual(parse_flexible_date("2025-05-20"), date(2025, 5, 20))
        self.assertEqual(parse_flexible_date("20-05-2025"), date(2025, 5, 20))
        self.assertEqual(parse_flexible_date(date(2025, 5, 20)), date(2025, 5, 20))
        self.assertIsNone(parse_flexible_date(None))

    def test_parse_flexible_date_invalid(self):
        """Should raise ValueError on invalid date format."""
        with self.assertRaises(ValueError):
            parse_flexible_date("invalid-date")

    def test_trade_create_valid(self):
        """Should construct valid TradeCreate schema with DD/MM/YYYY string."""
        trade = TradeCreate(
            trade_id="T1",
            version=1,
            counter_party_id="CP-1",
            portfolio_id="B1",
            maturity_date="20/05/2028",
            created_date="01/01/2026",
            expired="N",
        )
        self.assertEqual(trade.trade_id, "T1")
        self.assertEqual(trade.version, 1)
        self.assertEqual(trade.maturity_date, date(2028, 5, 20))
        self.assertEqual(trade.created_date, date(2026, 1, 1))
        self.assertEqual(trade.expired, "N")

    def test_trade_create_default_expiry(self):
        """Expired flag should default to 'N'."""
        trade = TradeCreate(
            trade_id="T2",
            version=2,
            counter_party_id="CP-2",
            portfolio_id="B1",
            maturity_date="2028-10-15",
        )
        self.assertEqual(trade.expired, "N")

    def test_trade_record_to_dict(self):
        """TradeRecord should convert to dictionary."""
        record = TradeRecord(
            trade_id="T1",
            version=1,
            counter_party_id="CP-1",
            portfolio_id="B1",
            maturity_date=date(2028, 5, 20),
            created_date=date(2026, 1, 1),
            expired="N",
        )
        data = record.to_dict()
        self.assertEqual(data["trade_id"], "T1")
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["maturity_date"], "2028-05-20")

    def test_trade_response_formatting(self):
        """TradeResponse should provide formatted date strings."""
        record = TradeRecord(
            trade_id="T1",
            version=1,
            counter_party_id="CP-1",
            portfolio_id="B1",
            maturity_date=date(2028, 5, 20),
            created_date=date(2026, 1, 1),
            expired="N",
        )
        response = TradeResponse.from_domain(record)
        self.assertEqual(response.maturity_date_formatted, "20/05/2028")
        self.assertEqual(response.created_date_formatted, "01/01/2026")


if __name__ == "__main__":
    unittest.main()
