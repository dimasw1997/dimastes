"""Lowongan yang sudah berlabel Applied tidak boleh muncul lagi."""

import pytest
from selenium.common.exceptions import NoSuchElementException

import job_filter as job_filter_module
import main as main_module
from auto_apply import ApplyResult
from config import config
from database import Database
from scraper import JobStreetBot


class FakeElement:
    def __init__(self, visible=True):
        self._visible = visible

    def is_displayed(self):
        return self._visible


class FakeLink:
    text = "Inventory Control"
    id = "link-123"

    def get_attribute(self, name):
        if name == "href":
            return "/job/123"
        return None


class FakeCard:
    def __init__(self, text="Inventory Control\nPT Contoh\nBandung", applied=False):
        self.text = text
        self._applied = applied

    def find_elements(self, by, selector):
        if selector in ("h3 a", "a[href*='/job/']"):
            return [FakeLink()]
        if self._applied and "applied" in selector:
            return [FakeElement(visible=True)]
        return []

    def find_element(self, by, selector):
        raise NoSuchElementException(selector)


class FakeDriver:
    current_url = "https://id.jobstreet.com/jobs?keywords=inventory"

    def find_elements(self, by, selector):
        return []


@pytest.fixture
def bot():
    bot = JobStreetBot()
    bot.driver = FakeDriver()
    return bot


def test_kartu_berlabel_applied_terdeteksi(bot):
    job = bot._parse_job_card(FakeCard(applied=True))

    assert job is not None
    assert job["applied"] is True


def test_kartu_biasa_tidak_dianggap_applied(bot):
    job = bot._parse_job_card(FakeCard(applied=False))

    assert job is not None
    assert job["applied"] is False


def test_kartu_dengan_teks_you_applied(bot):
    kartu = FakeCard(text="Inventory Control\nPT Contoh\nYou applied")

    assert bot._card_is_applied(kartu) is True


def test_badge_tersembunyi_tidak_dihitung(bot):
    class KartuBadgeTersembunyi(FakeCard):
        def find_elements(self, by, selector):
            if "applied" in selector:
                return [FakeElement(visible=False)]
            return super().find_elements(by, selector)

    kartu = KartuBadgeTersembunyi(text="Inventory Control\nPT Contoh")
    assert bot._card_is_applied(kartu) is False


# ----------------------------------------------------------------------
# main: lowongan applied dilewati tanpa ditampilkan / tanpa apply
# ----------------------------------------------------------------------
@pytest.fixture
def database(tmp_path, monkeypatch):
    db = Database(str(tmp_path / "applied.db"))
    monkeypatch.setattr(main_module, "db", db)
    monkeypatch.setattr(job_filter_module, "db", db)
    monkeypatch.setattr(config, "locations", ["Bandung"])
    monkeypatch.setattr(config, "keywords", ["inventory control"])
    monkeypatch.setattr(config, "max_pages", 1)
    monkeypatch.setattr(config, "delay_between_apply", 0)
    monkeypatch.setattr(config, "auto_apply", True)
    monkeypatch.setattr(config, "auto_apply_max_per_session", 25)
    monkeypatch.setattr(config, "strict_location", False)
    monkeypatch.setattr(config, "max_age_days", 0)
    monkeypatch.setattr(config, "min_salary", 0)
    monkeypatch.setattr(config, "max_experience", 5)
    return db


def job(job_id, applied=False):
    return {
        "job_id": job_id,
        "title": f"Inventory Control {job_id}",
        "company": "PT Contoh",
        "location": "Bandung",
        "salary": "Rp 8.000.000",
        "description": "",
        "url": f"https://id.jobstreet.com/job/{job_id}",
        "date_posted": "Hari ini",
        "age_days": 0,
        "applied": applied,
    }


def test_lowongan_applied_tidak_dilamar_ulang(database):
    class FakeBot:
        def __init__(self):
            self.diajukan = []

        def init_browser(self):
            pass

        def login(self):
            return True

        def search_jobs(self, keyword, page=1, location=None):
            if page > 1:
                return []
            return [job("1", applied=True), job("2")]

        def apply_job(self, lowongan):
            self.diajukan.append(lowongan["job_id"])
            database.record_application(lowongan["job_id"], "applied", "uji")
            return ApplyResult(True, "applied", "uji")

        def close(self):
            pass

    engine = main_module.AutoApplyEngine()
    engine.bot = FakeBot()
    engine.run()

    assert engine.session_stats["already"] == 1
    assert engine.session_stats["applied"] == 1
    assert engine.bot.diajukan == ["2"]
    assert database.get_today_apply_count() == 1


def test_lowongan_applied_tetap_dilewati_di_sesi_berikutnya(database):
    class FakeBot:
        def __init__(self):
            self.diajukan = []

        def init_browser(self):
            pass

        def login(self):
            return True

        def search_jobs(self, keyword, page=1, location=None):
            if page > 1:
                return []
            return [job("1")]

        def apply_job(self, lowongan):
            self.diajukan.append(lowongan["job_id"])
            database.record_application(lowongan["job_id"], "applied", "uji")
            return ApplyResult(True, "applied", "uji")

        def close(self):
            pass

    pertama = main_module.AutoApplyEngine()
    pertama.bot = FakeBot()
    pertama.run()
    assert pertama.session_stats["applied"] == 1

    kedua = main_module.AutoApplyEngine()
    kedua.bot = FakeBot()
    kedua.run()

    assert kedua.session_stats["already"] == 1
    assert kedua.bot.diajukan == []
    assert database.get_today_apply_count() == 1
