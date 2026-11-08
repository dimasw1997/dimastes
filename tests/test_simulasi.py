"""Simulasi offline harus selalu sesuai harapan."""

import simulasi


def test_semua_skenario_simulasi_sesuai():
    assert simulasi.jalankan() is True
