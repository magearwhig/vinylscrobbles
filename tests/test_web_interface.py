import pytest
import json
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock, mock_open
from flask import Flask
from flask_socketio import SocketIO

from src.web_interface import WebInterface, create_web_app


class TestFlaskApp:
    """Test Flask application routes and functionality."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        with patch('src.web_interface.get_config') as mock_get_config:
            config_mock = Mock()
            config_mock.get_web_config.return_value = {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False,
                'update_interval': 5,
                'enable_config_editing': True
            }
            config_mock.get_secret.return_value = 'test_secret_key'
            config_mock.get_config_dict.return_value = {'test': 'config'}
            config_mock.validate_secrets.return_value = {'valid': True}
            config_mock.update_config.return_value = None
            config_mock.save_config.return_value = None
            mock_get_config.return_value = config_mock
            yield mock_get_config
    
    @pytest.fixture
    def mock_database(self):
        """Mock database."""
        with patch('src.web_interface.DatabaseManager') as mock_db_class:
            mock_db = Mock()
            mock_db_class.return_value = mock_db
            mock_db.get_recent_scrobbles.return_value = [{'track': 'Test Track'}]
            mock_db.get_scrobble_stats.return_value = {'total': 10}
            mock_db.get_recent_stats.return_value = {'cpu': 50}
            mock_db.clear_duplicate_cache.return_value = 5
            yield mock_db
    
    @pytest.fixture
    def web_interface(self, mock_config, mock_database):
        """Create WebInterface instance for testing."""
        return WebInterface()
    
    @pytest.fixture
    def client(self, web_interface):
        """Create test client."""
        web_interface.app.config['TESTING'] = True
        return web_interface.app.test_client()
    
    def test_index_route(self, client):
        """Test index route."""
        response = client.get('/')
        assert response.status_code == 200
    
    def test_api_status_route(self, client):
        """Test API status route."""
        response = client.get('/api/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'running' in data
    
    def test_api_get_config_route(self, client):
        """Test API get config route."""
        response = client.get('/api/config')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'config' in data
        assert 'secrets' in data
    
    def test_api_logs_route(self, client):
        """Test API logs route."""
        # Mock the logs file reading
        with patch('builtins.open', mock_open(read_data='test log content')):
            response = client.get('/api/logs')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'logs' in data
    
    def test_logs_route(self, client):
        """Test logs page route."""
        response = client.get('/logs')
        assert response.status_code == 200
    
    def test_config_page_route(self, client):
        """Test config page route."""
        response = client.get('/config')
        assert response.status_code == 200
    
    def test_404_route(self, client):
        """Test 404 route."""
        response = client.get('/nonexistent')
        assert response.status_code == 404
    
    def test_api_recent_scrobbles_route(self, client, mock_database):
        """Test API recent scrobbles route."""
        response = client.get('/api/recent-scrobbles')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        mock_database.get_recent_scrobbles.assert_called_once_with(20)
    
    def test_api_recent_scrobbles_with_limit(self, client, mock_database):
        """Test API recent scrobbles route with custom limit."""
        response = client.get('/api/recent-scrobbles?limit=10')
        assert response.status_code == 200
        mock_database.get_recent_scrobbles.assert_called_once_with(10)
    
    def test_api_queue_route_with_system(self, client):
        """Test API queue route with vinyl system."""
        # Create WebInterface with mock vinyl system
        mock_vinyl_system = Mock()
        mock_scrobbler = Mock()
        mock_scrobbler.get_queue_entries.return_value = [{'track': 'Queued Track'}]
        mock_vinyl_system.lastfm_scrobbler = mock_scrobbler
        
        with patch('src.web_interface.get_config') as mock_get_config:
            config_mock = Mock()
            config_mock.get_web_config.return_value = {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False,
                'update_interval': 5,
                'enable_config_editing': True
            }
            config_mock.get_secret.return_value = 'test_secret_key'
            mock_get_config.return_value = config_mock
            
            web_interface = WebInterface(vinyl_system=mock_vinyl_system)
            web_interface.app.config['TESTING'] = True
            test_client = web_interface.app.test_client()
            
            response = test_client.get('/api/queue')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert isinstance(data, list)
    
    def test_api_queue_route_without_system(self, client):
        """Test API queue route without vinyl system."""
        response = client.get('/api/queue')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data == []
    
    def test_api_stats_route_success(self, client, mock_database):
        """Test API stats route success."""
        response = client.get('/api/stats')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'scrobble_stats' in data
        assert 'system_stats' in data
        mock_database.get_scrobble_stats.assert_called_once_with(days=30)
        mock_database.get_recent_stats.assert_called_once_with(hours=24)
    
    def test_api_stats_route_error(self, client, mock_database):
        """Test API stats route with error."""
        mock_database.get_scrobble_stats.side_effect = Exception("Database error")
        
        response = client.get('/api/stats')
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_api_update_config_route_success(self, client):
        """Test API update config route success."""
        config_data = {'audio': {'sample_rate': 48000}}
        response = client.post('/api/config', 
                             data=json.dumps(config_data),
                             content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
    
    def test_api_update_config_route_no_data(self, client):
        """Test API update config route with no data."""
        response = client.post('/api/config', 
                             data=json.dumps({}),
                             content_type='application/json')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_api_update_config_route_invalid_json(self, client):
        """Test API update config route with invalid JSON."""
        # Test with invalid JSON data
        response = client.post('/api/config', 
                             data='invalid json',
                             content_type='application/json')
        # Flask returns 500 for invalid JSON, not 400
        assert response.status_code == 500
    
    def test_api_update_config_route_error(self, client):
        """Test API update config route with error."""
        with patch('src.web_interface.get_config') as mock_get_config:
            config_mock = Mock()
            config_mock.get_web_config.return_value = {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False,
                'update_interval': 5,
                'enable_config_editing': True
            }
            config_mock.get_secret.return_value = 'test_secret_key'
            config_mock.update_config.side_effect = Exception("Config error")
            mock_get_config.return_value = config_mock
            
            web_interface = WebInterface()
            web_interface.app.config['TESTING'] = True
            test_client = web_interface.app.test_client()
            
            config_data = {'audio': {'sample_rate': 48000}}
            response = test_client.post('/api/config', 
                                      data=json.dumps(config_data),
                                      content_type='application/json')
            assert response.status_code == 500
            data = json.loads(response.data)
            assert 'error' in data
    
    def test_api_update_config_disabled(self, client):
        """Test API update config route when disabled."""
        # Create WebInterface with config editing disabled
        with patch('src.web_interface.get_config') as mock_get_config:
            config_mock = Mock()
            config_mock.get_web_config.return_value = {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False,
                'update_interval': 5,
                'enable_config_editing': False
            }
            config_mock.get_secret.return_value = 'test_secret_key'
            mock_get_config.return_value = config_mock
            
            web_interface = WebInterface()
            web_interface.app.config['TESTING'] = True
            test_client = web_interface.app.test_client()
            
            config_data = {'audio': {'sample_rate': 48000}}
            response = test_client.post('/api/config', 
                                      data=json.dumps(config_data),
                                      content_type='application/json')
            assert response.status_code == 403
            data = json.loads(response.data)
            assert 'error' in data
    
    def test_api_get_config_disabled(self, client):
        """Test API get config route when disabled."""
        # Create WebInterface with config editing disabled
        with patch('src.web_interface.get_config') as mock_get_config:
            config_mock = Mock()
            config_mock.get_web_config.return_value = {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False,
                'update_interval': 5,
                'enable_config_editing': False
            }
            config_mock.get_secret.return_value = 'test_secret_key'
            mock_get_config.return_value = config_mock
            
            web_interface = WebInterface()
            web_interface.app.config['TESTING'] = True
            test_client = web_interface.app.test_client()
            
            response = test_client.get('/api/config')
            assert response.status_code == 403
            data = json.loads(response.data)
            assert 'error' in data
    
    def test_api_test_components_route_with_system(self, client):
        """Test API test components route with vinyl system."""
        mock_vinyl_system = Mock()
        mock_vinyl_system.test_components.return_value = {'audio': 'ok', 'recognition': 'ok'}
        
        with patch('src.web_interface.get_config') as mock_get_config:
            config_mock = Mock()
            config_mock.get_web_config.return_value = {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False,
                'update_interval': 5,
                'enable_config_editing': True
            }
            config_mock.get_secret.return_value = 'test_secret_key'
            mock_get_config.return_value = config_mock
            
            web_interface = WebInterface(vinyl_system=mock_vinyl_system)
            web_interface.app.config['TESTING'] = True
            test_client = web_interface.app.test_client()
            
            response = test_client.get('/api/test-components')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'audio' in data
            assert 'recognition' in data
    
    def test_api_test_components_route_without_system(self, client):
        """Test API test components route without vinyl system."""
        response = client.get('/api/test-components')
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_api_control_start_success(self, client):
        """Test API control start route success."""
        mock_vinyl_system = Mock()
        mock_vinyl_system.running = False
        
        with patch('src.web_interface.get_config') as mock_get_config:
            config_mock = Mock()
            config_mock.get_web_config.return_value = {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False,
                'update_interval': 5,
                'enable_config_editing': True
            }
            config_mock.get_secret.return_value = 'test_secret_key'
            mock_get_config.return_value = config_mock
            
            web_interface = WebInterface(vinyl_system=mock_vinyl_system)
            web_interface.app.config['TESTING'] = True
            test_client = web_interface.app.test_client()
            
            response = test_client.post('/api/control/start')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            mock_vinyl_system.start.assert_called_once()
    
    def test_api_control_start_already_running(self, client):
        """Test API control start route when already running."""
        mock_vinyl_system = Mock()
        mock_vinyl_system.running = True
        
        with patch('src.web_interface.get_config') as mock_get_config:
            config_mock = Mock()
            config_mock.get_web_config.return_value = {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False,
                'update_interval': 5,
                'enable_config_editing': True
            }
            config_mock.get_secret.return_value = 'test_secret_key'
            mock_get_config.return_value = config_mock
            
            web_interface = WebInterface(vinyl_system=mock_vinyl_system)
            web_interface.app.config['TESTING'] = True
            test_client = web_interface.app.test_client()
            
            response = test_client.post('/api/control/start')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'error' in data
            mock_vinyl_system.start.assert_not_called()
    
    def test_api_control_stop_success(self, client):
        """Test API control stop route success."""
        mock_vinyl_system = Mock()
        mock_vinyl_system.running = True
        
        with patch('src.web_interface.get_config') as mock_get_config:
            config_mock = Mock()
            config_mock.get_web_config.return_value = {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False,
                'update_interval': 5,
                'enable_config_editing': True
            }
            config_mock.get_secret.return_value = 'test_secret_key'
            mock_get_config.return_value = config_mock
            
            web_interface = WebInterface(vinyl_system=mock_vinyl_system)
            web_interface.app.config['TESTING'] = True
            test_client = web_interface.app.test_client()
            
            response = test_client.post('/api/control/stop')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            mock_vinyl_system.stop.assert_called_once()
    
    def test_api_control_restart_success(self, client):
        """Test API control restart route success."""
        mock_vinyl_system = Mock()
        mock_vinyl_system.running = True
        
        with patch('src.web_interface.get_config') as mock_get_config:
            config_mock = Mock()
            config_mock.get_web_config.return_value = {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False,
                'update_interval': 5,
                'enable_config_editing': True
            }
            config_mock.get_secret.return_value = 'test_secret_key'
            mock_get_config.return_value = config_mock
            
            web_interface = WebInterface(vinyl_system=mock_vinyl_system)
            web_interface.app.config['TESTING'] = True
            test_client = web_interface.app.test_client()
            
            with patch('time.sleep'):
                response = test_client.post('/api/control/restart')
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data['success'] is True
                mock_vinyl_system.stop.assert_called_once()
                mock_vinyl_system.start.assert_called_once()
    
    def test_api_control_unknown_action(self, client):
        """Test API control route with unknown action."""
        mock_vinyl_system = Mock()
        
        with patch('src.web_interface.get_config') as mock_get_config:
            config_mock = Mock()
            config_mock.get_web_config.return_value = {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False,
                'update_interval': 5,
                'enable_config_editing': True
            }
            config_mock.get_secret.return_value = 'test_secret_key'
            mock_get_config.return_value = config_mock
            
            web_interface = WebInterface(vinyl_system=mock_vinyl_system)
            web_interface.app.config['TESTING'] = True
            test_client = web_interface.app.test_client()
            
            response = test_client.post('/api/control/unknown')
            assert response.status_code == 400
            data = json.loads(response.data)
            assert 'error' in data
    
    def test_api_control_without_system(self, client):
        """Test API control route without vinyl system."""
        response = client.post('/api/control/start')
        assert response.status_code == 500
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_api_clear_queue_route(self, client):
        """Test API clear queue route."""
        mock_vinyl_system = Mock()
        mock_scrobbler = Mock()
        mock_scrobbler.clear_queue.return_value = 5  # Return count of cleared items
        mock_vinyl_system.lastfm_scrobbler = mock_scrobbler
        
        with patch('src.web_interface.get_config') as mock_get_config:
            config_mock = Mock()
            config_mock.get_web_config.return_value = {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False,
                'update_interval': 5,
                'enable_config_editing': True
            }
            config_mock.get_secret.return_value = 'test_secret_key'
            mock_get_config.return_value = config_mock
            
            web_interface = WebInterface(vinyl_system=mock_vinyl_system)
            web_interface.app.config['TESTING'] = True
            test_client = web_interface.app.test_client()
            
            response = test_client.post('/api/clear-queue')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['cleared'] == 5
            mock_scrobbler.clear_queue.assert_called_once()
    
    def test_api_clear_duplicates_route(self, client, mock_database):
        """Test API clear duplicates route."""
        mock_vinyl_system = Mock()
        mock_duplicate_detector = Mock()
        mock_duplicate_detector.clear_cache.return_value = 5  # Return count of cleared items
        mock_vinyl_system.duplicate_detector = mock_duplicate_detector
        
        with patch('src.web_interface.get_config') as mock_get_config:
            config_mock = Mock()
            config_mock.get_web_config.return_value = {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False,
                'update_interval': 5,
                'enable_config_editing': True
            }
            config_mock.get_secret.return_value = 'test_secret_key'
            mock_get_config.return_value = config_mock
            
            web_interface = WebInterface(vinyl_system=mock_vinyl_system)
            web_interface.app.config['TESTING'] = True
            test_client = web_interface.app.test_client()
            
            response = test_client.post('/api/clear-duplicates')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['cleared'] == 5
            mock_duplicate_detector.clear_cache.assert_called_once()
    
    def test_socketio_connect_event(self, web_interface):
        """Test SocketIO connect event."""
        mock_socketio = Mock()
        web_interface.socketio = mock_socketio
        
        # Simulate connect event
        web_interface._setup_socketio_events()
        
        # Verify connect handler was registered
        assert mock_socketio.on.called
    
    def test_socketio_disconnect_event(self, web_interface):
        """Test SocketIO disconnect event."""
        mock_socketio = Mock()
        web_interface.socketio = mock_socketio
        
        # Simulate disconnect event
        web_interface._setup_socketio_events()
        
        # Verify disconnect handler was registered
        assert mock_socketio.on.called
    
    def test_socketio_request_status_event(self, web_interface):
        """Test SocketIO request status event."""
        mock_socketio = Mock()
        web_interface.socketio = mock_socketio
        
        # Simulate request status event
        web_interface._setup_socketio_events()
        
        # Verify request status handler was registered
        assert mock_socketio.on.called
    
    def test_socketio_request_recent_scrobbles_event(self, web_interface):
        """Test SocketIO request recent scrobbles event."""
        mock_socketio = Mock()
        web_interface.socketio = mock_socketio
        
        # Simulate request recent scrobbles event
        web_interface._setup_socketio_events()
        
        # Verify request recent scrobbles handler was registered
        assert mock_socketio.on.called
    
    def test_start_updates(self, web_interface):
        """Test starting update thread."""
        web_interface._running = False
        
        with patch('threading.Thread') as mock_thread:
            web_interface.start_updates()
            assert web_interface._running is True
            mock_thread.assert_called_once()
    
    def test_stop_updates(self, web_interface):
        """Test stopping update thread."""
        web_interface._running = True
        web_interface._update_thread = Mock()
        
        web_interface.stop_updates()
        assert web_interface._running is False
        web_interface._update_thread.join.assert_called_once()
    
    def test_update_loop(self, web_interface):
        """Test update loop."""
        web_interface._running = True
        web_interface.vinyl_system = Mock()
        web_interface.vinyl_system.get_status.return_value = {'running': True}
        
        with patch('time.sleep') as mock_sleep:
            # Set running to False after first iteration
            def stop_after_first(*args):
                web_interface._running = False
            
            mock_sleep.side_effect = stop_after_first
            web_interface._update_loop()
    
    def test_run_method(self, web_interface):
        """Test run method."""
        with patch.object(web_interface.socketio, 'run') as mock_run:
            # Don't pass host and port as kwargs to avoid conflict
            web_interface.run()
            # Check that run was called with the app
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == web_interface.app  # First positional arg should be app
    
    def test_create_web_app_function(self):
        """Test create_web_app function."""
        mock_vinyl_system = Mock()
        
        with patch('src.web_interface.get_config') as mock_get_config:
            config_mock = Mock()
            config_mock.get_web_config.return_value = {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False,
                'update_interval': 5,
                'enable_config_editing': True
            }
            config_mock.get_secret.return_value = 'test_secret_key'
            mock_get_config.return_value = config_mock
            
            app, socketio = create_web_app(vinyl_system=mock_vinyl_system)
            assert isinstance(app, Flask)
            assert isinstance(socketio, SocketIO)
    
    def test_web_interface_init_without_secret_key(self):
        """Test WebInterface initialization without secret key."""
        with patch('src.web_interface.get_config') as mock_get_config:
            config_mock = Mock()
            config_mock.get_web_config.return_value = {
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False,
                'update_interval': 5,
                'enable_config_editing': True
            }
            config_mock.get_secret.return_value = None  # No secret key
            mock_get_config.return_value = config_mock
            
            with patch('secrets.token_hex') as mock_token:
                mock_token.return_value = 'generated_secret'
                web_interface = WebInterface()
                assert web_interface.app.config['SECRET_KEY'] == 'generated_secret'
    
    def test_web_interface_init_with_custom_config(self):
        """Test WebInterface initialization with custom config."""
        with patch('src.web_interface.get_config') as mock_get_config:
            config_mock = Mock()
            config_mock.get_web_config.return_value = {
                'host': '127.0.0.1',
                'port': 8080,
                'debug': True,
                'update_interval': 10,
                'enable_config_editing': False
            }
            config_mock.get_secret.return_value = 'test_secret_key'
            mock_get_config.return_value = config_mock
            
            web_interface = WebInterface()
            assert web_interface.host == '127.0.0.1'
            assert web_interface.port == 8080
            assert web_interface.debug is True
            assert web_interface.update_interval == 10
            assert web_interface.enable_config_editing is False 