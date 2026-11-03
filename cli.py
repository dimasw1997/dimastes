import argparse
from rich.console import Console
from rich.table import Table
from database import db

console = Console()


def show_stats():
    stats = db.get_stats()
    table = Table(title="Statistik")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    for key, value in stats.items():
        table.add_row(key.replace("_", " ").title(), str(value))
    console.print(table)


def blacklist_company(company: str, reason: str = ""):
    db.add_blacklist(company, reason)
    console.print(f"[green]{company} di-blacklist[/]")


def show_applications():
    with db._get_conn() as conn:
        rows = conn.execute("""
            SELECT a.applied_at, j.title, j.company, a.status
            FROM applications a
            JOIN jobs j ON a.job_id = j.job_id
            ORDER BY a.applied_at DESC
            LIMIT 50
        """).fetchall()

    table = Table(title="Riwayat Lamaran (50 terakhir)")
    table.add_column("Tanggal", style="cyan")
    table.add_column("Posisi", style="white")
    table.add_column("Perusahaan", style="yellow")
    table.add_column("Status", style="green")

    for row in rows:
        table.add_row(
            row['applied_at'][:19],
            row['title'][:40],
            row['company'][:25],
            row['status']
        )
    console.print(table)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JobStreet Auto-Apply CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("run", help="Jalankan auto-apply")
    subparsers.add_parser("stats", help="Tampilkan statistik")
    subparsers.add_parser("history", help="Tampilkan riwayat lamaran")

    bl_parser = subparsers.add_parser("blacklist", help="Blacklist company")
    bl_parser.add_argument("company", help="Nama company")
    bl_parser.add_argument("--reason", default="", help="Alasan")

    args = parser.parse_args()

    if args.command == "run":
        from main import main
        main()
    elif args.command == "stats":
        show_stats()
    elif args.command == "history":
        show_applications()
    elif args.command == "blacklist":
        blacklist_company(args.company, args.reason)
    else:
        parser.print_help()