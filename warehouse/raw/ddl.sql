-- =====================================================================
-- Agent Operations Analytics Pipeline Warehouse DDL (BigQuery Standard SQL)
-- Raw ingest tables partitioned by date and clustered by team_id, agent_id
-- =====================================================================

-- 1. Teams Registry
CREATE TABLE IF NOT EXISTS agent_ops_raw.teams (
    team_id STRING NOT NULL,
    name STRING NOT NULL,
    domain STRING NOT NULL,
    created_at TIMESTAMP NOT NULL
);

-- 2. People & Interruption Budget Limits
CREATE TABLE IF NOT EXISTS agent_ops_raw.people (
    person_id STRING NOT NULL,
    team_id STRING NOT NULL,
    name STRING NOT NULL,
    email STRING NOT NULL,
    timezone STRING NOT NULL,
    quiet_hours_start INT64 NOT NULL,
    quiet_hours_end INT64 NOT NULL,
    weekly_interruption_budget INT64 NOT NULL
);

-- 3. Agents Registry
CREATE TABLE IF NOT EXISTS agent_ops_raw.agents (
    agent_id STRING NOT NULL,
    team_id STRING NOT NULL,
    name STRING NOT NULL,
    version STRING NOT NULL,
    status STRING NOT NULL,
    created_at TIMESTAMP NOT NULL
);

-- 4. Workflows Registry
CREATE TABLE IF NOT EXISTS agent_ops_raw.workflows (
    workflow_id STRING NOT NULL,
    team_id STRING NOT NULL,
    name STRING NOT NULL,
    is_automated BOOLEAN NOT NULL,
    cadence STRING NOT NULL,
    description STRING
);

-- 5. Agent Empirical Baselines
CREATE TABLE IF NOT EXISTS agent_ops_raw.agent_baselines (
    agent_id STRING NOT NULL,
    task_description STRING NOT NULL,
    baseline_minutes FLOAT64 NOT NULL,
    method STRING NOT NULL,
    measured_on DATE NOT NULL,
    confidence STRING NOT NULL  -- 'HIGH', 'MEDIUM', 'LOW'
);

-- 6. Evaluation Benchmark Results
CREATE TABLE IF NOT EXISTS agent_ops_raw.eval_results (
    eval_id STRING NOT NULL,
    agent_id STRING NOT NULL,
    test_suite_name STRING NOT NULL,
    score FLOAT64 NOT NULL,
    passed BOOLEAN NOT NULL,
    evaluated_at TIMESTAMP NOT NULL
);

-- 7. Agent Execution Runs
-- Partitioned by date of start_time, clustered by team_id and agent_id
CREATE TABLE IF NOT EXISTS agent_ops_raw.runs (
    run_id STRING NOT NULL,
    agent_id STRING NOT NULL,
    team_id STRING NOT NULL,
    workflow_id STRING NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    status STRING NOT NULL,  -- 'COMPLETED', 'FAILED', 'ROLLED_BACK'
    prompt_tokens INT64 NOT NULL,
    completion_tokens INT64 NOT NULL,
    model STRING NOT NULL,
    cost_usd FLOAT64 NOT NULL
)
PARTITION BY DATE(start_time)
CLUSTER BY team_id, agent_id;

-- 8. Run Telemetry Events
-- Partitioned by date of timestamp, clustered by run_id
CREATE TABLE IF NOT EXISTS agent_ops_raw.events (
    event_id STRING NOT NULL,
    run_id STRING NOT NULL,
    event_type STRING NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    payload_json STRING
)
PARTITION BY DATE(timestamp)
CLUSTER BY run_id;

-- 9. Human Review Approvals (Gate Health)
CREATE TABLE IF NOT EXISTS agent_ops_raw.approvals (
    approval_id STRING NOT NULL,
    run_id STRING NOT NULL,
    person_id STRING NOT NULL,
    decision STRING NOT NULL,  -- 'APPROVED_AS_IS', 'APPROVED_WITH_EDITS', 'REJECTED'
    requested_at TIMESTAMP NOT NULL,
    decided_at TIMESTAMP NOT NULL,
    human_review_minutes FLOAT64 NOT NULL,
    edit_summary STRING
);

-- 10. Reviewer Feedback
CREATE TABLE IF NOT EXISTS agent_ops_raw.reviewer_feedback (
    feedback_id STRING NOT NULL,
    run_id STRING NOT NULL,
    person_id STRING NOT NULL,
    rating INT64 NOT NULL,
    comments STRING,
    created_at TIMESTAMP NOT NULL
);

-- 11. Incidents & Rollbacks
CREATE TABLE IF NOT EXISTS agent_ops_raw.incidents (
    incident_id STRING NOT NULL,
    run_id STRING NOT NULL,
    team_id STRING NOT NULL,
    severity STRING NOT NULL,  -- 'SEV1', 'SEV2', 'SEV3'
    description STRING NOT NULL,
    root_cause STRING,
    occurred_at TIMESTAMP NOT NULL,
    resolved_at TIMESTAMP
);

-- 12. Contact Log & Delivery Attempts
CREATE TABLE IF NOT EXISTS agent_ops_raw.contact_attempts (
    attempt_id STRING NOT NULL,
    person_id STRING NOT NULL,
    agent_id STRING NOT NULL,
    kind STRING NOT NULL,
    urgency STRING NOT NULL,
    has_payload BOOLEAN NOT NULL,
    has_ask BOOLEAN NOT NULL,
    ask_count INT64 NOT NULL,
    payload_preview STRING,
    sent_at TIMESTAMP NOT NULL,
    status STRING NOT NULL,  -- 'ALLOWED', 'BLOCKED_BUDGET', 'HELD_QUIET_HOURS', 'REJECTED_COMPOSER'
    snoozed BOOLEAN NOT NULL
);
