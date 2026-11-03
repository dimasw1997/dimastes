import csv
import os
import webbrowser
from datetime import date
from urllib.parse import quote_plus

KEYWORDS = [
    "inventory control",
    "inventory controller",
    "PPIC",
    "production planner",
    "material planner",
    "material controller",
    "stock controller",
    "inventory analyst",
]
LOCATION = "Bandung"   # coba juga: "Cimahi" atau "Kabupaten Bandung"

TRACKER = "catatan_lamaran.csv"


def buat_tracker():
    if not os.path.exists(TRACKER):
        with open(TRACKER, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(
                ["Tanggal", "Posisi", "Perusahaan", "Link", "Status", "Catatan"]
            )
        print(f"File {TRACKER} dibuat. Buka dengan Excel dan isi manual.")
    else:
        print(f"File {TRACKER} sudah ada.")


def buka_pencarian():
    for kw in KEYWORDS:
        url = (
            "https://id.jobstreet.com/jobs"
            f"?keywords={quote_plus(kw)}&where={quote_plus(LOCATION)}"
        )
        print("Membuka:", kw)
        webbrowser.open_new_tab(url)


if __name__ == "__main__":
    print("Tanggal:", date.today())
    buat_tracker()
    buka_pencarian()
    print("Selesai. Periksa tab di browser Anda.")