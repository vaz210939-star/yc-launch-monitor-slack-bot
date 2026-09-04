from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Load a small, dependency-free .env file without overriding real environment values."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name or not name.replace("_", "a").isalnum() or name[0].isdigit():
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(name, value)


def _boolean(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _queries(name: str) -> tuple[str, ...] | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    values = json.loads(raw)
    if not isinstance(values, list) or not values or not all(isinstance(item, str) and item.strip() for item in values):
        raise ValueError(f"{name} must be a non-empty JSON array of strings")
    return tuple(item.strip() for item in values)


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: Path
    twitter_api_key: str
    tinyfish_api_key: str
    x_queries: tuple[str, ...] | None
    linkedin_queries: tuple[str, ...] | None
    slack_bot_token: str
    slack_channel_id: str
    slack_delivery_enabled: bool
    bootstrap_notify: bool
    notify_needs_review: bool
    interval_seconds: int
    health_host: str
    health_port: int

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv()
        return cls(
            database_path=Path(os.getenv("MONITOR_DATABASE_PATH", "data/monitor.db")),
            twitter_api_key=os.getenv("TWITTERAPIIO_API_KEY", ""),
            tinyfish_api_key=os.getenv("TINYFISH_API_KEY", ""),
            x_queries=_queries("X_QUERIES_JSON"),
            linkedin_queries=_queries("LINKEDIN_QUERIES_JSON"),
            slack_bot_token=os.getenv("SLACK_BOT_TOKEN", ""),
            slack_channel_id=os.getenv("SLACK_CHANNEL_ID", ""),
            slack_delivery_enabled=_boolean("SLACK_DELIVERY_ENABLED"),
            bootstrap_notify=_boolean("BOOTSTRAP_NOTIFY"),
            notify_needs_review=_boolean("NOTIFY_NEEDS_REVIEW"),
            interval_seconds=max(60, int(os.getenv("MONITOR_INTERVAL_SECONDS", "28800"))),
            health_host=os.getenv("HEALTH_HOST", "0.0.0.0"),
            health_port=int(os.getenv("HEALTH_PORT", "8080")),
        )
