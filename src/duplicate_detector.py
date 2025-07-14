"""
Duplicate Detector

Prevents duplicate scrobbles by creating fingerprints of recognized tracks
and checking them against a time-windowed cache.
"""

import hashlib
import time
import logging
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
import difflib

from .config_manager import get_config
from .database import DatabaseManager, DuplicateEntry
from .music_recognizer import RecognitionResult

logger = logging.getLogger(__name__)


@dataclass
class DuplicateCheck:
    """Result of duplicate detection check."""
    is_duplicate: bool
    confidence: float
    time_since_last: Optional[int] = None
    similar_track: Optional[Dict[str, str]] = None
    fingerprint: Optional[str] = None


class DuplicateDetector:
    """Detects and prevents duplicate track scrobbles."""
    
    def __init__(self, database: Optional[DatabaseManager] = None):
        """
        Initialize duplicate detector.
        
        Args:
            database: Optional database manager instance
        """
        self.config = get_config()
        duplicate_config = self.config.get('duplicate_detection', {})
        
        self.database = database or DatabaseManager()
        
        # Configuration
        self.enabled = duplicate_config.get('enabled', True)
        self.time_window = duplicate_config.get('time_window', 900)  # 15 minutes
        self.similarity_threshold = duplicate_config.get('similarity_threshold', 0.9)
        self.cache_size = duplicate_config.get('cache_size', 1000)
        
        logger.info(f"Duplicate detector initialized - enabled: {self.enabled}, window: {self.time_window}s")
    
    def is_duplicate(self, recognition_result: RecognitionResult) -> DuplicateCheck:
        """
        Check if a recognition result is a duplicate.
        
        Args:
            recognition_result: RecognitionResult to check
            
        Returns:
            DuplicateCheck with detection result
        """
        if not self.enabled:
            return DuplicateCheck(
                is_duplicate=False,
                confidence=0.0,
                fingerprint=None
            )
        
        if not recognition_result.success or not recognition_result.artist or not recognition_result.title:
            return DuplicateCheck(
                is_duplicate=False,
                confidence=0.0,
                fingerprint=None
            )
        
        # Create fingerprint for the track
        fingerprint = self._create_fingerprint(recognition_result)
        
        # Check for exact fingerprint match
        existing_entry = self.database.find_duplicate(fingerprint)
        
        if existing_entry:
            time_since_last = int(time.time()) - existing_entry.timestamp
            
            logger.debug(f"Exact duplicate found: {recognition_result.artist} - {recognition_result.title} "
                        f"(last seen {time_since_last}s ago)")
            
            return DuplicateCheck(
                is_duplicate=True,
                confidence=1.0,
                time_since_last=time_since_last,
                similar_track={
                    'artist': existing_entry.artist,
                    'title': existing_entry.title
                },
                fingerprint=fingerprint
            )
        
        # Check for similar tracks (fuzzy matching)
        similar_check = self._check_similar_tracks(recognition_result, fingerprint)
        
        return similar_check
    
    def _create_fingerprint(self, recognition_result: RecognitionResult) -> str:
        """
        Create a unique fingerprint for a track.
        
        Args:
            recognition_result: RecognitionResult to fingerprint
            
        Returns:
            Fingerprint string
        """
        # Normalize strings for consistent fingerprinting
        artist = self._normalize_string(recognition_result.artist or '')
        title = self._normalize_string(recognition_result.title or '')
        album = self._normalize_string(recognition_result.album or '')
        
        # Create fingerprint from normalized metadata
        fingerprint_data = f"{artist}|{title}|{album}"
        
        # Add duration if available (rounded to nearest 5 seconds for slight variations)
        if recognition_result.duration:
            duration_rounded = round(recognition_result.duration / 5) * 5
            fingerprint_data += f"|{duration_rounded}"
        
        # Create hash
        fingerprint = hashlib.sha256(fingerprint_data.encode('utf-8')).hexdigest()[:16]
        
        logger.debug(f"Created fingerprint: {fingerprint} for {artist} - {title}")
        return fingerprint
    
    def _normalize_string(self, text: str) -> str:
        """
        Normalize string for consistent comparison.
        
        Args:
            text: String to normalize
            
        Returns:
            Normalized string
        """
        if not text:
            return ''
        
        # Convert to lowercase
        normalized = text.lower()
        
        # Remove common variations
        replacements = {
            '&': 'and',
            '+': 'and',
            '  ': ' ',  # Double spaces
            '\t': ' ',
            '\n': ' ',
            '\r': ' '
        }
        
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)
        
        # Remove extra whitespace and punctuation at edges
        normalized = normalized.strip(' .,!?-_()[]{}"\'\t\n\r')
        
        # Remove multiple spaces
        while '  ' in normalized:
            normalized = normalized.replace('  ', ' ')
        
        return normalized
    
    def _check_similar_tracks(self, recognition_result: RecognitionResult, fingerprint: str) -> DuplicateCheck:
        """
        Check for similar tracks using fuzzy matching.
        
        Args:
            recognition_result: RecognitionResult to check
            fingerprint: Fingerprint of current track
            
        Returns:
            DuplicateCheck result
        """
        current_time = int(time.time())
        cutoff_time = current_time - self.time_window
        
        # Get recent tracks from database for comparison
        recent_stats = self.database.get_recent_stats(hours=int(self.time_window / 3600) + 1)
        recent_scrobbles = self.database.get_recent_scrobbles(limit=100)
        
        # Check recent scrobbles for similarity
        for scrobble in recent_scrobbles:
            if scrobble['scrobbled_at'] < cutoff_time:
                continue
            
            similarity = self._calculate_similarity(
                recognition_result.artist, recognition_result.title,
                scrobble['artist'], scrobble['title']
            )
            
            if similarity >= self.similarity_threshold:
                time_since_last = current_time - scrobble['scrobbled_at']
                
                logger.debug(f"Similar track found: {recognition_result.artist} - {recognition_result.title} "
                            f"~ {scrobble['artist']} - {scrobble['title']} "
                            f"(similarity: {similarity:.2f}, {time_since_last}s ago)")
                
                return DuplicateCheck(
                    is_duplicate=True,
                    confidence=similarity,
                    time_since_last=time_since_last,
                    similar_track={
                        'artist': scrobble['artist'],
                        'title': scrobble['title']
                    },
                    fingerprint=fingerprint
                )
        
        return DuplicateCheck(
            is_duplicate=False,
            confidence=0.0,
            fingerprint=fingerprint
        )
    
    def _calculate_similarity(self, artist1: str, title1: str, artist2: str, title2: str) -> float:
        """
        Calculate similarity between two tracks.
        
        Args:
            artist1, title1: First track
            artist2, title2: Second track
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Normalize strings
        artist1_norm = self._normalize_string(artist1 or '')
        title1_norm = self._normalize_string(title1 or '')
        artist2_norm = self._normalize_string(artist2 or '')
        title2_norm = self._normalize_string(title2 or '')
        
        # Calculate similarity using SequenceMatcher
        artist_similarity = difflib.SequenceMatcher(None, artist1_norm, artist2_norm).ratio()
        title_similarity = difflib.SequenceMatcher(None, title1_norm, title2_norm).ratio()
        
        # Weight title similarity more heavily
        overall_similarity = (title_similarity * 0.7) + (artist_similarity * 0.3)
        
        return overall_similarity
    
    def add_track(self, recognition_result: RecognitionResult) -> bool:
        """
        Add a track to the duplicate detection cache.
        
        Args:
            recognition_result: RecognitionResult to add
            
        Returns:
            True if added successfully
        """
        if not self.enabled or not recognition_result.success:
            return False
        
        fingerprint = self._create_fingerprint(recognition_result)
        
        entry = DuplicateEntry(
            fingerprint=fingerprint,
            artist=recognition_result.artist or '',
            title=recognition_result.title or '',
            timestamp=int(time.time()),
            confidence=recognition_result.confidence
        )
        
        try:
            self.database.add_duplicate_entry(entry, self.time_window)
            logger.debug(f"Added to duplicate cache: {entry.artist} - {entry.title}")
            return True
        except Exception as e:
            logger.error(f"Failed to add track to duplicate cache: {e}")
            return False
    
    def cleanup_expired(self) -> int:
        """
        Clean up expired entries from duplicate cache.
        
        Returns:
            Number of entries cleaned up
        """
        try:
            count = self.database.cleanup_expired_duplicates()
            if count > 0:
                logger.debug(f"Cleaned up {count} expired duplicate entries")
            return count
        except Exception as e:
            logger.error(f"Failed to cleanup expired duplicates: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get duplicate cache statistics."""
        try:
            db_stats = self.database.get_database_stats()
            
            return {
                'enabled': self.enabled,
                'time_window': self.time_window,
                'similarity_threshold': self.similarity_threshold,
                'cache_entries': db_stats.get('duplicate_cache_count', 0),
                'max_cache_size': self.cache_size
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {
                'enabled': self.enabled,
                'error': str(e)
            }
    
    def clear_cache(self) -> int:
        """
        Clear all entries from duplicate cache.
        
        Returns:
            Number of entries cleared
        """
        try:
            # Get all entries and remove them
            current_time = int(time.time())
            
            # Force cleanup by setting expiry time to past
            with self.database._get_connection() as conn:
                cursor = conn.execute('UPDATE duplicate_cache SET expires_at = 0')
                count = cursor.rowcount
                conn.commit()
            
            # Now cleanup expired entries
            self.cleanup_expired()
            
            logger.info(f"Cleared {count} entries from duplicate cache")
            return count
            
        except Exception as e:
            logger.error(f"Failed to clear duplicate cache: {e}")
            return 0
    
    def test_duplicate_detection(self, test_track: Dict[str, str]) -> DuplicateCheck:
        """
        Test duplicate detection with a sample track.
        
        Args:
            test_track: Dictionary with 'artist' and 'title' keys
            
        Returns:
            DuplicateCheck result
        """
        from .music_recognizer import RecognitionResult
        
        # Create a test recognition result
        test_result = RecognitionResult(
            success=True,
            confidence=0.9,
            provider='test',
            artist=test_track.get('artist', ''),
            title=test_track.get('title', ''),
            album=test_track.get('album')
        )
        
        return self.is_duplicate(test_result)
    
    def get_recent_fingerprints(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent fingerprints for debugging.
        
        Args:
            limit: Maximum number of fingerprints to return
            
        Returns:
            List of fingerprint dictionaries
        """
        try:
            with self.database._get_connection() as conn:
                cursor = conn.execute('''
                    SELECT fingerprint, artist, title, timestamp, confidence, expires_at
                    FROM duplicate_cache 
                    WHERE expires_at > ?
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (int(time.time()), limit))
                
                fingerprints = []
                for row in cursor.fetchall():
                    fingerprints.append({
                        'fingerprint': row['fingerprint'],
                        'artist': row['artist'],
                        'title': row['title'],
                        'timestamp': row['timestamp'],
                        'confidence': row['confidence'],
                        'expires_at': row['expires_at'],
                        'age_seconds': int(time.time()) - row['timestamp']
                    })
                
                return fingerprints
                
        except Exception as e:
            logger.error(f"Failed to get recent fingerprints: {e}")
            return []