"""
Supervity AI Service - Base class for AI integration

Handles client initialization and configuration for all Supervity AI features.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class GeminiService:
    """
    Base class for Supervity AI integration.
    
    Handles client initialization, configuration, and common patterns.
    Extend this class for specific Supervity AI features.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = os.getenv("AI_MODEL", "gemini-2.0-flash")
        self.client = None
        
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"Supervity AI client initialized with model: {self.model}")
            except ImportError:
                logger.warning("AI package not installed. Supervity AI features will use mock responses.")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
        else:
            logger.warning("AI API key not set. Supervity AI features will use mock responses.")
    
    @property
    def is_available(self) -> bool:
        """Check if the Gemini client is available."""
        return self.client is not None
    
    def _get_json_config(self):
        """Config for JSON output responses."""
        try:
            from google.genai import types
            return types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            )
        except ImportError:
            return None
    
    def _get_text_config(self, system_instruction: Optional[str] = None, temperature: float = 0.7):
        """Config for text/chat output."""
        try:
            from google.genai import types
            config = types.GenerateContentConfig(temperature=temperature)
            if system_instruction:
                config.system_instruction = system_instruction
            return config
        except ImportError:
            return None

