import argparse
import subprocess

from rich.console import Console
from rich.table import Table

from config import config
from database import db

console = Console()


def versi_kode() -> str:
    """Commit yang sedang dijalankan — untuk memastikan kode sudah terbaru."""
    try:
        hasil = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if hasil.returncode == 0:
            return hasil.stdout.strip() or "-"
    except Exception:
        pass
    return "-"


def show_stats():
    stats = db.get_stats()
    table = Table(title="Statistik")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    for key, value in stats.items():
        table.add_row(key.replace("_", " ").title(), str(value))

    console.print(table)


def uji_lamar(url: str):
    """Uji alur lamaran untuk satu lowongan, tanpa pencarian/filter."""
    from auto_apply import AutoApplier
    from scraper import JobStreetBot

    console.print(f"[cyan]Versi kode:[/] {versi_kode()}")
    console.print(f"[cyan]Lowongan uji:[/] {url}")

    bot = JobStreetBot()
    try:
        bot.init_browser()
        if not bot.login():
            console.print("[bold red]Login belum selesai. Uji dibatalkan.[/]")
            return

        hasil = AutoApplier(bot.driver, bot.wait).apply(
            {"url": url, "title": "lowongan uji"}
        )
    finally:
        try:
            bot.close()
        except Exception:
            pass

    warna = "green" if hasil.applied else "yellow"
    console.print(
        f"\n[bold {warna}]Status:[/] {hasil.status} — {hasil.reason}"
    )
    if hasil.applied:
        console.print("[bold green]Lamaran terkirim otomatis.[/]")
    else:
        console.print(
            "[dim]Bila perlu, kirim file di folder debug/ (png + txt) untuk "
            "perbaikan selector.[/]"
        )


def perbarui_env():
    """Samakan KEYWORDS/TITLE_KEYWORDS di .env dengan daftar terbaru."""
    from pathlib import Path

    from env_tools import perbarui_env as jalan

    hasil = jalan(Path(".env"), Path(".env.example"))

    if hasil["status"] == "contoh_tidak_ada":
        console.print("[bold red].env.example tidak ditemukan.[/]")
        return

    if hasil["status"] == "tidak_ada_kunci":
        console.print("[bold red].env.example tidak memuat KEYWORDS.[/]")
        return

    if hasil["status"] == "sudah_terbaru":
        console.print("[green].env sudah memakai daftar kata kunci terbaru.[/]")
        return

    console.print(
        "[bold green]Kata kunci di .env diperbarui:[/] "
        + ", ".join(hasil["perubahan"])
    )
    if hasil["backup"]:
        console.print(f"[dim]Cadangan file lama: {hasil['backup']}[/]")
    console.print(
        "[dim]Jalankan ulang program agar nilai baru terpakai.[/]"
    )


def simulasi():
    """Uji alur lamaran dengan halaman palsu (tanpa Chrome/internet)."""
    from simulasi import jalankan

    if not jalankan():
        raise SystemExit(1)


def atur_env(pasangan_teks):
    """Ubah nilai tertentu di .env, mis. MAX_APPLY_PER_DAY=500."""
    from pathlib import Path

    from env_tools import atur_nilai, parse_pasangan

    try:
        pasangan = parse_pasangan(pasangan_teks)
    except ValueError as exc:
        console.print(f"[bold red]{exc}[/]")
        raise SystemExit(2) from None

    hasil = atur_nilai(Path(".env"), pasangan)

    if hasil["status"] == "sudah_terbaru":
        console.print("[green].env sudah memakai nilai tersebut.[/]")
        return

    console.print(
        "[bold green]Nilai di .env diperbarui:[/] "
        + ", ".join(hasil["perubahan"])
    )
    if hasil["backup"]:
        console.print(f"[dim]Cadangan file lama: {hasil['backup']}[/]")
    console.print("[dim]Jalankan ulang program agar nilai baru terpakai.[/]")


def show_config():
    table = Table(title="Konfigurasi")
    table.add_column("Pengaturan", style="cyan")
    table.add_column("Nilai", style="green")

    table.add_row("Kata kunci", ", ".join(config.keywords))
    table.add_row(
        "Lokasi pencarian",
        ", ".join(config.locations) if config.locations else "(semua)",
    )
    table.add_row(
        "Filter judul minat",
        (
            f"Aktif ({len(config.title_keywords)} kata kunci)"
            if config.require_keyword_match
            else "Tidak aktif"
        ),
    )
    table.add_row(
        "Filter lokasi ketat",
        "Aktif" if config.strict_location else "Tidak aktif",
    )
    table.add_row(
        "Pertanyaan pilihan otomatis",
        (
            "Aktif "
            f"(S1, {config.years_experience:g} th, gaji "
            f"{config.expected_salary or 'tidak dijawab'})"
            if config.auto_answer_questions
            else "Tidak aktif"
        ),
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
    table.add_row(
        "Urutan pelamaran",
        (
            "Kumpulkan dulu, mulai dari posting terbaru"
            if config.auto_apply and config.collect_before_apply
            else "Lamar sambil mencari (halaman terbaru dulu)"
        ),
    )
    table.add_row(
        "Batas lamaran per hari",
        (
            str(config.max_apply_per_day)
            if config.max_apply_per_day > 0
            else "Tanpa batas"
        ),
    )
    table.add_row("Jeda antar-lowongan", f"{config.delay_between_apply} detik")
    table.add_row("Mode browser", "Headless" if config.headless else "Terlihat")
    table.add_row(
        "Mode lamaran",
        "Otomatis" if config.auto_apply else "Tinjau dan kirim manual",
    )
    if config.auto_apply:
        table.add_row(
            "Batas lamaran otomatis/sesi",
            (
                str(config.auto_apply_max_per_session)
                if config.auto_apply_max_per_session > 0
                else "Tanpa batas"
            ),
        )
        table.add_row(
            "Waktu kirim di halaman review",
            f"{config.auto_apply_submit_timeout} detik",
        )
    table.add_row("Versi kode (commit)", versi_kode())
    table.add_row("File database", config.db_path)
    table.add_row(
        "Notifikasi Telegram",
        "Aktif" if config.telegram_token and config.telegram_chat_id
        else "Tidak aktif",
    )

    console.print(table)


def blacklist_company(company: str, reason: str = ""):
    db.add_blacklist(company, reason)
    console.print(f"[green]{company} di-blacklist[/]")
    console.print(
        "[dim]Nama dicocokkan longgar: \"royal abadi\" juga menangkap "
        "\"PT Royal Abadi Sejahtera\", \"PT. ROYAL ABADI SEJAHTERA\", "
        "dst.[/]"
    )


def show_applications(limit: int = 50):
    rows = db.get_recent_applications(limit)

    table = Table(title=f"Riwayat Lamaran ({limit} terakhir)")
    table.add_column("Tanggal", style="cyan", no_wrap=True)
    table.add_column("Posisi", style="white")
    table.add_column("Perusahaan", style="yellow")
    table.add_column("Status", style="green", no_wrap=True)

    if not rows:
        console.print("[dim]Belum ada lamaran yang tercatat.[/]")
        return

    for row in rows:
        table.add_row(
            row["applied_at"][:19],
            row["title"][:40],
            row["company"][:25],
            row["status"],
        )

    console.print(table)


def repair_data():
    report = db.repair_data()

    table = Table(title="Perbaikan Data")
    table.add_column("Perbaikan", style="cyan")
    table.add_column("Jumlah", style="green", justify="right")

    table.add_row("Judul kosong diisi", str(report["empty_titles_fixed"]))
    table.add_row("Perusahaan kosong diisi", str(report["empty_companies_fixed"]))
    table.add_row("Status dinormalkan", str(report["statuses_normalized"]))
    table.add_row(
        "Lamaran ganda dihapus",
        str(report["duplicate_applications_removed"]),
    )

    console.print(table)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JobStreet Auto-Apply CLI")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Jalankan pencarian lowongan")
    run_mode = run_parser.add_mutually_exclusive_group()
    run_mode.add_argument(
        "--auto",
        action="store_true",
        help="Kirim lamaran otomatis (tanpa klik manual)",
    )
    run_mode.add_argument(
        "--manual",
        action="store_true",
        help="Buka lowongan untuk ditinjau dan dikirim manual (default)",
    )
    run_parser.add_argument(
        "--max-age-days",
        type=int,
        default=None,
        help="Hanya lowongan yang diposting dalam N hari terakhir",
    )
    run_parser.add_argument(
        "--locations",
        default=None,
        help="Daftar lokasi dipisah koma, mis. \"Bandung,Jakarta,Tangerang\"",
    )
    run_parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Jumlah halaman hasil pencarian per kata kunci",
    )
    run_parser.add_argument(
        "--headless",
        action="store_true",
        help="Jalankan Chrome tanpa jendela",
    )
    run_parser.add_argument(
        "--profile-dir",
        default=None,
        help="Folder profil Chrome untuk menyimpan sesi login",
    )
    run_parser.add_argument(
        "--no-profile",
        action="store_true",
        help="Pakai profil sementara (harus login ulang setiap sesi)",
    )
    run_parser.add_argument(
        "--no-login-wait",
        action="store_true",
        help="Jangan menunggu Enter saat login; berhenti bila belum login",
    )
    subparsers.add_parser("stats", help="Tampilkan statistik")
    subparsers.add_parser("config", help="Tampilkan konfigurasi aktif")
    subparsers.add_parser("repair", help="Rapikan data lama di database")
    subparsers.add_parser(
        "simulasi",
        help="Uji alur lamaran dengan halaman palsu (tanpa Chrome)",
    )
    subparsers.add_parser(
        "perbarui-env",
        help="Perbarui KEYWORDS/TITLE_KEYWORDS di .env dari .env.example",
    )

    history_parser = subparsers.add_parser(
        "history", help="Tampilkan riwayat lamaran"
    )
    history_parser.add_argument(
        "--limit", type=int, default=50, help="Jumlah baris (default 50)"
    )

    uji_parser = subparsers.add_parser(
        "uji-lamar",
        help="Uji alur lamaran untuk satu URL lowongan (tanpa filter)",
    )
    uji_parser.add_argument("--url", required=True, help="URL lowongan JobStreet")

    env_parser = subparsers.add_parser(
        "set-env",
        help="Ubah nilai di .env, mis. set-env MAX_APPLY_PER_DAY=500",
    )
    env_parser.add_argument(
        "pasangan",
        nargs="+",
        help="Satu atau beberapa KUNCI=nilai",
    )

    bl_parser = subparsers.add_parser("blacklist", help="Blacklist company")
    bl_parser.add_argument("company", help="Nama company")
    bl_parser.add_argument("--reason", default="", help="Alasan")

    args = parser.parse_args()

    if args.command == "run":
        if args.auto:
            config.auto_apply = True
        elif args.manual:
            config.auto_apply = False

        if args.locations:
            lokasi = [
                item.strip() for item in args.locations.split(",") if item.strip()
            ]
            if lokasi:
                config.locations = lokasi
                config.location = lokasi[0]

        if args.max_age_days is not None:
            config.max_age_days = max(0, args.max_age_days)

        if args.max_pages is not None:
            config.max_pages = max(1, args.max_pages)

        if args.headless:
            config.headless = True

        if args.profile_dir:
            config.profile_dir = args.profile_dir
            config.use_profile = True

        if args.no_profile:
            config.use_profile = False

        if args.no_login_wait:
            config.login_wait = False

        from main import main

        main()
    elif args.command == "stats":
        show_stats()
    elif args.command == "config":
        show_config()
    elif args.command == "repair":
        repair_data()
    elif args.command == "perbarui-env":
        perbarui_env()
    elif args.command == "simulasi":
        simulasi()
    elif args.command == "set-env":
        atur_env(args.pasangan)
    elif args.command == "history":
        show_applications(args.limit)
    elif args.command == "uji-lamar":
        uji_lamar(args.url)
    elif args.command == "blacklist":
        blacklist_company(args.company, args.reason)
    else:
        parser.print_help()
