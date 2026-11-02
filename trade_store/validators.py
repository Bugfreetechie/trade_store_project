"""Validation rules and business logic for incoming trades."""

from datetime import date
from typing import Optional
from trade_store.exceptions import LowerVersionException, PastMaturityDateException
from trade_store.models import TradeBase


class TradeValidator:
    """Validator enforcing store constraints on incoming trades."""

    def __init__(self, current_date_provider=None):
        self._current_date_provider = current_date_provider or date.today

    def get_current_date(self) -> date:
        if callable(self._current_date_provider):
            return self._current_date_provider()
        return self._current_date_provider

    def validate_maturity_date(self, trade: TradeBase, current_date: Optional[date] = None) -> None:
        """
        Validation 2: The store must reject any trade that has a maturity date earlier than today's date.
        """
        ref_date = current_date or self.get_current_date()
        if trade.maturity_date < ref_date:
            raise PastMaturityDateException(
                trade_id=trade.trade_id,
                maturity_date=trade.maturity_date.strftime("%d/%m/%Y"),
                reference_date=ref_date.strftime("%d/%m/%Y"),
            )

    def validate_version(self, trade: TradeBase, current_max_version: Optional[int]) -> bool:
        """
        Validation 1: If a trade with a lower version is received during transmission,
        the store will reject it and generate an exception.
        Trades with the same version will replace the current record.
        Returns:
            True if this trade replaces an existing same-version record,
            False if it is a new version / new trade.
        """
        if current_max_version is not None:
            if trade.version < current_max_version:
                raise LowerVersionException(
                    trade_id=trade.trade_id,
                    incoming_version=trade.version,
                    current_version=current_max_version,
                )
            if trade.version == current_max_version:
                return True  # Replaces existing record
        return False  # New trade or newer version

    def validate(self, trade: TradeBase, current_max_version: Optional[int], current_date: Optional[date] = None) -> bool:
        """Run all business validations against an incoming trade."""
        self.validate_maturity_date(trade, current_date=current_date)
        is_replacement = self.validate_version(trade, current_max_version)
        return is_replacement
