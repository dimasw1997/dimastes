"""Pembacaan konfigurasi dari file .env.

Semua nilai punya default yang aman sehingga program tetap berjalan
walaupun file .env belum dibuat.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Path absolut supaya .env dan database tetap ditemukan walaupun program
# dijalankan dari folder lain (misalnya `python /path/ke/dimastes/cli.py`).
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _list_setting(name: str, default: str) -> list[str]:
    value = os.getenv(name, default) or default
    return [item.strip() for item in value.split(",") if item.strip()]


def _int_setting(name: str, default: int) -> int:
    try:
        return int(str(os.getenv(name, str(default))).strip())
    except (TypeError, ValueError):
        return default


def _bool_setting(name: str, default: bool = False) -> bool:
    value = str(os.getenv(name, str(default))).strip().lower()
    return value in ("1", "true", "yes", "y", "ya")


# Minimal satu halaman supaya perulangan pencarian tidak kosong.
_MAX_PAGES = max(1, _int_setting("MAX_PAGES", 3))


@dataclass
class Config:
    email: str = os.getenv("JOBSTREET_EMAIL", "")
    password: str = os.getenv("JOBSTREET_PASSWORD", "")

    keywords: list[str] = field(default_factory=lambda: _list_setting(
        "KEYWORDS",
        "inventory control,PPIC,production planner,material planner"
    ))
    # Lokasi utama (dipertahankan untuk kompatibilitas).
    location: str = os.getenv("LOCATION", "Bandung")

    # Daftar lokasi yang dicari. Bila kosong, dipakai LOCATION saja.
    locations: list[str] = field(default_factory=lambda: _list_setting(
        "LOCATIONS", ""
    ))

    # Ikut sertakan lowongan yang sepenuhnya remote.
    allow_remote: bool = _bool_setting("ALLOW_REMOTE", False)
    min_salary: int = _int_setting("MIN_SALARY", 0)
    max_experience: int = _int_setting("MAX_EXPERIENCE_YEARS", 5)
    exclude_keywords: list[str] = field(default_factory=lambda: _list_setting(
        "EXCLUDE_KEYWORDS",
        "principal,director,head,senior,lead"
    ))

    # Tolak lowongan yang lokasinya jelas di luar LOCATION.
    strict_location: bool = _bool_setting("STRICT_LOCATION", False)

    # Urutkan hasil pencarian dari yang paling baru (ListedDate).
    # Kosongkan SORT_MODE untuk kembali ke urutan relevansi JobStreet.
    sort_mode: str = os.getenv("SORT_MODE", "ListedDate").strip()
    prefer_newest: bool = _bool_setting("PREFER_NEWEST", True)

    # 0 = tanpa batas umur. Nilai yang didukung JobStreet: 1, 3, 7, 14, 31.
    max_age_days: int = _int_setting("MAX_AGE_DAYS", 0)

    max_apply_per_day: int = _int_setting("MAX_APPLY_PER_DAY", 5)
    delay_between_apply: int = _int_setting("DELAY_BETWEEN_APPLY", 3)
    max_pages: int = _MAX_PAGES
    headless: bool = _bool_setting("HEADLESS_MODE", False)

    # --- Lamaran otomatis ---
    # Default mati; nyalakan lewat AUTO_APPLY=true di .env atau `run --auto`.
    auto_apply: bool = _bool_setting("AUTO_APPLY", False)
    auto_apply_max_per_session: int = max(
        1, _int_setting("AUTO_APPLY_MAX_PER_SESSION", 25)
    )
    auto_apply_step_timeout: int = max(
        5, _int_setting("AUTO_APPLY_STEP_TIMEOUT", 30)
    )

    base_url: str = "https://id.jobstreet.com"
    login_url: str = "https://id.jobstreet.com"
    search_url: str = "https://id.jobstreet.com/jobs"

    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

    db_path: str = os.getenv("DB_PATH", str(BASE_DIR / "jobstreet_auto.db"))

    def __post_init__(self):
        # LOCATIONS kosong -> pakai LOCATION tunggal.
        self.locations = [loc for loc in self.locations if loc.strip()]
        if not self.locations:
            self.locations = [self.location] if self.location else []

        if not self.location and self.locations:
            self.location = self.locations[0]


# Baris ini yang dibutuhkan oleh: from config import config
config = Config()
