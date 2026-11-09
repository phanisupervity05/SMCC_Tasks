"""
Seed Supervity AI Demo Data

This script populates the Supervity AI features with demonstration data.
The AI processes each natural language input to generate:
- Policy type (logical vs natural_language)
- Name, summary, tags
- DSL for logical policies
- Refined instruction for natural language policies

Run with: python -m scripts.seed_ai_demo
Add --seed flag to actually seed: python -m scripts.seed_ai_demo --seed

Note: For full AI processing, ensure GEMINI_API_KEY is set.
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta, timezone

# Configure logging for CLI output
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# Demo Policy Inputs - ONLY Natural Language
# The AI will process these and determine everything else
# ============================================================================

DEMO_POLICY_INPUTS = [
    # Finance / Accounts Payable
    {
        "input": "If an invoice total is less than $500 and the vendor is in our approved vendor list, automatically approve for payment without requiring manual review",
        "category": "finance",
        "priority": 10,
    },
    {
        "input": "Any transaction or purchase order exceeding $50,000 must be reviewed and approved by the CFO before processing",
        "category": "finance",
        "priority": 5,
    },
    
    # HR / People Operations
    {
        "input": "When a new employee record is created, automatically assign the standard onboarding checklist, notify their manager, and schedule the Day 1 orientation meeting",
        "category": "hr",
        "priority": 15,
    },
    {
        "input": "Automatically approve paid time off requests that are 3 days or less, as long as the employee has enough PTO balance and there are no blackout dates",
        "category": "hr",
        "priority": 20,
    },
    
    # IT / Security
    {
        "input": "If a user logs in from a new device or from a country they have never logged in from before, flag the session for security review and send an alert to the user's email",
        "category": "security",
        "priority": 1,
    },
    
    # Customer Support
    {
        "input": "When a support ticket is created by an enterprise-tier customer or a customer with annual contract value over $100K, automatically escalate to Tier 2 support and set priority to high",
        "category": "support",
        "priority": 8,
    },
    
    # Procurement - Vendor-specific (should be detected as natural_language)
    {
        "input": "For vendor Supervity, skip the standard 3-quote requirement and approve purchases directly since they are our strategic partner",
        "category": "procurement",
        "priority": 25,
    },
    
    # Compliance
    {
        "input": "When a customer submits a data deletion or data export request, automatically create a compliance ticket, set a 30-day deadline, and notify the DPO",
        "category": "compliance",
        "priority": 3,
    },
]


# ============================================================================
# Demo Insights
# ============================================================================

def get_demo_insights():
    """Generate demo insights with current timestamps."""
    now = datetime.now(timezone.utc)
    
    return [
        {
            "id": "demo-insight-001",
            "type": "pattern",
            "severity": "info",
            "title": "Peak Usage Pattern Detected",
            "description": "Most user activity occurs between 9 AM and 11 AM on weekdays. Tuesday shows 23% higher engagement than other days.",
            "data": {
                "peak_hours": "9:00 - 11:00",
                "peak_day": "Tuesday",
                "avg_daily_sessions": 156,
                "tuesday_increase": "23%"
            },
            "suggested_action": "Schedule system maintenance outside peak hours (before 8 AM or after 6 PM)",
            "action_type": "schedule_maintenance",
            "confidence": 0.92,
            "created_at": (now - timedelta(hours=2)).isoformat(),
            "is_demo": True
        },
        {
            "id": "demo-insight-002",
            "type": "anomaly",
            "severity": "warning",
            "title": "Unusual API Activity Spike",
            "description": "API requests spiked 340% at 3:15 AM, significantly outside normal usage patterns. Source traced to 3 IP addresses.",
            "data": {
                "spike_time": "03:15 AM",
                "normal_avg_requests": 45,
                "spike_requests": 198,
                "increase_percent": "340%",
                "source_ips": 3
            },
            "suggested_action": "Review API access logs and verify source IP addresses",
            "action_type": "investigate",
            "confidence": 0.95,
            "created_at": (now - timedelta(hours=6)).isoformat(),
            "is_demo": True
        },
        {
            "id": "demo-insight-003",
            "type": "recommendation",
            "severity": "info",
            "title": "Policy Optimization Opportunity",
            "description": "23 transactions were manually reviewed that match the 'Auto-Approve Low Value' policy criteria. Creating a supporting policy could save ~3.5 hours per week.",
            "data": {
                "manual_reviews": 23,
                "matching_criteria": "amount < $50, status = pending",
                "potential_savings_hours": 3.5,
                "suggested_threshold": "$50"
            },
            "suggested_action": "Create a complementary policy for amounts under $50",
            "action_type": "create_policy",
            "confidence": 0.88,
            "created_at": (now - timedelta(hours=12)).isoformat(),
            "is_demo": True
        },
        {
            "id": "demo-insight-004",
            "type": "trend",
            "severity": "info",
            "title": "Monthly Processing Volume Trend",
            "description": "Processing volume has increased 18% month-over-month for the past 3 months. Current trajectory suggests capacity planning may be needed.",
            "data": {
                "month_1_volume": 1250,
                "month_2_volume": 1475,
                "month_3_volume": 1740,
                "growth_rate": "18%",
                "projected_next_month": 2053
            },
            "suggested_action": "Review infrastructure capacity for projected growth",
            "action_type": "capacity_planning",
            "confidence": 0.85,
            "created_at": (now - timedelta(days=1)).isoformat(),
            "is_demo": True
        },
        {
            "id": "demo-insight-005",
            "type": "anomaly",
            "severity": "warning",  # Use valid severity: info, warning, high
            "title": "Duplicate Transaction Detected",
            "description": "Two transactions with identical amounts, timestamps, and vendor details submitted within 2 seconds. Potential duplicate entry.",
            "data": {
                "transaction_1_id": "TXN-2024-001234",
                "transaction_2_id": "TXN-2024-001235",
                "amount": 4750.00,
                "vendor": "TechSupply Inc",
                "time_difference_seconds": 1.8
            },
            "suggested_action": "Review and potentially void duplicate transaction",
            "action_type": "review_duplicate",
            "confidence": 0.97,
            "created_at": (now - timedelta(minutes=30)).isoformat(),
            "is_demo": True
        },
    ]


# ============================================================================
# Demo Patterns
# ============================================================================

DEMO_PATTERNS = [
    {
        "name": "Peak Business Hours",
        "frequency": "daily",
        "confidence": 0.92,
        "sample_size": 2500,
        "description": "Activity peaks between 9-11 AM and 2-4 PM on weekdays",
        "is_demo": True
    },
    {
        "name": "Weekend Activity Drop",
        "frequency": "weekly",
        "confidence": 0.96,
        "sample_size": 8400,
        "description": "Weekend activity drops to 12% of weekday average",
        "is_demo": True
    },
    {
        "name": "Month-End Surge",
        "frequency": "monthly",
        "confidence": 0.89,
        "sample_size": 15000,
        "description": "Last 3 days of month show 45% higher transaction volume",
        "is_demo": True
    },
    {
        "name": "Vendor Preference Clustering",
        "frequency": "ongoing",
        "confidence": 0.78,
        "sample_size": 1200,
        "description": "Top 5 vendors account for 67% of all transactions",
        "is_demo": True
    },
]


# ============================================================================
# Demo Actions
# ============================================================================

DEMO_ACTIONS = [
    {
        "title": "Create policy for sub-$50 auto-approval",
        "priority": "high",
        "estimated_impact": "Save 3.5 hours/week",
        "action_type": "create_policy",
        "action_config": {
            "template": "auto_approve",
            "threshold": 50,
            "name_suggestion": "Auto-Approve Micro Transactions"
        },
        "is_demo": True
    },
    {
        "title": "Investigate 3 AM API spike",
        "priority": "high",
        "estimated_impact": "Security improvement",
        "action_type": "investigate",
        "action_config": {
            "log_type": "api_access",
            "time_range": "02:00-04:00",
            "focus": "unusual_ips"
        },
        "is_demo": True
    },
    {
        "title": "Review duplicate transaction pair",
        "priority": "critical",
        "estimated_impact": "Prevent $4,750 overpayment",
        "action_type": "review_transaction",
        "action_config": {
            "transaction_ids": ["TXN-2024-001234", "TXN-2024-001235"],
            "action": "void_duplicate"
        },
        "is_demo": True
    },
    {
        "title": "Plan infrastructure scaling",
        "priority": "medium",
        "estimated_impact": "Prevent future bottlenecks",
        "action_type": "capacity_planning",
        "action_config": {
            "timeline": "next_quarter",
            "projected_growth": "18%"
        },
        "is_demo": True
    },
]


# ============================================================================
# AI-Powered Seed Function
# ============================================================================

# Concurrency limit for parallel AI processing (from environment)
AI_CONCURRENCY_LIMIT = int(os.getenv("AI_CONCURRENCY_LIMIT", "4"))


def _generate_ai_instruction(policy_type: str, dsl: dict, refined_instruction: str, natural_language: str) -> str:
    """Generate the AI instruction used by the engine - local helper to avoid circular import."""
    if policy_type == "logical" and dsl:
        conditions = dsl.get("conditions", [])
        actions = dsl.get("actions", [])
        cond_str = " AND ".join([f"{c['field']} {c['operator']} {c['value']}" for c in conditions])
        action_str = ", ".join([a['type'] for a in actions])
        return f"WHEN {cond_str} THEN {action_str}"
    elif refined_instruction:
        return refined_instruction
    else:
        return natural_language


async def _process_single_policy_cli(
    index: int,
    demo: dict,
    now: datetime,
    semaphore: asyncio.Semaphore,
    policy_service
) -> tuple:
    """
    Process a single policy with AI analysis (CLI version).
    Uses a semaphore to limit concurrency.
    
    Returns: (policy_id, policy_data, success, log_lines)
    """
    policy_id = f"demo-policy-{index + 1:03d}"
    natural_language = demo["input"]
    category = demo.get("category", "general")
    priority = demo.get("priority", (index + 1) * 10)
    log_lines = []
    
    async with semaphore:
        try:
            # Let AI analyze the input
            analysis = await policy_service.analyze(natural_language)
            
            # Build DSL dict if available
            dsl_dict = None
            if analysis.dsl:
                dsl_dict = analysis.dsl.model_dump()
            
            # Generate AI instruction
            ai_instruction = _generate_ai_instruction(
                analysis.policy_type,
                dsl_dict,
                analysis.refined_instruction,
                natural_language
            )
            
            # Create policy data
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
            
            type_emoji = "📐" if analysis.policy_type == "logical" else "💬"
            log_lines.append(f"   ✓ [{index + 1}] {type_emoji} {analysis.suggested_name}")
            log_lines.append(f"         Type: {analysis.policy_type} ({analysis.confidence:.0%} confidence)")
            if analysis.entity_name:
                log_lines.append(f"         Entity: {analysis.entity_name}")
            
            return policy_id, policy_data, True, log_lines
            
        except Exception as e:
            log_lines.append(f"   ✗ [{index + 1}] Failed: {e}")
            
            # Create fallback policy
            fallback_data = {
                "id": policy_id,
                "name": f"Policy {index + 1} (Pending AI)",
                "description": "AI analysis failed. Will retry on access.",
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
                "_needs_ai_enrichment": True,
            }
            return policy_id, fallback_data, False, log_lines


async def seed_policies_with_ai():
    """
    Seed demo policies by letting AI process each natural language input.
    Uses PARALLEL processing with asyncio.gather() for faster seeding.
    
    This demonstrates the real AI pipeline:
    - Only natural language is provided
    - AI determines policy type, name, summary, DSL, etc.
    """
    import time
    from app.services.ai import policy_service
    from app.routers.ai import _policies_store
    
    now = datetime.now(timezone.utc)
    total = len(DEMO_POLICY_INPUTS)
    
    logger.info("\n" + "=" * 70)
    logger.info(f"   🚀 SEEDING {total} DEMO POLICIES WITH AI ANALYSIS (PARALLEL)")
    logger.info(f"   Concurrency limit: {AI_CONCURRENCY_LIMIT}")
    logger.info("=" * 70 + "\n")
    
    # Create semaphore to limit concurrent API calls
    semaphore = asyncio.Semaphore(AI_CONCURRENCY_LIMIT)
    
    # Create tasks for all policies
    tasks = [
        _process_single_policy_cli(i, demo, now, semaphore, policy_service)
        for i, demo in enumerate(DEMO_POLICY_INPUTS)
    ]
    
    # Process all policies in parallel (with concurrency limit)
    start_time = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - start_time
    
    # Store results and collect logs
    success_count = 0
    all_logs = []
    
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"  ✗ Task failed with exception: {result}")
        elif isinstance(result, tuple) and len(result) == 4:
            policy_id, policy_data, success, log_lines = result
            _policies_store[policy_id] = policy_data
            all_logs.extend(log_lines)
            if success:
                success_count += 1
    
    # Print all logs in order
    for line in all_logs:
        logger.info(line)
    
    logger.info("")
    logger.info("-" * 70)
    logger.info(f"✅ Seeded {success_count}/{total} policies with AI analysis in {elapsed:.2f}s")
    logger.info(f"   Average: {elapsed/total:.2f}s per policy (sequential would be ~{elapsed/total * total:.1f}s)")
    logger.info("=" * 70 + "\n")
    
    return success_count


def seed_policies_sync():
    """
    Synchronous fallback - creates placeholder policies.
    These will be enriched by AI when accessed.
    """
    from app.routers.ai import _policies_store
    
    now = datetime.now(timezone.utc)
    
    logger.info("\n📝 Creating placeholder demo policies (AI will enrich on first access)...\n")
    
    for i, demo in enumerate(DEMO_POLICY_INPUTS):
        policy_id = f"demo-policy-{i + 1:03d}"
        natural_language = demo["input"]
        
        _policies_store[policy_id] = {
            "id": policy_id,
            "name": f"Demo Policy {i + 1} (Processing...)",
            "description": "This policy will be analyzed by AI on first access.",
            "summary": natural_language[:100] + "..." if len(natural_language) > 100 else natural_language,
            "natural_language": natural_language,
            "policy_type": "natural_language",
            "dsl": None,
            "refined_instruction": natural_language,
            "ai_instruction": natural_language,
            "entity_name": None,
            "is_active": True,
            "priority": demo["priority"],
            "tags": [demo["category"], "demo", "pending-analysis"],
            "created_at": now - timedelta(days=30 - i * 3),
            "updated_at": now,
            "execution_count": 0,
            "last_executed_at": None,
            "_needs_ai_enrichment": True,
        }
        
        logger.info(f"   📝 {policy_id}: {natural_language[:50]}...")
    
    logger.info(f"\n✓ Created {len(DEMO_POLICY_INPUTS)} placeholder policies\n")
    return len(DEMO_POLICY_INPUTS)


# ============================================================================
# Summary Functions
# ============================================================================

def get_seed_data():
    """Get all seed data as a dictionary."""
    return {
        "policy_inputs": DEMO_POLICY_INPUTS,
        "insights": get_demo_insights(),
        "patterns": DEMO_PATTERNS,
        "actions": DEMO_ACTIONS,
        "metadata": {
            "seeded_at": datetime.now(timezone.utc).isoformat(),
            "is_demo_data": True,
            "note": "Policies are processed by AI from natural language inputs."
        }
    }


def log_seed_summary():
    """Log a summary of what will be seeded."""
    logger.info("\n" + "=" * 70)
    logger.info("   SUPERVITY AI DEMO DATA - Natural Language → AI Processing")
    logger.info("=" * 70)
    
    logger.info(f"\n📋 Policy Inputs: {len(DEMO_POLICY_INPUTS)}")
    logger.info("   (AI will determine type, name, summary, DSL/instruction)\n")
    
    categories = {}
    for demo in DEMO_POLICY_INPUTS:
        cat = demo["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(demo["input"][:60] + "...")
    
    category_emojis = {
        "finance": "💰",
        "hr": "👥",
        "security": "🔒",
        "support": "🎧",
        "procurement": "📦",
        "compliance": "⚖️",
    }
    
    for cat, inputs in categories.items():
        emoji = category_emojis.get(cat, "📌")
        logger.info(f"   {emoji} {cat.upper()} ({len(inputs)} policies)")
        for inp in inputs:
            logger.info(f"      • {inp}")
        logger.info("")
    
    insights = get_demo_insights()
    logger.info(f"💡 Insights: {len(insights)}")
    for i in insights:
        severity_icon = {"high": "🔴", "warning": "🟡", "info": "🔵"}.get(i["severity"], "⚪")
        logger.info(f"   {severity_icon} {i['title']} ({i['type']})")
    
    logger.info(f"\n📊 Patterns: {len(DEMO_PATTERNS)}")
    for p in DEMO_PATTERNS:
        logger.info(f"   • {p['name']} - {p['frequency']}")
    
    logger.info(f"\n⚡ Recommended Actions: {len(DEMO_ACTIONS)}")
    for a in DEMO_ACTIONS:
        priority_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(a["priority"], "⚪")
        logger.info(f"   {priority_icon} {a['title']}")
    
    logger.info("\n" + "-" * 70)
    logger.info("ℹ️  Run with --seed flag to process with AI")
    logger.info("   Example: python -m scripts.seed_ai_demo --seed")
    logger.info("=" * 70 + "\n")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    if "--seed" in sys.argv:
        # Actually seed with AI processing
        try:
            # Check if we can import the router
            from app.routers.ai import _policies_store
            
            # Run async seeding
            count = asyncio.run(seed_policies_with_ai())
            logger.info(f"🎉 Successfully seeded {count} policies!")
            
        except ImportError as e:
            logger.error(f"❌ Import error: {e}")
            logger.error("   Make sure you're running from the project root.")
            logger.error("   Example: python -m scripts.seed_ai_demo --seed")
            sys.exit(1)
        except Exception as e:
            logger.error(f"❌ Error during seeding: {e}")
            sys.exit(1)
    
    elif "--sync" in sys.argv:
        # Sync fallback (no AI processing)
        try:
            from app.routers.ai import _policies_store
            count = seed_policies_sync()
            logger.info(f"📝 Created {count} placeholder policies")
        except ImportError as e:
            logger.error(f"❌ Import error: {e}")
            sys.exit(1)
    
    else:
        # Just show summary
        log_seed_summary()
