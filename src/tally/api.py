"""
FastAPI Service for Tally: Agent Operations Analytics Pipeline.

Exposes:
- Interruption budget transactions & enforcement (POST /contact/budget/spend)
- Defensible team maturity grades (GET /grades/{team}/{period})
- Immutable SQL query disclosure (GET /grades/{team}/{period}/query)
- Evidence-based dispute resolution endpoint (POST /grades/{team}/{period}/dispute)
- Value ledger and cost anomaly feeds (GET /ledger/monthly, GET /runs/anomalies)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field

from tally.contact.budget import (
    ContactBudgetManager,
    MessageKind,
    SpendResult,
    SpendStatus,
)
from tally.contact.bundler import (
    CandidateMessage,
    MessageBundler,
)
from tally.contact.composer import (
    MessageComposer,
    SnoozeTracker,
)
from tally.grading import (
    DisputeResolutionResult,
    GradeQueryDisclosure,
    GradeService,
    TeamGradeReport,
)

app = FastAPI(
    title="Agent Operations Analytics Pipeline API",
    version="0.1.0",
    description="Operational measurement, interruption budgeting, value ledger, and defensible maturity grading.",
)

# Global in-memory / state singletons
budget_mgr = ContactBudgetManager(db_path=":memory:")
bundler = MessageBundler()
snooze_tracker = SnoozeTracker()
composer = MessageComposer(snooze_tracker=snooze_tracker)
grade_service = GradeService()

# Seed a few test users in the budget manager for immediate out-of-the-box operation
budget_mgr.set_budget("usr-payments-01", limit=10, timezone="America/New_York")
budget_mgr.set_budget("usr-compliance-01", limit=8, timezone="Europe/London")
budget_mgr.set_budget("usr-ops-01", limit=5, timezone="America/Los_Angeles")


class SpendRequest(BaseModel):
    person_id: str
    message_id: str
    kind: MessageKind = MessageKind.FYI_DIGEST
    channel: str = "slack"
    cost: Optional[int] = None


class DisputeRequest(BaseModel):
    dispute_note: str = Field(..., description="Justification and explanation of data discrepancy")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Verified evidence payload (e.g. missing workflow)")


@app.get("/", tags=["Health"])
def health_check():
    return {
        "service": "Agent Operations Analytics Pipeline",
        "status": "HEALTHY",
        "philosophy": "The value of the system is a measurement, not a claim, and every grade comes with the SQL that produced it.",
    }


# =====================================================================
# 1. Contact Engine Endpoints
# =====================================================================

@app.post("/contact/budget/spend", response_model=SpendResult, tags=["Contact Budget"])
def spend_budget(req: SpendRequest):
    """
    Atomic transactional spend attempt.
    Guarantees hard interruption budget limits.
    """
    result = budget_mgr.try_spend(
        person_id=req.person_id,
        message_id=req.message_id,
        kind=req.kind,
        channel=req.channel,
        cost=req.cost,
    )
    return result


@app.get("/contact/budget/{person_id}", tags=["Contact Budget"])
def get_budget_status(person_id: str):
    """Fetches remaining interruption budget and quiet hours settings for a person."""
    status = budget_mgr.get_budget(person_id)
    if not status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Budget profile for person {person_id} not found",
        )
    return status


@app.post("/contact/candidates/submit", tags=["Contact Bundler"])
def submit_candidate(candidate: CandidateMessage):
    """Producers (agents) submit candidate messages to the queue."""
    bundler.submit(candidate)
    return {
        "status": "ENQUEUED",
        "message_id": candidate.message_id,
        "recipient_id": candidate.recipient_id,
        "queue_size": bundler.get_queue_size(candidate.recipient_id),
    }


@app.post("/contact/candidates/flush/{recipient_id}", tags=["Contact Bundler"])
def flush_and_compose(recipient_id: str):
    """Flushes recipient's queue, bundles items, and validates via value-first composer."""
    bundle = bundler.flush_bundle(recipient_id)
    if not bundle:
        return {"status": "NO_PENDING_MESSAGES", "recipient_id": recipient_id}

    res = composer.validate_and_compose(bundle)
    if not res.is_valid:
        return {
            "status": "REJECTED_BY_COMPOSER",
            "reason": res.rejection_reason,
            "bundle": bundle,
        }

    return {
        "status": "COMPOSED",
        "message": res.composed_message,
        "bundle_summary": {
            "items_merged": bundle.items_count,
            "duplicates_dropped": bundle.items_deduplicated_count,
            "expired_dropped": bundle.items_expired_dropped_count,
        }
    }


# =====================================================================
# 2. Defensible Grading & Dispute Disclosure Endpoints
# =====================================================================

@app.get("/grades/{team_id}/{period}", response_model=TeamGradeReport, tags=["Maturity Grades"])
def get_grade(team_id: str, period: str):
    """Returns computed team maturity grade, 5 signals, and rule breakdown."""
    grade = grade_service.get_team_grade(team_id, period)
    if not grade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Grade not found for team {team_id} in period {period}",
        )
    return grade


@app.get("/grades/{team_id}/{period}/query", response_model=GradeQueryDisclosure, tags=["Maturity Grades"])
def get_grade_query(team_id: str, period: str):
    """
    Returns the exact immutable SQL query string and rule hash that produced the grade.
    The answer to disputes is data and verifiable queries, not opinions.
    """
    return grade_service.get_query_disclosure(team_id, period)


@app.post("/grades/{team_id}/{period}/dispute", response_model=DisputeResolutionResult, tags=["Maturity Grades"])
def dispute_grade(team_id: str, period: str, req: DisputeRequest):
    """
    Submits a grade dispute note with evidence.
    Reruns the exact SQL query against updated source data and issues an audited resolution.
    """
    result = grade_service.dispute_grade(
        team_id=team_id,
        period=period,
        dispute_note=req.dispute_note,
        evidence=req.evidence,
    )
    return result


# =====================================================================
# 3. Warehouse Feeds: Value Ledger & Cost Anomalies
# =====================================================================

@app.get("/ledger/monthly", tags=["Warehouse Telemetry"])
def get_monthly_ledger(period: Optional[str] = Query(None, description="Optional YYYY-MM filter")):
    """Returns monthly net hours saved, cost, and hours per dollar across teams."""
    sql = "SELECT * FROM ledger_monthly"
    if period:
        sql += f" WHERE period = '{period}'"
    sql += " ORDER BY period DESC, net_absorbed_hours_expected DESC;"
    df = grade_service.harness.query(sql)
    return df.to_dict(orient="records")


@app.get("/runs/anomalies", tags=["Warehouse Telemetry"])
def get_cost_anomalies(limit: int = 50):
    """Returns agent runs flagged as cost anomalies (>3x agent median)."""
    sql = f"""
        SELECT
            run_id, agent_id, team_id, model, cost_usd,
            agent_median_cost, cost_ratio_to_median, duration_seconds, start_time
        FROM cost_per_run
        WHERE is_cost_anomaly = TRUE
        ORDER BY cost_usd DESC
        LIMIT {limit};
    """
    df = grade_service.harness.query(sql)
    return df.to_dict(orient="records")
