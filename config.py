import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _list_setting(name: str, default: str) -> list[str]:
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


def _int_setting(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default


def _bool_setting(name: str, default: bool = False) -> bool:
    value = os.getenv(name, str(default)).strip().lower()
    return value in ("1", "true", "yes", "y", "ya")


@dataclass
class Config:
    email: str = os.getenv("JOBSTREET_EMAIL", "")
    password: str = os.getenv("JOBSTREET_PASSWORD", "")

    keywords: list[str] = field(default_factory=lambda: _list_setting(
        "KEYWORDS",
        "inventory control,PPIC,production planner,material planner"
    ))
    location: str = os.getenv("LOCATION", "Bandung")
    min_salary: int = _int_setting("MIN_SALARY", 0)
    max_experience: int = _int_setting("MAX_EXPERIENCE_YEARS", 5)
    exclude_keywords: list[str] = field(default_factory=lambda: _list_setting(
        "EXCLUDE_KEYWORDS",
        "principal,director,head,senior,lead"
    ))

    max_apply_per_day: int = _int_setting("MAX_APPLY_PER_DAY", 5)
    delay_between_apply: int = _int_setting("DELAY_BETWEEN_APPLY", 3)
    headless: bool = _bool_setting("HEADLESS_MODE", False)

    base_url: str = "https://id.jobstreet.com"
    login_url: str = "https://id.jobstreet.com"
    search_url: str = "https://id.jobstreet.com/jobs"

    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")


# Baris ini yang dibutuhkan oleh: from config import config
config = Config()