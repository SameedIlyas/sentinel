"""SDK module for Sentinel AI."""

from sentinel.sdk.decorator import secure_agent
from sentinel.sdk.client import MiddlewareClient
from sentinel.sdk.interceptor import ToolCallInterceptor
from sentinel.sdk.cache import PolicyCache
from sentinel.sdk.telemetry import TelemetryData, TelemetryCollector, AsyncTelemetrySender
from sentinel.sdk.retry import (
    with_retry,
    retry_on_exception,
    RetryConfig,
    RetryError,
    RetryMetrics,
    get_retry_metrics
)
from sentinel.sdk.llm_adapter import LLMAdapter, LLMAdapterRegistry, ToolCall
from sentinel.sdk.adapters import (
    OpenAIAdapter,
    AnthropicAdapter,
    AzureOpenAIAdapter,
    GeminiAdapter,
    get_default_registry
)

__all__ = [
    "secure_agent",
    "MiddlewareClient",
    "ToolCallInterceptor",
    "PolicyCache",
    "TelemetryData",
    "TelemetryCollector",
    "AsyncTelemetrySender",
    "with_retry",
    "retry_on_exception",
    "RetryConfig",
    "RetryError",
    "RetryMetrics",
    "get_retry_metrics",
    "LLMAdapter",
    "LLMAdapterRegistry",
    "ToolCall",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "AzureOpenAIAdapter",
    "GeminiAdapter",
    "get_default_registry"
]

