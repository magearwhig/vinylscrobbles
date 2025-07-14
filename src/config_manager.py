"""
Configuration Manager

Handles loading and managing configuration from JSON files and environment variables.
Provides secure API key management and runtime configuration updates.
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import copy

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages application configuration from multiple sources."""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "config.json"
        self.example_config_file = self.config_dir / "config.example.json"
        self.secrets_file = self.config_dir / "secrets.env"
        self.example_secrets_file = self.config_dir / "secrets.example.env"
        
        self._config: Dict[str, Any] = {}
        self._secrets: Dict[str, str] = {}
        
        self._load_configuration()
    
    def _load_configuration(self):
        """Load configuration from files and environment variables."""
        try:
            self._load_config_file()
            self._load_secrets()
            logger.info("Configuration loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    def _load_config_file(self):
        """Load main configuration from JSON file."""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                self._config = json.load(f)
        elif self.example_config_file.exists():
            logger.warning(f"No config.json found, copying from example")
            with open(self.example_config_file, 'r') as f:
                self._config = json.load(f)
            self.save_config()
        else:
            raise FileNotFoundError(f"No configuration file found in {self.config_dir}")
    
    def _load_secrets(self):
        """Load secrets from environment file and system environment."""
        if self.secrets_file.exists():
            with open(self.secrets_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        self._secrets[key.strip()] = value.strip()
        
        for key, value in os.environ.items():
            if key.startswith(('LASTFM_', 'AUDD_', 'FLASK_', 'SHAZAM_', 'ACRCLOUD_')):
                self._secrets[key] = value
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path to configuration value
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        try:
            value = self._config
            for key in key_path.split('.'):
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path: str, value: Any) -> None:
        """
        Set configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path to configuration value
            value: Value to set
        """
        keys = key_path.split('.')
        config = self._config
        
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        config[keys[-1]] = value
    
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get secret value from environment.
        
        Args:
            key: Secret key name
            default: Default value if secret not found
            
        Returns:
            Secret value or default
        """
        return self._secrets.get(key, default)
    
    def has_secret(self, key: str) -> bool:
        """Check if secret exists."""
        return key in self._secrets and self._secrets[key] is not None
    
    def validate_secrets(self) -> Dict[str, bool]:
        """
        Validate that required secrets are present.
        
        Returns:
            Dictionary of secret validation results
        """
        required_secrets = {
            'LASTFM_API_KEY': 'Last.fm API key',
            'LASTFM_API_SECRET': 'Last.fm API secret',
            'LASTFM_SESSION_KEY': 'Last.fm session key (get with scripts/lastfm_auth.py)',
            'FLASK_SECRET_KEY': 'Flask secret key'
        }
        
        optional_secrets = {
            'AUDD_API_KEY': 'AudD API key (optional if using only Shazam)'
        }
        
        validation = {}
        
        for key, description in required_secrets.items():
            validation[key] = {
                'present': self.has_secret(key),
                'required': True,
                'description': description
            }
        
        for key, description in optional_secrets.items():
            validation[key] = {
                'present': self.has_secret(key),
                'required': False,
                'description': description
            }
        
        return validation
    
    def save_config(self) -> None:
        """Save current configuration to file."""
        try:
            self.config_dir.mkdir(exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(self._config, f, indent=2)
            logger.info("Configuration saved successfully")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise
    
    def backup_config(self, backup_suffix: str = None) -> Path:
        """
        Create a backup of the current configuration.
        
        Args:
            backup_suffix: Optional suffix for backup filename
            
        Returns:
            Path to backup file
        """
        import datetime
        
        if backup_suffix is None:
            backup_suffix = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        
        backup_file = self.config_dir / f"config_backup_{backup_suffix}.json"
        
        with open(backup_file, 'w') as f:
            json.dump(self._config, f, indent=2)
        
        logger.info(f"Configuration backed up to {backup_file}")
        return backup_file
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get a copy of the current configuration dictionary."""
        return copy.deepcopy(self._config)
    
    def update_config(self, updates: Dict[str, Any]) -> None:
        """
        Update configuration with new values.
        
        Args:
            updates: Dictionary of configuration updates
        """
        def update_nested_dict(original: Dict, updates: Dict):
            for key, value in updates.items():
                if isinstance(value, dict) and key in original and isinstance(original[key], dict):
                    update_nested_dict(original[key], value)
                else:
                    original[key] = value
        
        update_nested_dict(self._config, updates)
    
    def get_audio_config(self) -> Dict[str, Any]:
        """Get audio configuration."""
        return self.get('audio', {})
    
    def get_recognition_config(self) -> Dict[str, Any]:
        """Get recognition configuration."""
        return self.get('recognition', {})
    
    def get_scrobbling_config(self) -> Dict[str, Any]:
        """Get scrobbling configuration."""
        return self.get('scrobbling', {})
    
    def get_web_config(self) -> Dict[str, Any]:
        """Get web interface configuration."""
        return self.get('web_interface', {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self.get('logging', {})
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration."""
        return self.get('database', {})
    
    def is_provider_enabled(self, provider: str) -> bool:
        """Check if a recognition provider is enabled."""
        return self.get(f'recognition.providers.{provider}.enabled', False)
    
    def get_provider_order(self) -> list:
        """Get the order of recognition providers."""
        return self.get('recognition.providers.order', ['audd', 'shazam'])


# Global configuration instance
config = None


def initialize_config(config_dir: str = "config") -> ConfigManager:
    """Initialize the global configuration manager."""
    global config
    config = ConfigManager(config_dir)
    return config


def get_config() -> ConfigManager:
    """Get the global configuration manager instance."""
    global config
    if config is None:
        config = initialize_config()
    return config