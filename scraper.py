"""Pembungkus Selenium untuk membuka JobStreet dan membaca kartu lowongan.

Program ini tidak mengirim lamaran otomatis: halaman lowongan hanya dibuka
agar pengguna meninjau dan mengirim lamaran sendiri di browser.
"""

import hashlib
import re
import time
from typing import Dict, List, Optional
from urllib.parse import urldefrag, urlencode, urljoin

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from rich.console import Console

from auto_apply import ApplyResult, AutoApplier
from config import config
from database import db

console = Console()

CARD_SELECTORS = (
    "article",
    "[data-automation='normalJob']",
    "[data-testid='job-card']",
)

ALREADY_APPLIED_MARKERS = (
    "[data-automation='job-detail-applied-badge']",
    "[data-automation='appliedBadge']",
    "[data-testid='applied-badge']",
)


class JobStreetBot:
    def __init__(self):
        self.driver = None
        self.wait = None

    # ------------------------------------------------------------------
    # Browser
    # ------------------------------------------------------------------
    def init_browser(self):
        """Membuka Chrome. Mode headless mengikuti HEADLESS_MODE di .env."""
        console.print("[bold blue]Membuka Chrome...[/]")

        options = Options()
        options.add_argument("--window-size=1400,900")
        options.add_argument("--disable-blink-features=AutomationControlled")

        if config.headless:
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
        else:
            options.add_argument("--start-maximized")

        try:
            # Selenium 4.6+ sudah punya Selenium Manager, jadi tidak wajib
            # menyiapkan chromedriver secara manual.
            self.driver = webdriver.Chrome(options=options)
        except Exception as first_error:
            console.print(
                f"[yellow]ChromeDriver otomatis gagal ({first_error}). "
                "Mencoba webdriver-manager...[/]"
            )
            try:
                from webdriver_manager.chrome import ChromeDriverManager

                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(
                    service=service, options=options
                )
            except Exception as second_error:
                raise RuntimeError(
                    "Chrome tidak bisa dibuka. Pastikan Google Chrome sudah "
                    "terpasang, lalu jalankan ulang program. "
                    f"Detail: {second_error}"
                ) from first_error

        self.wait = WebDriverWait(self.driver, 20)
        console.print("[bold green]Chrome siap.[/]")

    def login(self) -> bool:
        """Login dilakukan sendiri oleh pengguna di browser."""
        if not self.driver:
            console.print("[bold red]Browser belum dibuka.[/]")
            return False

        try:
            self.driver.get(config.base_url)
            time.sleep(2)

            console.print("\n[bold cyan]Silakan login secara manual di jendela Chrome.[/]")

            if config.headless:
                console.print(
                    "[yellow]HEADLESS_MODE aktif sehingga jendela Chrome "
                    "tidak terlihat. Set HEADLESS_MODE=false untuk login "
                    "dan meninjau lowongan secara manual.[/]"
                )

            console.print("Buka tombol Sign in di halaman JobStreet dan selesaikan login.")
            input("Jika sudah selesai, kembali ke terminal lalu tekan Enter: ")

            return True

        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Login dibatalkan.[/]")
            return False

        except Exception as exc:
            console.print(f"[bold red]Gagal membuka JobStreet: {exc}[/]")
            return False

    # ------------------------------------------------------------------
    # Pencarian
    # ------------------------------------------------------------------
    def search_jobs(
        self, keyword: str, page: int = 1, location: Optional[str] = None
    ) -> List[Dict]:
        """Membuka hasil pencarian dan membaca lowongan yang dapat dikenali."""
        jobs: List[Dict] = []
        seen_urls = set()
        seen_ids = set()

        if not self.driver:
            console.print("[bold red]Browser belum dibuka.[/]")
            return jobs

        try:
            # Lokasi bisa berbeda per pencarian (mendukung banyak kota).
            lokasi = (location or config.location or "").strip()
            params = {"keywords": keyword}

            if lokasi:
                params["where"] = lokasi

            # ListedDate = urutkan dari lowongan yang paling baru diposting.
            if config.sort_mode:
                params["sortmode"] = config.sort_mode

            if config.max_age_days > 0:
                params["daterange"] = str(config.max_age_days)

            if page > 1:
                params["page"] = str(page)

            url = f"{config.search_url}?{urlencode(params)}"

            console.print(
                f"[bold cyan]Mencari: {keyword} — {lokasi or 'semua lokasi'} "
                f"— halaman {page}[/]"
            )
            self.driver.get(url)

            try:
                self.wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ", ".join(CARD_SELECTORS))
                    )
                )
            except TimeoutException:
                console.print(
                    "[yellow]Kartu lowongan tidak muncul dalam 20 detik. "
                    "Mungkin halaman masih memuat atau struktur website "
                    "berubah.[/]"
                )

            time.sleep(1)

            cards = []
            for selector in CARD_SELECTORS:
                found = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if found:
                    cards.extend(found)

            for card in cards:
                try:
                    job = self._parse_job_card(card)
                    if not job:
                        continue

                    if job["url"] in seen_urls or job["job_id"] in seen_ids:
                        continue

                    seen_urls.add(job["url"])
                    seen_ids.add(job["job_id"])
                    jobs.append(job)

                except Exception:
                    continue

            if jobs:
                console.print(f"   Terbaca {len(jobs)} lowongan.")
            else:
                console.print(
                    "[yellow]Tidak ada lowongan yang berhasil dibaca. "
                    "Periksa halaman Chrome; struktur website mungkin berubah.[/]"
                )
                console.print(f"[dim]Halaman pencarian: {url}[/]")

        except Exception as exc:
            console.print(f"[bold red]Gagal membaca hasil pencarian: {exc}[/]")

        return jobs

    def _parse_job_card(self, card) -> Optional[Dict]:
        """Membaca satu kartu lowongan. Kartu tanpa judul/URL dilewati."""
        links = self._collect_job_links(card)

        title = ""
        job_url = ""

        for link in links:
            href = link.get_attribute("href")
            if not href:
                continue

            candidate_title = self._read_link_title(link)
            if not candidate_title:
                continue

            title = candidate_title
            job_url = urldefrag(
                urljoin(self.driver.current_url, href)
            )[0]
            break

        # Jangan membuat atau memproses lowongan dengan judul kosong.
        if not title or not job_url:
            return None

        company = self._read_card_value(
            card,
            [
                "[data-automation='jobCompany']",
                "[data-automation*='jobCompany']",
            ],
        )

        location = self._read_card_value(
            card,
            [
                "[data-automation='jobLocation']",
                "[data-automation*='jobLocation']",
            ],
        )

        salary = self._read_card_value(
            card,
            [
                "[data-automation='jobSalary']",
                "[data-automation*='jobSalary']",
            ],
        )

        date_posted = self._read_card_value(
            card,
            [
                "[data-automation='jobListingDate']",
                "time",
            ],
        )

        try:
            description = (card.text or "").strip()
        except Exception:
            description = ""

        return {
            "job_id": self._extract_job_id(job_url),
            "title": title,
            "company": company or "Tidak diketahui",
            "location": location,
            "salary": salary or "Tidak disebutkan",
            "description": description,
            "url": job_url,
            "date_posted": date_posted,
            "age_days": self._parse_listing_age(date_posted),
        }

    @staticmethod
    def _parse_listing_age(text: str) -> Optional[int]:
        """Mengubah label tanggal ("Hari ini", "3 hari yang lalu") jadi umur hari."""
        value = " ".join(str(text or "").split()).lower()

        if not value:
            return None

        if any(word in value for word in ("hari ini", "today", "baru", "just now")):
            return 0

        if any(word in value for word in ("kemarin", "yesterday")):
            return 1

        if "+" in value and any(word in value for word in ("hari", "day")):
            return 30

        match = re.search(r"(\d+)\s*(?:jam|hour|h)\b", value)
        if match:
            return 0

        match = re.search(r"(\d+)\s*(?:hari|day|d)\b", value)
        if match:
            return int(match.group(1))

        match = re.search(r"(\d+)\s*(?:minggu|week|w)\b", value)
        if match:
            return int(match.group(1)) * 7

        match = re.search(r"(\d+)\s*(?:bulan|month|mo)\b", value)
        if match:
            return int(match.group(1)) * 30

        return None

    @staticmethod
    def _collect_job_links(card) -> list:
        selectors = (
            "a[data-automation='jobTitle']",
            "a[data-automation*='jobTitle']",
            "h3 a",
            "a[href*='/job/']",
            "a[href*='/job-']",
        )

        links = []
        seen = set()

        for selector in selectors:
            try:
                elements = card.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                continue

            for element in elements:
                if element.id in seen:
                    continue
                seen.add(element.id)
                links.append(element)

        return links

    @staticmethod
    def _read_link_title(link) -> str:
        candidates = [
            link.text,
            link.get_attribute("aria-label"),
            link.get_attribute("title"),
            link.get_attribute("textContent"),
        ]

        return next(
            (
                value.strip()
                for value in candidates
                if value and value.strip()
            ),
            "",
        )

    @staticmethod
    def _read_card_value(card, selectors: List[str]) -> str:
        for selector in selectors:
            try:
                element = card.find_element(By.CSS_SELECTOR, selector)
                value = (
                    element.text
                    or element.get_attribute("textContent")
                    or ""
                )
                value = value.strip()
                if value:
                    return value
            except NoSuchElementException:
                continue
            except Exception:
                continue

        return ""

    @staticmethod
    def _extract_job_id(url: str) -> str:
        """Membuat ID stabil agar lowongan yang sama tidak berubah ID."""
        match = re.search(r"/job(?:/|-)(\d+)", url, re.IGNORECASE)

        if match:
            return match.group(1)

        query_id = re.search(r"[?&]id=(\d+)", url)
        if query_id:
            return query_id.group(1)

        clean_url = url.split("?", 1)[0].rstrip("/")
        return hashlib.sha256(clean_url.encode("utf-8")).hexdigest()[:24]

    # ------------------------------------------------------------------
    # Meninjau / mencatat lamaran
    # ------------------------------------------------------------------
    def _is_already_applied_page(self) -> bool:
        for selector in ALREADY_APPLIED_MARKERS:
            try:
                if self.driver.find_elements(By.CSS_SELECTOR, selector):
                    return True
            except Exception:
                continue

        try:
            page_text = (self.driver.find_element(By.TAG_NAME, "body").text or "").lower()
        except Exception:
            return False

        markers = (
            "anda sudah melamar",
            "sudah pernah melamar",
            "you have already applied",
            "application submitted",
        )
        return any(marker in page_text for marker in markers)

    def apply_job(self, job: Dict) -> ApplyResult:
        """Melamar satu lowongan: otomatis bila AUTO_APPLY aktif, atau manual."""
        title = (job.get("title") or "").strip()
        job_url = (job.get("url") or "").strip()
        job_id = str(job.get("job_id") or "").strip()

        if not title or not job_url:
            console.print(
                "[yellow]Lowongan dilewati karena judul atau URL tidak terbaca.[/]"
            )
            return ApplyResult(False, "error", "Judul atau URL tidak terbaca")

        if not job_id:
            job_id = self._extract_job_id(job_url)
            job["job_id"] = job_id

        if db.is_already_applied(job_id):
            console.print(f"[yellow]Sudah tercatat sebagai dilamar: {title}[/]")
            return ApplyResult(False, "already_applied", "Sudah tercatat dilamar")

        if config.auto_apply:
            return self._apply_automatically(job, job_id)

        return self._apply_manually(job, job_id)

    @staticmethod
    def _record(job_id: str, status: str, notes: str):
        try:
            db.record_application(job_id, status, notes)
        except Exception as exc:
            console.print(f"[yellow]Gagal mencatat lamaran: {exc}[/]")

    def _apply_automatically(self, job: Dict, job_id: str) -> ApplyResult:
        title = (job.get("title") or "").strip()
        console.print(f"\n[bold magenta]{title}[/] [cyan](otomatis)[/]")

        result = AutoApplier(self.driver, self.wait).apply(job)

        if result.status == "applied":
            self._record(job_id, "applied", result.reason or "Dikirim otomatis")
            console.print("[bold green]Lamaran terkirim otomatis.[/]")

        elif result.status == "already_applied":
            self._record(job_id, "already_applied", result.reason)
            console.print(f"[yellow]{result.reason}. Dicatat dan dilewati.[/]")

        elif result.status == "manual_required":
            self._record(job_id, "manual_required", result.reason)
            console.print(
                f"[yellow]Perlu dilamar manual: {result.reason}[/]"
            )

        else:
            self._record(job_id, "error", result.reason)
            console.print(
                f"[bold red]Gagal melamar otomatis: {result.reason}[/]"
            )

        return result

    def _apply_manually(self, job: Dict, job_id: str) -> ApplyResult:
        """Membuka halaman lowongan agar pengguna melamar sendiri."""
        title = (job.get("title") or "").strip()
        job_url = (job.get("url") or "").strip()

        try:
            self.driver.get(job_url)
            self.wait.until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)

            if self._is_already_applied_page():
                self._record(
                    job_id,
                    "already_applied",
                    "Halaman menandai lowongan ini sudah pernah dilamar",
                )
                console.print(
                    f"[yellow]JobStreet menandai '{title}' sudah pernah "
                    "dilamar. Dicatat dan dilewati.[/]"
                )
                return ApplyResult(False, "already_applied", "Sudah pernah dilamar")

            console.print(f"\n[bold magenta]{title}[/]")
            console.print(f"Perusahaan: {job.get('company', 'Tidak diketahui')}")
            console.print(f"URL: {job_url}")
            console.print(
                "[cyan]Tinjau persyaratan di Chrome. "
                "Jika cocok, lakukan Apply dan Submit sendiri.[/]"
            )

            answer = input(
                "Setelah selesai meninjau, tekan Enter "
                "(ketik y bila lamaran sudah terkirim): "
            ).strip().lower()

            if answer in ("y", "ya", "yes"):
                self._record(
                    job_id,
                    "applied",
                    "Dikirim manual dan dikonfirmasi pengguna",
                )
                console.print("[bold green]Lamaran dicatat sebagai terkirim.[/]")
                return ApplyResult(True, "applied", "Dikonfirmasi manual")

            self._record(
                job_id,
                "skipped",
                "Tidak dikonfirmasi sebagai lamaran terkirim",
            )
            console.print("[yellow]Tidak dicatat sebagai lamaran terkirim.[/]")
            return ApplyResult(False, "skipped", "Tidak dikonfirmasi")

        except (EOFError, KeyboardInterrupt):
            console.print(
                "\n[yellow]Tinjauan dibatalkan; lamaran tidak dicatat.[/]"
            )
            return ApplyResult(False, "skipped", "Dibatalkan")

        except Exception as exc:
            console.print(f"[bold red]Gagal membuka lowongan: {exc}[/]")
            self._record(job_id, "error", str(exc))
            return ApplyResult(False, "error", str(exc))

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            finally:
                self.driver = None
                self.wait = None

            console.print("[blue]Chrome ditutup.[/]")
