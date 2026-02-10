"""Azure OpenAI API adapter for Sentinel SDK."""

import json
import logging
from typing import Any, Dict, List

from sentinel.sdk.llm_adapter import LLMAdapter, LLMRequest, ToolCall


logger = logging.getLogger(__name__)


class AzureOpenAIAdapter(LLMAdapter):
    """Adapter for Azure OpenAI API integration."""
    
    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "Azure OpenAI"
    
    def can_handle(self, endpoint: str, headers: Dict[str, str]) -> bool:
        """
        Determine if this is an Azure OpenAI API request.
        
        Args:
            endpoint: The API endpoint URL
            headers: Request headers
            
        Returns:
            True if this is an Azure OpenAI request
        """
        # Check for Azure OpenAI endpoint pattern
        if "openai.azure.com" in endpoint:
            return True
        
        # Check for Azure API key header
        if "api-key" in headers:
            return True
        
        # Check for Azure resource endpoints
        if ".azure.com" in endpoint and "/openai/" in endpoint:
            return True
        
        return False
    
    def extract_tool_calls(self, response: Dict[str, Any]) -> List[ToolCall]:
        """
        Extract tool calls from Azure OpenAI API response.
        
        Azure OpenAI uses the same format as OpenAI:
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
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
            response: The Azure OpenAI API response
            
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
                        "provider": "azure-openai",
                        "type": "function"
                    }
                )
                tool_calls.append(tool_call)
            
            logger.debug(f"Extracted {len(tool_calls)} tool calls from Azure OpenAI response")
            
        except Exception as e:
            logger.error(f"Error extracting tool calls from Azure OpenAI response: {e}")
        
        return tool_calls
    
    def intercept_request(self, request: LLMRequest) -> LLMRequest:
        """
        Intercept Azure OpenAI request.
        
        Can be used to:
        - Log request metadata
        - Handle Azure-specific authentication
        - Modify parameters
        
        Args:
            request: The original request
            
        Returns:
            The potentially modified request
        """
        # Log the request
        payload = request.payload
        
        # Azure uses deployment_id instead of model in some cases
        model = payload.get("model", "unknown")
        
        # Extract deployment from URL if present
        deployment = None
        if "/deployments/" in request.endpoint:
            parts = request.endpoint.split("/deployments/")
            if len(parts) > 1:
                deployment = parts[1].split("/")[0]
        
        tools = payload.get("tools", [])
        functions = payload.get("functions", [])
        
        logger.debug(
            f"Azure OpenAI request: "
            f"deployment={deployment or 'unknown'}, "
            f"model={model}, "
            f"tools={len(tools)}, "
            f"functions={len(functions)}"
        )
        
        # Could add modifications here, e.g.:
        # - Enforce deployment-specific limits
        # - Add Azure-specific tracking headers
        # - Modify tool definitions
        
        return request
    
    def intercept_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Intercept Azure OpenAI response.
        
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
                f"Azure OpenAI usage: "
                f"prompt_tokens={usage.get('prompt_tokens', 0)}, "
                f"completion_tokens={usage.get('completion_tokens', 0)}, "
                f"total_tokens={usage.get('total_tokens', 0)}"
            )
        
        # Could add modifications here, e.g.:
        # - Mask PII in content
        # - Filter out blocked tool calls
        # - Add Azure-specific audit metadata
        
        return response
    
    def get_model_from_request(self, request: Dict[str, Any]) -> str:
        """
        Extract model/deployment name from Azure OpenAI request.
        
        Args:
            request: The request payload
            
        Returns:
            Model or deployment name
        """
        return request.get("model", "gpt-4")
