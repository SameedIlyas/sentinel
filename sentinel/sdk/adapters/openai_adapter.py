"""OpenAI API adapter for Sentinel SDK."""

import json
import logging
from typing import Any, Dict, List

from sentinel.sdk.llm_adapter import LLMAdapter, LLMRequest, ToolCall


logger = logging.getLogger(__name__)


class OpenAIAdapter(LLMAdapter):
    """Adapter for OpenAI API integration."""
    
    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "OpenAI"
    
    def can_handle(self, endpoint: str, headers: Dict[str, str]) -> bool:
        """
        Determine if this is an OpenAI API request.
        
        Args:
            endpoint: The API endpoint URL
            headers: Request headers
            
        Returns:
            True if this is an OpenAI request
        """
        # Check for OpenAI API endpoint
        if "api.openai.com" in endpoint:
            return True
        
        # Check for OpenAI authorization header pattern
        auth_header = headers.get("Authorization", "")
        if auth_header.startswith("Bearer sk-"):
            return True
        
        return False
    
    def extract_tool_calls(self, response: Dict[str, Any]) -> List[ToolCall]:
        """
        Extract tool calls from OpenAI API response.
        
        OpenAI response format:
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": null,
                        "tool_calls": [
                            {
                                "id": "call_abc123",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": "{\"location\": \"San Francisco\"}"
                                }
                            }
                        ]
                    }
                }
            ]
        }
        
        Args:
            response: The OpenAI API response
            
        Returns:
            List of extracted ToolCall objects
        """
        tool_calls = []
        
        try:
            choices = response.get("choices", [])
            if not choices:
                return tool_calls
            
            message = choices[0].get("message", {})
            raw_tool_calls = message.get("tool_calls", [])
            
            for raw_call in raw_tool_calls:
                if raw_call.get("type") != "function":
                    continue
                
                function_data = raw_call.get("function", {})
                function_name = function_data.get("name")
                function_args_str = function_data.get("arguments", "{}")
                
                # Parse arguments JSON string
                try:
                    arguments = json.loads(function_args_str)
                except json.JSONDecodeError:
                    logger.warning(
                        f"Failed to parse function arguments for {function_name}: {function_args_str}"
                    )
                    arguments = {}
                
                tool_call = ToolCall(
                    id=raw_call.get("id", ""),
                    name=function_name,
                    arguments=arguments,
                    metadata={
                        "provider": "openai",
                        "type": "function"
                    }
                )
                tool_calls.append(tool_call)
            
            logger.debug(f"Extracted {len(tool_calls)} tool calls from OpenAI response")
            
        except Exception as e:
            logger.error(f"Error extracting tool calls from OpenAI response: {e}")
        
        return tool_calls
    
    def intercept_request(self, request: LLMRequest) -> LLMRequest:
        """
        Intercept OpenAI request.
        
        Can be used to:
        - Log request metadata
        - Modify parameters (e.g., enforce temperature limits)
        - Add tracking headers
        
        Args:
            request: The original request
            
        Returns:
            The potentially modified request
        """
        # Log the request
        payload = request.payload
        model = payload.get("model", "unknown")
        tools = payload.get("tools", [])
        functions = payload.get("functions", [])
        
        logger.debug(
            f"OpenAI request: model={model}, "
            f"tools={len(tools)}, functions={len(functions)}"
        )
        
        # Could add modifications here, e.g.:
        # - Enforce max_tokens limit
        # - Add required system instructions
        # - Modify tool definitions
        
        return request
    
    def intercept_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Intercept OpenAI response.
        
        Can be used to:
        - Log response metadata
        - Mask sensitive data
        - Track token usage
        
        Args:
            response: The original response
            
        Returns:
            The potentially modified response
        """
        # Log usage
        usage = response.get("usage", {})
        if usage:
            logger.debug(
                f"OpenAI usage: "
                f"prompt_tokens={usage.get('prompt_tokens', 0)}, "
                f"completion_tokens={usage.get('completion_tokens', 0)}, "
                f"total_tokens={usage.get('total_tokens', 0)}"
            )
        
        # Could add modifications here, e.g.:
        # - Mask PII in content
        # - Filter out blocked tool calls
        # - Add audit metadata
        
        return response
    
    def get_model_from_request(self, request: Dict[str, Any]) -> str:
        """
        Extract model name from OpenAI request.
        
        Args:
            request: The request payload
            
        Returns:
            Model name
        """
        return request.get("model", "gpt-4")
