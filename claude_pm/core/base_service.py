"""
Base service class for Claude PM Framework services.

Provides common functionality including:
- Lifecycle management (start, stop, health checks)
- Configuration management
- Logging
- Metrics collection
- Error handling and retry logic
- Service discovery and registration
"""

import asyncio
import logging
import signal
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import json

from .config import Config
from .logging_config import setup_logging


@dataclass
class ServiceHealth:
    """Service health status information."""
    status: str  # healthy, degraded, unhealthy, unknown
    message: str
    timestamp: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    checks: Dict[str, bool] = field(default_factory=dict)


@dataclass
class ServiceMetrics:
    """Service metrics collection."""
    requests_total: int = 0
    requests_failed: int = 0
    response_time_avg: float = 0.0
    uptime_seconds: int = 0
    memory_usage_mb: float = 0.0
    custom_metrics: Dict[str, Any] = field(default_factory=dict)


class BaseService(ABC):
    """
    Abstract base class for all Claude PM services.
    
    Provides common infrastructure for service lifecycle management,
    health monitoring, configuration, logging, and error handling.
    """
    
    def __init__(
        self, 
        name: str, 
        config: Optional[Dict[str, Any]] = None,
        config_path: Optional[Path] = None
    ):
        """
        Initialize the base service.
        
        Args:
            name: Service name for identification
            config: Optional configuration dictionary
            config_path: Optional path to configuration file
        """
        self.name = name
        self.config = Config(config or {}, config_path)
        self.logger = setup_logging(name, self.config.get("log_level", "INFO"))
        
        # Service state
        self._running = False
        self._start_time: Optional[datetime] = None
        self._stop_event = asyncio.Event()
        
        # Health and metrics
        self._health = ServiceHealth(
            status="unknown",
            message="Service not started",
            timestamp=datetime.now().isoformat()
        )
        self._metrics = ServiceMetrics()
        
        # Background tasks
        self._background_tasks: List[asyncio.Task] = []
        
        self.logger.info(f"Initialized {self.name} service")
    
    @property
    def running(self) -> bool:
        """Check if service is currently running."""
        return self._running
    
    @property
    def uptime(self) -> Optional[float]:
        """Get service uptime in seconds."""
        if self._start_time and self._running:
            return (datetime.now() - self._start_time).total_seconds()
        return None
    
    @property
    def health(self) -> ServiceHealth:
        """Get current service health status."""
        return self._health
    
    @property
    def metrics(self) -> ServiceMetrics:
        """Get current service metrics."""
        if self.uptime:
            self._metrics.uptime_seconds = int(self.uptime)
        return self._metrics
    
    async def start(self) -> None:
        """Start the service."""
        if self._running:
            self.logger.warning(f"Service {self.name} is already running")
            return
        
        self.logger.info(f"Starting {self.name} service...")
        
        try:
            # Setup signal handlers
            self._setup_signal_handlers()
            
            # Initialize service
            await self._initialize()
            
            # Start background tasks
            await self._start_background_tasks()
            
            # Mark as running
            self._running = True
            self._start_time = datetime.now()
            
            # Update health status
            self._health = ServiceHealth(
                status="healthy",
                message="Service started successfully",
                timestamp=datetime.now().isoformat(),
                checks={"startup": True}
            )
            
            self.logger.info(f"Service {self.name} started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start service {self.name}: {e}")
            self._health = ServiceHealth(
                status="unhealthy",
                message=f"Startup failed: {str(e)}",
                timestamp=datetime.now().isoformat(),
                checks={"startup": False}
            )
            raise
    
    async def stop(self) -> None:
        """Stop the service gracefully."""
        if not self._running:
            self.logger.warning(f"Service {self.name} is not running")
            return
        
        self.logger.info(f"Stopping {self.name} service...")
        
        try:
            # Signal stop to background tasks
            self._stop_event.set()
            
            # Cancel background tasks
            for task in self._background_tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete
            if self._background_tasks:
                await asyncio.gather(*self._background_tasks, return_exceptions=True)
            
            # Cleanup service
            await self._cleanup()
            
            # Mark as stopped
            self._running = False
            
            # Update health status
            self._health = ServiceHealth(
                status="unknown",
                message="Service stopped",
                timestamp=datetime.now().isoformat(),
                checks={"running": False}
            )
            
            self.logger.info(f"Service {self.name} stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Error stopping service {self.name}: {e}")
            raise
    
    async def restart(self) -> None:
        """Restart the service."""
        self.logger.info(f"Restarting {self.name} service...")
        await self.stop()
        await self.start()
    
    async def health_check(self) -> ServiceHealth:
        """
        Perform comprehensive health check.
        
        Returns:
            ServiceHealth object with current status
        """
        try:
            checks = {}
            
            # Basic running check
            checks["running"] = self._running
            
            # Custom health checks
            custom_checks = await self._health_check()
            checks.update(custom_checks)
            
            # Determine overall status
            if not checks["running"]:
                status = "unhealthy"
                message = "Service is not running"
            elif all(checks.values()):
                status = "healthy" 
                message = "All health checks passed"
            elif any(checks.values()):
                status = "degraded"
                message = "Some health checks failed"
            else:
                status = "unhealthy"
                message = "Multiple health checks failed"
            
            # Update health status
            self._health = ServiceHealth(
                status=status,
                message=message,
                timestamp=datetime.now().isoformat(),
                checks=checks,
                metrics={
                    "uptime": self.uptime,
                    "requests_total": self._metrics.requests_total,
                    "requests_failed": self._metrics.requests_failed
                }
            )
            
            return self._health
            
        except Exception as e:
            self.logger.error(f"Health check failed for {self.name}: {e}")
            self._health = ServiceHealth(
                status="unhealthy",
                message=f"Health check error: {str(e)}",
                timestamp=datetime.now().isoformat(),
                checks={"health_check_error": True}
            )
            return self._health
    
    def update_metrics(self, **kwargs) -> None:
        """Update service metrics."""
        for key, value in kwargs.items():
            if hasattr(self._metrics, key):
                setattr(self._metrics, key, value)
            else:
                self._metrics.custom_metrics[key] = value
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self.config.get(key, default)
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def _start_background_tasks(self) -> None:
        """Start background tasks."""
        # Health check task
        if self.get_config("enable_health_monitoring", True):
            interval = self.get_config("health_check_interval", 30)
            task = asyncio.create_task(self._health_monitor_task(interval))
            self._background_tasks.append(task)
        
        # Metrics collection task
        if self.get_config("enable_metrics", True):
            interval = self.get_config("metrics_interval", 60)
            task = asyncio.create_task(self._metrics_task(interval))
            self._background_tasks.append(task)
        
        # Custom background tasks
        custom_tasks = await self._start_custom_tasks()
        if custom_tasks:
            self._background_tasks.extend(custom_tasks)
    
    async def _health_monitor_task(self, interval: int) -> None:
        """Background task for periodic health monitoring."""
        while not self._stop_event.is_set():
            try:
                await self.health_check()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health monitor task error: {e}")
                await asyncio.sleep(interval)
    
    async def _metrics_task(self, interval: int) -> None:
        """Background task for metrics collection."""
        while not self._stop_event.is_set():
            try:
                await self._collect_metrics()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Metrics task error: {e}")
                await asyncio.sleep(interval)
    
    async def _collect_metrics(self) -> None:
        """Collect service metrics."""
        try:
            # Update uptime
            if self.uptime:
                self._metrics.uptime_seconds = int(self.uptime)
            
            # Memory usage (basic implementation)
            import psutil
            process = psutil.Process()
            self._metrics.memory_usage_mb = process.memory_info().rss / 1024 / 1024
            
            # Custom metrics collection
            await self._collect_custom_metrics()
            
        except Exception as e:
            self.logger.warning(f"Failed to collect metrics: {e}")
    
    # Abstract methods to be implemented by subclasses
    
    @abstractmethod
    async def _initialize(self) -> None:
        """Initialize the service. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    async def _cleanup(self) -> None:
        """Cleanup service resources. Must be implemented by subclasses."""
        pass
    
    async def _health_check(self) -> Dict[str, bool]:
        """
        Perform custom health checks. Override in subclasses.
        
        Returns:
            Dictionary of check name -> success boolean
        """
        return {}
    
    async def _start_custom_tasks(self) -> Optional[List[asyncio.Task]]:
        """
        Start custom background tasks. Override in subclasses.
        
        Returns:
            List of asyncio tasks or None
        """
        return None
    
    async def _collect_custom_metrics(self) -> None:
        """Collect custom metrics. Override in subclasses."""
        pass
    
    # Utility methods
    
    async def run_forever(self) -> None:
        """Run the service until stopped."""
        await self.start()
        try:
            # Wait for stop signal
            while self._running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        finally:
            await self.stop()
    
    def __repr__(self) -> str:
        """String representation of the service."""
        return f"<{self.__class__.__name__}(name='{self.name}', running={self._running})>"