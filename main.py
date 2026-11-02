"""Entrypoint script to launch the Trade Store REST API server."""

import uvicorn
from trade_store.api import create_app
from trade_store.config import settings

app = create_app(
    db_path=settings.db_path,
    start_scheduler=settings.enable_scheduler,
)

if __name__ == "__main__":
    print(f"Starting {settings.app_name} on {settings.host}:{settings.port}")
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=False)
