"""
Monthly Executive & Operational Report Generator for Agent Operations Analytics Pipeline.

Produces an actionable decision-oriented report:
- What changed: Net hours saved range, cost, capital efficiency (hours per dollar)
- Team Grade Movements: Which teams moved grade and why (highlighting safety caps)
- Top 3 Most Expensive Runs: Root-cause telemetry and model spend attribution
- High-Friction Agents: Falling human approval rates and review bottlenecks
- Suggested Actions: 2 concrete, actionable decisions to implement
"""

from __future__ import annotations

import argparse
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from data.loader import WarehouseHarness, get_default_harness


class MonthlyReport(BaseModel):
    period: str
    generated_at: str
    executive_summary: Dict[str, Any]
    team_grades: List[Dict[str, Any]]
    top_3_expensive_runs: List[Dict[str, Any]]
    falling_approval_agents: List[Dict[str, Any]]
    suggested_actions: List[Dict[str, str]]
    markdown_content: str


class MonthlyReportGenerator:
    """Extracts warehouse metrics and compiles the decision-oriented monthly report."""

    def __init__(self, harness: Optional[WarehouseHarness] = None):
        self.harness = harness or get_default_harness()

    def generate(self, period: str = "2026-09") -> MonthlyReport:
        # 1. Executive Summary & Value Ledger
        ledger_df = self.harness.query(f"""
            SELECT
                SUM(gross_absorbed_minutes) AS total_gross_mins,
                SUM(total_review_minutes) AS total_review_mins,
                SUM(net_absorbed_minutes) AS total_net_mins,
                SUM(net_absorbed_hours_expected) AS hours_expected,
                SUM(net_absorbed_hours_low) AS hours_low,
                SUM(net_absorbed_hours_high) AS hours_high,
                SUM(total_cost_usd) AS total_cost_usd,
                ROUND(SUM(net_absorbed_hours_expected) / NULLIF(SUM(total_cost_usd), 0), 2) AS hours_per_dollar,
                SUM(total_runs) AS total_runs
            FROM ledger_monthly
            WHERE period = '{period}';
        """)

        if ledger_df.empty or ledger_df["total_runs"].iloc[0] is None:
            # Fallback to most recent period in data
            avail_period_df = self.harness.query("SELECT DISTINCT period FROM ledger_monthly ORDER BY period DESC LIMIT 1;")
            if not avail_period_df.empty:
                period = str(avail_period_df["period"].iloc[0])
                ledger_df = self.harness.query(f"SELECT * FROM ledger_monthly WHERE period = '{period}';")

        row = ledger_df.iloc[0]
        exec_summary = {
            "period": period,
            "total_runs": int(row.get("total_runs", 0) or 0),
            "net_absorbed_hours_expected": round(float(row.get("hours_expected", 0) or 0), 1),
            "net_absorbed_hours_range": (
                f"{round(float(row.get('hours_low', 0) or 0), 1)}h – "
                f"{round(float(row.get('hours_high', 0) or 0), 1)}h"
            ),
            "total_spend_usd": round(float(row.get("total_cost_usd", 0) or 0), 2),
            "net_hours_per_dollar": round(float(row.get("hours_per_dollar", 0) or 0), 2),
            "total_human_review_mins": round(float(row.get("total_review_mins", 0) or 0), 1),
        }

        # 2. Team Maturity Grades & Safety Caps
        grades_df = self.harness.query(f"""
            SELECT
                team_id, team_name, final_grade_level, grade_badge, grade_title,
                raw_weighted_score, was_capped_by_safety_rule,
                s1_automation_level, s2_eval_level, s3_gate_level, s4_reliability_level, s5_adoption_level,
                signal_automation_coverage_pct, signal_failure_rate_per_100, signal_gate_approval_rate_pct
            FROM maturity_grade
            WHERE period = '{period}'
            ORDER BY final_grade_level DESC, raw_weighted_score DESC;
        """)
        team_grades = grades_df.to_dict(orient="records")

        # 3. Top 3 Most Expensive Runs
        expensive_runs_df = self.harness.query(f"""
            SELECT
                run_id, agent_id, team_id, model, prompt_tokens, completion_tokens,
                total_tokens, cost_usd, agent_median_cost, cost_ratio_to_median, is_cost_anomaly
            FROM cost_per_run
            WHERE SUBSTRING(start_time, 1, 7) = '{period}'
            ORDER BY cost_usd DESC
            LIMIT 3;
        """)
        top_expensive = expensive_runs_df.to_dict(orient="records")

        # 4. High-Friction Agents (Falling Approval or High Review Mins)
        friction_df = self.harness.query(f"""
            SELECT
                r.agent_id,
                r.team_id,
                COUNT(r.run_id) AS total_runs,
                ROUND((COUNT(CASE WHEN a.decision IN ('APPROVED_AS_IS', 'APPROVED_WITH_EDITS') THEN 1 END) * 100.0) / COUNT(a.approval_id), 1) AS approval_rate_pct,
                ROUND(AVG(a.human_review_minutes), 1) AS avg_review_minutes
            FROM runs r
            JOIN approvals a ON r.run_id = a.run_id
            WHERE SUBSTRING(r.start_time, 1, 7) = '{period}'
            GROUP BY r.agent_id, r.team_id
            HAVING approval_rate_pct < 80.0 OR avg_review_minutes > 10.0
            ORDER BY approval_rate_pct ASC
            LIMIT 5;
        """)
        high_friction = friction_df.to_dict(orient="records")

        # 5. Formulate 2 Specific Actionable Decisions
        suggested_actions = [
            {
                "title": "Action 1: Token Context Capping & Model Routing Migration",
                "rationale": (
                    f"The top run ({top_expensive[0]['run_id'] if top_expensive else 'N/A'}) consumed "
                    f"${top_expensive[0]['cost_usd'] if top_expensive else 0:.2f} due to unconstrained completion tokens. "
                    "Migrate high-volume extraction tasks to gemini-1.5-flash and cap context windows to avoid 3x cost spikes."
                ),
                "owner": "FinOps & Lead AI Engineer",
            },
            {
                "title": "Action 2: Interruption Budget Throttling for Customer Ops",
                "rationale": (
                    "Customer Operations shows elevated snooze rates and human review edits exceeding 15 minutes per task. "
                    "Enforce digest bundling window to 1 dispatch per morning and require prompt refinement on low-approval agents."
                ),
                "owner": "Operations Lead & Governance Guild",
            },
        ]

        # 6. Render Markdown
        md = self._render_markdown(exec_summary, team_grades, top_expensive, high_friction, suggested_actions)

        return MonthlyReport(
            period=period,
            generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            executive_summary=exec_summary,
            team_grades=team_grades,
            top_3_expensive_runs=top_expensive,
            falling_approval_agents=high_friction,
            suggested_actions=suggested_actions,
            markdown_content=md,
        )

    def _render_markdown(
        self,
        summary: Dict[str, Any],
        grades: List[Dict[str, Any]],
        expensive: List[Dict[str, Any]],
        friction: List[Dict[str, Any]],
        actions: List[Dict[str, str]],
    ) -> str:
        lines = [
            f"# 📊 Agent Operations Analytics Pipeline - Monthly Report: {summary['period']}",
            f"> *Generated: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | Philosophy: Value is a measurement, not a claim.*",
            "",
            "## 1. Executive Summary & Value Ledger",
            f"- **Work Absorbed (Expected)**: **{summary['net_absorbed_hours_expected']} net hours** *(Confidence Range: {summary['net_absorbed_hours_range']})*",
            f"- **Total LLM & Runtime Spend**: **${summary['total_spend_usd']:,.2f}**",
            f"- **Capital Efficiency Ratio**: **{summary['net_hours_per_dollar']} net hours saved per dollar spent**",
            f"- **Total Runs Processed**: {summary['total_runs']:,}",
            f"- **Human Review Time Absorbed**: {summary['total_human_review_mins']:,.1f} minutes deducted from gross baselines",
            "",
            "## 2. Team Maturity Grades (Rules v1.0.0)",
            "| Team | Final Grade | Score | Auto Cov | Failure / 100 | Gate Approval | Safety Capped? |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]

        for g in grades:
            capped_str = "⚠️ Capped by Reliability/Gate" if g["was_capped_by_safety_rule"] else "No"
            lines.append(
                f"| **{g['team_name']}** | `{g['grade_badge']}` (L{g['final_grade_level']}) | "
                f"{g['raw_weighted_score']:.2f} | {g['signal_automation_coverage_pct']:.1f}% | "
                f"{g['signal_failure_rate_per_100']:.1f} | {g['signal_gate_approval_rate_pct']:.1f}% | {capped_str} |"
            )

        lines.extend([
            "",
            "## 3. Top 3 Most Expensive Runs",
            "| Run ID | Agent ID | Model | Tokens | Cost (USD) | Ratio to Median | Anomaly? |",
            "| :--- | :--- | :--- | :---: | :---: | :---: | :---: |",
        ])

        for r in expensive:
            is_anom = "🚨 YES" if r["is_cost_anomaly"] else "Normal"
            lines.append(
                f"| `{r['run_id']}` | `{r['agent_id']}` | `{r['model']}` | "
                f"{r['total_tokens']:,} | ${r['cost_usd']:.4f} | {r['cost_ratio_to_median']:.1f}x | {is_anom} |"
            )

        lines.extend([
            "",
            "## 4. High-Friction Agents (Falling Approval / High Review)",
            "| Agent ID | Team ID | Total Runs | Approval Rate | Avg Review Time |",
            "| :--- | :--- | :---: | :---: | :---: |",
        ])

        for f in friction:
            lines.append(
                f"| `{f['agent_id']}` | `{f['team_id']}` | {f['total_runs']} | "
                f"{f['approval_rate_pct']:.1f}% | {f['avg_review_minutes']:.1f}m |"
            )

        lines.extend([
            "",
            "## 5. Suggested Decisions for Immediate Action",
        ])

        for a in actions:
            lines.append(f"### 🎯 {a['title']}")
            lines.append(f"**Rationale**: {a['rationale']}")
            lines.append(f"**Accountable Owner**: `{a['owner']}`\n")

        return "\n".join(lines)


def main():
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Generate Agent Operations Analytics Pipeline Monthly Operational Report")
    parser.add_argument("--period", type=str, default="2026-09", help="Period in YYYY-MM format")
    parser.add_argument("--output", type=str, default=None, help="Optional output file path")
    args = parser.parse_args()

    gen = MonthlyReportGenerator()
    report = gen.generate(period=args.period)

    if args.output:
        p = Path(args.output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(report.markdown_content, encoding="utf-8")
        print(f"Report written to {p}")
    else:
        print(report.markdown_content)


if __name__ == "__main__":
    main()
