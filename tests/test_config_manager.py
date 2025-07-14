"""
Unit tests for ConfigManager module.
"""

import pytest
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open, Mock
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config_manager import ConfigManager, initialize_config, get_config


class TestConfigManager:
    """Test cases for ConfigManager class."""
    
    def test_init_with_valid_config_dir(self, temp_config_dir, sample_config, sample_secrets):
        """Test ConfigManager initialization with valid configuration."""
        # Create config file
        config_file = temp_config_dir / "config.json"
        with open(config_file, 'w') as f:
            json.dump(sample_config, f)
        
        # Create secrets file
        secrets_file = temp_config_dir / "secrets.env"
        with open(secrets_file, 'w') as f:
            for key, value in sample_secrets.items():
                f.write(f"{key}={value}\n")
        
        config = ConfigManager(str(temp_config_dir))
        
        assert config.config_dir == temp_config_dir
        assert config.get("audio.device_name") == "USB Audio CODEC"
        assert config.get_secret("LASTFM_API_KEY") == "test_api_key"
    
    def test_init_with_example_config(self, temp_config_dir, sample_config):
        """Test ConfigManager initialization with example config file."""
        # Create only example config file
        example_config_file = temp_config_dir / "config.example.json"
        with open(example_config_file, 'w') as f:
            json.dump(sample_config, f)
        
        config = ConfigManager(str(temp_config_dir))
        
        assert config.get("audio.device_name") == "USB Audio CODEC"
        # Should create config.json from example
        assert (temp_config_dir / "config.json").exists()
    
    def test_init_with_no_config_files(self, temp_config_dir):
        """Test ConfigManager initialization with no config files."""
        with pytest.raises(FileNotFoundError):
            ConfigManager(str(temp_config_dir))
    
    def test_get_config_value(self, config_manager):
        """Test getting configuration values."""
        assert config_manager.get("audio.device_name") == "USB Audio CODEC"
        assert config_manager.get("audio.sample_rate") == 44100
        assert config_manager.get("recognition.providers.order") == ["audd", "shazam"]
    
    def test_get_config_value_with_default(self, config_manager):
        """Test getting configuration values with default fallback."""
        assert config_manager.get("nonexistent.key", "default") == "default"
        assert config_manager.get("audio.nonexistent", 123) == 123
    
    def test_set_config_value(self, config_manager):
        """Test setting configuration values."""
        config_manager.set("audio.device_name", "New Device")
        assert config_manager.get("audio.device_name") == "New Device"
        
        config_manager.set("new.section.value", "test")
        assert config_manager.get("new.section.value") == "test"
    
    def test_get_secret(self, config_manager):
        """Test getting secret values."""
        assert config_manager.get_secret("LASTFM_API_KEY") == "test_api_key"
        assert config_manager.get_secret("AUDD_API_KEY") == "test_audd_key"
        assert config_manager.get_secret("NONEXISTENT") is None
        assert config_manager.get_secret("NONEXISTENT", "default") == "default"
    
    def test_has_secret(self, config_manager):
        """Test checking if secrets exist."""
        assert config_manager.has_secret("LASTFM_API_KEY") is True
        assert config_manager.has_secret("NONEXISTENT") is False
    
    def test_validate_secrets(self, config_manager):
        """Test secret validation."""
        validation = config_manager.validate_secrets()
        
        assert "LASTFM_API_KEY" in validation
        assert validation["LASTFM_API_KEY"]["present"] is True
        assert validation["LASTFM_API_KEY"]["required"] is True
        
        assert "AUDD_API_KEY" in validation
        assert validation["AUDD_API_KEY"]["present"] is True
        assert validation["AUDD_API_KEY"]["required"] is False
    
    def test_validate_secrets_missing_required(self, temp_config_dir, sample_config):
        """Test secret validation with missing required secrets."""
        # Create config file only
        config_file = temp_config_dir / "config.json"
        with open(config_file, 'w') as f:
            json.dump(sample_config, f)
        
        config = ConfigManager(str(temp_config_dir))
        validation = config.validate_secrets()
        
        assert validation["LASTFM_API_KEY"]["present"] is False
        assert validation["LASTFM_API_KEY"]["required"] is True
    
    def test_save_config(self, config_manager, temp_config_dir):
        """Test saving configuration to file."""
        config_manager.set("audio.device_name", "Saved Device")
        config_manager.save_config()
        
        # Verify file was saved
        config_file = temp_config_dir / "config.json"
        assert config_file.exists()
        
        # Verify content
        with open(config_file, 'r') as f:
            saved_config = json.load(f)
        
        assert saved_config["audio"]["device_name"] == "Saved Device"
    
    def test_backup_config(self, config_manager, temp_config_dir):
        """Test creating configuration backup."""
        backup_path = config_manager.backup_config("test_backup")
        
        assert backup_path.exists()
        assert backup_path.name == "config_backup_test_backup.json"
        
        # Verify backup content
        with open(backup_path, 'r') as f:
            backup_config = json.load(f)
        
        assert backup_config["audio"]["device_name"] == "USB Audio CODEC"
    
    def test_backup_config_auto_suffix(self, config_manager, temp_config_dir):
        """Test creating configuration backup with auto-generated suffix."""
        backup_path = config_manager.backup_config()
        
        assert backup_path.exists()
        assert backup_path.name.startswith("config_backup_")
        assert backup_path.name.endswith(".json")
    
    def test_get_config_dict(self, config_manager):
        """Test getting configuration dictionary copy."""
        config_dict = config_manager.get_config_dict()
        
        assert isinstance(config_dict, dict)
        assert config_dict["audio"]["device_name"] == "USB Audio CODEC"
        
        # Verify it's a copy, not a reference
        config_dict["audio"]["device_name"] = "Modified"
        assert config_manager.get("audio.device_name") == "USB Audio CODEC"
    
    def test_update_config(self, config_manager):
        """Test updating configuration with new values."""
        updates = {
            "audio": {
                "device_name": "Updated Device",
                "sample_rate": 48000
            },
            "new_section": {
                "value": "test"
            }
        }
        
        config_manager.update_config(updates)
        
        assert config_manager.get("audio.device_name") == "Updated Device"
        assert config_manager.get("audio.sample_rate") == 48000
        assert config_manager.get("new_section.value") == "test"
    
    def test_get_audio_config(self, config_manager):
        """Test getting audio configuration section."""
        audio_config = config_manager.get_audio_config()
        
        assert audio_config["device_name"] == "USB Audio CODEC"
        assert audio_config["sample_rate"] == 44100
        assert audio_config["chunk_size"] == 4096
    
    def test_get_recognition_config(self, config_manager):
        """Test getting recognition configuration section."""
        recognition_config = config_manager.get_recognition_config()
        
        assert recognition_config["min_confidence"] == 0.6
        assert recognition_config["providers"]["order"] == ["audd", "shazam"]
    
    def test_get_scrobbling_config(self, config_manager):
        """Test getting scrobbling configuration section."""
        scrobbling_config = config_manager.get_scrobbling_config()
        
        assert scrobbling_config["lastfm"]["enabled"] is True
        assert scrobbling_config["lastfm"]["min_play_time"] == 30
    
    def test_get_web_config(self, config_manager):
        """Test getting web interface configuration section."""
        web_config = config_manager.get_web_config()
        
        assert web_config["host"] == "0.0.0.0"
        assert web_config["port"] == 5000
        assert web_config["debug"] is False
    
    def test_get_logging_config(self, config_manager):
        """Test getting logging configuration section."""
        logging_config = config_manager.get_logging_config()
        
        assert logging_config["level"] == "INFO"
        assert logging_config["console_output"] is True
    
    def test_get_database_config(self, config_manager):
        """Test getting database configuration section."""
        # Add database config to sample config
        config_manager.set("database", {
            "path": "data/vinyl_recognizer.db",
            "backup_interval": 86400
        })
        
        database_config = config_manager.get_database_config()
        
        assert database_config["path"] == "data/vinyl_recognizer.db"
        assert database_config["backup_interval"] == 86400
    
    def test_is_provider_enabled(self, config_manager):
        """Test checking if recognition provider is enabled."""
        assert config_manager.is_provider_enabled("audd") is True
        assert config_manager.is_provider_enabled("shazam") is True
        assert config_manager.is_provider_enabled("nonexistent") is False
    
    def test_get_provider_order(self, config_manager):
        """Test getting recognition provider order."""
        order = config_manager.get_provider_order()
        
        assert order == ["audd", "shazam"]
    
    def test_load_secrets_from_environment(self, temp_config_dir, sample_config):
        """Test loading secrets from environment variables."""
        # Create config file only
        config_file = temp_config_dir / "config.json"
        with open(config_file, 'w') as f:
            json.dump(sample_config, f)
        
        # Set environment variables
        os.environ["LASTFM_API_KEY"] = "env_api_key"
        os.environ["AUDD_API_KEY"] = "env_audd_key"
        
        try:
            config = ConfigManager(str(temp_config_dir))
            
            assert config.get_secret("LASTFM_API_KEY") == "env_api_key"
            assert config.get_secret("AUDD_API_KEY") == "env_audd_key"
        finally:
            # Clean up environment variables
            os.environ.pop("LASTFM_API_KEY", None)
            os.environ.pop("AUDD_API_KEY", None)
    
    def test_load_secrets_with_comments(self, temp_config_dir, sample_config):
        """Test loading secrets file with comments."""
        # Create config file
        config_file = temp_config_dir / "config.json"
        with open(config_file, 'w') as f:
            json.dump(sample_config, f)
        
        # Create secrets file with comments
        secrets_file = temp_config_dir / "secrets.env"
        with open(secrets_file, 'w') as f:
            f.write("# This is a comment\n")
            f.write("LASTFM_API_KEY=test_key\n")
            f.write("  # Another comment\n")
            f.write("AUDD_API_KEY=test_audd\n")
            f.write("\n")  # Empty line
            f.write("FLASK_SECRET_KEY=test_flask\n")
        
        config = ConfigManager(str(temp_config_dir))
        
        assert config.get_secret("LASTFM_API_KEY") == "test_key"
        assert config.get_secret("AUDD_API_KEY") == "test_audd"
        assert config.get_secret("FLASK_SECRET_KEY") == "test_flask"


class TestConfigManagerFunctions:
    """Test cases for ConfigManager utility functions."""
    
    def test_initialize_config(self, temp_config_dir, sample_config, sample_secrets):
        """Test initialize_config function."""
        # Create config files
        config_file = temp_config_dir / "config.json"
        with open(config_file, 'w') as f:
            json.dump(sample_config, f)
        
        secrets_file = temp_config_dir / "secrets.env"
        with open(secrets_file, 'w') as f:
            for key, value in sample_secrets.items():
                f.write(f"{key}={value}\n")
        
        config = initialize_config(str(temp_config_dir))
        
        assert isinstance(config, ConfigManager)
        assert config.get("audio.device_name") == "USB Audio CODEC"
    
    def test_get_config(self, config_manager):
        """Test get_config function."""
        # Since get_config() returns a new instance, we'll just test that it works
        result = get_config()
        assert isinstance(result, ConfigManager)
    
    def test_get_config_not_initialized(self):
        """Test get_config function when not initialized."""
        # The get_config function should always work since it creates a new instance
        result = get_config()
        assert isinstance(result, ConfigManager)


class TestConfigManagerErrorHandling:
    """Test cases for ConfigManager error handling."""
    
    def test_save_config_error(self, config_manager, temp_config_dir):
        """Test error handling when saving config fails."""
        # Make config directory read-only
        os.chmod(temp_config_dir, 0o444)
        
        try:
            with pytest.raises(Exception):
                config_manager.save_config()
        finally:
            # Restore permissions
            os.chmod(temp_config_dir, 0o755)
    
    def test_load_config_invalid_json(self, temp_config_dir):
        """Test handling invalid JSON in config file."""
        # Create invalid JSON config file
        config_file = temp_config_dir / "config.json"
        with open(config_file, 'w') as f:
            f.write('{"invalid": json}')
        
        # Create valid secrets file
        secrets_file = temp_config_dir / "secrets.env"
        with open(secrets_file, 'w') as f:
            f.write("LASTFM_API_KEY=test\n")
        
        with pytest.raises(json.JSONDecodeError):
            ConfigManager(str(temp_config_dir))
    
    def test_load_secrets_malformed_line(self, temp_config_dir, sample_config):
        """Test handling malformed lines in secrets file."""
        # Create config file
        config_file = temp_config_dir / "config.json"
        with open(config_file, 'w') as f:
            json.dump(sample_config, f)
        
        # Create secrets file with malformed line
        secrets_file = temp_config_dir / "secrets.env"
        with open(secrets_file, 'w') as f:
            f.write("LASTFM_API_KEY=test_key\n")
            f.write("MALFORMED_LINE\n")  # No equals sign
            f.write("AUDD_API_KEY=test_audd\n")
        
        config = ConfigManager(str(temp_config_dir))
        
        # Should still load valid secrets
        assert config.get_secret("LASTFM_API_KEY") == "test_key"
        assert config.get_secret("AUDD_API_KEY") == "test_audd" 