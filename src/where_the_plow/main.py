# src/where_the_plow/main.py
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from where_the_plow import collector
from where_the_plow.config import settings
from where_the_plow.db import Database
from where_the_plow.routes import router

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = Database(settings.db_path)
    db.init()
    app.state.db = db
    logger.info("Database initialized at %s", settings.db_path)

    task = asyncio.create_task(collector.run(db))
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    db.close()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Where the Plow",
    description="Real-time and historical plow tracker for the City of St. John's. "
    "All geo endpoints return GeoJSON FeatureCollections with cursor-based pagination.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/health", tags=["system"])
def health():
    db: Database = app.state.db
    stats = db.get_stats()
    return {"status": "ok", **stats}
