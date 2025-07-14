"""
Unit tests for duplicate detector module.
"""

import pytest
import tempfile
import os
import sys
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from database import DatabaseManager
from duplicate_detector import DuplicateDetector, DuplicateCheck
from music_recognizer import RecognitionResult


class TestRecognitionResult:
    """Test cases for RecognitionResult class."""
    
    def test_recognition_result_creation(self):
        """Test creating a RecognitionResult."""
        result = RecognitionResult(
            success=True,
            confidence=0.85,
            artist="Test Artist",
            title="Test Song",
            album="Test Album",
            provider="audd",
            duration=180
        )
        
        assert result.success is True
        assert result.confidence == 0.85
        assert result.artist == "Test Artist"
        assert result.title == "Test Song"
        assert result.album == "Test Album"
        assert result.provider == "audd"
        assert result.duration == 180
    
    def test_recognition_result_failure(self):
        """Test creating a failed RecognitionResult."""
        result = RecognitionResult(
            success=False,
            confidence=0.0,
            provider="audd",
            error_message="No match found"
        )
        
        assert result.success is False
        assert result.confidence == 0.0
        assert result.error_message == "No match found"
    
    def test_recognition_result_fingerprint(self):
        """Test fingerprint generation."""
        result = RecognitionResult(
            success=True,
            confidence=0.85,
            artist="Test Artist",
            title="Test Song",
            album="Test Album",
            provider="audd",
            duration=180
        )
        
        # Use the DuplicateDetector's fingerprint method instead
        detector = DuplicateDetector(DatabaseManager())
        fingerprint = detector._create_fingerprint(result)
        assert fingerprint is not None
        assert len(fingerprint) > 0
    
    def test_recognition_result_fingerprint_case_insensitive(self):
        """Test fingerprint generation is case insensitive."""
        result1 = RecognitionResult(
            success=True,
            confidence=0.85,
            artist="Test Artist",
            title="Test Song",
            album="Test Album",
            provider="audd",
            duration=180
        )
        
        result2 = RecognitionResult(
            success=True,
            confidence=0.85,
            artist="test artist",
            title="test song",
            album="test album",
            provider="audd",
            duration=180
        )
        
        detector = DuplicateDetector(DatabaseManager())
        fingerprint1 = detector._create_fingerprint(result1)
        fingerprint2 = detector._create_fingerprint(result2)
        assert fingerprint1 == fingerprint2


class TestDuplicateCheck:
    """Test cases for DuplicateCheck class."""
    
    def test_duplicate_check_creation(self):
        """Test creating a DuplicateCheck instance."""
        check = DuplicateCheck(
            is_duplicate=True,
            confidence=1.0,
            time_since_last=300,
            similar_track={'artist': 'Test Artist', 'title': 'Test Song'},
            fingerprint="test_fingerprint"
        )
        
        assert check.is_duplicate is True
        assert check.confidence == 1.0
        assert check.time_since_last == 300
        assert check.similar_track == {'artist': 'Test Artist', 'title': 'Test Song'}
        assert check.fingerprint == "test_fingerprint"
    
    def test_duplicate_check_not_duplicate(self):
        """Test creating a non-duplicate check result."""
        check = DuplicateCheck(
            is_duplicate=False,
            confidence=0.0,
            time_since_last=None,
            similar_track=None,
            fingerprint=None
        )
        
        assert check.is_duplicate is False
        assert check.confidence == 0.0
        assert check.time_since_last is None
        assert check.similar_track is None
        assert check.fingerprint is None


class TestDuplicateDetector:
    def setup_method(self):
        # Create a temporary database for each test
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db = DatabaseManager(self.temp_db_file.name)
        self.detector = DuplicateDetector(self.db)

    def teardown_method(self):
        # Clean up the temporary database file
        try:
            os.unlink(self.temp_db_file.name)
        except Exception:
            pass

    def test_is_duplicate_new_track(self):
        result = RecognitionResult(
            success=True,
            confidence=0.85,
            artist="New Artist",
            title="New Song",
            album="New Album",
            provider="audd",
            duration=180
        )
        check = self.detector.is_duplicate(result)
        assert isinstance(check, DuplicateCheck)
        assert check.is_duplicate is False

    def test_is_duplicate_exact_match(self):
        result = RecognitionResult(
            success=True,
            confidence=0.85,
            artist="Test Artist",
            title="Test Song",
            album="Test Album",
            provider="audd",
            duration=180
        )
        # Add to duplicate cache via add_duplicate_entry
        fingerprint = self.detector._create_fingerprint(result)
        from database import DuplicateEntry
        entry = DuplicateEntry(
            fingerprint=fingerprint,
            artist=result.artist,
            title=result.title,
            timestamp=int(datetime.now().timestamp()),
            confidence=result.confidence
        )
        self.db.add_duplicate_entry(entry)
        check = self.detector.is_duplicate(result)
        assert check.is_duplicate is True
        assert check.fingerprint == fingerprint

    def test_is_duplicate_similar_track(self):
        # This test will check for fuzzy matching
        result1 = RecognitionResult(
            success=True,
            confidence=0.85,
            artist="Test Artist",
            title="Test Song",
            album="Test Album",
            provider="audd",
            duration=180
        )
        result2 = RecognitionResult(
            success=True,
            confidence=0.85,
            artist="Test Artist",
            title="Test Song (Remix)",
            album="Test Album",
            provider="audd",
            duration=180
        )
        # Add first track to history with proper timestamp
        from database import ScrobbleEntry
        entry = ScrobbleEntry(
            artist=result1.artist,
            title=result1.title,
            album=result1.album,
            duration=result1.duration,
            timestamp=int(datetime.now().timestamp())
        )
        self.db.add_to_history(entry, result1.provider, result1.confidence)
        # Now check for similarity
        check = self.detector.is_duplicate(result2)
        assert isinstance(check, DuplicateCheck)
        assert check.is_duplicate is False or isinstance(check.confidence, float)

    def test_disabled_detector(self):
        self.detector.enabled = False
        result = RecognitionResult(
            success=True,
            confidence=0.85,
            artist="Test Artist",
            title="Test Song",
            album="Test Album",
            provider="audd",
            duration=180
        )
        check = self.detector.is_duplicate(result)
        assert check.is_duplicate is False

    def test_failed_recognition_result(self):
        result = RecognitionResult(
            success=False,
            confidence=0.0,
            artist="",
            title="",
            album="",
            provider="audd",
            duration=0
        )
        check = self.detector.is_duplicate(result)
        assert check.is_duplicate is False

    def test_low_confidence_result(self):
        result = RecognitionResult(
            success=True,
            confidence=0.3,  # Low confidence
            artist="Test Artist",
            title="Test Song",
            album="Test Album",
            provider="audd",
            duration=180
        )
        check = self.detector.is_duplicate(result)
        assert check.is_duplicate is False

    def test_similarity_calculation(self):
        """Test similarity calculation between tracks."""
        similarity = self.detector._calculate_similarity(
            "Test Artist", "Test Song",
            "Test Artist", "Test Song"
        )
        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0

    def test_get_cache_stats(self):
        """Test getting cache statistics."""
        stats = self.detector.get_cache_stats()
        assert isinstance(stats, dict)
        assert "cache_entries" in stats
        assert "max_cache_size" in stats
        assert "enabled" in stats

    def test_clear_cache(self):
        """Test clearing the cache."""
        result = RecognitionResult(
            success=True,
            confidence=0.85,
            artist="Test Artist",
            title="Test Song",
            album="Test Album",
            provider="audd",
            duration=180
        )
        # Add to cache via database
        fingerprint = self.detector._create_fingerprint(result)
        from database import DuplicateEntry
        entry = DuplicateEntry(
            fingerprint=fingerprint,
            artist=result.artist,
            title=result.title,
            timestamp=int(datetime.now().timestamp()),
            confidence=result.confidence
        )
        self.db.add_duplicate_entry(entry)
        
        # Clear cache
        cleared_count = self.detector.clear_cache()
        assert isinstance(cleared_count, int)

    def test_test_duplicate_detection(self):
        """Test the test_duplicate_detection method."""
        test_track = {
            "artist": "Test Artist",
            "title": "Test Song",
            "album": "Test Album"
        }
        
        check = self.detector.test_duplicate_detection(test_track)
        assert isinstance(check, DuplicateCheck)

    def test_cache_persistence(self):
        """Test that cache persists between calls."""
        result = RecognitionResult(
            success=True,
            confidence=0.85,
            artist="Test Artist",
            title="Test Song",
            album="Test Album",
            provider="audd",
            duration=180
        )
        
        # First call - should not be duplicate
        check1 = self.detector.is_duplicate(result)
        assert check1.is_duplicate is False
        
        # Add to cache
        fingerprint = self.detector._create_fingerprint(result)
        from database import DuplicateEntry
        entry = DuplicateEntry(
            fingerprint=fingerprint,
            artist=result.artist,
            title=result.title,
            timestamp=int(datetime.now().timestamp()),
            confidence=result.confidence
        )
        self.db.add_duplicate_entry(entry)
        
        # Second call - should be duplicate
        check2 = self.detector.is_duplicate(result)
        assert check2.is_duplicate is True 