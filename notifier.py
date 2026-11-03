import requests
from config import config
from rich.console import Console

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
                "text": message,
                "parse_mode": "HTML"
            }
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            console.print(f"[yellow]Notifikasi gagal: {e}[/]")

    def send_apply_success(self, job: dict):
        msg = (
            "Berhasil Apply!\n\n"
            f"Posisi: {job['title']}\n"
            f"Perusahaan: {job.get('company', 'N/A')}\n"
            f"Lokasi: {job.get('location', 'N/A')}\n"
            f"Gaji: {job.get('salary', 'N/A')}\n"
            f"Link: {job.get('url', '')}"
        )
        self.send(msg)

    def send_daily_report(self, stats: dict):
        msg = (
            "Laporan Harian\n\n"
            f"Total job ditemukan: {stats['total_jobs_found']}\n"
            f"Total sudah apply: {stats['total_applied']}\n"
            f"Apply hari ini: {stats['today_applied']}\n"
        )
        self.send(msg)

    def send_error(self, error_msg: str):
        self.send(f"Error: {error_msg}")


notifier = Notifier()