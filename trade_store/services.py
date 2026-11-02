"""Service layer orchestrating trade validation, persistence, and lifecycle operations."""

from datetime import date
from typing import List, Optional
from trade_store.exceptions import TradeNotFoundException
from trade_store.models import TradeCreate, TradeRecord
from trade_store.repository import TradeRepository
from trade_store.validators import TradeValidator


class TradeService:
    """Core domain service for processing trades in the store."""

    def __init__(self, repository: TradeRepository, validator: Optional[TradeValidator] = None):
        self.repository = repository
        self.validator = validator or TradeValidator()

    def process_incoming_trade(
        self,
        trade_in: TradeCreate,
        current_date: Optional[date] = None,
    ) -> TradeRecord:
        """
        Ingest an incoming trade:
        1. Validate maturity date >= current_date
        2. Validate version >= existing max_version
        3. If version == max_version: replace existing record
        4. If version > max_version: store new record
        """
        ref_date = current_date or self.validator.get_current_date()

        # Step 1: Check existing versions for this trade_id
        current_max_version = self.repository.get_max_version(trade_in.trade_id)

        # Step 2: Validate against domain rules
        self.validator.validate(
            trade=trade_in,
            current_max_version=current_max_version,
            current_date=ref_date,
        )

        # Step 3: Determine initial expired flag and created date
        created_date = trade_in.created_date or ref_date
        expired = trade_in.expired
        if trade_in.maturity_date < ref_date:
            expired = "Y"

        record = TradeRecord(
            trade_id=trade_in.trade_id,
            version=trade_in.version,
            counter_party_id=trade_in.counter_party_id,
            portfolio_id=trade_in.portfolio_id,
            maturity_date=trade_in.maturity_date,
            created_date=created_date,
            expired=expired,
        )

        # Step 4: Persist (Insert or Replace)
        return self.repository.save(record)

    def process_expired_trades(self, as_of_date: Optional[date] = None) -> int:
        """
        Batch/scheduled process: Marks trades as expired ('Y')
        if their maturity date has been surpassed.
        """
        ref_date = as_of_date or self.validator.get_current_date()
        return self.repository.mark_expired_trades(ref_date)

    def get_trade(self, trade_id: str, version: Optional[int] = None) -> TradeRecord:
        """Retrieve a trade by trade_id and optional version."""
        if version is not None:
            record = self.repository.find_by_id_and_version(trade_id, version)
        else:
            record = self.repository.find_latest_by_id(trade_id)

        if not record:
            raise TradeNotFoundException(trade_id)
        return record

    def get_trade_history(self, trade_id: str) -> List[TradeRecord]:
        """Retrieve all versions of a trade."""
        records = self.repository.find_all_versions_by_id(trade_id)
        if not records:
            raise TradeNotFoundException(trade_id)
        return records

    def list_trades(
        self,
        latest_only: bool = False,
        expired_filter: Optional[str] = None,
        auto_sync_expiry: bool = True,
    ) -> List[TradeRecord]:
        """List trades in store, optionally syncing expiry status first."""
        if auto_sync_expiry:
            self.process_expired_trades()
        return self.repository.find_all(latest_only=latest_only, expired_filter=expired_filter)
