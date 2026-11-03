from pathlib import Path

import pytest

from env_tools import baca_baku, perbarui_env, perbarui_nilai


def test_baca_baku_abaikan_komentar():
    teks = "# komentar\nKEYWORDS=a,b\n\nTITLE_KEYWORDS=c\n"
    assert baca_baku(teks) == {"KEYWORDS": "a,b", "TITLE_KEYWORDS": "c"}


def test_perbarui_nilai_pertahankan_baris_lain_dan_crlf():
    teks = "KEYWORDS=lama\r\nCOVER_LETTER=isi saya\r\n"
    baru, perubahan = perbarui_nilai(teks, {"KEYWORDS": "baru"})

    assert perubahan == ["KEYWORDS"]
    assert baru == "KEYWORDS=baru\r\nCOVER_LETTER=isi saya\r\n"


def test_perbarui_nilai_tambah_kunci_yang_belum_ada():
    baru, perubahan = perbarui_nilai("KEYWORDS=lama\n", {"TITLE_KEYWORDS": "x"})

    assert perubahan == ["TITLE_KEYWORDS"]
    assert baru == "KEYWORDS=lama\nTITLE_KEYWORDS=x\n"


def test_perbarui_nilai_tanpa_perubahan():
    teks = "KEYWORDS=sama\n"
    baru, perubahan = perbarui_nilai(teks, {"KEYWORDS": "sama"})

    assert perubahan == []
    assert baru == teks


def test_perbarui_env_membuat_cadangan(tmp_path):
    contoh = tmp_path / ".env.example"
    contoh.write_text("KEYWORDS=baru\nTITLE_KEYWORDS=judul\n", encoding="utf-8")

    env = tmp_path / ".env"
    env.write_text("KEYWORDS=lama\nCOVER_LETTER=hai\n", encoding="utf-8")

    hasil = perbarui_env(env, contoh)

    assert hasil["status"] == "diperbarui"
    assert set(hasil["perubahan"]) == {"KEYWORDS", "TITLE_KEYWORDS"}
    assert Path(hasil["backup"]).read_text(encoding="utf-8") == (
        "KEYWORDS=lama\nCOVER_LETTER=hai\n"
    )
    assert env.read_text(encoding="utf-8") == (
        "KEYWORDS=baru\nCOVER_LETTER=hai\nTITLE_KEYWORDS=judul\n"
    )


def test_perbarui_env_tidak_menimpa_isian_pengguna(tmp_path):
    contoh = tmp_path / ".env.example"
    contoh.write_text(
        "KEYWORDS=baru\nAUTO_ANSWER_QUESTIONS=true\n"
        "EXPECTED_SALARY=5000000\nYEARS_EXPERIENCE=3\n",
        encoding="utf-8",
    )

    env = tmp_path / ".env"
    env.write_text(
        "KEYWORDS=lama\nEXPECTED_SALARY=7000000\n", encoding="utf-8"
    )

    perbarui_env(env, contoh)
    isi = env.read_text(encoding="utf-8")

    assert "KEYWORDS=baru" in isi
    assert "EXPECTED_SALARY=7000000" in isi
    assert "AUTO_ANSWER_QUESTIONS=true" in isi
    assert "YEARS_EXPERIENCE=3" in isi
