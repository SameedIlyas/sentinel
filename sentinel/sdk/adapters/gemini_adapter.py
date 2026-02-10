"""Google Gemini API adapter for Sentinel SDK."""

import json
import logging
from typing import Any, Dict, List

from sentinel.sdk.llm_adapter import LLMAdapter, LLMRequest, ToolCall


logger = logging.getLogger(__name__)


class GeminiAdapter(LLMAdapter):
    """Adapter for Google Gemini API integration."""
    
    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "Google Gemini"
    
    def can_handle(self, endpoint: str, headers: Dict[str, str]) -> bool:
        """
        Determine if this is a Google Gemini API request.
        
        Args:
            endpoint: The API endpoint URL
            headers: Request headers
            
        Returns:
            True if this is a Gemini request
        """
        # Check for Gemini API endpoint
        if "generativelanguage.googleapis.com" in endpoint:
            return True
        
        # Check for Google AI API endpoint
        if "googleapis.com" in endpoint and "/models/gemini" in endpoint:
            return True
        
        return False
    
    def extract_tool_calls(self, response: Dict[str, Any]) -> List[ToolCall]:
        """
        Extract tool calls from Gemini API response.
        
        Gemini response format:
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "get_weather",
                                    "args": {
                                        "location": "San Francisco"
                                    }
                                }
                            }
                        ]
                    }
                }
            ]
        }
        
        Args:
            response: The Gemini API response
            
        Returns:
            List of extracted ToolCall objects
        """
        tool_calls = []
        
        try:
            candidates = response.get("candidates", [])
            if not candidates:
                return tool_calls
            
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            
            for idx, part in enumerate(parts):
                if "functionCall" not in part:
                    continue
                
                function_call = part["functionCall"]
                function_name = function_call.get("name")
                function_args = function_call.get("args", {})
                
                # Generate a unique ID for this tool call
                tool_id = f"gemini_call_{idx}"
                
                tool_call = ToolCall(
                    id=tool_id,
                    name=function_name,
                    arguments=function_args,
                    metadata={
                        "provider": "gemini",
                        "type": "function_call"
                    }
                )
                tool_calls.append(tool_call)
            
            logger.debug(f"Extracted {len(tool_calls)} tool calls from Gemini response")
            
        except Exception as e:
            logger.error(f"Error extracting tool calls from Gemini response: {e}")
        
        return tool_calls
    
    def intercept_request(self, request: LLMRequest) -> LLMRequest:
        """
        Intercept Gemini request.
        
        Can be used to:
        - Log request metadata
        - Modify parameters
        - Add safety settings
        
        Args:
            request: The original request
            
        Returns:
            The potentially modified request
        """
        # Log the request
        payload = request.payload
        
        # Extract model from URL if present
        model = None
        if "/models/" in request.endpoint:
            parts = request.endpoint.split("/models/")
            if len(parts) > 1:
                model = parts[1].split(":")[0]
        
        tools = payload.get("tools", [])
        
        logger.debug(
            f"Gemini request: model={model or 'unknown'}, tools={len(tools)}"
        )
        
        # Could add modifications here, e.g.:
        # - Enforce safety settings
        # - Add generation config limits
        # - Modify function declarations
        
        return request
    
    def intercept_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Intercept Gemini response.
        
        Can be used to:
        - Log response metadata
        - Mask sensitive data
        - Track usage
        
        Args:
            response: The original response
            
        Returns:
            The potentially modified response
        """
        # Log usage metadata
        usage_metadata = response.get("usageMetadata", {})
        if usage_metadata:
            logger.debug(
                f"Gemini usage: "
                f"prompt_token_count={usage_metadata.get('promptTokenCount', 0)}, "
                f"candidates_token_count={usage_metadata.get('candidatesTokenCount', 0)}, "
                f"total_token_count={usage_metadata.get('totalTokenCount', 0)}"
            )
        
        # Log safety ratings
        candidates = response.get("candidates", [])
        if candidates:
            safety_ratings = candidates[0].get("safetyRatings", [])
            if safety_ratings:
                logger.debug(f"Gemini safety ratings: {len(safety_ratings)} categories checked")
        
        # Could add modifications here, e.g.:
        # - Mask PII in content
        # - Filter out blocked tool calls
        # - Add audit metadata
        
        return response
    
    def get_model_from_request(self, request: Dict[str, Any]) -> str:
        """
        Extract model name from Gemini request.
        
        Args:
            request: The request payload
            
        Returns:
            Model name
        """
        # Gemini model is typically in the URL, not the payload
        return request.get("model", "gemini-pro")
