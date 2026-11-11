"""
AI Insights for the Call Intelligence Command Center.

Every insight is computed from the real calls in the database: lead bands, call audits,
failed and stuck calls, rejected requests and sales-agent performance. Nothing here is
sample data. When there are no calls yet, the only insight says so.
"""

import time
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.call import Call, CallStatus, RejectedRequest
from app.schemas.ai import (
    InsightsListResponse, InsightResponse, InsightType, InsightSeverity,
    PatternInfo, ActionRecommendation,
)
from app.services.call_stats import compute_stats
from .gemini import GeminiService

logger = logging.getLogger(__name__)

LOW_AUDIT_PERCENT = 60.0
HOT_BANDS = (4, 5)
COLD_BANDS = (0, 1)


def _plural(n: int, one: str, many: str | None = None) -> str:
    return one if n == 1 else (many or one + "s")


class InsightsService(GeminiService):
    """Builds insights, patterns and recommended actions from the calls data."""

    async def generate(
        self,
        batch_id: Optional[str] = None,
        date_range_start: Optional[datetime] = None,
        date_range_end: Optional[datetime] = None,
    ) -> InsightsListResponse:
        start = time.time()
        now = datetime.now(timezone.utc)
        db = SessionLocal()
        try:
            insights, patterns, actions = self._analyze(db, now)
        finally:
            db.close()
        return InsightsListResponse(
            insights=insights,
            patterns=patterns,
            actions=actions,
            total_count=len(insights),
            generated_at=now,
            analysis_duration_ms=(time.time() - start) * 1000,
        )

    # ------------------------------------------------------------------ analysis

    def _analyze(self, db: Session, now: datetime):
        stats = compute_stats(db, days=14)
        insights: list[InsightResponse] = []
        patterns: list[PatternInfo] = []
        actions: list[ActionRecommendation] = []

        def add(n: int, type_: InsightType, severity: InsightSeverity, title: str, description: str,
                data: dict, suggested: str | None = None, action_type: str | None = None):
            insights.append(InsightResponse(
                id=f"insight-{n:03d}", type=type_, severity=severity, title=title,
                description=description, data=data, suggested_action=suggested,
                action_type=action_type, confidence=1.0, created_at=now,
            ))

        total = stats["total"]
        if total == 0:
            add(1, InsightType.RECOMMENDATION, InsightSeverity.INFO, "No calls yet",
                "No sales calls have been dropped. Insights appear once calls are scored and audited.",
                {"total_calls": 0}, "Drop your first call", "drop_call")
            return insights, patterns, actions

        n = 0

        # 1. Failed calls
        failed = stats["failed"]
        if failed:
            reasons = Counter(
                (c.failure_reason or "No reason recorded")[:90]
                for c in db.query(Call).filter(Call.status == CallStatus.FAILED).all()
            ).most_common(3)
            n += 1
            add(n, InsightType.ALERT, InsightSeverity.HIGH,
                f"{failed} {_plural(failed, 'call')} failed",
                f"{failed} of {total} calls did not complete. Most common reason: {reasons[0][0]}.",
                {"failed": failed, "top_reasons": [{"reason": r, "count": c} for r, c in reasons]},
                "Re-run the failed calls from the Calls Dashboard", "retry_failed")
            actions.append(ActionRecommendation(
                title=f"Re-run {failed} failed {_plural(failed, 'call')}", priority="high",
                estimated_impact=f"Recovers {failed} {_plural(failed, 'call')} with no lead score or audit",
                action_type="retry_failed", action_config={"count": failed}))

        # 2. Stuck calls
        if stats["stuck"]:
            s = stats["stuck"]
            n += 1
            add(n, InsightType.ALERT, InsightSeverity.CRITICAL,
                f"{s} {_plural(s, 'call')} stuck in Sent to Auto",
                f"{s} {_plural(s, 'call is', 'calls are')} waiting on Supervity Auto for longer than the stuck limit "
                "with no full result.",
                {"stuck": s}, "Check the Orchestrator and the Auto workflow run", "check_auto")
            actions.append(ActionRecommendation(
                title="Check the Auto workflow for stuck calls", priority="high",
                estimated_impact=f"Unblocks {s} {_plural(s, 'call')}",
                action_type="check_auto", action_config={"stuck": s}))

        # 3. Rejected requests
        rejected = stats["rejected"]
        if rejected:
            reasons = Counter(
                r.reason[:90] for r in db.query(RejectedRequest).order_by(RejectedRequest.id.desc()).limit(200).all()
            ).most_common(3)
            n += 1
            add(n, InsightType.ANOMALY, InsightSeverity.WARNING,
                f"{rejected} {_plural(rejected, 'request')} rejected at intake",
                f"{rejected} {_plural(rejected, 'request was', 'requests were')} refused before becoming a call. "
                f"Most common reason: {reasons[0][0]}.",
                {"rejected": rejected, "top_reasons": [{"reason": r, "count": c} for r, c in reasons]},
                "Review the rejected requests and fix the source", "review_rejected")
            actions.append(ActionRecommendation(
                title="Review rejected requests", priority="medium",
                estimated_impact="Stops good calls being lost at intake",
                action_type="review_rejected", action_config={"count": rejected}))

        # 4. Hot and cold leads
        bands = {b["band"]: b["count"] for b in stats["bands"]}
        scored = sum(bands.values())
        if scored:
            hot = sum(bands[b] for b in HOT_BANDS)
            cold = sum(bands[b] for b in COLD_BANDS)
            n += 1
            if hot:
                add(n, InsightType.RECOMMENDATION, InsightSeverity.INFO,
                    f"{hot} high-intent {_plural(hot, 'lead')} (band 4-5)",
                    f"{round(hot * 100 / scored)}% of scored calls show high or immediate purchase intent. "
                    "These are the leads to follow up first.",
                    {"hot_leads": hot, "scored_calls": scored, "band_4": bands[4], "band_5": bands[5]},
                    "Prioritise follow-up on band 4 and 5 leads", "follow_up_leads")
                actions.append(ActionRecommendation(
                    title=f"Follow up {hot} band 4-5 {_plural(hot, 'lead')} first", priority="high",
                    estimated_impact="Highest chance of a site visit or booking",
                    action_type="follow_up_leads", action_config={"bands": list(HOT_BANDS)}))
            else:
                add(n, InsightType.TREND, InsightSeverity.WARNING,
                    "No high-intent leads yet",
                    f"None of the {scored} scored calls reached band 4 or 5.",
                    {"scored_calls": scored, "bands": bands},
                    "Review lead sources and call quality", "review_calls")
            if cold and cold * 100 / scored >= 40:
                n += 1
                add(n, InsightType.TREND, InsightSeverity.WARNING,
                    f"{round(cold * 100 / scored)}% of scored calls are band 0-1",
                    f"{cold} of {scored} scored calls had no usable conversation or no purchase intent.",
                    {"cold_leads": cold, "scored_calls": scored, "band_0": bands[0], "band_1": bands[1]},
                    "Check lead quality and call timing", "review_calls")
            patterns.append(PatternInfo(
                name="Lead band mix", frequency="all time", confidence=1.0, sample_size=scored,
                description=", ".join(f"Band {b}: {c}" for b, c in sorted(bands.items()) if c) or "No scored calls"))

        # 5. Audit quality
        audits = [c for c in db.query(Call).all() if c.call_audit is not None]
        if audits:
            avg = stats["avg_audit_percent"]
            checks: dict[str, list[float]] = {}
            for c in audits:
                for ch in c.call_audit.checks or []:
                    try:
                        checks.setdefault(str(ch["name"]), []).append(float(ch["score"]))
                    except (KeyError, TypeError, ValueError):
                        continue
            means = {k: sum(v) / len(v) for k, v in checks.items() if v}
            if means:
                weakest = min(means, key=means.get)
                n += 1
                add(n, InsightType.PATTERN, InsightSeverity.WARNING if means[weakest] < 3.5 else InsightSeverity.INFO,
                    f"Weakest audit area: {weakest}",
                    f"Across {len(audits)} audited {_plural(len(audits), 'call')}, {weakest} averages "
                    f"{means[weakest]:.1f} out of 5. Overall audit score is {avg:.0f}%.",
                    {"check": weakest, "average": round(means[weakest], 1), "audited_calls": len(audits),
                     "all_checks": {k: round(v, 1) for k, v in means.items()}},
                    f"Coach the sales team on {weakest}", "coach_agents")
                patterns.append(PatternInfo(
                    name="Audit score by check", frequency="all time", confidence=1.0, sample_size=len(audits),
                    description=", ".join(f"{k} {v:.1f}/5" for k, v in sorted(means.items(), key=lambda kv: kv[1]))))
                if means[weakest] < 3.5:
                    actions.append(ActionRecommendation(
                        title=f"Coach the team on {weakest}", priority="medium",
                        estimated_impact=f"Lifts the lowest audit check ({means[weakest]:.1f}/5)",
                        action_type="coach_agents", action_config={"check": weakest}))

        # 6. Agent performance
        low_agents = [a for a in stats["agents"]
                      if a["avg_audit_percent"] is not None and a["avg_audit_percent"] < LOW_AUDIT_PERCENT]
        if low_agents:
            worst = min(low_agents, key=lambda a: a["avg_audit_percent"])
            n += 1
            add(n, InsightType.ANOMALY, InsightSeverity.WARNING,
                f"{len(low_agents)} sales {_plural(len(low_agents), 'agent')} below {LOW_AUDIT_PERCENT:.0f}% audit",
                f"{worst['agent_name']} has the lowest average audit score at {worst['avg_audit_percent']:.0f}% "
                f"across {worst['calls']} {_plural(worst['calls'], 'call')}.",
                {"agents": [{"agent_id": a["agent_id"], "agent_name": a["agent_name"],
                             "avg_audit_percent": a["avg_audit_percent"], "calls": a["calls"]} for a in low_agents]},
                f"Review {worst['agent_name']}'s calls", "coach_agents")
            actions.append(ActionRecommendation(
                title=f"Review calls handled by {worst['agent_name']}", priority="medium",
                estimated_impact="Targets the lowest audit performer", action_type="coach_agents",
                action_config={"agent_id": worst["agent_id"]}))
        best = [a for a in stats["agents"] if a["avg_audit_percent"] is not None]
        if len(best) > 1:
            top = max(best, key=lambda a: a["avg_audit_percent"])
            n += 1
            add(n, InsightType.PATTERN, InsightSeverity.INFO,
                f"Top performer: {top['agent_name']}",
                f"{top['agent_name']} leads with a {top['avg_audit_percent']:.0f}% average audit score"
                + (f" and average lead band {top['avg_band']}." if top["avg_band"] is not None else "."),
                {"agent_id": top["agent_id"], "avg_audit_percent": top["avg_audit_percent"],
                 "avg_band": top["avg_band"], "calls": top["calls"]})

        # 7. Volume trend
        per_day = stats["per_day"]
        last7 = sum(d["count"] for d in per_day[-7:])
        prev7 = sum(d["count"] for d in per_day[-14:-7])
        if last7 or prev7:
            change = None if prev7 == 0 else round((last7 - prev7) * 100 / prev7)
            n += 1
            add(n, InsightType.TREND, InsightSeverity.INFO,
                f"{last7} {_plural(last7, 'call')} in the last 7 days",
                (f"That is {'up' if change >= 0 else 'down'} {abs(change)}% on the 7 days before ({prev7})."
                 if change is not None else "There were no calls in the 7 days before."),
                {"last_7_days": last7, "previous_7_days": prev7, "change_percent": change})
            patterns.append(PatternInfo(
                name="Daily call volume", frequency="daily", confidence=1.0, sample_size=sum(d["count"] for d in per_day),
                description=f"Average {sum(d['count'] for d in per_day) / len(per_day):.1f} calls per day over the last 14 days"))

        # 8. Processing health
        done = stats["processed"]
        patterns.append(PatternInfo(
            name="Processing success", frequency="all time", confidence=1.0, sample_size=total,
            description=f"{done} processed, {stats['in_progress']} in progress, {failed} failed of {total} calls "
                        f"({stats['success_rate']}% success)"))

        if not insights:
            add(1, InsightType.TREND, InsightSeverity.INFO,
                "All calls are healthy", f"{total} calls processed with no issues to report.", {"total_calls": total})
        return insights, patterns, actions


# Singleton instance
insights_service = InsightsService()
