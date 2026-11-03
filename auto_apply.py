"""Pengiriman lamaran otomatis di halaman detail lowongan JobStreet.

Alur yang ditangani: klik "Lamar" -> halaman/modal lamaran -> tombol
"Lanjutkan"/"Kirim lamaran" -> konfirmasi berhasil.

Modul ini sengaja konservatif: bila menemukan hal yang tidak bisa dipastikan
(lamaran diarahkan ke situs perusahaan, perlu unggah berkas, ada pertanyaan
yang harus dijawab), proses dihentikan dan lowongan dikembalikan sebagai
"manual_required" supaya Anda yang menyelesaikan sendiri.
"""

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from rich.console import Console
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

from config import config

console = Console()

# Tombol untuk masuk ke alur lamaran.
APPLY_SELECTORS = (
    "[data-automation='job-detail-apply']",
    "a[data-automation='applyButton']",
    "button[data-automation='applyButton']",
    "[data-testid='job-detail-apply']",
    "[data-automation='job-detail-apply-button']",
)

# Tombol final yang benar-benar mengirim lamaran.
SUBMIT_SELECTORS = (
    "[data-automation='job-apply-submit']",
    "[data-automation='submit-application']",
    "[data-automation='job-detail-submit']",
    "[data-testid='submit-application']",
)

# Tombol untuk maju ke langkah berikutnya.
CONTINUE_SELECTORS = (
    "[data-automation='job-apply-continue']",
    "[data-automation='continue-application']",
    "[data-automation='job-detail-continue']",
)

APPLY_TEXTS = ("lamar", "apply", "melamar")
SUBMIT_TEXTS = ("kirim lamaran", "kirim aplikasi", "submit application", "submit")
CONTINUE_TEXTS = ("lanjutkan", "continue", "berikutnya", "selanjutnya", "next")

SUCCESS_TEXTS = (
    "lamaran anda telah dikirim",
    "lamaran berhasil",
    "berhasil dikirim",
    "lamaran terkirim",
    "terima kasih telah melamar",
    "anda telah melamar",
    "lamaran telah dikirim",
    "lamaranmu telah dikirim",
    "lamaran kamu telah dikirim",
    "application submitted",
    "your application has been submitted",
    "you have successfully applied",
    "successfully applied",
    "application sent",
)

ALREADY_TEXTS = (
    "anda sudah melamar",
    "sudah pernah melamar",
    "you have already applied",
    "application submitted",
)

# Pesan validasi JobStreet saat formulir belum lengkap.
VALIDATION_TEXTS = (
    "please address the following issues",
    "please make a selection",
    "harap lengkapi",
    "wajib dipilih",
    "wajib diisi",
    "harus dipilih",
)

GAJI_KATA = ("gaji", "salary", "upah", "pendapatan", "remunerasi")
PENGALAMAN_KATA = ("pengalaman", "experience", "tahun", "years", "year")
PENDIDIKAN_KATA = (
    "kualifikasi", "pendidikan", "education", "ijazah", "jenjang",
    "degree", "qualification",
)
LEVEL_ATAS_KATA = (
    "kepala", "head", "manager", "manajer", "supervisor", "spv", "lead",
    "chief",
)
NOL_KATA = (
    "no experience", "belum", "tanpa pengalaman", "fresh", "none",
    "kurang dari 1", "less than 1",
)


def _norm(teks: str) -> str:
    return " ".join(str(teks or "").lower().split())


def parse_gaji_juta(teks: str) -> Optional[float]:
    """Ubah teks gaji menjadi angka juta (mis. "Rp 5 Jt" -> 5.0)."""
    teks = _norm(teks).replace(".", "").replace(",", ".")
    angka = re.findall(r"\d+(?:\.\d+)?", teks)

    if not angka:
        return None

    nilai = float(angka[0])
    if "jt" in teks or "juta" in teks or "million" in teks:
        return nilai
    if nilai >= 100_000:
        return nilai / 1_000_000
    return nilai


def parse_tahun(teks: str) -> Optional[tuple]:
    """Baca rentang pengalaman dari teks opsi (tahun)."""
    teks_awal = _norm(teks)

    if any(kata in teks_awal for kata in NOL_KATA):
        return (0.0, 0.99)

    angka = [float(item.replace(",", ".")) for item in
             re.findall(r"\d+(?:[.,]\d+)?", teks_awal.replace(".", ""))]

    if not angka:
        return None

    if len(angka) >= 2 and re.search(r"\d\s*(?:-|–|to|s/d|sampai)\s*\d", teks_awal):
        return (min(angka[0], angka[1]), max(angka[0], angka[1]))

    if any(tanda in teks_awal for tanda in ("more than", "lebih dari", "+")):
        return (angka[0], 99.0)

    return (angka[0], angka[0])


def klasifikasi_pertanyaan(teks: str) -> str:
    """Tentukan jenis pertanyaan: gaji / pengalaman / pendidikan."""
    teks = _norm(teks)

    if any(kata in teks for kata in PENDIDIKAN_KATA):
        return "pendidikan"

    if any(kata in teks for kata in GAJI_KATA):
        return "gaji"

    if any(kata in teks for kata in PENGALAMAN_KATA):
        return "pengalaman"

    return ""


def _pilih_gaji(opsi, target: float) -> str:
    terbaik = ""
    selisih = None

    for item in opsi:
        nilai = parse_gaji_juta(item)
        if nilai is None:
            continue
        beda = abs(nilai - target)
        if selisih is None or beda < selisih:
            terbaik, selisih = item, beda

    return terbaik


def _pilih_tahun(opsi, tahun: float) -> str:
    rentang = [(item, parse_tahun(item)) for item in opsi]
    rentang = [(item, nilai) for item, nilai in rentang if nilai]

    if not rentang:
        return ""

    for item, (bawah, atas) in rentang:
        if bawah <= tahun <= atas:
            return item

    dibawah = [(item, nilai[1]) for item, nilai in rentang if nilai[1] <= tahun]
    if dibawah:
        return max(dibawah, key=lambda pasangan: pasangan[1])[0]

    return min(rentang, key=lambda pasangan: pasangan[1][0])[0]


def _pilih_pendidikan(opsi, level: str) -> str:
    level = _norm(level).replace("-", "").replace(" ", "")

    padanan = {
        "s1": ("s1", "sarjana", "bachelor", "strata 1"),
        "s2": ("s2", "magister", "master"),
        "d3": ("d3", "diploma 3", "ahli madya"),
        "sma": ("sma", "smk", "senior high"),
    }

    kunci = padanan.get(level, (level,))

    for item in opsi:
        teks = _norm(item).replace("-", "")
        if any(kata in teks for kata in kunci if kata):
            return item

    return ""


def pilih_jawaban(pertanyaan: str, opsi, cfg=None) -> str:
    """Pilih teks opsi yang aman untuk sebuah pertanyaan ('' = tidak dijawab)."""
    cfg = cfg or config
    opsi = [item for item in (opsi or []) if _norm(item)]

    if not opsi:
        return ""

    jenis = klasifikasi_pertanyaan(pertanyaan)

    if jenis == "pendidikan":
        return _pilih_pendidikan(opsi, getattr(cfg, "education_level", ""))

    if jenis == "gaji":
        target = parse_gaji_juta(getattr(cfg, "expected_salary", "") or "")
        if target is None:
            return ""
        return _pilih_gaji(opsi, target)

    if jenis == "pengalaman":
        teks = _norm(pertanyaan)
        tahun = (
            0.0
            if any(kata in teks for kata in LEVEL_ATAS_KATA)
            else float(getattr(cfg, "years_experience", 0) or 0)
        )
        return _pilih_tahun(opsi, tahun)

    return ""


ALREADY_SELECTORS = (
    "[data-automation='job-detail-applied-badge']",
    "[data-automation='appliedBadge']",
    "[data-testid='applied-badge']",
)

JOBSTREET_DOMAIN = "jobstreet.com"

EXTERNAL_BUTTON_TEXTS = (
    "lamar di situs perusahaan",
    "apply on company site",
    "apply on employer site",
    "apply on company website",
)


@dataclass
class ApplyResult:
    """Hasil satu percobaan melamar."""

    applied: bool
    status: str  # applied | already_applied | manual_required | error
    reason: str = ""


class AutoApplier:
    def __init__(self, driver, wait=None):
        self.driver = driver
        self.wait = wait
        self.step_timeout = config.auto_apply_step_timeout
        self.submit_timeout = config.auto_apply_submit_timeout
        self.debug_dumps = 0

    # ------------------------------------------------------------------
    # Utilitas elemen
    # ------------------------------------------------------------------
    @staticmethod
    def _visible(element) -> bool:
        try:
            return element.is_displayed()
        except Exception:
            return False

    @staticmethod
    def _enabled(element) -> bool:
        try:
            return element.is_enabled()
        except Exception:
            return True

    @staticmethod
    def _text(element) -> str:
        try:
            value = element.text or element.get_attribute("textContent") or ""
        except Exception:
            value = ""
        return " ".join(str(value).split()).strip().lower()

    def _url(self) -> str:
        try:
            return str(self.driver.current_url or "")
        except Exception:
            return ""

    def _body_text(self) -> str:
        try:
            element = self.driver.find_element(By.TAG_NAME, "body")
            return " ".join((element.text or "").split()).lower()
        except Exception:
            return ""

    def _find_all(self, selector: str) -> list:
        try:
            return self.driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            return []

    def _find_clickable(self, selectors, texts=()) -> Optional[object]:
        """Cari elemen pertama yang terlihat dan cocok dengan selector/teks."""
        for selector in selectors:
            for element in self._find_all(selector):
                if self._visible(element) and self._enabled(element):
                    return element

        if not texts:
            return None

        for selector in ("button", "a", "[role='button']"):
            for element in self._find_all(selector):
                if not self._visible(element) or not self._enabled(element):
                    continue

                label = self._text(element)
                if not label:
                    continue

                if any(label == text or label.startswith(text) for text in texts):
                    return element

        return None

    def _click(self, element) -> bool:
        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", element
            )
        except Exception:
            pass

        try:
            element.click()
            return True
        except Exception:
            try:
                self.driver.execute_script("arguments[0].click();", element)
                return True
            except Exception:
                return False

    # ------------------------------------------------------------------
    # Deteksi status
    # ------------------------------------------------------------------
    def is_already_applied(self) -> bool:
        for selector in ALREADY_SELECTORS:
            for element in self._find_all(selector):
                if self._visible(element):
                    return True

        body = self._body_text()
        return any(text in body for text in ALREADY_TEXTS)

    @staticmethod
    def _is_jobstreet_url(url: str) -> bool:
        try:
            host = (urlparse(url or "").netloc or "").lower()
        except Exception:
            return True

        if not host:
            return True

        return JOBSTREET_DOMAIN in host

    def _is_external_page(self) -> bool:
        try:
            url = self.driver.current_url or ""
        except Exception:
            return False

        return bool(url) and not self._is_jobstreet_url(url)

    def _external_host(self) -> str:
        try:
            return (urlparse(self.driver.current_url or "").netloc or "").lower()
        except Exception:
            return ""

    def _is_review_page(self) -> bool:
        """Halaman terakhir "Review and submit"."""
        try:
            url = (self.driver.current_url or "").lower()
        except Exception:
            url = ""

        if "/apply/review" in url or "review-and-submit" in url:
            return True

        body = self._body_text()
        return any(
            text in body
            for text in ("review and submit", "review & submit",
                         "tinjau dan kirim")
        )

    def _dump_debug(self, job: dict):
        """Simpan HTML + screenshot agar selector mudah diperbaiki."""
        if not config.auto_apply_debug or self.debug_dumps >= 5:
            return

        try:
            folder = Path("debug")
            folder.mkdir(exist_ok=True)

            stamp = time.strftime("%Y%m%d-%H%M%S")
            nama = f"{stamp}-{job.get('job_id') or 'lowongan'}"
            dasar = folder / nama

            try:
                url = self.driver.current_url or ""
            except Exception:
                url = ""

            (dasar.with_suffix(".txt")).write_text(
                f"URL: {url}\nJob: {job.get('title') or '-'}\n",
                encoding="utf-8",
            )
            (dasar.with_suffix(".html")).write_text(
                self.driver.page_source or "", encoding="utf-8"
            )
            self.driver.save_screenshot(str(dasar.with_suffix(".png")))
            self.debug_dumps += 1
            console.print(
                f"[dim]Halaman tidak dikenali; debug disimpan di "
                f"debug/{nama}.html[/]"
            )
        except Exception:
            pass

    def _find_submit_button(self, review_page: bool = False):
        """Cari tombol kirim. Di halaman review, cakupannya lebih luas."""
        button = self._find_clickable(SUBMIT_SELECTORS, SUBMIT_TEXTS)
        if button is not None:
            return button

        if not review_page:
            return None

        negatif = ("back", "kembali", "batal", "cancel", "hapus", "delete")

        # Tombol kirim di halaman review hampir selalu bertipe submit.
        for element in self._find_all("button[type='submit']"):
            if not self._visible(element) or not self._enabled(element):
                continue
            if any(kata in self._text(element) for kata in negatif):
                continue
            return element

        # Hindari kata "lamar"/"apply": di halaman review tombol itu bisa
        # berarti memulai ulang lamaran.
        kata_kunci = ("submit", "kirim", "send application")

        for selector in ("button", "[role='button']", "a"):
            for element in self._find_all(selector):
                if not self._visible(element) or not self._enabled(element):
                    continue
                label = self._text(element)
                if any(kata in label for kata in negatif):
                    continue
                if any(kata in label for kata in kata_kunci):
                    return element

        return None

    def _is_login_page(self) -> bool:
        try:
            url = (self.driver.current_url or "").lower()
        except Exception:
            url = ""

        if "signin" in url or "/login" in url:
            return True

        return bool(self._find_all("input[type='password']"))

    def _is_success(self) -> bool:
        try:
            url = (self.driver.current_url or "").lower()
        except Exception:
            url = ""

        if "success" in url or "submitted" in url or "confirmation" in url:
            return True

        body = self._body_text()
        return any(text in body for text in SUCCESS_TEXTS)

    def _autofill(self) -> bool:
        """Isi cover letter dan unggah CV bila formulir memintanya.

        Hanya berjalan bila COVER_LETTER / RESUME_PATH diisi di .env.
        """
        terisi = False

        if config.cover_letter:
            for element in self._find_all("textarea"):
                if not self._visible(element):
                    continue
                if (element.get_attribute("value") or "").strip():
                    continue
                try:
                    element.send_keys(config.cover_letter)
                    terisi = True
                except Exception:
                    continue

        if config.resume_path:
            berkas = Path(config.resume_path).expanduser()

            if berkas.is_file():
                for element in self._find_all("input[type='file']"):
                    if not self._visible(element):
                        continue
                    if (element.get_attribute("value") or "").strip():
                        continue
                    try:
                        element.send_keys(str(berkas))
                        terisi = True
                    except Exception:
                        continue

        return terisi

    def _pertanyaan(self, element) -> str:
        """Label/teks pertanyaan untuk sebuah dropdown."""
        for atribut in ("aria-label", "name", "id"):
            try:
                nilai = (element.get_attribute(atribut) or "").strip()
            except Exception:
                nilai = ""
            if nilai:
                return nilai

        try:
            induk = element.find_element(By.XPATH, "..")
            teks = " ".join((induk.text or "").split())
            if teks:
                return teks
        except Exception:
            pass

        return ""

    @staticmethod
    def _teks_opsi(element) -> list:
        try:
            opsi = element.find_elements(By.TAG_NAME, "option")
        except Exception:
            return []

        hasil = []
        for item in opsi:
            try:
                teks = " ".join((item.text or "").split())
            except Exception:
                continue
            if teks and teks.lower() not in (
                "pilih", "select", "please select", "-", "--",
            ):
                hasil.append(teks)

        return hasil

    def _pilih_opsi(self, element, teks: str) -> bool:
        try:
            Select(element).select_by_visible_text(teks)
            return True
        except Exception:
            pass

        try:
            for item in element.find_elements(By.TAG_NAME, "option"):
                if " ".join((item.text or "").split()) == teks:
                    return self._click(item)
        except Exception:
            pass

        return False

    def jawab_pertanyaan(self) -> list:
        """Jawab pertanyaan pilihan yang polanya dikenali.

        Kembalikan daftar pertanyaan yang belum bisa dijawab otomatis.
        """
        if not config.auto_answer_questions:
            return []

        gagal = []

        for element in self._find_all("select"):
            if not self._visible(element) or not self._enabled(element):
                continue

            try:
                terisi = (element.get_attribute("value") or "").strip()
            except Exception:
                terisi = ""

            if terisi:
                continue

            pertanyaan = self._pertanyaan(element)
            opsi = self._teks_opsi(element)
            pilihan = pilih_jawaban(pertanyaan, opsi)

            if pilihan and self._pilih_opsi(element, pilihan):
                console.print(
                    f'[dim]   jawab "{pilihan}"'
                    f' untuk: {pertanyaan[:60] or "pertanyaan"}[/]'
                )
            else:
                gagal.append(pertanyaan or "pertanyaan tanpa label")

        return gagal

    def _validation_error(self) -> str:
        """Teks peringatan validasi formulir lamaran ('' bila tidak ada)."""
        body = self._body_text()

        for tanda in VALIDATION_TEXTS:
            posisi = body.find(tanda)
            if posisi >= 0:
                potong = " ".join(body[posisi:posisi + 220].split())
                return potong

        return ""

    @staticmethod
    def _is_required(element) -> bool:
        """True bila elemen benar-benar wajib (termasuk `required` kosong)."""
        try:
            if (element.get_attribute("aria-required") or "") == "true":
                return True
            return element.get_attribute("required") is not None
        except Exception:
            return False

    def _blocker(self) -> str:
        """Alasan alur tidak boleh dilanjutkan otomatis ("" = aman)."""
        for element in self._find_all("input[type='file']"):
            if not self._visible(element):
                continue

            # Unggah berkas biasanya OPSIONAL ("Documents included").
            # Hanya anggap penghalang bila memang wajib.
            value = (element.get_attribute("value") or "").strip()

            if self._is_required(element) and not value:
                return (
                    "Alur lamaran mewajibkan unggah berkas "
                    "(isi RESUME_PATH di .env agar otomatis)"
                )

        for element in self._find_all("textarea"):
            if not self._visible(element):
                continue
            value = (element.get_attribute("value") or "").strip()
            if self._is_required(element) and not value:
                return (
                    "Ada pertanyaan/cover letter wajib "
                    "(isi COVER_LETTER di .env agar otomatis)"
                )

        for element in self._find_all("select[required]"):
            if not self._visible(element):
                continue
            value = (element.get_attribute("value") or "").strip()
            if not value:
                return "Ada pertanyaan pilihan yang wajib dijawab"

        for element in self._find_all("input[type='radio'][required]"):
            if not self._visible(element):
                continue
            name = element.get_attribute("name") or ""
            if not name:
                return "Ada pertanyaan yang wajib dijawab"

            group = self._find_all(f"input[type='radio'][name='{name}']")
            if not any(self._selected(item) for item in group):
                return "Ada pertanyaan yang wajib dijawab"

        return ""

    @staticmethod
    def _selected(element) -> bool:
        try:
            return bool(element.is_selected())
        except Exception:
            return False

    def _external_button_present(self) -> bool:
        for selector in ("button", "a", "[role='button']"):
            for element in self._find_all(selector):
                if not self._visible(element):
                    continue
                label = self._text(element)
                if any(text in label for text in EXTERNAL_BUTTON_TEXTS):
                    return True
        return False

    # ------------------------------------------------------------------
    # Jendela / tab baru
    # ------------------------------------------------------------------
    def _handle_new_window(self, handles_before: set) -> str:
        """Tangani tab baru. Kembalikan alasan jika harus berhenti."""
        try:
            handles = set(self.driver.window_handles)
        except Exception:
            return ""

        new_handles = handles - handles_before
        if not new_handles:
            return ""

        try:
            self.driver.switch_to.window(new_handles.pop())
            time.sleep(0.3)
            url = self.driver.current_url or ""
        except Exception:
            return "Gagal berpindah ke tab lamaran"

        if self._is_jobstreet_url(url):
            return ""

        # Simpan domain sebelum tab ditutup, agar pesannya tetap benar.
        try:
            host = (urlparse(url).netloc or "").lower()
        except Exception:
            host = ""

        # Lamaran dibuka di situs perusahaan (ATS eksternal).
        try:
            self.driver.close()
            if handles_before:
                self.driver.switch_to.window(list(handles_before)[0])
        except Exception:
            pass

        return (
            "Lamaran diarahkan ke situs lain "
            f"({host or 'situs perusahaan'}) — dilewati"
        )

    # ------------------------------------------------------------------
    # Alur utama
    # ------------------------------------------------------------------
    def apply(self, job: dict) -> ApplyResult:
        url = (job.get("url") or "").strip()

        if not url:
            return ApplyResult(False, "error", "URL lowongan kosong")

        try:
            self.driver.get(url)
            time.sleep(0.8)

            if self._is_login_page():
                return ApplyResult(
                    False,
                    "login_required",
                    "Sesi login JobStreet sudah habis",
                )

            if self._is_external_page():
                return ApplyResult(
                    False,
                    "manual_required",
                    "Lowongan dialihkan ke situs lain "
                    f"({self._external_host()}) — dilewati",
                )

            if self.is_already_applied():
                return ApplyResult(
                    False,
                    "already_applied",
                    "JobStreet menandai lowongan ini sudah pernah dilamar",
                )

            if self._external_button_present():
                return ApplyResult(
                    False,
                    "manual_required",
                    "Lowongan menggunakan 'Lamar di situs perusahaan'",
                )

            # Tunggu tombol Lamar muncul, maksimal sepanjang batas waktu.
            apply_button = self._find_clickable(APPLY_SELECTORS, APPLY_TEXTS)
            batas_tombol = time.time() + self.step_timeout

            while apply_button is None and time.time() < batas_tombol:
                time.sleep(0.3)
                apply_button = self._find_clickable(
                    APPLY_SELECTORS, APPLY_TEXTS
                )

            if apply_button is None:
                return ApplyResult(
                    False,
                    "manual_required",
                    "Tombol Lamar tidak ditemukan di halaman",
                )

            handles_before = set(self.driver.window_handles)
            self._click(apply_button)
            time.sleep(0.5)

            external_reason = self._handle_new_window(handles_before)
            if external_reason:
                return ApplyResult(False, "manual_required", external_reason)

            if self._is_external_page():
                return ApplyResult(
                    False,
                    "manual_required",
                    "Lamaran dialihkan ke situs lain "
                    f"({self._external_host()}) — dilewati",
                )

            review_page = self._is_review_page()
            deadline = time.time() + (
                self.submit_timeout if review_page else self.step_timeout
            )
            sudah_klik_kirim = False
            percobaan_kirim = 0
            kirim_terakhir = 0.0
            jejak_lanjut = ""
            klik_lanjut = 0

            while time.time() < deadline:
                time.sleep(0.4)

                if self._is_external_page():
                    return ApplyResult(
                        False,
                        "manual_required",
                        "Lamaran dialihkan ke situs lain "
                        f"({self._external_host()}) — dilewati",
                    )

                if self._is_success():
                    return ApplyResult(True, "applied", "Terkirim otomatis")

                # Halaman "Review and submit" sering muncul setelah beberapa
                # detik; beri waktu lebih panjang untuk mengenalinya.
                if not review_page and self._is_review_page():
                    review_page = True
                    deadline = max(
                        deadline, time.time() + self.submit_timeout
                    )
                    console.print(
                        '[dim]   halaman "Review and submit" terdeteksi; '
                        f"menunggu tombol kirim s.d. {self.submit_timeout} "
                        "detik[/]"
                    )

                # Isi otomatis cover letter / unggah CV bila dikonfigurasi.
                self._autofill()

                if not review_page:
                    belum_terjawab = self.jawab_pertanyaan()

                    galat = self._validation_error()
                    if galat and belum_terjawab:
                        console.print(
                            "[dim]   pertanyaan belum bisa dijawab: "
                            f"{belum_terjawab[0][:60]}[/]"
                        )
                        self._dump_debug(job)
                        return ApplyResult(
                            False,
                            "manual_required",
                            "Formulir meminta isian yang belum bisa dijawab "
                            f"otomatis ({belum_terjawab[0][:60]}) — dilewati",
                        )

                    blocker = self._blocker()
                    if blocker:
                        # Pastikan bukan halaman yang masih memuat.
                        time.sleep(0.4)
                        if self._blocker() == blocker:
                            self._dump_debug(job)
                            return ApplyResult(
                                False, "manual_required", blocker
                            )

                submit_button = self._find_submit_button(review_page)
                if submit_button is not None:
                    # Hindari klik ganda: beri jeda 2 detik sebelum mencoba
                    # lagi bila tombol masih terlihat (halaman lambat).
                    boleh_klik = (
                        not sudah_klik_kirim
                        or time.time() - kirim_terakhir >= 2
                    )
                    if boleh_klik and percobaan_kirim < 3:
                        if not self._click(submit_button):
                            return ApplyResult(
                                False,
                                "error",
                                "Tombol kirim lamaran gagal diklik",
                            )
                        console.print(
                            "[dim]   klik tombol kirim "
                            f'"{self._text(submit_button) or "tanpa teks"}"'
                            f" (percobaan {percobaan_kirim + 1})[/]"
                        )
                        sudah_klik_kirim = True
                        percobaan_kirim += 1
                        kirim_terakhir = time.time()
                        review_page = True
                        deadline = time.time() + self.submit_timeout
                        continue

                continue_button = self._find_clickable(
                    CONTINUE_SELECTORS, CONTINUE_TEXTS
                )
                if continue_button is not None:
                    jejak = (
                        f"{self._url()}|{len(self._body_text())}"
                    )
                    if jejak == jejak_lanjut:
                        klik_lanjut += 1
                    else:
                        jejak_lanjut = jejak
                        klik_lanjut = 1

                    if klik_lanjut > 2:
                        galat = self._validation_error()
                        self._dump_debug(job)
                        return ApplyResult(
                            False,
                            "manual_required",
                            galat
                            or "Halaman tidak maju setelah tombol Lanjut "
                            "diklik 3 kali — dilewati",
                        )

                    console.print(
                        "[dim]   klik lanjut "
                        f'"{self._text(continue_button) or "tanpa teks"}"[/]'
                    )
                    if not self._click(continue_button):
                        return ApplyResult(
                            False, "error", "Tombol lanjut gagal diklik"
                        )
                    deadline = time.time() + self.step_timeout
                    continue

            if self._is_success():
                return ApplyResult(True, "applied", "Terkirim otomatis")

            self._dump_debug(job)

            if sudah_klik_kirim:
                return ApplyResult(
                    False,
                    "manual_required",
                    "Tombol Kirim sudah diklik, tetapi konfirmasi tidak "
                    f"muncul dalam {self.submit_timeout} detik "
                    "(periksa riwayat lamaran di JobStreet)",
                )

            if review_page:
                return ApplyResult(
                    False,
                    "manual_required",
                    "Halaman Review and submit tidak menampilkan tombol "
                    "kirim yang dikenali",
                )

            return ApplyResult(
                False,
                "manual_required",
                f"Alur lamaran tidak dikenali dalam {self.step_timeout} detik",
            )

        except (KeyboardInterrupt, SystemExit):
            raise

        except Exception as exc:
            return ApplyResult(False, "error", str(exc))
