from datetime import datetime, timedelta, timezone

import httpx

from where_the_plow.config import settings

# The AVL API returns epoch-millisecond timestamps that represent
# Newfoundland Standard Time (UTC-3:30) but are encoded as if they were UTC.
# To get the real UTC time we must add the 3:30 offset back.
_NST_CORRECTION = timedelta(hours=3, minutes=30)


def parse_avl_response(data: dict) -> tuple[list[dict], list[dict]]:
    vehicles = []
    positions = []
    for feature in data.get("features", []):
        attrs = feature["attributes"]
        geom = feature.get("geometry", {})

        vehicle_id = str(attrs["ID"])
        naive_ts = datetime.fromtimestamp(
            attrs["LocationDateTime"] / 1000, tz=timezone.utc
        )
        ts = naive_ts + _NST_CORRECTION

        vehicles.append(
            {
                "vehicle_id": vehicle_id,
                "description": attrs.get("Description", ""),
                "vehicle_type": attrs.get("VehicleType", ""),
            }
        )

        speed_raw = attrs.get("Speed", "0.0")
        try:
            speed = float(speed_raw)
        except (ValueError, TypeError):
            speed = 0.0

        positions.append(
            {
                "vehicle_id": vehicle_id,
                "timestamp": ts,
                "longitude": geom.get("x", 0.0),
                "latitude": geom.get("y", 0.0),
                "bearing": attrs.get("Bearing", 0),
                "speed": speed,
                "is_driving": attrs.get("isDriving", ""),
            }
        )

    return vehicles, positions


async def fetch_vehicles(client: httpx.AsyncClient) -> dict:
    params = {
        "f": "json",
        "outFields": "ID,Description,VehicleType,LocationDateTime,Bearing,Speed,isDriving",
        "outSR": "4326",
        "returnGeometry": "true",
        "where": "1=1",
    }
    headers = {
        "Referer": settings.avl_referer,
    }
    resp = await client.get(
        settings.avl_api_url, params=params, headers=headers, timeout=10
    )
    resp.raise_for_status()
    return resp.json()
