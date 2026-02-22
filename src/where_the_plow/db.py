# src/where_the_plow/db.py
import os

import duckdb
from datetime import datetime
from itertools import groupby


class Database:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.conn = duckdb.connect(path)

    def _cursor(self) -> duckdb.DuckDBPyConnection:
        """Create a thread-local cursor for safe concurrent access."""
        return self.conn.cursor()

    def init(self):
        cur = self._cursor()
        cur.execute("INSTALL spatial")
        cur.execute("LOAD spatial")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                vehicle_id    VARCHAR PRIMARY KEY,
                description   VARCHAR,
                vehicle_type  VARCHAR,
                first_seen    TIMESTAMPTZ NOT NULL,
                last_seen     TIMESTAMPTZ NOT NULL,
                city          VARCHAR NOT NULL DEFAULT 'st_johns'
            )
        """)
        cur.execute("""
            CREATE SEQUENCE IF NOT EXISTS positions_seq
        """)
        cur.execute("""
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
                city          VARCHAR NOT NULL DEFAULT 'st_johns',
                PRIMARY KEY (vehicle_id, timestamp, city)
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_time_geo
                ON positions (timestamp, latitude, longitude)
        """)
        cur.execute("""
            CREATE SEQUENCE IF NOT EXISTS viewports_seq
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS viewports (
                id          BIGINT DEFAULT nextval('viewports_seq') PRIMARY KEY,
                timestamp   TIMESTAMPTZ NOT NULL DEFAULT now(),
                ip          VARCHAR,
                user_agent  VARCHAR,
                zoom        DOUBLE NOT NULL,
                center_lng  DOUBLE NOT NULL,
                center_lat  DOUBLE NOT NULL,
                sw_lng      DOUBLE NOT NULL,
                sw_lat      DOUBLE NOT NULL,
                ne_lng      DOUBLE NOT NULL,
                ne_lat      DOUBLE NOT NULL
            )
        """)
        cur.execute("""
            CREATE SEQUENCE IF NOT EXISTS signups_seq
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS signups (
                id              BIGINT DEFAULT nextval('signups_seq') PRIMARY KEY,
                timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
                email           VARCHAR NOT NULL,
                ip              VARCHAR,
                user_agent      VARCHAR,
                notify_plow     BOOLEAN NOT NULL DEFAULT FALSE,
                notify_projects BOOLEAN NOT NULL DEFAULT FALSE,
                notify_siliconharbour BOOLEAN NOT NULL DEFAULT FALSE,
                note            VARCHAR
            )
        """)

        # Migration: add geom column to existing tables that lack it
        cols = cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='positions' AND column_name='geom'"
        ).fetchall()
        if not cols:
            cur.execute("ALTER TABLE positions ADD COLUMN geom GEOMETRY")

        # Backfill geom for existing rows
        cur.execute(
            "UPDATE positions SET geom = ST_Point(longitude, latitude) WHERE geom IS NULL"
        )

        # Migration: add ip/user_agent columns to viewports
        vp_cols = {
            r[0]
            for r in cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='viewports'"
            ).fetchall()
        }
        if "ip" not in vp_cols:
            cur.execute("ALTER TABLE viewports ADD COLUMN ip VARCHAR")
        if "user_agent" not in vp_cols:
            cur.execute("ALTER TABLE viewports ADD COLUMN user_agent VARCHAR")

        # Migration: add ip/user_agent columns to signups
        su_cols = {
            r[0]
            for r in cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='signups'"
            ).fetchall()
        }
        if su_cols:  # table exists from a prior run
            if "ip" not in su_cols:
                cur.execute("ALTER TABLE signups ADD COLUMN ip VARCHAR")
        if "user_agent" not in su_cols:
            cur.execute("ALTER TABLE signups ADD COLUMN user_agent VARCHAR")

        veh_cols = {
            r[0]
            for r in cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='vehicles'"
            ).fetchall()
        }
        if "city" not in veh_cols:
            cur.execute(
                "ALTER TABLE vehicles ADD COLUMN city VARCHAR NOT NULL DEFAULT 'st_johns'"
            )

        pos_cols = {
            r[0]
            for r in cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='positions'"
            ).fetchall()
        }
        if "city" not in pos_cols:
            cur.execute(
                "ALTER TABLE positions ADD COLUMN city VARCHAR NOT NULL DEFAULT 'st_johns'"
            )

    def upsert_vehicles(self, vehicles: list[dict], now: datetime, city: str):
        cur = self._cursor()
        for v in vehicles:
            cur.execute(
                """
                INSERT INTO vehicles (vehicle_id, description, vehicle_type, first_seen, last_seen, city)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (vehicle_id) DO UPDATE SET
                    description = EXCLUDED.description,
                    vehicle_type = EXCLUDED.vehicle_type,
                    last_seen = EXCLUDED.last_seen,
                    city = EXCLUDED.city
            """,
                [v["vehicle_id"], v["description"], v["vehicle_type"], now, now, city],
            )

    def insert_positions(
        self, positions: list[dict], collected_at: datetime, city: str
    ) -> int:
        if not positions:
            return 0
        cur = self._cursor()
        count_before = cur.execute("SELECT count(*) FROM positions").fetchone()[0]
        for p in positions:
            cur.execute(
                """
                INSERT OR IGNORE INTO positions
                    (vehicle_id, timestamp, collected_at, longitude, latitude, geom, bearing, speed, is_driving, city)
                VALUES (?, ?, ?, ?, ?, ST_Point(?, ?), ?, ?, ?, ?)
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
                    city,
                ],
            )
        count_after = cur.execute("SELECT count(*) FROM positions").fetchone()[0]
        return count_after - count_before

    def get_latest_positions(
        self, limit: int = 200, after: datetime | None = None, city: str | None = None
    ) -> list[dict]:
        """Get the latest position for each vehicle."""
        city_filter = "AND city = $3" if city else ""
        query = f"""
            WITH ranked AS (
                SELECT p.vehicle_id, p.timestamp, p.longitude, p.latitude,
                       p.bearing, p.speed, p.is_driving,
                       v.description, v.vehicle_type, v.city,
                       ROW_NUMBER() OVER (PARTITION BY p.vehicle_id ORDER BY p.timestamp DESC) as rn
                FROM positions p
                JOIN vehicles v ON p.vehicle_id = v.vehicle_id
            )
            SELECT vehicle_id, timestamp, longitude, latitude, bearing, speed,
                   is_driving, description, vehicle_type, city
            FROM ranked
            WHERE rn = 1
            AND ($1 IS NULL OR timestamp > $1)
            {city_filter}
            ORDER BY timestamp ASC
            LIMIT $2
        """
        params = [after, limit]
        if city:
            params.append(city)
        rows = self._cursor().execute(query, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_latest_positions_with_trails(
        self, trail_points: int = 6, max_gap_s: int = 120, city: str | None = None
    ) -> list[dict]:
        """Get the latest position for each vehicle plus a mini-trail of recent coords.

        Positions separated by more than max_gap_s seconds are treated as a
        discontinuity — the trail is truncated to only the contiguous segment
        ending at the most recent position.
        """
        city_filter = "AND city = $2" if city else ""
        query = f"""
            WITH ranked AS (
                SELECT p.vehicle_id, p.timestamp, p.longitude, p.latitude,
                       p.bearing, p.speed, p.is_driving,
                       v.description, v.vehicle_type, v.city,
                       ROW_NUMBER() OVER (PARTITION BY p.vehicle_id ORDER BY p.timestamp DESC) as rn
                FROM positions p
                JOIN vehicles v ON p.vehicle_id = v.vehicle_id
            )
            SELECT vehicle_id, timestamp, longitude, latitude, bearing, speed,
                   is_driving, description, vehicle_type, city
            FROM ranked
            WHERE rn <= $1
            {city_filter}
            ORDER BY vehicle_id, timestamp ASC
        """
        params = [trail_points, city] if city else [trail_points]
        rows = self._cursor().execute(query, params).fetchall()
        all_dicts = [self._row_to_dict(r) for r in rows]

        results = []
        for _, group in groupby(all_dicts, key=lambda r: r["vehicle_id"]):
            points = list(group)
            start = len(points) - 1
            for i in range(len(points) - 1, 0, -1):
                gap = (
                    points[i]["timestamp"] - points[i - 1]["timestamp"]
                ).total_seconds()
                if gap > max_gap_s:
                    break
                start = i - 1
            contiguous = points[start:]
            current = contiguous[-1]
            current["trail"] = [[p["longitude"], p["latitude"]] for p in contiguous]
            results.append(current)
        return results

    def get_nearby_vehicles(
        self,
        lat: float,
        lng: float,
        radius_m: float,
        limit: int = 200,
        after: datetime | None = None,
        city: str | None = None,
    ) -> list[dict]:
        """Get latest vehicle positions within radius_m meters of (lat, lng)."""
        radius_deg = radius_m / 111320.0
        city_filter = "AND city = $5" if city else ""
        query = f"""
            WITH ranked AS (
                SELECT p.vehicle_id, p.timestamp, p.longitude, p.latitude,
                       p.bearing, p.speed, p.is_driving, p.geom,
                       v.description, v.vehicle_type, v.city,
                       ROW_NUMBER() OVER (PARTITION BY p.vehicle_id ORDER BY p.timestamp DESC) as rn
                FROM positions p
                JOIN vehicles v ON p.vehicle_id = v.vehicle_id
            )
            SELECT vehicle_id, timestamp, longitude, latitude, bearing, speed,
                   is_driving, description, vehicle_type, city
            FROM ranked
            WHERE rn = 1
            AND ST_DWithin(geom, ST_Point($1, $2), $3)
            AND ($4 IS NULL OR timestamp > $4)
            {city_filter}
            ORDER BY timestamp ASC
            LIMIT $6
        """
        params = (
            [lng, lat, radius_deg, after, city, limit]
            if city
            else [lng, lat, radius_deg, after, limit]
        )
        rows = self._cursor().execute(query, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_vehicle_history(
        self,
        vehicle_id: str,
        since: datetime,
        until: datetime,
        limit: int = 200,
        after: datetime | None = None,
        city: str | None = None,
    ) -> list[dict]:
        """Get position history for a single vehicle in a time range."""
        city_filter = "AND v.city = $5" if city else ""
        query = f"""
            SELECT p.vehicle_id, p.timestamp, p.longitude, p.latitude,
                   p.bearing, p.speed, p.is_driving,
                   v.description, v.vehicle_type, v.city
            FROM positions p
            JOIN vehicles v ON p.vehicle_id = v.vehicle_id
            WHERE p.vehicle_id = $1
            AND p.timestamp >= $2
            AND p.timestamp <= $3
            AND ($4 IS NULL OR p.timestamp > $4)
            {city_filter}
            ORDER BY p.timestamp ASC
            LIMIT $6
        """
        params = (
            [vehicle_id, since, until, after, city, limit]
            if city
            else [vehicle_id, since, until, after, limit]
        )
        rows = self._cursor().execute(query, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_coverage(
        self,
        since: datetime,
        until: datetime,
        limit: int = 200,
        after: datetime | None = None,
        city: str | None = None,
    ) -> list[dict]:
        """Get all positions in a time range."""
        city_filter = "AND v.city = $4" if city else ""
        query = f"""
            SELECT p.vehicle_id, p.timestamp, p.longitude, p.latitude,
                   p.bearing, p.speed, p.is_driving,
                   v.description, v.vehicle_type, v.city
            FROM positions p
            JOIN vehicles v ON p.vehicle_id = v.vehicle_id
            WHERE p.timestamp >= $1
            AND p.timestamp <= $2
            AND ($3 IS NULL OR p.timestamp > $3)
            {city_filter}
            ORDER BY p.timestamp ASC
            LIMIT $5
        """
        params = (
            [since, until, after, city, limit] if city else [since, until, after, limit]
        )
        rows = self._cursor().execute(query, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_coverage_trails(
        self,
        since: datetime,
        until: datetime,
        city: str | None = None,
    ) -> list[dict]:
        """Get per-vehicle LineString trails in a time range.

        Uses SQL-side gap detection (>120s breaks a segment) and
        time_bucket downsampling (~1 point per 30s) to minimise
        the number of rows transferred to Python.
        """
        city_filter = "AND v.city = $3" if city else ""
        query = f"""
            WITH with_gap AS (
                SELECT
                    p.vehicle_id,
                    p.timestamp,
                    p.longitude,
                    p.latitude,
                    v.description,
                    v.vehicle_type,
                    EPOCH(p.timestamp - LAG(p.timestamp) OVER (
                        PARTITION BY p.vehicle_id ORDER BY p.timestamp
                    )) AS gap_s
                FROM positions p
                JOIN vehicles v ON p.vehicle_id = v.vehicle_id
                WHERE p.timestamp >= $1
                AND p.timestamp <= $2
                {city_filter}
            ),
            with_segment AS (
                SELECT *,
                    SUM(CASE WHEN gap_s IS NULL OR gap_s > 120 THEN 1 ELSE 0 END)
                        OVER (PARTITION BY vehicle_id ORDER BY timestamp) AS segment_id
                FROM with_gap
            ),
            bucketed AS (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY vehicle_id, segment_id,
                            time_bucket(INTERVAL '30 seconds', timestamp)
                        ORDER BY timestamp
                    ) AS bucket_rn
                FROM with_segment
            )
            SELECT vehicle_id, segment_id, timestamp, longitude, latitude,
                   description, vehicle_type
            FROM bucketed
            WHERE bucket_rn = 1
            ORDER BY vehicle_id, segment_id, timestamp
        """
        params = [since, until, city] if city else [since, until]
        rows = self._cursor().execute(query, params).fetchall()

        trails = []
        for (vid, seg_id), group in groupby(rows, key=lambda r: (r[0], r[1])):
            points = list(group)
            if len(points) < 2:
                continue
            trails.append(
                {
                    "vehicle_id": vid,
                    "description": points[0][5],
                    "vehicle_type": points[0][6],
                    "coordinates": [[p[3], p[4]] for p in points],
                    "timestamps": [
                        p[2].isoformat() if isinstance(p[2], datetime) else str(p[2])
                        for p in points
                    ],
                }
            )

        return trails

    def _row_to_dict(self, row) -> dict:
        return {
            "vehicle_id": row[0],
            "timestamp": row[1],
            "longitude": row[2],
            "latitude": row[3],
            "bearing": row[4],
            "speed": row[5],
            "is_driving": row[6],
            "description": row[7],
            "vehicle_type": row[8],
            "city": row[9] if len(row) > 9 else "st_johns",
        }

    def get_stats(self) -> dict:
        cur = self._cursor()
        row = cur.execute("SELECT count(*) FROM positions").fetchone()
        total_positions = row[0] if row else 0

        row = cur.execute("SELECT count(*) FROM vehicles").fetchone()
        total_vehicles = row[0] if row else 0

        row = cur.execute(
            "SELECT count(DISTINCT vehicle_id) FROM positions WHERE is_driving = 'maybe'"
        ).fetchone()
        active_vehicles = row[0] if row else 0

        try:
            db_size_bytes = os.path.getsize(self.path)
        except OSError:
            db_size_bytes = None
        result = {
            "total_positions": total_positions,
            "total_vehicles": total_vehicles,
            "active_vehicles": active_vehicles,
            "db_size_bytes": db_size_bytes,
        }
        if total_positions > 0:
            row = cur.execute(
                "SELECT min(timestamp), max(timestamp) FROM positions"
            ).fetchone()
            if row:
                result["earliest"] = row[0]
                result["latest"] = row[1]
        return result

    def insert_viewport(
        self,
        zoom: float,
        center_lng: float,
        center_lat: float,
        sw_lng: float,
        sw_lat: float,
        ne_lng: float,
        ne_lat: float,
        ip: str | None = None,
        user_agent: str | None = None,
    ):
        """Record a user viewport focus event."""
        self._cursor().execute(
            """
            INSERT INTO viewports (ip, user_agent, zoom, center_lng, center_lat, sw_lng, sw_lat, ne_lng, ne_lat)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ip,
                user_agent,
                zoom,
                center_lng,
                center_lat,
                sw_lng,
                sw_lat,
                ne_lng,
                ne_lat,
            ],
        )

    def insert_signup(
        self,
        email: str,
        ip: str | None = None,
        user_agent: str | None = None,
        notify_plow: bool = False,
        notify_projects: bool = False,
        notify_siliconharbour: bool = False,
        note: str | None = None,
    ):
        """Record an email signup."""
        self._cursor().execute(
            """
            INSERT INTO signups (email, ip, user_agent, notify_plow, notify_projects, notify_siliconharbour, note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                email,
                ip,
                user_agent,
                notify_plow,
                notify_projects,
                notify_siliconharbour,
                note,
            ],
        )

    def count_recent_signups(self, ip: str, minutes: int = 30) -> int:
        """Count signups from an IP in the last N minutes."""
        row = (
            self._cursor()
            .execute(
                """
            SELECT count(*) FROM signups
            WHERE ip = ? AND timestamp > now() - INTERVAL (?) MINUTE
            """,
                [ip, minutes],
            )
            .fetchone()
        )
        return row[0] if row else 0

    def close(self):
        self.conn.close()
