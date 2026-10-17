-- =====================================================================
-- View: ledger_monthly
-- Audited monthly ledger of work absorbed by autonomous agents
-- Implements net review time deduction and Low/Expected/High confidence ranges
-- =====================================================================

CREATE OR REPLACE VIEW ledger_monthly AS
WITH run_level_ledger AS (
    SELECT
        r.run_id,
        r.agent_id,
        r.team_id,
        r.cost_usd,
        SUBSTRING(r.start_time, 1, 7) AS period,
        b.baseline_minutes,
        b.confidence,
        CASE
            WHEN b.confidence = 'HIGH' THEN 0.10
            WHEN b.confidence = 'MEDIUM' THEN 0.25
            ELSE 0.40
        END AS uncertainty_factor,
        COALESCE(a.decision, 'REJECTED') AS approval_decision,
        COALESCE(a.human_review_minutes, 0.0) AS human_review_minutes,
        -- Approval Factor: 1.0 for as-is, 0.5 for edits, 0.0 for rejected/failed
        CASE
            WHEN r.status != 'COMPLETED' THEN 0.0
            WHEN a.decision = 'APPROVED_AS_IS' THEN 1.0
            WHEN a.decision = 'APPROVED_WITH_EDITS' THEN 0.5
            ELSE 0.0
        END AS approval_factor,
        -- Gross Minutes Absorbed
        CASE
            WHEN r.status = 'COMPLETED' AND a.decision = 'APPROVED_AS_IS' THEN b.baseline_minutes
            WHEN r.status = 'COMPLETED' AND a.decision = 'APPROVED_WITH_EDITS' THEN b.baseline_minutes * 0.5
            ELSE 0.0
        END AS gross_minutes_absorbed,
        -- Net Minutes Absorbed (Subtract human review duration, floor at zero)
        GREATEST(
            0.0,
            CASE
                WHEN r.status = 'COMPLETED' AND a.decision = 'APPROVED_AS_IS'
                    THEN (b.baseline_minutes - COALESCE(a.human_review_minutes, 0.0))
                WHEN r.status = 'COMPLETED' AND a.decision = 'APPROVED_WITH_EDITS'
                    THEN ((b.baseline_minutes * 0.5) - COALESCE(a.human_review_minutes, 0.0))
                ELSE 0.0
            END
        ) AS net_minutes_absorbed
    FROM runs r
    JOIN agent_baselines b ON r.agent_id = b.agent_id
    LEFT JOIN approvals a ON r.run_id = a.run_id
)
SELECT
    period,
    team_id,
    COUNT(run_id) AS total_runs,
    COUNT(CASE WHEN approval_factor > 0 THEN 1 END) AS approved_runs,
    ROUND(SUM(gross_minutes_absorbed), 1) AS gross_absorbed_minutes,
    ROUND(SUM(human_review_minutes), 1) AS total_review_minutes,
    ROUND(SUM(net_minutes_absorbed), 1) AS net_absorbed_minutes,
    ROUND(SUM(net_minutes_absorbed) / 60.0, 2) AS net_absorbed_hours_expected,
    ROUND(SUM(net_minutes_absorbed * (1.0 - uncertainty_factor)) / 60.0, 2) AS net_absorbed_hours_low,
    ROUND(SUM(net_minutes_absorbed * (1.0 + uncertainty_factor)) / 60.0, 2) AS net_absorbed_hours_high,
    ROUND(SUM(cost_usd), 2) AS total_cost_usd,
    ROUND(
        (SUM(net_minutes_absorbed) / 60.0) / NULLIF(SUM(cost_usd), 0.0),
        2
    ) AS net_hours_per_dollar
FROM run_level_ledger
GROUP BY period, team_id;
