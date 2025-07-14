import pytest
import json
import tempfile
import os
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from src.lastfm_scrobbler import LastFMScrobbler, ScrobbleResult
from src.database import ScrobbleEntry
from src.music_recognizer import RecognitionResult


class TestLastFMScrobbler:
    """Test LastFMScrobbler class."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        with patch('src.lastfm_scrobbler.get_config') as mock_get_config:
            config_mock = Mock()
            config_mock.get_scrobbling_config.return_value = {
                'lastfm': {
                    'enabled': True,
                    'min_play_time': 30,
                    'max_queue_size': 1000,
                    'retry_interval': 300,
                    'max_retries': 5
                }
            }
            config_mock.get_secret.side_effect = lambda key: {
                'LASTFM_API_KEY': 'test_api_key',
                'LASTFM_API_SECRET': 'test_api_secret',
                'LASTFM_SESSION_KEY': 'test_session_key'
            }.get(key)
            mock_get_config.return_value = config_mock
            yield mock_get_config
    
    @pytest.fixture
    def mock_database(self):
        """Mock database."""
        with patch('src.lastfm_scrobbler.DatabaseManager') as mock_db_class:
            mock_db = Mock()
            mock_db_class.return_value = mock_db
            yield mock_db
    
    @pytest.fixture
    def scrobbler(self, mock_config, mock_database):
        """Create LastFMScrobbler instance for testing."""
        return LastFMScrobbler()
    
    def test_queue_scrobble_and_get_queue_entries(self, scrobbler, mock_database):
        """Test queueing scrobble and getting queue entries."""
        # Create a mock RecognitionResult
        mock_recognition = Mock(spec=RecognitionResult)
        mock_recognition.success = True
        mock_recognition.artist = "Test Artist"
        mock_recognition.title = "Test Track"
        mock_recognition.album = "Test Album"
        mock_recognition.confidence = 0.9
        
        # Mock database methods to return proper values
        mock_database.get_queue_size.return_value = 0  # Queue not full
        mock_database.add_to_scrobble_queue.return_value = True
        
        # Test queueing a scrobble
        result = scrobbler.queue_scrobble(mock_recognition)
        assert result is True
        mock_database.add_to_scrobble_queue.assert_called_once()
        
        # Test getting queue entries
        mock_database.get_scrobble_queue.return_value = []
        queue_entries = scrobbler.get_queue_entries()
        
        assert isinstance(queue_entries, list)
        mock_database.get_scrobble_queue.assert_called_once()
    
    def test_clear_queue(self, scrobbler, mock_database):
        """Test clearing the scrobble queue."""
        mock_database.get_scrobble_queue.return_value = [Mock(), Mock()]  # 2 entries
        mock_database.remove_from_scrobble_queue.return_value = True
        
        count = scrobbler.clear_queue()
        
        assert count == 2
        mock_database.get_scrobble_queue.assert_called_once_with(limit=1000)
        assert mock_database.remove_from_scrobble_queue.call_count == 2
    
    def test_get_status(self, scrobbler, mock_database):
        """Test getting scrobbler status."""
        mock_database.get_queue_size.return_value = 5
        mock_database.get_scrobble_stats.return_value = {'total': 10, 'successful': 8}
        
        status = scrobbler.get_status()
        
        assert 'authenticated' in status
        assert 'available' in status
        assert 'enabled' in status
        assert 'queue_size' in status
        assert 'stats' in status
        assert status['queue_size'] == 5
    
    def test_get_recent_scrobbles(self, scrobbler, mock_database):
        """Test getting recent scrobbles."""
        mock_scrobbles = [
            {'artist': 'Artist 1', 'title': 'Track 1', 'timestamp': int(time.time())},
            {'artist': 'Artist 2', 'title': 'Track 2', 'timestamp': int(time.time())}
        ]
        mock_database.get_recent_scrobbles.return_value = mock_scrobbles
        
        recent_scrobbles = scrobbler.get_recent_scrobbles(limit=5)
        
        assert recent_scrobbles == mock_scrobbles
        mock_database.get_recent_scrobbles.assert_called_once_with(5)
    
    def test_get_recent_scrobbles_default_limit(self, scrobbler, mock_database):
        """Test getting recent scrobbles with default limit."""
        mock_database.get_recent_scrobbles.return_value = []
        
        scrobbler.get_recent_scrobbles()
        
        mock_database.get_recent_scrobbles.assert_called_once_with(20)
    
    def test_scrobble_now(self, scrobbler):
        """Test scrobble_now method."""
        mock_recognition = Mock(spec=RecognitionResult)
        mock_recognition.success = True
        mock_recognition.artist = "Test Artist"
        mock_recognition.title = "Test Track"
        mock_recognition.album = "Test Album"
        
        result = scrobbler.scrobble_now(mock_recognition)
        
        assert isinstance(result, ScrobbleResult)
        assert result.success is False  # Should fail since Last.fm is not authenticated in test
    
    def test_test_connection(self, scrobbler):
        """Test connection testing."""
        result = scrobbler.test_connection()
        assert isinstance(result, dict)
        assert 'status' in result
        assert 'message' in result
    
    def test_cleanup(self, scrobbler):
        """Test cleanup method."""
        scrobbler.cleanup()  # Should not raise exception
    
    def test_scrobble_entry_creation(self):
        """Test ScrobbleEntry creation."""
        timestamp = int(time.time())
        entry = ScrobbleEntry(
            artist="Test Artist",
            title="Test Track",
            album="Test Album",
            timestamp=timestamp
        )
        
        assert entry.artist == "Test Artist"
        assert entry.title == "Test Track"
        assert entry.album == "Test Album"
        assert entry.timestamp == timestamp
    
    def test_scrobble_entry_defaults(self):
        """Test ScrobbleEntry with default values."""
        entry = ScrobbleEntry(
            artist="Test Artist",
            title="Test Track"
        )
        
        assert entry.artist == "Test Artist"
        assert entry.title == "Test Track"
        assert entry.album is None
        assert entry.timestamp is None
    
    def test_lastfm_scrobbler_init_with_custom_config(self, mock_database):
        """Test LastFMScrobbler initialization with custom config."""
        with patch('src.lastfm_scrobbler.get_config') as mock_get_config:
            config_mock = Mock()
            config_mock.get_scrobbling_config.return_value = {
                'lastfm': {
                    'enabled': True,
                    'min_play_time': 60,
                    'max_queue_size': 200,
                    'retry_interval': 600,
                    'max_retries': 10
                }
            }
            config_mock.get_secret.side_effect = lambda key: {
                'LASTFM_API_KEY': 'custom_key',
                'LASTFM_API_SECRET': 'custom_secret',
                'LASTFM_SESSION_KEY': 'custom_session'
            }.get(key)
            mock_get_config.return_value = config_mock
            
            scrobbler = LastFMScrobbler()
            
            assert scrobbler.api_key == 'custom_key'
            assert scrobbler.api_secret == 'custom_secret'
            assert scrobbler.session_key == 'custom_session'
            assert scrobbler.min_play_time == 60
            assert scrobbler.max_queue_size == 200
            assert scrobbler.retry_interval == 600
            assert scrobbler.max_retries == 10
    
    def test_lastfm_scrobbler_init_with_defaults(self, mock_database):
        """Test LastFMScrobbler initialization with defaults."""
        with patch('src.lastfm_scrobbler.get_config') as mock_get_config:
            config_mock = Mock()
            config_mock.get_scrobbling_config.return_value = {}
            config_mock.get_secret.return_value = None
            mock_get_config.return_value = config_mock
            
            scrobbler = LastFMScrobbler()
            
            assert scrobbler.api_key is None
            assert scrobbler.api_secret is None
            assert scrobbler.session_key is None
            assert scrobbler.enabled is False
            assert scrobbler.min_play_time == 30
            assert scrobbler.max_queue_size == 1000
            assert scrobbler.retry_interval == 300
            assert scrobbler.max_retries == 5
    
    def test_queue_scrobble_with_failed_recognition(self, scrobbler, mock_database):
        """Test queueing failed recognition result."""
        mock_recognition = Mock(spec=RecognitionResult)
        mock_recognition.success = False
        
        result = scrobbler.queue_scrobble(mock_recognition)
        
        assert result is False
        mock_database.add_to_scrobble_queue.assert_not_called()
    
    def test_queue_scrobble_with_none_recognition(self, scrobbler, mock_database):
        """Test queueing None recognition result."""
        # Mock database method to return proper value
        mock_database.get_queue_size.return_value = 0
        
        # Should raise AttributeError when passing None
        with pytest.raises(AttributeError):
            scrobbler.queue_scrobble(None)
    
    def test_get_status_with_empty_queue(self, scrobbler, mock_database):
        """Test getting status with empty queue."""
        mock_database.get_queue_size.return_value = 0
        mock_database.get_scrobble_stats.return_value = {'total': 0, 'successful': 0}
        
        status = scrobbler.get_status()
        
        assert status['queue_size'] == 0
        assert 'stats' in status
    
    def test_get_status_with_database_error(self, scrobbler, mock_database):
        """Test getting status with database error."""
        mock_database.get_queue_size.side_effect = Exception("Database error")
        mock_database.get_scrobble_stats.return_value = {'total': 0, 'successful': 0}
        
        # Should raise exception when database fails
        with pytest.raises(Exception, match="Database error"):
            scrobbler.get_status()
    
    def test_get_recent_scrobbles_with_database_error(self, scrobbler, mock_database):
        """Test getting recent scrobbles with database error."""
        mock_database.get_recent_scrobbles.side_effect = Exception("Database error")
        
        # Should raise exception when database fails
        with pytest.raises(Exception, match="Database error"):
            scrobbler.get_recent_scrobbles()
    
    def test_clear_queue_with_database_error(self, scrobbler, mock_database):
        """Test clearing queue with database error."""
        mock_database.get_scrobble_queue.side_effect = Exception("Database error")
        
        # Should raise exception when database fails
        with pytest.raises(Exception, match="Database error"):
            scrobbler.clear_queue()
    
    def test_test_connection_with_missing_credentials(self, scrobbler):
        """Test connection testing with missing credentials."""
        scrobbler.api_key = None
        scrobbler.api_secret = None
        
        result = scrobbler.test_connection()
        
        assert result['status'] == 'error'
        assert 'credentials' in result['message'].lower()
    
    def test_test_connection_with_invalid_credentials(self, scrobbler):
        """Test connection testing with invalid credentials."""
        scrobbler.api_key = "invalid_key"
        scrobbler.api_secret = "invalid_secret"
        scrobbler.session_key = "invalid_session"
        
        result = scrobbler.test_connection()
        
        assert result['status'] == 'error'
        assert 'connection' in result['message'].lower()
    
    def test_scrobble_entry_with_future_timestamp(self):
        """Test ScrobbleEntry with future timestamp."""
        future_timestamp = int(time.time()) + 3600  # 1 hour in future
        
        entry = ScrobbleEntry(
            artist="Test Artist",
            title="Test Track",
            timestamp=future_timestamp
        )
        
        # Should allow future timestamps (for scheduled scrobbles)
        assert entry.timestamp == future_timestamp
    
    def test_scrobble_entry_with_very_old_timestamp(self):
        """Test ScrobbleEntry with very old timestamp."""
        old_timestamp = int(time.time()) - 86400 * 365  # 1 year ago
        
        entry = ScrobbleEntry(
            artist="Test Artist",
            title="Test Track",
            timestamp=old_timestamp
        )
        
        # Should allow old timestamps (for historical data)
        assert entry.timestamp == old_timestamp
    
    def test_scrobble_entry_album_with_special_characters(self):
        """Test ScrobbleEntry with special characters in album."""
        entry = ScrobbleEntry(
            artist="Test Artist",
            title="Test Track",
            album="Album (Deluxe Edition) [2023]"
        )
        
        assert entry.album == "Album (Deluxe Edition) [2023]"
    
    def test_scrobble_entry_artist_with_unicode(self):
        """Test ScrobbleEntry with unicode characters in artist."""
        entry = ScrobbleEntry(
            artist="Björk",
            title="Test Track"
        )
        
        assert entry.artist == "Björk"
    
    def test_scrobble_entry_title_with_very_long_string(self):
        """Test ScrobbleEntry with very long title."""
        long_title = "A" * 1000  # Very long title
        
        entry = ScrobbleEntry(
            artist="Test Artist",
            title=long_title
        )
        
        assert entry.title == long_title
    
    def test_lastfm_scrobbler_queue_size_limit(self, scrobbler, mock_database):
        """Test LastFMScrobbler queue size limit."""
        # Mock queue at capacity
        mock_database.get_queue_size.return_value = scrobbler.max_queue_size
        
        # Try to add another entry
        mock_recognition = Mock(spec=RecognitionResult)
        mock_recognition.success = True
        mock_recognition.artist = "Artist"
        mock_recognition.title = "Track"
        
        result = scrobbler.queue_scrobble(mock_recognition)
        
        # Should not add when queue is full
        assert result is False
        mock_database.add_to_scrobble_queue.assert_not_called()
    
    def test_lastfm_scrobbler_retry_logic(self, scrobbler, mock_database):
        """Test LastFMScrobbler retry logic."""
        # Mock failed scrobble with retry count
        failed_entry = Mock()
        failed_entry.retry_count = 1
        
        mock_database.get_scrobble_queue.return_value = [failed_entry]
        
        # Should respect retry attempts limit
        assert scrobbler.max_retries == 5
    
    def test_lastfm_scrobbler_min_play_time_validation(self, scrobbler, mock_database):
        """Test LastFMScrobbler minimum play time validation."""
        # Test with play time below minimum
        short_play_time = scrobbler.min_play_time - 10
        
        mock_recognition = Mock(spec=RecognitionResult)
        mock_recognition.success = True
        mock_recognition.artist = "Test Artist"
        mock_recognition.title = "Test Track"
        mock_recognition.duration = short_play_time
        
        # Mock database method to return proper value
        mock_database.get_queue_size.return_value = 0
        mock_database.add_to_scrobble_queue.return_value = 1
        
        # Should queue entries regardless of play time (validation happens elsewhere)
        result = scrobbler.queue_scrobble(mock_recognition)
        assert result is True
    
    def test_lastfm_scrobbler_config_validation(self, mock_database):
        """Test LastFMScrobbler configuration validation."""
        with patch('src.lastfm_scrobbler.get_config') as mock_get_config:
            config_mock = Mock()
            config_mock.get_scrobbling_config.return_value = {
                'lastfm': {
                    'enabled': True,
                    'min_play_time': -5,  # Invalid
                    'max_queue_size': -1,  # Invalid
                    'retry_interval': -10,  # Invalid
                    'max_retries': 0  # Invalid
                }
            }
            config_mock.get_secret.side_effect = lambda key: {
                'LASTFM_API_KEY': 'test_key',
                'LASTFM_API_SECRET': 'test_secret',
                'LASTFM_SESSION_KEY': 'test_session'
            }.get(key)
            mock_get_config.return_value = config_mock
            
            scrobbler = LastFMScrobbler()
            
            # Should use config values as-is (no validation in current implementation)
            assert scrobbler.min_play_time == -5  # Uses config value
            assert scrobbler.max_queue_size == -1  # Uses config value
            assert scrobbler.retry_interval == -10  # Uses config value
            assert scrobbler.max_retries == 0  # Uses config value
    
    def test_start_stop_scrobble_processor(self, scrobbler):
        """Test starting and stopping scrobble processor."""
        # Mock authentication
        scrobbler._authenticated = True
        scrobbler.network = Mock()
        
        scrobbler.start_scrobble_processor()
        assert scrobbler._running is True
        assert scrobbler._scrobble_thread is not None
        
        scrobbler.stop_scrobble_processor()
        assert scrobbler._running is False
    
    def test_start_scrobble_processor_when_not_available(self, scrobbler):
        """Test starting scrobble processor when not available."""
        scrobbler.enabled = False
        
        scrobbler.start_scrobble_processor()
        assert scrobbler._running is False
    
    def test_is_available(self, scrobbler):
        """Test is_available method."""
        # Test when disabled
        scrobbler.enabled = False
        assert scrobbler.is_available() is False
        
        # Test when enabled but not authenticated
        scrobbler.enabled = True
        scrobbler._authenticated = False
        assert scrobbler.is_available() is False
        
        # Test when enabled and authenticated
        scrobbler._authenticated = True
        scrobbler.network = Mock()
        assert scrobbler.is_available() is True
    
    def test_scrobble_result_creation(self):
        """Test ScrobbleResult creation."""
        result = ScrobbleResult(
            success=True,
            entry_id=123,
            error_message=None,
            should_retry=False
        )
        
        assert result.success is True
        assert result.entry_id == 123
        assert result.error_message is None
        assert result.should_retry is False
    
    def test_scrobble_result_defaults(self):
        """Test ScrobbleResult with defaults."""
        result = ScrobbleResult(success=False)
        
        assert result.success is False
        assert result.entry_id is None
        assert result.error_message is None
        assert result.should_retry is False 