# ADR 0001: Transactional Consistency Model for Interruption Budgets

## Status
Accepted

## Context
Autonomous agents generate proactive alerts, pull request reviews, approval requests, and digests. Without strict mechanical controls, agents rapidly cause alert fatigue, leading human operators to mute channels or disregard agent output.
Many systems attempt to manage notification volume through "soft policies" or asynchronously calculated metrics (e.g., nightly batch counts). In high-concurrency environments where multiple agents fire near-simultaneous events, an eventual consistency model creates a race condition:
- Operator has 1 remaining budget unit for the week.
- Agent A and Agent B both check remaining budget asynchronously, see `budget_remaining = 1`, and both fire messages.
- The operator receives 2 interruptions, violating the human agreement.

## Decision
We enforce interruption budgets strictly in code via a single transactional primitive:
`try_spend(person_id: str, cost: int) -> bool`

1. **Transactional Row-Locking**: The budget check and the spend increment execute inside an ACID transaction (`SELECT ... FOR UPDATE` in PostgreSQL, or atomic transaction lock in SQLite/DuckDB local engine).
2. **Atomic Condition**: The counter `used` is incremented if and only if `used + cost <= limit`. If the condition fails, the transaction safely aborts and returns `False`.
3. **No Alternative Bypass**: All delivery channels (Slack, Email, Webhooks) must receive a signed authorization token from `try_spend` before transmitting any message.

## Consequences
### Positive
- **Zero Budget Overruns**: Mathematically guarantees that a person will never receive more pings than their agreed limit, even under extreme concurrent bursts.
- **Trust Preservation**: Engineers and operators know the budget is a hard contractual ceiling, not a loose suggestion.

### Negative / Trade-offs
- Requires transactional database writes rather than cheap append-only event logs.
- Agents whose requests are rejected must handle deferral, bundling, or drop logic gracefully.
