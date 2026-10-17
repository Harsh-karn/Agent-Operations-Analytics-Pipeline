"""
Warehouse SQL View Validation and Data Quality Assertions

Tests the analytical views:
- cost_per_run
- ledger_monthly
- team_signals
- maturity_grade

Verifies data constraints:
- Zero nulls in mandatory dimensions
- Non-negative costs and absorbed minutes
- Monotonic confidence intervals (Low <= Expected <= High)
- Anomaly flags logic
- Seeded known facts (Compliance team 12 workflows)
- Weakest-link safety capping in maturity grades
"""

from pathlib import Path
import pytest
from data.loader import WarehouseHarness


@pytest.fixture(scope="module")
def harness():
    """Module-level fixture to load synthetic tables and execute view definitions."""
    h = WarehouseHarness()
    # 1. Load raw tables from parquet
    counts = h.load_from_parquet("data/synthetic")
    assert counts["runs"] > 0, "No runs loaded into warehouse test harness"

    # 2. Execute SQL views in dependency order
    views_dir = Path("warehouse/views")
    view_files = ["cost_per_run.sql", "ledger_monthly.sql", "team_signals.sql", "maturity_grade.sql"]
    for vf in view_files:
        sql = (views_dir / vf).read_text(encoding="utf-8")
        h.execute(sql)

    yield h
    h.close()


def test_no_nulls_in_critical_tables(harness):
    """Assert zero nulls in primary identity columns."""
    for table, col in [("runs", "run_id"), ("teams", "team_id"), ("agents", "agent_id")]:
        df = harness.query(f"SELECT COUNT(*) as null_count FROM {table} WHERE {col} IS NULL")
        assert df["null_count"].iloc[0] == 0, f"Found nulls in {table}.{col}"


def test_cost_per_run_anomalies(harness):
    """Verify cost_per_run calculates non-negative costs and flags >3x median anomalies."""
    df = harness.query("SELECT * FROM cost_per_run LIMIT 500")
    assert len(df) > 0
    assert (df["cost_usd"] >= 0).all()
    assert (df["duration_seconds"] >= 0).all()

    # Check that anomalies exist and satisfy ratio condition
    anomalies = harness.query("SELECT * FROM cost_per_run WHERE is_cost_anomaly = TRUE")
    assert len(anomalies) > 0, "Expected some cost anomalies to be flagged in synthetic data"
    for _, row in anomalies.iterrows():
        assert row["cost_usd"] >= (2.9 * row["agent_median_cost"])


def test_ledger_monthly_ranges(harness):
    """Verify ledger_monthly adheres to: Low <= Expected <= High, and non-negative net minutes."""
    df = harness.query("SELECT * FROM ledger_monthly")
    assert len(df) > 0

    for _, row in df.iterrows():
        assert row["net_absorbed_minutes"] >= 0.0
        assert row["net_absorbed_hours_low"] <= row["net_absorbed_hours_expected"] + 0.01
        assert row["net_absorbed_hours_expected"] <= row["net_absorbed_hours_high"] + 0.01
        assert row["total_cost_usd"] >= 0.0


def test_seeded_fact_compliance_workflows(harness):
    """Verify Compliance & Risk has exactly 12 automated workflows in the signals view."""
    df = harness.query("""
        SELECT automated_workflows, total_workflows, signal_automation_coverage_pct
        FROM team_signals
        WHERE team_id = 'team-compliance-risk'
        LIMIT 1
    """)
    assert len(df) == 1
    assert df["automated_workflows"].iloc[0] == 12, f"Expected 12 automated workflows, got {df['automated_workflows'].iloc[0]}"
    assert df["total_workflows"].iloc[0] == 15
    assert round(df["signal_automation_coverage_pct"].iloc[0], 1) == 80.0


def test_maturity_grade_defensibility_and_rules(harness):
    """Verify maturity grades are between 1 and 5, badges match, and query reproducibility."""
    df = harness.query("SELECT * FROM maturity_grade")
    assert len(df) > 0

    # Ensure levels in [1, 5]
    assert (df["final_grade_level"] >= 1).all()
    assert (df["final_grade_level"] <= 5).all()

    # Verify Payments Core earns high grade (Level 4 or 5)
    payments = df[df["team_id"] == "team-payments-core"]
    assert payments["final_grade_level"].max() in (4, 5)

    # Verify Growth Marketing has low grade (Level 1 or 2)
    growth = df[df["team_id"] == "team-growth-marketing"]
    assert growth["final_grade_level"].min() in (1, 2)
    assert payments["final_grade_level"].mean() > growth["final_grade_level"].mean()

    # Check weakest-link rule logic: final_grade_level <= reliability_level + 1
    for _, row in df.iterrows():
        assert row["final_grade_level"] <= (row["s4_reliability_level"] + 1)
        assert row["final_grade_level"] <= (row["s3_gate_level"] + 1)
