"""
Supervity AI Router - API endpoints for AI features (chat, policies, insights)

Note: Demo data is automatically loaded on startup.
Configure your AI API key for full Supervity AI functionality.
"""

import asyncio
import logging
import os
import time
from typing import Optional, List
from datetime import datetime, timedelta, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.security import get_current_user
from app.schemas.ai import (
    ChatRequest, ChatResponse,
    PolicyCreate, PolicyUpdate, PolicyResponse, PolicyDSL, PolicyType,
    PolicyTranslateRequest, PolicyTranslateResponse,
    PolicyAnalyzeRequest, PolicyAnalyzeResponse,
    InsightsListResponse, AnalyzeRequest
)
from app.services.ai import ai_service, policy_service
from app.services.rule_architect import rule_architect, prompt_optimizer

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
    try:
        response = await ai_service.chat_message(
            message=request.message,
            history=request.history,
            context=request.context,
            user_id=current_user.get("sub")
        )
        return response
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process chat message")


# ============================================================================
# Policy Endpoints
# ============================================================================

# In-memory storage for demo (replace with database in production)
_policies_store: dict = {}
_demo_initialized: bool = False


# ============================================================================
# Import ALL demo data from centralized seed script
# ============================================================================
try:
    from scripts.seed_ai_demo import (
        DEMO_POLICY_INPUTS,
        DEMO_PATTERNS,
        DEMO_ACTIONS,
        get_demo_insights,
    )
    _SEED_SCRIPT_AVAILABLE = True
except ImportError:
    _SEED_SCRIPT_AVAILABLE = False
    # Minimal fallback only if script not available
    DEMO_POLICY_INPUTS = [
        {"input": "If an invoice is less than $500 from an approved vendor, auto-approve payment", "category": "finance", "priority": 10},
        {"input": "Transactions over $50,000 require CFO approval", "category": "finance", "priority": 5},
    ]
    DEMO_PATTERNS = []
    DEMO_ACTIONS = []
    def get_demo_insights():
        return []


# Concurrency limit for parallel AI processing (from environment)
AI_CONCURRENCY_LIMIT = int(os.getenv("AI_CONCURRENCY_LIMIT", "4"))


async def _process_single_policy(
    index: int,
    demo: dict,
    now: datetime,
    semaphore: asyncio.Semaphore
) -> tuple[str, dict]:
    """
    Process a single policy with AI analysis.
    Uses a semaphore to limit concurrency.
    
    Returns: (policy_id, policy_data)
    """
    policy_id = f"demo-policy-{index + 1:03d}"
    
    # Support both formats: dict with 'input' key or plain string
    if isinstance(demo, dict):
        natural_language = demo.get("input", str(demo))
        category = demo.get("category", "general")
        priority = demo.get("priority", (index + 1) * 10)
    else:
        natural_language = str(demo)
        category = "general"
        priority = (index + 1) * 10
    
    async with semaphore:
        try:
            # Let AI analyze the input - this is the real pipeline
            analysis = await policy_service.analyze(natural_language)
            
            # Build the policy from AI analysis
            dsl_dict = None
            if analysis.dsl:
                dsl_dict = analysis.dsl.model_dump()
            
            ai_instruction = _generate_ai_instruction(
                analysis.policy_type,
                dsl_dict,
                analysis.refined_instruction,
                natural_language
            )
            
            policy_data = {
                "id": policy_id,
                "name": analysis.suggested_name,
                "description": f"AI-generated from natural language. Category: {category}. [DEMO]",
                "summary": analysis.summary,
                "natural_language": natural_language,
                "policy_type": analysis.policy_type,
                "dsl": dsl_dict,
                "refined_instruction": analysis.refined_instruction,
                "ai_instruction": ai_instruction,
                "entity_name": analysis.entity_name,
                "is_active": True,
                "priority": priority,
                "tags": list(set((analysis.suggested_tags or []) + [category, "demo", "ai-generated"])),
                "created_at": now - timedelta(days=30 - index * 3),
                "updated_at": now - timedelta(hours=index * 2),
                "execution_count": (8 - index) * 15 if index < 8 else 10,
                "last_executed_at": now - timedelta(hours=index + 1),
            }
            
            logger.info(f"  ✓ [{index + 1}] {analysis.suggested_name} ({analysis.policy_type}, {analysis.confidence:.0%})")
            return policy_id, policy_data
            
        except Exception as e:
            logger.error(f"  ✗ [{index + 1}] Failed: {e}")
            # Create a fallback policy without AI
            fallback_data = {
                "id": policy_id,
                "name": f"Policy {index + 1}",
                "description": f"Demo policy - {category} (AI unavailable)",
                "summary": natural_language[:100],
                "natural_language": natural_language,
                "policy_type": "natural_language",
                "dsl": None,
                "refined_instruction": natural_language,
                "ai_instruction": natural_language,
                "entity_name": None,
                "is_active": True,
                "priority": priority,
                "tags": [category, "demo", "needs-review"],
                "created_at": now - timedelta(days=30 - index * 3),
                "updated_at": now,
                "execution_count": 0,
                "last_executed_at": None,
            }
            return policy_id, fallback_data


async def seed_demo_policies():
    """
    Seed demo policies by letting AI process each natural language input.
    Uses PARALLEL processing with asyncio.gather() for faster seeding.
    
    This demonstrates the real AI pipeline - only natural language is provided,
    and the AI determines:
    - Policy type (logical vs natural_language)
    - Name, summary, tags
    - DSL for logical policies
    - Refined instruction for natural language policies
    """
    global _policies_store, _demo_initialized
    
    if _demo_initialized:
        return
    
    now = datetime.now(timezone.utc)
    total = len(DEMO_POLICY_INPUTS)
    logger.info(f"🚀 Seeding {total} demo policies with AI analysis (parallel, max {AI_CONCURRENCY_LIMIT} concurrent)...")
    
    # Create semaphore to limit concurrent API calls
    semaphore = asyncio.Semaphore(AI_CONCURRENCY_LIMIT)
    
    # Create tasks for all policies
    tasks = [
        _process_single_policy(i, demo, now, semaphore)
        for i, demo in enumerate(DEMO_POLICY_INPUTS)
    ]
    
    # Process all policies in parallel (with concurrency limit)
    start_time = time.time()
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    elapsed = time.time() - start_time
    
    # Store results
    success_count = 0
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"  ✗ Task failed with exception: {result}")
        elif isinstance(result, tuple) and len(result) == 2:
            policy_id, policy_data = result
            _policies_store[policy_id] = policy_data
            success_count += 1
    
    _demo_initialized = True
    logger.info(f"✅ Seeded {success_count}/{total} demo policies in {elapsed:.2f}s (parallel processing)")


def _sync_init_demo_policies():
    """
    Synchronous fallback for demo initialization (when async isn't available).
    Creates minimal placeholder policies that will be enriched on first access.
    """
    global _policies_store, _demo_initialized
    
    if _demo_initialized or _policies_store:
        return
    
    now = datetime.now(timezone.utc)
    logger.info("📝 Creating placeholder demo policies (will be enriched by AI on first access)...")
    
    for i, demo in enumerate(DEMO_POLICY_INPUTS):
        policy_id = f"demo-policy-{i + 1:03d}"
        
        # Support both formats: dict with 'input' key or plain string
        if isinstance(demo, dict):
            natural_language = demo.get("input", str(demo))
            category = demo.get("category", "general")
            priority = demo.get("priority", (i + 1) * 10)
        else:
            natural_language = str(demo)
            category = "general"
            priority = (i + 1) * 10
        
        summary = natural_language[:100] + "..." if len(natural_language) > 100 else natural_language
        
        # Create minimal placeholders - marked for AI enrichment
        _policies_store[policy_id] = {
            "id": policy_id,
            "name": f"Demo Policy {i + 1} (Processing...)",
            "description": f"Pending AI analysis. Category: {category}",
            "summary": summary,
            "natural_language": natural_language,
            "policy_type": "natural_language",  # Default
            "dsl": None,
            "refined_instruction": natural_language,
            "ai_instruction": natural_language,
            "entity_name": None,
            "is_active": True,
            "priority": priority,
            "tags": [category, "demo", "pending-analysis"],
            "created_at": now - timedelta(days=30 - i * 3),
            "updated_at": now,
            "execution_count": 0,
            "last_executed_at": None,
            "_needs_ai_enrichment": True,  # Flag for lazy enrichment
        }
    
    logger.info(f"📝 Created {len(_policies_store)} placeholder policies")


# Initialize with sync fallback on module load
try:
    _sync_init_demo_policies()
except Exception as e:
    logger.error(f"Error during demo policy initialization: {e}")


@router.post("/policies/seed-demo")
async def seed_demo_policies_endpoint(
    current_user: dict = Depends(get_current_user)
):
    """
    Manually trigger AI-powered demo policy seeding.
    
    This processes all demo policy inputs through the AI pipeline,
    generating real type detection, DSL, summaries, etc.
    """
    global _demo_initialized
    
    # Reset and re-seed
    _demo_initialized = False
    await seed_demo_policies()
    
    return {
        "message": f"Seeded {len(_policies_store)} demo policies with AI analysis",
        "policies": [
            {"id": p["id"], "name": p["name"], "type": p["policy_type"]}
            for p in _policies_store.values()
        ]
    }


async def _enrich_policy_with_ai(policy_id: str):
    """Enrich a single policy with AI analysis if needed."""
    if policy_id not in _policies_store:
        return
    
    policy = _policies_store[policy_id]
    
    # Check if needs enrichment
    if not policy.get("_needs_ai_enrichment"):
        return
    
    try:
        analysis = await policy_service.analyze(policy["natural_language"])
        
        # Update with AI analysis
        dsl_dict = analysis.dsl.model_dump() if analysis.dsl else None
        
        policy.update({
            "name": analysis.suggested_name,
            "summary": analysis.summary,
            "policy_type": analysis.policy_type,
            "dsl": dsl_dict,
            "refined_instruction": analysis.refined_instruction,
            "ai_instruction": _generate_ai_instruction(
                analysis.policy_type, dsl_dict, analysis.refined_instruction, policy["natural_language"]
            ),
            "entity_name": analysis.entity_name,
            "tags": list(set((analysis.suggested_tags or []) + ["demo", "ai-generated"])),
            "description": f"AI-analyzed policy. Type: {analysis.policy_type}, Confidence: {analysis.confidence:.0%}",
            "_needs_ai_enrichment": False,
            "updated_at": datetime.now(timezone.utc),
        })
        
        _policies_store[policy_id] = policy
        logger.info(f"  ✓ Enriched {policy_id} with AI: {analysis.suggested_name}")
        
    except Exception as e:
        logger.warning(f"  ✗ Failed to enrich {policy_id}: {e}")
        # Remove the flag so we don't keep retrying
        policy["_needs_ai_enrichment"] = False
        policy["tags"] = list(set(policy.get("tags", []) + ["enrichment-failed"]))


@router.get("/policies", response_model=List[PolicyResponse])
async def list_policies(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all AI policies for the current user/organization.
    
    On first access, policies that haven't been AI-analyzed yet will be
    enriched IN PARALLEL using asyncio.gather.
    """
    # Check if any policies need AI enrichment
    needs_enrichment = [
        pid for pid, p in _policies_store.items()
        if p.get("_needs_ai_enrichment")
    ]
    
    if needs_enrichment:
        # Enrich ALL policies in PARALLEL (respects AI_CONCURRENCY_LIMIT via semaphore)
        start_time = time.time()
        logger.info(f"🔄 Enriching {len(needs_enrichment)} policies with AI (parallel)...")
        
        # Create semaphore and tasks for parallel enrichment
        semaphore = asyncio.Semaphore(AI_CONCURRENCY_LIMIT)
        
        async def enrich_with_semaphore(pid: str):
            async with semaphore:
                await _enrich_policy_with_ai(pid)
        
        await asyncio.gather(*[enrich_with_semaphore(pid) for pid in needs_enrichment])
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Enriched {len(needs_enrichment)} policies in {elapsed:.2f}s (parallel)")
    
    policies = list(_policies_store.values())
    
    # Remove internal flags before returning
    for p in policies:
        p.pop("_needs_ai_enrichment", None)
    
    if is_active is not None:
        policies = [p for p in policies if p["is_active"] == is_active]
    
    return [PolicyResponse(**p) for p in policies]


def _generate_ai_instruction(policy_type: str, dsl: Optional[dict], refined_instruction: Optional[str], natural_language: str) -> str:
    """Generate the AI instruction based on policy type."""
    if policy_type == "natural_language":
        return refined_instruction or natural_language
    
    if dsl and dsl.get("conditions"):
        # Generate a readable instruction from DSL
        conditions = dsl.get("conditions", [])
        actions = dsl.get("actions", [])
        match_mode = dsl.get("match_mode", "all")
        
        cond_strs = []
        for c in conditions:
            field = c.get("field", "?")
            op = c.get("operator", "eq")
            val = c.get("value")
            op_map = {"eq": "=", "neq": "!=", "gt": ">", "lt": "<", "gte": ">=", "lte": "<=", "in": "IN", "contains": "CONTAINS"}
            op_str = op_map.get(op, op)
            cond_strs.append(f"{field} {op_str} {val}")
        
        joiner = " AND " if match_mode == "all" else " OR "
        condition_text = joiner.join(cond_strs)
        
        action_strs = [a.get("type", "?") + (f"('{a.get('value')}')" if a.get("value") else "") for a in actions]
        action_text = ", ".join(action_strs)
        
        return f"IF {condition_text} THEN {action_text}"
    
    return natural_language


@router.post("/policies", response_model=PolicyResponse, status_code=201)
async def create_policy(
    policy: PolicyCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new AI policy.
    
    Uses AI to intelligently determine the best representation:
    - LOGICAL (DSL): Structured conditions and actions for discrete rules
    - NATURAL_LANGUAGE: AI-refined instruction for complex/contextual rules
    
    All analysis is fully AI-powered - no keyword detection.
    """
    policy_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    # Get the original input (handles both alias and direct field)
    original_input = policy.original_input
    
    # If user explicitly provided DSL, use logical type
    if policy.dsl:
        policy_type = "logical"
        dsl = policy.dsl
        dsl_dict = dsl.model_dump()
        refined_instruction = policy.refined_instruction
        summary = policy.summary if hasattr(policy, 'summary') and policy.summary else None
        entity_name = policy.entity_name
        tags = policy.tags or []
    # If user explicitly set a type, honor it
    elif policy.policy_type:
        policy_type = policy.policy_type.value
        dsl = None
        dsl_dict = None
        refined_instruction = policy.refined_instruction or original_input
        summary = policy.summary if hasattr(policy, 'summary') and policy.summary else None
        entity_name = policy.entity_name
        tags = policy.tags or []
        
        # For logical type without DSL, let AI generate it
        if policy_type == "logical":
            try:
                translation = await policy_service.translate(original_input)
                dsl = translation.dsl
                dsl_dict = dsl.model_dump() if dsl else None
            except Exception as e:
                logger.warning(f"DSL translation failed: {e}")
    else:
        # === FULL AI ANALYSIS ===
        # No explicit type or DSL - let AI decide everything
        user_preferred = policy.policy_type.value if policy.policy_type else None
        
        analysis = await policy_service.analyze(
            natural_language=original_input,
            user_preferred_type=user_preferred
        )
        
        policy_type = analysis.policy_type
        dsl = analysis.dsl
        dsl_dict = dsl.model_dump() if dsl else None
        refined_instruction = analysis.refined_instruction or original_input
        summary = analysis.summary
        entity_name = analysis.entity_name or policy.entity_name
        tags = analysis.suggested_tags or policy.tags or []
        
        # Log the AI decision
        logger.info(f"AI analysis: type={policy_type}, confidence={analysis.confidence:.2f}, reason='{analysis.reason}'")
        
        if analysis.warnings:
            for warning in analysis.warnings:
                logger.warning(f"Policy analysis warning: {warning}")
    
    # For natural language type, ensure we have refined instruction
    if policy_type == "natural_language" and not refined_instruction:
        try:
            refined_instruction = await policy_service.refine_instruction(original_input)
        except Exception as e:
            logger.warning(f"Instruction refinement failed: {e}")
            refined_instruction = original_input
    
    # Generate summary if not provided by AI or user
    if not summary:
        try:
            summary = await policy_service.generate_summary(original_input)
        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")
            summary = original_input[:97] + "..." if len(original_input) > 100 else original_input
    
    # Generate the AI instruction (for execution engine)
    ai_instruction = _generate_ai_instruction(policy_type, dsl_dict, refined_instruction, original_input)
    
    policy_data = {
        "id": policy_id,
        "name": policy.name,
        "description": policy.description or "",
        "summary": summary,
        "natural_language": original_input,
        "policy_type": policy_type,
        "dsl": dsl_dict,
        "refined_instruction": refined_instruction,
        "ai_instruction": ai_instruction,
        "entity_name": entity_name,
        "is_active": policy.is_active,
        "priority": policy.priority,
        "tags": tags,
        "created_at": now,
        "updated_at": now,
        "execution_count": 0,
        "last_executed_at": None
    }
    
    _policies_store[policy_id] = policy_data
    
    return PolicyResponse(**policy_data)


@router.get("/policies/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific policy by ID.
    """
    if policy_id not in _policies_store:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    return PolicyResponse(**_policies_store[policy_id])


@router.patch("/policies/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: str,
    policy: PolicyUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update an existing policy.
    """
    if policy_id not in _policies_store:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    existing = _policies_store[policy_id]
    update_data = policy.model_dump(exclude_unset=True)
    
    # Handle DSL update
    if "dsl" in update_data and update_data["dsl"]:
        update_data["dsl"] = update_data["dsl"].model_dump() if hasattr(update_data["dsl"], 'model_dump') else update_data["dsl"]
    
    existing.update(update_data)
    existing["updated_at"] = datetime.now(timezone.utc)
    
    _policies_store[policy_id] = existing
    
    return PolicyResponse(**existing)


@router.delete("/policies/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a policy.
    """
    if policy_id not in _policies_store:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    del _policies_store[policy_id]


@router.post("/policies/translate", response_model=PolicyTranslateResponse)
async def translate_policy(
    request: PolicyTranslateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Translate natural language policy description to structured DSL.
    """
    try:
        result = await ai_service.translate_policy(request.natural_language)
        return result
    except Exception as e:
        logger.error(f"Translation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to translate policy")


@router.post("/policies/analyze-input", response_model=PolicyAnalyzeResponse)
async def analyze_policy_input(
    request: PolicyAnalyzeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Analyze a natural language policy input using AI to determine the best representation.
    
    This is the first step in the guided policy creation wizard.
    ALL ANALYSIS IS AI-POWERED - no keyword detection or hardcoded rules.
    
    Returns:
    - suggested_type: Whether to use 'logical' (DSL) or 'natural_language'
    - confidence: How confident the AI is in the suggestion (0-1)
    - reason: AI-generated explanation of why this type was chosen
    - suggested_name: AI-generated policy name
    - summary: AI-generated one-liner summary for card display
    - dsl: If logical, the AI-generated structured conditions/actions
    - refined_instruction: AI-refined instruction for natural language policies
    - entity_name: AI-detected entity (vendor, customer, etc.) if any
    - suggested_tags: AI-recommended tags
    """
    input_text = request.input.strip()
    
    if not input_text:
        raise HTTPException(status_code=400, detail="Policy input cannot be empty")
    
    # Get optional user preference from request
    user_preferred_type = None
    if hasattr(request, 'preferred_type') and request.preferred_type:
        user_preferred_type = request.preferred_type
    
    # === FULL AI ANALYSIS ===
    # The AI will analyze the input and determine:
    # - Best policy type (logical vs natural_language)
    # - Appropriate name and summary
    # - DSL for logical policies
    # - Refined instruction for natural language policies
    # - Entity names and tags
    
    try:
        analysis = await policy_service.analyze(
            natural_language=input_text,
            user_preferred_type=user_preferred_type
        )
        
        logger.info(f"AI policy analysis: type={analysis.policy_type}, confidence={analysis.confidence:.2f}")
        
        return PolicyAnalyzeResponse(
            suggested_type=PolicyType(analysis.policy_type),
            confidence=analysis.confidence,
            reason=analysis.reason,
            suggested_name=analysis.suggested_name,
            summary=analysis.summary,
            dsl=analysis.dsl,
            refined_instruction=analysis.refined_instruction,
            entity_name=analysis.entity_name,
            suggested_tags=analysis.suggested_tags or []
        )
        
    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        # Return a minimal valid response on error
        return PolicyAnalyzeResponse(
            suggested_type=PolicyType.NATURAL_LANGUAGE,
            confidence=0.3,
            reason=f"AI analysis encountered an error: {str(e)}. Using fallback.",
            suggested_name="New Policy",
            summary=input_text[:97] + "..." if len(input_text) > 100 else input_text,
            dsl=None,
            refined_instruction=input_text,
            entity_name=None,
            suggested_tags=["needs-review"]
        )


@router.post("/policies/analyze")
async def analyze_policy(
    request: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze a new policy for conflicts and generate refined instructions.
    
    Returns:
    - conflicts: Rules that contradict the new rule
    - overrides: BASE rules that will be overridden by this INSTRUCTION
    - clarifications: Questions to make the rule more precise
    - suggested_instructions: AI-refined versions of the rule
    - refined_instruction: The best refined instruction
    """
    try:
        natural_language = request.get("natural_language", "")
        policy_type = request.get("policy_type", "BASE")
        entity_name = request.get("entity_name")
        
        # Get existing rules for comparison
        existing_rules = [
            {
                "id": pid,
                "name": p.get("name"),
                "natural_language": p.get("natural_language"),
                "policy_type": p.get("policy_type", "BASE"),
                "entity_name": p.get("entity_name"),
                "is_active": p.get("is_active", True)
            }
            for pid, p in _policies_store.items()
        ]
        
        # Analyze with Rule Architect
        analysis = await rule_architect.analyze_rule(
            new_rule={
                "natural_language": natural_language,
                "policy_type": policy_type,
                "entity_name": entity_name
            },
            existing_rules=existing_rules,
            entity_name=entity_name
        )
        
        return analysis.to_dict()
        
    except Exception as e:
        logger.error(f"Policy analysis error: {e}")
        # Return a minimal valid response on error
        refined = await prompt_optimizer.refine(request.get("natural_language", ""))
        return {
            "conflicts": [],
            "overrides": [],
            "clarifications": [],
            "suggested_instructions": [refined],
            "refined_instruction": refined,
            "is_valid": True,
            "warnings": [str(e)]
        }


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

