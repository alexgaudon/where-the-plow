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


settings = Settings()
