"""Profil Chrome antar-situs: tunggu sampai Chrome sebelumnya melepas profil.

Latar belakang (log 12 Nov 2026): setelah JobStreet, Glints gagal membuka
profil yang sama ("Chrome instance exited") lalu turun ke profil baru yang
belum login, sehingga sesi Glints berakhir tanpa satu lamaran pun.
"""

from pathlib import Path

import browser


def _profil(tmp_path) -> Path:
    folder = tmp_path / "chrome-profile"
    folder.mkdir()
    return folder


def test_profil_tanpa_kunci_tidak_terkunci(tmp_path):
    assert browser.profil_terkunci(_profil(tmp_path)) is False


def test_profil_dengan_berkas_kunci_terkunci(tmp_path):
    profil = _profil(tmp_path)
    (profil / "SingletonLock").write_text("")

    assert browser.profil_terkunci(profil) is True


def test_profil_belum_ada_dianggap_bebas(tmp_path):
    assert browser.profil_terkunci(tmp_path / "belum-ada") is False


def test_tunggu_profil_bebas_langsung_true(tmp_path):
    assert browser.tunggu_profil_bebas(_profil(tmp_path), batas_detik=0.2) is True


def test_tunggu_profil_bebas_habis_waktu(tmp_path):
    profil = _profil(tmp_path)
    (profil / "lockfile").write_text("")

    assert (
        browser.tunggu_profil_bebas(profil, batas_detik=0.2, jeda=0.05) is False
    )


def test_kunci_dibersihkan_membuat_profil_bebas(tmp_path):
    profil = _profil(tmp_path)
    (profil / "SingletonLock").write_text("")
    (profil / "DevToolsActivePort").write_text("")

    dihapus = browser.bersihkan_kunci_profil(profil)

    assert sorted(dihapus) == ["DevToolsActivePort", "SingletonLock"]
    assert browser.profil_terkunci(profil) is False
