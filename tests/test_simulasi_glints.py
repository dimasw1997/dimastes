"""Uji skenario simulasi Glints lewat jalur yang sama dengan `cli glints simulasi`."""

import pytest

import simulasi_glints
from config import config
from simulasi_glints import SKENARIO, _cocok, _siapkan


@pytest.mark.parametrize(
    "fungsi", [fungsi for _, fungsi in SKENARIO], ids=[nama for nama, _ in SKENARIO]
)
def test_skenario_glints(fungsi, monkeypatch):
    monkeypatch.setattr(config, "cover_letter", "Saya tertarik dengan posisi ini.")
    monkeypatch.setattr(config, "auto_apply_debug", False)

    pulihkan = _siapkan()
    try:
        hasil, harapan, _ = fungsi()
    finally:
        pulihkan()

    assert _cocok(hasil, harapan), f"{hasil.status}: {hasil.reason}"


def test_semua_skenario_lulus(monkeypatch):
    monkeypatch.setattr(config, "auto_apply_debug", False)
    assert simulasi_glints.jalankan() is True
