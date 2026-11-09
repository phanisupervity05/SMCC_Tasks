"""
AI Services Package

This package provides modular AI services for the platform:
- gemini: Base Gemini AI integration
- rule_engine: Policy/rule execution engine
- tools: AI function calling tools
- chat: Conversational AI service
- policy: Policy translation service
- insights: AI-generated insights service
"""

from .gemini import GeminiService
from .rule_engine import RuleEngine, rule_engine
from .tools import get_tool_definitions, ToolExecutor, tool_executor
from .chat import ChatService, chat_service
from .policy import PolicyService, policy_service
from .insights import InsightsService, insights_service


# Convenience class that combines all services
class AIService:
    """
    Unified AI service interface.
    
    Provides access to all AI capabilities through a single interface.
    Use this for simple use cases or the individual services for more control.
    """
    
    def __init__(self):
        self.chat = chat_service
        self.policy = policy_service
        self.insights = insights_service
        self.rule_engine = rule_engine
    
    async def chat_message(self, message, history=None, context=None, user_id=None):
        """Send a chat message."""
        return await self.chat.chat(message, history, context, user_id)
    
    async def translate_policy(self, natural_language):
        """Translate natural language to policy DSL."""
        return await self.policy.translate(natural_language)
    
    async def generate_insights(self, batch_id=None, date_range_start=None, date_range_end=None):
        """Generate AI insights."""
        return await self.insights.generate(batch_id, date_range_start, date_range_end)


# Singleton instance for convenience
ai_service = AIService()


__all__ = [
    # Base classes
    "GeminiService",
    "RuleEngine",
    "ToolExecutor",
    "ChatService",
    "PolicyService",
    "InsightsService",
    # Singleton instances
    "rule_engine",
    "tool_executor",
    "chat_service",
    "policy_service",
    "insights_service",
    "ai_service",
    # Utilities
    "get_tool_definitions",
]

