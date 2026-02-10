# Sentinel SDK - LLM Provider Adapters

This module provides adapters for intercepting and monitoring tool calls from multiple LLM providers.

## Supported Providers

The Sentinel SDK supports the following LLM providers out of the box:

1. **OpenAI** - GPT-4, GPT-3.5-turbo with function calling
2. **Anthropic** - Claude 3 (Opus, Sonnet, Haiku) with tool use
3. **Azure OpenAI** - Azure-hosted OpenAI models
4. **Google Gemini** - Gemini Pro with function calling

## How It Works

The adapter system automatically detects which LLM provider you're using based on:
- API endpoint URL patterns
- Authentication header formats
- Request/response structures

When your AI agent makes a call to an LLM API, Sentinel:
1. Intercepts the request before it's sent
2. Extracts tool/function calls from the response
3. Checks each tool call against your security policies
4. Blocks or allows the tool execution
5. Logs everything for audit purposes

## Quick Start

### Basic Usage

```python
from sentinel.sdk import secure_agent

@secure_agent(
    agent_id="my-agent",
    config={
        "api_key": "sentinel_key_xxx",
        "endpoint": "https://api.sentinel.ai"
    }
)
def my_openai_agent():
    import openai
    
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "What's the weather?"}],
        functions=[{
            "name": "get_weather",
            "description": "Get weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                }
            }
        }]
    )
    
    return response
```

The adapter is **automatically detected** - no additional configuration needed!

## Provider-Specific Examples

### OpenAI

```python
import openai

@secure_agent(agent_id="openai-agent", config={...})
def openai_agent():
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[...],
        functions=[...]  # or tools=[...]
    )
    return response
```

**Detection criteria:**
- Endpoint contains `api.openai.com`
- Authorization header starts with `Bearer sk-`

**Extracted data:**
- Function name
- Function arguments (parsed from JSON string)
- Call ID
- Model used

### Anthropic Claude

```python
import anthropic

@secure_agent(agent_id="claude-agent", config={...})
def claude_agent():
    client = anthropic.Anthropic(api_key="sk-ant-xxx")
    
    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=1024,
        tools=[{
            "name": "get_weather",
            "description": "Get weather",
            "input_schema": {...}
        }],
        messages=[...]
    )
    return response
```

**Detection criteria:**
- Endpoint contains `api.anthropic.com`
- Header `x-api-key` starts with `sk-ant-`

**Extracted data:**
- Tool name
- Tool input arguments
- Call ID
- Stop reason

### Azure OpenAI

```python
import openai

@secure_agent(agent_id="azure-agent", config={...})
def azure_agent():
    openai.api_type = "azure"
    openai.api_base = "https://your-resource.openai.azure.com/"
    openai.api_version = "2023-12-01-preview"
    
    response = openai.ChatCompletion.create(
        engine="gpt-4-deployment",
        messages=[...],
        functions=[...]
    )
    return response
```

**Detection criteria:**
- Endpoint contains `openai.azure.com`
- Header contains `api-key`
- Endpoint contains `/openai/` and `.azure.com`

**Extracted data:**
- Function name
- Function arguments
- Deployment name
- Model used

### Google Gemini

```python
import google.generativeai as genai

@secure_agent(agent_id="gemini-agent", config={...})
def gemini_agent():
    genai.configure(api_key="your-key")
    
    model = genai.GenerativeModel(
        model_name="gemini-pro",
        tools=[{
            "name": "get_weather",
            "description": "Get weather",
            "parameters": {...}
        }]
    )
    
    response = model.generate_content("What's the weather?")
    return response
```

**Detection criteria:**
- Endpoint contains `generativelanguage.googleapis.com`
- Endpoint contains `/models/gemini`

**Extracted data:**
- Function name
- Function arguments
- Safety ratings
- Token counts

## Advanced Usage

### Manual Adapter Selection

```python
from sentinel.sdk import get_default_registry

# Get the adapter registry
registry = get_default_registry()

# List all providers
providers = registry.list_providers()
print(providers)  # ['Azure OpenAI', 'OpenAI', 'Anthropic', 'Google Gemini']

# Get specific adapter
openai_adapter = registry.get_adapter_by_name("OpenAI")

# Manually extract tool calls from a response
tool_calls = openai_adapter.extract_tool_calls(response_dict)
```

### Custom Adapter

Create your own adapter for proprietary LLMs:

```python
from sentinel.sdk.llm_adapter import LLMAdapter, LLMRequest, ToolCall
from typing import Dict, List, Any

class MyCustomAdapter(LLMAdapter):
    @property
    def provider_name(self) -> str:
        return "MyLLM"
    
    def can_handle(self, endpoint: str, headers: Dict[str, str]) -> bool:
        return "my-llm.com" in endpoint
    
    def extract_tool_calls(self, response: Dict[str, Any]) -> List[ToolCall]:
        # Parse your custom response format
        tool_calls = []
        for call in response.get("my_tool_calls", []):
            tool_calls.append(ToolCall(
                id=call["id"],
                name=call["function_name"],
                arguments=call["params"],
                metadata={"provider": "my-llm"}
            ))
        return tool_calls
    
    def intercept_request(self, request: LLMRequest) -> LLMRequest:
        # Optionally modify requests
        return request
    
    def intercept_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        # Optionally modify responses
        return response

# Register it
from sentinel.sdk import get_default_registry
registry = get_default_registry()
registry.register(MyCustomAdapter())
```

## Architecture

### ToolCall Object

```python
@dataclass
class ToolCall:
    id: str                          # Unique call identifier
    name: str                        # Function/tool name
    arguments: Dict[str, Any]        # Parsed arguments
    metadata: Optional[Dict[str, Any]]  # Provider-specific metadata
```

### LLMAdapter Interface

All adapters implement:
- `provider_name` - Provider identifier
- `can_handle()` - Auto-detection logic
- `extract_tool_calls()` - Parse tool calls from response
- `intercept_request()` - Pre-process requests
- `intercept_response()` - Post-process responses

### Adapter Priority

Adapters are checked in this order:
1. **Azure OpenAI** (must be before OpenAI to avoid false positives)
2. **OpenAI**
3. **Anthropic**
4. **Google Gemini**
5. Custom adapters (in registration order)

## Response Formats

### OpenAI Format
```json
{
  "choices": [{
    "message": {
      "tool_calls": [{
        "id": "call_123",
        "type": "function",
        "function": {
          "name": "get_weather",
          "arguments": "{\"location\": \"NYC\"}"
        }
      }]
    }
  }]
}
```

### Anthropic Format
```json
{
  "content": [{
    "type": "tool_use",
    "id": "toolu_123",
    "name": "get_weather",
    "input": {"location": "NYC"}
  }]
}
```

### Gemini Format
```json
{
  "candidates": [{
    "content": {
      "parts": [{
        "functionCall": {
          "name": "get_weather",
          "args": {"location": "NYC"}
        }
      }]
    }
  }]
}
```

## Testing

Run the examples:

```bash
cd sentinel/sdk/adapters
python examples.py
```

## Requirements

- Python 3.9+
- Provider-specific SDKs (optional):
  - `openai` for OpenAI/Azure
  - `anthropic` for Claude
  - `google-generativeai` for Gemini

## See Also

- [Main SDK Documentation](../README.md)
- [Policy Configuration Guide](../../policy_engine/README.md)
- [API Reference](../../docs/api.md)
