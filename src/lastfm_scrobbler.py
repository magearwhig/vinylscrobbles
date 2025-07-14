"""
Last.fm Scrobbler

Handles scrobbling tracks to Last.fm with queue management, retry logic,
and offline resilience.
"""

import pylast
import time
import threading
import logging
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from config_manager import get_config
from database import DatabaseManager, ScrobbleEntry
from music_recognizer import RecognitionResult

logger = logging.getLogger(__name__)


@dataclass
class ScrobbleResult:
    """Result from a scrobble attempt."""
    success: bool
    entry_id: Optional[int] = None
    error_message: Optional[str] = None
    should_retry: bool = False


class LastFMScrobbler:
    """Manages Last.fm scrobbling with queue and retry logic."""
    
    def __init__(self, database: Optional[DatabaseManager] = None):
        """
        Initialize Last.fm scrobbler.
        
        Args:
            database: Optional database manager instance
        """
        self.config = get_config()
        self.scrobbling_config = self.config.get_scrobbling_config()
        self.lastfm_config = self.scrobbling_config.get('lastfm', {})
        
        self.database = database or DatabaseManager()
        
        # Last.fm configuration
        self.enabled = self.lastfm_config.get('enabled', False)
        self.min_play_time = self.lastfm_config.get('min_play_time', 30)
        self.max_queue_size = self.lastfm_config.get('max_queue_size', 1000)
        self.retry_interval = self.lastfm_config.get('retry_interval', 300)  # 5 minutes
        self.max_retries = self.lastfm_config.get('max_retries', 5)
        
        # Authentication
        self.api_key = self.config.get_secret('LASTFM_API_KEY')
        self.api_secret = self.config.get_secret('LASTFM_API_SECRET')
        self.session_key = self.config.get_secret('LASTFM_SESSION_KEY')
        
        # Last.fm network instance
        self.network = None
        self.user = None
        self._authenticated = False
        
        # Threading
        self._running = False
        self._scrobble_thread = None
        self._lock = threading.Lock()
        
        # Statistics
        self.stats = {
            'scrobbles_attempted': 0,
            'scrobbles_successful': 0,
            'scrobbles_failed': 0,
            'queue_processed': 0,
            'authentication_errors': 0,
            'network_errors': 0
        }
        
        self._initialize_lastfm()
    
    def _initialize_lastfm(self):
        """Initialize Last.fm API connection."""
        if not self.enabled:
            logger.info("Last.fm scrobbling is disabled")
            return
        
        if not all([self.api_key, self.api_secret, self.session_key]):
            logger.error("Last.fm credentials not configured. Please run scripts/lastfm_auth.py")
            return
        
        try:
            self.network = pylast.LastFMNetwork(
                api_key=self.api_key,
                api_secret=self.api_secret,
                session_key=self.session_key
            )
            
            # Test authentication
            self.user = self.network.get_authenticated_user()
            user_info = self.user.get_name()
            self._authenticated = True
            
            logger.info(f"Last.fm authentication successful for user: {user_info}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Last.fm: {e}")
            self._authenticated = False
            self.stats['authentication_errors'] += 1
    
    def is_available(self) -> bool:
        """Check if Last.fm scrobbling is available."""
        return self.enabled and self._authenticated and self.network is not None
    
    def start_scrobble_processor(self):
        """Start the scrobble queue processor."""
        if self._running:
            logger.warning("Scrobble processor is already running")
            return
        
        if not self.is_available():
            logger.warning("Cannot start scrobble processor - Last.fm not available")
            return
        
        self._running = True
        self._scrobble_thread = threading.Thread(target=self._scrobble_loop, daemon=True)
        self._scrobble_thread.start()
        logger.info("Scrobble processor started")
    
    def stop_scrobble_processor(self):
        """Stop the scrobble queue processor."""
        self._running = False
        
        if self._scrobble_thread and self._scrobble_thread.is_alive():
            self._scrobble_thread.join(timeout=10.0)
        
        logger.info("Scrobble processor stopped")
    
    def _scrobble_loop(self):
        """Main scrobble processing loop."""
        while self._running:
            try:
                self._process_scrobble_queue()
                time.sleep(self.retry_interval)
            except Exception as e:
                logger.error(f"Error in scrobble loop: {e}")
                time.sleep(60)  # Wait longer on error
    
    def _process_scrobble_queue(self):
        """Process pending scrobbles in the queue."""
        if not self.is_available():
            return
        
        queue_entries = self.database.get_scrobble_queue(limit=50)
        
        if not queue_entries:
            return
        
        logger.debug(f"Processing {len(queue_entries)} queued scrobbles")
        
        for entry in queue_entries:
            if not self._running:
                break
            
            try:
                result = self._attempt_scrobble(entry)
                
                if result.success:
                    # Remove from queue and add to history
                    self.database.remove_from_scrobble_queue(entry.id)
                    self.database.add_to_history(entry, 'lastfm', 1.0)
                    self.stats['scrobbles_successful'] += 1
                    self.stats['queue_processed'] += 1
                    
                elif result.should_retry and entry.retry_count < self.max_retries:
                    # Increment retry count
                    self.database.increment_retry_count(entry.id)
                    self.stats['scrobbles_failed'] += 1
                    
                else:
                    # Max retries reached or permanent failure
                    self.database.remove_from_scrobble_queue(entry.id)
                    logger.error(f"Giving up on scrobble after {entry.retry_count} retries: {entry.artist} - {entry.title}")
                    self.stats['scrobbles_failed'] += 1
                    self.stats['queue_processed'] += 1
                
            except Exception as e:
                logger.error(f"Error processing scrobble: {e}")
                if entry.retry_count < self.max_retries:
                    self.database.increment_retry_count(entry.id)
    
    def _attempt_scrobble(self, entry: ScrobbleEntry) -> ScrobbleResult:
        """
        Attempt to scrobble a single entry.
        
        Args:
            entry: ScrobbleEntry to scrobble
            
        Returns:
            ScrobbleResult with attempt result
        """
        try:
            # Validate entry
            if not entry.artist or not entry.title:
                return ScrobbleResult(
                    success=False,
                    error_message="Missing artist or title",
                    should_retry=False
                )
            
            # Check minimum play time
            if entry.duration and entry.duration < self.min_play_time:
                return ScrobbleResult(
                    success=False,
                    error_message=f"Track too short ({entry.duration}s < {self.min_play_time}s)",
                    should_retry=False
                )
            
            # Perform scrobble
            timestamp = entry.timestamp or int(time.time())
            
            track = self.network.get_track(entry.artist, entry.title)
            
            # Scrobble the track
            self.network.scrobble(
                artist=entry.artist,
                title=entry.title,
                timestamp=timestamp,
                album=entry.album,
                duration=entry.duration,
                track_number=entry.track_number,
                mbid=entry.mbid
            )
            
            logger.info(f"Successfully scrobbled: {entry.artist} - {entry.title}")
            self.stats['scrobbles_attempted'] += 1
            
            return ScrobbleResult(
                success=True,
                entry_id=entry.id
            )
            
        except pylast.WSError as e:
            error_code = getattr(e, 'error_code', None)
            error_message = str(e)
            
            # Determine if we should retry based on error code
            should_retry = error_code not in [
                2,    # Invalid service
                3,    # Invalid method
                4,    # Authentication failed
                5,    # Invalid format
                6,    # Invalid parameters
                7,    # Invalid resource specified
                9,    # Invalid session key
                10,   # Invalid API key
                13,   # Invalid method signature supplied
                26,   # Suspended API key
            ]
            
            logger.error(f"Last.fm API error scrobbling {entry.artist} - {entry.title}: {error_message}")
            self.stats['scrobbles_attempted'] += 1
            
            return ScrobbleResult(
                success=False,
                error_message=error_message,
                should_retry=should_retry
            )
            
        except Exception as e:
            logger.error(f"Network error scrobbling {entry.artist} - {entry.title}: {e}")
            self.stats['scrobbles_attempted'] += 1
            self.stats['network_errors'] += 1
            
            return ScrobbleResult(
                success=False,
                error_message=str(e),
                should_retry=True  # Retry network errors
            )
    
    def queue_scrobble(self, recognition_result: RecognitionResult, timestamp: Optional[int] = None) -> bool:
        """
        Queue a track for scrobbling.
        
        Args:
            recognition_result: Recognition result to scrobble
            timestamp: Optional timestamp (defaults to current time)
            
        Returns:
            True if queued successfully
        """
        if not recognition_result.success:
            logger.warning("Cannot queue failed recognition result")
            return False
        
        if not recognition_result.artist or not recognition_result.title:
            logger.warning("Cannot queue scrobble without artist and title")
            return False
        
        # Check queue size
        current_queue_size = self.database.get_queue_size()
        if current_queue_size >= self.max_queue_size:
            logger.warning(f"Scrobble queue is full ({current_queue_size} >= {self.max_queue_size})")
            return False
        
        # Create scrobble entry
        entry = ScrobbleEntry(
            artist=recognition_result.artist,
            title=recognition_result.title,
            album=recognition_result.album,
            timestamp=timestamp or int(time.time()),
            duration=recognition_result.duration
        )
        
        # Add to queue
        try:
            entry_id = self.database.add_to_scrobble_queue(entry, recognition_result.metadata)
            logger.info(f"Queued scrobble: {entry.artist} - {entry.title} (ID: {entry_id})")
            return True
        except Exception as e:
            logger.error(f"Failed to queue scrobble: {e}")
            return False
    
    def scrobble_now(self, recognition_result: RecognitionResult, timestamp: Optional[int] = None) -> ScrobbleResult:
        """
        Immediately attempt to scrobble a track (bypass queue).
        
        Args:
            recognition_result: Recognition result to scrobble
            timestamp: Optional timestamp
            
        Returns:
            ScrobbleResult
        """
        if not self.is_available():
            return ScrobbleResult(
                success=False,
                error_message="Last.fm not available",
                should_retry=True
            )
        
        entry = ScrobbleEntry(
            artist=recognition_result.artist,
            title=recognition_result.title,
            album=recognition_result.album,
            timestamp=timestamp or int(time.time()),
            duration=recognition_result.duration
        )
        
        return self._attempt_scrobble(entry)
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test Last.fm connection and authentication.
        
        Returns:
            Test result dictionary
        """
        if not self.enabled:
            return {
                'status': 'disabled',
                'message': 'Last.fm scrobbling is disabled'
            }
        
        if not all([self.api_key, self.api_secret, self.session_key]):
            return {
                'status': 'error',
                'message': 'Last.fm credentials not configured. Run scripts/lastfm_auth.py'
            }
        
        try:
            # Test basic authentication
            if not self._authenticated:
                self._initialize_lastfm()
            
            if self._authenticated and self.user:
                user_info = self.user.get_name()
                playcount = self.user.get_playcount()
                
                return {
                    'status': 'success',
                    'message': f'Connected as {user_info}',
                    'user': user_info,
                    'playcount': playcount
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Authentication failed'
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Connection test failed: {e}'
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get scrobbler status and statistics."""
        queue_size = self.database.get_queue_size()
        
        return {
            'enabled': self.enabled,
            'authenticated': self._authenticated,
            'running': self._running,
            'available': self.is_available(),
            'queue_size': queue_size,
            'max_queue_size': self.max_queue_size,
            'min_play_time': self.min_play_time,
            'retry_interval': self.retry_interval,
            'max_retries': self.max_retries,
            'stats': self.stats.copy()
        }
    
    def get_recent_scrobbles(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent scrobbles from history."""
        return self.database.get_recent_scrobbles(limit)
    
    def clear_queue(self) -> int:
        """
        Clear all pending scrobbles from queue.
        
        Returns:
            Number of entries cleared
        """
        count = 0
        entries = self.database.get_scrobble_queue(limit=1000)
        
        for entry in entries:
            if self.database.remove_from_scrobble_queue(entry.id):
                count += 1
        
        logger.info(f"Cleared {count} entries from scrobble queue")
        return count
    
    def get_queue_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get current queue entries for inspection."""
        entries = self.database.get_scrobble_queue(limit)
        
        return [
            {
                'id': entry.id,
                'artist': entry.artist,
                'title': entry.title,
                'album': entry.album,
                'timestamp': entry.timestamp,
                'duration': entry.duration,
                'retry_count': entry.retry_count,
                'created_at': entry.created_at
            }
            for entry in entries
        ]
    
    def cleanup(self):
        """Clean up scrobbler resources."""
        self.stop_scrobble_processor()
        logger.info("Last.fm scrobbler cleaned up")