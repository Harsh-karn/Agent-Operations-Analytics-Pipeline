"""
Comprehensive test suite for Tally Contact Engine:
- Concurrency stress tests on try_spend() (Zero budget overruns guaranteed)
- Quiet hours holding behavior
- Bundler deduplication and stale expiration
- Composer 'Value-First' validation and single ask enforcement
- Channel authorization verification
- Adaptive snooze-rate throttling
"""

import concurrent.futures
import datetime
import os
import tempfile
import pytest

from tally.contact.budget import (
    ContactBudgetManager,
    MessageKind,
    SpendResult,
    SpendStatus,
)
from tally.contact.bundler import (
    CandidateMessage,
    MessageBundler,
)
from tally.contact.composer import (
    MessageComposer,
    SnoozeTracker,
)
from tally.contact.channels import (
    ChannelDispatchError,
    MockChannel,
)


def test_concurrent_budget_spend_guarantee():
    """
    Concurrency Stress Test:
    Spawns 25 concurrent threads attempting to spend 1 unit when limit = 5.
    Guarantees: Exactly 5 allowed, 20 denied, final used == 5.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        mgr = ContactBudgetManager(db_path=db_path)
        person_id = "user-concurrency-test"
        mgr.set_budget(person_id=person_id, limit=5, timezone="UTC", quiet_hours_start=23, quiet_hours_end=4)

        now = datetime.datetime(2026, 10, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)

        def attempt_spend(worker_id: int) -> SpendResult:
            # Separate connection instance per worker thread
            worker_mgr = ContactBudgetManager(db_path=db_path)
            return worker_mgr.try_spend(
                person_id=person_id,
                message_id=f"msg-worker-{worker_id}",
                kind=MessageKind.FYI_DIGEST,
                cost=1,
                now=now,
            )

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(attempt_spend, i) for i in range(25)]
            for fut in concurrent.futures.as_completed(futures):
                results.append(fut.result())

        allowed = [r for r in results if r.status == SpendStatus.ALLOWED]
        denied = [r for r in results if r.status == SpendStatus.DENIED_BUDGET]

        assert len(allowed) == 5, f"Expected exactly 5 allowed spends, got {len(allowed)}"
        assert len(denied) == 20, f"Expected exactly 20 denied spends, got {len(denied)}"

        # Check tokens
        for r in allowed:
            assert r.authorized_token.startswith("AUTH-SPEND-")

        # Verify state in database
        final_budget = mgr.get_budget(person_id)
        assert final_budget["budget_used"] == 5
        assert final_budget["remaining"] == 0

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_quiet_hours_deferral():
    """Verify that messages sent during quiet hours are held, not dropped, unless critical."""
    mgr = ContactBudgetManager(db_path=":memory:")
    person_id = "usr-quiet"
    mgr.set_budget(person_id, limit=10, timezone="America/New_York", quiet_hours_start=19, quiet_hours_end=8)

    # 10 PM in NY
    night_time = datetime.datetime(2026, 10, 15, 22, 0, 0)

    # Regular FYI digest should be held
    res1 = mgr.try_spend(person_id, message_id="m1", kind=MessageKind.FYI_DIGEST, now=night_time)
    assert res1.status == SpendStatus.HELD_QUIET_HOURS
    assert res1.budget_used_after == 0  # No budget consumed while held

    # Critical security alert should bypass quiet hours
    res2 = mgr.try_spend(person_id, message_id="m2", kind=MessageKind.CRITICAL_SECURITY_ALERT, now=night_time)
    assert res2.status == SpendStatus.ALLOWED
    assert res2.authorized_token is not None


def test_bundler_deduplication_and_expiration():
    """Verify bundler drops expired messages and deduplicates identical candidate messages."""
    bundler = MessageBundler()
    recipient = "usr-recipient-1"
    now = datetime.datetime(2026, 10, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)

    # 1. Stale/expired message
    bundler.submit(CandidateMessage(
        message_id="msg-stale",
        recipient_id=recipient,
        sender_agent_id="agent-01",
        title="Old Report",
        payload="Outdated summary from 2 hours ago",
        expires_at=now - datetime.timedelta(hours=1),
    ))

    # 2. Duplicate messages
    bundler.submit(CandidateMessage(
        message_id="msg-dup-1",
        recipient_id=recipient,
        sender_agent_id="agent-02",
        title="Payment Anomaly",
        payload="Detected spike in transaction latency on EU gateway",
        expires_at=now + datetime.timedelta(hours=2),
    ))
    bundler.submit(CandidateMessage(
        message_id="msg-dup-2",
        recipient_id=recipient,
        sender_agent_id="agent-02",
        title="Payment Anomaly",
        payload="Detected spike in transaction latency on EU gateway",
        expires_at=now + datetime.timedelta(hours=2),
    ))

    # 3. Unique action ask message
    bundler.submit(CandidateMessage(
        message_id="msg-ask-1",
        recipient_id=recipient,
        sender_agent_id="agent-03",
        title="PR #402 Validation",
        payload="Completed test run with 100% pass rate. Lint check verified.",
        has_ask=True,
        ask_text="Please sign off on PR #402 merge to staging.",
        expires_at=now + datetime.timedelta(hours=4),
    ))

    assert bundler.get_queue_size(recipient) == 4

    dispatch = bundler.flush_bundle(recipient, now=now)
    assert dispatch is not None
    assert dispatch.items_count == 4
    assert dispatch.items_expired_dropped_count == 1
    assert dispatch.items_deduplicated_count == 1
    assert len(dispatch.candidate_message_ids) == 2
    assert dispatch.primary_ask == "Please sign off on PR #402 merge to staging."
    assert dispatch.consolidated_kind == MessageKind.GATE_APPROVAL_ASK


def test_composer_rules_value_first_and_ask_cap():
    """Verify composer rejects asks without payload and caps asks to 1."""
    composer = MessageComposer()
    now = datetime.datetime.now(datetime.timezone.utc)

    # Violation 1: Ask with no payload
    bad_dispatch_no_payload = CandidateMessage(
        message_id="m1",
        recipient_id="u1",
        sender_agent_id="a1",
        title="Ping",
        payload="Hi",  # Stub/empty payload
        has_ask=True,
        ask_text="Review this now",
        expires_at=now + datetime.timedelta(hours=1),
    )
    bundler = MessageBundler()
    bundler.submit(bad_dispatch_no_payload)
    disp1 = bundler.flush_bundle("u1")

    res1 = composer.validate_and_compose(disp1)
    assert not res1.is_valid
    assert "REJECTED_NO_PAYLOAD_FOR_ASK" in res1.rejection_reason

    # Violation 2: More than 1 ask in dispatch
    good_payload = "Generated unit test report: 45 passed, 0 failed. Full logs linked in artifact."
    bundler.submit(CandidateMessage(
        message_id="m2",
        recipient_id="u2",
        sender_agent_id="a2",
        title="Test report",
        payload=good_payload,
        has_ask=True,
        ask_text="Approve release",
        expires_at=now + datetime.timedelta(hours=1),
    ))
    disp2 = bundler.flush_bundle("u2")
    res2 = composer.validate_and_compose(disp2, asks_count=2)
    assert not res2.is_valid
    assert "REJECTED_EXCESSIVE_ASKS" in res2.rejection_reason

    # Compliant dispatch
    res3 = composer.validate_and_compose(disp2, asks_count=1)
    assert res3.is_valid
    assert res3.composed_message is not None
    assert "Delivered Value / Payload:" in res3.composed_message.formatted_body
    assert any(b["action"] == "snooze" for b in res3.composed_message.action_buttons)


def test_channel_authorization_enforcement():
    """Verify channels reject dispatches without valid spend authorization tokens."""
    channel = MockChannel()
    now = datetime.datetime.now(datetime.timezone.utc)
    bundler = MessageBundler()
    bundler.submit(CandidateMessage(
        message_id="m-valid",
        recipient_id="u-ch",
        sender_agent_id="a1",
        title="Nightly Summary",
        payload="All 12 automated workflows completed without incident.",
        expires_at=now + datetime.timedelta(hours=1),
    ))
    disp = bundler.flush_bundle("u-ch")
    composer = MessageComposer()
    res = composer.validate_and_compose(disp)

    # Attempt without token
    with pytest.raises(ChannelDispatchError):
        channel.send(res.composed_message, auth_token="")

    with pytest.raises(ChannelDispatchError):
        channel.send(res.composed_message, auth_token="FAKE-TOKEN-123")

    # Attempt with valid token
    result = channel.send(res.composed_message, auth_token="AUTH-SPEND-u-ch-m-valid-20261015")
    assert result["status"] == "SUCCESS"
    assert len(channel.dispatched) == 1


def test_adaptive_snooze_throttling():
    """Verify system flags message kinds for throttling when snooze rate exceeds 35%."""
    tracker = SnoozeTracker(high_snooze_threshold=0.35)
    kind = MessageKind.FYI_DIGEST

    # Deliver 10 items, 4 snoozed (40% snooze rate > 35%)
    for _ in range(10):
        tracker.record_delivery(kind)

    for _ in range(4):
        tracker.record_feedback(kind, "snooze")

    assert tracker.get_snooze_rate(kind) == 0.40
    assert tracker.should_throttle(kind) is True
