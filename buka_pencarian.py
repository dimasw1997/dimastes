"""Membuka tab pencarian JobStreet untuk beberapa lokasi dan kata kunci.

Skrip ringan ini tidak butuh Selenium: cukup browser default Anda.
"""

import argparse
import csv
import os
import time
import webbrowser
from datetime import date
from urllib.parse import quote_plus

from config import config

TRACKER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "catatan_lamaran.csv"
)


def buat_tracker():
    if not os.path.exists(TRACKER):
        with open(TRACKER, "w", newline="", encoding="utf-8-sig") as file:
            csv.writer(file).writerow(
                ["Tanggal", "Posisi", "Perusahaan", "Link", "Status", "Catatan"]
            )
        print(f"File {TRACKER} dibuat. Buka dengan Excel dan isi manual.")
    else:
        print(f"File {TRACKER} sudah ada.")


def buat_url(keyword: str, location: str) -> str:
    params = f"keywords={quote_plus(keyword)}"

    if location:
        params += f"&where={quote_plus(location)}"

    if config.sort_mode:
        params += f"&sortmode={quote_plus(config.sort_mode)}"

    return f"{config.search_url}?{params}"


def buka_pencarian(
    locations=None,
    keywords=None,
    delay: float = 1.0,
    max_tabs: int = 24,
) -> int:
    """Buka tab pencarian. Mengembalikan jumlah tab yang dibuka."""
    daftar_kata = [
        kata.strip()
        for kata in (keywords or config.keywords)
        if kata and kata.strip()
    ]
    daftar_lokasi = [
        loc.strip() for loc in (locations or config.locations) if loc.strip()
    ] or [""]

    if not daftar_kata:
        print("KEYWORDS di .env masih kosong.")
        return 0

    total = 0

    for location in daftar_lokasi:
        for keyword in daftar_kata:
            if total >= max_tabs:
                print(
                    f"Batas {max_tabs} tab tercapai. Sisa pencarian dilewati; "
                    "naikkan dengan --max-tabs bila perlu."
                )
                return total

            print(f"[{total + 1}] {location or 'semua lokasi'}: {keyword}")
            webbrowser.open_new_tab(buat_url(keyword, location))
            total += 1

            # Jeda kecil supaya browser tidak menganggapnya pop-up.
            if delay and total < max_tabs:
                time.sleep(delay)

    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Buka tab pencarian JobStreet"
    )
    parser.add_argument(
        "--locations",
        default=None,
        help='Daftar lokasi dipisah koma, mis. "Bandung,Jakarta,Tangerang"',
    )
    parser.add_argument(
        "--max-tabs", type=int, default=24, help="Batas jumlah tab (default 24)"
    )
    parser.add_argument(
        "--delay", type=float, default=1.0, help="Jeda antar tab dalam detik"
    )
    args = parser.parse_args()

    lokasi = None
    if args.locations:
        lokasi = [
            item.strip() for item in args.locations.split(",") if item.strip()
        ]

    print("Tanggal:", date.today())
    print("Lokasi:", ", ".join(lokasi or config.locations))
    buat_tracker()
    jumlah = buka_pencarian(
        locations=lokasi,
        delay=max(0.0, args.delay),
        max_tabs=max(1, args.max_tabs),
    )
    print(f"Selesai. {jumlah} tab dibuka. Periksa browser Anda.")
