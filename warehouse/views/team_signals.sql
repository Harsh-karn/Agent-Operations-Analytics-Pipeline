-- =====================================================================
-- View: team_signals
-- Computes the 5 core operational telemetry signals per team per period
-- 1. Automation Coverage (workflows)
-- 2. Evaluation Coverage (eval benchmark results)
-- 3. Gate Health (approval rate and review duration)
-- 4. Reliability (failure and incident rate per 100 runs)
-- 5. Adoption & Hygiene (active user engagement and snooze rate)
-- =====================================================================

CREATE OR REPLACE VIEW team_signals AS
WITH periods_teams AS (
    SELECT DISTINCT
        SUBSTRING(start_time, 1, 7) AS period,
        team_id
    FROM runs
),
wf_stats AS (
    SELECT
        team_id,
        COUNT(workflow_id) AS total_workflows,
        COUNT(CASE WHEN is_automated = TRUE THEN 1 END) AS automated_workflows,
        ROUND((COUNT(CASE WHEN is_automated = TRUE THEN 1 END) * 100.0) / NULLIF(COUNT(workflow_id), 0), 2) AS automation_coverage_pct
    FROM workflows
    GROUP BY team_id
),
eval_stats AS (
    SELECT
        a.team_id,
        COUNT(DISTINCT a.agent_id) AS total_agents,
        COUNT(DISTINCT CASE WHEN e.passed = TRUE THEN a.agent_id END) AS agents_with_passing_eval,
        ROUND(
            (COUNT(DISTINCT CASE WHEN e.passed = TRUE THEN a.agent_id END) * 100.0) /
            NULLIF(COUNT(DISTINCT a.agent_id), 0),
            2
        ) AS eval_coverage_pct
    FROM agents a
    LEFT JOIN eval_results e ON a.agent_id = e.agent_id
    GROUP BY a.team_id
),
gate_stats AS (
    SELECT
        SUBSTRING(r.start_time, 1, 7) AS period,
        r.team_id,
        COUNT(a.approval_id) AS total_approval_requests,
        COUNT(CASE WHEN a.decision IN ('APPROVED_AS_IS', 'APPROVED_WITH_EDITS') THEN 1 END) AS total_approvals,
        ROUND(
            (COUNT(CASE WHEN a.decision IN ('APPROVED_AS_IS', 'APPROVED_WITH_EDITS') THEN 1 END) * 100.0) /
            NULLIF(COUNT(a.approval_id), 0),
            2
        ) AS gate_approval_rate_pct,
        ROUND(MEDIAN(a.human_review_minutes), 1) AS median_approval_minutes
    FROM runs r
    JOIN approvals a ON r.run_id = a.run_id
    GROUP BY SUBSTRING(r.start_time, 1, 7), r.team_id
),
reliability_stats AS (
    SELECT
        SUBSTRING(r.start_time, 1, 7) AS period,
        r.team_id,
        COUNT(r.run_id) AS total_runs,
        COUNT(CASE WHEN r.status IN ('FAILED', 'ROLLED_BACK') THEN 1 END) AS failed_runs,
        COALESCE(inc.incident_count, 0) AS incident_count,
        ROUND(
            ((COUNT(CASE WHEN r.status IN ('FAILED', 'ROLLED_BACK') THEN 1 END) + COALESCE(inc.incident_count, 0)) * 100.0) /
            NULLIF(COUNT(r.run_id), 0),
            2
        ) AS failure_rate_per_100
    FROM runs r
    LEFT JOIN (
        SELECT
            SUBSTRING(occurred_at, 1, 7) AS period,
            team_id,
            COUNT(incident_id) AS incident_count
        FROM incidents
        GROUP BY SUBSTRING(occurred_at, 1, 7), team_id
    ) inc ON SUBSTRING(r.start_time, 1, 7) = inc.period AND r.team_id = inc.team_id
    GROUP BY SUBSTRING(r.start_time, 1, 7), r.team_id, inc.incident_count
),
adoption_stats AS (
    SELECT
        pt.period,
        pt.team_id,
        COUNT(DISTINCT p.person_id) AS total_team_members,
        COUNT(DISTINCT a.person_id) AS active_reviewers,
        ROUND(
            (COUNT(DISTINCT a.person_id) * 100.0) / NULLIF(COUNT(DISTINCT p.person_id), 0),
            2
        ) AS adoption_pct,
        COALESCE(cnt.snooze_rate_pct, 0.0) AS snooze_rate_pct
    FROM periods_teams pt
    JOIN people p ON pt.team_id = p.team_id
    LEFT JOIN (
        SELECT DISTINCT
            SUBSTRING(r.start_time, 1, 7) AS period,
            ap.person_id
        FROM runs r
        JOIN approvals ap ON r.run_id = ap.run_id
    ) a ON pt.period = a.period AND p.person_id = a.person_id
    LEFT JOIN (
        SELECT
            SUBSTRING(ca.sent_at, 1, 7) AS period,
            pe.team_id,
            ROUND(
                (COUNT(CASE WHEN ca.snoozed = TRUE THEN 1 END) * 100.0) /
                NULLIF(COUNT(ca.attempt_id), 0),
                2
            ) AS snooze_rate_pct
        FROM contact_attempts ca
        JOIN people pe ON ca.person_id = pe.person_id
        GROUP BY SUBSTRING(ca.sent_at, 1, 7), pe.team_id
    ) cnt ON pt.period = cnt.period AND pt.team_id = cnt.team_id
    GROUP BY pt.period, pt.team_id, cnt.snooze_rate_pct
)
SELECT
    pt.period,
    pt.team_id,
    t.name AS team_name,
    COALESCE(wf.automation_coverage_pct, 0.0) AS signal_automation_coverage_pct,
    COALESCE(ev.eval_coverage_pct, 0.0) AS signal_eval_coverage_pct,
    COALESCE(gt.gate_approval_rate_pct, 0.0) AS signal_gate_approval_rate_pct,
    COALESCE(gt.median_approval_minutes, 0.0) AS signal_median_approval_minutes,
    COALESCE(rel.failure_rate_per_100, 0.0) AS signal_failure_rate_per_100,
    COALESCE(ad.adoption_pct, 0.0) AS signal_adoption_pct,
    COALESCE(ad.snooze_rate_pct, 0.0) AS signal_snooze_rate_pct,
    wf.total_workflows,
    wf.automated_workflows,
    rel.total_runs
FROM periods_teams pt
JOIN teams t ON pt.team_id = t.team_id
LEFT JOIN wf_stats wf ON pt.team_id = wf.team_id
LEFT JOIN eval_stats ev ON pt.team_id = ev.team_id
LEFT JOIN gate_stats gt ON pt.period = gt.period AND pt.team_id = gt.team_id
LEFT JOIN reliability_stats rel ON pt.period = rel.period AND pt.team_id = rel.team_id
LEFT JOIN adoption_stats ad ON pt.period = ad.period AND pt.team_id = ad.team_id;
