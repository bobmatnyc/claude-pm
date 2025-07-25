"""
Health Monitor Service for Claude PM Framework.

Provides comprehensive health monitoring using the Python health monitor
as a service component within the Claude PM service ecosystem.
"""

import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..core.base_service import BaseService


class HealthMonitorService(BaseService):
    """
    Service wrapper for the Claude PM health monitoring system.
    
    Integrates the standalone health monitor into the service framework
    for coordinated lifecycle management and health reporting.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize health monitor service."""
        super().__init__("health_monitor", config)
        
        # Health monitor configuration
        self.check_interval = self.get_config("health_check_interval", 300)  # 5 minutes
        self.enable_background_monitoring = self.get_config("enable_background_monitoring", True)
        self.alert_threshold = self.get_config("alert_threshold", 60)
        
        # Health monitor script path
        self.health_script = Path(__file__).parent.parent.parent / "scripts" / "automated_health_monitor.py"
        
        # Background monitoring process
        self._monitor_process: Optional[subprocess.Popen] = None
        self._last_health_report: Optional[Dict] = None
    
    async def _initialize(self) -> None:
        """Initialize the health monitor service."""
        self.logger.info("Initializing Health Monitor Service...")
        
        # Verify health monitor script exists
        if not self.health_script.exists():
            raise FileNotFoundError(f"Health monitor script not found: {self.health_script}")
        
        # Run initial health check
        await self._run_health_check()
        
        self.logger.info("Health Monitor Service initialized successfully")
    
    async def _cleanup(self) -> None:
        """Cleanup health monitor service."""
        self.logger.info("Cleaning up Health Monitor Service...")
        
        # Stop background monitoring if running
        if self._monitor_process:
            await self._stop_background_monitoring()
        
        self.logger.info("Health Monitor Service cleanup completed")
    
    async def _health_check(self) -> Dict[str, bool]:
        """Perform health monitor service health checks."""
        checks = {}
        
        try:
            # Check if health script is accessible
            checks["health_script_exists"] = self.health_script.exists()
            
            # Check if we can run a basic health check
            checks["can_run_health_check"] = await self._test_health_check()
            
            # Check background monitoring status
            if self.enable_background_monitoring:
                checks["background_monitoring"] = self._monitor_process is not None and self._monitor_process.poll() is None
            else:
                checks["background_monitoring"] = True  # Not required
            
            # Check last health report freshness
            checks["recent_health_data"] = self._is_health_data_recent()
            
        except Exception as e:
            self.logger.error(f"Health monitor service health check failed: {e}")
            checks["health_check_error"] = False
        
        return checks
    
    async def _start_custom_tasks(self) -> Optional[List[asyncio.Task]]:
        """Start custom background tasks."""
        tasks = []
        
        # Background monitoring task
        if self.enable_background_monitoring:
            task = asyncio.create_task(self._background_monitoring_task())
            tasks.append(task)
        
        # Periodic health check task
        task = asyncio.create_task(self._periodic_health_check_task())
        tasks.append(task)
        
        return tasks if tasks else None
    
    async def _run_health_check(self) -> Dict:
        """Run a single health check and return results."""
        try:
            # Run the health monitor script
            result = await asyncio.create_subprocess_exec(
                "python",
                str(self.health_script),
                "once",
                "--verbose" if self.get_config("verbose", False) else "",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                # Try to load the health report
                health_report = await self._load_health_report()
                if health_report:
                    self._last_health_report = health_report
                    self.logger.info("Health check completed successfully")
                    return health_report
                else:
                    self.logger.warning("Health check completed but no report found")
                    return {"status": "completed", "timestamp": datetime.now().isoformat()}
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                self.logger.error(f"Health check failed: {error_msg}")
                return {"status": "failed", "error": error_msg, "timestamp": datetime.now().isoformat()}
                
        except Exception as e:
            self.logger.error(f"Error running health check: {e}")
            return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}
    
    async def _load_health_report(self) -> Optional[Dict]:
        """Load the latest health report from file."""
        try:
            import json
            
            # Default location for health reports
            health_report_path = Path.home() / "Projects" / "Claude-PM" / "logs" / "health-report.json"
            
            if health_report_path.exists():
                with open(health_report_path, 'r') as f:
                    return json.load(f)
            
        except Exception as e:
            self.logger.warning(f"Failed to load health report: {e}")
        
        return None
    
    async def _test_health_check(self) -> bool:
        """Test if we can run a basic health check."""
        try:
            result = await asyncio.create_subprocess_exec(
                "python",
                str(self.health_script),
                "--help",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await result.communicate()
            return result.returncode == 0
            
        except Exception:
            return False
    
    def _is_health_data_recent(self) -> bool:
        """Check if health data is recent (within last hour)."""
        if not self._last_health_report:
            return False
        
        try:
            report_time = datetime.fromisoformat(self._last_health_report.get("timestamp", ""))
            age = (datetime.now() - report_time).total_seconds()
            return age < 3600  # Less than 1 hour old
        except (ValueError, KeyError):
            return False
    
    async def _background_monitoring_task(self) -> None:
        """Background task for continuous health monitoring."""
        self.logger.info("Starting background health monitoring...")
        
        while not self._stop_event.is_set():
            try:
                # Start background monitoring process if not running
                if not self._monitor_process or self._monitor_process.poll() is not None:
                    await self._start_background_monitoring()
                
                # Wait for interval or stop signal
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Background monitoring task error: {e}")
                await asyncio.sleep(60)
        
        # Cleanup on exit
        if self._monitor_process:
            await self._stop_background_monitoring()
    
    async def _start_background_monitoring(self) -> None:
        """Start background health monitoring process."""
        try:
            self.logger.info("Starting background health monitoring process...")
            
            self._monitor_process = await asyncio.create_subprocess_exec(
                "python",
                str(self.health_script),
                "monitor",
                f"--interval={self.check_interval // 60}",  # Convert to minutes
                f"--threshold={self.alert_threshold}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            self.logger.info(f"Background monitoring started with PID: {self._monitor_process.pid}")
            
        except Exception as e:
            self.logger.error(f"Failed to start background monitoring: {e}")
    
    async def _stop_background_monitoring(self) -> None:
        """Stop background health monitoring process."""
        if self._monitor_process:
            try:
                self.logger.info("Stopping background health monitoring...")
                self._monitor_process.terminate()
                
                # Wait for graceful shutdown
                try:
                    await asyncio.wait_for(self._monitor_process.wait(), timeout=10)
                except asyncio.TimeoutError:
                    self.logger.warning("Health monitor didn't stop gracefully, forcing termination")
                    self._monitor_process.kill()
                    await self._monitor_process.wait()
                
                self.logger.info("Background monitoring stopped")
                
            except Exception as e:
                self.logger.error(f"Error stopping background monitoring: {e}")
            finally:
                self._monitor_process = None
    
    async def _periodic_health_check_task(self) -> None:
        """Periodic health check task for service metrics."""
        while not self._stop_event.is_set():
            try:
                # Run health check and update metrics
                health_report = await self._run_health_check()
                
                # Extract metrics from health report
                if health_report and "summary" in health_report:
                    summary = health_report["summary"]
                    self.update_metrics(
                        overall_health_percentage=summary.get("overall_health_percentage", 0),
                        total_projects=summary.get("total_projects", 0),
                        healthy_projects=summary.get("healthy_projects", 0),
                        critical_projects=summary.get("critical_projects", 0)
                    )
                
                # Wait for next check
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Periodic health check error: {e}")
                await asyncio.sleep(self.check_interval)
    
    # Public API methods
    
    async def run_health_check(self) -> Dict:
        """Public method to run a health check on demand."""
        self.logger.info("Running on-demand health check...")
        return await self._run_health_check()
    
    def get_last_health_report(self) -> Optional[Dict]:
        """Get the last health report."""
        return self._last_health_report
    
    async def get_health_status(self) -> Dict:
        """Get current health status summary."""
        if self._last_health_report:
            return {
                "timestamp": self._last_health_report.get("timestamp"),
                "overall_health": self._last_health_report.get("summary", {}).get("overall_health_percentage", 0),
                "total_projects": self._last_health_report.get("summary", {}).get("total_projects", 0),
                "healthy_projects": self._last_health_report.get("summary", {}).get("healthy_projects", 0),
                "alerts": len(self._last_health_report.get("alerts", [])),
                "framework_compliance": self._last_health_report.get("summary", {}).get("framework_compliance", 0)
            }
        else:
            return {
                "timestamp": None,
                "overall_health": 0,
                "total_projects": 0,
                "healthy_projects": 0,
                "alerts": 0,
                "framework_compliance": 0
            }
    
    def is_background_monitoring_active(self) -> bool:
        """Check if background monitoring is active."""
        return (
            self._monitor_process is not None and 
            self._monitor_process.poll() is None
        )