"""Background scheduler for automatically updating expired trades."""

import logging
import threading
import time
from typing import Optional
from trade_store.services import TradeService

logger = logging.getLogger(__name__)


class TradeExpiryScheduler:
    """Runs a periodic background worker that updates expired trades."""

    def __init__(self, trade_service: TradeService, interval_seconds: int = 60):
        self.trade_service = trade_service
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _worker(self):
        logger.info("TradeExpiryScheduler background worker started.")
        while not self._stop_event.is_set():
            try:
                updated_count = self.trade_service.process_expired_trades()
                if updated_count > 0:
                    logger.info(f"TradeExpiryScheduler updated {updated_count} expired trades.")
            except Exception as e:
                logger.error(f"Error in TradeExpiryScheduler worker: {e}", exc_info=True)

            # Wait for interval or stop event
            self._stop_event.wait(timeout=self.interval_seconds)
        logger.info("TradeExpiryScheduler background worker stopped.")

    def start(self) -> None:
        """Start the background scheduler thread if not running."""
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._worker,
                name="TradeExpirySchedulerThread",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Signal the worker to stop and wait for thread to join."""
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join(timeout=timeout)

    def is_running(self) -> bool:
        """Check if scheduler thread is actively running."""
        return self._thread is not None and self._thread.is_alive()

    def trigger_now(self) -> int:
        """Manually trigger immediate execution of expiry processing."""
        return self.trade_service.process_expired_trades()
