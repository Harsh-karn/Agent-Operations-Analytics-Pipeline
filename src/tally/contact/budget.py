"""
Transactional Interruption Budget Engine for Tally.

Guarantees hard, code-enforced per-person interruption limits.
No notification can be transmitted without an atomic authorization token from try_spend().
"""

from __future__ import annotations

import datetime
from enum import Enum
from pathlib import Path
from typing import NamedTuple, Optional
import sqlite3
from zoneinfo import ZoneInfo
from pydantic import BaseModel


class MessageKind(str, Enum):
    FYI_DIGEST = "FYI_DIGEST"
    GATE_APPROVAL_ASK = "GATE_APPROVAL_ASK"
    ACTION_REQUEST = "ACTION_REQUEST"
    CRITICAL_SECURITY_ALERT = "CRITICAL_SECURITY_ALERT"


DEFAULT_KIND_COSTS = {
    MessageKind.FYI_DIGEST: 1,
    MessageKind.GATE_APPROVAL_ASK: 2,
    MessageKind.ACTION_REQUEST: 3,
    MessageKind.CRITICAL_SECURITY_ALERT: 0,
}


class SpendStatus(str, Enum):
    ALLOWED = "ALLOWED"
    DENIED_BUDGET = "DENIED_BUDGET"
    HELD_QUIET_HOURS = "HELD_QUIET_HOURS"
    INVALID_PERSON = "INVALID_PERSON"


class SpendResult(BaseModel):
    status: SpendStatus
    person_id: str
    cost_requested: int
    budget_limit: int
    budget_used_before: int
    budget_used_after: int
    authorized_token: Optional[str] = None
    next_send_window: Optional[str] = None


class ContactBudgetManager:
    """Manages transactional interruption budgets and quiet-hours enforcement."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._shared_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._shared_conn = sqlite3.connect(
                ":memory:",
                check_same_thread=False,
                isolation_level=None
            )
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._shared_conn is not None:
            return self._shared_conn
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            isolation_level=None,  # Manual transaction management
            check_same_thread=False
        )
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_db(self):
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contact_budget (
                person_id TEXT NOT NULL,
                week_start TEXT NOT NULL,
                budget_limit INTEGER NOT NULL,
                budget_used INTEGER NOT NULL DEFAULT 0,
                timezone TEXT NOT NULL DEFAULT 'America/New_York',
                quiet_hours_start INTEGER NOT NULL DEFAULT 19,
                quiet_hours_end INTEGER NOT NULL DEFAULT 8,
                PRIMARY KEY (person_id, week_start)
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contact_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id TEXT NOT NULL,
                ts TEXT NOT NULL,
                message_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                cost INTEGER NOT NULL,
                channel TEXT NOT NULL,
                status TEXT NOT NULL
            );
        """)
        if self._shared_conn is None:
            conn.close()

    def set_budget(
        self,
        person_id: str,
        limit: int,
        week_start: Optional[str] = None,
        timezone: str = "America/New_York",
        quiet_hours_start: int = 19,
        quiet_hours_end: int = 8,
    ):
        """Initializes or updates a person's budget configuration."""
        if week_start is None:
            today = datetime.date.today()
            week_start = (today - datetime.timedelta(days=today.weekday())).isoformat()

        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT INTO contact_budget (person_id, week_start, budget_limit, budget_used, timezone, quiet_hours_start, quiet_hours_end)
                VALUES (?, ?, ?, 0, ?, ?, ?)
                ON CONFLICT(person_id, week_start) DO UPDATE SET
                    budget_limit = excluded.budget_limit,
                    timezone = excluded.timezone,
                    quiet_hours_start = excluded.quiet_hours_start,
                    quiet_hours_end = excluded.quiet_hours_end;
            """, (person_id, week_start, limit, timezone, quiet_hours_start, quiet_hours_end))
        finally:
            if self._shared_conn is None:
                conn.close()

    def get_budget(self, person_id: str, week_start: Optional[str] = None) -> Optional[dict]:
        """Fetches current budget state."""
        if week_start is None:
            today = datetime.date.today()
            week_start = (today - datetime.timedelta(days=today.weekday())).isoformat()

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT person_id, week_start, budget_limit, budget_used, timezone, quiet_hours_start, quiet_hours_end
                FROM contact_budget
                WHERE person_id = ? AND week_start = ?;
            """, (person_id, week_start))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "person_id": row[0],
                "week_start": row[1],
                "budget_limit": row[2],
                "budget_used": row[3],
                "remaining": max(0, row[2] - row[3]),
                "timezone": row[4],
                "quiet_hours_start": row[5],
                "quiet_hours_end": row[6],
            }
        finally:
            if self._shared_conn is None:
                conn.close()

    def is_in_quiet_hours(
        self,
        timezone_str: str,
        quiet_start: int,
        quiet_end: int,
        current_dt: Optional[datetime.datetime] = None
    ) -> bool:
        """Determines whether current time falls within recipient's quiet window."""
        try:
            tz = ZoneInfo(timezone_str)
        except Exception:
            tz = datetime.timezone.utc

        now = current_dt or datetime.datetime.now(tz)
        if now.tzinfo is None:
            now = now.replace(tzinfo=tz)
        else:
            now = now.astimezone(tz)

        hour = now.hour
        # Overnight quiet window (e.g. 19:00 to 08:00)
        if quiet_start > quiet_end:
            return hour >= quiet_start or hour < quiet_end
        else:
            return quiet_start <= hour < quiet_end

    def try_spend(
        self,
        person_id: str,
        message_id: str,
        kind: MessageKind = MessageKind.FYI_DIGEST,
        channel: str = "slack",
        cost: Optional[int] = None,
        week_start: Optional[str] = None,
        now: Optional[datetime.datetime] = None,
    ) -> SpendResult:
        """
        Atomic transactional spend attempt.
        Only allows spend if used + cost <= limit.
        Guarantees zero over-spending under concurrent threads.
        """
        if cost is None:
            cost = DEFAULT_KIND_COSTS.get(kind, 1)

        if week_start is None:
            today = (now.date() if now else datetime.date.today())
            week_start = (today - datetime.timedelta(days=today.weekday())).isoformat()

        timestamp_str = (now or datetime.datetime.now(datetime.timezone.utc)).isoformat()

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # BEGIN IMMEDIATE ensures write lock is acquired upfront to prevent concurrency race
            cursor.execute("BEGIN IMMEDIATE;")

            cursor.execute("""
                SELECT budget_limit, budget_used, timezone, quiet_hours_start, quiet_hours_end
                FROM contact_budget
                WHERE person_id = ? AND week_start = ?;
            """, (person_id, week_start))
            row = cursor.fetchone()

            if not row:
                cursor.execute("ROLLBACK;")
                return SpendResult(
                    status=SpendStatus.INVALID_PERSON,
                    person_id=person_id,
                    cost_requested=cost,
                    budget_limit=0,
                    budget_used_before=0,
                    budget_used_after=0,
                )

            limit, used, tz_name, q_start, q_end = row

            # Check quiet hours (critical alerts bypass quiet hours)
            if kind != MessageKind.CRITICAL_SECURITY_ALERT:
                if self.is_in_quiet_hours(tz_name, q_start, q_end, now):
                    cursor.execute("""
                        INSERT INTO contact_log (person_id, ts, message_id, kind, cost, channel, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?);
                    """, (person_id, timestamp_str, message_id, kind.value, 0, channel, SpendStatus.HELD_QUIET_HOURS.value))
                    cursor.execute("COMMIT;")
                    return SpendResult(
                        status=SpendStatus.HELD_QUIET_HOURS,
                        person_id=person_id,
                        cost_requested=cost,
                        budget_limit=limit,
                        budget_used_before=used,
                        budget_used_after=used,
                        next_send_window=f"Next morning after {q_end:02d}:00 {tz_name}",
                    )

            # Check Budget Limit
            if used + cost > limit:
                cursor.execute("""
                    INSERT INTO contact_log (person_id, ts, message_id, kind, cost, channel, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (person_id, timestamp_str, message_id, kind.value, cost, channel, SpendStatus.DENIED_BUDGET.value))
                cursor.execute("COMMIT;")
                return SpendResult(
                    status=SpendStatus.DENIED_BUDGET,
                    person_id=person_id,
                    cost_requested=cost,
                    budget_limit=limit,
                    budget_used_before=used,
                    budget_used_after=used,
                )

            # Atomic Increment
            new_used = used + cost
            cursor.execute("""
                UPDATE contact_budget
                SET budget_used = ?
                WHERE person_id = ? AND week_start = ?;
            """, (new_used, person_id, week_start))

            cursor.execute("""
                INSERT INTO contact_log (person_id, ts, message_id, kind, cost, channel, status)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (person_id, timestamp_str, message_id, kind.value, cost, channel, SpendStatus.ALLOWED.value))

            cursor.execute("COMMIT;")

            token = f"AUTH-SPEND-{person_id}-{message_id}-{timestamp_str}"
            return SpendResult(
                status=SpendStatus.ALLOWED,
                person_id=person_id,
                cost_requested=cost,
                budget_limit=limit,
                budget_used_before=used,
                budget_used_after=new_used,
                authorized_token=token,
            )

        except Exception as e:
            cursor.execute("ROLLBACK;")
            raise e
        finally:
            if self._shared_conn is None:
                conn.close()
