# tests/test_db.py
import os
import tempfile
from datetime import datetime, timezone

from where_the_plow.db import Database


def make_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path)
    db.init()
    return db, path


def test_init_creates_tables():
    db, path = make_db()
    tables = db.conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
    ).fetchall()
    table_names = {t[0] for t in tables}
    assert "vehicles" in table_names
    assert "positions" in table_names
    db.close()
    os.unlink(path)


def test_upsert_vehicles():
    db, path = make_db()
    now = datetime.now(timezone.utc)
    vehicles = [
        {"vehicle_id": "v1", "description": "Plow 1", "vehicle_type": "LOADER"},
    ]
    db.upsert_vehicles(vehicles, now)

    rows = db.conn.execute("SELECT * FROM vehicles").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "v1"

    # Upsert again — should update last_seen
    later = datetime(2026, 3, 1, tzinfo=timezone.utc)
    db.upsert_vehicles(vehicles, later)
    rows = db.conn.execute(
        "SELECT last_seen FROM vehicles WHERE vehicle_id='v1'"
    ).fetchone()
    assert rows[0] == later

    db.close()
    os.unlink(path)


def test_insert_positions_dedup():
    db, path = make_db()
    now = datetime.now(timezone.utc)
    ts = datetime(2026, 2, 19, 12, 0, 0, tzinfo=timezone.utc)

    positions = [
        {
            "vehicle_id": "v1",
            "timestamp": ts,
            "longitude": -52.73,
            "latitude": 47.56,
            "bearing": 135,
            "speed": 13.4,
            "is_driving": "maybe",
        },
    ]

    inserted = db.insert_positions(positions, now)
    assert inserted == 1

    # Same data again — should be deduped
    inserted = db.insert_positions(positions, now)
    assert inserted == 0

    total = db.conn.execute("SELECT count(*) FROM positions").fetchone()[0]
    assert total == 1

    db.close()
    os.unlink(path)


def test_get_stats_empty():
    db, path = make_db()
    stats = db.get_stats()
    assert stats["total_positions"] == 0
    assert stats["total_vehicles"] == 0
    db.close()
    os.unlink(path)
