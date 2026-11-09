"""
AI Feature Schemas - Pydantic models for AI endpoints

This module provides:
- Chat schemas for conversational AI
- Policy DSL schemas with execution support
- Insights schemas for AI-generated analytics
"""

from datetime import datetime
from typing import Optional, List, Any, Union, Literal, Dict
from pydantic import BaseModel, Field
from enum import Enum


# ============================================================================
# Chat Schemas
# ============================================================================

class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    role: ChatRole
    content: str


class ChatContext(BaseModel):
    """Context passed to AI for better responses."""
    page: Optional[str] = None
    selected_data: Optional[dict] = None
    user_preferences: Optional[dict] = None
    environment: Optional[dict] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    history: Optional[List[ChatMessage]] = Field(default_factory=list)
    context: Optional[ChatContext] = None


class ToolCall(BaseModel):
    id: str
    name: str
    args: dict
    result: Optional[Any] = None


class ChatResponse(BaseModel):
    response: str
    tool_calls: Optional[List[ToolCall]] = None
    suggestions: Optional[List[str]] = None
    confidence: Optional[float] = None


# ============================================================================
# Policy DSL Schemas - Flexible Rule Definition System
# ============================================================================

# Extensible field types - add new fields as needed
PolicyField = Literal[
    # Numeric fields
    "amount",
    "amount_delta",
    "count",
    "percentage",
    "score",
    "risk_score",
    "priority",
    # String fields
    "status",
    "type",
    "category",
    "source",
    "user_role",
    "region",
    # Reference fields
    "user_id",
    "resource_id",
    "merchant_id",
    "transaction_id",
    # Time fields
    "created_days_ago",
    "updated_days_ago",
    "age_days",
    # Custom - allows any field name
    "custom",
]

# Operators for condition evaluation
ConditionOperator = Literal[
    "eq",        # Equals
    "neq",       # Not equals
    "gt",        # Greater than
    "lt",        # Less than
    "gte",       # Greater or equal
    "lte",       # Less or equal
    "contains",  # String contains
    "not_contains",  # String does not contain
    "starts_with",  # String starts with
    "ends_with",    # String ends with
    "between",   # Range check [min, max]
    "in",        # Value in list
    "not_in",    # Value not in list
    "matches",   # Regex match
    "is_null",   # Is null/empty
    "is_not_null",  # Is not null/empty
]

# Action types - extensible for different use cases
ActionType = Literal[
    # Status actions
    "set_status",
    "set_field",
    # Approval workflow
    "auto_approve",
    "auto_reject",
    "flag_review",
    "require_approval",
    # Notifications
    "notify",
    "notify_user",
    "notify_admin",
    "send_email",
    "send_webhook",
    # Escalation
    "escalate",
    "escalate_to_manager",
    # Annotations
    "add_note",
    "add_tag",
    "add_label",
    # Custom actions
    "custom",
]


class PolicyCondition(BaseModel):
    """A single condition to evaluate against a record."""
    
    field: str = Field(
        description="Field to evaluate. Use standard fields or custom field names."
    )
    operator: ConditionOperator = Field(
        default="eq",
        description="Comparison operator"
    )
    value: Union[float, int, str, bool, List[Any], None] = Field(
        description="Value to compare. Use list [min, max] for 'between', list for 'in'."
    )
    # Optional: custom field path for nested objects
    field_path: Optional[str] = Field(
        default=None,
        description="Dot-notation path for nested fields, e.g., 'metadata.category'"
    )


class PolicyAction(BaseModel):
    """An action to execute when conditions match."""
    
    type: str = Field(description="Action type to execute")
    value: Optional[Union[str, int, float, bool, dict]] = Field(
        default=None,
        description="Action value or configuration"
    )
    params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional parameters for the action"
    )


class PolicyDSL(BaseModel):
    """Complete policy definition with conditions and actions.
    
    Conditions use AND logic by default. For OR logic, create separate policies.
    """
    
    conditions: List[PolicyCondition] = Field(
        description="All conditions must match (AND logic)"
    )
    actions: List[PolicyAction] = Field(
        description="Actions to execute when all conditions match"
    )
    # Optional: metadata for complex policies
    match_mode: Literal["all", "any"] = Field(
        default="all",
        description="'all' = AND logic, 'any' = OR logic"
    )
    stop_on_match: bool = Field(
        default=True,
        description="Stop processing other policies after this one matches"
    )
    
    def to_dict(self) -> dict:
        return self.model_dump()


class PolicyType(str, Enum):
    """Policy execution type - determines how the policy is processed."""
    LOGICAL = "logical"  # Converted to structured DSL with conditions/actions
    NATURAL_LANGUAGE = "natural_language"  # Kept as refined natural language for AI interpretation


class PolicyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default="", max_length=1000)
    # Original user input - always preserved
    original_input: str = Field(..., min_length=1, max_length=5000, alias="natural_language")
    # AI-determined or user-selected policy type (optional - AI will decide if not set)
    policy_type: Optional[PolicyType] = Field(default=None, description="Leave empty for AI to decide")
    # For LOGICAL type - structured DSL
    dsl: Optional[PolicyDSL] = None
    # For NATURAL_LANGUAGE type - AI-refined instruction
    refined_instruction: Optional[str] = Field(default=None, max_length=5000)
    # AI-generated summary for card display
    summary: Optional[str] = Field(default=None, max_length=200, description="One-liner summary")
    is_active: bool = True
    priority: int = Field(default=100, ge=0, le=1000, description="Lower = higher priority")
    tags: Optional[List[str]] = Field(default_factory=list)
    # Entity this policy applies to (e.g., vendor name, category)
    entity_name: Optional[str] = Field(default=None, max_length=200)
    
    class Config:
        populate_by_name = True


class PolicyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    original_input: Optional[str] = Field(None, min_length=1, max_length=5000, alias="natural_language")
    policy_type: Optional[PolicyType] = None
    dsl: Optional[PolicyDSL] = None
    refined_instruction: Optional[str] = Field(None, max_length=5000)
    is_active: Optional[bool] = None
    priority: Optional[int] = Field(None, ge=0, le=1000)
    tags: Optional[List[str]] = None
    entity_name: Optional[str] = Field(None, max_length=200)
    
    class Config:
        populate_by_name = True


class PolicyResponse(BaseModel):
    id: str
    name: str
    description: str
    # AI-generated one-liner summary for display
    summary: Optional[str] = None
    # Original user input - what the user typed
    original_input: str = Field(alias="natural_language")
    # Policy type - how AI processes this
    policy_type: PolicyType = PolicyType.LOGICAL
    # For LOGICAL type - structured conditions/actions
    dsl: Optional[PolicyDSL] = None
    # For NATURAL_LANGUAGE type - AI-refined instruction
    refined_instruction: Optional[str] = None
    # The actual instruction AI uses (either from DSL explanation or refined_instruction)
    ai_instruction: Optional[str] = None
    is_active: bool
    priority: int = 100
    tags: List[str] = Field(default_factory=list)
    entity_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # Execution stats
    execution_count: int = 0
    last_executed_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True


class PolicyTranslateRequest(BaseModel):
    natural_language: str = Field(..., min_length=1, max_length=5000)
    # Optional: provide context for better translation
    available_fields: Optional[List[str]] = None
    available_actions: Optional[List[str]] = None


class PolicyTranslateResponse(BaseModel):
    dsl: PolicyDSL
    confidence: float = Field(ge=0, le=1)
    explanation: Optional[str] = None
    warnings: Optional[List[str]] = None


# ============================================================================
# Policy Analysis Schemas - For AI-powered type detection
# ============================================================================

class PolicyAnalyzeRequest(BaseModel):
    """Request to analyze a natural language policy input using AI."""
    input: str = Field(..., min_length=1, max_length=5000, description="Natural language policy description")
    # Optional user preference - AI will honor this if the input allows
    preferred_type: Optional[PolicyType] = Field(default=None, description="Optional user preference for policy type")
    # Optional context for better analysis
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context for analysis")


class PolicyAnalyzeResponse(BaseModel):
    """Response from policy analysis with AI suggestions."""
    suggested_type: PolicyType = Field(description="AI-suggested policy type")
    confidence: float = Field(ge=0, le=1, description="Confidence in the suggestion (0-1)")
    reason: str = Field(description="Human-readable explanation for the type choice")
    suggested_name: str = Field(description="AI-suggested policy name")
    summary: str = Field(description="One-liner summary of what this policy does")
    # For LOGICAL type
    dsl: Optional[PolicyDSL] = Field(default=None, description="Structured DSL if type is logical")
    # For NATURAL_LANGUAGE type  
    refined_instruction: Optional[str] = Field(default=None, description="Refined instruction if type is natural_language")
    # Detected entity
    entity_name: Optional[str] = Field(default=None, description="Detected entity this policy applies to")
    # Suggested tags
    suggested_tags: List[str] = Field(default_factory=list, description="AI-suggested tags")


class PolicyExecutionResult(BaseModel):
    """Result of applying a policy to a record."""
    matched: bool
    policy_id: Optional[str] = None
    policy_name: Optional[str] = None
    actions_applied: List[str] = Field(default_factory=list)
    modified_fields: Dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: float = 0


# ============================================================================
# Insights Schemas
# ============================================================================

class InsightType(str, Enum):
    PATTERN = "pattern"
    ANOMALY = "anomaly"
    RECOMMENDATION = "recommendation"
    TREND = "trend"
    ALERT = "alert"


class InsightSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    WARNING = "warning"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class InsightBase(BaseModel):
    type: InsightType
    severity: InsightSeverity
    title: str
    description: str
    data: Optional[dict] = None
    suggested_action: Optional[str] = None
    action_type: Optional[str] = None  # e.g., "create_policy", "review_data"
    confidence: float = Field(default=0.8, ge=0, le=1)


class InsightResponse(InsightBase):
    id: str
    created_at: datetime
    is_dismissed: bool = False
    is_actioned: bool = False


class PatternInfo(BaseModel):
    """Detected pattern information."""
    name: str
    frequency: str  # e.g., "daily", "weekly", "hourly"
    confidence: float = Field(ge=0, le=1)
    sample_size: int = 0
    description: Optional[str] = None
    data_points: Optional[List[dict]] = None


class ActionRecommendation(BaseModel):
    """Recommended action from insights."""
    title: str
    priority: Literal["high", "medium", "low"]
    estimated_impact: str
    action_type: str
    action_config: Optional[dict] = None


class InsightsListResponse(BaseModel):
    insights: List[InsightResponse]
    patterns: List[PatternInfo]
    actions: List[ActionRecommendation]
    total_count: int
    generated_at: datetime
    analysis_duration_ms: float = 0


class AnalyzeRequest(BaseModel):
    batch_id: Optional[str] = None
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    focus_areas: Optional[List[str]] = None
    include_patterns: bool = True
    include_anomalies: bool = True
    include_recommendations: bool = True
    max_insights: int = Field(default=20, ge=1, le=100)

