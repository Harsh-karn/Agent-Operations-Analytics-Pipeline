"""
Tests for Monthly Report Generator.
Verifies that executive numbers, grade movements, expensive runs, and decisions
are properly populated without nulls or formatting breakages.
"""

from tally.reports.monthly import MonthlyReportGenerator


def test_monthly_report_generation():
    gen = MonthlyReportGenerator()
    report = gen.generate(period="2026-09")

    assert report is not None
    assert report.period == "2026-09"
    assert "total_runs" in report.executive_summary
    assert report.executive_summary["total_runs"] > 0
    assert report.executive_summary["net_absorbed_hours_expected"] > 0
    assert report.executive_summary["total_spend_usd"] > 0

    # Team grades
    assert len(report.team_grades) == 5
    for g in report.team_grades:
        assert g["final_grade_level"] in range(1, 6)

    # Top 3 runs
    assert len(report.top_3_expensive_runs) <= 3
    if report.top_3_expensive_runs:
        assert report.top_3_expensive_runs[0]["cost_usd"] >= 0.0

    # Suggested actions
    assert len(report.suggested_actions) == 2
    for a in report.suggested_actions:
        assert "title" in a
        assert "rationale" in a
        assert "owner" in a

    # Markdown content
    assert "# 📊 Agent Operations Analytics Pipeline" in report.markdown_content
    assert "## 1. Executive Summary & Value Ledger" in report.markdown_content
    assert "## 5. Suggested Decisions for Immediate Action" in report.markdown_content
