"""Jeda menunggu lanjut tanpa kehilangan perintah berhenti."""

import pytest

import kendali


def test_jeda_menunggu_sampai_lanjut(tmp_path, capsys):
    assert kendali.perintah("jeda", tmp_path)
    jumlah = []

    def tidur(_):
        jumlah.append(1)
        if len(jumlah) == 3:
            kendali.perintah("lanjut", tmp_path)

    kendali.periksa(tmp_path, tidur=tidur)
    assert len(jumlah) == 3
    keluaran = capsys.readouterr().out
    assert "Sesi dijeda" in keluaran
    assert "Sesi dilanjutkan" in keluaran


def test_stop_saat_dijeda(tmp_path):
    kendali.perintah("jeda", tmp_path)

    def tidur(_):
        kendali.perintah("stop", tmp_path)

    with pytest.raises(kendali.Berhenti):
        kendali.periksa(tmp_path, tidur=tidur)


def test_jeda_tidak_berakhir_otomatis_setelah_satu_jam(tmp_path, monkeypatch):
    kendali.perintah("jeda", tmp_path)
    waktu = iter([0, 3601, 3602, 3603])
    monkeypatch.setattr(kendali.time, "monotonic", lambda: next(waktu, 3603))
    hitung = []

    def tidur(_):
        hitung.append(1)
        if len(hitung) == 2:
            kendali.perintah("lanjut", tmp_path)

    kendali.periksa(tmp_path, tidur=tidur)
    assert len(hitung) == 2
