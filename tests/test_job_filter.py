import pytest

import job_filter as job_filter_module
from config import config
from database import Database
from job_filter import JobFilter


@pytest.fixture
def filter_baru(tmp_path, monkeypatch):
    """JobFilter dengan database kosong supaya hasil test deterministik."""
    database = Database(str(tmp_path / "filter.db"))
    monkeypatch.setattr(job_filter_module, "db", database)
    return JobFilter()


def make_job(**overrides):
    job = {
        "job_id": "123",
        "title": "Inventory Control",
        "company": "PT Contoh",
        "location": "Bandung, West Java",
        "salary": "Rp 8.000.000 per month",
        "description": "Mengelola stok gudang.",
        "url": "https://id.jobstreet.com/job/123",
        "date_posted": "Hari ini",
    }
    job.update(overrides)
    return job


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Rp 7.000.000 – Rp 10.500.000 per month", 7_000_000),
        ("Rp 8.000.000", 8_000_000),
        ("8500000", 8_500_000),
        ("Rp 5 juta", 5_000_000),
        ("7,5 juta", 7_500_000),
        ("Rp 900 ribu", 900_000),
        ("Tidak disebutkan", 0),
        ("", 0),
    ],
)
def test_parse_salary(filter_baru, text, expected):
    assert filter_baru._parse_salary(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Minimal 3 tahun pengalaman", 3),
        ("5+ years of experience required", 5),
        ("2-4 tahun", 2),
        ("Tanpa pengalaman", None),
    ],
)
def test_extract_experience(filter_baru, text, expected):
    assert filter_baru._extract_experience(text) == expected


def test_lolos_untuk_lowongan_biasa(filter_baru):
    lolos, alasan = filter_baru.should_apply(make_job())
    assert lolos is True
    assert alasan == "OK"


def test_tolak_judul_kosong(filter_baru):
    lolos, alasan = filter_baru.should_apply(make_job(title="   "))
    assert lolos is False
    assert "judul" in alasan.lower()


def test_tolak_kata_kunci_terlarang(filter_baru):
    lolos, alasan = filter_baru.should_apply(make_job(title="Senior Planner"))
    assert lolos is False
    assert "senior" in alasan.lower() or "excluded" in alasan.lower()


def test_tolak_perusahaan_blacklist(filter_baru, tmp_path):
    job_filter_module.db.add_blacklist("PT Contoh", "tidak sesuai")
    lolos, alasan = filter_baru.should_apply(make_job())
    assert lolos is False
    assert "blacklist" in alasan.lower()


def test_tolak_job_yang_sudah_dilamar(filter_baru):
    job_filter_module.db.record_application("123", "applied")
    lolos, alasan = filter_baru.should_apply(make_job())
    assert lolos is False
    assert "sudah" in alasan.lower()


def test_tolak_pengalaman_berlebih(filter_baru, monkeypatch):
    monkeypatch.setattr(config, "max_experience", 5)
    lolos, alasan = filter_baru.should_apply(
        make_job(description="Minimal 8 tahun pengalaman di bidang PPIC.")
    )
    assert lolos is False
    assert "pengalaman" in alasan.lower() or "experience" in alasan.lower()


def test_tolak_gaji_di_bawah_minimum(filter_baru, monkeypatch):
    monkeypatch.setattr(config, "min_salary", 5_000_000)
    lolos, alasan = filter_baru.should_apply(
        make_job(salary="Rp 3.000.000 per month")
    )
    assert lolos is False
    assert "salary" in alasan.lower() or "gaji" in alasan.lower()


def test_strict_location(filter_baru, monkeypatch):
    monkeypatch.setattr(config, "strict_location", True)
    monkeypatch.setattr(config, "location", "Bandung")
    monkeypatch.setattr(config, "locations", ["Bandung"])

    lolos, alasan = filter_baru.should_apply(
        make_job(location="Jakarta Selatan")
    )
    assert lolos is False
    assert "lokasi" in alasan.lower()

    lolos, _ = filter_baru.should_apply(make_job(location="Cimahi, Bandung"))
    assert lolos is True


def test_job_tanpa_job_id_tidak_error(filter_baru):
    job = make_job()
    job.pop("job_id")
    assert filter_baru.should_apply(job)[0] is True


def test_rank_jobs_aman_untuk_salary_none(filter_baru):
    jobs = [
        make_job(job_id="1", salary=None),
        make_job(job_id="2", salary="Rp 9.000.000"),
    ]
    hasil = filter_baru.rank_jobs(jobs)

    assert len(hasil) == 2
    assert hasil[0]["salary"] == "Rp 9.000.000"


def test_tolak_lowongan_terlalu_lama(filter_baru, monkeypatch):
    monkeypatch.setattr(config, "max_age_days", 3)

    lolos, alasan = filter_baru.should_apply(make_job(age_days=5))
    assert lolos is False
    assert "3 hari" in alasan

    assert filter_baru.should_apply(make_job(age_days=1))[0] is True
    # Umur tidak diketahui -> jangan dibuang.
    assert filter_baru.should_apply(make_job(age_days=None))[0] is True


def test_rank_jobs_utamakan_yang_terbaru(filter_baru):
    jobs = [
        make_job(job_id="1", title="Inventory Control", age_days=6),
        make_job(job_id="2", title="Stok Controller", age_days=0),
        make_job(job_id="3", title="PPIC", age_days=None),
    ]

    hasil = filter_baru.rank_jobs(jobs, prefer_newest=True)

    assert [job["job_id"] for job in hasil] == ["2", "1", "3"]


def test_rank_jobs_mode_skor(filter_baru):
    jobs = [
        make_job(job_id="1", title="Stok Controller", age_days=0),
        make_job(job_id="2", title="Inventory Control", age_days=9),
    ]

    hasil = filter_baru.rank_jobs(jobs, prefer_newest=False)

    # Judul yang persis cocok dengan kata kunci mendapat skor lebih tinggi.
    assert hasil[0]["job_id"] == "2"
