"""
Unit tests for Synthetic Data Generator and Seeded Known Facts
"""

from data.generate import SyntheticDataGenerator, SEED_COMPLIANCE_AUTOMATED_WORKFLOWS
from data.loader import WarehouseHarness


def test_generator_structure_and_seeded_facts():
    gen = SyntheticDataGenerator(seed=42, months=2)
    data = gen.generate_all()

    # Verify tables present
    required_tables = [
        "teams", "people", "agents", "workflows", "agent_baselines",
        "eval_results", "runs", "events", "approvals", "reviewer_feedback",
        "incidents", "contact_attempts"
    ]
    for table in required_tables:
        assert table in data, f"Missing table {table}"
        assert len(data[table]) > 0, f"Table {table} is empty"

    # Verify 5 distinct teams
    assert len(data["teams"]) == 5

    # Verify seeded fact: Compliance & Risk has exactly 12 automated workflows
    compliance_workflows = [
        w for w in data["workflows"]
        if w["team_id"] == "team-compliance-risk" and w["is_automated"] is True
    ]
    assert len(compliance_workflows) == SEED_COMPLIANCE_AUTOMATED_WORKFLOWS, (
        f"Expected {SEED_COMPLIANCE_AUTOMATED_WORKFLOWS} automated workflows for Compliance team, "
        f"got {len(compliance_workflows)}"
    )


def test_warehouse_harness_duckdb():
    harness = WarehouseHarness()
    # Test creating and querying
    harness.execute("CREATE TABLE test_runs (run_id VARCHAR, cost_usd DOUBLE);")
    harness.execute("INSERT INTO test_runs VALUES ('run-01', 0.045), ('run-02', 0.012);")
    df = harness.query("SELECT COUNT(*) as cnt, SUM(cost_usd) as total_cost FROM test_runs")
    assert df["cnt"].iloc[0] == 2
    assert round(df["total_cost"].iloc[0], 3) == 0.057
    harness.close()
