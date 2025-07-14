"""
Web Interface

Flask-based web interface with WebSocket support for real-time monitoring
and configuration of the vinyl recognition system.
"""

import json
import time
import threading
from typing import Optional, Dict, Any
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO, emit
import logging

from .config_manager import get_config
from .database import DatabaseManager

logger = logging.getLogger(__name__)


class WebInterface:
    """Web interface for vinyl recognition system monitoring and control."""
    
    def __init__(self, vinyl_system=None):
        """
        Initialize web interface.
        
        Args:
            vinyl_system: Reference to main VinylRecognitionSystem instance
        """
        self.config = get_config()
        web_config = self.config.get_web_config()
        
        self.vinyl_system = vinyl_system
        self.database = DatabaseManager()
        
        # Flask configuration
        self.host = web_config.get('host', '0.0.0.0')
        self.port = web_config.get('port', 5000)
        self.debug = web_config.get('debug', False)
        
        # Create Flask app
        self.app = Flask(__name__, 
                        template_folder='../templates',
                        static_folder='../static')
        
        # Configure secret key
        secret_key = self.config.get_secret('FLASK_SECRET_KEY')
        if not secret_key:
            import secrets
            secret_key = secrets.token_hex(32)
            logger.warning("No Flask secret key configured, using temporary key")
        
        self.app.config['SECRET_KEY'] = secret_key
        
        # Initialize SocketIO
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # Real-time update configuration
        self.update_interval = web_config.get('update_interval', 5)
        self.enable_config_editing = web_config.get('enable_config_editing', True)
        
        # Threading
        self._update_thread = None
        self._running = False
        
        # Setup routes
        self._setup_routes()
        self._setup_socketio_events()
        
        logger.info(f"Web interface initialized on {self.host}:{self.port}")
    
    def _setup_routes(self):
        """Setup Flask routes."""
        
        @self.app.route('/')
        def index():
            """Main dashboard."""
            return render_template('index.html')
        
        @self.app.route('/api/status')
        def api_status():
            """Get system status."""
            if self.vinyl_system:
                status = self.vinyl_system.get_status()
            else:
                status = {'running': False, 'error': 'System not initialized'}
            return jsonify(status)
        
        @self.app.route('/api/recent-scrobbles')
        def api_recent_scrobbles():
            """Get recent scrobbles."""
            limit = request.args.get('limit', 20, type=int)
            scrobbles = self.database.get_recent_scrobbles(limit)
            return jsonify(scrobbles)
        
        @self.app.route('/api/queue')
        def api_queue():
            """Get scrobble queue status."""
            if self.vinyl_system and hasattr(self.vinyl_system, 'lastfm_scrobbler'):
                queue_entries = self.vinyl_system.lastfm_scrobbler.get_queue_entries()
                return jsonify(queue_entries)
            return jsonify([])
        
        @self.app.route('/api/stats')
        def api_stats():
            """Get system statistics."""
            try:
                stats = self.database.get_scrobble_stats(days=30)
                system_stats = self.database.get_recent_stats(hours=24)
                
                return jsonify({
                    'scrobble_stats': stats,
                    'system_stats': system_stats
                })
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/config', methods=['GET'])
        def api_get_config():
            """Get current configuration."""
            if not self.enable_config_editing:
                return jsonify({'error': 'Configuration editing disabled'}), 403
            
            config_dict = self.config.get_config_dict()
            secrets_validation = self.config.validate_secrets()
            
            return jsonify({
                'config': config_dict,
                'secrets': secrets_validation
            })
        
        @self.app.route('/api/config', methods=['POST'])
        def api_update_config():
            """Update configuration."""
            if not self.enable_config_editing:
                return jsonify({'error': 'Configuration editing disabled'}), 403
            
            try:
                updates = request.get_json()
                if not updates:
                    return jsonify({'error': 'No configuration data provided'}), 400
                
                # Update configuration
                self.config.update_config(updates)
                self.config.save_config()
                
                return jsonify({'success': True, 'message': 'Configuration updated'})
            
            except Exception as e:
                logger.error(f"Error updating configuration: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/test-components')
        def api_test_components():
            """Test all system components."""
            if self.vinyl_system:
                results = self.vinyl_system.test_components()
                return jsonify(results)
            return jsonify({'error': 'System not initialized'}), 500
        
        @self.app.route('/api/control/<action>', methods=['POST'])
        def api_control(action):
            """Control system (start/stop/restart)."""
            if not self.vinyl_system:
                return jsonify({'error': 'System not initialized'}), 500
            
            try:
                if action == 'start':
                    if not self.vinyl_system.running:
                        self.vinyl_system.start()
                        return jsonify({'success': True, 'message': 'System started'})
                    else:
                        return jsonify({'error': 'System already running'})
                
                elif action == 'stop':
                    if self.vinyl_system.running:
                        self.vinyl_system.stop()
                        return jsonify({'success': True, 'message': 'System stopped'})
                    else:
                        return jsonify({'error': 'System not running'})
                
                elif action == 'restart':
                    if self.vinyl_system.running:
                        self.vinyl_system.stop()
                        time.sleep(2)
                    self.vinyl_system.start()
                    return jsonify({'success': True, 'message': 'System restarted'})
                
                else:
                    return jsonify({'error': f'Unknown action: {action}'}), 400
            
            except Exception as e:
                logger.error(f"Error controlling system: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/clear-queue', methods=['POST'])
        def api_clear_queue():
            """Clear scrobble queue."""
            if self.vinyl_system and hasattr(self.vinyl_system, 'lastfm_scrobbler'):
                count = self.vinyl_system.lastfm_scrobbler.clear_queue()
                return jsonify({'success': True, 'cleared': count})
            return jsonify({'error': 'Scrobbler not available'}), 500
        
        @self.app.route('/api/clear-duplicates', methods=['POST'])
        def api_clear_duplicates():
            """Clear duplicate detection cache."""
            if self.vinyl_system and hasattr(self.vinyl_system, 'duplicate_detector'):
                count = self.vinyl_system.duplicate_detector.clear_cache()
                return jsonify({'success': True, 'cleared': count})
            return jsonify({'error': 'Duplicate detector not available'}), 500
        
        @self.app.route('/logs')
        def logs():
            """View system logs."""
            return render_template('logs.html')
        
        @self.app.route('/api/logs')
        def api_logs():
            """Get recent log entries."""
            try:
                log_file = self.config.get('logging.file', 'logs/vinyl_recognizer.log')
                lines = request.args.get('lines', 100, type=int)
                
                try:
                    with open(log_file, 'r') as f:
                        log_lines = f.readlines()
                        recent_lines = log_lines[-lines:] if len(log_lines) > lines else log_lines
                        return jsonify({'logs': ''.join(recent_lines)})
                except FileNotFoundError:
                    return jsonify({'logs': 'Log file not found'})
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/config')
        def config_page():
            """Configuration page."""
            if not self.enable_config_editing:
                return redirect(url_for('index'))
            return render_template('config.html')
    
    def _setup_socketio_events(self):
        """Setup SocketIO event handlers."""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Handle client connection."""
            logger.debug("Client connected to WebSocket")
            emit('status', {'connected': True})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection."""
            logger.debug("Client disconnected from WebSocket")
        
        @self.socketio.on('request_status')
        def handle_request_status():
            """Handle status request."""
            if self.vinyl_system:
                status = self.vinyl_system.get_status()
                emit('status_update', status)
        
        @self.socketio.on('request_recent_scrobbles')
        def handle_request_recent_scrobbles():
            """Handle recent scrobbles request."""
            scrobbles = self.database.get_recent_scrobbles(10)
            emit('recent_scrobbles', scrobbles)
    
    def start_updates(self):
        """Start real-time updates thread."""
        if self._running:
            return
        
        self._running = True
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()
        logger.info("Started real-time updates")
    
    def stop_updates(self):
        """Stop real-time updates."""
        self._running = False
        if self._update_thread and self._update_thread.is_alive():
            self._update_thread.join(timeout=5.0)
        logger.info("Stopped real-time updates")
    
    def _update_loop(self):
        """Real-time update loop."""
        while self._running:
            try:
                # Emit status updates
                if self.vinyl_system:
                    status = self.vinyl_system.get_status()
                    self.socketio.emit('status_update', status)
                
                # Emit recent scrobbles
                recent_scrobbles = self.database.get_recent_scrobbles(5)
                self.socketio.emit('recent_scrobbles', recent_scrobbles)
                
                time.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in update loop: {e}")
                time.sleep(10)
    
    def run(self, **kwargs):
        """Run the web interface."""
        # Start real-time updates
        self.start_updates()
        
        try:
            # Run Flask app with SocketIO
            self.socketio.run(
                self.app,
                host=self.host,
                port=self.port,
                debug=self.debug,
                **kwargs
            )
        finally:
            self.stop_updates()


def create_web_app(vinyl_system=None):
    """
    Create and configure Flask app.
    
    Args:
        vinyl_system: Reference to main system
        
    Returns:
        Configured Flask app
    """
    web_interface = WebInterface(vinyl_system)
    return web_interface.app, web_interface.socketio