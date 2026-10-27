#!/usr/bin/env python3
"""Run the lab's starter queries against Postgres at DATABASE_URL."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

ENV_PATH = Path(__file__).resolve().parent / ".env"

QUERIES = [
    ("Student count (should match the CSV row count)", "SELECT count(*) FROM students;"),
    (
        "First 5 students",
        "SELECT name, school_year FROM students LIMIT 5;",
    ),
    (
        "Students per tool",
        """
        SELECT t.name, COUNT(*) AS n_students
        FROM student_tools st
        JOIN tools t ON st.tool_id = t.id
        GROUP BY t.name
        ORDER BY n_students DESC;
        """,
    ),
]


def load_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url.strip()

    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "DATABASE_URL":
                return value.strip().strip('"').strip("'")

    raise SystemExit(
        "DATABASE_URL is not set. Add DATABASE_URL=<public Railway URL> to .env."
    )


def main() -> None:
    conn = psycopg2.connect(load_database_url(), sslmode="require")
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for title, sql in QUERIES:
                print(f"\n-- {title}")
                cur.execute(sql)
                rows = cur.fetchall()
                for row in rows:
                    print(dict(row))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
