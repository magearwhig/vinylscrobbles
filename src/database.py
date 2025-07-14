"""
Database Manager

Handles SQLite database operations for scrobble queue, history, and duplicate detection.
"""

import sqlite3
import logging
import threading
import time
import json
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

from config_manager import get_config

logger = logging.getLogger(__name__)


@dataclass
class ScrobbleEntry:
    """Represents a scrobble entry."""
    artist: str
    title: str
    album: Optional[str] = None
    timestamp: Optional[int] = None
    duration: Optional[int] = None
    track_number: Optional[int] = None
    mbid: Optional[str] = None
    retry_count: int = 0
    created_at: Optional[int] = None
    id: Optional[int] = None


@dataclass
class DuplicateEntry:
    """Represents a duplicate detection entry."""
    fingerprint: str
    artist: str
    title: str
    timestamp: int
    confidence: float
    id: Optional[int] = None


class DatabaseManager:
    """Manages SQLite database operations for the vinyl recognition system."""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.config = get_config()
        db_config = self.config.get_database_config()
        
        if db_path is None:
            db_path = db_config.get('path', 'data/vinyl_recognizer.db')
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._lock = threading.Lock()
        self._initialize_database()
        
        logger.info(f"Database initialized at {self.db_path}")
    
    def _initialize_database(self):
        """Initialize database tables."""
        with self._get_connection() as conn:
            # Scrobble queue table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS scrobble_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    artist TEXT NOT NULL,
                    title TEXT NOT NULL,
                    album TEXT,
                    timestamp INTEGER,
                    duration INTEGER,
                    track_number INTEGER,
                    mbid TEXT,
                    retry_count INTEGER DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    metadata TEXT
                )
            ''')
            
            # Scrobble history table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS scrobble_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    artist TEXT NOT NULL,
                    title TEXT NOT NULL,
                    album TEXT,
                    timestamp INTEGER NOT NULL,
                    duration INTEGER,
                    track_number INTEGER,
                    mbid TEXT,
                    scrobbled_at INTEGER NOT NULL,
                    recognition_provider TEXT,
                    recognition_confidence REAL,
                    metadata TEXT
                )
            ''')
            
            # Duplicate detection cache
            conn.execute('''
                CREATE TABLE IF NOT EXISTS duplicate_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fingerprint TEXT UNIQUE NOT NULL,
                    artist TEXT NOT NULL,
                    title TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    expires_at INTEGER NOT NULL
                )
            ''')
            
            # System statistics
            conn.execute('''
                CREATE TABLE IF NOT EXISTS system_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    cpu_usage REAL,
                    memory_usage REAL,
                    disk_usage REAL,
                    temperature REAL,
                    recognition_count INTEGER DEFAULT 0,
                    scrobble_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0
                )
            ''')
            
            # Configuration storage
            conn.execute('''
                CREATE TABLE IF NOT EXISTS configuration (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            ''')
            
            # Create indexes for better performance
            conn.execute('CREATE INDEX IF NOT EXISTS idx_scrobble_queue_created_at ON scrobble_queue(created_at)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_scrobble_history_timestamp ON scrobble_history(timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_duplicate_cache_fingerprint ON duplicate_cache(fingerprint)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_duplicate_cache_expires_at ON duplicate_cache(expires_at)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_system_stats_timestamp ON system_stats(timestamp)')
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper locking."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            finally:
                conn.close()
    
    # Scrobble Queue Operations
    
    def add_to_scrobble_queue(self, entry: ScrobbleEntry, metadata: Optional[Dict] = None) -> int:
        """
        Add entry to scrobble queue.
        
        Args:
            entry: ScrobbleEntry to add
            metadata: Optional metadata dict
            
        Returns:
            ID of inserted entry
        """
        if entry.created_at is None:
            entry.created_at = int(time.time())
        
        if entry.timestamp is None:
            entry.timestamp = entry.created_at
        
        metadata_json = json.dumps(metadata) if metadata else None
        
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO scrobble_queue 
                (artist, title, album, timestamp, duration, track_number, mbid, retry_count, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry.artist, entry.title, entry.album, entry.timestamp,
                entry.duration, entry.track_number, entry.mbid,
                entry.retry_count, entry.created_at, metadata_json
            ))
            conn.commit()
            entry.id = cursor.lastrowid
            
        logger.debug(f"Added to scrobble queue: {entry.artist} - {entry.title}")
        return entry.id
    
    def get_scrobble_queue(self, limit: int = 100) -> List[ScrobbleEntry]:
        """
        Get entries from scrobble queue.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of ScrobbleEntry objects
        """
        with self._get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM scrobble_queue 
                ORDER BY created_at ASC 
                LIMIT ?
            ''', (limit,))
            
            entries = []
            for row in cursor.fetchall():
                entry = ScrobbleEntry(
                    id=row['id'],
                    artist=row['artist'],
                    title=row['title'],
                    album=row['album'],
                    timestamp=row['timestamp'],
                    duration=row['duration'],
                    track_number=row['track_number'],
                    mbid=row['mbid'],
                    retry_count=row['retry_count'],
                    created_at=row['created_at']
                )
                entries.append(entry)
            
            return entries
    
    def remove_from_scrobble_queue(self, entry_id: int) -> bool:
        """
        Remove entry from scrobble queue.
        
        Args:
            entry_id: ID of entry to remove
            
        Returns:
            True if removed, False if not found
        """
        with self._get_connection() as conn:
            cursor = conn.execute('DELETE FROM scrobble_queue WHERE id = ?', (entry_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def increment_retry_count(self, entry_id: int) -> bool:
        """
        Increment retry count for a scrobble entry.
        
        Args:
            entry_id: ID of entry
            
        Returns:
            True if updated, False if not found
        """
        with self._get_connection() as conn:
            cursor = conn.execute('''
                UPDATE scrobble_queue 
                SET retry_count = retry_count + 1 
                WHERE id = ?
            ''', (entry_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_queue_size(self) -> int:
        """Get current scrobble queue size."""
        with self._get_connection() as conn:
            cursor = conn.execute('SELECT COUNT(*) FROM scrobble_queue')
            return cursor.fetchone()[0]
    
    # Scrobble History Operations
    
    def add_to_history(self, entry: ScrobbleEntry, provider: str, confidence: float, metadata: Optional[Dict] = None) -> int:
        """
        Add successfully scrobbled entry to history.
        
        Args:
            entry: ScrobbleEntry that was scrobbled
            provider: Recognition provider used
            confidence: Recognition confidence
            metadata: Optional metadata
            
        Returns:
            ID of inserted history entry
        """
        scrobbled_at = int(time.time())
        metadata_json = json.dumps(metadata) if metadata else None
        
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO scrobble_history 
                (artist, title, album, timestamp, duration, track_number, mbid, 
                 scrobbled_at, recognition_provider, recognition_confidence, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry.artist, entry.title, entry.album, entry.timestamp,
                entry.duration, entry.track_number, entry.mbid,
                scrobbled_at, provider, confidence, metadata_json
            ))
            conn.commit()
            history_id = cursor.lastrowid
            
        logger.info(f"Added to scrobble history: {entry.artist} - {entry.title}")
        return history_id
    
    def get_recent_scrobbles(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent scrobbles from history.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of scrobble dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM scrobble_history 
                ORDER BY scrobbled_at DESC 
                LIMIT ?
            ''', (limit,))
            
            scrobbles = []
            for row in cursor.fetchall():
                scrobble = dict(row)
                if scrobble['metadata']:
                    try:
                        scrobble['metadata'] = json.loads(scrobble['metadata'])
                    except json.JSONDecodeError:
                        scrobble['metadata'] = None
                scrobbles.append(scrobble)
            
            return scrobbles
    
    def get_scrobble_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        Get scrobble statistics for the specified period.
        
        Args:
            days: Number of days to include in stats
            
        Returns:
            Dictionary with statistics
        """
        since_timestamp = int(time.time()) - (days * 24 * 60 * 60)
        
        with self._get_connection() as conn:
            # Total scrobbles
            cursor = conn.execute('''
                SELECT COUNT(*) FROM scrobble_history 
                WHERE scrobbled_at >= ?
            ''', (since_timestamp,))
            total_scrobbles = cursor.fetchone()[0]
            
            # Unique artists
            cursor = conn.execute('''
                SELECT COUNT(DISTINCT artist) FROM scrobble_history 
                WHERE scrobbled_at >= ?
            ''', (since_timestamp,))
            unique_artists = cursor.fetchone()[0]
            
            # Top artists
            cursor = conn.execute('''
                SELECT artist, COUNT(*) as count FROM scrobble_history 
                WHERE scrobbled_at >= ?
                GROUP BY artist 
                ORDER BY count DESC 
                LIMIT 10
            ''', (since_timestamp,))
            top_artists = [dict(row) for row in cursor.fetchall()]
            
            # Recognition providers
            cursor = conn.execute('''
                SELECT recognition_provider, COUNT(*) as count FROM scrobble_history 
                WHERE scrobbled_at >= ?
                GROUP BY recognition_provider 
                ORDER BY count DESC
            ''', (since_timestamp,))
            providers = [dict(row) for row in cursor.fetchall()]
            
            return {
                'period_days': days,
                'total_scrobbles': total_scrobbles,
                'unique_artists': unique_artists,
                'top_artists': top_artists,
                'recognition_providers': providers
            }
    
    # Duplicate Detection Operations
    
    def add_duplicate_entry(self, entry: DuplicateEntry, ttl_seconds: int = 900) -> int:
        """
        Add entry to duplicate detection cache.
        
        Args:
            entry: DuplicateEntry to add
            ttl_seconds: Time to live in seconds
            
        Returns:
            ID of inserted entry
        """
        expires_at = int(time.time()) + ttl_seconds
        
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT OR REPLACE INTO duplicate_cache 
                (fingerprint, artist, title, timestamp, confidence, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                entry.fingerprint, entry.artist, entry.title,
                entry.timestamp, entry.confidence, expires_at
            ))
            conn.commit()
            return cursor.lastrowid
    
    def find_duplicate(self, fingerprint: str) -> Optional[DuplicateEntry]:
        """
        Find duplicate entry by fingerprint.
        
        Args:
            fingerprint: Fingerprint to search for
            
        Returns:
            DuplicateEntry if found, None otherwise
        """
        current_time = int(time.time())
        
        with self._get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM duplicate_cache 
                WHERE fingerprint = ? AND expires_at > ?
            ''', (fingerprint, current_time))
            
            row = cursor.fetchone()
            if row:
                return DuplicateEntry(
                    id=row['id'],
                    fingerprint=row['fingerprint'],
                    artist=row['artist'],
                    title=row['title'],
                    timestamp=row['timestamp'],
                    confidence=row['confidence']
                )
            return None
    
    def cleanup_expired_duplicates(self) -> int:
        """
        Clean up expired duplicate entries.
        
        Returns:
            Number of entries cleaned up
        """
        current_time = int(time.time())
        
        with self._get_connection() as conn:
            cursor = conn.execute('DELETE FROM duplicate_cache WHERE expires_at <= ?', (current_time,))
            conn.commit()
            return cursor.rowcount
    
    # System Statistics Operations
    
    def add_system_stats(self, stats: Dict[str, Any]) -> int:
        """
        Add system statistics entry.
        
        Args:
            stats: Dictionary of system statistics
            
        Returns:
            ID of inserted entry
        """
        timestamp = int(time.time())
        
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO system_stats 
                (timestamp, cpu_usage, memory_usage, disk_usage, temperature,
                 recognition_count, scrobble_count, error_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                timestamp,
                stats.get('cpu_usage'),
                stats.get('memory_usage'),
                stats.get('disk_usage'),
                stats.get('temperature'),
                stats.get('recognition_count', 0),
                stats.get('scrobble_count', 0),
                stats.get('error_count', 0)
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_recent_stats(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get recent system statistics.
        
        Args:
            hours: Number of hours to include
            
        Returns:
            List of statistics dictionaries
        """
        since_timestamp = int(time.time()) - (hours * 60 * 60)
        
        with self._get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM system_stats 
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
            ''', (since_timestamp,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    # Database Maintenance
    
    def cleanup_old_data(self, days: int = 90) -> Dict[str, int]:
        """
        Clean up old data from database.
        
        Args:
            days: Age threshold in days
            
        Returns:
            Dictionary with cleanup counts
        """
        cutoff_timestamp = int(time.time()) - (days * 24 * 60 * 60)
        cleanup_counts = {}
        
        with self._get_connection() as conn:
            # Clean up old system stats
            cursor = conn.execute('DELETE FROM system_stats WHERE timestamp < ?', (cutoff_timestamp,))
            cleanup_counts['system_stats'] = cursor.rowcount
            
            # Clean up expired duplicates (do it directly here to avoid nested connections)
            current_time = int(time.time())
            cursor = conn.execute('DELETE FROM duplicate_cache WHERE expires_at <= ?', (current_time,))
            cleanup_counts['duplicate_cache'] = cursor.rowcount
            
            conn.commit()
        
        logger.info(f"Database cleanup completed: {cleanup_counts}")
        return cleanup_counts
    
    def vacuum_database(self):
        """Vacuum database to reclaim space."""
        with self._get_connection() as conn:
            conn.execute('VACUUM')
            conn.commit()
        logger.info("Database vacuumed")
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self._get_connection() as conn:
            stats = {}
            
            # Table row counts
            for table in ['scrobble_queue', 'scrobble_history', 'duplicate_cache', 'system_stats']:
                cursor = conn.execute(f'SELECT COUNT(*) FROM {table}')
                stats[f'{table}_count'] = cursor.fetchone()[0]
            
            # Database file size
            stats['file_size'] = self.db_path.stat().st_size if self.db_path.exists() else 0
            
            return stats
    
    def backup_database(self, backup_path: Optional[str] = None) -> str:
        """
        Create database backup.
        
        Args:
            backup_path: Optional backup file path
            
        Returns:
            Path to backup file
        """
        if backup_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = str(self.db_path.parent / f"vinyl_recognizer_backup_{timestamp}.db")
        
        with self._get_connection() as conn:
            backup_conn = sqlite3.connect(backup_path)
            conn.backup(backup_conn)
            backup_conn.close()
        
        logger.info(f"Database backed up to {backup_path}")
        return backup_path