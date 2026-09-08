import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


@dataclass(frozen=True)
class Config:
    token: str = _env("BOT_TOKEN")
    owner_username: str = _env("OWNER_USERNAME", default="inna_strakhova").lstrip("@").lower()
    group_username: str = _env("GROUP_USERNAME", default="inna_kolor").lstrip("@").lower()
    tz: str = _env("TZ", default="Europe/Moscow")
    work_start: str = _env("WORK_START", default="10:00")
    work_end: str = _env("WORK_END", default="22:00")
    db_path: str = _env("DB_PATH", default="bookings.db")
    openrouter_api_key: str = _env("inna_api_key", "OPENROUTER_API_KEY")
    openrouter_model: str = _env("OPENROUTER_MODEL", default="openrouter/auto")
    openrouter_site_url: str = _env("OPENROUTER_SITE_URL", default="https://t.me/inna_kolor")
    port: int = int(_env("PORT", default="10000"))


config = Config()
