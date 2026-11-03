import time

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config import config
from database import db
from job_filter import job_filter
from notifier import notifier
from scraper import JobStreetBot


console = Console()


class AutoApplyEngine:
    def __init__(self):
        self.bot = JobStreetBot()
        self.seen_job_ids = set()
        self.session_stats = {
            "found": 0,
            "new": 0,
            "applied": 0,
            "already": 0,
            "manual": 0,
            "skipped": 0,
            "errors": 0,
        }
        self.manual_jobs = []
        self.stop_requested = False

    def run(self):
        self._print_banner()
        self._print_config()

        if not config.auto_apply:
            console.print(
                "[bold yellow]Mode manual aktif: setiap lowongan akan "
                "menunggu Enter dan lamaran Anda kirim sendiri. "
                "Pakai `run --auto` (atau AUTO_APPLY=true di .env) untuk "
                "mengirim lamaran otomatis.[/]\n"
            )

        try:
            self.bot.init_browser()

            if not self.bot.login():
                console.print("[bold red]Login belum selesai. Program berhenti.[/]")
                return

            for location in config.locations:
                console.print(
                    f"\n[bold blue]{'#' * 60}[/]"
                )
                console.print(f"[bold blue]LOKASI: {location}[/]")
                console.print(f"[bold blue]{'#' * 60}[/]")

                for keyword in config.keywords:
                    keyword = keyword.strip()

                    if not keyword:
                        continue

                    console.print(f"\n{'=' * 60}")
                    console.print(
                        f"[bold]Lokasi: {location} — kata kunci: {keyword}[/]"
                    )
                    console.print(f"{'=' * 60}")

                    self._process_keyword(keyword, location=location)

                    if self.stop_requested:
                        break

                if self.stop_requested:
                    break

        except KeyboardInterrupt:
            console.print("\n[bold yellow]Proses dihentikan.[/]")

        except Exception as exc:
            console.print(f"[bold red]Terjadi error: {exc}[/]")
            self.session_stats["errors"] += 1
            notifier.send_error(str(exc))

        finally:
            self.bot.close()
            self._print_results()

            try:
                notifier.send_daily_report(db.get_stats())
            except Exception as exc:
                console.print(f"[yellow]Laporan harian gagal dikirim: {exc}[/]")

    def _process_keyword(self, keyword: str, location: str = ""):
        for page in range(1, config.max_pages + 1):
            if db.get_today_apply_count() >= config.max_apply_per_day:
                console.print(
                    f"[bold yellow]Batas harian tercapai "
                    f"({config.max_apply_per_day}).[/]"
                )
                return

            jobs = self.bot.search_jobs(keyword, page, location=location)

            if not jobs:
                console.print(f"Tidak ada lowongan terbaca di halaman {page}.")
                break

            # Lewati hasil duplikat atau yang tidak memiliki judul/URL/ID.
            new_jobs = []

            for job in jobs:
                title = (job.get("title") or "").strip()
                url = (job.get("url") or "").strip()
                job_id = str(job.get("job_id") or "").strip()

                if not title or not url or not job_id:
                    # Tandai supaya lowongan rusak yang sama tidak dihitung
                    # berkali-kali untuk setiap kata kunci.
                    kunci = job_id or url
                    if kunci:
                        self.seen_job_ids.add(kunci)

                    console.print(
                        "[yellow]Lowongan dilewati: judul, URL, atau ID tidak terbaca.[/]"
                    )
                    self.session_stats["skipped"] += 1
                    continue

                if job_id in self.seen_job_ids:
                    continue

                self.seen_job_ids.add(job_id)

                # Lowongan yang sudah berlabel Applied / sudah pernah dilamar
                # dilewati diam-diam: tidak ditampilkan dan tidak memakai kuota.
                if job.get("applied") or db.is_already_applied(job_id):
                    self.session_stats["already"] += 1

                    if job.get("applied"):
                        # Simpan detailnya supaya tetap tampil rapi di riwayat.
                        db.add_job(job)
                        db.record_application(
                            job_id,
                            "already_applied",
                            "Ditandai sudah dilamar di JobStreet",
                        )
                    continue

                # Lowongan lama yang belum pernah dilamar tetap ditinjau
                # kembali; yang benar-benar baru dihitung terpisah.
                if db.add_job(job):
                    self.session_stats["new"] += 1

                new_jobs.append(job)

            self.session_stats["found"] += len(new_jobs)

            if not new_jobs:
                continue

            # Hasil sudah diurutkan dari yang terbaru: begitu satu halaman
            # tidak memuat lowongan baru lagi, halaman berikutnya pasti lebih
            # lama dan sudah pernah diproses pada sesi ini.
            if page > 1 and len(new_jobs) == 0 and config.sort_mode:
                console.print(
                    "[dim]Halaman ini tidak memuat lowongan baru; "
                    "berhenti karena hasil diurutkan dari yang terbaru.[/]"
                )
                break

            eligible_jobs = []

            for job in new_jobs:
                try:
                    should_apply, reason = job_filter.should_apply(job)
                except Exception as exc:
                    console.print(
                        f"[yellow]Lowongan dilewati karena gagal diperiksa: {exc}[/]"
                    )
                    self.session_stats["errors"] += 1
                    continue

                if should_apply:
                    eligible_jobs.append(job)
                else:
                    title = job.get("title", "Tanpa judul")
                    console.print(
                        f"[dim]Dilewati: {title[:50]} — {reason}[/]"
                    )
                    self.session_stats["skipped"] += 1

            eligible_jobs = job_filter.rank_jobs(eligible_jobs)

            console.print(
                f"{len(eligible_jobs)} dari {len(new_jobs)} "
                "lowongan baru lolos filter."
            )

            for job in eligible_jobs:
                if db.get_today_apply_count() >= config.max_apply_per_day:
                    console.print(
                        "[bold yellow]Batas lamaran harian tercapai.[/]"
                    )
                    return

                if (
                    config.auto_apply
                    and self.session_stats["applied"]
                    >= config.auto_apply_max_per_session
                ):
                    console.print(
                        "[bold yellow]Batas lamaran otomatis per sesi "
                        f"({config.auto_apply_max_per_session}) tercapai. "
                        "Sisa lowongan dilewati.[/]"
                    )
                    return

                title = (job.get("title") or "").strip()

                try:
                    # Mode otomatis: bot mengirim lamaran sendiri.
                    # Mode manual: halaman dibuka untuk Anda tinjau.
                    hasil = self.bot.apply_job(job)

                except KeyboardInterrupt:
                    raise

                except Exception as exc:
                    console.print(
                        f"[bold red]Error saat memproses lowongan "
                        f"'{title}': {exc}[/]"
                    )
                    self.session_stats["errors"] += 1
                    continue

                if hasil.status == "login_required":
                    self.session_stats["errors"] += 1
                    self.stop_requested = True
                    console.print(
                        "[bold red]Sesi login JobStreet sudah habis. "
                        "Sesi dihentikan agar tidak menumpuk error.[/]"
                    )
                    notifier.send_error("Sesi login JobStreet habis")
                    return

                if hasil.applied:
                    self.session_stats["applied"] += 1
                    notifier.send_apply_success(job)

                elif hasil.status == "manual_required":
                    self.session_stats["manual"] += 1
                    self.manual_jobs.append((job, hasil.reason))

                else:
                    self.session_stats["skipped"] += 1

                delay = max(0, int(config.delay_between_apply))

                if delay:
                    console.print(
                        f"[dim]Jeda {delay} detik sebelum lowongan berikutnya...[/]"
                    )
                    time.sleep(delay)

    def _print_banner(self):
        banner = """
    ==========================================
        JobStreet Job Review System
    ==========================================
        """
        console.print(Panel(banner, style="bold blue"))

    def _print_config(self):
        table = Table(title="Konfigurasi", show_header=False)
        table.add_column("Pengaturan", style="cyan")
        table.add_column("Nilai", style="green")

        table.add_row("Kata kunci", ", ".join(config.keywords))
        table.add_row(
            "Lokasi pencarian",
            ", ".join(config.locations) if config.locations else "(semua)",
        )
        table.add_row(
            "Filter lokasi ketat",
            "Aktif" if config.strict_location else "Tidak aktif",
        )
        table.add_row("Gaji minimum", f"Rp {config.min_salary:,}")
        table.add_row("Batas pengalaman", f"{config.max_experience} tahun")
        table.add_row(
            "Urutan hasil",
            f"Dari yang terbaru ({config.sort_mode})"
            if config.sort_mode else "Relevansi JobStreet",
        )
        table.add_row(
            "Hanya lowongan baru",
            f"Maksimal {config.max_age_days} hari"
            if config.max_age_days > 0 else "Tanpa batas umur",
        )
        table.add_row("Halaman per kata kunci", str(config.max_pages))
        table.add_row("Batas lamaran per hari", str(config.max_apply_per_day))
        table.add_row("Jeda antar-lowongan", f"{config.delay_between_apply} detik")
        table.add_row(
            "Mode browser",
            "Headless" if config.headless else "Terlihat",
        )
        table.add_row(
            "Mode lamaran",
            "Otomatis" if config.auto_apply
            else "Tinjau dan kirim secara manual",
        )
        if config.auto_apply:
            table.add_row(
                "Batas lamaran otomatis/sesi",
                str(config.auto_apply_max_per_session),
            )
        table.add_row(
            "Notifikasi Telegram",
            "Aktif" if notifier.enabled else "Tidak aktif",
        )

        console.print(table)
        console.print()

    def _print_results(self):
        console.print(f"\n{'=' * 60}")

        table = Table(title="Hasil Sesi")
        table.add_column("Keterangan", style="cyan")
        table.add_column("Jumlah", style="green", justify="right")

        table.add_row("Lowongan diproses", str(self.session_stats["found"]))
        table.add_row(
            "Lowongan baru di database", str(self.session_stats["new"])
        )
        table.add_row(
            "Lamaran dikonfirmasi terkirim", str(self.session_stats["applied"])
        )
        table.add_row(
            "Sudah dilamar (dilewati)", str(self.session_stats["already"])
        )
        table.add_row(
            "Perlu dilamar manual", str(self.session_stats["manual"])
        )
        table.add_row(
            "Dilewati / tidak dikonfirmasi", str(self.session_stats["skipped"])
        )
        table.add_row("Error", str(self.session_stats["errors"]))

        try:
            stats = db.get_stats()
            table.add_row(
                "Total lowongan di database", str(stats["total_jobs_found"])
            )
            table.add_row("Total lamaran tercatat", str(stats["total_applied"]))
            table.add_row("Lamaran tercatat hari ini", str(stats["today_applied"]))
        except Exception as exc:
            console.print(f"[yellow]Statistik database tidak tersedia: {exc}[/]")

        console.print(table)

        if self.manual_jobs:
            console.print(
                "\n[bold yellow]Lowongan yang perlu Anda lamar manual:[/]"
            )
            for job, reason in self.manual_jobs:
                console.print(
                    f"  • {job.get('title')} — {job.get('company', '')}"
                )
                console.print(f"    {job.get('url')}  [dim]({reason})[/]")


def main():
    AutoApplyEngine().run()


if __name__ == "__main__":
    main()
