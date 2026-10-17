# Metrics Definitions: Agent Operations Analytics Pipeline Catalog

> **Core Philosophy**: *A metric without an agreed-upon definition, explicit provenance, known caveats, and an accountable owner is merely an opinion. The platform mandates strict semantic precision.*

---

## 🎯 Foundational Operational Concepts

### 1. Work Absorbed
> **One-Sentence Definition**: A unit of work absorbed is defined as a completed, approved agent run that successfully replaces a distinct, repeatable task a human operator would otherwise perform manually.

* **Eligibility Rule**: If a run fails, is rejected during human review, or is rolled back, it earns **zero** absorbed minutes. If heavily edited, its absorbed minutes are penalized proportionately.
* **Accounting Principle**: Gross task time saved is never reported in isolation; the pipeline subtracts human review and modification time to compute **Net Absorbed Minutes**.

### 2. Adoption
> **One-Sentence Definition**: Adoption is the percentage of eligible team members who actively consume, interact with, or approve agent outputs in a given weekly rolling window without persistent opt-out or snooze behavior.

### 3. Automated Workflow
> **One-Sentence Definition**: An automated workflow is a registered operational business process executed end-to-end by one or more agents on a recurring or event-driven trigger without requiring manual initiation.

### 4. Incident
> **One-Sentence Definition**: An incident is an operational failure, downstream data corruption, unhandled exception, or post-approval rollback caused by an agent run that required manual remediation.

---

## 📊 Comprehensive Metric Catalog

### Metric 1: Net Absorbed Minutes (`net_absorbed_minutes`)
* **Plain-English Definition**: The net human time saved by an agent execution, calculated by taking the empirically measured baseline duration of the task and subtracting all human review, validation, and post-generation edit duration.
* **Source Tables**: `warehouse.raw.runs`, `warehouse.raw.approvals`, `warehouse.raw.agent_baselines`.
* **Formula**:
  $$\text{Net Minutes} = \max\left(0, \text{Baseline Minutes} \times \text{Approval Factor} - \text{Review Minutes}\right)$$
  Where:
  * $\text{Approval Factor} = 1.0$ if status is `APPROVED_AS_IS`
  * $\text{Approval Factor} = 0.5$ if status is `APPROVED_WITH_EDITS`
  * $\text{Approval Factor} = 0.0$ if status is `REJECTED` or `ROLLED_BACK`
* **Known Caveats**:
  * Assumes the baseline task would have been executed by a proficient human operator.
  * Does not account for cognitive context switching before/after the review.
  * Subject to baseline uncertainty; must always be presented alongside Low, Expected, and High confidence ranges.
* **Metric Owner**: Platform Value & Operations Lead (`value-governance@platform.internal`)

---

### Metric 2: Value Delivery Range (`absorbed_hours_low`, `absorbed_hours_expected`, `absorbed_hours_high`)
* **Plain-English Definition**: The range of estimated human hours saved per month, adjusted for the empirical confidence level of each agent's baseline measurement.
* **Source Tables**: `warehouse.views.ledger_monthly`.
* **Formula**:
  $$\text{Net Hours}_{\text{expected}} = \frac{\sum \text{Net Minutes}}{60}$$
  $$\text{Net Hours}_{\text{low}} = \text{Net Hours}_{\text{expected}} \times (1 - \text{Baseline Uncertainty Factor})$$
  $$\text{Net Hours}_{\text{high}} = \text{Net Hours}_{\text{expected}} \times (1 + \text{Baseline Uncertainty Factor})$$
  *(Uncertainty factors: HIGH confidence = $\pm 10\%$, MEDIUM confidence = $\pm 25\%$, LOW confidence = $\pm 40\%$)*
* **Known Caveats**:
  * Reflects measurement uncertainty, not system instability.
* **Metric Owner**: Lead Data Scientist & Value Governance

---

### Metric 3: Cost Per Run (`cost_per_run_usd`)
* **Plain-English Definition**: The fully attributed monetary cost of a single agent execution, derived from prompt tokens, completion tokens, model catalog pricing, and external tool call overhead.
* **Source Tables**: `warehouse.raw.events`, `warehouse.raw.model_pricing`.
* **Formula**:
  $$\text{Cost} = (\text{Prompt Tokens} \times P_{\text{input}}) + (\text{Completion Tokens} \times P_{\text{output}}) + \text{Tool Execution Fees}$$
* **Known Caveats**:
  * Excludes shared hosting compute amortization (Cloud Run fixed tier) unless configured.
  * Token caches reduce cost; requires cache-hit observability.
* **Metric Owner**: FinOps & Infrastructure Lead (`finops@platform.internal`)

---

### Metric 4: Net Hours Per Dollar (`net_hours_per_dollar`)
* **Plain-English Definition**: The capital efficiency ratio measuring how many net human hours are absorbed for every dollar spent on LLM tokens and execution.
* **Source Tables**: `warehouse.views.ledger_monthly`.
* **Formula**:
  $$\text{Efficiency} = \frac{\text{Net Absorbed Hours}_{\text{expected}}}{\sum \text{Cost Per Run}_{\text{usd}}}$$
* **Known Caveats**:
  * Highly variable for experimental or exploratory agents with low initial task completions.
* **Metric Owner**: Head of Engineering & FinOps

---

### Metric 5: Automation Coverage (`automation_coverage_pct`)
* **Plain-English Definition**: The percentage of a team's cataloged recurring operational workflows that are actively executed by autonomous agents without human initiation.
* **Source Tables**: `warehouse.raw.workflows`, `warehouse.raw.runs`.
* **Formula**:
  $$\text{Automation Coverage} = \frac{\text{Count of Active Automated Workflows}}{\text{Total Cataloged Workflows in Team Registry}} \times 100$$
* **Known Caveats**:
  * Only as accurate as the team's workflow registry completeness. If a team hides workflows, coverage appears deceptively high.
* **Metric Owner**: Enterprise Architecture & Team Leads

---

### Metric 6: Evaluation Coverage (`eval_coverage_pct`)
* **Plain-English Definition**: The proportion of active production agents deployed by a team that possess an automated test & evaluation benchmark suite with a passing grade ($\ge 85\%$).
* **Source Tables**: `warehouse.raw.agents`, `warehouse.raw.eval_results`.
* **Formula**:
  $$\text{Eval Coverage} = \frac{\text{Active Agents with Passing Eval Suite}}{\text{Total Active Agents Assigned to Team}} \times 100$$
* **Known Caveats**:
  * Passing a synthetic benchmark does not guarantee absence of zero-day production edge cases.
* **Metric Owner**: AI Quality & Testing Guild

---

### Metric 7: Gate Health (`gate_approval_rate` & `median_approval_minutes`)
* **Plain-English Definition**: A two-dimensional metric tracking (1) the proportion of agent runs that humans approve, and (2) the median human turnaround time in minutes to grant approval.
* **Source Tables**: `warehouse.raw.approvals`.
* **Formula**:
  $$\text{Gate Approval Rate} = \frac{\text{Count of Approvals (with or without minor edits)}}{\text{Total Gate Decisions Requested}} \times 100$$
  $$\text{Median Approval Time} = \operatorname{Percentile}_{50}\left(\text{Decision Timestamp} - \text{Requested Timestamp}\right)$$
* **Known Caveats**:
  * High approval rate with sub-5-second turnaround times may indicate "rubber-stamping" rather than genuine human oversight.
* **Metric Owner**: Compliance & Human-in-the-Loop Governance

---

### Metric 8: Failure & Incident Rate (`failure_rate_per_100_runs`)
* **Plain-English Definition**: The normalized frequency of operational incidents, unhandled exceptions, and rollbacks occurring per 100 executed agent runs.
* **Source Tables**: `warehouse.raw.runs`, `warehouse.raw.incidents`.
* **Formula**:
  $$\text{Incident Rate} = \frac{\text{Count of Incidents} + \text{Count of Failed Runs}}{\text{Total Agent Runs}} \times 100$$
* **Known Caveats**:
  * Teams running experimental agents may register higher failure rates during incubation phases.
* **Metric Owner**: Site Reliability Engineering (SRE)

---

### Metric 9: Interruption Budget Burn Rate (`budget_burn_pct`)
* **Plain-English Definition**: The percentage of an individual human's weekly interruption budget consumed by incoming automated pings and bundled action requests.
* **Source Tables**: `operational.contact_budget`, `operational.contact_log`.
* **Formula**:
  $$\text{Burn Rate} = \frac{\text{Budget Units Used in Current Week Window}}{\text{Total Weekly Budget Limit Allowed for Person}} \times 100$$
* **Known Caveats**:
  * Urgent/critical security alerts bypass standard limits but are recorded with negative headroom.
* **Metric Owner**: Contact Engine & Employee Experience Lead

---

### Metric 10: Message Snooze & Disregard Rate (`snooze_rate_pct`)
* **Plain-English Definition**: The fraction of outgoing agent notifications of a specific kind that recipient humans actively snooze, dismiss, or ignore without action.
* **Source Tables**: `operational.contact_feedback`.
* **Formula**:
  $$\text{Snooze Rate} = \frac{\text{Count of Snooze or Opt-out Actions}}{\text{Total Delivered Dispatches of Kind } K} \times 100$$
* **Known Caveats**:
  * If snooze rate exceeds $35\%$, the pipeline bundler automatically down-throttles the dispatch frequency of that message category.
* **Metric Owner**: Product & User Experience Guild
