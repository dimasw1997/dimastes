import html

import requests
from rich.console import Console

from config import config

console = Console()


class Notifier:
    def __init__(self):
        self.enabled = bool(config.telegram_token and config.telegram_chat_id)

    def send(self, message: str):
        if not self.enabled:
            return

        try:
            url = f"https://api.telegram.org/bot{config.telegram_token}/sendMessage"
            payload = {
                "chat_id": config.telegram_chat_id,
                # Pesan di-escape karena parse_mode=HTML; tanpa escape,
                # karakter seperti "&" atau "<" membuat Telegram menolak.
                "text": html.escape(str(message)),
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
            response = requests.post(url, json=payload, timeout=10)

            if response.status_code >= 400:
                console.print(
                    f"[yellow]Notifikasi gagal (HTTP {response.status_code}).[/]"
                )

        except Exception as exc:
            console.print(f"[yellow]Notifikasi gagal: {exc}[/]")

    def send_apply_success(self, job: dict):
        msg = (
            "Berhasil Apply!\n\n"
            f"Posisi: {job.get('title', 'N/A')}\n"
            f"Perusahaan: {job.get('company', 'N/A')}\n"
            f"Lokasi: {job.get('location', 'N/A')}\n"
            f"Gaji: {job.get('salary', 'N/A')}\n"
            f"Link: {job.get('url', '')}"
        )
        self.send(msg)

    def send_daily_report(self, stats: dict):
        msg = (
            "Laporan Harian\n\n"
            f"Total job ditemukan: {stats.get('total_jobs_found', 0)}\n"
            f"Total sudah apply: {stats.get('total_applied', 0)}\n"
            f"Apply hari ini: {stats.get('today_applied', 0)}"
        )
        self.send(msg)

    def send_error(self, error_msg: str):
        self.send(f"Error: {error_msg}")


notifier = Notifier()
