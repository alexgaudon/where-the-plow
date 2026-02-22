import os


class Settings:
    def __init__(self):
        self.db_path: str = os.environ.get("DB_PATH", "/data/plow.db")
        self.poll_interval: int = int(os.environ.get("POLL_INTERVAL", "6"))
        self.log_level: str = os.environ.get("LOG_LEVEL", "INFO")
        self.avl_api_url: str = os.environ.get(
            "AVL_API_URL",
            "https://map.stjohns.ca/mapsrv/rest/services/AVL/MapServer/0/query",
        )
        self.avl_referer: str = "https://map.stjohns.ca/avl/"
        self.mt_pearl_api_url: str = os.environ.get(
            "MT_PEARL_API_URL",
            "https://gps5.aatracking.com/api/MtPearlPortal/GetPlows",
        )


CITY_CONFIGS = {
    "st_johns": {
        "center": [-52.71, 47.56],
        "zoom": 12,
        "display_name": "St. John's",
    },
    "mt_pearl": {
        "center": [-52.81, 47.52],
        "zoom": 13,
        "display_name": "Mount Pearl",
    },
}


settings = Settings()
