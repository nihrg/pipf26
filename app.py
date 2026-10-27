#!/usr/bin/env python3
"""Flask app that lists student names from Postgres."""

from __future__ import annotations

from flask import Flask, render_template
import psycopg2

from query_db import load_database_url

app = Flask(__name__)


def fetch_student_names() -> list[str]:
    conn = psycopg2.connect(load_database_url(), sslmode="require")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM students ORDER BY name;")
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


@app.route("/")
def index():
    return render_template("index.html", students=fetch_student_names())


if __name__ == "__main__":
    app.run(debug=True)
