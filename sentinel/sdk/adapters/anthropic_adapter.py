"""Anthropic API adapter for Sentinel SDK."""

import json
import logging
from typing import Any, Dict, List

from sentinel.sdk.llm_adapter import LLMAdapter, LLMRequest, ToolCall


logger = logging.getLogger(__name__)


class AnthropicAdapter(LLMAdapter):
    """Adapter for Anthropic Claude API integration."""
    
    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "Anthropic"
    
    def can_handle(self, endpoint: str, headers: Dict[str, str]) -> bool:
        """
        Determine if this is an Anthropic API request.
        
        Args:
            endpoint: The API endpoint URL
            headers: Request headers
            
        Returns:
            True if this is an Anthropic request
        """
        # Check for Anthropic API endpoint
        if "api.anthropic.com" in endpoint:
            return True
        
        # Check for Anthropic API key header
        if "x-api-key" in headers:
            api_key = headers.get("x-api-key", "")
            if api_key.startswith("sk-ant-"):
                return True
        
        return False
    
    def extract_tool_calls(self, response: Dict[str, Any]) -> List[ToolCall]:
        """
        Extract tool calls from Anthropic API response.
        
        Anthropic response format:
        {
            "id": "msg_123",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_123",
                    "name": "get_weather",
                    "input": {
                        "location": "San Francisco"
                    }
                }
            ]
        }
        
        Args:
            response: The Anthropic API response
            
        Returns:
            List of extracted ToolCall objects
        """
        tool_calls = []
        
        try:
            content = response.get("content", [])
            if not content:
                return tool_calls
            
            for content_block in content:
                if content_block.get("type") != "tool_use":
                    continue
                
                tool_name = content_block.get("name")
                tool_input = content_block.get("input", {})
                tool_id = content_block.get("id", "")
                
                tool_call = ToolCall(
                    id=tool_id,
                    name=tool_name,
                    arguments=tool_input,
                    metadata={
                        "provider": "anthropic",
                        "type": "tool_use"
                    }
                )
                tool_calls.append(tool_call)
            
            logger.debug(f"Extracted {len(tool_calls)} tool calls from Anthropic response")
            
        except Exception as e:
            logger.error(f"Error extracting tool calls from Anthropic response: {e}")
        
        return tool_calls
    
    def intercept_request(self, request: LLMRequest) -> LLMRequest:
        """
        Intercept Anthropic request.
        
        Can be used to:
        - Log request metadata
        - Modify parameters
        - Add tracking metadata
        
        Args:
            request: The original request
            
        Returns:
            The potentially modified request
        """
        # Log the request
        payload = request.payload
        model = payload.get("model", "unknown")
        tools = payload.get("tools", [])
        
        logger.debug(
            f"Anthropic request: model={model}, tools={len(tools)}"
        )
        
        # Could add modifications here, e.g.:
        # - Enforce max_tokens limit
        # - Add required system prompts
        # - Modify tool definitions
        
        return request
    
    def intercept_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Intercept Anthropic response.
        
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
                f"Anthropic usage: "
                f"input_tokens={usage.get('input_tokens', 0)}, "
                f"output_tokens={usage.get('output_tokens', 0)}"
            )
        
        # Log stop reason
        stop_reason = response.get("stop_reason")
        if stop_reason:
            logger.debug(f"Anthropic stop_reason: {stop_reason}")
        
        # Could add modifications here, e.g.:
        # - Mask PII in content
        # - Filter out blocked tool calls
        # - Add audit metadata
        
        return response
    
    def get_model_from_request(self, request: Dict[str, Any]) -> str:
        """
        Extract model name from Anthropic request.
        
        Args:
            request: The request payload
            
        Returns:
            Model name
        """
        return request.get("model", "claude-3-opus-20240229")
