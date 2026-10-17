# ADR 0003: Value Ledger - Net Deduction of Review Time and Range Estimates

## Status
Accepted

## Context
A major risk in AI and autonomous agent systems is executive skepticism over "hours saved" claims. Traditional ROI models multiply total agent executions by an estimated manual task duration. This leads to inflated, ungrounded numbers because:
1. It ignores the significant time human operators spend reviewing, fact-checking, and editing agent deliverables.
2. It assumes all tasks take a uniform time, masking measurement uncertainty.
3. It counts failed runs, rejected drafts, and rolled-back changes as "value delivered."

## Decision
1. **Measured Empirical Baselines**: Every agent registered in `agent_baselines` must have an empirical human duration timed by a practitioner, documented with measurement method, timestamp, and confidence tier (`HIGH`, `MEDIUM`, `LOW`).
2. **Net Deduction of Review Time**:
   $$\text{Net Minutes} = \text{Baseline Minutes} \times \text{Approval Weight} - \text{Human Review Duration}$$
   - If an agent generates code in 10 seconds that took a human 30 minutes, but the human spends 25 minutes debugging and editing it, the net work absorbed is **5 minutes**, not 30 minutes.
   - If rejected, absorbed work is **0 minutes**.
3. **Range-Based Reporting**: Monthly reports and dashboards will never display a single point estimate. They must present a range:
   - **Low Estimate**: Conservative bound (accounting for baseline uncertainty and maximum review drag).
   - **Expected Estimate**: Realistic operational outcome.
   - **High Estimate**: Optimal execution ceiling.

## Consequences
### Positive
- Defensibility: Finance and leadership trust the figures because they account for human review friction and explicit uncertainty bounds.
- Incentivizes Quality: Encourages agents that generate high-quality drafts requiring minimal editing, as heavy edits degrade net absorbed minutes.

### Negative / Trade-offs
- Requires instrumentation of the human approval step (recording time elapsed between request and review decision).
