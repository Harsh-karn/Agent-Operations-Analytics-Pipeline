# ADR 0002: Defensible Grading via Immutable SQL Query Disclosure

## Status
Accepted

## Context
Organizational maturity scorecards frequently fail because team leads view them as arbitrary, opaque, or politically motivated. When a team receives a "Bronze" or "Amber" grade, standard management responses devolve into qualitative arguments over definitions or data staleness.
Furthermore, if metrics logic is modified in code over time, retrospective historical grades become irreproducible if the historical query is not captured.

## Decision
1. **Rule Versioning & Declarative Rubrics**: All grading rules, thresholds, and weighting coefficients reside in a versioned SQL table / CTE (`grading_rules_v1`), completely free of hardcoded procedural logic.
2. **Deterministic SQL Disclosure Endpoint**:
   - `GET /grades/{team}/{period}` returns the computed grade, each of the 5 constituent signals, and the rule that determined each tier.
   - `GET /grades/{team}/{period}/query` returns the exact, immutable SQL query text, schema dependencies, and parameter bindings that computed that specific grade.
3. **Dispute Resolution as Re-executable Queries**:
   - When a team disputes a score (e.g. arguing an automated workflow was omitted), they submit a dispute note and source data correction.
   - The platform reruns the *exact* stored SQL query against updated data. If the numbers change the grade, the system updates automatically.
   - No human administrator "overrides" a grade with a manual switch.

## Consequences
### Positive
- Total transparency: Every grade is backed by code, not opinion.
- Complete reproducibility: Anyone can copy the SQL from the API and execute it directly in BigQuery console to obtain the identical result.

### Negative / Trade-offs
- The analytics pipeline must store the rendered query string and rule version alongside every recorded grade in the persistent history table.
