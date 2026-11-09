"""
Supervity AI Chat Service - Conversational AI with function calling

Handles chat interactions with the Supervity AI Manager.
"""

import uuid
import logging
from typing import Optional, List

from app.schemas.ai import ChatMessage, ChatContext, ChatResponse, ToolCall
from .gemini import GeminiService
from .tools import get_tool_definitions, tool_executor

logger = logging.getLogger(__name__)


class ChatService(GeminiService):
    """
    Service for AI chat interactions.
    Supports conversational context and function calling.
    """
    
    MAX_TOOL_ITERATIONS = 5
    
    SYSTEM_PROMPT = """You are the **Supervity AI Manager**, an intelligent AI assistant for the Supervity command center platform.
Your role is to help users manage Supervity AI policies, understand insights, and navigate the platform.

**IMPORTANT: You are the Supervity AI Manager. Always identify yourself as "Supervity" or "Supervity AI". Never mention any underlying AI technology or model names.**

**Greetings:** When greeting users, say things like:
- "Greetings from Supervity!"
- "Hello! I'm your Supervity AI Manager."
- "Welcome! Supervity AI at your service."

**Your Capabilities:**
- Answer questions about the platform and its features
- Help create and manage Supervity AI policies using natural language
- Explain insights and patterns in data
- Generate reports and summaries
- Execute actions through available tools

**Response Guidelines:**
- Be concise, helpful, and professional
- Use **bold** for emphasis and important terms
- Use bullet points for lists
- When mentioning actions, be specific about what you can do
- If you used a tool, explain what you did
- Always refer to yourself as "Supervity AI" or "Supervity AI Manager"

**Available Tools:**
- list_recent_activity: Get recent system activity
- get_system_stats: Get system statistics
- generate_report: Create reports
- explain_page: Explain page functionality
- create_policy: Create new Supervity AI policies"""

    async def chat(
        self,
        message: str,
        history: Optional[List[ChatMessage]] = None,
        context: Optional[ChatContext] = None,
        user_id: Optional[str] = None
    ) -> ChatResponse:
        """
        Process a chat message and return AI response.
        Supports function calling for agentic capabilities.
        """
        try:
            system_prompt = self._build_system_prompt(context)
            
            if self.client:
                response_text, tool_calls = await self._gemini_chat(
                    message, history, system_prompt, context
                )
            else:
                response_text = self._mock_chat(message, context)
                tool_calls = None
            
            return ChatResponse(
                response=response_text,
                tool_calls=tool_calls,
                suggestions=self._generate_suggestions(message, context),
                confidence=0.95 if self.client else 0.7
            )
            
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return ChatResponse(
                response="I apologize, but I encountered an error processing your request. Please try again.",
                confidence=0.0
            )
    
    async def _gemini_chat(
        self,
        message: str,
        history: Optional[List[ChatMessage]],
        system_prompt: str,
        context: Optional[ChatContext]
    ) -> tuple[str, Optional[List[ToolCall]]]:
        """Execute chat with real Gemini API."""
        try:
            from google.genai import types as genai_types
            
            contents = []
            if history:
                for msg in history:
                    role = "user" if msg.role.value == "user" else "model"
                    contents.append(genai_types.Content(
                        role=role,
                        parts=[genai_types.Part.from_text(text=msg.content)]
                    ))
            
            contents.append(genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text=message)]
            ))
            
            config = genai_types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=get_tool_definitions(),
                temperature=0.7,
            )
            
            tool_calls_executed = []
            
            for _ in range(self.MAX_TOOL_ITERATIONS):
                response = await self.client.aio.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config
                )
                
                candidate = response.candidates[0] if response.candidates else None
                if not candidate:
                    return "I couldn't generate a response. Please try again.", None
                
                function_calls = [
                    p.function_call 
                    for p in candidate.content.parts 
                    if hasattr(p, 'function_call') and p.function_call
                ]
                
                if not function_calls:
                    text_parts = [
                        p.text for p in candidate.content.parts 
                        if hasattr(p, 'text') and p.text
                    ]
                    return '\n'.join(text_parts), tool_calls_executed if tool_calls_executed else None
                
                contents.append(candidate.content)
                tool_results = []
                
                for fc in function_calls:
                    result = tool_executor.execute(fc.name, dict(fc.args))
                    tool_calls_executed.append(ToolCall(
                        id=str(uuid.uuid4()),
                        name=fc.name,
                        args=dict(fc.args),
                        result=result
                    ))
                    tool_results.append(genai_types.Part.from_function_response(
                        name=fc.name,
                        response={"result": result}
                    ))
                
                contents.append(genai_types.Content(role="user", parts=tool_results))
            
            return "I've reached my processing limit. Please try a simpler request.", tool_calls_executed
            
        except Exception as e:
            logger.error(f"Gemini chat error: {e}")
            return self._mock_chat(message, context), None
    
    def _build_system_prompt(self, context: Optional[ChatContext]) -> str:
        """Build a context-aware system prompt."""
        prompt = self.SYSTEM_PROMPT
        if context and context.page:
            prompt += f"\n\n**Current Context:** User is viewing `{context.page}`"
        return prompt
    
    def _mock_chat(self, message: str, context: Optional[ChatContext]) -> str:
        """Generate mock AI response for development/demo."""
        message_lower = message.lower()
        
        if "help" in message_lower or "what can you" in message_lower:
            return """I can help you with several things:

**AI Policies**
* Create new policies using natural language
* Translate rules into structured conditions
* Manage and organize your policy library

**AI Insights**
* Analyze patterns in your data
* Identify anomalies and trends
* Suggest optimizations and improvements

**General Assistance**
* Navigate the platform
* Generate reports
* Understand features and capabilities

What would you like to explore?"""

        elif "activity" in message_lower or "recent" in message_lower:
            return """Here's a summary of **recent activity**:

**Last 24 Hours**
* 156 user logins
* 23 policy executions
* 8 new insights generated
* 2 alerts resolved

Would you like me to generate a detailed report?"""

        elif "report" in message_lower:
            return """I can generate several types of reports:

1. **Activity Report** - User actions and system events
2. **Audit Report** - Security and compliance logs
3. **Performance Report** - System metrics and trends
4. **User Report** - User statistics and engagement
5. **Policy Report** - Policy execution statistics

Which report would you like?"""

        elif "policy" in message_lower or "policies" in message_lower:
            return """**AI Policies** allow you to define business rules in natural language.

For example, you can write:
> "If the amount is less than $100, auto-approve it"

The AI will translate this into executable logic that runs automatically.

Would you like me to help you create a new policy?"""

        elif "insight" in message_lower:
            return """**AI Insights** proactively analyze your data to find:

* **Patterns** - Recurring behaviors and trends
* **Anomalies** - Unusual activities that need attention
* **Recommendations** - Suggested actions to optimize

Visit the **AI Insights** page to explore these in detail."""

        else:
            return f"""I understand you're asking about: *"{message}"*

I'm here to help with AI policies, insights, and general platform navigation. Could you provide more details?

**Quick suggestions:**
* "Help me create a new policy"
* "Show me recent activity"
* "Explain this page"
* "Generate a report" """
    
    def _generate_suggestions(self, message: str, context: Optional[ChatContext]) -> List[str]:
        """Generate follow-up suggestions based on conversation."""
        message_lower = message.lower()
        
        if "policy" in message_lower:
            return ["Show me my active policies", "Create a new policy", "Explain policy conditions"]
        elif "insight" in message_lower:
            return ["Run a new analysis", "Show critical insights", "Export insights report"]
        elif "report" in message_lower:
            return ["Generate activity report", "Show user statistics", "Export to Excel"]
        else:
            return ["What can you help me with?", "Show me insights", "Create a policy"]


# Singleton instance
chat_service = ChatService()

