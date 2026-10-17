"""
CLI Interface for Agent Operations Analytics Pipeline.
Provides command-line management for:
- Nightly team maturity grading batch
- Monthly executive decision report generation
- Interruption budget inspection
- Cost anomaly analysis
"""

from __future__ import annotations

import datetime
from pathlib import Path
import sys
from typing import Optional
import typer

from tally.grading import GradeService
from tally.reports.monthly import MonthlyReportGenerator
from tally.contact.budget import ContactBudgetManager

app = typer.Typer(
    name="agent-ops",
    help="Agent Operations Analytics Pipeline CLI: Measurements, budgets, and defensible grading.",
    add_completion=False,
)


@app.command("nightly-grade")
def nightly_grade(
    period: Optional[str] = typer.Option(None, "--period", "-p", help="Reporting period (YYYY-MM). Defaults to current."),
):
    """Executes nightly maturity grading audit and refreshes warehouse metrics."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    service = GradeService()
    now_period = period or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
    typer.echo(f"--- Executing Nightly Grading Batch (Period: {now_period}) ---")

    teams_df = service.harness.query("SELECT DISTINCT team_id FROM teams ORDER BY team_id;")
    graded_count = 0
    for _, row in teams_df.iterrows():
        t_id = row["team_id"]
        report = service.get_team_grade(t_id, now_period)
        if report:
            typer.echo(f"  Team: {report.team_name:<25} | Grade: {report.grade_badge:<6} (Level {report.final_grade_level}) | Score: {report.raw_weighted_score}")
            graded_count += 1

    typer.echo(f"--- Nightly grading batch completed. Successfully scored {graded_count} teams. ---")


@app.command("monthly-report")
def monthly_report(
    period: str = typer.Option("2026-09", "--period", "-p", help="Reporting period in YYYY-MM format"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Optional output path for markdown report"),
):
    """Generates the executive decision and operational return report."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    gen = MonthlyReportGenerator()
    rep = gen.generate(period=period)
    typer.echo(f"--- Generated Monthly Report for {period} ---")
    typer.echo(f"Expected Net Hours Saved: {rep.executive_summary['net_absorbed_hours_expected']} hrs (Range: {rep.executive_summary['net_absorbed_hours_range']})")
    typer.echo(f"Total LLM Spend: ${rep.executive_summary['total_spend_usd']:,.2f}")
    typer.echo(f"Capital Efficiency: {rep.executive_summary['net_hours_per_dollar']} hrs/$")

    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rep.markdown_content, encoding="utf-8")
        typer.echo(f"Report saved to: {out_path.resolve()}")


@app.command("budget-status")
def budget_status(
    person_id: str = typer.Argument(..., help="Person identifier (e.g. usr-payments-01)"),
    db_path: str = typer.Option("data/contact_budget.db", "--db", help="Path to contact SQLite database"),
):
    """Inspects a recipient's remaining interruption budget and quiet hours."""
    mgr = ContactBudgetManager(db_path=db_path)
    status = mgr.get_budget(person_id)
    if not status:
        typer.echo(f"Error: No budget record found for person '{person_id}' in {db_path}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Interruption Budget for {person_id}:")
    typer.echo(f"  Limit:      {status['budget_limit']} units/week")
    typer.echo(f"  Used:       {status['budget_used']} units")
    typer.echo(f"  Remaining:  {status['remaining']} units")
    typer.echo(f"  Timezone:   {status['timezone']}")
    typer.echo(f"  Quiet Window: {status['quiet_hours_start']:02d}:00 to {status['quiet_hours_end']:02d}:00")


@app.command("inspect-anomalies")
def inspect_anomalies(
    limit: int = typer.Option(5, "--limit", "-n", help="Number of anomalies to display"),
):
    """Displays top token cost anomalies (>3x agent median)."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    service = GradeService()
    df = service.harness.query(f"""
        SELECT run_id, agent_id, team_id, model, cost_usd, agent_median_cost, cost_ratio_to_median
        FROM cost_per_run
        WHERE is_cost_anomaly = TRUE
        ORDER BY cost_ratio_to_median DESC
        LIMIT {limit};
    """)
    if df.empty:
        typer.echo("Zero cost anomalies detected.")
        return

    typer.echo(f"Top {len(df)} Cost Anomalies (>3x Median):")
    for _, row in df.iterrows():
        typer.echo(
            f"  Run: {row['run_id']} | Agent: {row['agent_id']} | Model: {row['model']} | "
            f"Cost: ${row['cost_usd']:.4f} (Median: ${row['agent_median_cost']:.4f}, Ratio: {row['cost_ratio_to_median']}x)"
        )


if __name__ == "__main__":
    app()
