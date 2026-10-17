"""
Message Bundler for Agent Operations Analytics Pipeline.

Collects, deduplicates, and merges pending candidate agent messages into single dispatches.
Prevents uncoordinated notification storms by dropping stale items and coalescing pings.
"""

from __future__ import annotations

import datetime
import hashlib
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from tally.contact.budget import MessageKind


class CandidateMessage(BaseModel):
    message_id: str
    recipient_id: str
    sender_agent_id: str
    kind: MessageKind = MessageKind.FYI_DIGEST
    urgency: str = Field(default="MEDIUM", description="LOW, MEDIUM, HIGH, CRITICAL")
    title: str
    payload: str = Field(..., description="Useful work payload: summary, link, draft")
    has_ask: bool = False
    ask_text: Optional[str] = None
    action_type: Optional[str] = None
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    expires_at: datetime.datetime
    dedup_key: Optional[str] = None

    def get_dedup_hash(self) -> str:
        if self.dedup_key:
            return self.dedup_key
        raw = f"{self.recipient_id}:{self.kind.value}:{self.title}:{self.payload.strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class BundledDispatch(BaseModel):
    bundle_id: str
    recipient_id: str
    items_count: int
    items_deduplicated_count: int
    items_expired_dropped_count: int
    highest_urgency: str
    consolidated_kind: MessageKind
    aggregated_payload: str
    raw_payload_text: str
    candidate_message_ids: List[str]
    primary_ask: Optional[str] = None
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


class MessageBundler:
    """In-memory or stateful collector of candidate messages before scheduled delivery."""

    def __init__(self):
        # Maps recipient_id -> List[CandidateMessage]
        self._queues: Dict[str, List[CandidateMessage]] = {}

    def submit(self, message: CandidateMessage):
        """Enqueue a candidate message from an agent producer."""
        if message.recipient_id not in self._queues:
            self._queues[message.recipient_id] = []
        self._queues[message.recipient_id].append(message)

    def get_queue_size(self, recipient_id: str) -> int:
        return len(self._queues.get(recipient_id, []))

    def flush_bundle(
        self,
        recipient_id: str,
        now: Optional[datetime.datetime] = None,
    ) -> Optional[BundledDispatch]:
        """
        Processes and aggregates pending candidates for recipient:
        1. Drops expired candidates.
        2. Deduplicates candidates by content hash.
        3. Merges remaining items into a single structured BundledDispatch.
        """
        raw_candidates = self._queues.pop(recipient_id, [])
        if not raw_candidates:
            return None

        current_time = now or datetime.datetime.now(datetime.timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=datetime.timezone.utc)

        # 1. Filter out expired candidates
        valid_candidates = []
        expired_count = 0
        for c in raw_candidates:
            exp = c.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=datetime.timezone.utc)
            if exp <= current_time:
                expired_count += 1
            else:
                valid_candidates.append(c)

        if not valid_candidates:
            return None

        # 2. Deduplicate
        deduped: List[CandidateMessage] = []
        seen_hashes = set()
        dedup_dropped_count = 0

        for c in valid_candidates:
            h = c.get_dedup_hash()
            if h in seen_hashes:
                dedup_dropped_count += 1
            else:
                seen_hashes.add(h)
                deduped.append(c)

        # 3. Urgency sort: CRITICAL > HIGH > MEDIUM > LOW
        urgency_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        deduped.sort(key=lambda m: urgency_rank.get(m.urgency, 1), reverse=True)

        highest_urgency = deduped[0].urgency
        has_ask = any(m.has_ask for m in deduped)
        primary_ask = next((m.ask_text for m in deduped if m.has_ask and m.ask_text), None)

        if any(m.kind == MessageKind.CRITICAL_SECURITY_ALERT for m in deduped):
            consolidated_kind = MessageKind.CRITICAL_SECURITY_ALERT
        elif has_ask:
            consolidated_kind = MessageKind.GATE_APPROVAL_ASK
        else:
            consolidated_kind = MessageKind.FYI_DIGEST

        # Formulate consolidated payload
        payload_sections = []
        for idx, m in enumerate(deduped, 1):
            sec = f"[{idx}] {m.title} (Agent: {m.sender_agent_id})\n    {m.payload}"
            payload_sections.append(sec)

        bundle_text = "\n\n".join(payload_sections)
        raw_text = "\n".join(m.payload.strip() for m in deduped)
        bundle_id = f"bnd-{recipient_id}-{int(current_time.timestamp())}"

        return BundledDispatch(
            bundle_id=bundle_id,
            recipient_id=recipient_id,
            items_count=len(raw_candidates),
            items_deduplicated_count=dedup_dropped_count,
            items_expired_dropped_count=expired_count,
            highest_urgency=highest_urgency,
            consolidated_kind=consolidated_kind,
            aggregated_payload=bundle_text,
            raw_payload_text=raw_text,
            candidate_message_ids=[m.message_id for m in deduped],
            primary_ask=primary_ask,
            created_at=current_time,
        )
