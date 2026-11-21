"""Simulasi offline harus selalu sesuai harapan."""

import simulasi
from config import config


def test_semua_skenario_simulasi_sesuai():
    assert simulasi.jalankan() is True


def test_simulasi_persingkat_log_tanpa_mengubah_waktu_sesi(monkeypatch, capsys):
    monkeypatch.setattr(config, "auto_answer_wait", 60)

    assert simulasi.jalankan() is True
    assert config.auto_answer_wait == 60
    keluaran = capsys.readouterr().out
    assert "tidak membuka Chrome" in keluaran
    assert "sisa 60 detik" not in keluaran
