# app/models/call.py
"""
Call lead-score and call-audit tables.

    calls              one row per sales call (task_id is the unique key)
    lead_scores        at most one per call (Lead Score operator result)
    call_audits        at most one per call (Call Audit operator result)
    rejected_requests  payloads refused by intake or the output webhook

No recordings or transcripts are stored here, only the recording link.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Boolean,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from ..core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CallStatus:
    RECEIVED = "received"
    SENT_TO_AUTO = "sent_to_auto"
    DONE = "done"
    FAILED = "failed"

    ALL = (RECEIVED, SENT_TO_AUTO, DONE, FAILED)


class Call(Base):
    __tablename__ = "calls"
    __table_args__ = (
        Index("ix_calls_created_at", "created_at"),
        Index("ix_calls_status_sent_to_auto_at", "status", "sent_to_auto_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(64), unique=True, nullable=False, index=True)
    lead_id = Column(String(128), nullable=True)
    agent_id = Column(String(128), nullable=False, index=True)
    agent_name = Column(String(255), nullable=False)
    customer_name = Column(String(255), nullable=True)
    call_date = Column(DateTime(timezone=True), nullable=True)
    recording_url = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default=CallStatus.RECEIVED, index=True)
    failure_reason = Column(Text, nullable=True)
    # Set when the hand-off to Auto succeeds. Drives the "stuck" warning.
    sent_to_auto_at = Column(DateTime(timezone=True), nullable=True)
    # Speaker-labelled transcript returned by the Auto workflow (text).
    transcript = Column(Text, nullable=True)
    # The final combined JSON from the Auto workflow, as received.
    auto_output = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    lead_score = relationship(
        "LeadScore", back_populates="call", uselist=False, lazy="selectin"
    )
    call_audit = relationship(
        "CallAudit", back_populates="call", uselist=False, lazy="selectin"
    )
    flags = relationship(
        "CallFlag", back_populates="call", lazy="selectin", order_by="CallFlag.id"
    )


class LeadScore(Base):
    __tablename__ = "lead_scores"
    __table_args__ = (Index("ix_lead_scores_band", "band"),)

    id = Column(Integer, primary_key=True)
    task_id = Column(
        String(64), ForeignKey("calls.task_id"), unique=True, nullable=False, index=True
    )
    band = Column(Integer, nullable=False)  # whole number 0..5
    label = Column(String(255), nullable=True)
    reason = Column(Text, nullable=False)
    evidence = Column(JSON, nullable=False, default=list)  # list of quote strings
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    call = relationship("Call", back_populates="lead_score")


class CallAudit(Base):
    __tablename__ = "call_audits"

    id = Column(Integer, primary_key=True)
    task_id = Column(
        String(64), ForeignKey("calls.task_id"), unique=True, nullable=False, index=True
    )
    # list of {"name": str, "score": 1..5, "evidence": [str]}
    checks = Column(JSON, nullable=False, default=list)
    score_percent = Column(Float, nullable=False)  # always recalculated by the backend
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    call = relationship("Call", back_populates="call_audit")


class CommandPolicy(Base):
    """A rule the Command Center itself enforces (not a Supervity Auto policy)."""

    __tablename__ = "command_policies"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    stage = Column(String(16), nullable=False)  # "intake" (before a call is saved) or "results" (once scored)
    action = Column(String(16), nullable=False)  # "reject" (intake only) or "flag"
    match_mode = Column(String(8), nullable=False, default="all")  # "all" or "any"
    conditions = Column(JSON, nullable=False, default=list)  # [{"field", "operator", "value"}]
    message = Column(String(255), nullable=True)  # shown when the policy matches
    source = Column(String(16), nullable=False, default="builder")  # "builder" or "ai"
    natural_language = Column(Text, nullable=True)
    hit_count = Column(Integer, nullable=False, default=0)
    created_by = Column(String(128), nullable=True)
    updated_by = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class CallFlag(Base):
    """A call a policy marked for review."""

    __tablename__ = "call_flags"
    __table_args__ = (UniqueConstraint("task_id", "policy_id", name="uq_call_flags_task_policy"),)

    id = Column(Integer, primary_key=True)
    task_id = Column(String(64), ForeignKey("calls.task_id"), nullable=False, index=True)
    policy_id = Column(Integer, nullable=False, index=True)
    policy_name = Column(String(120), nullable=False)
    message = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    call = relationship("Call", back_populates="flags")


class RejectedRequest(Base):
    __tablename__ = "rejected_requests"

    id = Column(Integer, primary_key=True)
    endpoint = Column(String(255), nullable=False)
    reason = Column(Text, nullable=False)
    payload = Column(JSON, nullable=True)  # safe copy: no tokens, truncated
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
