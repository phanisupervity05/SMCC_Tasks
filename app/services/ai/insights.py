"""
Supervity AI Insights Service - AI-powered data analysis and insights generation

Generates insights, patterns, and recommendations from data using Supervity AI.
"""

import uuid
import time
import logging
from typing import Optional
from datetime import datetime

from app.schemas.ai import (
    InsightsListResponse, InsightResponse, InsightType, InsightSeverity,
    PatternInfo, ActionRecommendation
)
from .gemini import GeminiService

logger = logging.getLogger(__name__)


class InsightsService(GeminiService):
    """
    Service for AI-generated insights.
    Analyzes data to find patterns, anomalies, and recommendations.
    """
    
    async def generate(
        self,
        batch_id: Optional[str] = None,
        date_range_start: Optional[datetime] = None,
        date_range_end: Optional[datetime] = None
    ) -> InsightsListResponse:
        """Generate AI insights from data analysis."""
        start_time = time.time()
        now = datetime.utcnow()
        
        # In production, this would analyze real data
        # For now, return mock insights that demonstrate the system
        insights = self._generate_mock_insights(now)
        patterns = self._generate_mock_patterns()
        actions = self._generate_mock_actions()
        
        return InsightsListResponse(
            insights=insights,
            patterns=[p.model_dump() for p in patterns],
            actions=[a.model_dump() for a in actions],
            total_count=len(insights),
            generated_at=now,
            analysis_duration_ms=(time.time() - start_time) * 1000
        )
    
    def _generate_mock_insights(self, now: datetime) -> list[InsightResponse]:
        """Generate demo insights for demonstration. Labeled as [DEMO]."""
        return [
            InsightResponse(
                id="demo-insight-001",
                type=InsightType.PATTERN,
                severity=InsightSeverity.INFO,
                title="Peak Usage Pattern Detected [DEMO]",
                description="Most user activity occurs between 9 AM and 11 AM on weekdays, with Tuesday showing the highest engagement.",
                data={"peak_hour": 10, "peak_day": "Tuesday", "avg_sessions": 45, "is_demo": True},
                suggested_action="Schedule maintenance outside peak hours",
                action_type="schedule_maintenance",
                confidence=0.89,
                created_at=now
            ),
            InsightResponse(
                id="demo-insight-002",
                type=InsightType.ANOMALY,
                severity=InsightSeverity.WARNING,
                title="Unusual API Activity Detected [DEMO]",
                description="API requests spiked 300% at 3 AM, which is significantly outside normal usage patterns.",
                data={"spike_time": "03:00", "normal_avg": 50, "spike_count": 200, "source_ips": 3, "is_demo": True},
                suggested_action="Investigate the source of unusual activity",
                action_type="investigate",
                confidence=0.95,
                created_at=now
            ),
            InsightResponse(
                id="demo-insight-003",
                type=InsightType.RECOMMENDATION,
                severity=InsightSeverity.INFO,
                title="Policy Optimization Opportunity [DEMO]",
                description="15 transactions were manually reviewed that match existing auto-approval criteria. Creating a policy could save ~2.5 hours per week.",
                data={"manual_reviews": 15, "potential_savings_hours": 2.5, "matching_pattern": "amount < $50", "is_demo": True},
                suggested_action="Create auto-approval policy for low-value transactions",
                action_type="create_policy",
                confidence=0.87,
                created_at=now
            ),
            InsightResponse(
                id="demo-insight-004",
                type=InsightType.ANOMALY,
                severity=InsightSeverity.HIGH,
                title="Duplicate Transaction Detected [DEMO]",
                description="Two transactions with identical amounts and vendor details submitted within 2 seconds. Potential duplicate entry requiring review.",
                data={"transaction_ids": ["TXN-001234", "TXN-001235"], "amount": 4750.00, "vendor": "TechSupply Inc", "is_demo": True},
                suggested_action="Review and void duplicate transaction",
                action_type="review_duplicate",
                confidence=0.97,
                created_at=now
            ),
        ]
    
    def _generate_mock_patterns(self) -> list[PatternInfo]:
        """Generate demo patterns. Labeled as [DEMO]."""
        return [
            PatternInfo(
                name="Peak Usage Hours [DEMO]",
                frequency="daily",
                confidence=0.89,
                sample_size=1500,
                description="9 AM - 11 AM shows 3x normal activity"
            ),
            PatternInfo(
                name="Weekend Activity Dip [DEMO]",
                frequency="weekly",
                confidence=0.95,
                sample_size=4200,
                description="Weekend activity drops to 15% of weekday average"
            ),
            PatternInfo(
                name="Month-End Surge [DEMO]",
                frequency="monthly",
                confidence=0.78,
                sample_size=12000,
                description="Last 3 days of month show 45% higher volume"
            ),
        ]
    
    def _generate_mock_actions(self) -> list[ActionRecommendation]:
        """Generate demo action recommendations. Labeled as [DEMO]."""
        return [
            ActionRecommendation(
                title="Create policy for sub-$50 auto-approval [DEMO]",
                priority="high",
                estimated_impact="Save 3.5 hours/week",
                action_type="create_policy",
                action_config={"template": "auto_approve_low_value", "is_demo": True}
            ),
            ActionRecommendation(
                title="Investigate 3 AM API spike [DEMO]",
                priority="high",
                estimated_impact="Security improvement",
                action_type="investigate",
                action_config={"time_range": "02:00-04:00", "is_demo": True}
            ),
            ActionRecommendation(
                title="Review duplicate transaction pair [DEMO]",
                priority="high",
                estimated_impact="Prevent $4,750 overpayment",
                action_type="review_transaction",
                action_config={"transaction_ids": ["TXN-001234", "TXN-001235"], "is_demo": True}
            ),
        ]


# Singleton instance
insights_service = InsightsService()

