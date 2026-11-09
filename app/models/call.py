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
    Integer,
    String,
    Text,
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


class LeadScore(Base):
    __tablename__ = "lead_scores"

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


class RejectedRequest(Base):
    __tablename__ = "rejected_requests"

    id = Column(Integer, primary_key=True)
    endpoint = Column(String(255), nullable=False)
    reason = Column(Text, nullable=False)
    payload = Column(JSON, nullable=True)  # safe copy: no tokens, truncated
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
