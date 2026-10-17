"""
Synthetic Data Generator for Agent Operations Analytics Pipeline

Generates 3 to 6 months of realistic, production-like agent telemetry for 5 distinct teams:
1. payments-core: Mature, high automation (85%+), passing evals, high approval, low incidents (Target Grade: Level 5 / Level 4)
2. data-platform: Growing, moderate automation (~40%), expanding test coverage (Target Grade: Level 3)
3. customer-ops: Noisy, high contact load, falling approval rates, snooze spikes (Target Grade: Level 2)
4. compliance-risk: Disputing team, strict governance, seeded known fact: EXACTLY 12 automated workflows (Target Grade: Level 4)
5. growth-marketing: Ad-hoc experimental pilot, low eval coverage, elevated failure rate (Target Grade: Level 1)
"""

from __future__ import annotations

import argparse
import datetime
import json
import random
from pathlib import Path
from typing import Any, Dict, List

# Seeded known constants
SEED_COMPLIANCE_AUTOMATED_WORKFLOWS = 12
MODEL_PRICING = {
    "gemini-1.5-pro": {"input_per_million": 3.50, "output_per_million": 10.50},
    "gemini-1.5-flash": {"input_per_million": 0.35, "output_per_million": 1.05},
    "gpt-4o": {"input_per_million": 5.00, "output_per_million": 15.00},
    "claude-3-5-sonnet": {"input_per_million": 3.00, "output_per_million": 15.00},
}


class SyntheticDataGenerator:
    def __init__(self, seed: int = 42, months: int = 4):
        self.seed = seed
        self.months = months
        random.seed(seed)

        # Calculate time horizon
        self.end_date = datetime.datetime(2026, 10, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
        self.start_date = self.end_date - datetime.timedelta(days=months * 30)

        # Team definitions with behavior archetypes
        self.team_specs = [
            {
                "id": "team-payments-core",
                "name": "Payments Core",
                "domain": "FinTech Core Banking",
                "automation_target": 0.88,
                "eval_pass_rate": 0.95,
                "approval_rate": 0.96,
                "incident_rate_per_100": 0.8,
                "avg_review_mins": 3.5,
                "weekly_runs": 85,
                "total_workflows": 16,
                "automated_workflows": 14,
            },
            {
                "id": "team-data-platform",
                "name": "Data Platform",
                "domain": "Warehouse & Data Engineering",
                "automation_target": 0.45,
                "eval_pass_rate": 0.65,
                "approval_rate": 0.82,
                "incident_rate_per_100": 4.5,
                "avg_review_mins": 12.0,
                "weekly_runs": 45,
                "total_workflows": 20,
                "automated_workflows": 9,
            },
            {
                "id": "team-customer-ops",
                "name": "Customer Operations",
                "domain": "Support & Escalations",
                "automation_target": 0.60,
                "eval_pass_rate": 0.50,
                "approval_rate": 0.70,
                "incident_rate_per_100": 9.5,
                "avg_review_mins": 18.0,
                "weekly_runs": 120,
                "total_workflows": 15,
                "automated_workflows": 9,
            },
            {
                "id": "team-compliance-risk",
                "name": "Compliance & Risk",
                "domain": "Regulatory & AML",
                "automation_target": 0.80,
                "eval_pass_rate": 0.88,
                "approval_rate": 0.89,
                "incident_rate_per_100": 1.5,
                "avg_review_mins": 8.0,
                "weekly_runs": 60,
                "total_workflows": 15,
                "automated_workflows": SEED_COMPLIANCE_AUTOMATED_WORKFLOWS,  # Seeded known fact: exactly 12
            },
            {
                "id": "team-growth-marketing",
                "name": "Growth & Marketing",
                "domain": "Acquisition & Lifecycle",
                "automation_target": 0.18,
                "eval_pass_rate": 0.20,
                "approval_rate": 0.55,
                "incident_rate_per_100": 14.0,
                "avg_review_mins": 25.0,
                "weekly_runs": 30,
                "total_workflows": 12,
                "automated_workflows": 2,
            },
        ]

    def _random_timestamp(self, start: datetime.datetime, end: datetime.datetime) -> datetime.datetime:
        delta = end - start
        random_seconds = random.randint(0, int(delta.total_seconds()))
        return start + datetime.timedelta(seconds=random_seconds)

    def generate_all(self) -> Dict[str, List[Dict[str, Any]]]:
        teams: List[Dict[str, Any]] = []
        people: List[Dict[str, Any]] = []
        agents: List[Dict[str, Any]] = []
        workflows: List[Dict[str, Any]] = []
        baselines: List[Dict[str, Any]] = []
        eval_results: List[Dict[str, Any]] = []
        runs: List[Dict[str, Any]] = []
        events: List[Dict[str, Any]] = []
        approvals: List[Dict[str, Any]] = []
        feedback: List[Dict[str, Any]] = []
        incidents: List[Dict[str, Any]] = []
        contact_attempts: List[Dict[str, Any]] = []

        # 1. Generate Teams & Workflows
        for spec in self.team_specs:
            team_id = spec["id"]
            created_at = (self.start_date - datetime.timedelta(days=180)).isoformat()
            teams.append({
                "team_id": team_id,
                "name": spec["name"],
                "domain": spec["domain"],
                "created_at": created_at,
            })

            # Workflows
            tot = spec["total_workflows"]
            auto_count = spec["automated_workflows"]
            for w_idx in range(1, tot + 1):
                is_auto = w_idx <= auto_count
                w_id = f"wf-{team_id}-{w_idx:02d}"
                workflows.append({
                    "workflow_id": w_id,
                    "team_id": team_id,
                    "name": f"{spec['name']} Workflow {w_idx}",
                    "is_automated": is_auto,
                    "cadence": random.choice(["HOURLY", "DAILY", "WEEKLY", "EVENT_DRIVEN"]),
                    "description": f"Operational process {w_idx} for {spec['name']}",
                })

            # People (4 per team)
            team_slug = team_id.replace("team-", "")
            for p_idx in range(1, 5):
                p_id = f"usr-{team_slug}-{p_idx:02d}"
                people.append({
                    "person_id": p_id,
                    "team_id": team_id,
                    "name": f"Operator {p_idx} ({spec['name']})",
                    "email": f"operator.{p_idx}.{team_slug}@enterprise.internal",
                    "timezone": random.choice(["America/New_York", "America/Los_Angeles", "Europe/London"]),
                    "quiet_hours_start": 19,
                    "quiet_hours_end": 8,
                    "weekly_interruption_budget": random.choice([5, 8, 10, 12]),
                })

            # Agents (3 per team)
            for a_idx in range(1, 4):
                a_id = f"agent-{team_slug}-{a_idx:02d}"
                agents.append({
                    "agent_id": a_id,
                    "team_id": team_id,
                    "name": f"{spec['name']} Agent {a_idx}",
                    "version": f"1.{a_idx}.0",
                    "status": "ACTIVE",
                    "created_at": created_at,
                })

                # Agent Baselines
                base_mins = random.choice([20.0, 35.0, 50.0, 75.0, 90.0])
                baselines.append({
                    "agent_id": a_id,
                    "task_description": f"Manual human equivalence benchmark for {spec['name']} Agent {a_idx}",
                    "baseline_minutes": base_mins,
                    "method": random.choice(["TIMED_MANUAL_BENCHMARK", "HISTORICAL_TIMESHEET_AUDIT", "CONTROL_EXPERIMENT"]),
                    "measured_on": "2026-05-01",
                    "confidence": "HIGH" if spec["eval_pass_rate"] > 0.8 else ("MEDIUM" if spec["eval_pass_rate"] > 0.4 else "LOW"),
                })

                # Eval Results (Evaluation Coverage)
                for eval_run in range(1, 3):
                    e_id = f"eval-{a_id}-{eval_run}"
                    passed = random.random() < spec["eval_pass_rate"]
                    score = round(random.uniform(85.0, 99.0) if passed else random.uniform(40.0, 84.0), 1)
                    eval_results.append({
                        "eval_id": e_id,
                        "agent_id": a_id,
                        "test_suite_name": f"Standard Regression Suite v{eval_run}",
                        "score": score,
                        "passed": passed,
                        "evaluated_at": self._random_timestamp(self.start_date, self.end_date).isoformat(),
                    })

        # Pre-index objects for run synthesis
        team_agents = {spec["id"]: [a for a in agents if a["team_id"] == spec["id"]] for spec in self.team_specs}
        team_workflows = {spec["id"]: [w for w in workflows if w["team_id"] == spec["id"]] for spec in self.team_specs}
        team_people = {spec["id"]: [p for p in people if p["team_id"] == spec["id"]] for spec in self.team_specs}

        # 2. Synthesize Runs, Events, Approvals, Incidents, and Contact Attempts
        num_weeks = int((self.end_date - self.start_date).days / 7)
        run_seq = 1
        event_seq = 1
        incident_seq = 1
        contact_seq = 1

        for spec in self.team_specs:
            t_id = spec["id"]
            t_ag = team_agents[t_id]
            t_wf = team_workflows[t_id]
            t_ppl = team_people[t_id]

            for week in range(num_weeks):
                w_start = self.start_date + datetime.timedelta(days=week * 7)
                w_end = w_start + datetime.timedelta(days=7)
                runs_in_week = max(5, int(random.gauss(spec["weekly_runs"], spec["weekly_runs"] * 0.15)))

                for _ in range(runs_in_week):
                    run_id = f"run-{run_seq:06d}"
                    run_seq += 1

                    agent = random.choice(t_ag)
                    wf = random.choice(t_wf)
                    reviewer = random.choice(t_ppl)

                    run_start = self._random_timestamp(w_start, w_end)
                    duration_secs = random.randint(15, 180)
                    run_end = run_start + datetime.timedelta(seconds=duration_secs)

                    # Determine Run Outcome
                    is_incident = random.random() < (spec["incident_rate_per_100"] / 100.0)
                    is_failure = (not is_incident) and (random.random() < 0.04)

                    if is_incident:
                        status = "ROLLED_BACK" if random.random() < 0.5 else "FAILED"
                    elif is_failure:
                        status = "FAILED"
                    else:
                        status = "COMPLETED"

                    # Token telemetry and Model choice
                    model = random.choice(list(MODEL_PRICING.keys()))
                    pricing = MODEL_PRICING[model]
                    prompt_tokens = random.randint(800, 4500)
                    completion_tokens = random.randint(200, 2500)

                    # Intentional anomaly injection (e.g. 1 in 150 runs has huge tokens)
                    if random.random() < 0.007:
                        prompt_tokens *= 10
                        completion_tokens *= 8

                    cost_usd = round(
                        (prompt_tokens / 1_000_000.0 * pricing["input_per_million"]) +
                        (completion_tokens / 1_000_000.0 * pricing["output_per_million"]),
                        6
                    )

                    runs.append({
                        "run_id": run_id,
                        "agent_id": agent["agent_id"],
                        "team_id": t_id,
                        "workflow_id": wf["workflow_id"],
                        "start_time": run_start.isoformat(),
                        "end_time": run_end.isoformat(),
                        "status": status,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "model": model,
                        "cost_usd": cost_usd,
                    })

                    # Events for Run
                    events.append({
                        "event_id": f"evt-{event_seq:07d}",
                        "run_id": run_id,
                        "event_type": "RUN_STARTED",
                        "timestamp": run_start.isoformat(),
                        "payload_json": json.dumps({"workflow_id": wf["workflow_id"]}),
                    })
                    event_seq += 1

                    events.append({
                        "event_id": f"evt-{event_seq:07d}",
                        "run_id": run_id,
                        "event_type": "LLM_CALL",
                        "timestamp": (run_start + datetime.timedelta(seconds=duration_secs // 2)).isoformat(),
                        "payload_json": json.dumps({
                            "model": model,
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "cost_usd": cost_usd,
                        }),
                    })
                    event_seq += 1

                    # Approvals & Gate Health
                    if status in ("COMPLETED", "ROLLED_BACK"):
                        approval_id = f"app-{run_id}"
                        decision_rand = random.random()
                        if status == "ROLLED_BACK":
                            decision = "REJECTED"
                        elif decision_rand < spec["approval_rate"]:
                            decision = "APPROVED_AS_IS" if random.random() < 0.75 else "APPROVED_WITH_EDITS"
                        else:
                            decision = "REJECTED"

                        req_time = run_end
                        review_mins = max(1.0, random.gauss(spec["avg_review_mins"], spec["avg_review_mins"] * 0.3))
                        dec_time = req_time + datetime.timedelta(minutes=review_mins)

                        approvals.append({
                            "approval_id": approval_id,
                            "run_id": run_id,
                            "person_id": reviewer["person_id"],
                            "decision": decision,
                            "requested_at": req_time.isoformat(),
                            "decided_at": dec_time.isoformat(),
                            "human_review_minutes": round(review_mins, 2),
                            "edit_summary": "Minor adjustments to agent response" if decision == "APPROVED_WITH_EDITS" else None,
                        })

                        # Reviewer Feedback (for adoption)
                        if random.random() < 0.4:
                            rating = 5 if decision == "APPROVED_AS_IS" else (3 if decision == "APPROVED_WITH_EDITS" else 1)
                            feedback.append({
                                "feedback_id": f"fb-{run_id}",
                                "run_id": run_id,
                                "person_id": reviewer["person_id"],
                                "rating": rating,
                                "comments": "Agent output was accurate and ready." if rating >= 4 else "Needed correction.",
                                "created_at": dec_time.isoformat(),
                            })

                    # Incidents
                    if is_incident:
                        inc_id = f"inc-{incident_seq:04d}"
                        incident_seq += 1
                        incidents.append({
                            "incident_id": inc_id,
                            "run_id": run_id,
                            "team_id": t_id,
                            "severity": random.choice(["SEV2", "SEV3"]),
                            "description": f"Output validation failure in run {run_id}",
                            "root_cause": "Edge case payload unhandled by model prompt schema",
                            "occurred_at": run_end.isoformat(),
                            "resolved_at": (run_end + datetime.timedelta(hours=random.randint(1, 12))).isoformat(),
                        })

                # Contact Attempts for each person in week (testing budget, quiet hours, bundling)
                for person in t_ppl:
                    attempts_count = random.randint(2, 7)
                    for _ in range(attempts_count):
                        contact_time = self._random_timestamp(w_start, w_end)
                        c_id = f"cnt-{contact_seq:06d}"
                        contact_seq += 1

                        kind = random.choice(["FYI_DIGEST", "GATE_APPROVAL_ASK", "ACTION_REQUEST"])
                        has_payload = random.random() > 0.05  # 95% adhere to value first
                        has_ask = kind in ("GATE_APPROVAL_ASK", "ACTION_REQUEST")
                        snoozed = random.random() < (0.35 if t_id == "team-customer-ops" else 0.08)

                        contact_attempts.append({
                            "attempt_id": c_id,
                            "person_id": person["person_id"],
                            "agent_id": random.choice(t_ag)["agent_id"],
                            "kind": kind,
                            "urgency": "HIGH" if kind == "GATE_APPROVAL_ASK" else "LOW",
                            "has_payload": has_payload,
                            "has_ask": has_ask,
                            "ask_count": 1 if has_ask else 0,
                            "payload_preview": "Verified digest: 4 items completed without incident" if has_payload else "",
                            "sent_at": contact_time.isoformat(),
                            "status": "ALLOWED" if has_payload else "REJECTED_COMPOSER",
                            "snoozed": snoozed,
                        })

        return {
            "teams": teams,
            "people": people,
            "agents": agents,
            "workflows": workflows,
            "agent_baselines": baselines,
            "eval_results": eval_results,
            "runs": runs,
            "events": events,
            "approvals": approvals,
            "reviewer_feedback": feedback,
            "incidents": incidents,
            "contact_attempts": contact_attempts,
        }

    def save(self, data: Dict[str, List[Dict[str, Any]]], output_dir: str, export_format: str = "jsonl") -> None:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        for table_name, rows in data.items():
            if export_format in ("jsonl", "both"):
                jsonl_file = out_path / f"{table_name}.jsonl"
                with open(jsonl_file, "w", encoding="utf-8") as f:
                    for r in rows:
                        f.write(json.dumps(r) + "\n")
                print(f"Exported {len(rows):>6} rows to {jsonl_file}")

            if export_format in ("csv", "both"):
                csv_file = out_path / f"{table_name}.csv"
                if rows:
                    import csv
                    keys = list(rows[0].keys())
                    with open(csv_file, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=keys)
                        writer.writeheader()
                        writer.writerows(rows)
                    print(f"Exported {len(rows):>6} rows to {csv_file}")

            # Try parquet if pyarrow/pandas installed
            if export_format in ("parquet", "both"):
                try:
                    import pandas as pd
                    parquet_file = out_path / f"{table_name}.parquet"
                    df = pd.DataFrame(rows)
                    df.to_parquet(parquet_file, index=False)
                    print(f"Exported {len(rows):>6} rows to {parquet_file}")
                except Exception:
                    # Non-fatal if pyarrow not yet ready
                    pass


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic telemetry for Agent Operations Analytics Pipeline")
    parser.add_argument("--months", type=int, default=4, help="Number of months of historical data (default: 4)")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed (default: 42)")
    parser.add_argument("--output-dir", type=str, default="data/synthetic", help="Output directory path")
    parser.add_argument("--format", type=str, choices=["jsonl", "csv", "parquet", "both"], default="both")
    args = parser.parse_args()

    print(f"--- Generating Synthetic Data ({args.months} months, seed={args.seed}) ---")
    gen = SyntheticDataGenerator(seed=args.seed, months=args.months)
    dataset = gen.generate_all()
    gen.save(dataset, args.output_dir, export_format=args.format)
    print("--- Synthetic generation completed successfully! ---")


if __name__ == "__main__":
    main()
