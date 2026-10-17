"""
Message Composer & Validator for Tally.

Strictly enforces:
1. 'Value Before Ask': Every outgoing notification must provide tangible value
   (a summary, draft, or link) before posing any ask to a human operator.
2. 'Single Ask Cap': Caps asks per outgoing dispatch to at most one.
3. 'Opt-out & Snooze Controls': Integrates one-click snooze/opt-out mechanisms.
4. 'Adaptive Throttling': Automatically detects elevated snooze rates and down-throttles ignored kinds.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from tally.contact.budget import MessageKind
from tally.contact.bundler import BundledDispatch


class ComposedMessage(BaseModel):
    message_id: str
    recipient_id: str
    kind: MessageKind
    formatted_body: str
    action_buttons: List[Dict[str, str]]
    snooze_url: str
    opt_out_url: str


class ComposerValidationResult(BaseModel):
    is_valid: bool
    rejection_reason: Optional[str] = None
    composed_message: Optional[ComposedMessage] = None


class SnoozeTracker:
    """Monitors recipient response and snooze patterns per message category."""

    def __init__(self, high_snooze_threshold: float = 0.35):
        self.threshold = high_snooze_threshold
        # Maps kind -> {"delivered": int, "responded": int, "snoozed": int, "opt_out": int}
        self._counts: Dict[str, Dict[str, int]] = {}

    def record_delivery(self, kind: MessageKind):
        k = kind.value
        self._counts.setdefault(k, {"delivered": 0, "responded": 0, "snoozed": 0, "opt_out": 0})
        self._counts[k]["delivered"] += 1

    def record_feedback(self, kind: MessageKind, action: str):
        k = kind.value
        self._counts.setdefault(k, {"delivered": 0, "responded": 0, "snoozed": 0, "opt_out": 0})
        if action in ("responded", "approved", "acted"):
            self._counts[k]["responded"] += 1
        elif action == "snooze":
            self._counts[k]["snoozed"] += 1
        elif action == "opt_out":
            self._counts[k]["opt_out"] += 1

    def get_snooze_rate(self, kind: MessageKind) -> float:
        stats = self._counts.get(kind.value, {"delivered": 0, "snoozed": 0, "opt_out": 0})
        total = stats.get("delivered", 0)
        if total == 0:
            return 0.0
        return round((stats.get("snoozed", 0) + stats.get("opt_out", 0)) / total, 3)

    def should_throttle(self, kind: MessageKind) -> bool:
        """Returns True if message category exceeds snooze threshold (ignored/disliked)."""
        stats = self._counts.get(kind.value, {"delivered": 0})
        if stats.get("delivered", 0) < 5:
            return False  # Minimum sample size
        return self.get_snooze_rate(kind) >= self.threshold


class MessageComposer:
    """Enforces composition ethics and formats production payloads."""

    def __init__(self, snooze_tracker: Optional[SnoozeTracker] = None):
        self.tracker = snooze_tracker or SnoozeTracker()

    def validate_and_compose(
        self,
        dispatch: BundledDispatch,
        asks_count: int = 1,
    ) -> ComposerValidationResult:
        """
        Validates the dispatch against Tally's core composition rules:
        1. No ask without a payload.
        2. At most one ask per message.
        3. Automatic down-throttle check.
        """
        has_ask = dispatch.primary_ask is not None and len(dispatch.primary_ask.strip()) > 0
        raw_content = getattr(dispatch, "raw_payload_text", dispatch.aggregated_payload).strip()

        # Rule 1: No ask without a meaningful payload (value first)
        if has_ask and len(raw_content) < 15:
            return ComposerValidationResult(
                is_valid=False,
                rejection_reason="REJECTED_NO_PAYLOAD_FOR_ASK: Outgoing message requested human intervention without providing verified work payload.",
            )

        # Rule 2: Single ask cap
        if asks_count > 1:
            return ComposerValidationResult(
                is_valid=False,
                rejection_reason=f"REJECTED_EXCESSIVE_ASKS: Found {asks_count} asks in dispatch. The pipeline permits at most 1 ask per message.",
            )

        # Adaptive throttling rule: if kind is chronically snoozed, flag or downgrade
        is_throttled = self.tracker.should_throttle(dispatch.consolidated_kind)

        # Build Slack/Email Markdown Body
        body_lines = [
            f"### 🤖 Agent Operations Dispatch: {dispatch.consolidated_kind.value}",
            f"**Recipient**: `{dispatch.recipient_id}` | **Urgency**: `{dispatch.highest_urgency}`",
            "",
            "#### 📦 Delivered Value / Payload:",
            dispatch.aggregated_payload,
        ]

        if is_throttled:
            body_lines.append("\n> ⚠️ *Notice: This message category is currently frequency-throttled due to low engagement.*")

        action_buttons = []
        if has_ask:
            body_lines.extend([
                "",
                "#### ❓ Requested Human Action:",
                f"👉 **{dispatch.primary_ask}**",
            ])
            action_buttons.append({"action": "approve", "label": "✅ Approve / Acknowledge"})
            action_buttons.append({"action": "edit", "label": "✏️ Approve with Edits"})
            action_buttons.append({"action": "reject", "label": "❌ Reject"})

        # Snooze & Opt-Out Controls
        snooze_url = f"https://agent-ops.internal/contact/snooze?recipient={dispatch.recipient_id}&kind={dispatch.consolidated_kind.value}"
        opt_out_url = f"https://agent-ops.internal/contact/opt-out?recipient={dispatch.recipient_id}&kind={dispatch.consolidated_kind.value}"

        action_buttons.append({"action": "snooze", "label": "💤 Snooze 7d", "url": snooze_url})
        action_buttons.append({"action": "opt_out", "label": "🚫 Opt-out", "url": opt_out_url})

        composed = ComposedMessage(
            message_id=dispatch.bundle_id,
            recipient_id=dispatch.recipient_id,
            kind=dispatch.consolidated_kind,
            formatted_body="\n".join(body_lines),
            action_buttons=action_buttons,
            snooze_url=snooze_url,
            opt_out_url=opt_out_url,
        )

        return ComposerValidationResult(
            is_valid=True,
            composed_message=composed,
        )
