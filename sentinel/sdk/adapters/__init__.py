"""LLM adapters package for Sentinel SDK."""

from sentinel.sdk.llm_adapter import LLMAdapter, LLMAdapterRegistry, ToolCall
from sentinel.sdk.adapters.openai_adapter import OpenAIAdapter
from sentinel.sdk.adapters.anthropic_adapter import AnthropicAdapter
from sentinel.sdk.adapters.azure_openai_adapter import AzureOpenAIAdapter
from sentinel.sdk.adapters.gemini_adapter import GeminiAdapter


# Create default global registry with all adapters
default_registry = LLMAdapterRegistry()

# Register adapters in priority order
# Azure OpenAI should be checked before regular OpenAI to avoid false positives
default_registry.register(AzureOpenAIAdapter())
default_registry.register(OpenAIAdapter())
default_registry.register(AnthropicAdapter())
default_registry.register(GeminiAdapter())


def get_default_registry() -> LLMAdapterRegistry:
    """
    Get the default adapter registry with all providers registered.
    
    Returns:
        The default LLMAdapterRegistry instance
    """
    return default_registry


__all__ = [
    "LLMAdapter",
    "LLMAdapterRegistry",
    "ToolCall",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "AzureOpenAIAdapter",
    "GeminiAdapter",
    "default_registry",
    "get_default_registry",
]
