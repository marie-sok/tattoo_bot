import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    token: str = os.getenv('BOT_TOKEN', '')
    owner_username: str = os.getenv('OWNER_USERNAME', 'inna_strakhova').lstrip('@').lower()
    tz: str = os.getenv('TZ', 'Europe/Moscow')
    work_start: str = os.getenv('WORK_START', '10:00')
    work_end: str = os.getenv('WORK_END', '22:00')
    openrouter_api_key: str = os.getenv('OPENROUTER_API_KEY', '')
    openrouter_model: str = os.getenv('OPENROUTER_MODEL', 'openai/gpt-5.3-chat')
    openrouter_site_url: str = os.getenv('OPENROUTER_SITE_URL', 'https://t.me/')


config = Config()
