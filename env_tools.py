"""Alat bantu memperbarui nilai di file .env tanpa menimpa isian lain."""

from pathlib import Path

# Kunci yang isinya boleh diganti otomatis dari .env.example saat daftar
# kata kunci diperbarui. Kunci lain (token, path CV, cover letter) tidak
# pernah disentuh.
KUNCI_KATA_KUNCI = ("KEYWORDS", "TITLE_KEYWORDS")

# Kunci baru yang ditambahkan hanya bila belum ada di .env, sehingga isian
# yang sudah Anda sesuaikan sendiri tidak pernah tertimpa.
KUNCI_TAMBAHAN = (
    "BLACKLIST_COMPANIES",
    "COLLECT_BEFORE_APPLY",
    "AUTO_ANSWER_QUESTIONS",
    "AUTO_ANSWER_YES",
    "EXPECTED_SALARY",
    "YEARS_EXPERIENCE",
    "EDUCATION_LEVEL",
)


def baca_baku(teks: str) -> dict:
    """Ambil pasangan KUNCI=nilai dari isi .env."""
    hasil = {}
    for baris in teks.splitlines():
        baris = baris.strip()
        if not baris or baris.startswith("#") or "=" not in baris:
            continue
        kunci, _, nilai = baris.partition("=")
        kunci = kunci.strip()
        if kunci:
            hasil[kunci] = nilai.strip()
    return hasil


def perbarui_nilai(teks_env: str, nilai_baru: dict, hanya_tambah=()) -> tuple:
    """Ganti nilai kunci tertentu di isi .env.

    Kembalikan (teks_baru, daftar_perubahan). Baris lain, komentar, urutan,
    dan jenis akhir baris (LF/CRLF) dipertahankan.
    """
    akhir = "\r\n" if "\r\n" in teks_env else "\n"
    baris_baru = []
    perubahan = []
    sudah = set()

    for baris in teks_env.splitlines():
        utuh = baris.strip()

        if utuh and not utuh.startswith("#") and "=" in utuh:
            kunci, _, nilai_lama = utuh.partition("=")
            kunci = kunci.strip()
            nilai_lama = nilai_lama.strip()

            if kunci in nilai_baru:
                sudah.add(kunci)

                # Kunci pelengkap: jangan pernah menimpa isian pengguna.
                if kunci in hanya_tambah:
                    baris_baru.append(baris)
                    continue

                nilai_target = str(nilai_baru[kunci]).strip()
                if nilai_lama != nilai_target:
                    perubahan.append(kunci)
                baris_baru.append(f"{kunci}={nilai_target}")
                continue

        baris_baru.append(baris)

    # Kunci yang belum ada di .env ditambahkan di bagian akhir.
    for kunci, nilai in nilai_baru.items():
        if kunci in sudah:
            continue
        baris_baru.append(f"{kunci}={str(nilai).strip()}")
        perubahan.append(kunci)

    teks = akhir.join(baris_baru)
    if teks_env.endswith(("\n", "\r\n")):
        teks += akhir

    return teks, perubahan


def perbarui_env(
    path_env: Path,
    path_contoh: Path,
    kunci=KUNCI_KATA_KUNCI,
    kunci_tambahan=KUNCI_TAMBAHAN,
) -> dict:
    """Perbarui kunci kata kunci di .env dari .env.example.

    Mengembalikan ringkasan: {"status": ..., "perubahan": [...],
    "backup": path atau None}.
    """
    path_env = Path(path_env)
    path_contoh = Path(path_contoh)

    if not path_contoh.is_file():
        return {"status": "contoh_tidak_ada", "perubahan": [], "backup": None}

    contoh = baca_baku(path_contoh.read_text(encoding="utf-8"))
    nilai_baru = {k: contoh[k] for k in kunci if k in contoh}
    nilai_baru.update(
        {k: contoh[k] for k in kunci_tambahan if k in contoh}
    )

    if not nilai_baru:
        return {"status": "tidak_ada_kunci", "perubahan": [], "backup": None}

    if path_env.is_file():
        teks_lama = path_env.read_text(encoding="utf-8")
        backup = path_env.with_name(path_env.name + ".bak")
        backup.write_text(teks_lama, encoding="utf-8")
    else:
        teks_lama = ""
        backup = None

    teks_baru, perubahan = perbarui_nilai(
        teks_lama, nilai_baru, hanya_tambah=tuple(kunci_tambahan)
    )
    path_env.write_text(teks_baru, encoding="utf-8")

    return {
        "status": "diperbarui" if perubahan else "sudah_terbaru",
        "perubahan": perubahan,
        "backup": str(backup) if backup else None,
    }


# Batas yang harus berupa bilangan bulat positif.
KUNCI_ANGKA = ("MAX_APPLY_PER_DAY", "AUTO_APPLY_MAX_PER_SESSION")


def parse_pasangan(daftar) -> dict:
    """Ubah ["KUNCI=nilai", ...] menjadi dict, dengan validasi sederhana."""
    hasil = {}

    for item in daftar:
        teks = str(item or "")
        if "=" not in teks:
            raise ValueError(
                f"Format harus KUNCI=nilai (contoh MAX_APPLY_PER_DAY=500): {teks}"
            )

        kunci, _, nilai = teks.partition("=")
        kunci = kunci.strip().upper()
        nilai = nilai.strip()

        if not kunci:
            raise ValueError(f"Nama kunci kosong: {teks}")

        if kunci in KUNCI_ANGKA:
            try:
                angka = int(nilai)
            except ValueError:
                raise ValueError(
                    f"{kunci} harus berupa angka: {nilai}"
                ) from None
            if angka < 0:
                raise ValueError(
                    f"{kunci} minimal 0 (0 = tanpa batas)"
                )
            nilai = str(angka)

        hasil[kunci] = nilai

    return hasil


def atur_nilai(path_env: Path, pasangan: dict) -> dict:
    """Ganti/tambah nilai tertentu di .env (cadangan .env.bak)."""
    path_env = Path(path_env)
    teks_lama = (
        path_env.read_text(encoding="utf-8") if path_env.is_file() else ""
    )

    backup = None
    if path_env.is_file():
        backup = path_env.with_name(path_env.name + ".bak")
        backup.write_text(teks_lama, encoding="utf-8")

    teks_baru, perubahan = perbarui_nilai(teks_lama, pasangan)
    path_env.write_text(teks_baru, encoding="utf-8")

    return {
        "status": "diperbarui" if perubahan else "sudah_terbaru",
        "perubahan": perubahan,
        "backup": str(backup) if backup else None,
    }
