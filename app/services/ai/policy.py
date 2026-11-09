"""
Policy Service - AI-powered policy analysis and translation

All policy intelligence is powered by AI with structured outputs.
Uses Pydantic schemas with Gemini's response_json_schema for guaranteed type-safe responses.
"""

import json
import logging
from typing import Optional, List, Literal
from dataclasses import dataclass
from pydantic import BaseModel, Field

from app.schemas.ai import PolicyDSL, PolicyCondition, PolicyAction, PolicyTranslateResponse
from .gemini import GeminiService

logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Schemas for Structured Outputs
# ============================================================================

class ConditionSchema(BaseModel):
    """Schema for a single policy condition."""
    field: str = Field(description="The field to evaluate (e.g., amount, status, vendor_status)")
    operator: Literal["eq", "neq", "gt", "lt", "gte", "lte", "in", "not_in", "contains", "matches", "between", "is_null", "is_not_null"] = Field(
        description="The comparison operator"
    )
    value: str | int | float | bool | list | None = Field(description="The value to compare against")


class ActionSchema(BaseModel):
    """Schema for a single policy action."""
    type: str = Field(description="The action type (e.g., auto_approve, notify, flag_review)")
    value: str | int | float | bool | None = Field(default=None, description="Optional value for the action")


class DSLSchema(BaseModel):
    """Schema for structured policy DSL."""
    conditions: List[ConditionSchema] = Field(description="List of conditions to evaluate")
    actions: List[ActionSchema] = Field(description="List of actions to perform when conditions are met")
    match_mode: Literal["all", "any"] = Field(default="all", description="Whether ALL or ANY conditions must match")
    stop_on_match: bool = Field(default=True, description="Whether to stop processing other policies after this matches")


class PolicyAnalysisSchema(BaseModel):
    """
    Schema for AI policy analysis response.
    This schema is passed to Gemini for guaranteed structured output.
    """
    policy_type: Literal["logical", "natural_language"] = Field(
        description="Type of policy: 'logical' for structured rules with conditions/actions, 'natural_language' for AI-interpreted instructions"
    )
    confidence: float = Field(
        ge=0, le=1,
        description="Confidence score (0-1) for the suggested policy type"
    )
    reason: str = Field(
        description="Brief explanation of why this policy type was chosen"
    )
    suggested_name: str = Field(
        max_length=60,
        description="A clear, descriptive policy name"
    )
    summary: str = Field(
        max_length=200,
        description="One-sentence summary of what this policy does (under 200 chars)"
    )
    entity_name: Optional[str] = Field(
        default=None,
        description="Name of specific entity (vendor, customer, etc.) if the rule references one"
    )
    suggested_tags: List[str] = Field(
        default_factory=list,
        description="Recommended tags for categorizing this policy"
    )
    dsl: Optional[DSLSchema] = Field(
        default=None,
        description="Structured DSL with conditions and actions (only for 'logical' type)"
    )
    refined_instruction: str = Field(
        description="Clear, structured instruction for AI interpretation (always provided)"
    )
    warnings: Optional[List[str]] = Field(
        default=None,
        description="Any warnings or notes about the analysis"
    )


class PolicyTranslationSchema(BaseModel):
    """Schema for DSL translation response."""
    conditions: List[ConditionSchema] = Field(description="List of conditions")
    actions: List[ActionSchema] = Field(description="List of actions")
    match_mode: Literal["all", "any"] = Field(default="all")
    stop_on_match: bool = Field(default=True)


class PolicySummarySchema(BaseModel):
    """Schema for summary generation."""
    summary: str = Field(max_length=200, description="One-sentence summary of the policy (under 200 chars)")


class RefinedInstructionSchema(BaseModel):
    """Schema for instruction refinement."""
    refined_instruction: str = Field(description="The refined, clear instruction for AI interpretation")


# ============================================================================
# Result Dataclass
# ============================================================================

@dataclass
class PolicyAnalysisResult:
    """Complete AI analysis of a policy input."""
    policy_type: str  # "logical" or "natural_language"
    confidence: float
    reason: str
    suggested_name: str
    summary: str
    entity_name: Optional[str] = None
    suggested_tags: Optional[List[str]] = None
    # For logical policies
    dsl: Optional[PolicyDSL] = None
    # For natural language policies  
    refined_instruction: Optional[str] = None
    # Warnings/notes from AI
    warnings: Optional[List[str]] = None


# ============================================================================
# Policy Service
# ============================================================================

class PolicyService(GeminiService):
    """
    AI-powered policy service using structured outputs.
    
    Uses Pydantic schemas with Gemini's response_json_schema for 
    guaranteed type-safe, parsable responses.
    """
    
    def _get_structured_config(self, schema: type[BaseModel], temperature: float = 0.2):
        """Get config for structured output with a Pydantic schema."""
        try:
            from google.genai import types
            return types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=schema.model_json_schema(),
                temperature=temperature,
            )
        except ImportError:
            return None
    
    async def analyze(
        self,
        natural_language: str,
        available_fields: Optional[List[str]] = None,
        available_actions: Optional[List[str]] = None,
        user_preferred_type: Optional[str] = None
    ) -> PolicyAnalysisResult:
        """
        Comprehensive AI analysis of policy input using structured outputs.
        
        The AI will analyze the input and return a guaranteed schema-compliant response:
        - Policy type (logical vs natural_language)
        - Suggested name, summary, tags
        - DSL for logical policies
        - Refined instruction for natural language policies
        """
        if self.client:
            return await self._ai_analyze(
                natural_language,
                available_fields,
                available_actions,
                user_preferred_type
            )
        else:
            return self._mock_analyze(natural_language, user_preferred_type)
    
    async def _ai_analyze(
        self,
        natural_language: str,
        available_fields: Optional[List[str]] = None,
        available_actions: Optional[List[str]] = None,
        user_preferred_type: Optional[str] = None
    ) -> PolicyAnalysisResult:
        """Use AI with structured outputs for policy analysis."""
        
        # Build context
        fields_context = ", ".join(available_fields) if available_fields else (
            "amount, status, type, category, user_role, vendor_status, score, count, "
            "percentage, priority, risk_score, days_since_created, region, source"
        )
        
        actions_context = ", ".join(available_actions) if available_actions else (
            "auto_approve, auto_reject, flag_review, require_approval, notify, "
            "add_note, set_status, add_tag, route_to, escalate, block, allow"
        )
        
        user_preference_hint = ""
        if user_preferred_type:
            user_preference_hint = f"\nUser Preference: The user prefers '{user_preferred_type}' type. Honor this if the input allows."
        
        prompt = f"""Analyze this business rule and determine the best representation.

User Input: "{natural_language}"

Available Fields: {fields_context}
Available Actions: {actions_context}
{user_preference_hint}

Guidelines:
- Choose "logical" when the rule has clear, discrete conditions (numeric thresholds, exact values, boolean checks)
- Choose "natural_language" when the rule requires contextual judgment, has exceptions, or complex workflows
- For "logical" type: provide complete DSL with conditions and actions
- For "natural_language" type: provide a clear refined_instruction
- Always provide a suggested_name (max 60 chars) and summary (max 200 chars)
- Extract entity_name if a specific vendor/customer/entity is mentioned
- Suggest relevant tags for categorization"""

        try:
            from google.genai import types
            
            contents = [types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)]
            )]
            
            # Use structured output with Pydantic schema
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config=self._get_structured_config(PolicyAnalysisSchema)
            )
            
            # Parse with Pydantic for validation
            analysis = PolicyAnalysisSchema.model_validate_json(response.text)
            
            # Convert DSL to our internal format
            dsl = None
            if analysis.dsl and analysis.policy_type == "logical":
                try:
                    dsl = PolicyDSL(
                        conditions=[
                            PolicyCondition(field=c.field, operator=c.operator, value=c.value)
                            for c in analysis.dsl.conditions
                        ],
                        actions=[
                            PolicyAction(type=a.type, value=a.value)
                            for a in analysis.dsl.actions
                        ],
                        match_mode=analysis.dsl.match_mode,
                        stop_on_match=analysis.dsl.stop_on_match
                    )
                except Exception as e:
                    logger.warning(f"Failed to convert DSL: {e}")
            
            return PolicyAnalysisResult(
                policy_type=analysis.policy_type,
                confidence=analysis.confidence,
                reason=analysis.reason,
                suggested_name=analysis.suggested_name,
                summary=analysis.summary,
                entity_name=analysis.entity_name,
                suggested_tags=analysis.suggested_tags,
                dsl=dsl,
                refined_instruction=analysis.refined_instruction,
                warnings=analysis.warnings
            )
            
        except Exception as e:
            logger.error(f"AI analysis error: {e}")
            return self._mock_analyze(natural_language, user_preferred_type)
    
    def _mock_analyze(
        self,
        natural_language: str,
        user_preferred_type: Optional[str] = None
    ) -> PolicyAnalysisResult:
        """Mock analysis when AI is not available."""
        policy_type = user_preferred_type if user_preferred_type else "natural_language"
        
        words = natural_language.split()[:6]
        suggested_name = " ".join(words).title()[:57] + "..." if len(" ".join(words)) > 57 else " ".join(words).title()
        
        summary = natural_language[:97] + "..." if len(natural_language) > 100 else natural_language
        
        return PolicyAnalysisResult(
            policy_type=policy_type,
            confidence=0.5,
            reason="AI service unavailable - using fallback. Configure GEMINI_API_KEY for full analysis.",
            suggested_name=suggested_name,
            summary=summary,
            entity_name=None,
            suggested_tags=["needs-review"],
            dsl=None,
            refined_instruction=natural_language,
            warnings=["This policy was analyzed without AI. Review and adjust as needed."]
        )
    
    async def translate(self, natural_language: str) -> PolicyTranslateResponse:
        """Translate natural language to structured DSL using structured outputs."""
        try:
            if self.client:
                dsl = await self._ai_translate(natural_language)
            else:
                dsl = self._mock_translate()
            
            return PolicyTranslateResponse(
                dsl=dsl,
                confidence=0.90 if self.client else 0.5,
                explanation="Policy translated to structured rules by AI."
            )
            
        except Exception as e:
            logger.error(f"Policy translation error: {e}")
            return PolicyTranslateResponse(
                dsl=self._mock_translate(),
                confidence=0.3,
                explanation="Translation completed with fallback.",
                warnings=["AI translation failed. Please review the generated rules."]
            )
    
    async def _ai_translate(self, natural_language: str) -> PolicyDSL:
        """Use AI with structured outputs to translate to DSL."""
        prompt = f"""Convert this business rule into structured conditions and actions:

Rule: "{natural_language}"

Available operators: eq, neq, gt, lt, gte, lte, in, not_in, contains, matches, between, is_null, is_not_null
Available actions: auto_approve, auto_reject, flag_review, require_approval, notify, add_note, set_status, add_tag, route_to, escalate, block, allow

Extract all conditions and actions from the rule."""

        try:
            from google.genai import types
            
            contents = [types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)]
            )]
            
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config=self._get_structured_config(PolicyTranslationSchema)
            )
            
            result = PolicyTranslationSchema.model_validate_json(response.text)
            
            return PolicyDSL(
                conditions=[
                    PolicyCondition(field=c.field, operator=c.operator, value=c.value)
                    for c in result.conditions
                ],
                actions=[
                    PolicyAction(type=a.type, value=a.value)
                    for a in result.actions
                ],
                match_mode=result.match_mode,
                stop_on_match=result.stop_on_match
            )
            
        except Exception as e:
            logger.error(f"AI translation error: {e}")
            raise
    
    def _mock_translate(self) -> PolicyDSL:
        """Return a minimal mock DSL when AI is unavailable."""
        return PolicyDSL(
            conditions=[PolicyCondition(field="status", operator="eq", value="pending")],
            actions=[PolicyAction(type="flag_review", value="Requires manual review - AI unavailable")],
            match_mode="all",
            stop_on_match=True
        )
    
    async def refine_instruction(self, natural_language: str) -> str:
        """Refine instruction using structured outputs."""
        if not self.client:
            return natural_language
        
        prompt = f"""Refine this business policy instruction to be clear, specific, and actionable:

Original: "{natural_language}"

Requirements:
- Maintain the original intent
- Make it unambiguous
- Be specific about conditions and actions
- Keep it concise but complete"""

        try:
            from google.genai import types
            
            contents = [types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)]
            )]
            
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config=self._get_structured_config(RefinedInstructionSchema, temperature=0.3)
            )
            
            result = RefinedInstructionSchema.model_validate_json(response.text)
            return result.refined_instruction
            
        except Exception as e:
            logger.error(f"Instruction refinement error: {e}")
            return natural_language
    
    async def generate_summary(self, natural_language: str) -> str:
        """Generate summary using structured outputs."""
        if not self.client:
            return natural_language[:97] + "..." if len(natural_language) > 100 else natural_language
        
        prompt = f"""Create a one-sentence summary (max 100 characters) for this business rule:

"{natural_language}" """

        try:
            from google.genai import types
            
            contents = [types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)]
            )]
            
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config=self._get_structured_config(PolicySummarySchema, temperature=0.3)
            )
            
            result = PolicySummarySchema.model_validate_json(response.text)
            return result.summary[:100]
            
        except Exception as e:
            logger.error(f"Summary generation error: {e}")
            return natural_language[:97] + "..." if len(natural_language) > 100 else natural_language


# Singleton instance
policy_service = PolicyService()
