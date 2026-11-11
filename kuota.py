"""Kuota lamaran harian — dihitung **per situs**.

Aturan pemakai (2026-11-11): setiap situs wajib mengirim **50 lamaran per
hari**. Angka 50 bukan lagi batas bersama yang dibagi JobStreet/Glints/Indeed,
melainkan target sekaligus batas atas untuk **masing-masing** situs:

* JobStreet 50, Glints 50, Indeed 50 (masing-masing punya hitungan sendiri);
* hitungan diambil dari lamaran yang benar-benar terkirim hari ini (WIB);
* nilai `MAX_APPLY_PER_DAY=0` berarti tanpa batas untuk semua situs.

Karena satu situs tidak lagi memakan jatah situs lain, Glints tetap bisa
mencapai 50 walau JobStreet sudah 50.

Objek database dan konfigurasi bisa diberikan oleh pemanggil (dipakai tes agar
tidak menyentuh database asli).
"""


from config import config
from database import db

SITUS_BAKU = ("jobstreet", "glints", "indeed")
NAMA_SITUS = {
    "jobstreet": "JobStreet",
    "glints": "Glints",
    "indeed": "Indeed",
}


def batas(cfg=None) -> int:
    """Batas/target harian per situs (0 = tanpa batas)."""
    cfg = cfg or config
    return max(0, int(getattr(cfg, "max_apply_per_day", 0) or 0))


def target(cfg=None) -> int:
    """Nama lain `batas()`: angka yang wajib dicapai tiap situs hari ini."""
    return batas(cfg)


def _hitung(db_obj, situs: str) -> int:
    """Lamaran hari ini untuk satu situs (atau semua bila `situs` kosong)."""
    try:
        return int(db_obj.get_today_apply_count(situs) or 0)
    except TypeError:
        # Objek database lama/palsu yang belum menerima parameter situs.
        return int(db_obj.get_today_apply_count() or 0)


def terpakai(db_obj=None, situs: str = "") -> int:
    """Lamaran yang sudah terkirim hari ini (untuk satu situs bila diisi)."""
    return _hitung(db_obj or db, situs)


def tanpa_batas(cfg=None) -> bool:
    return batas(cfg) <= 0


def sisa(db_obj=None, cfg=None, situs: str = "") -> int | None:
    """Sisa slot situs ini hari ini; None bila tanpa batas."""
    batas_harian = batas(cfg)

    if batas_harian <= 0:
        return None

    return max(0, batas_harian - terpakai(db_obj or db, situs))


def kurang(db_obj=None, cfg=None, situs: str = "") -> int:
    """Berapa lamaran lagi yang dibutuhkan situs ini untuk mencapai target."""
    sisa_hari_ini = sisa(db_obj, cfg, situs)
    return 0 if sisa_hari_ini is None else sisa_hari_ini


def habis(db_obj=None, cfg=None, situs: str = "") -> bool:
    sisa_hari_ini = sisa(db_obj, cfg, situs)
    return sisa_hari_ini is not None and sisa_hari_ini <= 0


def ringkasan(db_obj=None, cfg=None, situs: str = "") -> str:
    """Kalimat kuota untuk satu situs (atau gabungan bila situs kosong)."""
    nama = NAMA_SITUS.get(str(situs or "").lower(), "")
    awalan = f"Kuota {nama}: " if nama else "Kuota harian: "

    if tanpa_batas(cfg):
        return f"{awalan}tanpa batas (MAX_APPLY_PER_DAY=0)."

    return (
        f"{awalan}{terpakai(db_obj, situs)} sudah dilamar hari ini, "
        f"sisa {sisa(db_obj, cfg, situs)} dari {batas(cfg)}."
    )


def ringkasan_situs(db_obj=None, cfg=None, daftar=SITUS_BAKU) -> list[dict]:
    """Angka kuota tiap situs, siap ditampilkan sebagai tabel."""
    hasil = []

    for nama in daftar:
        sisa_hari_ini = sisa(db_obj, cfg, nama)
        hasil.append(
            {
                "situs": nama,
                "nama": NAMA_SITUS.get(nama, nama.title()),
                "terpakai": terpakai(db_obj, nama),
                "batas": batas(cfg),
                "sisa": sisa_hari_ini,
                "tercapai": sisa_hari_ini == 0 if sisa_hari_ini is not None else None,
            }
        )

    return hasil


def potong(kandidat: list[dict], db_obj=None, cfg=None, situs: str = "") -> list[dict]:
    """Batasi kandidat sesuai sisa kuota situs ini (tanpa batas = utuh)."""
    sisa_hari_ini = sisa(db_obj, cfg, situs)

    if sisa_hari_ini is None:
        return list(kandidat)

    return list(kandidat)[:sisa_hari_ini]


def pesan_habis(situs: str = "") -> str:
    nama = NAMA_SITUS.get(str(situs or "").lower(), "")
    siapa = f" {nama}" if nama else ""

    return (
        f"Kuota{siapa} hari ini sudah habis. Tidak ada lamaran dikirim. "
        "Kuota dihitung per situs, jadi situs lain tetap bisa jalan."
    )
