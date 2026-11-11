"""
AI Services Package

This package provides modular AI services for the platform:
- gemini: Base Gemini AI integration
- tools: AI function calling tools
- chat: Conversational AI service
- insights: AI-generated insights service
"""

from .gemini import GeminiService
from .tools import get_tool_definitions, ToolExecutor, tool_executor
from .chat import ChatService, chat_service
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
        self.insights = insights_service
    
    async def chat_message(self, message, history=None, context=None, user_id=None):
        """Send a chat message."""
        return await self.chat.chat(message, history, context, user_id)

    async def generate_insights(self, batch_id=None, date_range_start=None, date_range_end=None):
        """Generate insights from the real calls data."""
        return await self.insights.generate(batch_id, date_range_start, date_range_end)


# Singleton instance for convenience
ai_service = AIService()


__all__ = [
    # Base classes
    "GeminiService",
    "ToolExecutor",
    "ChatService",
    "InsightsService",
    # Singleton instances
    "tool_executor",
    "chat_service",
    "insights_service",
    "ai_service",
    # Utilities
    "get_tool_definitions",
]

