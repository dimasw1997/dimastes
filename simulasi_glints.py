"""Simulasi alur lamaran Glints tanpa Chrome dan tanpa internet.

Menjalankan beberapa bentuk halaman/modal Glints terhadap mesin pelamar yang
sama dengan yang dipakai `cli.py glints run`, supaya perilaku "kirim / lewati"
bisa diperiksa kapan saja:

    python cli.py glints simulasi

Bentuk modal yang disimulasikan mengikuti alur Glints: klik **Lamar**, lalu
modal berisi CV/surat lamaran dan tombol **Lamar Sekarang**. Semua langkah
memakai jam tiruan, jadi selesai dalam hitungan detik.
"""

import tempfile
from pathlib import Path

from rich.console import Console
from rich.table import Table

from config import config
from glints import GlintsApplier
from simulasi import Chrome, Elemen, _siapkan

console = Console()

URL_GLINTS = (
    "https://glints.com/id/opportunities/jobs/admin-warehouse/"
    "b5f8d754-afd9-4f0c-a618-360afe12248c"
)
SUKSES = "Lamaran berhasil dikirim"


def _lamar(driver):
    return GlintsApplier(driver).apply({"url": URL_GLINTS, "title": "uji"})


class ChromeGlints(Chrome):
    """Chrome palsu dengan dukungan refresh() untuk galat server Glints."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("url", URL_GLINTS)
        super().__init__(*args, **kwargs)
        self.refresh_dipanggil = 0

    def refresh(self):
        self.refresh_dipanggil += 1
        self.body = "Review and submit"
        self.elements.pop("[role='dialog']", None)


# ----------------------------------------------------------------------
# Skenario
# ----------------------------------------------------------------------
def skenario_modal_berhasil():
    """Klik Lamar → modal → tombol "Lamar Sekarang" → terkirim."""
    driver = ChromeGlints(body="Admin Warehouse Rp 5-6jt Penuh Waktu")

    def kirim():
        driver.body = SUKSES

    def buka_modal():
        driver.elements["[role='dialog']"] = [
            Elemen(text="Lamar pekerjaan ini\nCV terpilih: cv.pdf")
        ]
        driver.elements["button"] = [
            Elemen(text="Lamar Sekarang", on_click=kirim)
        ]

    driver.elements = {"button": [Elemen(text="Lamar", on_click=buka_modal)]}
    return _lamar(driver), ("applied", True), driver


def skenario_modal_dengan_cover_letter():
    """Modal Glints berisi surat lamaran; COVER_LETTER diisi otomatis."""
    driver = ChromeGlints(body="Admin Warehouse Rp 5-6jt")

    kotak = Elemen(attrs={"value": ""})

    def kirim():
        driver.body = SUKSES

    def buka_modal():
        driver.elements["textarea"] = [kotak]
        driver.elements["[role='dialog']"] = [Elemen(text="Lamar pekerjaan")]
        driver.elements["button"] = [
            Elemen(text="Lamar Sekarang", on_click=kirim)
        ]

    driver.elements = {"button": [Elemen(text="Lamar", on_click=buka_modal)]}
    hasil = _lamar(driver)
    terisi = bool(kotak.get_attribute("value"))
    return hasil, ("applied", True, terisi), driver


def skenario_hanya_aplikasi():
    """Lowongan "Lamar 1x tap di aplikasi" tidak dibuka lebih jauh."""
    driver = ChromeGlints(body="Lamar 1x tap di aplikasi")
    driver.elements = {
        "button": [Elemen(text="Lamar 1x tap di aplikasi")],
    }
    return _lamar(driver), ("manual_required", "aplikasi mobile"), driver


def skenario_profil_belum_lengkap():
    """Modal meminta melengkapi profil → dilewati dengan alasan jelas."""
    driver = ChromeGlints(body="Admin Warehouse Rp 5-6jt")

    def buka_modal():
        driver.body = "Lengkapi profil kamu dulu untuk melamar pekerjaan ini"

    driver.elements = {"button": [Elemen(text="Lamar", on_click=buka_modal)]}
    return _lamar(driver), ("manual_required", "profil"), driver


def skenario_sudah_pernah_melamar():
    """Halaman menandai sudah pernah melamar → tidak dikirim ulang."""
    driver = ChromeGlints(body="Kamu sudah melamar lowongan ini")
    return _lamar(driver), ("already_applied", "sudah"), driver


def skenario_galat_server_lalu_berhasil():
    """Galat server JobStreet/Glints: muat ulang sekali, lalu berhasil."""
    driver = ChromeGlints(body="Admin Warehouse Rp 5-6jt")
    jumlah = {"klik": 0}

    def kirim():
        jumlah["klik"] += 1
        if jumlah["klik"] == 1:
            driver.body = (
                "Something has gone wrong. Please try again or contact "
                "Customer Service"
            )
        else:
            driver.body = SUKSES

    def buka_modal():
        driver.elements["button"] = [
            Elemen(text="Lamar Sekarang", on_click=kirim)
        ]

    driver.elements = {"button": [Elemen(text="Lamar", on_click=buka_modal)]}
    hasil = _lamar(driver)
    harapan = ("applied", True, jumlah["klik"] == 2)
    return hasil, harapan, driver


def skenario_modal_minta_cv():
    """Modal mewajibkan unggah CV; RESUME_PATH dipakai otomatis."""
    berkas = Path(tempfile.gettempdir()) / "cv-simulasi.pdf"
    berkas.write_text("contoh", encoding="utf-8")

    lama = config.resume_path
    config.resume_path = str(berkas)

    driver = ChromeGlints(body="Admin Warehouse Rp 5-6jt")
    unggah = Elemen(attrs={"required": "", "value": ""})

    def kirim():
        driver.body = SUKSES

    def buka_modal():
        driver.elements["input[type='file']"] = [unggah]
        driver.elements["button"] = [
            Elemen(text="Lamar Sekarang", on_click=kirim)
        ]

    driver.elements = {"button": [Elemen(text="Lamar", on_click=buka_modal)]}
    hasil = _lamar(driver)
    config.resume_path = lama

    terisi = bool(unggah.get_attribute("value"))
    return hasil, ("applied", True, terisi), driver


SKENARIO = (
    ("Lamar → modal → Lamar Sekarang", skenario_modal_berhasil),
    ("Surat lamaran diisi otomatis", skenario_modal_dengan_cover_letter),
    ("Hanya bisa dilamar via aplikasi", skenario_hanya_aplikasi),
    ("Profil belum lengkap", skenario_profil_belum_lengkap),
    ("Sudah pernah melamar", skenario_sudah_pernah_melamar),
    ("Galat server lalu berhasil", skenario_galat_server_lalu_berhasil),
    ("Modal mewajibkan CV", skenario_modal_minta_cv),
)


def _cocok(hasil, harapan) -> bool:
    status = harapan[0]
    if hasil.status != status:
        return False

    if hasil.applied is not (status == "applied"):
        return False

    if (
        len(harapan) > 1
        and isinstance(harapan[1], str)
        and harapan[1] not in hasil.reason.lower()
    ):
        return False

    return not (len(harapan) > 2 and isinstance(harapan[2], bool)
                and harapan[2] is not True)

    return True


def jalankan() -> bool:
    """Jalankan semua skenario Glints dan cetak tabel hasilnya."""
    pulihkan = _siapkan()

    lama = (
        config.cover_letter,
        config.auto_apply_debug,
    )
    config.cover_letter = "Saya tertarik dengan posisi ini."
    config.auto_apply_debug = False

    table = Table(title="Simulasi alur lamaran Glints")
    table.add_column("Skenario", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Hasil", overflow="fold")
    table.add_column("Cek", justify="center")

    semua_ok = True

    try:
        for nama, fungsi in SKENARIO:
            hasil, harapan, _ = fungsi()
            ok = _cocok(hasil, harapan)
            semua_ok = semua_ok and ok

            table.add_row(
                nama,
                hasil.status,
                hasil.reason[:70],
                "[green]OK[/]" if ok else "[red]GAGAL[/]",
            )
    finally:
        pulihkan()
        config.cover_letter, config.auto_apply_debug = lama

    console.print(table)

    if semua_ok:
        console.print(
            "[bold green]Semua skenario Glints sesuai harapan.[/] "
            "[dim]Ini simulasi offline; uji sungguhan tetap di Chrome.[/]"
        )
    else:
        console.print("[bold red]Ada skenario Glints yang tidak sesuai.[/]")

    return semua_ok
