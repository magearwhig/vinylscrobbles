"""
Pytest configuration and fixtures for vinyl recognition system tests.
"""

import pytest
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config_manager import ConfigManager


@pytest.fixture
def temp_config_dir():
    """Create a temporary configuration directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_dir = Path(temp_dir) / "config"
        config_dir.mkdir()
        yield config_dir


@pytest.fixture
def sample_config():
    """Sample configuration data for testing."""
    return {
        "audio": {
            "device_name": "USB Audio CODEC",
            "sample_rate": 44100,
            "chunk_size": 4096,
            "channels": 2,
            "format": "int16",
            "silence_threshold": 0.01,
            "silence_duration": 2.0,
            "recording_duration": 30.0
        },
        "recognition": {
            "providers": {
                "order": ["audd", "shazam"],
                "audd": {
                    "enabled": True,
                    "api_url": "https://api.audd.io/",
                    "timeout": 30,
                    "max_retries": 3
                },
                "shazam": {
                    "enabled": True,
                    "timeout": 30,
                    "max_retries": 3
                }
            },
            "min_confidence": 0.6,
            "rate_limit_delay": 1.0
        },
        "scrobbling": {
            "lastfm": {
                "enabled": True,
                "api_url": "https://ws.audioscrobbler.com/2.0/",
                "min_play_time": 30,
                "max_queue_size": 1000,
                "retry_interval": 300,
                "max_retries": 5
            }
        },
        "web_interface": {
            "host": "0.0.0.0",
            "port": 5000,
            "debug": False,
            "secret_key_env": "FLASK_SECRET_KEY",
            "update_interval": 5,
            "enable_config_editing": True
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file": "logs/vinyl_recognizer.log",
            "max_bytes": 10485760,
            "backup_count": 5,
            "console_output": True
        }
    }


@pytest.fixture
def sample_secrets():
    """Sample secrets data for testing."""
    return {
        "LASTFM_API_KEY": "test_api_key",
        "LASTFM_API_SECRET": "test_api_secret",
        "LASTFM_SESSION_KEY": "test_session_key",
        "AUDD_API_KEY": "test_audd_key",
        "FLASK_SECRET_KEY": "test_flask_key"
    }


@pytest.fixture
def config_manager(temp_config_dir, sample_config, sample_secrets):
    """Create a ConfigManager instance with test data."""
    # Create config file
    config_file = temp_config_dir / "config.json"
    with open(config_file, 'w') as f:
        json.dump(sample_config, f)
    
    # Create secrets file
    secrets_file = temp_config_dir / "secrets.env"
    with open(secrets_file, 'w') as f:
        for key, value in sample_secrets.items():
            f.write(f"{key}={value}\n")
    
    return ConfigManager(str(temp_config_dir))


@pytest.fixture
def mock_audio_device():
    """Mock audio device for testing."""
    device = Mock()
    device.name = "USB Audio CODEC"
    device.index = 1
    device.maxInputChannels = 2
    device.defaultSampleRate = 44100
    return device


@pytest.fixture
def mock_recognition_result():
    """Mock recognition result for testing."""
    return {
        "success": True,
        "confidence": 0.85,
        "artist": "Test Artist",
        "title": "Test Song",
        "album": "Test Album",
        "provider": "audd",
        "duration": 180
    }


@pytest.fixture
def mock_scrobble_data():
    """Mock scrobble data for testing."""
    return {
        "artist": "Test Artist",
        "title": "Test Song",
        "album": "Test Album",
        "timestamp": 1640995200,
        "duration": 180
    }


@pytest.fixture
def temp_database():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    yield db_path
    
    # Cleanup
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def mock_lastfm_network():
    """Mock Last.fm network for testing."""
    network = Mock()
    network.get_authenticated_user.return_value = Mock()
    network.get_authenticated_user.return_value.get_name.return_value = "testuser"
    network.get_authenticated_user.return_value.get_playcount.return_value = 1000
    return network


@pytest.fixture
def mock_web_socket():
    """Mock WebSocket for testing."""
    socket = Mock()
    socket.emit = Mock()
    socket.on = Mock()
    return socket 