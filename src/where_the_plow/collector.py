# src/where_the_plow/collector.py
import asyncio
import logging
from datetime import datetime, timezone

import httpx

from where_the_plow.client import (
    fetch_vehicles,
    fetch_mt_pearl_vehicles,
    parse_avl_response,
    parse_mt_pearl_response,
)
from where_the_plow.db import Database
from where_the_plow.config import settings
from where_the_plow.snapshot import build_realtime_snapshot

logger = logging.getLogger(__name__)


def process_poll_st_johns(db: Database, response: dict) -> int:
    now = datetime.now(timezone.utc)
    vehicles, positions = parse_avl_response(response)
    db.upsert_vehicles(vehicles, now, "st_johns")
    inserted = db.insert_positions(positions, now, "st_johns")
    return inserted


def process_poll_mt_pearl(db: Database, response: list) -> int:
    now = datetime.now(timezone.utc)
    vehicles, positions = parse_mt_pearl_response(response)
    db.upsert_vehicles(vehicles, now, "mt_pearl")
    inserted = db.insert_positions(positions, now, "mt_pearl")
    return inserted


async def poll_st_johns(client: httpx.AsyncClient, db: Database) -> int:
    try:
        response = await fetch_vehicles(client)
        count = len(response.get("features", []))
        inserted = process_poll_st_johns(db, response)
        logger.info("st_johns: %d vehicles seen, %d new positions", count, inserted)
        return inserted
    except Exception:
        logger.exception("st_johns poll failed")
        return 0


async def poll_mt_pearl(client: httpx.AsyncClient, db: Database) -> int:
    try:
        response = await fetch_mt_pearl_vehicles(client)
        count = len(response) if isinstance(response, list) else 0
        inserted = process_poll_mt_pearl(db, response)
        logger.info("mt_pearl: %d vehicles seen, %d new positions", count, inserted)
        return inserted
    except Exception:
        logger.exception("mt_pearl poll failed")
        return 0


async def run(db: Database, store: dict):
    logger.info("Collector starting — polling every %ds", settings.poll_interval)

    stats = db.get_stats()
    logger.info(
        "DB stats: %d positions, %d vehicles",
        stats["total_positions"],
        stats["total_vehicles"],
    )

    async with httpx.AsyncClient() as client:
        while True:
            try:
                await asyncio.gather(
                    poll_st_johns(client, db),
                    poll_mt_pearl(client, db),
                )
                store["realtime"] = {
                    "st_johns": build_realtime_snapshot(db, "st_johns"),
                    "mt_pearl": build_realtime_snapshot(db, "mt_pearl"),
                }
            except asyncio.CancelledError:
                logger.info("Collector shutting down")
                raise
            except Exception:
                logger.exception("Poll cycle failed")

            await asyncio.sleep(settings.poll_interval)
