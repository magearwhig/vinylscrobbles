"""
Unit tests for database module.
"""

import pytest
import sqlite3
import tempfile
import os
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from database import DatabaseManager, ScrobbleEntry, DuplicateEntry


class TestDatabaseManager:
    """Test cases for DatabaseManager class."""
    
    def test_init_with_temp_database(self, temp_database):
        """Test DatabaseManager initialization with temporary database."""
        db = DatabaseManager(temp_database)
        
        assert str(db.db_path) == temp_database
        assert db.config is not None
        
        # Verify database file was created
        assert os.path.exists(temp_database)
    
    def test_init_with_existing_database(self, temp_database):
        """Test DatabaseManager initialization with existing database."""
        # Create database with some data
        db1 = DatabaseManager(temp_database)
        entry = ScrobbleEntry("Artist1", "Song1", "Album1", duration=100, timestamp=int(time.time()))
        db1.add_to_scrobble_queue(entry)
        
        # Create new instance with same database
        db2 = DatabaseManager(temp_database)
        
        # Verify data is still there
        queue = db2.get_scrobble_queue()
        assert len(queue) == 1
        assert queue[0].artist == "Artist1"
    
    def test_add_to_scrobble_queue(self, temp_database):
        """Test adding scrobble to queue."""
        db = DatabaseManager(temp_database)
        
        entry = ScrobbleEntry("Test Artist", "Test Song", "Test Album", duration=180, timestamp=int(time.time()))
        entry_id = db.add_to_scrobble_queue(entry)
        
        assert entry_id is not None
        assert entry.id is not None
        
        queue = db.get_scrobble_queue()
        assert len(queue) == 1
        assert queue[0].artist == "Test Artist"
        assert queue[0].title == "Test Song"
        assert queue[0].album == "Test Album"
        assert queue[0].duration == 180
    
    def test_get_scrobble_queue_empty(self, temp_database):
        """Test getting empty scrobble queue."""
        db = DatabaseManager(temp_database)
        
        queue = db.get_scrobble_queue()
        assert queue == []
    
    def test_get_scrobble_queue_with_limit(self, temp_database):
        """Test getting scrobble queue with limit."""
        db = DatabaseManager(temp_database)
        
        # Add multiple scrobbles
        for i in range(5):
            entry = ScrobbleEntry(f"Artist{i}", f"Song{i}", f"Album{i}", duration=180, timestamp=int(time.time()))
            db.add_to_scrobble_queue(entry)
        
        queue = db.get_scrobble_queue(limit=3)
        assert len(queue) == 3
    
    def test_remove_from_scrobble_queue(self, temp_database):
        """Test removing scrobble from queue."""
        db = DatabaseManager(temp_database)
        
        entry = ScrobbleEntry("Artist", "Song", "Album", duration=180, timestamp=int(time.time()))
        entry_id = db.add_to_scrobble_queue(entry)
        
        success = db.remove_from_scrobble_queue(entry_id)
        assert success is True
        
        queue = db.get_scrobble_queue()
        assert len(queue) == 0
    
    def test_increment_retry_count(self, temp_database):
        """Test incrementing retry count."""
        db = DatabaseManager(temp_database)
        
        entry = ScrobbleEntry("Artist", "Song", "Album", duration=180, timestamp=int(time.time()))
        entry_id = db.add_to_scrobble_queue(entry)
        
        success = db.increment_retry_count(entry_id)
        assert success is True
        
        queue = db.get_scrobble_queue()
        assert queue[0].retry_count == 1
    
    def test_add_to_history(self, temp_database):
        """Test adding scrobble to history."""
        db = DatabaseManager(temp_database)
        
        entry = ScrobbleEntry("Artist", "Song", "Album", duration=180, timestamp=int(time.time()))
        entry_id = db.add_to_history(entry, "audd", 0.85)
        
        assert entry_id is not None
        
        history = db.get_recent_scrobbles()
        assert len(history) == 1
        assert history[0]["artist"] == "Artist"
        assert history[0]["title"] == "Song"
        assert history[0]["recognition_provider"] == "audd"
        assert history[0]["recognition_confidence"] == 0.85
    
    def test_add_duplicate_entry(self, temp_database):
        """Test adding duplicate entry."""
        db = DatabaseManager(temp_database)
        
        entry = DuplicateEntry(
            fingerprint="test_fingerprint_123",
            artist="Artist",
            title="Song",
            timestamp=int(datetime.now().timestamp()),
            confidence=0.85
        )
        
        entry_id = db.add_duplicate_entry(entry)
        assert entry_id is not None
    
    def test_find_duplicate(self, temp_database):
        """Test finding duplicate entry."""
        db = DatabaseManager(temp_database)
        
        entry = DuplicateEntry(
            fingerprint="test_fingerprint_123",
            artist="Artist",
            title="Song",
            timestamp=int(datetime.now().timestamp()),
            confidence=0.85
        )
        
        db.add_duplicate_entry(entry)
        
        found = db.find_duplicate("test_fingerprint_123")
        assert found is not None
        assert found.artist == "Artist"
        assert found.title == "Song"
    
    def test_find_duplicate_not_exists(self, temp_database):
        """Test finding non-existing duplicate."""
        db = DatabaseManager(temp_database)
        
        found = db.find_duplicate("nonexistent_fingerprint")
        assert found is None
    
    def test_add_system_stats(self, temp_database):
        """Test adding system stats."""
        db = DatabaseManager(temp_database)
        
        stats = {
            "cpu_usage": 25.5,
            "memory_usage": 512.0,
            "temperature": 45.0
        }
        
        stats_id = db.add_system_stats(stats)
        assert stats_id is not None
        
        recent_stats = db.get_recent_stats()
        assert len(recent_stats) == 1
        assert recent_stats[0]["cpu_usage"] == 25.5
        assert recent_stats[0]["memory_usage"] == 512.0
    
    def test_get_database_stats(self, temp_database):
        """Test getting database statistics."""
        db = DatabaseManager(temp_database)
        
        # Add some test data
        entry = ScrobbleEntry("Artist", "Song", "Album", duration=180, timestamp=int(time.time()))
        db.add_to_scrobble_queue(entry)
        db.add_to_history(entry, "audd", 0.85)
        
        stats = db.get_database_stats()
        
        assert "scrobble_queue_count" in stats
        assert "scrobble_history_count" in stats
        assert "duplicate_cache_count" in stats
        assert "system_stats_count" in stats
        assert "file_size" in stats
    
    def test_cleanup_old_data(self, temp_database):
        """Test cleaning up old data."""
        db = DatabaseManager(temp_database)
        
        # Add some data
        entry = ScrobbleEntry("Artist", "Song", "Album", duration=180, timestamp=int(time.time()))
        db.add_to_history(entry, "audd", 0.85)
        
        # Clean up data older than 1 day
        cleanup_stats = db.cleanup_old_data(days=1)
        
        assert "system_stats" in cleanup_stats
        assert "duplicate_cache" in cleanup_stats
    
    def test_vacuum_database(self, temp_database):
        """Test database vacuum operation."""
        db = DatabaseManager(temp_database)
        
        # Add and remove some data to create fragmentation
        entry = ScrobbleEntry("Artist", "Song", "Album", duration=180, timestamp=int(time.time()))
        entry_id = db.add_to_scrobble_queue(entry)
        db.remove_from_scrobble_queue(entry_id)
        
        # Vacuum should complete without error
        db.vacuum_database()
        
        # Database should still be accessible
        queue = db.get_scrobble_queue()
        assert len(queue) == 0


class TestScrobbleEntry:
    """Test cases for ScrobbleEntry class."""
    
    def test_scrobble_entry_creation(self):
        """Test creating a ScrobbleEntry."""
        entry = ScrobbleEntry(
            artist="Test Artist",
            title="Test Song",
            album="Test Album",
            duration=180
        )
        
        assert entry.artist == "Test Artist"
        assert entry.title == "Test Song"
        assert entry.album == "Test Album"
        assert entry.duration == 180
        assert entry.retry_count == 0
        assert entry.id is None
    
    def test_scrobble_entry_with_timestamp(self):
        """Test creating ScrobbleEntry with timestamp."""
        timestamp = int(datetime.now().timestamp())
        entry = ScrobbleEntry(
            artist="Test Artist",
            title="Test Song",
            timestamp=timestamp
        )
        
        assert entry.timestamp == timestamp
    
    def test_scrobble_entry_defaults(self):
        """Test ScrobbleEntry default values."""
        entry = ScrobbleEntry("Artist", "Song")
        
        assert entry.album is None
        assert entry.timestamp is None
        assert entry.duration is None
        assert entry.retry_count == 0
        assert entry.created_at is None


class TestDuplicateEntry:
    """Test cases for DuplicateEntry class."""
    
    def test_duplicate_entry_creation(self):
        """Test creating a DuplicateEntry."""
        timestamp = int(datetime.now().timestamp())
        entry = DuplicateEntry(
            fingerprint="test_fingerprint",
            artist="Test Artist",
            title="Test Song",
            timestamp=timestamp,
            confidence=0.85
        )
        
        assert entry.fingerprint == "test_fingerprint"
        assert entry.artist == "Test Artist"
        assert entry.title == "Test Song"
        assert entry.timestamp == timestamp
        assert entry.confidence == 0.85
        assert entry.id is None 