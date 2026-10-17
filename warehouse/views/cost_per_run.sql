-- =====================================================================
-- View: cost_per_run
-- Fully attributed cost per run with duration, model, and anomaly flags
-- =====================================================================

CREATE OR REPLACE VIEW cost_per_run AS
WITH run_durations AS (
    SELECT
        r.run_id,
        r.agent_id,
        r.team_id,
        r.workflow_id,
        r.start_time,
        r.end_time,
        r.status,
        r.prompt_tokens,
        r.completion_tokens,
        (r.prompt_tokens + r.completion_tokens) AS total_tokens,
        r.model,
        r.cost_usd,
        ROUND(date_diff('second', CAST(r.start_time AS TIMESTAMP), CAST(r.end_time AS TIMESTAMP)), 2) AS duration_seconds
    FROM runs r
),
agent_benchmarks AS (
    SELECT
        agent_id,
        ROUND(MEDIAN(cost_usd), 6) AS agent_median_cost,
        ROUND(AVG(cost_usd), 6) AS agent_avg_cost
    FROM runs
    GROUP BY agent_id
)
SELECT
    rd.run_id,
    rd.agent_id,
    rd.team_id,
    rd.workflow_id,
    rd.start_time,
    rd.end_time,
    rd.status,
    rd.prompt_tokens,
    rd.completion_tokens,
    rd.total_tokens,
    rd.model,
    rd.cost_usd,
    rd.duration_seconds,
    ab.agent_median_cost,
    ab.agent_avg_cost,
    CASE
        WHEN rd.cost_usd > (3.0 * ab.agent_median_cost) THEN TRUE
        ELSE FALSE
    END AS is_cost_anomaly,
    CASE
        WHEN ab.agent_median_cost > 0 THEN ROUND(rd.cost_usd / ab.agent_median_cost, 2)
        ELSE 1.0
    END AS cost_ratio_to_median
FROM run_durations rd
JOIN agent_benchmarks ab ON rd.agent_id = ab.agent_id;
