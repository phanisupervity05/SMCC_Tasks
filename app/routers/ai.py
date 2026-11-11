"""
Supervity AI Router: the AI Manager chat and AI Insights for the call intelligence Command Center.

Both read the real calls data. There is no demo data.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.security import get_current_user
from app.schemas.ai import (
    ChatRequest, ChatResponse,
    InsightsListResponse, AnalyzeRequest,
)
from app.services.ai import ai_service
from app.services.ai.guard import check_message, rate_limiter, trim_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI"])


# ============================================================================
# Chat Endpoints
# ============================================================================

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Send a message to the AI assistant.
    Supports conversational context and function calling.
    """
    check_message(request.message)
    rate_limiter.check(str((current_user or {}).get("sub") or "anonymous"))
    try:
        response = await ai_service.chat_message(
            message=request.message,
            history=trim_history(request.history),
            context=request.context,
            user_id=current_user.get("sub")
        )
        return response
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process chat message")


# ============================================================================
# Insights Endpoints
# ============================================================================

@router.get("/insights", response_model=InsightsListResponse)
async def list_insights(
    batch_id: Optional[str] = Query(None, description="Filter by batch ID"),
    date_start: Optional[datetime] = Query(None, description="Start date for date range"),
    date_end: Optional[datetime] = Query(None, description="End date for date range"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Insights computed from the real calls: failed/stuck calls, rejected requests,
    high-intent leads, audit quality and agent performance.
    """
    try:
        return await ai_service.generate_insights(
            batch_id=batch_id,
            date_range_start=date_start,
            date_range_end=date_end
        )
    except Exception as e:
        logger.error(f"Insights error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate insights")


@router.post("/insights/analyze", response_model=InsightsListResponse)
async def analyze_data(
    request: AnalyzeRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Trigger AI analysis on specified data.
    """
    try:
        insights = await ai_service.generate_insights(
            batch_id=request.batch_id,
            date_range_start=request.date_range_start,
            date_range_end=request.date_range_end
        )
        return insights
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze data")

