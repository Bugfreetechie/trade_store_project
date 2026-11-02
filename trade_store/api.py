"""FastAPI application providing REST endpoints for Trade Store."""

from datetime import date
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from trade_store.database import DatabaseManager
from trade_store.exceptions import (
    LowerVersionException,
    PastMaturityDateException,
    TradeNotFoundException,
    TradeStoreException,
)
from trade_store.models import TradeCreate, TradeResponse, parse_flexible_date
from trade_store.repository import TradeRepository
from trade_store.scheduler import TradeExpiryScheduler
from trade_store.services import TradeService
from trade_store.validators import TradeValidator


def create_app(
    db_path: str = "trade_store.db",
    start_scheduler: bool = True,
    current_date_provider=None,
) -> FastAPI:
    """Factory function for creating the Trade Store FastAPI application."""
    app = FastAPI(
        title="Trade Store REST API",
        description="High-throughput Trade Store with versioning, maturity validation, and auto-expiration.",
        version="1.0.0",
    )

    db_manager = DatabaseManager(db_path=db_path)
    repository = TradeRepository(db_manager)
    validator = TradeValidator(current_date_provider=current_date_provider)
    trade_service = TradeService(repository=repository, validator=validator)
    scheduler = TradeExpiryScheduler(trade_service=trade_service, interval_seconds=60)

    # Attach to app state for dependency injection / access in tests
    app.state.db_manager = db_manager
    app.state.repository = repository
    app.state.validator = validator
    app.state.trade_service = trade_service
    app.state.scheduler = scheduler

    @app.on_event("startup")
    def on_startup():
        if start_scheduler:
            scheduler.start()

    @app.on_event("shutdown")
    def on_shutdown():
        scheduler.stop()
        db_manager.close()

    # Exception Handlers
    @app.exception_handler(LowerVersionException)
    async def handle_lower_version(request: Request, exc: LowerVersionException):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "LowerVersionException",
                "message": str(exc),
                "trade_id": exc.trade_id,
                "incoming_version": exc.incoming_version,
                "current_version": exc.current_version,
            },
        )

    @app.exception_handler(PastMaturityDateException)
    async def handle_past_maturity_date(request: Request, exc: PastMaturityDateException):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "PastMaturityDateException",
                "message": str(exc),
                "trade_id": exc.trade_id,
                "maturity_date": exc.maturity_date,
                "reference_date": exc.reference_date,
            },
        )

    @app.exception_handler(TradeNotFoundException)
    async def handle_not_found(request: Request, exc: TradeNotFoundException):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "TradeNotFoundException",
                "message": str(exc),
                "trade_id": exc.trade_id,
            },
        )

    # API Routes
    @app.get("/health", tags=["System"])
    def health_check():
        return {
            "status": "healthy",
            "service": "Trade Store REST API",
            "scheduler_running": scheduler.is_running(),
            "total_trades": repository.count(),
        }

    @app.post(
        "/trades",
        response_model=TradeResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["Trades"],
        summary="Ingest a new trade or replace an existing version",
    )
    def submit_trade(
        trade: TradeCreate,
        simulated_today: Optional[str] = Query(
            None,
            description="Optional simulated current date (DD/MM/YYYY or YYYY-MM-DD) for testing/simulation",
        ),
    ):
        ref_date = parse_flexible_date(simulated_today) if simulated_today else None
        saved_record = trade_service.process_incoming_trade(trade, current_date=ref_date)
        return TradeResponse.from_domain(saved_record)

    @app.get(
        "/trades",
        response_model=List[TradeResponse],
        tags=["Trades"],
        summary="List all trades with optional filtering",
    )
    def list_trades(
        latest_only: bool = Query(False, description="Return only highest version per trade ID"),
        expired: Optional[str] = Query(None, regex="^(Y|N|y|n)$", description="Filter by expired flag ('Y' or 'N')"),
        auto_sync: bool = Query(True, description="Sync expired trades against current date before returning"),
    ):
        records = trade_service.list_trades(
            latest_only=latest_only,
            expired_filter=expired,
            auto_sync_expiry=auto_sync,
        )
        return [TradeResponse.from_domain(r) for r in records]

    @app.get(
        "/trades/{trade_id}",
        response_model=TradeResponse,
        tags=["Trades"],
        summary="Retrieve trade details by ID",
    )
    def get_trade(
        trade_id: str,
        version: Optional[int] = Query(None, ge=1, description="Specific trade version, defaults to latest"),
    ):
        record = trade_service.get_trade(trade_id=trade_id, version=version)
        return TradeResponse.from_domain(record)

    @app.get(
        "/trades/{trade_id}/history",
        response_model=List[TradeResponse],
        tags=["Trades"],
        summary="Retrieve all versions and audit trail of a trade",
    )
    def get_trade_history(trade_id: str):
        records = trade_service.get_trade_history(trade_id=trade_id)
        return [TradeResponse.from_domain(r) for r in records]

    @app.post(
        "/trades/process-expiry",
        tags=["Trades"],
        summary="Trigger automated expiry check across all stored trades",
    )
    def trigger_expiry_processing(
        as_of_date: Optional[str] = Query(
            None,
            description="Reference date for expiry check (DD/MM/YYYY or YYYY-MM-DD). Defaults to today.",
        ),
    ):
        ref_date = parse_flexible_date(as_of_date) if as_of_date else None
        updated_count = trade_service.process_expired_trades(as_of_date=ref_date)
        return {
            "status": "success",
            "updated_count": updated_count,
            "as_of_date": (ref_date or validator.get_current_date()).isoformat(),
        }

    return app


app = create_app()
