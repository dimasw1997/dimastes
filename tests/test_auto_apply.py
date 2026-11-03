import pytest
from selenium.common.exceptions import NoSuchElementException

import auto_apply
import scraper
from auto_apply import APPLY_SELECTORS, SUBMIT_SELECTORS, AutoApplier
from config import config


class FakeElement:
    def __init__(
        self,
        text="",
        attrs=None,
        visible=True,
        enabled=True,
        selected=False,
        on_click=None,
    ):
        self.text = text
        self._attrs = attrs or {}
        self._visible = visible
        self._enabled = enabled
        self._selected = selected
        self._on_click = on_click

    def is_displayed(self):
        return self._visible

    def is_enabled(self):
        return self._enabled

    def is_selected(self):
        return self._selected

    def get_attribute(self, name):
        return self._attrs.get(name)

    def click(self):
        if self._on_click:
            self._on_click()

    def send_keys(self, value):
        self._attrs["value"] = value
        self.text = str(value)


class FakeDriver:
    def __init__(self, elements=None, body="", url="https://id.jobstreet.com/job/1"):
        self.elements = elements or {}
        self.body = body
        self.current_url = url
        self.window_handles = ["main"]
        self.switch_to = self
        self.opened_urls = []

    def get(self, url):
        self.opened_urls.append(url)
        self.current_url = url

    def find_elements(self, by, selector):
        return list(self.elements.get(selector, []))

    def find_element(self, by, selector):
        if selector == "body":
            return FakeElement(text=self.body)
        raise NoSuchElementException(selector)

    def execute_script(self, *args, **kwargs):
        return None

    def window(self, handle):
        return None

    def close(self):
        return None


class FakeWait:
    def until(self, condition):
        return True


@pytest.fixture(autouse=True)
def tanpa_jeda(monkeypatch):
    monkeypatch.setattr(auto_apply.time, "sleep", lambda *_: None)
    monkeypatch.setattr(scraper.time, "sleep", lambda *_: None)


def tombol_apply(driver, teks_sukses="Lamaran Anda telah dikirim"):
    def klik():
        driver.body = teks_sukses

    return FakeElement(text="Lamar", on_click=klik)


# ----------------------------------------------------------------------
# Umur lowongan
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "label, expected",
    [
        ("Hari ini", 0),
        ("Baru", 0),
        ("Kemarin", 1),
        ("3 hari yang lalu", 3),
        ("30+ hari yang lalu", 30),
        ("2 minggu yang lalu", 14),
        ("1 bulan yang lalu", 30),
        ("", None),
        ("tanpa tanggal", None),
    ],
)
def test_parse_listing_age(label, expected):
    assert scraper.JobStreetBot._parse_listing_age(label) == expected


def test_search_memakai_urutan_terbaru(monkeypatch):
    monkeypatch.setattr(config, "location", "Bandung")
    monkeypatch.setattr(config, "sort_mode", "ListedDate")
    monkeypatch.setattr(config, "max_age_days", 7)

    driver = FakeDriver()
    bot = scraper.JobStreetBot()
    bot.driver = driver
    bot.wait = FakeWait()

    bot.search_jobs("PPIC", page=2)

    url = driver.opened_urls[0]
    assert "sortmode=ListedDate" in url
    assert "daterange=7" in url
    assert "where=Bandung" in url
    assert "page=2" in url


# ----------------------------------------------------------------------
# Auto apply
# ----------------------------------------------------------------------
def test_auto_apply_sukses():
    driver = FakeDriver()
    driver.elements = {APPLY_SELECTORS[0]: [tombol_apply(driver)]}

    hasil = AutoApplier(driver).apply({"url": driver.current_url})

    assert hasil.applied is True
    assert hasil.status == "applied"


def test_auto_apply_tombol_tidak_ada(monkeypatch):
    monkeypatch.setattr(config, "auto_apply_step_timeout", 0)

    hasil = AutoApplier(FakeDriver()).apply({"url": "https://id.jobstreet.com/job/1"})

    assert hasil.applied is False
    assert hasil.status == "manual_required"
    assert "tidak ditemukan" in hasil.reason.lower()


def test_auto_apply_berhenti_bila_perlu_unggah_berkas():
    driver = FakeDriver()
    driver.elements = {
        APPLY_SELECTORS[0]: [tombol_apply(driver, teks_sukses="")],
        "input[type='file']": [FakeElement(attrs={"value": ""})],
    }

    hasil = AutoApplier(driver).apply({"url": "https://id.jobstreet.com/job/1"})

    assert hasil.applied is False
    assert hasil.status == "manual_required"
    assert "unggah" in hasil.reason.lower()


def test_auto_apply_klik_kirim_lamaran():
    driver = FakeDriver()

    def klik_kirim():
        driver.body = "Terima kasih telah melamar"

    driver.elements = {
        APPLY_SELECTORS[0]: [tombol_apply(driver, teks_sukses="")],
        SUBMIT_SELECTORS[0]: [
            FakeElement(text="Kirim lamaran", on_click=klik_kirim)
        ],
    }

    hasil = AutoApplier(driver).apply({"url": "https://id.jobstreet.com/job/1"})

    assert hasil.applied is True
    assert hasil.status == "applied"


def test_auto_apply_sudah_dilamar():
    driver = FakeDriver(body="Anda sudah melamar lowongan ini")

    hasil = AutoApplier(driver).apply({"url": "https://id.jobstreet.com/job/1"})

    assert hasil.applied is False
    assert hasil.status == "already_applied"


def test_auto_apply_lamar_di_situs_perusahaan():
    driver = FakeDriver()
    driver.elements = {
        "button": [FakeElement(text="Lamar di situs perusahaan")],
    }

    hasil = AutoApplier(driver).apply({"url": "https://id.jobstreet.com/job/1"})

    assert hasil.applied is False
    assert hasil.status == "manual_required"
    assert "situs perusahaan" in hasil.reason.lower()


def test_auto_apply_tab_eksternal():
    driver = FakeDriver()

    def buka_tab_luar():
        driver.window_handles = ["main", "luar"]
        driver.current_url = "https://karier.contoh.com/apply/123"

    driver.elements = {
        APPLY_SELECTORS[0]: [
            FakeElement(text="Lamar", on_click=buka_tab_luar)
        ],
    }

    hasil = AutoApplier(driver).apply({"url": "https://id.jobstreet.com/job/1"})

    assert hasil.applied is False
    assert hasil.status == "manual_required"
    assert "situs perusahaan" in hasil.reason.lower()


def test_auto_apply_berhenti_bila_halaman_login():
    driver = FakeDriver()
    driver.elements = {"input[type='password']": [FakeElement()]}

    hasil = AutoApplier(driver).apply({"url": "https://id.jobstreet.com/job/1"})

    assert hasil.applied is False
    assert hasil.status == "login_required"
    assert "login" in hasil.reason.lower()


def test_auto_apply_berhenti_bila_dialihkan_ke_signin():
    class DriverDialihkan(FakeDriver):
        def get(self, url):
            self.current_url = "https://id.jobstreet.com/signin?redirect=job"

    hasil = AutoApplier(DriverDialihkan()).apply(
        {"url": "https://id.jobstreet.com/job/1"}
    )

    assert hasil.status == "login_required"


def test_auto_apply_isi_cover_letter_otomatis(monkeypatch):
    monkeypatch.setattr(config, "cover_letter", "Saya siap bergabung.")
    monkeypatch.setattr(config, "resume_path", "")

    driver = FakeDriver()

    def klik_kirim():
        driver.body = "Lamaran Anda telah dikirim"

    textarea = FakeElement(attrs={"value": "", "required": "true"})
    driver.elements = {
        APPLY_SELECTORS[0]: [tombol_apply(driver, teks_sukses="")],
        "textarea": [textarea],
        SUBMIT_SELECTORS[0]: [
            FakeElement(text="Kirim lamaran", on_click=klik_kirim)
        ],
    }

    hasil = AutoApplier(driver).apply({"url": "https://id.jobstreet.com/job/1"})

    assert hasil.applied is True
    assert textarea.get_attribute("value") == "Saya siap bergabung."


def test_auto_apply_unggah_cv_otomatis(monkeypatch, tmp_path):
    cv = tmp_path / "cv.pdf"
    cv.write_text("contoh", encoding="utf-8")

    monkeypatch.setattr(config, "cover_letter", "")
    monkeypatch.setattr(config, "resume_path", str(cv))

    driver = FakeDriver()

    def klik_kirim():
        driver.body = "Application submitted"

    berkas = FakeElement(attrs={"value": ""})
    driver.elements = {
        APPLY_SELECTORS[0]: [tombol_apply(driver, teks_sukses="")],
        "input[type='file']": [berkas],
        SUBMIT_SELECTORS[0]: [
            FakeElement(text="Kirim lamaran", on_click=klik_kirim)
        ],
    }

    hasil = AutoApplier(driver).apply({"url": "https://id.jobstreet.com/job/1"})

    assert hasil.applied is True
    assert berkas.get_attribute("value") == str(cv)


def test_auto_apply_tanpa_konfigurasi_tetap_berhenti_aman(monkeypatch):
    monkeypatch.setattr(config, "cover_letter", "")
    monkeypatch.setattr(config, "resume_path", "")

    driver = FakeDriver()
    driver.elements = {
        APPLY_SELECTORS[0]: [tombol_apply(driver, teks_sukses="")],
        "input[type='file']": [FakeElement(attrs={"value": ""})],
    }

    hasil = AutoApplier(driver).apply({"url": "https://id.jobstreet.com/job/1"})

    assert hasil.applied is False
    assert hasil.status == "manual_required"
    assert "RESUME_PATH" in hasil.reason


def test_auto_apply_lewati_setelah_batas_waktu(monkeypatch):
    """Alur tidak dikenali dalam 3 detik -> dilewati, lanjut lowongan berikutnya."""
    monkeypatch.setattr(config, "auto_apply_step_timeout", 3)

    jam = {"t": 100.0}
    monkeypatch.setattr(auto_apply.time, "time", lambda: jam["t"])
    monkeypatch.setattr(
        auto_apply.time,
        "sleep",
        lambda detik=0: jam.__setitem__("t", jam["t"] + detik),
    )

    driver = FakeDriver()
    driver.elements = {APPLY_SELECTORS[0]: [FakeElement(text="Lamar")]}

    hasil = AutoApplier(driver).apply({"url": "https://id.jobstreet.com/job/1"})

    assert hasil.applied is False
    assert hasil.status == "manual_required"
    assert "3 detik" in hasil.reason
