import pytest

import scraper
from config import config


class FakeElement:
    def __init__(self, visible=True):
        self._visible = visible

    def is_displayed(self):
        return self._visible


class FakeDriver:
    def __init__(self, elements=None):
        self.elements = elements or {}
        self.opened_urls = []

    def get(self, url):
        self.opened_urls.append(url)

    def find_elements(self, by, selector):
        return list(self.elements.get(selector, []))

    def find_element(self, by, selector):
        return FakeElement()


@pytest.fixture(autouse=True)
def tanpa_jeda(monkeypatch):
    monkeypatch.setattr(scraper.time, "sleep", lambda *_: None)


def buat_bot(elements):
    bot = scraper.JobStreetBot()
    bot.driver = FakeDriver(elements)
    return bot


def test_status_login_terdeteksi_belum_login():
    bot = buat_bot({"a[data-automation='signIn']": [FakeElement()]})
    assert bot._login_status() is False


def test_status_login_terdeteksi_sudah_login():
    bot = buat_bot({"[data-automation='accountMenu']": [FakeElement()]})
    assert bot._login_status() is True


def test_status_login_tidak_pasti():
    bot = buat_bot({})
    assert bot._login_status() is None


def test_login_langsung_lanjut_bila_sesi_tersimpan(monkeypatch):
    bot = buat_bot({"a[href*='/profile']": [FakeElement()]})

    def jangan_tanya(*args, **kwargs):
        raise AssertionError("input() tidak boleh dipanggil saat sudah login")

    monkeypatch.setattr("builtins.input", jangan_tanya)

    assert bot.login() is True


def test_login_berhenti_tanpa_menunggu_bila_belum_login(monkeypatch):
    monkeypatch.setattr(config, "login_wait", False)
    bot = buat_bot({"a[data-automation='signIn']": [FakeElement()]})

    def jangan_tanya(*args, **kwargs):
        raise AssertionError("input() tidak boleh dipanggil")

    monkeypatch.setattr("builtins.input", jangan_tanya)

    assert bot.login() is False


def test_login_menunggu_enter_bila_belum_login(monkeypatch):
    monkeypatch.setattr(config, "login_wait", True)
    bot = buat_bot({"a[data-automation='signIn']": [FakeElement()]})
    dipanggil = {"jumlah": 0}

    def jawab(*args, **kwargs):
        dipanggil["jumlah"] += 1
        return ""

    monkeypatch.setattr("builtins.input", jawab)

    assert bot.login() is True
    assert dipanggil["jumlah"] == 1
