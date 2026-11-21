"""Audit live tidak boleh menavigasi atau berinteraksi dengan formulir."""

import pytest

import audit_form_live


class Layanan:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


class DriverBaca:
    def __init__(self, gagal=False):
        self.service = Layanan()
        self.panggilan = []
        self.gagal = gagal

    def execute_script(self, skrip):
        self.panggilan.append(skrip)
        if self.gagal:
            raise RuntimeError("gagal membaca")
        return {"situs": "glints.com", "kontrol": 2}


def test_audit_hanya_baca_dan_hentikan_driver(monkeypatch):
    driver = DriverBaca()
    monkeypatch.setattr(audit_form_live, "tempel_chrome", lambda port: driver)
    hasil = audit_form_live.audit(9222)
    assert hasil["kontrol"] == 2
    assert driver.panggilan == [audit_form_live.SKRIP_BACA]
    assert driver.service.stopped


def test_driver_dihentikan_saat_gagal(monkeypatch):
    driver = DriverBaca(gagal=True)
    monkeypatch.setattr(audit_form_live, "tempel_chrome", lambda port: driver)
    with pytest.raises(RuntimeError):
        audit_form_live.audit(9222)
    assert driver.service.stopped


def test_port_tidak_valid_tidak_menempel(monkeypatch):
    def tidak_boleh_dipanggil(port):
        pytest.fail("tidak boleh menempel")

    monkeypatch.setattr(audit_form_live, "tempel_chrome", tidak_boleh_dipanggil)
    with pytest.raises(ValueError):
        audit_form_live.audit(0)


def test_skrip_menghitung_kontrol_dan_status_aria():
    import json
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js tidak terpasang untuk uji skrip DOM")
    fixture = '''
    const location = {hostname: "id.jobstreet.com"};
    const make = (tag, attrs, checked = false) => ({
      tagName: tag, checked, getClientRects: () => [1],
      getAttribute: k => attrs[k] ?? null,
      hasAttribute: k => Object.hasOwn(attrs, k)
    });
    const elems = [make("INPUT", {type:"radio", required:""}, true),
      make("DIV", {role:"checkbox", "aria-checked":"false"}),
      make("INPUT", {type:"text", "aria-required":"true"}),
      make("INPUT", {type:"password"})];
    const document = {querySelectorAll: s => s === 'iframe' ? [1] : elems};
    const window = {getComputedStyle: () => ({visibility:'visible', display:'block'})};
    '''
    program = fixture + "console.log(JSON.stringify((function(){" + (
        audit_form_live.SKRIP_BACA + "})()));"
    )
    hasil = subprocess.run(
        [node, "-e", program], capture_output=True, text=True, check=True
    )
    data = json.loads(hasil.stdout)
    assert (data["kontrol"], data["wajib"], data["iframe"]) == (3, 2, 1)
    assert data["situs"] == "jobstreet.com"
    assert data["pilihan_terpilih"] == data["pilihan_tidak_terpilih"] == 1


def test_skrip_tidak_membaca_isian_atau_memicu_aksi():
    skrip = audit_form_live.SKRIP_BACA
    for larangan in (".value", ".click(", ".submit(", "fetch(", "location.href"):
        assert larangan not in skrip
