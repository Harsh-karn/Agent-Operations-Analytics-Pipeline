# Tally: Agent Operations Analytics Pipeline

> *"The value of the system is a measurement, not a claim, and every grade comes with the SQL that produced it."*

Tally is an enterprise-grade measurement and contact layer for autonomous agents and generative AI workflows. It serves two critical operational responsibilities:

1. **Intelligent Contact Layer**: Governs system-to-human communications with hard, transactionally enforced interruption budgets per person, quiet hours, message bundling into digestible dispatches, and a strict value-first composer ("no ask without a payload").
2. **Measurement & Value Ledger**: Provides an audited ledger of human work absorbed by agents (with documented empirical baselines and confidence intervals), granular token-level cost attribution per run, and defensible team maturity grades computed from warehouse data where any grade can be contested through a show-the-query dispute endpoint.

---

## 🏛 Architecture Overview

```text
 Synthetic run logs (or BigQuery agent runtime events)
                    │
                    ▼
   BigQuery Raw Warehouse: runs, events, approvals, feedback, contacts, workflows
                    │
        SQL Views (versioned, tested, auditable)
        ┌───────────┴─────────────┬──────────────────┐
        ▼                         ▼                  ▼
   ledger_monthly           cost_per_run       team_signals (5 signals)
   (net min, ranges)        (token costs,      (automation, evals, gate,
                             anomaly flags)     reliability, adoption)
        │                         │                  │
        └────────────┬────────────┴──────────────────┘
                     ▼
             maturity_grade (rules v1)  ───►  GET /grades/{team}/{period}/query
                     │                        (100% reproducible SQL disclosure)
                     ▼
         Streamlit Dashboard + Monthly Executive Decision Report
```

### Operational Contact Path (Transactional State)
```text
Candidate Message ──► Bundler (dedupe, cull expired)
                  ──► Budget Check (atomic transaction: try_spend)
                  ──► Composer (value-first payload validation, max 1 ask)
                  ──► Dispatch (Slack / Email) ──► contact_log
```

---

## 🚀 Key Capabilities & Design Guarantees

| Area | Feature | Guarantee |
| :--- | :--- | :--- |
| **Contact Engine** | Hard Interruption Budget | Code-enforced transactional atomicity (`try_spend`). Zero sends over budget even under concurrent burst conditions. |
| **Contact Engine** | Digest Bundling & Value First | Pending pings merged into one scheduled digest. Every message requires tangible work (summary, artifact, draft) before asking for human intervention. |
| **Value Ledger** | Net Absorbed Minutes | Baseline task minutes minus human review/edit time. Range outputs: Low, Expected, High confidence intervals. |
| **Cost Attribution** | Model & Run Observability | Exact token cost attribution grouped by agent, model, and team. Automated anomaly detection for runs exceeding 3x median cost. |
| **Maturity Grading** | 5 Signals & Weakest-Link Cap | Defensible levels (1–5) based on Automation Coverage, Eval Coverage, Gate Health, Reliability, and Adoption. |
| **Auditability** | Show-The-Query Endpoint | `GET /grades/{team}/{period}/query` returns the exact immutable SQL query string and rule version to audit and reproduce the grade. |

---

## 📂 Project Structure

```text
├── .github/workflows/          # Continuous integration and SQL test pipeline
├── data/                       # High-fidelity synthetic data generator (Faker)
├── dashboards/                 # Streamlit operational & executive analytics app
├── docs/                       # Metric definitions, grading rules v1, and ADRs
│   ├── adr/                    # Architecture Decision Records
│   ├── grading-rules-v1.md     # Team maturity grading rubric & thresholds
│   └── metrics-definitions.md  # Official platform metric catalog
├── infra/                      # Terraform modules for BigQuery, Cloud Run, Scheduler
├── src/tally/                  # Core Python engine
│   ├── contact/                # Budget, Bundler, Composer, and Channels
│   ├── reports/                # Monthly executive report generator
│   ├── api.py                  # FastAPI service for contact & dispute disclosure
│   └── grading.py              # Grade execution and query reproduction engine
├── warehouse/                  # Analytical warehouse layer
│   ├── raw/                    # DDL schemas (partitioned & clustered)
│   ├── views/                  # BigQuery analytical views & rules
│   └── tests/                  # Warehouse assertions (nulls, ranges, sanity)
└── tests/                      # Concurrency, unit, and integration tests
```

---

## 🛠 Local Setup & Quickstart

### Prerequisites
- Python 3.11+
- Git

### Installation
```bash
git clone https://github.com/Harsh-karn/Agent-Operations-Analytics-Pipeline.git
cd Agent-Operations-Analytics-Pipeline
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -e ".[dev,gcp]"
```

### Running the Test Suite
```bash
pytest -v
```

---

## 📄 License
Licensed under Apache 2.0.
