"""Step 6 — Data-quality checks run after the load.

Each check is (name, SQL returning one number, predicate). Prints PASS/FAIL per
check and exits non-zero if any fail, so Airflow (Step 7) marks the run failed
when the warehouse is in a bad state.
"""
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# name, SQL (returns a single value), predicate that must hold for a PASS
CHECKS = [
    ("fact_deliveries not empty",
     "SELECT COUNT(*) FROM fact_deliveries",
     lambda n: n > 0),
    ("dim_match not empty",
     "SELECT COUNT(*) FROM dim_match",
     lambda n: n > 0),
    ("all 15 teams loaded",
     "SELECT COUNT(*) FROM dim_team",
     lambda n: n == 15),
    ("no orphan match_id in fact",
     "SELECT COUNT(*) FROM fact_deliveries f "
     "LEFT JOIN dim_match m ON f.match_id = m.match_id WHERE m.match_id IS NULL",
     lambda n: n == 0),
    ("no orphan batsman_id in fact",
     "SELECT COUNT(*) FROM fact_deliveries f "
     "LEFT JOIN dim_player p ON f.batsman_id = p.player_id WHERE p.player_id IS NULL",
     lambda n: n == 0),
    ("no null batsman_id",
     "SELECT COUNT(*) FROM fact_deliveries WHERE batsman_id IS NULL",
     lambda n: n == 0),
    ("no null bowler_id",
     "SELECT COUNT(*) FROM fact_deliveries WHERE bowler_id IS NULL",
     lambda n: n == 0),
    ("runs_scored within sane range (0-7)",
     "SELECT COUNT(*) FROM fact_deliveries WHERE runs_scored < 0 OR runs_scored > 7",
     lambda n: n == 0),
    ("seasons span 2008-2024",
     "SELECT COUNT(DISTINCT season) FROM dim_match",
     lambda n: n == 17),
]


def get_engine():
    load_dotenv()
    url = os.getenv("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError("SUPABASE_DB_URL not set — check your .env file.")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return create_engine(url, pool_pre_ping=True)


def main() -> None:
    engine = get_engine()
    failures = 0
    with engine.connect() as conn:
        for name, sql, ok in CHECKS:
            value = conn.execute(text(sql)).scalar()
            passed = ok(value)
            failures += not passed
            status = "PASS" if passed else "FAIL"
            print(f"[{status}] {name} (value={value})")

    print()
    if failures:
        print(f"{failures} data-quality check(s) FAILED.")
        sys.exit(1)
    print("All data-quality checks passed.")


if __name__ == "__main__":
    main()
