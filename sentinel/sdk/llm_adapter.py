"""LLM provider adapter interface for Sentinel SDK."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ToolCall:
    """Represents a tool/function call extracted from an LLM response."""
    
    id: str
    name: str
    arguments: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class LLMRequest:
    """Represents an LLM API request."""
    
    endpoint: str
    headers: Dict[str, str]
    payload: Dict[str, Any]
    method: str = "POST"


@dataclass
class LLMResponse:
    """Represents an LLM API response."""
    
    status_code: int
    headers: Dict[str, str]
    body: Dict[str, Any]
    tool_calls: List[ToolCall]


class LLMAdapter(ABC):
    """Abstract base class for LLM provider adapters."""
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of the LLM provider (e.g., 'openai', 'anthropic')."""
        pass
    
    @abstractmethod
    def can_handle(self, endpoint: str, headers: Dict[str, str]) -> bool:
        """
        Determine if this adapter can handle the given API request.
        
        Args:
            endpoint: The API endpoint URL
            headers: Request headers
            
        Returns:
            True if this adapter can handle the request, False otherwise
        """
        pass
    
    @abstractmethod
    def extract_tool_calls(self, response: Dict[str, Any]) -> List[ToolCall]:
        """
        Extract tool/function calls from an LLM response.
        
        Args:
            response: The LLM API response body
            
        Returns:
            List of ToolCall objects
        """
        pass
    
    @abstractmethod
    def intercept_request(self, request: LLMRequest) -> LLMRequest:
        """
        Intercept and potentially modify an LLM request before it's sent.
        
        Args:
            request: The original LLM request
            
        Returns:
            The potentially modified LLM request
        """
        pass
    
    @abstractmethod
    def intercept_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Intercept and potentially modify an LLM response before it's returned.
        
        Args:
            response: The original LLM response body
            
        Returns:
            The potentially modified LLM response body
        """
        pass
    
    def get_model_from_request(self, request: Dict[str, Any]) -> Optional[str]:
        """
        Extract the model name from a request payload.
        
        Args:
            request: The LLM API request payload
            
        Returns:
            Model name if found, None otherwise
        """
        return request.get("model")
    
    def mask_sensitive_data(self, data: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
        """
        Mask sensitive data in a dictionary.
        
        Args:
            data: The data dictionary
            keys: List of keys to mask
            
        Returns:
            Dictionary with masked values
        """
        masked = data.copy()
        for key in keys:
            if key in masked:
                masked[key] = "***MASKED***"
        return masked


class LLMAdapterRegistry:
    """Registry for LLM adapters with auto-detection capability."""
    
    def __init__(self):
        """Initialize the adapter registry."""
        self._adapters: List[LLMAdapter] = []
        self._adapter_cache: Dict[str, LLMAdapter] = {}
    
    def register(self, adapter: LLMAdapter) -> None:
        """
        Register an LLM adapter.
        
        Args:
            adapter: The adapter to register
        """
        self._adapters.append(adapter)
    
    def get_adapter(self, endpoint: str, headers: Dict[str, str]) -> Optional[LLMAdapter]:
        """
        Auto-detect and return the appropriate adapter for a request.
        
        Args:
            endpoint: The API endpoint URL
            headers: Request headers
            
        Returns:
            The matching adapter, or None if no adapter can handle the request
        """
        # Check cache first
        cache_key = f"{endpoint}:{headers.get('Authorization', '')[:20]}"
        if cache_key in self._adapter_cache:
            return self._adapter_cache[cache_key]
        
        # Find matching adapter
        for adapter in self._adapters:
            if adapter.can_handle(endpoint, headers):
                self._adapter_cache[cache_key] = adapter
                return adapter
        
        return None
    
    def get_adapter_by_name(self, provider_name: str) -> Optional[LLMAdapter]:
        """
        Get an adapter by provider name.
        
        Args:
            provider_name: The provider name (e.g., 'openai', 'anthropic')
            
        Returns:
            The matching adapter, or None if not found
        """
        for adapter in self._adapters:
            if adapter.provider_name.lower() == provider_name.lower():
                return adapter
        return None
    
    def list_providers(self) -> List[str]:
        """
        List all registered provider names.
        
        Returns:
            List of provider names
        """
        return [adapter.provider_name for adapter in self._adapters]
