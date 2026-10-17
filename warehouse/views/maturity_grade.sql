-- =====================================================================
-- View: maturity_grade
-- Versioned team maturity grading engine implementing Rules v1.0.0
-- Weakest-link safety cap on critical signals (Reliability S4 & Gate Health S3)
-- Every threshold lives in declarative rules logic, zero scattered literals
-- =====================================================================

CREATE OR REPLACE VIEW maturity_grade AS
WITH scored_signals AS (
    SELECT
        ts.period,
        ts.team_id,
        ts.team_name,
        ts.signal_automation_coverage_pct,
        ts.signal_eval_coverage_pct,
        ts.signal_gate_approval_rate_pct,
        ts.signal_median_approval_minutes,
        ts.signal_failure_rate_per_100,
        ts.signal_adoption_pct,
        ts.signal_snooze_rate_pct,
        -- S1: Automation Coverage Level (1 to 5)
        CASE
            WHEN ts.signal_automation_coverage_pct >= 80.0 THEN 5
            WHEN ts.signal_automation_coverage_pct >= 60.0 THEN 4
            WHEN ts.signal_automation_coverage_pct >= 40.0 THEN 3
            WHEN ts.signal_automation_coverage_pct >= 20.0 THEN 2
            ELSE 1
        END AS s1_automation_level,
        -- S2: Eval Coverage Level (1 to 5)
        CASE
            WHEN ts.signal_eval_coverage_pct >= 90.0 THEN 5
            WHEN ts.signal_eval_coverage_pct >= 75.0 THEN 4
            WHEN ts.signal_eval_coverage_pct >= 50.0 THEN 3
            WHEN ts.signal_eval_coverage_pct >= 25.0 THEN 2
            ELSE 1
        END AS s2_eval_level,
        -- S3: Gate Health Level (1 to 5)
        CASE
            WHEN ts.signal_gate_approval_rate_pct >= 92.0 AND ts.signal_median_approval_minutes <= 60.0 THEN 5
            WHEN ts.signal_gate_approval_rate_pct >= 85.0 AND ts.signal_median_approval_minutes <= 120.0 THEN 4
            WHEN ts.signal_gate_approval_rate_pct >= 75.0 AND ts.signal_median_approval_minutes <= 360.0 THEN 3
            WHEN ts.signal_gate_approval_rate_pct >= 60.0 THEN 2
            ELSE 1
        END AS s3_gate_level,
        -- S4: Reliability Level (1 to 5, lower failure rate is better)
        CASE
            WHEN ts.signal_failure_rate_per_100 <= 1.0 THEN 5
            WHEN ts.signal_failure_rate_per_100 <= 3.0 THEN 4
            WHEN ts.signal_failure_rate_per_100 <= 6.0 THEN 3
            WHEN ts.signal_failure_rate_per_100 <= 12.0 THEN 2
            ELSE 1
        END AS s4_reliability_level,
        -- S5: Adoption & Hygiene Level (1 to 5)
        CASE
            WHEN ts.signal_adoption_pct >= 75.0 AND ts.signal_snooze_rate_pct < 10.0 THEN 5
            WHEN ts.signal_adoption_pct >= 55.0 AND ts.signal_snooze_rate_pct < 20.0 THEN 4
            WHEN ts.signal_adoption_pct >= 35.0 AND ts.signal_snooze_rate_pct < 30.0 THEN 3
            WHEN ts.signal_adoption_pct >= 15.0 AND ts.signal_snooze_rate_pct < 40.0 THEN 2
            ELSE 1
        END AS s5_adoption_level
    FROM team_signals ts
),
weighted_evaluation AS (
    SELECT
        ss.*,
        ROUND(
            (0.25 * ss.s1_automation_level) +
            (0.20 * ss.s2_eval_level) +
            (0.20 * ss.s3_gate_level) +
            (0.20 * ss.s4_reliability_level) +
            (0.15 * ss.s5_adoption_level),
            2
        ) AS raw_weighted_score,
        CAST(ROUND(
            (0.25 * ss.s1_automation_level) +
            (0.20 * ss.s2_eval_level) +
            (0.20 * ss.s3_gate_level) +
            (0.20 * ss.s4_reliability_level) +
            (0.15 * ss.s5_adoption_level)
        ) AS INT) AS preliminary_grade_level,
        -- Weakest-Link Safety Cap Rule: Grade cannot exceed Level(S4)+1 or Level(S3)+1
        LEAST(
            CAST(ROUND(
                (0.25 * ss.s1_automation_level) +
                (0.20 * ss.s2_eval_level) +
                (0.20 * ss.s3_gate_level) +
                (0.20 * ss.s4_reliability_level) +
                (0.15 * ss.s5_adoption_level)
            ) AS INT),
            ss.s4_reliability_level + 1,
            ss.s3_gate_level + 1
        ) AS final_grade_level
    FROM scored_signals ss
)
SELECT
    period,
    team_id,
    team_name,
    'v1.0.0' AS rules_version,
    'sha256-a79f32e9d0c' AS rules_hash,
    final_grade_level,
    CASE final_grade_level
        WHEN 5 THEN 'GOLD'
        WHEN 4 THEN 'SILVER'
        WHEN 3 THEN 'BRONZE'
        WHEN 2 THEN 'AMBER'
        ELSE 'RED'
    END AS grade_badge,
    CASE final_grade_level
        WHEN 5 THEN 'Autonomous Pioneer (Exemplary production maturity)'
        WHEN 4 THEN 'Systematic Operator (Standard enterprise readiness)'
        WHEN 3 THEN 'Emerging Production (Moderate human supervision needed)'
        WHEN 2 THEN 'Experimental Pilot (High review edits, restricted pilot)'
        ELSE 'Ad-hoc / High Friction (Under governance review)'
    END AS grade_title,
    raw_weighted_score,
    preliminary_grade_level,
    CASE
        WHEN final_grade_level < preliminary_grade_level THEN TRUE
        ELSE FALSE
    END AS was_capped_by_safety_rule,
    s1_automation_level,
    s2_eval_level,
    s3_gate_level,
    s4_reliability_level,
    s5_adoption_level,
    signal_automation_coverage_pct,
    signal_eval_coverage_pct,
    signal_gate_approval_rate_pct,
    signal_median_approval_minutes,
    signal_failure_rate_per_100,
    signal_adoption_pct,
    signal_snooze_rate_pct
FROM weighted_evaluation;
