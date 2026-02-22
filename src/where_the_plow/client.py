from datetime import datetime, timedelta, timezone

import httpx

from where_the_plow.config import settings

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


def parse_mt_pearl_response(data: list) -> tuple[list[dict], list[dict]]:
    vehicles = []
    positions = []
    for item in data:
        vehicle_id = str(item["VEH_ID"])

        ts_str = item.get("VEH_EVENT_DATETIME", "")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            ts = datetime.now(timezone.utc)

        vehicles.append(
            {
                "vehicle_id": vehicle_id,
                "description": item.get("VEH_NAME", ""),
                "vehicle_type": item.get("LOO_DESCRIPTION", "Unknown"),
            }
        )

        positions.append(
            {
                "vehicle_id": vehicle_id,
                "timestamp": ts,
                "longitude": item.get("VEH_EVENT_LONGITUDE", 0.0),
                "latitude": item.get("VEH_EVENT_LATITUDE", 0.0),
                "bearing": int(item.get("VEH_EVENT_HEADING", 0)),
                "speed": None,
                "is_driving": "maybe",
            }
        )

    return vehicles, positions


async def fetch_mt_pearl_vehicles(client: httpx.AsyncClient) -> list:
    resp = await client.get(settings.mt_pearl_api_url, timeout=10)
    resp.raise_for_status()
    return resp.json()
