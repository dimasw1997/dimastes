import re
from typing import Dict, List
from config import config
from database import db


class JobFilter:
    def __init__(self):
        self.exclude_keywords = [k.strip().lower()
                                  for k in config.exclude_keywords if k.strip()]

    def should_apply(self, job: Dict) -> tuple:
        title = job.get('title', '').lower()
        company = job.get('company', '')
        description = job.get('description', '').lower()
        salary_text = job.get('salary', '').lower()

        if db.is_already_applied(job['job_id']):
            return False, "Sudah pernah apply"

        if db.is_blacklisted(company):
            return False, f"Company di-blacklist: {company}"

        for keyword in self.exclude_keywords:
            if keyword in title:
                return False, f"Title mengandung excluded: '{keyword}'"

        senior_keywords = ['senior', 'sr.', 'lead', 'principal',
                           'director', 'head of', 'chief', 'vp ',
                           'vice president', 'manager']
        for keyword in senior_keywords:
            if keyword in title:
                return False, f"Posisi terlalu senior: '{keyword}'"

        if config.min_salary > 0 and salary_text:
            parsed_salary = self._parse_salary(salary_text)
            if parsed_salary and parsed_salary < config.min_salary:
                return False, f"Salary terlalu rendah: {parsed_salary:,}"

        exp_years = self._extract_experience(description)
        if exp_years and exp_years > config.max_experience:
            return False, f"Experience terlalu tinggi: {exp_years} tahun"

        return True, "OK"

    def _parse_salary(self, salary_text: str) -> int:
        numbers = re.findall(r'[\d.,]+', salary_text.replace('.', ''))
        if numbers:
            try:
                salary = int(numbers[0].replace(',', '').replace('.', ''))
                if salary < 1000:
                    salary *= 1_000_000
                return salary
            except ValueError:
                return 0
        return 0

    def _extract_experience(self, text: str) -> int:
        patterns = [
            r'(\d+)\+?\s*(?:years?|tahun)\s*(?:of\s+)?(?:experience|pengalaman)',
            r'(?:minimal?|minimum|at least)\s*(\d+)\s*(?:years?|tahun)',
            r'(\d+)\s*-\s*\d+\s*(?:years?|tahun)',
        ]
        min_years = None
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                years = int(match.group(1))
                if min_years is None or years < min_years:
                    min_years = years
        return min_years

    def rank_jobs(self, jobs: List[Dict]) -> List[Dict]:
        scored_jobs = []
        for job in jobs:
            score = self._calculate_score(job)
            job['_score'] = score
            scored_jobs.append(job)
        scored_jobs.sort(key=lambda x: x['_score'], reverse=True)
        return scored_jobs

    def _calculate_score(self, job: Dict) -> int:
        score = 0
        title = job.get('title', '').lower()
        description = job.get('description', '').lower()

        for keyword in config.keywords:
            kw = keyword.strip().lower()
            if kw in title:
                score += 10
            if kw in description:
                score += 3

        if job.get('salary') and job['salary'] != "Tidak disebutkan":
            score += 5

        date_posted = job.get('date_posted', '').lower()
        if any(w in date_posted for w in ['hari ini', 'today', '1 day', 'baru']):
            score += 5
        elif any(w in date_posted for w in ['kemarin', 'yesterday', '2 day']):
            score += 3

        return score


job_filter = JobFilter()