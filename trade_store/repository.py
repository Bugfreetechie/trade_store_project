"""Repository layer for persisting and retrieving trades in the database."""

from datetime import date, datetime
from typing import List, Optional
from trade_store.database import DatabaseManager
from trade_store.models import TradeRecord


class TradeRepository:
    """Thread-safe Repository for Trade records."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def _row_to_record(self, row) -> TradeRecord:
        return TradeRecord(
            trade_id=row["trade_id"],
            version=row["version"],
            counter_party_id=row["counter_party_id"],
            portfolio_id=row["portfolio_id"],
            maturity_date=datetime.strptime(row["maturity_date"], "%Y-%m-%d").date(),
            created_date=datetime.strptime(row["created_date"], "%Y-%m-%d").date(),
            expired=row["expired"],
        )

    def get_max_version(self, trade_id: str) -> Optional[int]:
        """Return the highest version recorded for a given trade_id, or None."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(version) FROM trades WHERE trade_id = ?", (trade_id,))
        row = cursor.fetchone()
        if row and row[0] is not None:
            return int(row[0])
        return None

    def save(self, trade: TradeRecord) -> TradeRecord:
        """
        Insert a new trade or replace an existing trade record if (trade_id, version) matches.
        """
        conn = self.db_manager.get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO trades (
                    trade_id, version, counter_party_id, portfolio_id,
                    maturity_date, created_date, expired, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(trade_id, version) DO UPDATE SET
                    counter_party_id = excluded.counter_party_id,
                    portfolio_id = excluded.portfolio_id,
                    maturity_date = excluded.maturity_date,
                    created_date = excluded.created_date,
                    expired = excluded.expired,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (
                    trade.trade_id,
                    trade.version,
                    trade.counter_party_id,
                    trade.portfolio_id,
                    trade.maturity_date.isoformat(),
                    trade.created_date.isoformat(),
                    trade.expired,
                ),
            )
        return trade

    def find_by_id_and_version(self, trade_id: str, version: int) -> Optional[TradeRecord]:
        """Fetch a specific version of a trade."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM trades WHERE trade_id = ? AND version = ?",
            (trade_id, version),
        )
        row = cursor.fetchone()
        return self._row_to_record(row) if row else None

    def find_latest_by_id(self, trade_id: str) -> Optional[TradeRecord]:
        """Fetch the highest version record for a trade_id."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM trades WHERE trade_id = ? ORDER BY version DESC LIMIT 1",
            (trade_id,),
        )
        row = cursor.fetchone()
        return self._row_to_record(row) if row else None

    def find_all_versions_by_id(self, trade_id: str) -> List[TradeRecord]:
        """Fetch all versions of a trade ordered by version ascending."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM trades WHERE trade_id = ? ORDER BY version ASC",
            (trade_id,),
        )
        return [self._row_to_record(row) for row in cursor.fetchall()]

    def find_all(
        self,
        latest_only: bool = False,
        expired_filter: Optional[str] = None,
    ) -> List[TradeRecord]:
        """
        List all trades in the store.
        If latest_only=True, returns only the latest version of each trade_id.
        Optional filter on expired ('Y' or 'N').
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        query_parts = []
        params = []

        if latest_only:
            # Subquery selecting the max version per trade_id
            sql = """
                SELECT t.* FROM trades t
                INNER JOIN (
                    SELECT trade_id, MAX(version) as max_v
                    FROM trades
                    GROUP BY trade_id
                ) m ON t.trade_id = m.trade_id AND t.version = m.max_v
            """
        else:
            sql = "SELECT * FROM trades"

        if expired_filter:
            sql += " WHERE expired = ?" if not latest_only else " WHERE t.expired = ?"
            params.append(expired_filter.upper())

        sql += " ORDER BY trade_id ASC, version ASC"
        cursor.execute(sql, params)
        return [self._row_to_record(row) for row in cursor.fetchall()]

    def mark_expired_trades(self, as_of_date: date) -> int:
        """
        Validation 3: Automatically mark trades as expired ('Y') when maturity date < as_of_date.
        Returns the number of records updated.
        """
        conn = self.db_manager.get_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE trades
                SET expired = 'Y', updated_at = CURRENT_TIMESTAMP
                WHERE maturity_date < ? AND expired != 'Y'
                """,
                (as_of_date.isoformat(),),
            )
            return cursor.rowcount

    def count(self) -> int:
        """Total trade records count."""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM trades")
        return cursor.fetchone()[0]

    def clear(self) -> None:
        """Delete all trades (primarily for test teardown)."""
        conn = self.db_manager.get_connection()
        with conn:
            conn.execute("DELETE FROM trades")
