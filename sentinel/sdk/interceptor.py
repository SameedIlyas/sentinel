"""Tool call interception mechanism for Sentinel SDK."""

import inspect
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional


class ToolCallInterceptor:
    """Captures and processes function calls from AI agents."""
    
    def __init__(self, agent_id: str, user_id: Optional[str] = None):
        """
        Initialize the tool call interceptor.
        
        Args:
            agent_id: Unique identifier for the agent
            user_id: Optional user identifier who triggered the agent
        """
        self.agent_id = agent_id
        self.user_id = user_id
        self._call_history: list[Dict[str, Any]] = []
    
    def intercept(
        self,
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Intercept a function call and extract metadata.
        
        Args:
            func: The function being called
            args: Positional arguments passed to the function
            kwargs: Keyword arguments passed to the function
            context: Additional context information
            
        Returns:
            Dictionary containing call metadata with keys:
                - func_name: Name of the function
                - arguments: Combined args and kwargs
                - context: Execution context
                - timestamp: ISO format timestamp
                - agent_id: Agent identifier
                - user_id: User identifier (if available)
        """
        # Extract function name
        func_name = self._extract_function_name(func)
        
        # Extract and combine arguments
        arguments = self._extract_arguments(func, args, kwargs)
        
        # Build context
        call_context = self._build_context(context)
        
        # Create metadata dictionary
        metadata = {
            "func_name": func_name,
            "arguments": arguments,
            "context": call_context,
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": self.agent_id,
            "user_id": self.user_id,
        }
        
        # Store in history
        self._call_history.append(metadata)
        
        return metadata
    
    def _extract_function_name(self, func: Callable[..., Any]) -> str:
        """
        Extract the function name from a callable.
        
        Args:
            func: The function to extract name from
            
        Returns:
            Function name as string
        """
        if hasattr(func, "__name__"):
            return func.__name__
        elif hasattr(func, "__class__"):
            return func.__class__.__name__
        else:
            return str(func)
    
    def _extract_arguments(
        self,
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract and combine function arguments into a dictionary.
        
        Args:
            func: The function being called
            args: Positional arguments
            kwargs: Keyword arguments
            
        Returns:
            Dictionary mapping parameter names to values
        """
        try:
            # Get function signature
            sig = inspect.signature(func)
            bound_args = sig.bind_partial(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Convert to dictionary
            arguments = dict(bound_args.arguments)
        except (ValueError, TypeError):
            # Fallback if signature inspection fails
            arguments = {
                "_args": args,
                "_kwargs": kwargs
            }
        
        return arguments
    
    def _build_context(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Build execution context with tracking information.
        
        Args:
            context: Optional additional context
            
        Returns:
            Dictionary containing context information
        """
        call_context = {
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Merge additional context if provided
        if context:
            call_context.update(context)
        
        return call_context
    
    def get_call_history(self) -> list[Dict[str, Any]]:
        """
        Get the history of intercepted calls.
        
        Returns:
            List of call metadata dictionaries
        """
        return self._call_history.copy()
    
    def clear_history(self) -> None:
        """Clear the call history."""
        self._call_history.clear()
