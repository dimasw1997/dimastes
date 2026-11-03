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
    def search_jobs(self, keyword: str, page: int = 1) -> List[Dict]:
        """Membuka hasil pencarian dan membaca lowongan yang dapat dikenali."""
        jobs: List[Dict] = []
        seen_urls = set()
        seen_ids = set()

        if not self.driver:
            console.print("[bold red]Browser belum dibuka.[/]")
            return jobs

        try:
            params = {"keywords": keyword}

            if config.location:
                params["where"] = config.location

            if page > 1:
                params["page"] = str(page)

            url = f"{config.search_url}?{urlencode(params)}"

            console.print(f"[bold cyan]Mencari: {keyword} — halaman {page}[/]")
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
        }

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

    def apply_job(self, job: Dict) -> bool:
        """
        Membuka halaman lowongan untuk ditinjau.
        Pengguna sendiri yang menekan Apply dan Submit di browser.
        """
        title = (job.get("title") or "").strip()
        job_url = (job.get("url") or "").strip()
        job_id = str(job.get("job_id") or "").strip()

        if not title or not job_url:
            console.print(
                "[yellow]Lowongan dilewati karena judul atau URL tidak terbaca.[/]"
            )
            return False

        if not job_id:
            job_id = self._extract_job_id(job_url)

        if db.is_already_applied(job_id):
            console.print(f"[yellow]Sudah tercatat sebagai dilamar: {title}[/]")
            return False

        try:
            self.driver.get(job_url)
            self.wait.until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)

            if self._is_already_applied_page():
                db.record_application(
                    job_id,
                    "already_applied",
                    "Halaman menandai lowongan ini sudah pernah dilamar",
                )
                console.print(
                    f"[yellow]JobStreet menandai '{title}' sudah pernah "
                    "dilamar. Dicatat dan dilewati.[/]"
                )
                return False

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
                db.record_application(
                    job_id,
                    "applied",
                    "Dikirim manual dan dikonfirmasi pengguna",
                )
                console.print("[bold green]Lamaran dicatat sebagai terkirim.[/]")
                return True

            db.record_application(
                job_id,
                "skipped",
                "Tidak dikonfirmasi sebagai lamaran terkirim",
            )
            console.print("[yellow]Tidak dicatat sebagai lamaran terkirim.[/]")
            return False

        except (EOFError, KeyboardInterrupt):
            console.print(
                "\n[yellow]Tinjauan dibatalkan; lamaran tidak dicatat.[/]"
            )
            return False

        except Exception as exc:
            console.print(f"[bold red]Gagal membuka lowongan: {exc}[/]")

            try:
                db.record_application(job_id, "error", str(exc))
            except Exception:
                pass

            return False

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
