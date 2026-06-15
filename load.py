"""Step 5 — Load the star-schema CSVs into PostgreSQL (Supabase).

Idempotent: every run first truncates all tables, then re-loads from
data/transformed/. So re-running (or a daily Airflow run) never duplicates
rows. Tables are loaded parents-first to satisfy foreign keys.
"""
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

OUT = Path("data/transformed")

# Parents before children (FK dependency order).
LOAD_ORDER = ["dim_team", "dim_venue", "dim_player", "dim_match", "fact_deliveries"]


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

    # Wipe all tables once so the load is repeatable. RESTART IDENTITY resets
    # the fact_deliveries BIGSERIAL; CASCADE clears child rows first.
    with engine.begin() as conn:
        conn.execute(text(
            f"TRUNCATE {', '.join(LOAD_ORDER)} RESTART IDENTITY CASCADE"
        ))
    print("Truncated all tables.")

    for table in LOAD_ORDER:
        df = pd.read_csv(OUT / f"{table}.csv")
        # chunksize=4000: ~13 cols x 4000 rows stays under Postgres' 65,535
        # bind-parameter cap per statement when method='multi'.
        df.to_sql(
            table, engine, if_exists="append", index=False,
            chunksize=4000, method="multi",
        )
        print(f"Loaded {len(df):>7,} rows into {table}")

    print("Load complete.")


if __name__ == "__main__":
    main()
