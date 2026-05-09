"""
Example usage of Sentinel SDK LLM adapters.

This file demonstrates how to use the various LLM provider adapters
to intercept and monitor AI agent tool calls.
"""

from sentinel.sdk import (
    secure_agent,
    get_default_registry
)


# Example 1: Using adapters with the default registry (auto-detection)
# =====================================================================

@secure_agent(
    agent_id="my-openai-agent",
    config={
        "api_key": "sentinel_key_xxx",
        "endpoint": "https://api.sentinel.ai"
    }
)
def openai_agent():
    """
    Example agent using OpenAI.
    The adapter will be auto-detected based on the API endpoint.
    """
    import openai
    
    # Make a regular OpenAI API call with function calling
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "What's the weather in NYC?"}],
        functions=[{
            "name": "get_weather",
            "description": "Get current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                }
            }
        }]
    )
    
    # Sentinel will intercept the response and extract tool calls
    return response


# Example 2: Using Anthropic adapter
# ===================================

@secure_agent(
    agent_id="my-anthropic-agent",
    config={
        "api_key": "sentinel_key_xxx",
        "endpoint": "https://api.sentinel.ai"
    }
)
def anthropic_agent():
    """
    Example agent using Anthropic Claude.
    The adapter will be auto-detected based on the API endpoint.
    """
    import anthropic
    
    client = anthropic.Anthropic(api_key="sk-ant-xxx")
    
    # Make a Claude API call with tool use
    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=1024,
        tools=[{
            "name": "get_weather",
            "description": "Get current weather for a location",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                },
                "required": ["location"]
            }
        }],
        messages=[{"role": "user", "content": "What's the weather in NYC?"}]
    )
    
    # Sentinel will intercept the response and extract tool calls
    return response


# Example 3: Using Azure OpenAI adapter
# ======================================

@secure_agent(
    agent_id="my-azure-agent",
    config={
        "api_key": "sentinel_key_xxx",
        "endpoint": "https://api.sentinel.ai"
    }
)
def azure_openai_agent():
    """
    Example agent using Azure OpenAI.
    The adapter will be auto-detected based on the Azure endpoint.
    """
    import openai
    
    # Configure for Azure
    openai.api_type = "azure"
    openai.api_base = "https://your-resource.openai.azure.com/"
    openai.api_version = "2023-12-01-preview"
    openai.api_key = "your-azure-key"
    
    # Make an Azure OpenAI API call
    response = openai.ChatCompletion.create(
        engine="gpt-4-deployment",  # Azure uses deployment names
        messages=[{"role": "user", "content": "What's the weather in NYC?"}],
        functions=[{
            "name": "get_weather",
            "description": "Get current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                }
            }
        }]
    )
    
    # Sentinel will intercept the response and extract tool calls
    return response


# Example 4: Using Google Gemini adapter
# =======================================

@secure_agent(
    agent_id="my-gemini-agent",
    config={
        "api_key": "sentinel_key_xxx",
        "endpoint": "https://api.sentinel.ai"
    }
)
def gemini_agent():
    """
    Example agent using Google Gemini.
    The adapter will be auto-detected based on the Google API endpoint.
    """
    import google.generativeai as genai
    
    genai.configure(api_key="your-google-api-key")
    
    # Define function declaration
    get_weather_func = {
        "name": "get_weather",
        "description": "Get current weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"}
            },
            "required": ["location"]
        }
    }
    
    # Make a Gemini API call with function calling
    model = genai.GenerativeModel(
        model_name="gemini-pro",
        tools=[get_weather_func]
    )
    
    response = model.generate_content("What's the weather in NYC?")
    
    # Sentinel will intercept the response and extract tool calls
    return response


# Example 5: Manual adapter usage (advanced)
# ==========================================

def manual_adapter_example():
    """
    Example of manually using adapters without auto-detection.
    Useful for testing or custom workflows.
    """
    # Get the default registry
    registry = get_default_registry()
    
    # List all available providers
    providers = registry.list_providers()
    print(f"Available providers: {providers}")
    
    # Get a specific adapter by name
    openai_adapter = registry.get_adapter_by_name("OpenAI")
    
    # Simulate an OpenAI response
    mock_response = {
        "choices": [{
            "message": {
                "role": "assistant",
                "tool_calls": [{
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"location": "New York"}'
                    }
                }]
            }
        }]
    }
    
    # Extract tool calls
    tool_calls = openai_adapter.extract_tool_calls(mock_response)
    
    for tool_call in tool_calls:
        print(f"Tool: {tool_call.name}")
        print(f"Arguments: {tool_call.arguments}")
        print(f"Provider: {tool_call.metadata.get('provider')}")


# Example 6: Custom adapter registration
# =======================================

from sentinel.sdk.llm_adapter import LLMAdapter, LLMRequest, ToolCall
from typing import Dict, List, Any


class CustomLLMAdapter(LLMAdapter):
    """Example custom adapter for a proprietary LLM."""
    
    @property
    def provider_name(self) -> str:
        return "CustomLLM"
    
    def can_handle(self, endpoint: str, headers: Dict[str, str]) -> bool:
        return "custom-llm.com" in endpoint
    
    def extract_tool_calls(self, response: Dict[str, Any]) -> List[ToolCall]:
        # Implement custom extraction logic
        tool_calls = []
        # ... extract from custom response format
        return tool_calls
    
    def intercept_request(self, request: LLMRequest) -> LLMRequest:
        return request
    
    def intercept_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        return response


def register_custom_adapter():
    """Register a custom adapter with the default registry."""
    registry = get_default_registry()
    custom_adapter = CustomLLMAdapter()
    registry.register(custom_adapter)
    print(f"Registered custom adapter: {custom_adapter.provider_name}")


if __name__ == "__main__":
    print("Sentinel SDK LLM Adapter Examples")
    print("=" * 50)
    
    # Show available providers
    registry = get_default_registry()
    providers = registry.list_providers()
    print(f"\nSupported LLM providers: {', '.join(providers)}")
    
    # Run manual example
    print("\n\nManual adapter example:")
    print("-" * 50)
    manual_adapter_example()
    
    # Show custom adapter registration
    print("\n\nCustom adapter registration:")
    print("-" * 50)
    register_custom_adapter()
