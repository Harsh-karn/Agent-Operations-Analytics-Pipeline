"""
Dataset loader and database connection manager for Tally.

Supports loading synthetic or runtime logs into BigQuery or an embedded DuckDB
instance for local testing, view verification, and zero-GCP-dependency execution.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
import duckdb
import pandas as pd


class WarehouseHarness:
    """Local warehouse execution harness backed by DuckDB for BigQuery SQL compatibility."""

    def __init__(self, db_path: str = ":memory:"):
        self.conn = duckdb.connect(db_path)
        self.conn.execute("SET schema='main';")

    def load_from_parquet(self, data_dir: str = "data/synthetic") -> Dict[str, int]:
        """Loads all parquet tables from data_dir into DuckDB."""
        p_dir = Path(data_dir)
        counts = {}
        for p_file in p_dir.glob("*.parquet"):
            table_name = p_file.stem
            self.conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM '{p_file.as_posix()}'")
            cnt = self.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            counts[table_name] = cnt
        return counts

    def load_views(self, views_dir: str = "warehouse/views"):
        """Loads all SQL analytical views into DuckDB."""
        v_path = Path(views_dir)
        for vf in ["cost_per_run.sql", "ledger_monthly.sql", "team_signals.sql", "maturity_grade.sql"]:
            target = v_path / vf
            if target.exists():
                sql = target.read_text(encoding="utf-8")
                self.conn.execute(sql)

    def query(self, sql: str) -> pd.DataFrame:
        """Executes a SQL query and returns a pandas DataFrame."""
        return self.conn.execute(sql).df()

    def execute(self, sql: str) -> Any:
        """Executes raw SQL DDL or DML."""
        return self.conn.execute(sql)

    def close(self):
        self.conn.close()


def get_default_harness() -> WarehouseHarness:
    """Initializes and returns a populated warehouse harness with raw tables and views."""
    harness = WarehouseHarness()
    data_dir = Path("data/synthetic")
    if not any(data_dir.glob("*.parquet")):
        from data.generate import SyntheticDataGenerator
        gen = SyntheticDataGenerator(seed=42, months=4)
        dataset = gen.generate_all()
        gen.save(dataset, str(data_dir), export_format="parquet")
    harness.load_from_parquet(str(data_dir))
    harness.load_views()
    return harness
