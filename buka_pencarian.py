"""Membuka tab pencarian JobStreet untuk beberapa kata kunci sekaligus.

Skrip ringan ini tidak butuh Selenium: cukup browser default Anda.
"""

import csv
import os
import time
import webbrowser
from datetime import date
from urllib.parse import quote_plus

from config import config

TRACKER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "catatan_lamaran.csv")


def buat_tracker():
    if not os.path.exists(TRACKER):
        with open(TRACKER, "w", newline="", encoding="utf-8-sig") as file:
            csv.writer(file).writerow(
                ["Tanggal", "Posisi", "Perusahaan", "Link", "Status", "Catatan"]
            )
        print(f"File {TRACKER} dibuat. Buka dengan Excel dan isi manual.")
    else:
        print(f"File {TRACKER} sudah ada.")


def buka_pencarian(delay: float = 1.0):
    """Membuka satu tab per kata kunci, berurutan dari .env."""
    keywords = [keyword for keyword in config.keywords if keyword.strip()]

    if not keywords:
        print("KEYWORDS di .env masih kosong.")
        return

    for index, keyword in enumerate(keywords, start=1):
        url = (
            f"{config.search_url}"
            f"?keywords={quote_plus(keyword)}"
            f"&where={quote_plus(config.location)}"
        )
        print(f"[{index}/{len(keywords)}] Membuka: {keyword}")
        webbrowser.open_new_tab(url)

        # Jeda kecil supaya browser tidak dianggap memblokir pop-up.
        if index < len(keywords):
            time.sleep(delay)


if __name__ == "__main__":
    print("Tanggal:", date.today())
    print("Lokasi:", config.location)
    buat_tracker()
    buka_pencarian()
    print("Selesai. Periksa tab di browser Anda.")
