# API & Map Frontend Design

## Context

We have a running data collector that polls the St. John's AVL API every 6 seconds and stores deduplicated vehicle positions in DuckDB. We now need:

1. DuckDB spatial extension integration for geometry-aware queries
2. A public GeoJSON API so consumers (and our frontend) can access the data
3. A MapLibre GL JS map frontend to visualize vehicles in real-time

## DuckDB Spatial Integration

### Extension Setup

On database init, install and load the spatial extension:

```sql
INSTALL spatial;
LOAD spatial;
```

### Schema Changes

Add a `GEOMETRY` column to the `positions` table. Keep `longitude`/`latitude` columns for convenience — the geometry column enables spatial indexing and native GeoJSON output.

```sql
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
);
```

On insert, populate `geom` via `ST_Point(longitude, latitude)`.

### Why Spatial Extension

- `ST_DWithin(geom, ST_Point(lng, lat), radius)` — fast proximity queries for "plow near me"
- `ST_AsGeoJSON(geom)` — build GeoJSON responses directly in SQL, no Python transformation
- `ST_Distance(geom, ST_Point(lng, lat))` — sort results by distance
- Spatial indexing for efficient radius queries as data grows

## API Endpoints

All geo endpoints return GeoJSON FeatureCollections. The API is served by the existing FastAPI app.

### GET /vehicles

Current position of every vehicle.

```
Response: GeoJSON FeatureCollection
```

Each feature:
```json
{
  "type": "Feature",
  "geometry": { "type": "Point", "coordinates": [-52.731, 47.564] },
  "properties": {
    "vehicle_id": "281474984421544",
    "description": "2222 SA PLOW TRUCK",
    "vehicle_type": "SA PLOW TRUCK",
    "speed": 13.4,
    "bearing": 135,
    "is_driving": "maybe",
    "timestamp": "2026-02-19T12:53:14Z"
  }
}
```

SQL approach: For each vehicle, get the row with the latest `timestamp` from `positions`, join with `vehicles` for description/type.

### GET /vehicles/nearby

Vehicles within a radius of a point.

```
Query params:
  lat    (required) — latitude
  lng    (required) — longitude
  radius (optional, default 500) — radius in meters

Response: GeoJSON FeatureCollection (same feature shape as /vehicles)
```

SQL approach: Same as `/vehicles` but filtered with `ST_DWithin()`. Radius in meters converted to approximate degrees at St. John's latitude (~1m ≈ 0.000009 degrees).

### GET /vehicles/{id}/history

Position history for one vehicle.

```
Query params:
  since (optional, default 4 hours ago) — ISO 8601 datetime
  until (optional, default now)         — ISO 8601 datetime

Response: GeoJSON FeatureCollection of Point features, ordered by timestamp
```

Each feature's properties include `timestamp`, `speed`, `bearing`, `is_driving`.

### GET /coverage

All positions in a time window. For heatmap visualization.

```
Query params:
  since (optional, default 4 hours ago) — ISO 8601 datetime
  until (optional, default now)         — ISO 8601 datetime

Response: GeoJSON FeatureCollection of all position points
```

### GET /stats

Collection statistics (plain JSON, not GeoJSON).

```json
{
  "total_positions": 12345,
  "total_vehicles": 112,
  "active_vehicles": 15,
  "earliest": "2026-02-19T00:00:00Z",
  "latest": "2026-02-19T12:53:14Z"
}
```

### GET /health

Existing endpoint. Unchanged.

## MapLibre Frontend

A single HTML page served at `GET /`. No build step, no bundling.

### Technical Stack

- MapLibre GL JS loaded from CDN (unpkg)
- Vanilla JavaScript — no framework
- Single file: `src/where_the_plow/static/index.html`
- FastAPI serves it via `StaticFiles` mount or direct route

### Features

- Full-screen map centered on St. John's (~47.56, -52.71)
- Free tile source (OpenFreeMap or MapLibre demo tiles)
- Vehicle markers from `GET /vehicles` GeoJSON source
- Markers colored by vehicle type (plow = blue, loader = orange, etc.)
- Marker rotation from `bearing` property
- Auto-refresh every 6 seconds via `source.setData()`
- Click marker → popup with vehicle description, speed, last update time

### Refresh Loop

```javascript
setInterval(async () => {
    const resp = await fetch('/vehicles');
    const data = await resp.json();
    map.getSource('vehicles').setData(data);
}, 6000);
```

### Tile Source

Use OpenFreeMap (free, no API key required):
```
https://tiles.openfreemap.org/styles/liberty
```

## Project Structure Changes

```
src/where_the_plow/
├── main.py           # Add new routes + static file serving
├── routes.py         # New — API endpoint handlers
├── db.py             # Update — spatial extension, geom column, new query methods
├── static/
│   └── index.html    # New — MapLibre frontend
├── collector.py      # Update — insert geom on position writes
├── client.py         # Unchanged
└── config.py         # Unchanged
```

## Implementation Order

1. DuckDB spatial extension + schema migration (add geom column)
2. Update collector to populate geom on insert
3. Add query methods to db.py (latest positions, nearby, history, coverage)
4. Add API routes (routes.py + wire into main.py)
5. Build the MapLibre frontend (static/index.html)
6. Update Dockerfile (ensure spatial extension available in container)

## Migration Strategy

The DuckDB file already has data in it. We need to:

1. Load the spatial extension
2. Add the `geom` column if it doesn't exist
3. Backfill existing rows: `UPDATE positions SET geom = ST_Point(longitude, latitude) WHERE geom IS NULL`
4. Future inserts populate geom at write time

This runs in `db.init()` — idempotent, safe to run on every startup.
