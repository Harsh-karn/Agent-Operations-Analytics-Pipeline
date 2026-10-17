"""
Streamlit Interactive Operations Analytics Dashboard for Tally.

Features:
- Tab 1: Executive Value Ledger (Net Hours Saved, Ranges, Capital Efficiency)
- Tab 2: Defensible Maturity Grading & 'Show-The-Query' SQL Disclosure
- Tab 3: Contact Engine Governance (Interruption Budgets, Quiet Hours, Snooze Rates)
- Tab 4: LLM Cost Attribution & Token Anomaly Inspector (>3x Median)
- Tab 5: Interactive Dispute Simulator (Deterministic SQL Query Replay)
"""

import datetime
from pathlib import Path
import duckdb
import pandas as pd
import streamlit as st

# Page configuration
st.set_page_config(
    page_title="Tally: Agent Operations Analytics",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling (Dark Glassmorphism)
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.05) 0%, rgba(255, 255, 255, 0.01) 100%);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 12px;
        padding: 18px 22px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
    }
    .badge-gold { color: #facc15; font-weight: 700; background: rgba(250, 204, 21, 0.15); padding: 4px 8px; border-radius: 6px; }
    .badge-silver { color: #e2e8f0; font-weight: 700; background: rgba(226, 232, 240, 0.15); padding: 4px 8px; border-radius: 6px; }
    .badge-bronze { color: #f97316; font-weight: 700; background: rgba(249, 115, 22, 0.15); padding: 4px 8px; border-radius: 6px; }
    .badge-amber { color: #fbbf24; font-weight: 700; background: rgba(251, 191, 36, 0.15); padding: 4px 8px; border-radius: 6px; }
    .badge-red { color: #ef4444; font-weight: 700; background: rgba(239, 68, 68, 0.15); padding: 4px 8px; border-radius: 6px; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_warehouse_connection():
    from data.loader import get_default_harness
    return get_default_harness()


harness = get_warehouse_connection()

# Sidebar Controls
st.sidebar.title("⚖️ Tally Platform")
st.sidebar.caption("Agent Operations & Value Analytics")

# Period Selector
periods_df = harness.query("SELECT DISTINCT period FROM ledger_monthly ORDER BY period DESC;")
all_periods = periods_df["period"].tolist() if not periods_df.empty else ["2026-09"]
selected_period = st.sidebar.selectbox("📅 Reporting Period", all_periods, index=0)

st.sidebar.markdown("---")
st.sidebar.markdown("""
**Core Guarantee**:
> *"The value of the system is a measurement, not a claim, and every grade comes with the SQL that produced it."*
""")

# Main Title
st.title(f"Tally: Operational Telemetry & Governance ({selected_period})")

tabs = st.tabs([
    "📈 Value Ledger",
    "🏛 Defensible Maturity Grades",
    "🔔 Contact Budgets & Bundling",
    "💸 Cost Attribution & Anomalies",
    "⚖️ Dispute Re-evaluator",
])

# =====================================================================
# TAB 1: VALUE LEDGER
# =====================================================================
with tabs[0]:
    st.subheader("Human Work Absorbed & Capital Efficiency")

    ledger_df = harness.query(f"SELECT * FROM ledger_monthly WHERE period = '{selected_period}';")
    if not ledger_df.empty:
        total_expected_hrs = ledger_df["net_absorbed_hours_expected"].sum()
        total_low_hrs = ledger_df["net_absorbed_hours_low"].sum()
        total_high_hrs = ledger_df["net_absorbed_hours_high"].sum()
        total_cost = ledger_df["total_cost_usd"].sum()
        hours_per_dollar = round(total_expected_hrs / max(1.0, total_cost), 2)
        review_mins_deducted = ledger_df["total_review_minutes"].sum()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                label="Net Work Absorbed (Expected)",
                value=f"{total_expected_hrs:,.1f} hrs",
                delta=f"Range: {total_low_hrs:,.0f}h – {total_high_hrs:,.0f}h",
                help="Net human duration saved minus empirical human review time",
            )
        with col2:
            st.metric(
                label="Total LLM & Run Spend",
                value=f"${total_cost:,.2f}",
                delta="Attributed Token Cost",
            )
        with col3:
            st.metric(
                label="Capital Efficiency",
                value=f"{hours_per_dollar} hrs / $",
                delta="Net hours per dollar",
            )
        with col4:
            st.metric(
                label="Review Friction Deducted",
                value=f"{review_mins_deducted:,.1f} mins",
                delta="Net Human Deduction",
                delta_color="inverse",
            )

        st.markdown("### Team Value Breakdown")
        display_ledger = ledger_df[[
            "team_id", "total_runs", "approved_runs",
            "net_absorbed_hours_expected", "net_absorbed_hours_low", "net_absorbed_hours_high",
            "total_review_minutes", "total_cost_usd", "net_hours_per_dollar"
        ]].copy()
        st.dataframe(display_ledger, use_container_width=True)

# =====================================================================
# TAB 2: DEFENSIBLE MATURITY GRADING & QUERY DISCLOSURE
# =====================================================================
with tabs[1]:
    st.subheader("Team Maturity Grades (Rules Version: v1.0.0)")
    grades_df = harness.query(f"SELECT * FROM maturity_grade WHERE period = '{selected_period}' ORDER BY final_grade_level DESC;")

    if not grades_df.empty:
        st.dataframe(
            grades_df[[
                "team_id", "team_name", "grade_badge", "final_grade_level",
                "raw_weighted_score", "was_capped_by_safety_rule",
                "signal_automation_coverage_pct", "signal_eval_coverage_pct",
                "signal_gate_approval_rate_pct", "signal_failure_rate_per_100",
                "signal_adoption_pct"
            ]],
            use_container_width=True,
        )

        st.markdown("---")
        st.subheader("🔍 Show-The-Query: Grade Disclosure Inspector")
        inspect_team = st.selectbox("Select Team to Inspect Exact SQL Query:", grades_df["team_id"].tolist())

        from tally.grading import GradeService
        service = GradeService(harness=harness)
        disclosure = service.get_query_disclosure(inspect_team, selected_period)

        st.markdown(f"**Rules Version**: `{disclosure.rules_version}` | **Rules Hash**: `{disclosure.rules_hash}`")
        st.markdown("Every team can reproduce their score directly in BigQuery or DuckDB using this exact query:")
        st.code(disclosure.exact_sql_query, language="sql")
        st.info(f"**Rerun via CLI**: `{disclosure.rerun_command_bigquery}`")

# =====================================================================
# TAB 3: CONTACT BUDGETS & BUNDLING
# =====================================================================
with tabs[2]:
    st.subheader("Per-Person Interruption Budgets & Delivery Hygiene")

    people_df = harness.query("""
        SELECT
            p.person_id, p.team_id, p.name, p.timezone,
            p.weekly_interruption_budget,
            COALESCE(c.sent_count, 0) AS contact_attempts_this_month,
            COALESCE(c.snoozed_count, 0) AS snoozed_attempts
        FROM people p
        LEFT JOIN (
            SELECT
                person_id,
                COUNT(attempt_id) AS sent_count,
                COUNT(CASE WHEN snoozed = TRUE THEN 1 END) AS snoozed_count
            FROM contact_attempts
            GROUP BY person_id
        ) c ON p.person_id = c.person_id;
    """)
    st.dataframe(people_df, use_container_width=True)

    st.markdown("### Message Categories & Snooze Frequency")
    kinds_df = harness.query("""
        SELECT
            kind,
            COUNT(attempt_id) AS total_attempts,
            COUNT(CASE WHEN snoozed = TRUE THEN 1 END) AS snoozed_count,
            ROUND((COUNT(CASE WHEN snoozed = TRUE THEN 1 END) * 100.0) / COUNT(attempt_id), 1) AS snooze_rate_pct,
            CASE
                WHEN (COUNT(CASE WHEN snoozed = TRUE THEN 1 END) * 100.0) / COUNT(attempt_id) >= 35.0 THEN '🚨 THROTTLED'
                ELSE '✅ NORMAL'
            END AS throttling_status
        FROM contact_attempts
        GROUP BY kind;
    """)
    st.dataframe(kinds_df, use_container_width=True)

# =====================================================================
# TAB 4: COST OBSERVABILITY & ANOMALIES
# =====================================================================
with tabs[3]:
    st.subheader("Attributed Token Costs & Anomaly Detection")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Model Spend Distribution")
        model_spend = harness.query(f"""
            SELECT model, COUNT(run_id) AS total_runs, ROUND(SUM(cost_usd), 2) AS total_spend_usd
            FROM cost_per_run
            WHERE SUBSTRING(start_time, 1, 7) = '{selected_period}'
            GROUP BY model
            ORDER BY total_spend_usd DESC;
        """)
        st.dataframe(model_spend, use_container_width=True)

    with col2:
        st.markdown("#### Cost Anomalies (>3x Agent Median)")
        anom_df = harness.query(f"""
            SELECT run_id, agent_id, team_id, model, cost_usd, agent_median_cost, cost_ratio_to_median
            FROM cost_per_run
            WHERE SUBSTRING(start_time, 1, 7) = '{selected_period}' AND is_cost_anomaly = TRUE
            ORDER BY cost_usd DESC
            LIMIT 10;
        """)
        st.dataframe(anom_df, use_container_width=True)

# =====================================================================
# TAB 5: DISPUTE SIMULATOR
# =====================================================================
with tabs[4]:
    st.subheader("⚖️ Interactive Dispute Resolution Console")
    st.markdown("""
    When a team believes their maturity grade is inaccurate, they submit verified evidence.
    Tally re-runs the exact reproducible query against the updated warehouse state—answering with data, not opinions.
    """)

    d_team = st.selectbox("Disputing Team:", [
        "team-growth-marketing", "team-customer-ops", "team-compliance-risk", "team-data-platform"
    ])
    d_note = st.text_area(
        "Dispute Note & Rationale:",
        "Omitted 3 newly cataloged automated workflows running in production.",
    )
    new_workflows_count = st.slider("Additional Automated Workflows to Register as Evidence:", 1, 5, 2)

    if st.button("🚀 Re-run Deterministic Grading Query"):
        from tally.grading import GradeService
        svc = GradeService(harness=harness)
        result = svc.dispute_grade(
            team_id=d_team,
            period=selected_period,
            dispute_note=d_note,
            evidence={
                "add_automated_workflow": {
                    "workflow_id": f"wf-{d_team}-simulated-{int(datetime.datetime.now().timestamp())}",
                    "name": "Simulated High-Throughput Ingestion Workflow"
                }
            }
        )

        st.success("✅ Dispute Adjudicated Successfully via Deterministic SQL Replay!")
        st.json(result.model_dump())
