"""Automated regression test suite mapping directly to the problem statement scenarios."""

import unittest
from datetime import date
from trade_store.database import DatabaseManager
from trade_store.exceptions import LowerVersionException, PastMaturityDateException
from trade_store.models import TradeCreate, TradeRecord
from trade_store.repository import TradeRepository
from trade_store.services import TradeService
from trade_store.validators import TradeValidator


class TestTradeStoreRegression(unittest.TestCase):
    """
    Regression suite verifying exact user requirements:
    1. Lower version rejection; same version replacement.
    2. Past maturity date rejection (< today).
    3. Auto-expiration when maturity date is surpassed.
    4. Exact table scenarios (T1, T2, T3).
    """

    def setUp(self):
        # We set reference date corresponding to the problem table context (e.g., 20/05/2020)
        self.simulated_today = date(2020, 5, 20)
        self.db_manager = DatabaseManager(db_path=":memory:")
        self.repo = TradeRepository(self.db_manager)
        self.validator = TradeValidator(current_date_provider=lambda: self.simulated_today)
        self.service = TradeService(repository=self.repo, validator=self.validator)

    def tearDown(self):
        self.db_manager.close()

    def test_scenario_t1_creation_and_auto_expiry(self):
        """
        Table Row:
        T1 | 1 | CP-1 | B1 | 20/05/2020 | <today date> | N

        - Accepted when today = 20/05/2020 (maturity date == today).
        - Initial expired status is 'N'.
        - When date advances to 21/05/2020, automatically becomes 'Y'.
        """
        t1 = TradeCreate(
            trade_id="T1",
            version=1,
            counter_party_id="CP-1",
            portfolio_id="B1",
            maturity_date="20/05/2020",
            created_date=self.simulated_today,
            expired="N",
        )
        saved = self.service.process_incoming_trade(t1, current_date=self.simulated_today)
        self.assertEqual(saved.trade_id, "T1")
        self.assertEqual(saved.version, 1)
        self.assertEqual(saved.counter_party_id, "CP-1")
        self.assertEqual(saved.portfolio_id, "B1")
        self.assertEqual(saved.maturity_date, date(2020, 5, 20))
        self.assertEqual(saved.created_date, self.simulated_today)
        self.assertEqual(saved.expired, "N")

        # Advance current date by 1 day to 21/05/2020 (maturity date is now surpassed)
        day_after = date(2020, 5, 21)
        updated_count = self.service.process_expired_trades(as_of_date=day_after)
        self.assertEqual(updated_count, 1)

        refreshed = self.service.get_trade("T1", version=1)
        self.assertEqual(refreshed.expired, "Y")

    def test_scenario_t2_versioning_and_rejection(self):
        """
        Table Rows:
        T2 | 2 | CP-2 | B1 | 20/05/2021 | <today date> | N
        T2 | 1 | CP-1 | B1 | 20/05/2021 | 14/03/2015   | N

        Transmission sequence:
        1. Historical trade T2 (v1) received on 14/03/2015 with maturity 20/05/2021 -> Stored.
        2. Trade T2 (v2) received today (20/05/2020) -> Version 2 > 1 -> Stored.
        3. Transmission receives Trade T2 (v1) again -> Lower version than v2 -> REJECTED with Exception.
        4. Transmission receives Trade T2 (v2) with modification -> Same version -> REPLACES record.
        """
        # Step 1: Historical reception of T2 v1 in 2015
        date_2015 = date(2015, 3, 14)
        t2_v1 = TradeCreate(
            trade_id="T2",
            version=1,
            counter_party_id="CP-1",
            portfolio_id="B1",
            maturity_date="20/05/2021",
            created_date=date_2015,
            expired="N",
        )
        saved_v1 = self.service.process_incoming_trade(t2_v1, current_date=date_2015)
        self.assertEqual(saved_v1.version, 1)

        # Step 2: Trade T2 v2 received on simulated today (20/05/2020)
        t2_v2 = TradeCreate(
            trade_id="T2",
            version=2,
            counter_party_id="CP-2",
            portfolio_id="B1",
            maturity_date="20/05/2021",
            created_date=self.simulated_today,
            expired="N",
        )
        saved_v2 = self.service.process_incoming_trade(t2_v2, current_date=self.simulated_today)
        self.assertEqual(saved_v2.version, 2)
        self.assertEqual(saved_v2.counter_party_id, "CP-2")

        # Step 3: Now attempt to transmit lower version T2 v1 -> MUST REJECT WITH EXCEPTION
        t2_v1_incoming = TradeCreate(
            trade_id="T2",
            version=1,
            counter_party_id="CP-1",
            portfolio_id="B1",
            maturity_date="20/05/2021",
            created_date=self.simulated_today,
            expired="N",
        )
        with self.assertRaises(LowerVersionException) as ctx:
            self.service.process_incoming_trade(t2_v1_incoming, current_date=self.simulated_today)
        self.assertEqual(ctx.exception.trade_id, "T2")
        self.assertEqual(ctx.exception.incoming_version, 1)
        self.assertEqual(ctx.exception.current_version, 2)

        # Step 4: Transmit same version T2 v2 with updated portfolio -> MUST REPLACE
        t2_v2_update = TradeCreate(
            trade_id="T2",
            version=2,
            counter_party_id="CP-2",
            portfolio_id="B1-UPDATED-PORTFOLIO",
            maturity_date="20/05/2021",
            created_date=self.simulated_today,
            expired="N",
        )
        replaced = self.service.process_incoming_trade(t2_v2_update, current_date=self.simulated_today)
        self.assertEqual(replaced.portfolio_id, "B1-UPDATED-PORTFOLIO")

        fetched_v2 = self.service.get_trade("T2", version=2)
        self.assertEqual(fetched_v2.portfolio_id, "B1-UPDATED-PORTFOLIO")

    def test_scenario_t3_past_maturity_rejection(self):
        """
        Table Row:
        T3 | 3 | CP-3 | B2 | 20/05/2014 | <today date> | Y

        Validation 2: The store must reject any trade that has a maturity date earlier than today's date.
        If someone transmits T3 with maturity 20/05/2014 when today is 20/05/2020:
        Store MUST reject it and raise PastMaturityDateException.
        """
        t3 = TradeCreate(
            trade_id="T3",
            version=3,
            counter_party_id="CP-3",
            portfolio_id="B2",
            maturity_date="20/05/2014",  # In the past relative to 20/05/2020
            created_date=self.simulated_today,
        )
        with self.assertRaises(PastMaturityDateException) as ctx:
            self.service.process_incoming_trade(t3, current_date=self.simulated_today)
        self.assertEqual(ctx.exception.trade_id, "T3")
        self.assertIn("20/05/2014", ctx.exception.maturity_date)

    def test_high_volume_trade_ingestion_regression(self):
        """Verify performance and correctness across 1,000 trades in sequence."""
        for i in range(1, 1001):
            trade = TradeCreate(
                trade_id=f"BULK_{i % 50}",
                version=(i // 50) + 1,
                counter_party_id=f"CP_{i % 10}",
                portfolio_id=f"B_{i % 5}",
                maturity_date="20/05/2030",
                created_date=self.simulated_today,
            )
            # Either new trade, new version, or same version replacement
            self.service.process_incoming_trade(trade, current_date=self.simulated_today)

        # Store should have successfully processed all trades without corruption
        latest_trades = self.service.list_trades(latest_only=True)
        self.assertEqual(len(latest_trades), 50)


if __name__ == "__main__":
    unittest.main()
