# src/where_the_plow/db.py
import duckdb
from datetime import datetime


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn = duckdb.connect(path)

    def init(self):
        self.conn.execute("INSTALL spatial")
        self.conn.execute("LOAD spatial")

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                vehicle_id    VARCHAR PRIMARY KEY,
                description   VARCHAR,
                vehicle_type  VARCHAR,
                first_seen    TIMESTAMPTZ NOT NULL,
                last_seen     TIMESTAMPTZ NOT NULL
            )
        """)
        self.conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS positions_seq
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id            BIGINT DEFAULT nextval('positions_seq'),
                vehicle_id    VARCHAR NOT NULL,
                timestamp     TIMESTAMPTZ NOT NULL,
                collected_at  TIMESTAMPTZ NOT NULL,
                longitude     DOUBLE NOT NULL,
                latitude      DOUBLE NOT NULL,
                geom          GEOMETRY,
                bearing       INTEGER,
                speed         DOUBLE,
                is_driving    VARCHAR,
                PRIMARY KEY (vehicle_id, timestamp)
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_time_geo
                ON positions (timestamp, latitude, longitude)
        """)

        # Migration: add geom column to existing tables that lack it
        cols = self.conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='positions' AND column_name='geom'"
        ).fetchall()
        if not cols:
            self.conn.execute("ALTER TABLE positions ADD COLUMN geom GEOMETRY")

        # Backfill geom for existing rows
        self.conn.execute(
            "UPDATE positions SET geom = ST_Point(longitude, latitude) WHERE geom IS NULL"
        )

    def upsert_vehicles(self, vehicles: list[dict], now: datetime):
        for v in vehicles:
            self.conn.execute(
                """
                INSERT INTO vehicles (vehicle_id, description, vehicle_type, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (vehicle_id) DO UPDATE SET
                    description = EXCLUDED.description,
                    vehicle_type = EXCLUDED.vehicle_type,
                    last_seen = EXCLUDED.last_seen
            """,
                [v["vehicle_id"], v["description"], v["vehicle_type"], now, now],
            )

    def insert_positions(self, positions: list[dict], collected_at: datetime) -> int:
        if not positions:
            return 0
        count_before = self.conn.execute("SELECT count(*) FROM positions").fetchone()[0]
        for p in positions:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO positions
                    (vehicle_id, timestamp, collected_at, longitude, latitude, geom, bearing, speed, is_driving)
                VALUES (?, ?, ?, ?, ?, ST_Point(?, ?), ?, ?, ?)
            """,
                [
                    p["vehicle_id"],
                    p["timestamp"],
                    collected_at,
                    p["longitude"],
                    p["latitude"],
                    p["longitude"],
                    p["latitude"],
                    p["bearing"],
                    p["speed"],
                    p["is_driving"],
                ],
            )
        count_after = self.conn.execute("SELECT count(*) FROM positions").fetchone()[0]
        return count_after - count_before

    def get_stats(self) -> dict:
        total_positions = self.conn.execute(
            "SELECT count(*) FROM positions"
        ).fetchone()[0]
        total_vehicles = self.conn.execute("SELECT count(*) FROM vehicles").fetchone()[
            0
        ]
        result = {
            "total_positions": total_positions,
            "total_vehicles": total_vehicles,
        }
        if total_positions > 0:
            row = self.conn.execute(
                "SELECT min(timestamp), max(timestamp) FROM positions"
            ).fetchone()
            result["earliest"] = row[0]
            result["latest"] = row[1]
        return result

    def close(self):
        self.conn.close()
