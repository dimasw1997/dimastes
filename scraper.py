import hashlib
import re
import time
from typing import Dict, List, Optional
from urllib.parse import urlencode, urljoin

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from rich.console import Console

from config import config
from database import db

console = Console()


class JobStreetBot:
    def __init__(self):
        self.driver = None
        self.wait = None

    def init_browser(self):
        """Membuka Chrome yang terlihat agar pengguna bisa login dan meninjau lowongan."""
        console.print("[bold blue]Membuka Chrome...[/]")

        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--window-size=1400,900")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 20)

        console.print("[bold green]Chrome siap.[/]")

    def login(self) -> bool:
        """
        Login dilakukan sendiri oleh pengguna di browser.
        Tidak menyimpan atau mengetikkan password secara otomatis.
        """
        try:
            self.driver.get(config.base_url)
            time.sleep(2)

            console.print("\n[bold cyan]Silakan login secara manual di jendela Chrome.[/]")
            console.print("Buka tombol Sign in di halaman JobStreet dan selesaikan login.")
            input("Jika sudah selesai, kembali ke terminal lalu tekan Enter: ")

            return True

        except Exception as exc:
            console.print(f"[bold red]Gagal membuka JobStreet: {exc}[/]")
            return False

    def search_jobs(self, keyword: str, page: int = 1) -> List[Dict]:
        """Membuka hasil pencarian dan membaca lowongan yang dapat dikenali."""
        jobs: List[Dict] = []
        seen_urls = set()

        try:
            params = {"keywords": keyword}

            if config.location:
                params["where"] = config.location

            if page > 1:
                params["page"] = str(page)

            url = f"{config.search_url}?{urlencode(params)}"

            console.print(f"[bold cyan]Mencari: {keyword} — halaman {page}[/]")
            self.driver.get(url)
            self.wait.until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)

            cards = self.driver.find_elements(By.CSS_SELECTOR, "article")

            if not cards:
                cards = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "[data-automation='normalJob']"
                )

            for card in cards:
                try:
                    job = self._parse_job_card(card)
                    if not job:
                        continue

                    if job["url"] in seen_urls:
                        continue

                    seen_urls.add(job["url"])
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
        """Membaca satu kartu lowongan. Kartu tanpa judul atau URL akan dilewati."""
        selectors = (
            "a[data-automation*='jobTitle']",
            "a[href*='/job/']",
            "a[href*='/job-']",
        )

        links = []
        for selector in selectors:
            try:
                links.extend(card.find_elements(By.CSS_SELECTOR, selector))
            except Exception:
                continue

        title = ""
        job_url = ""

        for link in links:
            href = link.get_attribute("href")
            if not href:
                continue

            possible_titles = [
                link.text,
                link.get_attribute("aria-label"),
                link.get_attribute("title"),
                link.get_attribute("textContent"),
            ]

            candidate_title = next(
                (
                    value.strip()
                    for value in possible_titles
                    if value and value.strip()
                ),
                "",
            )

            if candidate_title:
                title = candidate_title
                job_url = urljoin(self.driver.current_url, href)
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
    def _read_card_value(card, selectors: List[str]) -> str:
        for selector in selectors:
            try:
                element = card.find_element(By.CSS_SELECTOR, selector)
                value = element.text or element.get_attribute("textContent") or ""
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
        """Membuat ID stabil agar lowongan yang sama tidak berubah ID tiap dijalankan."""
        match = re.search(r"/job(?:/|-)(\d+)", url, re.IGNORECASE)

        if match:
            return match.group(1)

        clean_url = url.split("?", 1)[0].rstrip("/")
        return hashlib.sha256(clean_url.encode("utf-8")).hexdigest()[:24]

    def apply_job(self, job: Dict) -> bool:
        """
        Membuka halaman lowongan untuk ditinjau.
        Pengguna sendiri yang menekan Apply dan Submit di browser.
        """
        title = (job.get("title") or "").strip()
        job_url = (job.get("url") or "").strip()
        job_id = (job.get("job_id") or "").strip()

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

            console.print(f"\n[bold magenta]{title}[/]")
            console.print(f"Perusahaan: {job.get('company', 'Tidak diketahui')}")
            console.print(f"URL: {job_url}")
            console.print(
                "[cyan]Tinjau persyaratan di Chrome. "
                "Jika cocok, lakukan Apply dan Submit sendiri.[/]"
            )

            input("Setelah selesai meninjau halaman, tekan Enter di terminal: ")
            submitted = input(
                "Apakah Anda benar-benar sudah mengirim lamaran? [y/N]: "
            ).strip().lower()

            if submitted in ("y", "ya"):
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

            console.print("[blue]Chrome ditutup.[/]")