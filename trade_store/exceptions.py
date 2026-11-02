"""Custom domain exceptions for Trade Store application."""


class TradeStoreException(Exception):
    """Base exception for all Trade Store domain errors."""
    pass


class LowerVersionException(TradeStoreException):
    """Raised when an incoming trade version is lower than the existing store version."""
    def __init__(self, trade_id: str, incoming_version: int, current_version: int):
        self.trade_id = trade_id
        self.incoming_version = incoming_version
        self.current_version = current_version
        super().__init__(
            f"Trade '{trade_id}' rejection: Incoming version {incoming_version} "
            f"is lower than current version {current_version} in the store."
        )


class PastMaturityDateException(TradeStoreException):
    """Raised when an incoming trade has a maturity date earlier than current date."""
    def __init__(self, trade_id: str, maturity_date: str, reference_date: str):
        self.trade_id = trade_id
        self.maturity_date = maturity_date
        self.reference_date = reference_date
        super().__init__(
            f"Trade '{trade_id}' rejection: Maturity date ({maturity_date}) "
            f"cannot be earlier than current date ({reference_date})."
        )


class TradeNotFoundException(TradeStoreException):
    """Raised when a requested trade is not found in the store."""
    def __init__(self, trade_id: str):
        self.trade_id = trade_id
        super().__init__(f"Trade with id '{trade_id}' was not found.")
