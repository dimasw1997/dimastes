"""Simulasi alur lamaran tanpa Chrome dan tanpa internet.

Menjalankan beberapa skenario halaman JobStreet palsu terhadap mesin
AutoApplier, supaya perilaku "kirim / lewati" bisa diperiksa kapan saja:

    python cli.py simulasi

Semua langkah memakai jam tiruan, jadi selesai dalam hitungan detik.
"""

import types

from rich.console import Console
from rich.table import Table

import auto_apply
from auto_apply import APPLY_SELECTORS, AutoApplier
from config import config

console = Console()

URL_LOWONGAN = "https://id.jobstreet.com/job/95629793"
URL_REVIEW = "https://id.jobstreet.com/job/95629793/apply/review"
SUKSES = "Lamaran Anda telah dikirim"


class Elemen:
    def __init__(
        self,
        text="",
        attrs=None,
        visible=True,
        enabled=True,
        options=None,
        parent=None,
        on_click=None,
    ):
        self.text = text
        self.attrs = attrs or {}
        self.visible = visible
        self.enabled = enabled
        self.options = options or []
        self.parent = parent
        self.on_click = on_click

    def is_displayed(self):
        return self.visible

    def is_enabled(self):
        return self.enabled

    def is_selected(self):
        return False

    def get_attribute(self, nama):
        return self.attrs.get(nama)

    def click(self):
        if self.on_click:
            self.on_click()

    def send_keys(self, nilai):
        self.attrs["value"] = nilai
        self.text = str(nilai)

    def find_elements(self, by, selector):
        if selector == "option":
            return list(self.options)
        return []

    def find_element(self, by, selector):
        if selector == ".." and self.parent is not None:
            return self.parent
        raise LookupError(selector)


class Chrome:
    def __init__(self, elements=None, body="", url=URL_LOWONGAN):
        self.elements = elements or {}
        self.body = body
        self.current_url = url
        self.window_handles = ["utama"]
        self.switch_to = self
        self.klik_lanjut = 0

    def get(self, url):
        self.current_url = url

    def find_elements(self, by, selector):
        return list(self.elements.get(selector, []))

    def find_element(self, by, selector):
        if selector == "body":
            return Elemen(text=self.body)
        raise LookupError(selector)

    def execute_script(self, *args, **kwargs):
        return None

    def window(self, handle):
        return None

    def close(self):
        return None

    def save_screenshot(self, path):
        return None

    @property
    def page_source(self):
        return ""


class PilihanPalsu:
    """Pengganti selenium Select."""

    def __init__(self, element):
        self.element = element

    def select_by_visible_text(self, teks):
        daftar = [item.text for item in self.element.options]
        if teks not in daftar:
            raise ValueError(teks)
        self.element.attrs["value"] = teks


class Jam:
    """Jam tiruan supaya simulasi tidak menunggu detik sungguhan."""

    def __init__(self):
        self.sekarang = 100.0

    def time(self):
        return self.sekarang

    def sleep(self, detik=0):
        self.sekarang += detik

    @staticmethod
    def strftime(format):
        return "simulasi"


def _select(pertanyaan, opsi):
    element = Elemen(attrs={"aria-label": pertanyaan, "value": ""})
    element.options = [Elemen(text=teks) for teks in opsi]
    return element


def _siapkan():
    """Pasang jam tiruan + Select palsu, kembalikan fungsi pemulih."""
    jam = Jam()
    asli = (auto_apply.time, auto_apply.Select)
    auto_apply.time = types.SimpleNamespace(
        time=jam.time, sleep=jam.sleep, strftime=Jam.strftime
    )
    auto_apply.Select = PilihanPalsu
    return lambda: (
        setattr(auto_apply, "time", asli[0]),
        setattr(auto_apply, "Select", asli[1]),
    )


def _hasil(driver):
    return AutoApplier(driver).apply({"url": URL_LOWONGAN, "title": "uji"})


def skenario_lamaran_sederhana():
    """Tombol Lamar → konfirmasi langsung."""
    driver = Chrome()

    def kirim():
        driver.body = SUKSES

    driver.elements = {
        APPLY_SELECTORS[0]: [Elemen(text="Lamar", on_click=kirim)]
    }
    return _hasil(driver), ("applied", True), driver


def skenario_pertanyaan_pilihan():
    """Dropdown gaji/pengalaman/pendidikan wajib diisi dulu."""
    driver = Chrome()
    gaji = _select("Berapa gaji bulanan yang kamu inginkan?",
                   ["Rp 4 Jt", "Rp 5 Jt", "Rp 6 Jt"])
    pengalaman = _select(
        "How many years' experience do you have as an Inventory Controller?",
        ["0 years", "2 years", "3 years"],
    )
    kepala = _select("Berapa tahun pengalaman kerjamu sebagai Kepala PPIC?",
                     ["0 years", "1 year", "2 years"])
    kualifikasi = _select("Kualifikasi mana yang kamu miliki?",
                          ["SMA", "Sarjana (S1)", "Master (S2)"])
    pilihan = [gaji, pengalaman, kepala, kualifikasi]

    def lanjut():
        driver.klik_lanjut += 1
        kosong = [p for p in pilihan if not (p.get_attribute("value") or "")]
        if kosong:
            driver.body = (
                "Before you can continue with the application, please "
                "address the following issues: Berapa tahun pengalaman "
                "kerjamu sebagai Kepala PPIC? - Please make a selection"
            )
        else:
            driver.body = SUKSES

    driver.elements = {
        APPLY_SELECTORS[0]: [Elemen(text="Lamar")],
        "select": pilihan,
        "button": [Elemen(text="Continue", on_click=lanjut)],
    }
    hasil = _hasil(driver)
    jawaban = [p.get_attribute("value") for p in pilihan]
    return hasil, ("applied", True, jawaban), driver


def skenario_halaman_review():
    """Langkah terakhir "Review and submit" harus dikirim, bukan dilewati."""
    driver = Chrome()

    def ke_review():
        driver.current_url = URL_REVIEW
        driver.elements["button[type='submit']"] = [
            Elemen(text="Kirim lamaran", on_click=lambda: setattr(
                driver, "body", SUKSES
            ))
        ]

    driver.elements = {
        APPLY_SELECTORS[0]: [Elemen(text="Lamar", on_click=ke_review)]
    }
    return _hasil(driver), ("applied", True), driver


def skenario_situs_lain():
    """Lamaran dialihkan ke ATS perusahaan → dilewati."""
    driver = Chrome()

    def ke_workday():
        driver.current_url = "https://jobs.workday.com/apply/123"

    driver.elements = {
        APPLY_SELECTORS[0]: [Elemen(text="Lamar", on_click=ke_workday)]
    }
    return _hasil(driver), ("manual_required", "situs lain"), driver


def skenario_pertanyaan_asing():
    """Pertanyaan yang tidak dikenal tidak ditebak, dan tidak klik berulang."""
    driver = Chrome(body=(
        "Before you can continue with the application, please address the "
        "following issues: Warna favorit kamu? - Please make a selection"
    ))
    aneh = _select("Warna favorit kamu?", ["Merah", "Biru"])

    def lanjut():
        driver.klik_lanjut += 1

    driver.elements = {
        APPLY_SELECTORS[0]: [Elemen(text="Lamar")],
        "select": [aneh],
        "button": [Elemen(text="Continue", on_click=lanjut)],
    }
    return _hasil(driver), ("manual_required", "dijawab otomatis"), driver


def skenario_tak_dikenali():
    """Tidak ada tombol apa pun → dilewati setelah batas waktu langkah."""
    driver = Chrome()
    driver.elements = {APPLY_SELECTORS[0]: [Elemen(text="Lamar")]}
    return _hasil(driver), ("manual_required", "tidak dikenali"), driver


SKENARIO = (
    ("Lamaran sederhana", skenario_lamaran_sederhana),
    ("Pertanyaan pilihan dijawab", skenario_pertanyaan_pilihan),
    ("Review and submit dikirim", skenario_halaman_review),
    ("Dialihkan ke situs lain", skenario_situs_lain),
    ("Pertanyaan asing dilewati", skenario_pertanyaan_asing),
    ("Alur tak dikenali dilewati", skenario_tak_dikenali),
)


def _cocok(hasil, harapan) -> bool:
    if hasil.status != harapan[0]:
        return False
    if len(harapan) > 1 and isinstance(harapan[1], bool):
        return hasil.applied is harapan[1]
    if len(harapan) > 1:
        return harapan[1].lower() in (hasil.reason or "").lower()
    return True


def jalankan() -> bool:
    """Jalankan semua skenario. True bila semuanya sesuai harapan."""
    pulihkan = _siapkan()
    hasil_lama = (
        config.auto_answer_questions,
        config.expected_salary,
        config.years_experience,
        config.education_level,
        config.auto_apply_debug,
    )
    config.auto_answer_questions = True
    config.expected_salary = "5000000"
    config.years_experience = 3.0
    config.education_level = "S1"
    config.auto_apply_debug = False

    table = Table(title="Simulasi alur lamaran")
    table.add_column("Skenario", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Hasil", overflow="fold")
    table.add_column("Cek", justify="center")

    semua_ok = True

    try:
        for nama, fungsi in SKENARIO:
            hasil, harapan, driver = fungsi()
            ok = _cocok(hasil, harapan)
            semua_ok = semua_ok and ok

            if nama == "Pertanyaan pilihan dijawab":
                jawaban = harapan[2] if len(harapan) > 2 else []
                if jawaban != ["Rp 5 Jt", "3 years", "0 years", "Sarjana (S1)"]:
                    ok = False
                    semua_ok = False

            if nama == "Pertanyaan asing dilewati" and driver.klik_lanjut > 2:
                ok = False
                semua_ok = False

            table.add_row(
                nama,
                hasil.status,
                hasil.reason[:70],
                "[green]OK[/]" if ok else "[red]GAGAL[/]",
            )
    finally:
        pulihkan()
        (
            config.auto_answer_questions,
            config.expected_salary,
            config.years_experience,
            config.education_level,
            config.auto_apply_debug,
        ) = hasil_lama

    console.print(table)

    if semua_ok:
        console.print(
            "[bold green]Semua skenario sesuai harapan.[/] "
            "[dim]Ini simulasi offline; uji sungguhan tetap di Chrome.[/]"
        )
    else:
        console.print("[bold red]Ada skenario yang tidak sesuai.[/]")

    return semua_ok
