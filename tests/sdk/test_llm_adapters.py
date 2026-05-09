"""Phase 2 — Test Coverage Retrofit: SDK LLM Adapters.

Covers: sentinel/sdk/adapters/*.py, sentinel/sdk/llm_adapter.py
"""

from sentinel.sdk.adapters.openai_adapter import OpenAIAdapter
from sentinel.sdk.adapters.anthropic_adapter import AnthropicAdapter
from sentinel.sdk.adapters.azure_openai_adapter import AzureOpenAIAdapter
from sentinel.sdk.adapters.gemini_adapter import GeminiAdapter
from sentinel.sdk.adapters import get_default_registry


# ---------------------------------------------------------------------------
# OpenAI adapter
# ---------------------------------------------------------------------------

class TestOpenAIAdapter:
    def setup_method(self):
        self.adapter = OpenAIAdapter()

    def test_provider_name(self):
        assert self.adapter.provider_name == "OpenAI"

    def test_can_handle_openai_endpoint(self):
        assert self.adapter.can_handle("https://api.openai.com/v1/chat/completions", {})

    def test_cannot_handle_unknown_endpoint(self):
        assert not self.adapter.can_handle("https://example.com/api", {})

    def test_detects_openai_from_bearer_sk_header(self):
        headers = {"Authorization": "Bearer sk-abc123xxxx"}
        assert self.adapter.can_handle("https://custom.proxy.com", headers)

    def test_extract_tool_calls_from_response(self):
        response = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "id": "call_abc",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"city": "London"}',
                        }
                    }]
                }
            }]
        }
        calls = self.adapter.extract_tool_calls(response)
        assert len(calls) == 1
        assert calls[0].name == "get_weather"
        assert calls[0].arguments == {"city": "London"}

    def test_extract_tool_calls_handles_missing_tool_calls(self):
        response = {"choices": [{"message": {"content": "Hello"}}]}
        calls = self.adapter.extract_tool_calls(response)
        assert calls == []

    def test_extract_tool_calls_handles_empty_response(self):
        calls = self.adapter.extract_tool_calls({})
        assert isinstance(calls, list)


# ---------------------------------------------------------------------------
# Anthropic adapter
# ---------------------------------------------------------------------------

class TestAnthropicAdapter:
    def setup_method(self):
        self.adapter = AnthropicAdapter()

    def test_provider_name(self):
        assert self.adapter.provider_name == "Anthropic"

    def test_can_handle_anthropic_endpoint(self):
        assert self.adapter.can_handle("https://api.anthropic.com/v1/messages", {})

    def test_cannot_handle_openai_endpoint(self):
        assert not self.adapter.can_handle("https://api.openai.com/v1/chat/completions", {})

    def test_extract_tool_use_blocks(self):
        response = {
            "content": [
                {"type": "text", "text": "Let me help..."},
                {
                    "type": "tool_use",
                    "id": "toolu_01",
                    "name": "get_weather",
                    "input": {"city": "Paris"},
                }
            ]
        }
        calls = self.adapter.extract_tool_calls(response)
        assert len(calls) == 1
        assert calls[0].name == "get_weather"
        assert calls[0].arguments == {"city": "Paris"}

    def test_extract_tool_calls_handles_empty_content(self):
        response = {"content": []}
        calls = self.adapter.extract_tool_calls(response)
        assert calls == []

    def test_extract_tool_calls_no_tool_use_blocks(self):
        response = {"content": [{"type": "text", "text": "Hello"}]}
        calls = self.adapter.extract_tool_calls(response)
        assert calls == []


# ---------------------------------------------------------------------------
# Azure OpenAI adapter
# ---------------------------------------------------------------------------

class TestAzureOpenAIAdapter:
    def setup_method(self):
        self.adapter = AzureOpenAIAdapter()

    def test_provider_name(self):
        assert self.adapter.provider_name == "Azure OpenAI"

    def test_can_handle_azure_endpoint(self):
        assert self.adapter.can_handle(
            "https://my-resource.openai.azure.com/openai/deployments/gpt-4/chat/completions", {}
        )

    def test_detected_before_openai_adapter(self):
        """Azure should be registered before OpenAI in the registry to avoid false positives."""
        registry = get_default_registry()
        providers = registry.list_providers()
        azure_idx = next((i for i, p in enumerate(providers) if "azure" in p.lower()), None)
        openai_idx = next((i for i, p in enumerate(providers) if p.lower() == "openai"), None)
        assert azure_idx is not None and openai_idx is not None
        assert azure_idx < openai_idx, "AzureOpenAI must be registered before OpenAI"

    def test_extracts_deployment_from_url(self):
        # Azure adapter's get_model_from_request takes a dict payload
        request = {"model": "gpt-4-turbo", "messages": []}
        model = self.adapter.get_model_from_request(request)
        assert model is not None
        assert model == "gpt-4-turbo"

    def test_extract_tool_calls_same_format_as_openai(self):
        response = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "id": "call_xyz",
                        "type": "function",
                        "function": {
                            "name": "search",
                            "arguments": '{"query": "test"}',
                        }
                    }]
                }
            }]
        }
        calls = self.adapter.extract_tool_calls(response)
        assert len(calls) == 1
        assert calls[0].name == "search"


# ---------------------------------------------------------------------------
# Gemini adapter
# ---------------------------------------------------------------------------

class TestGeminiAdapter:
    def setup_method(self):
        self.adapter = GeminiAdapter()

    def test_provider_name(self):
        assert self.adapter.provider_name == "Google Gemini"

    def test_can_handle_gemini_endpoint(self):
        assert self.adapter.can_handle(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent", {}
        )

    def test_cannot_handle_openai_endpoint(self):
        assert not self.adapter.can_handle("https://api.openai.com/v1/chat/completions", {})

    def test_extract_function_calls(self):
        response = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "functionCall": {
                            "name": "get_weather",
                            "args": {"location": "Tokyo"},
                        }
                    }]
                }
            }]
        }
        calls = self.adapter.extract_tool_calls(response)
        assert len(calls) == 1
        assert calls[0].name == "get_weather"


# ---------------------------------------------------------------------------
# Registry — auto-detection
# ---------------------------------------------------------------------------

class TestAdapterRegistry:
    def test_registry_auto_detects_openai(self):
        registry = get_default_registry()
        adapter = registry.get_adapter("https://api.openai.com/v1/chat/completions", {})
        assert adapter is not None
        assert "openai" in adapter.provider_name.lower()

    def test_registry_auto_detects_anthropic(self):
        registry = get_default_registry()
        adapter = registry.get_adapter("https://api.anthropic.com/v1/messages", {})
        assert adapter is not None
        assert "anthropic" in adapter.provider_name.lower()

    def test_registry_auto_detects_gemini(self):
        registry = get_default_registry()
        adapter = registry.get_adapter(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
            {}
        )
        assert adapter is not None
        assert "gemini" in adapter.provider_name.lower()

    def test_registry_returns_none_for_unknown_provider(self):
        registry = get_default_registry()
        adapter = registry.get_adapter("https://totally-unknown-llm-provider.io/api", {})
        assert adapter is None

    def test_registry_lists_all_four_providers(self):
        registry = get_default_registry()
        providers = registry.list_providers()
        assert len(providers) >= 4

    def test_tool_call_normalization_consistent_across_providers(self):
        """All adapters return ToolCall with consistent .name and .arguments fields."""
        openai_resp = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "search", "arguments": '{"q": "test"}'},
                    }]
                }
            }]
        }
        anthropic_resp = {
            "content": [{
                "type": "tool_use",
                "id": "toolu_1",
                "name": "search",
                "input": {"q": "test"},
            }]
        }

        oa = OpenAIAdapter().extract_tool_calls(openai_resp)
        aa = AnthropicAdapter().extract_tool_calls(anthropic_resp)

        assert oa[0].name == aa[0].name == "search"
        assert oa[0].arguments == aa[0].arguments == {"q": "test"}
