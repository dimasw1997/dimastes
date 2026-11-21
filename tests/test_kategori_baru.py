"""Daftar baru dan migrasi .env untuk riset ketiga situs."""

from pathlib import Path

from config import Config
from env_tools import baca_baku, perbarui_env

KATEGORI = (  # noqa: SIM905
    "Inventory,Warehouse,PPIC,Material,Production,Logistics,Supply Chain,Stock,"
    "Purchasing,Procurement,Planning,Quality,Audit,Operations,Manufacturing,"
    "Distribution,Shipping,Receiving,Storekeeper,Expedition,Import,Export,"
    "Freight,Transportation,Delivery,Dispatch,Packaging,Manufacturing Control,"
    "Production Planning,Production Control,Inventory Control,Stock Control,"
    "Warehouse Control,Material Control,Quality Control,Quality Assurance,"
    "Document Control,Project Control,Cost Control,Demand Planning,Supply Planning,"
    "Order Management,Purchasing Management,Procurement Management,"
    "Logistics Management,Warehouse Management,Inventory Management,"
    "Operations Management,Production Management,Supply Management"
).split(",")  # noqa: SIM905

KATA = (  # noqa: SIM905
    "Inventory,Warehouse,PPIC,Material,Production,Logistics,Supply,Stock,"
    "Purchasing,Procurement,Planning,Quality,Audit,Operations,Manufacturing,"
    "Distribution,Shipping,Receiving,Storekeeper,Expedition,Import,Export,"
    "Freight,Transportation,Delivery,Dispatch,Packaging,Control,Management,"
    "Inventory Control,Stock Control,Warehouse Control,Material Control,"
    "Quality Control,Quality Assurance,Document Control,Project Control,"
    "Cost Control,Demand Planning,Supply Planning,Order Management,"
    "Purchasing Management,Procurement Management,Logistics Management,"
    "Warehouse Management,Inventory Management,Operations Management,"
    "Production Management,Supply Management,Distribution Management"
).split(",")  # noqa: SIM905


def test_daftar_baku_dan_contoh_sama_persis(monkeypatch):
    for key in ("KEYWORDS", "TITLE_KEYWORDS", "RESEARCH_KEYWORDS"):
        monkeypatch.delenv(key, raising=False)
    cfg = Config()
    contoh = baca_baku(Path(".env.example").read_text(encoding="utf-8"))
    assert len(KATEGORI) == len(KATA) == 50
    assert cfg.keywords == cfg.title_keywords == KATA
    assert cfg.keywords_riset == KATEGORI
    assert contoh["KEYWORDS"].split(",") == KATA
    assert contoh["TITLE_KEYWORDS"].split(",") == KATA
    assert contoh["RESEARCH_KEYWORDS"].split(",") == KATEGORI


def test_perbarui_env_mengganti_daftar_lama_dan_menjaga_pengaturan(tmp_path):
    env = tmp_path / ".env"
    lama = (
        "KEYWORDS=lama\nTITLE_KEYWORDS=judul lama\nRESEARCH_KEYWORDS=riset lama\n"
        "INGAT_JAWABAN=false\nLOCATIONS=Bandung\n"
    )
    env.write_text(lama, encoding="utf-8")
    contoh = Path(".env.example")
    hasil = perbarui_env(env, contoh)
    nilai = baca_baku(env.read_text(encoding="utf-8"))
    assert set(hasil["perubahan"]) >= {
        "KEYWORDS", "TITLE_KEYWORDS", "RESEARCH_KEYWORDS"
    }
    assert nilai["KEYWORDS"].split(",") == KATA
    assert nilai["TITLE_KEYWORDS"].split(",") == KATA
    assert nilai["RESEARCH_KEYWORDS"].split(",") == KATEGORI
    assert nilai["INGAT_JAWABAN"] == "false"
    assert nilai["LOCATIONS"] == "Bandung"
    assert Path(hasil["backup"]).read_text(encoding="utf-8") == lama
