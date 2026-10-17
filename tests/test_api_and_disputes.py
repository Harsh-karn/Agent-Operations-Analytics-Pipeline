"""
Integration and API tests for Tally:
- FastAPI endpoint verification
- Show-the-query disclosure and SQL reproducibility test
- Dispute resolution workflow test
- Value ledger and anomaly feeds
"""

import datetime
import pytest
from fastapi.testclient import TestClient

from tally.api import app
from tally.contact.budget import MessageKind, SpendStatus


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "HEALTHY"
    assert "measurement, not a claim" in data["philosophy"]


def test_api_contact_budget_spend(client):
    person_id = "usr-payments-01"

    # Initial check
    status_res = client.get(f"/contact/budget/{person_id}")
    assert status_res.status_code == 200
    assert status_res.json()["budget_limit"] == 10

    # Spend 2 units
    spend_res = client.post("/contact/budget/spend", json={
        "person_id": person_id,
        "message_id": "msg-api-01",
        "kind": MessageKind.GATE_APPROVAL_ASK.value,
        "channel": "slack",
        "cost": 2
    })
    assert spend_res.status_code == 200
    spend_data = spend_res.json()
    assert spend_data["status"] == SpendStatus.ALLOWED.value
    assert spend_data["budget_used_after"] >= 2
    assert spend_data["authorized_token"].startswith("AUTH-SPEND-")


def test_api_candidate_submission_and_flush(client):
    now = datetime.datetime.now(datetime.timezone.utc)
    recip = "usr-api-bundler"

    # Submit candidate
    sub_res = client.post("/contact/candidates/submit", json={
        "message_id": "c-01",
        "recipient_id": recip,
        "sender_agent_id": "ag-01",
        "title": "CI Regression Report",
        "payload": "Executed 120 regression tests with 0 failures across all services.",
        "has_ask": False,
        "expires_at": (now + datetime.timedelta(hours=2)).isoformat(),
    })
    assert sub_res.status_code == 200
    assert sub_res.json()["status"] == "ENQUEUED"

    # Flush bundle
    flush_res = client.post(f"/contact/candidates/flush/{recip}")
    assert flush_res.status_code == 200
    flush_data = flush_res.json()
    assert flush_data["status"] == "COMPOSED"
    assert flush_data["message"]["recipient_id"] == recip


def test_api_grade_and_query_disclosure(client):
    team_id = "team-compliance-risk"
    period = "2026-09"

    # 1. Fetch Grade
    grade_res = client.get(f"/grades/{team_id}/{period}")
    assert grade_res.status_code == 200
    g_data = grade_res.json()
    assert g_data["team_id"] == team_id
    assert g_data["final_grade_level"] in (3, 4, 5)
    assert "signal_breakdown" in g_data

    # 2. Fetch Show-the-Query Disclosure
    query_res = client.get(f"/grades/{team_id}/{period}/query")
    assert query_res.status_code == 200
    q_data = query_res.json()
    assert q_data["team_id"] == team_id
    assert "FROM maturity_grade" in q_data["exact_sql_query"]
    assert "rules_hash" in q_data
    assert "duckdb" in q_data["rerun_command_duckdb"]

    # 3. Defensibility Verification: Rerun the exact disclosed SQL directly
    # and confirm it yields the identical grade!
    from tally.api import grade_service
    reproduced_df = grade_service.harness.query(q_data["exact_sql_query"])
    assert len(reproduced_df) == 1
    reproduced_level = int(reproduced_df["final_grade_level"].iloc[0])
    assert reproduced_level == g_data["final_grade_level"], (
        f"Disclosed SQL reproduced grade level {reproduced_level}, but API served {g_data['final_grade_level']}"
    )


def test_api_dispute_resolution(client):
    team_id = "team-growth-marketing"
    period = "2026-09"

    dispute_payload = {
        "dispute_note": "Omitted newly launched automated lifecycle onboarding workflow that ran continuously in Sept.",
        "evidence": {
            "add_automated_workflow": {
                "workflow_id": "wf-growth-onboarding-auto",
                "name": "Automated Lifecycle Onboarding Engine"
            }
        }
    }

    res = client.post(f"/grades/{team_id}/{period}/dispute", json=dispute_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["team_id"] == team_id
    assert "evidence_applied" in data
    assert data["reproduced_with_sql_hash"] != ""


def test_api_warehouse_ledger_and_anomalies(client):
    # Ledger feed
    l_res = client.get("/ledger/monthly")
    assert l_res.status_code == 200
    records = l_res.json()
    assert len(records) > 0
    assert "net_absorbed_hours_expected" in records[0]

    # Anomalies feed
    a_res = client.get("/runs/anomalies?limit=10")
    assert a_res.status_code == 200
    anomalies = a_res.json()
    assert len(anomalies) > 0
    assert anomalies[0]["cost_ratio_to_median"] >= 3.0
