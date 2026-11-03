import sqlite3
from contextlib import contextmanager


class Database:
    def __init__(self, db_path: str = "jobstreet_auto.db"):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    company TEXT,
                    location TEXT,
                    salary TEXT,
                    description TEXT,
                    url TEXT NOT NULL,
                    date_posted TEXT,
                    date_scraped TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    status TEXT DEFAULT 'applied',
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    response TEXT,
                    notes TEXT
                );

                CREATE TABLE IF NOT EXISTS blacklist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_name TEXT UNIQUE NOT NULL,
                    reason TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def add_job(self, job_data: dict) -> bool:
        with self._get_conn() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO jobs (
                        job_id, title, company, location,
                        salary, description, url, date_posted
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_data["job_id"],
                        job_data["title"],
                        job_data.get("company", ""),
                        job_data.get("location", ""),
                        job_data.get("salary", ""),
                        job_data.get("description", ""),
                        job_data["url"],
                        job_data.get("date_posted", ""),
                    ),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def is_already_applied(self, job_id: str) -> bool:
        """Hanya status applied yang dihitung sebagai lamaran terkirim."""
        with self._get_conn() as conn:
            result = conn.execute(
                """
                SELECT 1
                FROM applications
                WHERE job_id = ? AND status = 'applied'
                LIMIT 1
                """,
                (job_id,),
            ).fetchone()

            return result is not None

    def record_application(
        self,
        job_id: str,
        status: str = "applied",
        notes: str = "",
    ):
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO applications (job_id, status, notes)
                VALUES (?, ?, ?)
                """,
                (job_id, status, notes),
            )

    def get_today_apply_count(self) -> int:
        with self._get_conn() as conn:
            result = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM applications
                WHERE DATE(applied_at, 'localtime') = DATE('now', 'localtime')
                  AND status = 'applied'
                """
            ).fetchone()

            return result["count"]

    def is_blacklisted(self, company_name: str) -> bool:
        if not company_name:
            return False

        with self._get_conn() as conn:
            result = conn.execute(
                "SELECT 1 FROM blacklist WHERE company_name = ? LIMIT 1",
                (company_name,),
            ).fetchone()

            return result is not None

    def add_blacklist(self, company_name: str, reason: str = ""):
        with self._get_conn() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO blacklist (company_name, reason)
                    VALUES (?, ?)
                    """,
                    (company_name, reason),
                )
            except sqlite3.IntegrityError:
                pass

    def get_stats(self) -> dict:
        with self._get_conn() as conn:
            total_jobs = conn.execute(
                "SELECT COUNT(*) AS count FROM jobs"
            ).fetchone()["count"]

            total_applied = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM applications
                WHERE status = 'applied'
                """
            ).fetchone()["count"]

            today_applied = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM applications
                WHERE DATE(applied_at, 'localtime') = DATE('now', 'localtime')
                  AND status = 'applied'
                """
            ).fetchone()["count"]

            return {
                "total_jobs_found": total_jobs,
                "total_applied": total_applied,
                "today_applied": today_applied,
            }


db = Database()