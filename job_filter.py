"""Aturan penyaringan dan pemeringkatan lowongan."""

import re
from typing import Dict, List, Optional

from config import config
from database import db


class JobFilter:
    def __init__(self):
        self.exclude_keywords = [
            k.strip().lower() for k in config.exclude_keywords if k.strip()
        ]
        self.senior_keywords = [
            "senior", "sr.", "lead", "principal", "director", "head of",
            "chief", "vp ", "vice president", "manager",
        ]

    def should_apply(self, job: Dict) -> tuple[bool, str]:
        job_id = str(job.get("job_id") or "").strip()
        title = str(job.get("title") or "").strip()
        company = str(job.get("company") or "").strip()
        description = str(job.get("description") or "")
        salary_text = str(job.get("salary") or "")
        location = str(job.get("location") or "").strip()

        if not title:
            return False, "Judul lowongan tidak terbaca"

        if job_id and db.is_already_applied(job_id):
            return False, "Sudah pernah apply"

        if company and db.is_blacklisted(company):
            return False, f"Company di-blacklist: {company}"

        title_lower = title.lower()

        for keyword in self.exclude_keywords:
            if keyword in title_lower:
                return False, f"Title mengandung excluded: '{keyword}'"

        for keyword in self.senior_keywords:
            if keyword in title_lower:
                return False, f"Posisi terlalu senior: '{keyword}'"

        if config.strict_location and config.location and location:
            target = config.location.lower()
            if target not in location.lower():
                return False, f"Lokasi di luar {config.location}: {location}"

        if config.min_salary > 0 and salary_text:
            parsed_salary = self._parse_salary(salary_text)
            if parsed_salary and parsed_salary < config.min_salary:
                return False, f"Salary terlalu rendah: {parsed_salary:,}"

        exp_years = self._extract_experience(description)
        if exp_years is not None and exp_years > config.max_experience:
            return False, f"Experience terlalu tinggi: {exp_years} tahun"

        return True, "OK"

    @staticmethod
    def _to_number(token: str) -> float:
        """Mengubah potongan angka Indonesia menjadi float.

        Contoh: "7.000.000" -> 7000000, "7,5" -> 7.5, "8500000" -> 8500000.
        """
        token = token.strip()

        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", token):
            return float(token.replace(".", ""))

        if re.fullmatch(r"\d{1,3}(?:,\d{3})+", token):
            return float(token.replace(",", ""))

        if re.fullmatch(r"\d+,\d+", token):
            return float(token.replace(",", "."))

        if re.fullmatch(r"\d+\.\d{1,2}", token):
            return float(token)

        digits = re.sub(r"[^\d]", "", token)
        return float(digits) if digits else 0.0

    def _parse_salary(self, salary_text: str) -> int:
        """Mengambil batas bawah gaji dari teks seperti
        "Rp 7.000.000 – Rp 10.500.000 per month"."""
        text = str(salary_text or "").lower()
        text = re.sub(r"\b(?:rp|idr)\b\.?", " ", text)

        tokens = re.findall(r"\d[\d.,]*", text)
        values = [self._to_number(token) for token in tokens]
        values = [value for value in values if value > 0]

        if not values:
            return 0

        multiplier = 1
        if "juta" in text:
            multiplier = 1_000_000
        elif "ribu" in text or "rb" in text:
            multiplier = 1_000

        salary = int(min(values) * multiplier)

        # Angka kecil tanpa satuan, misal "gaji 8", dianggap satuan juta.
        if multiplier == 1 and salary < 1_000:
            salary *= 1_000_000

        return salary

    def _extract_experience(self, text: str) -> Optional[int]:
        patterns = [
            r"(\d+)\+?\s*(?:years?|tahun)\s*(?:of\s+)?"
            r"(?:experience|pengalaman)",
            r"(?:minimal?|minimum|at least)\s*(\d+)\s*(?:years?|tahun)",
            r"(\d+)\s*-\s*\d+\s*(?:years?|tahun)",
        ]
        text = str(text or "")
        min_years = None

        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                years = int(match.group(1))
                if min_years is None or years < min_years:
                    min_years = years

        return min_years

    def rank_jobs(self, jobs: List[Dict]) -> List[Dict]:
        scored_jobs = []

        for job in jobs:
            job["_score"] = self._calculate_score(job)
            scored_jobs.append(job)

        scored_jobs.sort(key=lambda item: item["_score"], reverse=True)
        return scored_jobs

    def _calculate_score(self, job: Dict) -> int:
        score = 0
        title = str(job.get("title") or "").lower()
        description = str(job.get("description") or "").lower()

        for keyword in config.keywords:
            kw = keyword.strip().lower()
            if not kw:
                continue
            if kw in title:
                score += 10
            if kw in description:
                score += 3

        salary = str(job.get("salary") or "").strip()
        if salary and salary != "Tidak disebutkan":
            score += 5

        date_posted = str(job.get("date_posted") or "").lower()
        if any(w in date_posted for w in ["hari ini", "today", "1 day", "baru"]):
            score += 5
        elif any(w in date_posted for w in ["kemarin", "yesterday", "2 day"]):
            score += 3

        return score


job_filter = JobFilter()
