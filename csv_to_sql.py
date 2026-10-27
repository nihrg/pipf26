#!/usr/bin/env python3
"""Create schema and load data/class_dataset.csv into Postgres at DATABASE_URL."""

from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "data" / "class_dataset.csv"
SCHEMA_PATH = ROOT / "schema.sql"
ENV_PATH = ROOT / ".env"
TABLES = (
    "students",
    "tools",
    "student_tools",
    "availability_slots",
    "student_availability",
)


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


def split_multi(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def parse_submitted_at(value: str) -> datetime:
    return datetime.fromisoformat(value)


def main() -> None:
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = psycopg2.connect(load_database_url(), sslmode="require")
    try:
        with conn.cursor() as cur:
            cur.execute(schema)

            tools = sorted({t for row in rows for t in split_multi(row["tools"])})
            slots = sorted({s for row in rows for s in split_multi(row["availability"])})
            cur.executemany("INSERT INTO tools(name) VALUES (%s)", [(t,) for t in tools])
            cur.executemany(
                "INSERT INTO availability_slots(name) VALUES (%s)",
                [(s,) for s in slots],
            )

            cur.execute("SELECT name, id FROM tools")
            tool_ids = dict(cur.fetchall())
            cur.execute("SELECT name, id FROM availability_slots")
            slot_ids = dict(cur.fetchall())

            for row in rows:
                cur.execute(
                    """
                    INSERT INTO students (
                        netid, name, school_year, intro_programming,
                        skill_programming, skill_data_stats,
                        skill_frontend_design, skill_business_pitch,
                        working_style, interests, semester_goal, submitted_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING student_id
                    """,
                    (
                        row["netid"],
                        row["name"],
                        row["school_year"],
                        row["intro_programming"],
                        int(row["skill_programming"]),
                        int(row["skill_data_stats"]),
                        int(row["skill_frontend_design"]),
                        int(row["skill_business_pitch"]),
                        row["working_style"],
                        row["interests"],
                        row["semester_goal"],
                        parse_submitted_at(row["submitted_at"]),
                    ),
                )
                student_id = cur.fetchone()[0]
                cur.executemany(
                    "INSERT INTO student_tools(student_id, tool_id) VALUES (%s, %s)",
                    [(student_id, tool_ids[tool]) for tool in split_multi(row["tools"])],
                )
                cur.executemany(
                    "INSERT INTO student_availability(student_id, slot_id) VALUES (%s, %s)",
                    [(student_id, slot_ids[slot]) for slot in split_multi(row["availability"])],
                )

            print("Row counts:")
            for table in TABLES:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                print(f"  {table}: {cur.fetchone()[0]}")

        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
