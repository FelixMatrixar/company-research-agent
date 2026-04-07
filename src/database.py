import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "companies.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS companies (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT NOT NULL UNIQUE,
                website      TEXT,
                description  TEXT,
                github_url   TEXT,
                stars          INTEGER,
                language       TEXT,
                topics         TEXT,
                readme_summary TEXT,
                collected_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS analysis (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id     INTEGER NOT NULL REFERENCES companies(id),
                industry       TEXT NOT NULL,
                business_model TEXT NOT NULL,
                summary        TEXT NOT NULL,
                use_case       TEXT NOT NULL,
                raw_response   TEXT,
                analyzed_at    TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_analysis_industry ON analysis(industry);
        """)
        # Migrations for columns added after initial schema.
        for col, typedef in [("topics", "TEXT"), ("readme_summary", "TEXT")]:
            try:
                conn.execute(f"ALTER TABLE companies ADD COLUMN {col} {typedef}")
            except sqlite3.OperationalError:
                pass  # column already exists


def save_company(
    name: str,
    website: str | None,
    description: str | None,
    github_url: str | None,
    stars: int | None,
    language: str | None,
    topics: str | None,
    readme_summary: str | None,
    collected_at: str,
) -> int:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO companies
                (name, website, description, github_url, stars, language, topics, readme_summary, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                website        = excluded.website,
                description    = excluded.description,
                github_url     = excluded.github_url,
                stars          = excluded.stars,
                language       = excluded.language,
                topics         = excluded.topics,
                readme_summary = excluded.readme_summary,
                collected_at   = excluded.collected_at
            """,
            (name, website, description, github_url, stars, language, topics, readme_summary, collected_at),
        )
        row = conn.execute("SELECT id FROM companies WHERE name = ?", (name,)).fetchone()
        return row["id"]


def get_all_companies(
    industry: str | None = None,
    business_model: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> list[dict]:
    offset = (page - 1) * per_page
    query = """
        SELECT
            c.id, c.name, c.website, c.description, c.github_url,
            c.stars, c.language, c.topics, c.readme_summary, c.collected_at,
            a.industry, a.business_model, a.summary, a.use_case, a.analyzed_at
        FROM companies c
        LEFT JOIN analysis a ON a.company_id = c.id
        WHERE 1=1
    """
    params: list = []
    if industry:
        query += " AND LOWER(a.industry) = LOWER(?)"
        params.append(industry)
    if business_model:
        query += " AND LOWER(a.business_model) = LOWER(?)"
        params.append(business_model)
    query += " ORDER BY c.stars DESC LIMIT ? OFFSET ?"
    params.extend([per_page, offset])

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_company_by_id(company_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT
                c.id, c.name, c.website, c.description, c.github_url,
                c.stars, c.language, c.topics, c.readme_summary, c.collected_at,
                a.industry, a.business_model, a.summary, a.use_case, a.analyzed_at
            FROM companies c
            LEFT JOIN analysis a ON a.company_id = c.id
            WHERE c.id = ?
            """,
            (company_id,),
        ).fetchone()
        return dict(row) if row else None


def get_analysis_by_company_id(company_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, company_id, industry, business_model, summary,
                   use_case, raw_response, analyzed_at
            FROM analysis
            WHERE company_id = ?
            """,
            (company_id,),
        ).fetchone()
        return dict(row) if row else None


def get_raw_response(company_id: int) -> str | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT raw_response FROM analysis WHERE company_id = ?",
            (company_id,),
        ).fetchone()
        return row["raw_response"] if row else None


def save_analysis(
    company_id: int,
    industry: str,
    business_model: str,
    summary: str,
    use_case: str,
    raw_response: str,
    analyzed_at: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO analysis
                (company_id, industry, business_model, summary, use_case, raw_response, analyzed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (company_id, industry, business_model, summary, use_case, raw_response, analyzed_at),
        )


def get_unanalyzed_companies() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.name, c.description, c.stars, c.language, c.topics, c.readme_summary
            FROM companies c
            LEFT JOIN analysis a ON a.company_id = c.id
            WHERE a.id IS NULL
            """,
        ).fetchall()
        return [dict(r) for r in rows]


def get_companies_by_topic(topic: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT
                c.id, c.name, c.website, c.description, c.github_url,
                c.stars, c.language, c.topics, c.readme_summary, c.collected_at,
                a.industry, a.business_model, a.summary, a.use_case, a.analyzed_at
            FROM companies c
            LEFT JOIN analysis a ON a.company_id = c.id
            WHERE LOWER(c.topics) LIKE LOWER(?)
            ORDER BY c.stars DESC
            """,
            (f"%{topic}%",),
        ).fetchall()
        return [dict(r) for r in rows]


def get_industry_aggregation(industry: str) -> dict:
    with _connect() as conn:
        lang_rows = conn.execute(
            """
            SELECT
                c.language,
                COUNT(*)       AS count,
                AVG(c.stars)   AS avg_stars
            FROM companies c
            JOIN analysis a ON a.company_id = c.id
            WHERE LOWER(a.industry) = LOWER(?)
              AND c.language IS NOT NULL
            GROUP BY c.language
            ORDER BY count DESC
            """,
            (industry,),
        ).fetchall()
        total_row = conn.execute(
            """
            SELECT COUNT(*) AS count, AVG(c.stars) AS avg_stars
            FROM companies c
            JOIN analysis a ON a.company_id = c.id
            WHERE LOWER(a.industry) = LOWER(?)
            """,
            (industry,),
        ).fetchone()
        return {
            "industry":   industry,
            "total":      total_row["count"],
            "avg_stars":  round(total_row["avg_stars"] or 0),
            "by_language": [
                {
                    "language":  r["language"],
                    "count":     r["count"],
                    "avg_stars": round(r["avg_stars"] or 0),
                }
                for r in lang_rows
            ],
        }


def get_stats() -> dict:
    with _connect() as conn:
        total_companies = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        total_analyzed = conn.execute("SELECT COUNT(*) FROM analysis").fetchone()[0]
        coverage_pct = (
            round(total_analyzed / total_companies * 100, 1) if total_companies else 0.0
        )
        industry_rows = conn.execute(
            """
            SELECT industry, COUNT(*) AS count
            FROM analysis
            GROUP BY industry
            ORDER BY count DESC
            """
        ).fetchall()
        return {
            "total_companies": total_companies,
            "total_analyzed": total_analyzed,
            "coverage_pct": coverage_pct,
            "by_industry": [dict(r) for r in industry_rows],
        }
