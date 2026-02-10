"""Telemetry data collection and async sending for Sentinel SDK."""

import logging
import queue
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TelemetryData:
    """Model for telemetry data structure."""
    
    def __init__(
        self,
        agent_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        timestamp: str,
        user_id: Optional[str] = None,
        decision: Optional[str] = None,
        latency_ms: Optional[float] = None,
        error: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize telemetry data.
        
        Args:
            agent_id: Unique identifier for the agent
            tool_name: Name of the tool/function called
            arguments: Arguments passed to the tool
            timestamp: ISO format timestamp
            user_id: Optional user identifier
            decision: Policy decision (allow/block/require_approval)
            latency_ms: Request latency in milliseconds
            error: Error message if call failed
            context: Additional context information
        """
        self.agent_id = agent_id
        self.tool_name = tool_name
        self.arguments = arguments
        self.timestamp = timestamp
        self.user_id = user_id
        self.decision = decision
        self.latency_ms = latency_ms
        self.error = error
        self.context = context or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert telemetry data to dictionary.
        
        Returns:
            Dictionary representation of telemetry data
        """
        data = {
            "agent_id": self.agent_id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "timestamp": self.timestamp,
        }
        
        if self.user_id:
            data["user_id"] = self.user_id
        if self.decision:
            data["decision"] = self.decision
        if self.latency_ms is not None:
            data["latency_ms"] = self.latency_ms
        if self.error:
            data["error"] = self.error
        if self.context:
            data["context"] = self.context
        
        return data


class TelemetryCollector:
    """Collects and batches telemetry data for async sending."""
    
    def __init__(
        self,
        batch_size: int = 10,
        batch_timeout: float = 5.0,
        max_queue_size: int = 1000
    ):
        """
        Initialize the telemetry collector.
        
        Args:
            batch_size: Number of events to batch before sending (default: 10)
            batch_timeout: Maximum time to wait before sending partial batch in seconds (default: 5.0)
            max_queue_size: Maximum size of the telemetry queue (default: 1000)
        """
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.max_queue_size = max_queue_size
        
        self._queue: queue.Queue[TelemetryData] = queue.Queue(maxsize=max_queue_size)
        self._batch: List[TelemetryData] = []
        self._last_send_time = time.time()
        self._lock = threading.Lock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._send_callback: Optional[Any] = None
        
        logger.info(
            f"Initialized TelemetryCollector "
            f"(batch_size={batch_size}, batch_timeout={batch_timeout}s)"
        )
    
    def start(self, send_callback: Any) -> None:
        """
        Start the telemetry collector worker thread.
        
        Args:
            send_callback: Callback function to send batched telemetry data
                          Should accept List[Dict[str, Any]] as argument
        """
        if self._running:
            logger.warning("TelemetryCollector already running")
            return
        
        self._send_callback = send_callback
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker,
            daemon=True,
            name="TelemetryWorker"
        )
        self._worker_thread.start()
        logger.info("Started telemetry collector worker thread")
    
    def stop(self, timeout: float = 5.0) -> None:
        """
        Stop the telemetry collector and flush remaining data.
        
        Args:
            timeout: Maximum time to wait for worker thread to finish
        """
        if not self._running:
            return
        
        self._running = False
        
        # Flush any remaining data
        self._flush_batch()
        
        # Wait for worker thread to finish
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)
        
        logger.info("Stopped telemetry collector")
    
    def collect(self, telemetry_data: TelemetryData) -> None:
        """
        Collect a telemetry data point.
        
        Args:
            telemetry_data: Telemetry data to collect
        """
        try:
            self._queue.put_nowait(telemetry_data)
        except queue.Full:
            logger.warning("Telemetry queue full, dropping event")
    
    def _worker(self) -> None:
        """Worker thread that processes telemetry queue and sends batches."""
        while self._running:
            try:
                # Try to get item from queue with timeout
                try:
                    telemetry_data = self._queue.get(timeout=0.5)
                    self._add_to_batch(telemetry_data)
                except queue.Empty:
                    pass
                
                # Check if we should send the batch
                current_time = time.time()
                should_send = (
                    len(self._batch) >= self.batch_size or
                    (len(self._batch) > 0 and 
                     current_time - self._last_send_time >= self.batch_timeout)
                )
                
                if should_send:
                    self._flush_batch()
                
            except Exception as e:
                logger.error(f"Error in telemetry worker: {e}")
    
    def _add_to_batch(self, telemetry_data: TelemetryData) -> None:
        """
        Add telemetry data to the current batch.
        
        Args:
            telemetry_data: Telemetry data to add
        """
        with self._lock:
            self._batch.append(telemetry_data)
    
    def _flush_batch(self) -> None:
        """Send the current batch of telemetry data."""
        with self._lock:
            if not self._batch:
                return
            
            batch_to_send = self._batch.copy()
            self._batch.clear()
            self._last_send_time = time.time()
        
        # Send batch outside of lock
        if self._send_callback:
            try:
                batch_dicts = [data.to_dict() for data in batch_to_send]
                self._send_callback(batch_dicts)
                logger.debug(f"Sent telemetry batch with {len(batch_to_send)} events")
            except Exception as e:
                logger.error(f"Failed to send telemetry batch: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get telemetry collector statistics.
        
        Returns:
            Dictionary with collector statistics
        """
        with self._lock:
            return {
                "queue_size": self._queue.qsize(),
                "batch_size": len(self._batch),
                "running": self._running,
                "max_queue_size": self.max_queue_size,
                "configured_batch_size": self.batch_size,
                "batch_timeout": self.batch_timeout
            }


class AsyncTelemetrySender:
    """Async telemetry sender that integrates with MiddlewareClient."""
    
    def __init__(
        self,
        middleware_client: Any,
        batch_size: int = 10,
        batch_timeout: float = 5.0
    ):
        """
        Initialize the async telemetry sender.
        
        Args:
            middleware_client: MiddlewareClient instance for sending data
            batch_size: Number of events to batch before sending
            batch_timeout: Maximum time to wait before sending partial batch
        """
        self.middleware_client = middleware_client
        self.collector = TelemetryCollector(
            batch_size=batch_size,
            batch_timeout=batch_timeout
        )
        
        # Start the collector with send callback
        self.collector.start(send_callback=self._send_batch)
        
        logger.info("Initialized AsyncTelemetrySender")
    
    def send(self, telemetry_data: TelemetryData) -> None:
        """
        Send telemetry data asynchronously.
        
        Args:
            telemetry_data: Telemetry data to send
        """
        self.collector.collect(telemetry_data)
    
    def _send_batch(self, batch: List[Dict[str, Any]]) -> None:
        """
        Send a batch of telemetry data to middleware.
        
        Args:
            batch: List of telemetry data dictionaries
        """
        try:
            # Send batch to middleware
            self.middleware_client.send_telemetry({
                "events": batch,
                "batch_timestamp": datetime.utcnow().isoformat(),
                "batch_size": len(batch)
            })
        except Exception as e:
            logger.error(f"Failed to send telemetry batch to middleware: {e}")
    
    def stop(self) -> None:
        """Stop the telemetry sender and flush remaining data."""
        self.collector.stop()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get telemetry sender statistics.
        
        Returns:
            Dictionary with sender statistics
        """
        return self.collector.get_stats()
