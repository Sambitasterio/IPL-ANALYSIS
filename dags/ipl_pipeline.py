"""Step 7 — Airflow DAG orchestrating the IPL ETL.

Flow:  check_raw  ->  transform  ->  load  ->  validate

The pipeline scripts (transform.py, load.py, validate.py) live in the project
root, which is mounted into the Airflow containers at /opt/airflow/project.
Each task chdir's there so the scripts' relative paths (data/raw, .env, ...)
and their imports resolve.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

from airflow.decorators import dag, task

PROJECT_DIR = "/opt/airflow/project"


def _prepare() -> None:
    """Run from the project root and make its modules importable."""
    os.chdir(PROJECT_DIR)
    if PROJECT_DIR not in sys.path:
        sys.path.insert(0, PROJECT_DIR)


@dag(
    dag_id="ipl_pipeline",
    description="IPL ball-by-ball ETL: raw CSVs -> star schema in Supabase",
    schedule=None,            # manual trigger while developing; '@daily' once stable
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["ipl", "etl"],
)
def ipl_pipeline():

    @task
    def check_raw() -> str:
        _prepare()
        for f in ["data/raw/matches.csv", "data/raw/deliveries.csv"]:
            if not Path(f).exists():
                raise FileNotFoundError(f"Missing raw file: {f}")
        return "raw files present"

    @task
    def transform() -> None:
        _prepare()
        import transform as m
        m.main()

    @task
    def load() -> None:
        _prepare()
        import load as m
        m.main()

    @task
    def validate() -> None:
        _prepare()
        import validate as m
        m.main()

    check_raw() >> transform() >> load() >> validate()


ipl_pipeline()
