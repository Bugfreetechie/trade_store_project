"""Data models for Trade Store entity and API schemas."""

from datetime import date, datetime
from typing import Optional, Union
from pydantic import BaseModel, Field, validator


def parse_flexible_date(v: Union[date, str, None]) -> Optional[date]:
    """Parse dates from either date objects, DD/MM/YYYY, or YYYY-MM-DD strings."""
    if v is None:
        return None
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        v = v.strip()
        # Try DD/MM/YYYY first as specified in problem statement
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(v, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Invalid date format '{v}'. Expected DD/MM/YYYY or YYYY-MM-DD.")
    raise ValueError(f"Unsupported date type: {type(v)}")


class TradeBase(BaseModel):
    """Base trade schema with shared attributes."""
    trade_id: str = Field(..., description="Unique Trade identifier (e.g. T1, T2)", min_length=1)
    version: int = Field(..., description="Trade version number (1, 2, ...)", ge=1)
    counter_party_id: str = Field(..., description="Counterparty identifier (e.g. CP-1)", min_length=1)
    portfolio_id: str = Field(..., description="Portfolio identifier (e.g. B1)", min_length=1)
    maturity_date: date = Field(..., description="Trade maturity date (DD/MM/YYYY or YYYY-MM-DD)")
    created_date: Optional[date] = Field(None, description="Trade creation date. Defaults to current date if omitted.")
    expired: str = Field("N", description="Expiry status: 'Y' or 'N'", regex="^(Y|N)$")

    @validator("maturity_date", pre=True)
    def validate_maturity_date(cls, v):
        return parse_flexible_date(v)

    @validator("created_date", pre=True)
    def validate_created_date(cls, v):
        return parse_flexible_date(v)

    @validator("expired", pre=True)
    def normalize_expired(cls, v):
        if isinstance(v, bool):
            return "Y" if v else "N"
        if isinstance(v, str):
            v = v.strip().upper()
            if v in ("Y", "YES", "TRUE", "1"):
                return "Y"
            if v in ("N", "NO", "FALSE", "0"):
                return "N"
        return "N"

    class Config:
        anystr_strip_whitespace = True
        allow_population_by_field_name = True


class TradeCreate(TradeBase):
    """Schema for trade submission to store."""
    pass


class TradeResponse(TradeBase):
    """Schema for trade responses, including display format."""
    maturity_date_formatted: Optional[str] = None
    created_date_formatted: Optional[str] = None

    @classmethod
    def from_domain(cls, trade: "TradeRecord") -> "TradeResponse":
        return cls(
            trade_id=trade.trade_id,
            version=trade.version,
            counter_party_id=trade.counter_party_id,
            portfolio_id=trade.portfolio_id,
            maturity_date=trade.maturity_date,
            created_date=trade.created_date,
            expired=trade.expired,
            maturity_date_formatted=trade.maturity_date.strftime("%d/%m/%Y") if trade.maturity_date else None,
            created_date_formatted=trade.created_date.strftime("%d/%m/%Y") if trade.created_date else None,
        )


class TradeRecord:
    """Domain record representing an entry in the trade store."""
    def __init__(
        self,
        trade_id: str,
        version: int,
        counter_party_id: str,
        portfolio_id: str,
        maturity_date: date,
        created_date: Optional[date] = None,
        expired: str = "N",
    ):
        self.trade_id = trade_id
        self.version = version
        self.counter_party_id = counter_party_id
        self.portfolio_id = portfolio_id
        self.maturity_date = maturity_date
        self.created_date = created_date or date.today()
        self.expired = "Y" if expired.upper() in ("Y", "YES", "TRUE") else "N"

    def to_dict(self):
        return {
            "trade_id": self.trade_id,
            "version": self.version,
            "counter_party_id": self.counter_party_id,
            "portfolio_id": self.portfolio_id,
            "maturity_date": self.maturity_date.isoformat(),
            "created_date": self.created_date.isoformat(),
            "expired": self.expired,
        }

    def __repr__(self):
        return (
            f"TradeRecord(trade_id='{self.trade_id}', version={self.version}, "
            f"counter_party_id='{self.counter_party_id}', portfolio_id='{self.portfolio_id}', "
            f"maturity_date={self.maturity_date}, created_date={self.created_date}, "
            f"expired='{self.expired}')"
        )
