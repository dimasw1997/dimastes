import pytest

import buka_pencarian
import job_filter as job_filter_module
import scraper
from config import config
from database import Database
from job_filter import JobFilter

LOKASI = [
    "Bandung",
    "Jakarta",
    "Tangerang",
    "Jababeka",
    "Cimahi",
    "Purwakarta",
    "Bogor",
]


@pytest.fixture
def filter_multi(tmp_path, monkeypatch):
    monkeypatch.setattr(
        job_filter_module, "db", Database(str(tmp_path / "lokasi.db"))
    )
    monkeypatch.setattr(config, "strict_location", True)
    monkeypatch.setattr(config, "allow_remote", False)
    monkeypatch.setattr(config, "locations", list(LOKASI))
    return JobFilter()


def make_job(location: str) -> dict:
    return {
        "job_id": "abc",
        "title": "Inventory Control",
        "company": "PT Contoh",
        "location": location,
        "salary": "Rp 8.000.000",
        "description": "",
        "url": "https://id.jobstreet.com/job/abc",
        "date_posted": "Hari ini",
    }


@pytest.mark.parametrize(
    "location",
    [
        "Bandung, West Java",
        "Jakarta Selatan",
        "Tangerang, Banten",
        "Tangerang Selatan",
        "Cikarang, West Java",  # Jababeka
        "Cimahi, West Java",
        "Purwakarta, West Java",
        "Bogor, West Java",
        "",
    ],
)
def test_lokasi_diterima(filter_multi, location):
    lolos, alasan = filter_multi.should_apply(make_job(location))
    assert lolos is True, alasan


@pytest.mark.parametrize(
    "location",
    ["Surabaya, East Java", "Denpasar, Bali", "Medan, North Sumatra"],
)
def test_lokasi_ditolak(filter_multi, location):
    lolos, alasan = filter_multi.should_apply(make_job(location))
    assert lolos is False
    assert "lokasi" in alasan.lower()


def test_lokasi_daftar_bisa_diubah(filter_multi, monkeypatch):
    monkeypatch.setattr(config, "locations", ["Surabaya"])

    assert filter_multi.should_apply(make_job("Surabaya, East Java"))[0] is True
    assert filter_multi.should_apply(make_job("Bandung, West Java"))[0] is False


def test_remote_mengikuti_setting(filter_multi, monkeypatch):
    assert filter_multi.should_apply(make_job("Remote"))[0] is False

    monkeypatch.setattr(config, "allow_remote", True)
    assert filter_multi.should_apply(make_job("Remote"))[0] is True


class FakeDriver:
    def __init__(self):
        self.opened_urls = []

    def get(self, url):
        self.opened_urls.append(url)

    def find_elements(self, by, selector):
        return []


class FakeWait:
    def until(self, condition):
        return True


def test_pencarian_memakai_lokasi_tertentu(monkeypatch):
    monkeypatch.setattr(scraper.time, "sleep", lambda *_: None)
    monkeypatch.setattr(config, "sort_mode", "ListedDate")
    monkeypatch.setattr(config, "max_age_days", 0)

    driver = FakeDriver()
    bot = scraper.JobStreetBot()
    bot.driver = driver
    bot.wait = FakeWait()

    bot.search_jobs("PPIC", page=1, location="Jakarta")

    assert "where=Jakarta" in driver.opened_urls[0]


def test_buka_pencarian_semua_lokasi(monkeypatch):
    dibuka = []
    monkeypatch.setattr(
        buka_pencarian.webbrowser,
        "open_new_tab",
        lambda url: dibuka.append(url),
    )
    monkeypatch.setattr(config, "sort_mode", "ListedDate")

    jumlah = buka_pencarian.buka_pencarian(
        locations=["Bandung", "Jakarta"],
        keywords=["PPIC", "inventory control"],
        delay=0,
        max_tabs=10,
    )

    assert jumlah == 4
    assert "where=Bandung" in dibuka[0]
    assert "where=Jakarta" in dibuka[2]
    assert "sortmode=ListedDate" in dibuka[0]


def test_buka_pencarian_menghormati_batas_tab(monkeypatch):
    dibuka = []
    monkeypatch.setattr(
        buka_pencarian.webbrowser,
        "open_new_tab",
        lambda url: dibuka.append(url),
    )

    jumlah = buka_pencarian.buka_pencarian(
        locations=["Bandung", "Jakarta"],
        keywords=["PPIC", "inventory control"],
        delay=0,
        max_tabs=3,
    )

    assert jumlah == 3
    assert len(dibuka) == 3
