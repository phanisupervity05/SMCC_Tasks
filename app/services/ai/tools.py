"""
AI Tools - Function calling tools for the AI assistant

Defines tools the AI can call and handles their execution.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def get_tool_definitions() -> List:
    """
    Define tools the AI can call.
    Returns dynamically to support extension at runtime.
    """
    try:
        from google.genai import types as genai_types
        
        return [
            genai_types.Tool(
                function_declarations=[
                    genai_types.FunctionDeclaration(
                        name="list_recent_activity",
                        description="Get recent activity and events from the system",
                        parameters=genai_types.Schema(
                            type=genai_types.Type.OBJECT,
                            properties={
                                "limit": genai_types.Schema(
                                    type=genai_types.Type.INTEGER,
                                    description="Maximum number of activities to return (default 10)"
                                ),
                                "activity_type": genai_types.Schema(
                                    type=genai_types.Type.STRING,
                                    description="Filter by activity type",
                                    enum=["login", "action", "error", "all"]
                                ),
                            },
                        ),
                    ),
                    genai_types.FunctionDeclaration(
                        name="get_system_stats",
                        description="Get statistics about the system",
                        parameters=genai_types.Schema(
                            type=genai_types.Type.OBJECT,
                            properties={
                                "include_details": genai_types.Schema(
                                    type=genai_types.Type.BOOLEAN,
                                    description="Include detailed breakdown"
                                ),
                            },
                        ),
                    ),
                    genai_types.FunctionDeclaration(
                        name="generate_report",
                        description="Generate a report based on specified parameters",
                        parameters=genai_types.Schema(
                            type=genai_types.Type.OBJECT,
                            properties={
                                "report_type": genai_types.Schema(
                                    type=genai_types.Type.STRING,
                                    description="Type of report to generate",
                                    enum=["activity", "users", "audit", "performance", "policies"]
                                ),
                                "format": genai_types.Schema(
                                    type=genai_types.Type.STRING,
                                    description="Output format",
                                    enum=["json", "csv", "excel"]
                                ),
                                "date_range": genai_types.Schema(
                                    type=genai_types.Type.STRING,
                                    description="Date range for the report",
                                    enum=["today", "last_7_days", "last_30_days", "this_month"]
                                ),
                            },
                            required=["report_type"]
                        ),
                    ),
                    genai_types.FunctionDeclaration(
                        name="explain_page",
                        description="Explain the current page and its functionality to the user",
                        parameters=genai_types.Schema(
                            type=genai_types.Type.OBJECT,
                            properties={
                                "page_path": genai_types.Schema(
                                    type=genai_types.Type.STRING,
                                    description="The path of the page to explain"
                                ),
                            },
                            required=["page_path"]
                        ),
                    ),
                    genai_types.FunctionDeclaration(
                        name="create_policy",
                        description="Create a new AI policy from natural language description",
                        parameters=genai_types.Schema(
                            type=genai_types.Type.OBJECT,
                            properties={
                                "name": genai_types.Schema(
                                    type=genai_types.Type.STRING,
                                    description="Name for the policy"
                                ),
                                "description": genai_types.Schema(
                                    type=genai_types.Type.STRING,
                                    description="Natural language description of the policy"
                                ),
                            },
                            required=["name", "description"]
                        ),
                    ),
                ]
            )
        ]
    except ImportError:
        return []


class ToolExecutor:
    """Executes AI tool calls and returns results."""
    
    # Page explanations
    PAGE_EXPLANATIONS = {
        "/": """**Dashboard**

Your command center overview showing:
* Key performance metrics
* Recent activity summary
* System health indicators
* Quick action buttons""",
        
        "/workbench": """**Workbench**

Your workspace for:
* Launching AI tools and assistants
* Managing automation workflows
* Accessing integrations
* Running quick actions""",
        
        "/ai/policies": """**AI Policies**

Create and manage business rules:
* **Natural Language Tab** - Write rules in plain English
* **Structured Rules Tab** - Build rules visually with conditions
* **Permission Matrix Tab** - Define role-based access

Policies are automatically executed when conditions match.""",
        
        "/ai/insights": """**AI Insights**

View AI-generated analytics:
* **Summary** - Overview of all insights with severity levels
* **Patterns** - Detected recurring behaviors
* **Actions** - Recommended improvements

Click "Run Analysis" to generate fresh insights.""",
        
        "/admin/users": """**User Management**

Manage user accounts:
* View all registered users
* Approve pending registrations
* Assign roles and permissions
* Manage user sessions""",
        
        "/settings": """**Settings**

Configure your preferences:
* Profile information
* Notification settings
* Display preferences
* Account security""",
    }
    
    def execute(self, name: str, args: Dict) -> Any:
        """Execute a tool and return the result."""
        logger.info(f"Executing tool: {name} with args: {args}")
        
        if name == "list_recent_activity":
            return self._list_recent_activity(args)
        elif name == "get_system_stats":
            return self._get_system_stats(args)
        elif name == "generate_report":
            return self._generate_report(args)
        elif name == "explain_page":
            return self._explain_page(args)
        elif name == "create_policy":
            return self._create_policy(args)
        
        return {"error": f"Unknown tool: {name}"}
    
    def _list_recent_activity(self, args: Dict) -> Dict:
        return {
            "activities": [
                {"type": "login", "user": "admin", "time": "2 minutes ago"},
                {"type": "action", "description": "Policy created", "time": "10 minutes ago"},
                {"type": "login", "user": "user1", "time": "1 hour ago"},
            ][:args.get("limit", 10)]
        }
    
    def _get_system_stats(self, args: Dict) -> Dict:
        return {
            "total_users": 156,
            "active_sessions": 23,
            "policies_active": 12,
            "insights_pending": 3
        }
    
    def _generate_report(self, args: Dict) -> Dict:
        return {
            "status": "generated",
            "report_type": args.get("report_type"),
            "format": args.get("format", "json"),
            "download_url": "/api/reports/latest"
        }
    
    def _explain_page(self, args: Dict) -> str:
        page_path = args.get("page_path", "/")
        
        for path, explanation in self.PAGE_EXPLANATIONS.items():
            if page_path.startswith(path) or page_path == path:
                return explanation
        
        return f"You're viewing **{page_path}**. How can I help you with it?"
    
    def _create_policy(self, args: Dict) -> Dict:
        return {
            "status": "created",
            "policy_name": args.get("name"),
            "message": f"Policy '{args.get('name')}' has been created successfully."
        }


# Singleton instance
tool_executor = ToolExecutor()

