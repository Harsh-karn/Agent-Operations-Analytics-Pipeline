# Team Maturity Grading Rubric (Rules Version: v1.0.0)

> **Core Philosophy**: *"Maturity is an empirical state, not an executive proclamation. Every grade is computed strictly from verified production telemetry, and every grade comes with the SQL query that produced it."*

---

## 🏛 The 5 Core Telemetry Signals

Every team operating autonomous agents or AI-assisted pipelines is evaluated across 5 core signals extracted from production warehouse tables:

1. **Automation Coverage ($S_1$)**: Share of the team's registered recurring business workflows executing automatically.
2. **Evaluation Coverage ($S_2$)**: Share of active agents governed by passing automated evaluation suites ($\ge 85\%$ benchmark score).
3. **Gate Health ($S_3$)**: Human review approval rate and reasonable approval turnaround times (no rubber-stamping, no abandoned gates).
4. **Reliability ($S_4$)**: Normalized incident and execution failure rate per 100 runs.
5. **Adoption & Contact Hygiene ($S_5$)**: Active team members utilizing agent deliverables weekly, balanced against snooze/opt-out rates.

---

## 📏 Signal Level Thresholds (1 to 5)

| Level | Maturity Tier | $S_1$: Automation Coverage | $S_2$: Eval Coverage | $S_3$: Gate Approval Rate | $S_4$: Failures / 100 Runs | $S_5$: Weekly Adoption |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **5** | **Autonomous Pioneer** | $\ge 80\%$ | $\ge 90\%$ | $\ge 92\%$ & $< 60\text{m}$ | $\le 1.0$ | $\ge 75\%$ & snooze $< 10\%$ |
| **4** | **Systematic Operator** | $\ge 60\%$ | $\ge 75\%$ | $\ge 85\%$ & $< 120\text{m}$ | $\le 3.0$ | $\ge 55\%$ & snooze $< 20\%$ |
| **3** | **Emerging Production** | $\ge 40\%$ | $\ge 50\%$ | $\ge 75\%$ & $< 360\text{m}$ | $\le 6.0$ | $\ge 35\%$ & snooze $< 30\%$ |
| **2** | **Experimental Pilot** | $\ge 20\%$ | $\ge 25\%$ | $\ge 60\%$ | $\le 12.0$ | $\ge 15\%$ & snooze $< 40\%$ |
| **1** | **Ad-hoc / Uncontrolled** | $< 20\%$ | $< 25\%$ | $< 60\%$ | $> 12.0$ | $< 15\%$ or snooze $\ge 40\%$ |

---

## ⚙️ Aggregation & Grading Rules Engine

### 1. Base Weighted Score
The preliminary base score is computed using a balanced operational weighting:
$$\text{Base Score} = (0.25 \times S_1) + (0.20 \times S_2) + (0.20 \times S_3) + (0.20 \times S_4) + (0.15 \times S_5)$$

### 2. The "Weakest-Link" Governance Cap Rule
A team cannot claim high operational maturity if their agents are hazardous or breaking production. Therefore:
* **Critical Signals**: Reliability ($S_4$) and Gate Health ($S_3$) are designated **Critical Safety Signals**.
* **Cap Logic**:
  $$\text{Final Grade Level} = \min\left(\operatorname{round}(\text{Base Score}), \text{Level}(S_4) + 1, \text{Level}(S_3) + 1\right)$$
* *Example*: If a team has Level 5 Automation and Level 5 Adoption, but their Reliability is Level 1 (frequent incidents and rollbacks), their maximum possible grade is capped at **Level 2** (`Level 1 + 1`).

---

## 📋 Canonical Grade Labels

| Grade Level | Display Title | Operational Implication |
| :---: | :--- | :--- |
| **Level 5** | **Gold (Autonomous Pioneer)** | Fully defensible, low intervention overhead, exemplary reliability, high human leverage. Eligible for zero-gate autonomous dispatch. |
| **Level 4** | **Silver (Systematic Operator)** | Robust evaluation and consistent human gates. Standard enterprise production readiness. |
| **Level 3** | **Bronze (Emerging Production)** | Proven value absorption with moderate manual supervision required. Active remediation backlog. |
| **Level 2** | **Amber (Experimental Pilot)** | Substantial human intervention and review edits required. Pings restricted to limited pilot recipients. |
| **Level 1** | **Red (Ad-hoc / High Friction)** | Unreliable or intrusive. Interruption budget strictly capped; requires architecture review before new agent onboarding. |

---

## ⚖️ Dispute Resolution Protocol

1. **Zero-Opinion Adjudication**: When a team lead disputes a grade (e.g. arguing *"We deserve Silver, not Bronze"*), leadership does not hold subjective debates.
2. **Deterministic SQL Disclosure**: The platform exposes `GET /grades/{team}/{period}/query`, returning the exact warehouse SQL text and referenced tables.
3. **Evidence-Based Rerun**:
   * If the team claims a workflow was omitted, they submit the missing workflow ID.
   * If the registry was out of date, the team submits a pull request updating `warehouse.raw.workflows`.
   * Upon merging, the pipeline reruns the identical SQL logic. If the data validates the claim, the grade automatically updates.
