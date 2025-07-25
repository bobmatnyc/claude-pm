"""
Configuration management for Claude PM Framework.

Handles loading configuration from files, environment variables,
and default values with proper validation and type conversion.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union
import yaml
import logging

logger = logging.getLogger(__name__)


class Config:
    """
    Configuration manager for Claude PM services.
    
    Supports loading from:
    - Python dictionaries
    - JSON files
    - YAML files  
    - Environment variables
    """
    
    def __init__(
        self, 
        config: Optional[Dict[str, Any]] = None,
        config_file: Optional[Union[str, Path]] = None,
        env_prefix: str = "CLAUDE_PM_"
    ):
        """
        Initialize configuration.
        
        Args:
            config: Base configuration dictionary
            config_file: Path to configuration file (JSON or YAML)
            env_prefix: Prefix for environment variables
        """
        self._config: Dict[str, Any] = {}
        self._env_prefix = env_prefix
        
        # Load base configuration
        if config:
            self._config.update(config)
        
        # Load from file if provided
        if config_file:
            self.load_file(config_file)
        
        # Load from environment variables
        self._load_env_vars()
        
        # Apply defaults
        self._apply_defaults()
    
    def load_file(self, file_path: Union[str, Path]) -> None:
        """Load configuration from file."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.warning(f"Configuration file not found: {file_path}")
            return
        
        try:
            with open(file_path, 'r') as f:
                if file_path.suffix.lower() in ['.yml', '.yaml']:
                    file_config = yaml.safe_load(f)
                elif file_path.suffix.lower() == '.json':
                    file_config = json.load(f)
                else:
                    logger.error(f"Unsupported configuration file format: {file_path}")
                    return
            
            if file_config:
                self._config.update(file_config)
                logger.info(f"Loaded configuration from {file_path}")
                
        except Exception as e:
            logger.error(f"Failed to load configuration from {file_path}: {e}")
    
    def _load_env_vars(self) -> None:
        """Load configuration from environment variables."""
        for key, value in os.environ.items():
            if key.startswith(self._env_prefix):
                config_key = key[len(self._env_prefix):].lower()
                
                # Convert environment variable value to appropriate type
                converted_value = self._convert_env_value(value)
                self._config[config_key] = converted_value
                
                logger.debug(f"Loaded env var: {key} -> {config_key}")
    
    def _convert_env_value(self, value: str) -> Union[str, int, float, bool]:
        """Convert environment variable string to appropriate type."""
        # Boolean conversion
        if value.lower() in ('true', 'yes', '1', 'on'):
            return True
        elif value.lower() in ('false', 'no', '0', 'off'):
            return False
        
        # Numeric conversion
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # Return as string
        return value
    
    def _apply_defaults(self) -> None:
        """Apply default configuration values."""
        defaults = {
            # Logging
            "log_level": "INFO",
            "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            
            # Health monitoring
            "enable_health_monitoring": True,
            "health_check_interval": 30,
            
            # Metrics
            "enable_metrics": True,
            "metrics_interval": 60,
            
            # Service management
            "graceful_shutdown_timeout": 30,
            "startup_timeout": 60,
            
            # Claude PM specific
            "base_path": str(Path.home() / "Projects"),
            "claude_pm_path": str(Path.home() / "Projects" / "Claude-PM"),
            "managed_path": str(Path.home() / "Projects" / "managed"),
            
            # mem0AI integration
            "mem0ai_host": "localhost",
            "mem0ai_port": 8002,
            "mem0ai_timeout": 30,
            
            # Alerting
            "enable_alerting": True,
            "alert_threshold": 60,
            
            # Development
            "debug": False,
            "verbose": False,
        }
        
        # Apply defaults for missing keys
        for key, default_value in defaults.items():
            if key not in self._config:
                self._config[key] = default_value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        # Support nested keys with dot notation
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        # Support nested keys with dot notation
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def update(self, config: Dict[str, Any]) -> None:
        """Update configuration with new values."""
        self._config.update(config)
    
    def to_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary."""
        return self._config.copy()
    
    def save(self, file_path: Union[str, Path], format: str = "json") -> None:
        """Save configuration to file."""
        file_path = Path(file_path)
        
        try:
            with open(file_path, 'w') as f:
                if format.lower() == "json":
                    json.dump(self._config, f, indent=2)
                elif format.lower() in ["yaml", "yml"]:
                    yaml.dump(self._config, f, default_flow_style=False)
                else:
                    raise ValueError(f"Unsupported format: {format}")
            
            logger.info(f"Configuration saved to {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration to {file_path}: {e}")
            raise
    
    def validate(self, schema: Dict[str, Any]) -> bool:
        """
        Validate configuration against a schema.
        
        Args:
            schema: Dictionary defining required keys and types
            
        Returns:
            True if valid, False otherwise
        """
        try:
            for key, expected_type in schema.items():
                if key not in self._config:
                    logger.error(f"Missing required configuration key: {key}")
                    return False
                
                value = self.get(key)
                if not isinstance(value, expected_type):
                    logger.error(
                        f"Configuration key '{key}' has wrong type. "
                        f"Expected {expected_type}, got {type(value)}"
                    )
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation error: {e}")
            return False
    
    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access."""
        return self.get(key)
    
    def __setitem__(self, key: str, value: Any) -> None:
        """Allow dictionary-style assignment."""
        self.set(key, value)
    
    def __contains__(self, key: str) -> bool:
        """Check if configuration contains a key."""
        return self.get(key) is not None
    
    def __repr__(self) -> str:
        """String representation of configuration."""
        return f"<Config({len(self._config)} keys)>"