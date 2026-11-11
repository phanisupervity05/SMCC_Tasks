"""
AI Tools for the Supervity AI Manager.

Every tool reads the real calls data of this Command Center (calls, lead scores, call
audits, rejected requests). Nothing is invented: if a tool returns nothing, the AI says so.
"""

import logging
from typing import Any, Dict, List

from app.core.database import SessionLocal
from app.models.call import Call, CallStatus, LeadScore, RejectedRequest
from app.services.call_stats import compute_stats
from app.services.call_views import call_detail, call_summary, rejected_view

logger = logging.getLogger(__name__)


def get_tool_definitions() -> List:
    """Tools the AI can call. Returns [] if the AI package is not installed."""
    try:
        from google.genai import types as t

        S, T = t.Schema, t.Type
        return [
            t.Tool(
                function_declarations=[
                    t.FunctionDeclaration(
                        name="get_call_stats",
                        description=(
                            "Overall numbers for the sales calls: total, processed, failed, rejected, in progress, "
                            "stuck, success rate, average audit score, lead band distribution (band 0 to 5), "
                            "calls per day and per-agent performance. Use for any 'how many' or 'how are we doing' question."
                        ),
                        parameters=S(type=T.OBJECT, properties={}),
                    ),
                    t.FunctionDeclaration(
                        name="list_calls",
                        description="List calls, newest first, optionally filtered by status, lead band or sales agent.",
                        parameters=S(
                            type=T.OBJECT,
                            properties={
                                "status": S(type=T.STRING, description="Call status", enum=list(CallStatus.ALL)),
                                "band": S(type=T.INTEGER, description="Lead band 0 to 5"),
                                "agent_id": S(type=T.STRING, description="Sales agent ID"),
                                "limit": S(type=T.INTEGER, description="Max calls to return (default 10, max 25)"),
                            },
                        ),
                    ),
                    t.FunctionDeclaration(
                        name="get_call_details",
                        description=(
                            "Full detail for one call by task ID: lead band, reason and evidence, audit checks and "
                            "score, status and failure reason."
                        ),
                        parameters=S(
                            type=T.OBJECT,
                            properties={"task_id": S(type=T.STRING, description="The call's task ID")},
                            required=["task_id"],
                        ),
                    ),
                    t.FunctionDeclaration(
                        name="list_rejected_requests",
                        description="Recent requests refused at intake (missing or invalid fields), with the reason.",
                        parameters=S(
                            type=T.OBJECT,
                            properties={"limit": S(type=T.INTEGER, description="Max to return (default 10)")},
                        ),
                    ),
                    t.FunctionDeclaration(
                        name="explain_page",
                        description="Explain what a page of this Command Center shows and what the user can do there.",
                        parameters=S(
                            type=T.OBJECT,
                            properties={"page_path": S(type=T.STRING, description="Path such as / or /calls/new")},
                            required=["page_path"],
                        ),
                    ),
                ]
            )
        ]
    except ImportError:
        return []


class ToolExecutor:
    """Runs AI tool calls against the real data."""

    PAGE_EXPLANATIONS = {
        "/calls/new": """**Drop a call**

Send a sales call for scoring and audit:
* Paste a recording link or drop an audio file
* Sales agent ID, agent name and **Lead ID** are required
* Customer name and call date are optional
* Dropping the same recording and date twice gives the same call, never a duplicate""",
        "/calls/": """**Call detail**

One call in full:
* Status and, if it failed, the reason, with a **Re-run** button
* **Lead score**: band 0 to 5, the reason and the customer quotes behind it
* **Call audit**: the 1 to 5 checks (Politeness, Information, Query solved), the score percent and a summary
* The recording link and the transcript""",
        "/rejected": """**Rejected requests**

Requests refused at intake before they became a call, each with the reason (for example a missing
Lead ID or an invalid recording link). Nothing here was scored.""",
        "/ai/policies": """**Policies**

Two kinds, on two tabs:
* **Command Center policies**: rules this app enforces on every call. Anyone approved can create, edit, switch off or delete them, with a rule builder or by describing the rule in plain English. A policy runs at intake (drop form and webhook) or after results, and either **flags** the call for review or, at intake, **rejects** it. Examples: duplicate Lead ID, Lead ID format, high-intent leads.
* **Auto policies (call agent)**: the two Supervity Auto policies that score each call, shown read only. The **ORL Lead Score Policy** gives band 0 to 5 and the **ORL Call Audit Policy** scores Politeness, Information and Query solved from 1 to 5.""",
        "/ai/insights": """**AI Insights**

Insights computed from your real calls: failed and stuck calls, rejected requests, high-intent leads
(band 4 and 5), the weakest audit area, agent performance and call volume. Click **Run Analysis**
to refresh them.""",
        "/settings": """**Settings**

Your profile, notification and display preferences.""",
        "/": """**Calls Dashboard**

The home screen for sales call intelligence:
* KPI cards: total, processed, failed, rejected and average audit score
* Lead band distribution (band 0 to 5), status breakdown, calls per day and sales agent table
* The full list of calls with filters for band, sales agent and status
* A **Re-run** button on failed calls
* A warning when calls are stuck in Sent to Auto""",
    }

    def execute(self, name: str, args: Dict) -> Any:
        logger.info(f"Executing tool: {name} with args: {args}")
        handlers = {
            "get_call_stats": self._get_call_stats,
            "list_calls": self._list_calls,
            "get_call_details": self._get_call_details,
            "list_rejected_requests": self._list_rejected,
            "explain_page": self._explain_page,
        }
        handler = handlers.get(name)
        if handler is None:
            return {"error": f"Unknown tool: {name}"}
        try:
            return handler(args or {})
        except Exception as e:  # a tool must never break the chat
            logger.exception("Tool %s failed", name)
            return {"error": f"Could not read the data: {type(e).__name__}"}

    def _get_call_stats(self, args: Dict) -> Dict:
        db = SessionLocal()
        try:
            return compute_stats(db, days=14)
        finally:
            db.close()

    def _list_calls(self, args: Dict) -> Dict:
        status = args.get("status")
        if status is not None and status not in CallStatus.ALL:
            return {"error": f"status must be one of: {', '.join(CallStatus.ALL)}"}
        limit = min(max(1, int(args.get("limit") or 10)), 25)
        db = SessionLocal()
        try:
            q = db.query(Call)
            if args.get("band") is not None:
                q = q.join(LeadScore, LeadScore.task_id == Call.task_id).filter(LeadScore.band == int(args["band"]))
            if args.get("agent_id"):
                q = q.filter(Call.agent_id == args["agent_id"])
            if status:
                q = q.filter(Call.status == status)
            total = q.count()
            rows = q.order_by(Call.created_at.desc(), Call.id.desc()).limit(limit).all()
            return {"total_matching": total, "calls": [call_summary(c) for c in rows]}
        finally:
            db.close()

    def _get_call_details(self, args: Dict) -> Dict:
        db = SessionLocal()
        try:
            call = db.query(Call).filter(Call.task_id == args.get("task_id")).first()
            if call is None:
                return {"error": "No call with that task ID."}
            d = call_detail(call)
            d.pop("auto_output", None)  # raw payload, not useful in chat
            if d.get("transcript"):
                d["transcript"] = d["transcript"][:1500]
            return d
        finally:
            db.close()

    def _list_rejected(self, args: Dict) -> Dict:
        limit = min(max(1, int(args.get("limit") or 10)), 25)
        db = SessionLocal()
        try:
            total = db.query(RejectedRequest).count()
            rows = db.query(RejectedRequest).order_by(RejectedRequest.id.desc()).limit(limit).all()
            items = [{k: v for k, v in rejected_view(r).items() if k != "payload"} for r in rows]
            return {"total": total, "items": items}
        finally:
            db.close()

    def _explain_page(self, args: Dict) -> str:
        path = args.get("page_path") or "/"
        if path == "/":
            return self.PAGE_EXPLANATIONS["/"]
        for prefix, text in self.PAGE_EXPLANATIONS.items():
            if prefix != "/" and path.startswith(prefix):
                return text
        return f"You're on **{path}**. Ask me about your calls, lead bands, audits or this page."


# Singleton instance
tool_executor = ToolExecutor()
