"""Database connection and initialization module for Trade Store."""

import sqlite3
import threading
from typing import Optional


class DatabaseManager:
    """Manages SQLite database connections, schema setup, and transactions."""

    def __init__(self, db_path: str = "trade_store.db"):
        if db_path == ":memory:":
            # Use SQLite shared-memory URI so multiple worker threads share the same database
            self._is_memory = True
            self.db_path = f"file:memdb_{id(self)}?mode=memory&cache=shared"
            self._uri = True
        else:
            self._is_memory = False
            self.db_path = db_path
            self._uri = False

        self._local = threading.local()
        self._lock = threading.Lock()

        # For in-memory shared database, maintain a persistent reference connection
        # so SQLite doesn't wipe the DB when worker threads close their connections
        if self._is_memory:
            self._anchor_conn = sqlite3.connect(
                self.db_path,
                uri=True,
                check_same_thread=False,
            )
        else:
            self._anchor_conn = None

        self.init_schema()

    def get_connection(self) -> sqlite3.Connection:
        """Get a thread-local SQLite connection."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            conn = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                check_same_thread=False,
                uri=self._uri,
            )
            conn.row_factory = sqlite3.Row
            if not self._is_memory:
                conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            self._local.connection = conn
        return self._local.connection

    def init_schema(self) -> None:
        """Create trades table and indexes if not exists."""
        with self._lock:
            conn = self.get_connection()
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS trades (
                        trade_id TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        counter_party_id TEXT NOT NULL,
                        portfolio_id TEXT NOT NULL,
                        maturity_date TEXT NOT NULL,
                        created_date TEXT NOT NULL,
                        expired TEXT NOT NULL DEFAULT 'N',
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (trade_id, version)
                    );
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_trades_trade_id ON trades(trade_id);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_trades_maturity ON trades(maturity_date, expired);"
                )

    def close(self) -> None:
        """Close connection for current thread and anchor connection."""
        if hasattr(self._local, "connection") and self._local.connection is not None:
            self._local.connection.close()
            self._local.connection = None
        if self._anchor_conn is not None:
            self._anchor_conn.close()
            self._anchor_conn = None
