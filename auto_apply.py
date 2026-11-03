"""Pengiriman lamaran otomatis di halaman detail lowongan JobStreet.

Alur yang ditangani: klik "Lamar" -> halaman/modal lamaran -> tombol
"Lanjutkan"/"Kirim lamaran" -> konfirmasi berhasil.

Modul ini sengaja konservatif: bila menemukan hal yang tidak bisa dipastikan
(lamaran diarahkan ke situs perusahaan, perlu unggah berkas, ada pertanyaan
yang harus dijawab), proses dihentikan dan lowongan dikembalikan sebagai
"manual_required" supaya Anda yang menyelesaikan sendiri.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from rich.console import Console
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By

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
    "application submitted",
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

ALREADY_SELECTORS = (
    "[data-automation='job-detail-applied-badge']",
    "[data-automation='appliedBadge']",
    "[data-testid='applied-badge']",
)

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

    def _blocker(self) -> str:
        """Alasan alur tidak boleh dilanjutkan otomatis ("" = aman)."""
        for element in self._find_all("input[type='file']"):
            if not self._visible(element):
                continue
            value = (element.get_attribute("value") or "").strip()
            if not value:
                return (
                    "Alur lamaran meminta unggah berkas "
                    "(isi RESUME_PATH di .env agar otomatis)"
                )

        for element in self._find_all("textarea"):
            if not self._visible(element):
                continue
            required = element.get_attribute("required")
            value = (element.get_attribute("value") or "").strip()
            if required and not value:
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
            time.sleep(1)
            url = (self.driver.current_url or "").lower()
        except Exception:
            return "Gagal berpindah ke tab lamaran"

        if "jobstreet." in url:
            return ""

        # Lamaran dibuka di situs perusahaan (ATS eksternal).
        try:
            self.driver.close()
            if handles_before:
                self.driver.switch_to.window(list(handles_before)[0])
        except Exception:
            pass

        return "Lamaran diarahkan ke situs perusahaan, bukan JobStreet"

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

            deadline = time.time() + self.step_timeout
            sudah_klik_kirim = False

            while time.time() < deadline:
                time.sleep(0.4)

                if self._is_success():
                    return ApplyResult(True, "applied", "Terkirim otomatis")

                # Isi otomatis cover letter / unggah CV bila dikonfigurasi.
                self._autofill()

                blocker = self._blocker()
                if blocker:
                    return ApplyResult(False, "manual_required", blocker)

                submit_button = self._find_clickable(
                    SUBMIT_SELECTORS, SUBMIT_TEXTS
                )
                if submit_button is not None:
                    if not self._click(submit_button):
                        return ApplyResult(
                            False, "error", "Tombol kirim lamaran gagal diklik"
                        )
                    sudah_klik_kirim = True
                    deadline = time.time() + self.step_timeout
                    continue

                continue_button = self._find_clickable(
                    CONTINUE_SELECTORS, CONTINUE_TEXTS
                )
                if continue_button is not None:
                    if not self._click(continue_button):
                        return ApplyResult(
                            False, "error", "Tombol lanjut gagal diklik"
                        )
                    deadline = time.time() + self.step_timeout
                    continue

            if self._is_success():
                return ApplyResult(True, "applied", "Terkirim otomatis")

            if sudah_klik_kirim:
                return ApplyResult(
                    False,
                    "manual_required",
                    "Tombol Kirim sudah diklik, tetapi konfirmasi tidak "
                    f"muncul dalam {self.step_timeout} detik "
                    "(periksa riwayat lamaran di JobStreet)",
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
