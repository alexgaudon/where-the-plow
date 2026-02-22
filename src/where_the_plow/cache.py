# src/where_the_plow/cache.py
"""Simple file-based cache for coverage trail responses.

Stores JSON in /tmp/where-the-plow-cache/ keyed by a hash of the
(since, until) time range.  Only caches queries whose `until` is
before today (i.e. fully historical, immutable data).  Uses LRU
eviction by file access time when total cache size exceeds a budget.
"""

import hashlib
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

CACHE_DIR = Path(tempfile.gettempdir()) / "where-the-plow-cache"
MAX_CACHE_BYTES = 200 * 1024 * 1024  # 200 MB


def _cache_key(since: datetime, until: datetime) -> str:
    raw = f"{since.isoformat()}|{until.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _is_cacheable(until: datetime) -> bool:
    """Only cache if the entire window is in the past (before today UTC)."""
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    until_utc = until if until.tzinfo else until.replace(tzinfo=timezone.utc)
    return until_utc < today_start


def _ensure_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _evict_if_needed():
    """Delete oldest-accessed files until total size is under budget."""
    try:
        files = list(CACHE_DIR.glob("*.json"))
        if not files:
            return
        total = sum(f.stat().st_size for f in files)
        if total <= MAX_CACHE_BYTES:
            return
        # Sort by access time, oldest first
        files.sort(key=lambda f: f.stat().st_atime)
        for f in files:
            if total <= MAX_CACHE_BYTES:
                break
            size = f.stat().st_size
            f.unlink(missing_ok=True)
            total -= size
            logger.debug("cache evict: %s (%d bytes)", f.name, size)
    except OSError:
        pass


def get(since: datetime, until: datetime) -> list[dict] | None:
    """Return cached trails or None if not cached."""
    if not _is_cacheable(until):
        return None
    path = CACHE_DIR / f"{_cache_key(since, until)}.json"
    if not path.exists():
        return None
    try:
        # Touch access time for LRU
        os.utime(path)
        data = json.loads(path.read_text())
        logger.debug("cache hit: %s", path.name)
        return data
    except (OSError, json.JSONDecodeError):
        return None


def put(since: datetime, until: datetime, trails: list[dict]):
    """Store trails in cache if the query is cacheable."""
    if not _is_cacheable(until):
        return
    _ensure_dir()
    _evict_if_needed()
    path = CACHE_DIR / f"{_cache_key(since, until)}.json"
    try:
        path.write_text(json.dumps(trails))
        logger.debug("cache put: %s (%d trails)", path.name, len(trails))
    except OSError:
        pass
