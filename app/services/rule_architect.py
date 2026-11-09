"""
Supervity Rule Architect - AI-powered rule analysis, conflict detection, and optimization

This module provides:
- RuleArchitect: Analyzes new rules for conflicts and provides suggestions
- PromptOptimizer: Converts natural language rules to Supervity AI-optimized instructions
- RuleHierarchy: Manages BASE vs entity-specific INSTRUCTION rules
"""

import os
import json
import logging
import re
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================================
# Rule Hierarchy Types
# ============================================================================

class PolicyType:
    """Rule policy types with priority order."""
    BASE = "BASE"           # System-wide rules, lower priority
    INSTRUCTION = "INSTRUCTION"  # Entity-specific overrides, higher priority
    CUSTOM = "CUSTOM"       # User-defined custom rules


class RuleAnalysisResult:
    """Result of analyzing a new rule against existing rules."""
    
    def __init__(
        self,
        conflicts: List[Dict] = None,
        overrides: List[Dict] = None,
        clarifications: List[str] = None,
        suggested_instructions: List[str] = None,
        refined_instruction: str = None,
        warnings: List[str] = None,
        is_valid: bool = True
    ):
        self.conflicts = conflicts or []
        self.overrides = overrides or []
        self.clarifications = clarifications or []
        self.suggested_instructions = suggested_instructions or []
        self.refined_instruction = refined_instruction
        self.warnings = warnings or []
        self.is_valid = is_valid
    
    def to_dict(self) -> Dict:
        return {
            "conflicts": self.conflicts,
            "overrides": self.overrides,
            "clarifications": self.clarifications,
            "suggested_instructions": self.suggested_instructions,
            "refined_instruction": self.refined_instruction,
            "warnings": self.warnings,
            "is_valid": self.is_valid,
        }


# ============================================================================
# Prompt Optimizer - Converts natural language to AI-optimized instructions
# ============================================================================

class PromptOptimizer:
    """
    Converts user-friendly natural language rules into Supervity AI-optimized instructions.
    
    Uses AI to refine prompts while preserving intent.
    Falls back to rule-based optimization when AI is unavailable.
    """
    
    OPTIMIZER_SYSTEM_PROMPT = """You are the Supervity AI Rule Optimizer. Your task is to take a user's business rule, 
written in plain English, and convert it into a clear, concise, and direct instruction 
for the Supervity AI system to follow.

**CRITICAL RULES:**
1. **Preserve Intent:** Do not change the core logic or meaning
2. **Remove Fluff:** Eliminate conversational phrases like "I think we should", "probably", "maybe"
3. **Be Direct:** Rephrase as a direct command or verification statement
4. **Be Specific:** Include specific thresholds, fields, and conditions
5. **State Outcomes:** Clearly state what happens when conditions are met/not met
6. **Output ONLY the Instruction:** No explanations or metadata

**Examples:**

User: "For this vendor, I think we should probably make sure that the invoice date isn't more than 5 days after the PO date."
Refined: "Verify that the invoice_date is no more than 5 days after the associated purchase_order_date. If it exceeds this threshold, mark the check as FAILED."

User: "We need to be careful about prices, they shouldn't be too different from what we agreed"
Refined: "Verify that line item prices do not exceed the agreed contract prices by more than the configured tolerance percentage. If any price exceeds tolerance, flag for REVIEW."

User: "Auto approve small orders"
Refined: "Automatically approve orders where the total amount is below the configured threshold. No manual review required for these orders."

Now refine this rule:
"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = None
        self.model = os.getenv("AI_MODEL", "gemini-2.0-flash")
        
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info("PromptOptimizer initialized with Gemini")
            except ImportError:
                logger.warning("google-genai not installed, using rule-based optimization")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
    
    async def refine(self, natural_language: str) -> str:
        """
        Refines a natural language rule into an AI-optimized instruction.
        
        Args:
            natural_language: User's plain English rule
            
        Returns:
            Refined instruction optimized for AI processing
        """
        if self.client:
            try:
                return await self._refine_with_ai(natural_language)
            except Exception as e:
                logger.warning(f"AI refinement failed, using fallback: {e}")
        
        return self._refine_with_rules(natural_language)
    
    async def _refine_with_ai(self, natural_language: str) -> str:
        """Use Gemini to refine the prompt."""
        from google.genai import types
        
        prompt = f"{self.OPTIMIZER_SYSTEM_PROMPT}\n\n\"{natural_language}\""
        
        contents = [types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)]
        )]
        
        config = types.GenerateContentConfig(
            temperature=0.3,  # Lower temperature for more consistent output
        )
        
        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config
        )
        
        refined = response.text.strip()
        # Remove quotes if the AI wrapped the response
        if refined.startswith('"') and refined.endswith('"'):
            refined = refined[1:-1]
        
        return refined
    
    def _refine_with_rules(self, natural_language: str) -> str:
        """
        Rule-based refinement fallback when AI is unavailable.
        Applies common cleanup patterns.
        """
        text = natural_language.strip()
        
        # Remove conversational fillers
        fillers = [
            r"\bI think\b",
            r"\bwe should\b",
            r"\bprobably\b",
            r"\bmaybe\b",
            r"\bperhaps\b",
            r"\bkind of\b",
            r"\bsort of\b",
            r"\bbasically\b",
        ]
        for filler in fillers:
            text = re.sub(filler, "", text, flags=re.IGNORECASE)
        
        # Clean up extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Capitalize first letter
        if text:
            text = text[0].upper() + text[1:]
        
        # Ensure it ends with a period
        if text and not text.endswith(('.', '!', '?')):
            text += '.'
        
        # Add outcome if not present
        outcome_keywords = ['if', 'when', 'then', 'flag', 'approve', 'reject', 'review', 'mark', 'fail', 'pass']
        has_outcome = any(kw in text.lower() for kw in outcome_keywords)
        
        if not has_outcome:
            text += " If this condition is not met, flag for REVIEW."
        
        return text
    
    def generate_suggestions(self, natural_language: str, count: int = 3) -> List[str]:
        """
        Generate multiple refined instruction suggestions.
        
        For demo/fallback, creates variations of the refined instruction.
        """
        base = self._refine_with_rules(natural_language)
        suggestions = [base]
        
        # Variation 1: More formal
        formal = base.replace("flag for", "escalate for immediate")
        if formal != base:
            suggestions.append(formal)
        
        # Variation 2: More specific
        specific = base
        if "threshold" not in base.lower():
            specific = base.replace(".", " against configured thresholds.")
        if specific != base:
            suggestions.append(specific)
        
        # Variation 3: Add tracing
        traced = base.rstrip('.') + ". Log detailed comparison in the audit trace."
        suggestions.append(traced)
        
        return suggestions[:count]


# ============================================================================
# Rule Architect - Conflict detection and rule analysis
# ============================================================================

class RuleArchitect:
    """
    AI-powered rule analysis for conflict detection and suggestions.
    
    Analyzes new rules against existing rules to detect:
    - Conflicts: Rules that contradict each other
    - Overrides: New rules that override existing BASE rules
    - Clarifications: Questions the AI needs answered
    """
    
    ARCHITECT_SYSTEM_PROMPT = """You are the Supervity AI Rule Architect. Analyze the new rule against existing rules.

**Your Task:**
1. Identify CONFLICTS - rules that directly contradict each other
2. Identify OVERRIDES - where the new rule (if INSTRUCTION type) would override a BASE rule
3. Suggest CLARIFICATIONS - questions that would help make the rule more precise
4. Generate 2-3 SUGGESTED_INSTRUCTIONS - refined versions of the rule

**Rule Hierarchy:**
- BASE rules are system-wide defaults
- INSTRUCTION rules are entity-specific and override BASE rules for that entity

**Output JSON Schema:**
{
    "conflicts": [
        {"conflicting_rule_id": "...", "conflicting_rule_name": "...", "explanation": "..."}
    ],
    "overrides": [
        {"overridden_rule_id": "...", "overridden_rule_name": "...", "explanation": "..."}
    ],
    "clarifications": ["question 1", "question 2"],
    "suggested_instructions": ["instruction 1", "instruction 2"],
    "is_valid": true
}

Return ONLY valid JSON.
"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = None
        self.model = os.getenv("AI_MODEL", "gemini-2.0-flash")
        self.prompt_optimizer = PromptOptimizer(api_key)
        
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info("RuleArchitect initialized with Gemini")
            except ImportError:
                logger.warning("google-genai not installed, using heuristic analysis")
    
    async def analyze_rule(
        self,
        new_rule: Dict[str, Any],
        existing_rules: List[Dict[str, Any]],
        entity_name: Optional[str] = None
    ) -> RuleAnalysisResult:
        """
        Analyze a new rule against existing rules.
        
        Args:
            new_rule: The new rule to analyze (dict with natural_language, policy_type, etc.)
            existing_rules: List of existing rules in the system
            entity_name: Optional entity (vendor, user, etc.) for INSTRUCTION rules
            
        Returns:
            RuleAnalysisResult with conflicts, overrides, and suggestions
        """
        if self.client:
            try:
                return await self._analyze_with_ai(new_rule, existing_rules, entity_name)
            except Exception as e:
                logger.warning(f"AI analysis failed, using heuristic: {e}")
        
        return await self._analyze_with_heuristics(new_rule, existing_rules, entity_name)
    
    async def _analyze_with_ai(
        self,
        new_rule: Dict,
        existing_rules: List[Dict],
        entity_name: Optional[str]
    ) -> RuleAnalysisResult:
        """Use Gemini for intelligent rule analysis."""
        from google.genai import types
        
        # Build context
        existing_summary = json.dumps([{
            "id": r.get("id"),
            "name": r.get("name"),
            "natural_language": r.get("natural_language"),
            "policy_type": r.get("policy_type", "BASE"),
            "entity_name": r.get("entity_name"),
            "is_active": r.get("is_active", True)
        } for r in existing_rules], indent=2)
        
        prompt = f"""{self.ARCHITECT_SYSTEM_PROMPT}

**New Rule:**
- Natural Language: "{new_rule.get('natural_language')}"
- Policy Type: {new_rule.get('policy_type', 'BASE')}
- Entity: {entity_name or 'ALL (system-wide)'}

**Existing Rules:**
{existing_summary}

Analyze and return JSON:"""

        contents = [types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)]
        )]
        
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        )
        
        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config
        )
        
        data = json.loads(response.text.strip())
        
        # Also generate refined instruction
        refined = await self.prompt_optimizer.refine(new_rule.get('natural_language', ''))
        
        return RuleAnalysisResult(
            conflicts=data.get("conflicts", []),
            overrides=data.get("overrides", []),
            clarifications=data.get("clarifications", []),
            suggested_instructions=data.get("suggested_instructions", []),
            refined_instruction=refined,
            is_valid=data.get("is_valid", True)
        )
    
    async def _analyze_with_heuristics(
        self,
        new_rule: Dict,
        existing_rules: List[Dict],
        entity_name: Optional[str]
    ) -> RuleAnalysisResult:
        """
        Heuristic-based rule analysis when AI is unavailable.
        Uses keyword matching and simple logic.
        """
        conflicts = []
        overrides = []
        clarifications = []
        warnings = []
        
        new_text = new_rule.get('natural_language', '').lower()
        new_type = new_rule.get('policy_type', 'BASE')
        
        # Extract key concepts from new rule
        new_concepts = self._extract_concepts(new_text)
        
        for existing in existing_rules:
            if not existing.get('is_active', True):
                continue
            
            existing_text = existing.get('natural_language', '').lower()
            existing_concepts = self._extract_concepts(existing_text)
            existing_type = existing.get('policy_type', 'BASE')
            
            # Check for conceptual overlap
            overlap = new_concepts & existing_concepts
            
            if overlap:
                # Check for conflicting logic
                if self._has_conflicting_logic(new_text, existing_text):
                    if new_type == 'INSTRUCTION' and existing_type == 'BASE':
                        overrides.append({
                            "overridden_rule_id": existing.get("id"),
                            "overridden_rule_name": existing.get("name"),
                            "explanation": f"Your INSTRUCTION rule will override the BASE rule for {entity_name or 'this entity'}. Overlapping concepts: {', '.join(overlap)}"
                        })
                    else:
                        conflicts.append({
                            "conflicting_rule_id": existing.get("id"),
                            "conflicting_rule_name": existing.get("name"),
                            "explanation": f"Both rules affect {', '.join(overlap)} with potentially conflicting logic"
                        })
        
        # Generate clarifying questions
        if 'tolerance' in new_text and not re.search(r'\d+%', new_text):
            clarifications.append("What specific percentage tolerance should apply?")
        
        if 'threshold' in new_text and not re.search(r'\$?\d+', new_text):
            clarifications.append("What specific threshold value should be used?")
        
        if 'review' in new_text and 'approve' in new_text:
            clarifications.append("Should this auto-approve or flag for manual review?")
        
        # Generate refined instruction
        refined = await self.prompt_optimizer.refine(new_rule.get('natural_language', ''))
        
        # Generate suggestions
        suggestions = self.prompt_optimizer.generate_suggestions(
            new_rule.get('natural_language', '')
        )
        
        return RuleAnalysisResult(
            conflicts=conflicts,
            overrides=overrides,
            clarifications=clarifications,
            suggested_instructions=suggestions,
            refined_instruction=refined,
            warnings=warnings,
            is_valid=len(conflicts) == 0 or new_type == 'INSTRUCTION'
        )
    
    def _extract_concepts(self, text: str) -> set:
        """Extract key concepts from rule text for comparison."""
        concepts = set()
        
        # Field/domain concepts
        domain_keywords = {
            'price': {'price', 'cost', 'amount', 'total', 'value'},
            'quantity': {'quantity', 'qty', 'count', 'units', 'number'},
            'date': {'date', 'time', 'day', 'period', 'deadline'},
            'status': {'status', 'state', 'approval', 'review'},
            'user': {'user', 'role', 'permission', 'access'},
            'tolerance': {'tolerance', 'variance', 'difference', 'deviation'},
        }
        
        for concept, keywords in domain_keywords.items():
            if any(kw in text for kw in keywords):
                concepts.add(concept)
        
        return concepts
    
    def _has_conflicting_logic(self, text1: str, text2: str) -> bool:
        """Check if two rule texts have conflicting logic."""
        # Simple heuristic: opposite keywords
        opposites = [
            ('approve', 'reject'),
            ('allow', 'deny'),
            ('accept', 'reject'),
            ('pass', 'fail'),
            ('increase', 'decrease'),
            ('more than', 'less than'),
            ('above', 'below'),
        ]
        
        for word1, word2 in opposites:
            if (word1 in text1 and word2 in text2) or (word2 in text1 and word1 in text2):
                return True
        
        return False


# ============================================================================
# Rule Compiler - Compiles rules for AI processing
# ============================================================================

class RuleCompiler:
    """
    Compiles rules into a format optimized for AI processing.
    
    Handles:
    - Rule hierarchy (BASE vs INSTRUCTION)
    - Priority ordering
    - Entity-specific filtering
    """
    
    def compile_rules(
        self,
        rules: List[Dict[str, Any]],
        entity_name: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> str:
        """
        Compile rules into a single prompt-ready text block.
        
        Args:
            rules: List of rule dictionaries
            entity_name: Entity for filtering INSTRUCTION rules
            context: Additional context (tolerances, settings, etc.)
            
        Returns:
            Compiled rules text for AI prompt injection
        """
        # Separate by type
        base_rules = [r for r in rules if r.get('policy_type') == 'BASE' and r.get('is_active', True)]
        instruction_rules = [
            r for r in rules 
            if r.get('policy_type') == 'INSTRUCTION' 
            and r.get('is_active', True)
            and (entity_name is None or r.get('entity_name') == entity_name)
        ]
        
        # Sort by priority (lower = higher priority)
        base_rules.sort(key=lambda r: r.get('priority', 100))
        instruction_rules.sort(key=lambda r: r.get('priority', 100))
        
        # Build compiled text
        lines = []
        
        if context:
            lines.append("**CONTEXT SETTINGS:**")
            for key, value in context.items():
                lines.append(f"- {key}: {value}")
            lines.append("")
        
        lines.append("**BASE RULES (System-Wide):**")
        for i, rule in enumerate(base_rules, 1):
            instruction = rule.get('refined_instruction') or rule.get('natural_language')
            lines.append(f"{i}. {instruction}")
        
        if instruction_rules:
            lines.append("")
            lines.append(f"**ENTITY-SPECIFIC INSTRUCTIONS ({entity_name or 'Current Entity'}):**")
            lines.append("(These override conflicting BASE rules)")
            for i, rule in enumerate(instruction_rules, 1):
                instruction = rule.get('refined_instruction') or rule.get('natural_language')
                lines.append(f"{i}. {instruction}")
        
        return "\n".join(lines)
    
    def get_rule_trace_template(self) -> str:
        """Get the expected trace output format for AI responses."""
        return """
For each rule evaluated, include a trace entry in this format:
{
    "step": "Rule Name or Description",
    "rule_id": "rule-id",
    "rule_type": "BASE or INSTRUCTION",
    "status": "PASS or FAIL or WARNING",
    "message": "Human-readable explanation",
    "details": {
        // Relevant comparison data
    }
}
"""


# Singleton instances
prompt_optimizer = PromptOptimizer()
rule_architect = RuleArchitect()
rule_compiler = RuleCompiler()

