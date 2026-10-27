#!/usr/bin/env python3
"""Load class_dataset.csv into PostgreSQL using schema.sql."""

from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "class_dataset.csv"
SCHEMA_PATH = ROOT / "schema.sql"
ENV_PATH = ROOT / ".env"


def load_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url.strip()

    if ENV_PATH.exists():
        raw = ENV_PATH.read_text(encoding="utf-8").strip()
        if raw.startswith("postgres"):
            return raw
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "DATABASE_URL":
                return value.strip().strip('"').strip("'")

    raise SystemExit("DATABASE_URL is not set. Put the Postgres URI in .env or the environment.")


def split_multi(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def parse_submitted_at(value: str) -> datetime:
    return datetime.fromisoformat(value)


def main() -> None:
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    database_url = load_database_url()
    schema = SCHEMA_PATH.read_text(encoding="utf-8")

    with psycopg.connect(database_url, sslmode="require") as conn:
        conn.execute(schema)

        tools: set[str] = set()
        slots: set[str] = set()
        for row in rows:
            tools.update(split_multi(row["tools"]))
            slots.update(split_multi(row["availability"]))

        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO tools(name) VALUES (%s)",
                [(t,) for t in sorted(tools)],
            )
            cur.executemany(
                "INSERT INTO availability_slots(name) VALUES (%s)",
                [(s,) for s in sorted(slots)],
            )

        tool_ids = dict(conn.execute("SELECT name, tool_id FROM tools"))
        slot_ids = dict(conn.execute("SELECT name, slot_id FROM availability_slots"))

        student_sql = """
            INSERT INTO students (
                netid, name, school_year, intro_programming,
                skill_programming, skill_data_stats, skill_frontend_design, skill_business_pitch,
                working_style, interests, semester_goal, submitted_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        with conn.cursor() as cur:
            cur.executemany(
                student_sql,
                [
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
                    )
                    for row in rows
                ],
            )

            student_tools = []
            student_slots = []
            for row in rows:
                netid = row["netid"]
                for tool in split_multi(row["tools"]):
                    student_tools.append((netid, tool_ids[tool]))
                for slot in split_multi(row["availability"]):
                    student_slots.append((netid, slot_ids[slot]))

            cur.executemany(
                "INSERT INTO student_tools(netid, tool_id) VALUES (%s, %s)",
                student_tools,
            )
            cur.executemany(
                "INSERT INTO student_availability(netid, slot_id) VALUES (%s, %s)",
                student_slots,
            )

        n_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        n_tools = conn.execute("SELECT COUNT(*) FROM student_tools").fetchone()[0]
        n_slots = conn.execute("SELECT COUNT(*) FROM student_availability").fetchone()[0]
        conn.commit()

    print(
        f"Loaded PostgreSQL: {n_students} students, "
        f"{n_tools} tool links, {n_slots} availability links"
    )


if __name__ == "__main__":
    main()
