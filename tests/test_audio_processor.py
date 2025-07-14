import pytest
import numpy as np
import tempfile
import os
import time
import threading
from unittest.mock import Mock, patch, MagicMock, call

from src.audio_processor import AudioProcessor


class TestAudioProcessor:
    """Test AudioProcessor class."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        with patch('src.audio_processor.get_config') as mock_get_config:
            config_mock = Mock()
            config_mock.get_audio_config.return_value = {
                'device_name': 'Test Device',
                'sample_rate': 44100,
                'chunk_size': 1024,
                'channels': 2,
                'format': 'int16',
                'silence_threshold': 0.01,
                'silence_duration': 2.0,
                'recording_duration': 30.0,
                'max_recording_duration': 120.0
            }
            mock_get_config.return_value = config_mock
            yield mock_get_config
    
    @pytest.fixture
    def mock_pyaudio(self):
        """Mock PyAudio."""
        with patch('src.audio_processor.pyaudio') as mock_pyaudio_module:
            # Mock PyAudio constants
            mock_pyaudio_module.paInt16 = 8
            mock_pyaudio_module.paInt24 = 9
            mock_pyaudio_module.paInt32 = 10
            mock_pyaudio_module.paFloat32 = 11
            
            # Mock PyAudio class
            mock_pyaudio = Mock()
            mock_pyaudio_module.PyAudio.return_value = mock_pyaudio
            
            # Mock device info - provide enough devices to avoid StopIteration
            mock_pyaudio.get_device_count.return_value = 3
            mock_pyaudio.get_device_info_by_index.side_effect = [
                {'name': 'Test Device', 'maxInputChannels': 2},
                {'name': 'Other Device', 'maxInputChannels': 1},
                {'name': 'Another Device', 'maxInputChannels': 0}
            ]
            mock_pyaudio.get_default_input_device_info.return_value = {
                'name': 'Default Device',
                'index': 0
            }
            
            # Mock stream
            mock_stream = Mock()
            mock_stream.is_active.return_value = True
            mock_stream.read.return_value = b'\x00\x01\x02\x03' * 1024
            mock_pyaudio.open.return_value = mock_stream
            
            yield mock_pyaudio
    
    def test_audio_processor_creation(self, mock_config, mock_pyaudio):
        """Test AudioProcessor creation."""
        processor = AudioProcessor()
        assert processor.device_name == 'Test Device'
        assert processor.sample_rate == 44100
        assert processor.chunk_size == 1024
        assert processor.channels == 2
        assert processor.silence_threshold == 0.01
        assert processor.is_running is False
        assert processor.is_recording is False
    
    def test_audio_processor_start_stop(self, mock_config, mock_pyaudio):
        """Test AudioProcessor start and stop monitoring."""
        processor = AudioProcessor()
        
        # Mock the audio loop to avoid infinite loop
        with patch.object(processor, '_audio_loop'):
            processor.start_monitoring()
            assert processor.is_running is True
            assert processor._audio_thread is not None
            # Don't check if thread is alive since it's mocked and may not actually run
            
            processor.stop_monitoring()
            assert processor.is_running is False
    
    def test_audio_processor_get_status(self, mock_config, mock_pyaudio):
        """Test AudioProcessor get_status method."""
        processor = AudioProcessor()
        status = processor.get_status()
        
        assert 'is_running' in status
        assert 'is_recording' in status
        assert 'device_name' in status
        assert 'sample_rate' in status
        assert 'channels' in status
        assert 'silence_threshold' in status
        assert 'recording_duration' in status
        assert 'music_detected' in status
        assert 'silence_duration' in status
    
    def test_audio_processor_cleanup(self, mock_config, mock_pyaudio):
        """Test AudioProcessor cleanup."""
        processor = AudioProcessor()
        processor.cleanup()
        
        # Verify PyAudio was terminated
        mock_pyaudio.terminate.assert_called_once()
    
    def test_find_input_device_success(self, mock_config, mock_pyaudio):
        """Test finding input device successfully."""
        processor = AudioProcessor()
        # The device should already be found during initialization
        assert processor.input_device_index == 0  # First device matches
    
    def test_find_input_device_fallback(self, mock_config, mock_pyaudio):
        """Test finding input device with fallback to default."""
        # Create a new processor with different mock setup
        with patch('src.audio_processor.pyaudio') as mock_pyaudio_module:
            # Mock PyAudio constants
            mock_pyaudio_module.paInt16 = 8
            
            # Mock PyAudio class
            mock_audio_instance = Mock()
            mock_pyaudio_module.PyAudio.return_value = mock_audio_instance
            
            # Mock no matching devices but provide default
            mock_audio_instance.get_device_count.return_value = 2
            mock_audio_instance.get_device_info_by_index.side_effect = [
                {'name': 'Other Device 1', 'maxInputChannels': 2},
                {'name': 'Other Device 2', 'maxInputChannels': 1}
            ]
            mock_audio_instance.get_default_input_device_info.return_value = {
                'name': 'Default Device',
                'index': 5
            }
            
            # Mock stream
            mock_stream = Mock()
            mock_audio_instance.open.return_value = mock_stream
            
            processor = AudioProcessor()
            assert processor.input_device_index == 5
    
    def test_find_input_device_no_devices(self, mock_config, mock_pyaudio):
        """Test finding input device when no devices available."""
        # Create a new processor with different mock setup
        with patch('src.audio_processor.pyaudio') as mock_pyaudio_module:
            # Mock PyAudio constants
            mock_pyaudio_module.paInt16 = 8
            
            # Mock PyAudio class
            mock_audio_instance = Mock()
            mock_pyaudio_module.PyAudio.return_value = mock_audio_instance
            
            # Mock no devices and no default device
            mock_audio_instance.get_device_count.return_value = 0
            mock_audio_instance.get_default_input_device_info.side_effect = Exception("No default device")
            
            # This should raise an exception during initialization
            with pytest.raises(RuntimeError, match="Audio device 'Test Device' not found"):
                AudioProcessor()
    
    def test_open_stream_success(self, mock_config, mock_pyaudio):
        """Test opening audio stream successfully."""
        processor = AudioProcessor()
        processor._open_stream()
        
        mock_pyaudio.open.assert_called_once()
        assert processor.stream is not None
    
    def test_open_stream_failure(self, mock_config, mock_pyaudio):
        """Test opening audio stream with failure."""
        mock_pyaudio.open.side_effect = Exception("Stream open failed")
        
        processor = AudioProcessor()
        with pytest.raises(Exception, match="Stream open failed"):
            processor._open_stream()
    
    def test_close_stream(self, mock_config, mock_pyaudio):
        """Test closing audio stream."""
        processor = AudioProcessor()
        # Create a proper mock stream
        mock_stream = Mock()
        processor.stream = mock_stream
        processor._close_stream()
        
        mock_stream.stop_stream.assert_called_once()
        mock_stream.close.assert_called_once()
        assert processor.stream is None
    
    def test_close_stream_none(self, mock_config, mock_pyaudio):
        """Test closing audio stream when stream is None."""
        processor = AudioProcessor()
        processor.stream = None
        processor._close_stream()  # Should not raise exception
    
    def test_process_audio_chunk_silence(self, mock_config, mock_pyaudio):
        """Test processing audio chunk with silence."""
        processor = AudioProcessor()
        
        # Create silent audio data
        silent_data = np.zeros(1024, dtype=np.int16)
        
        with patch.object(processor, '_handle_silence') as mock_handle_silence:
            processor._process_audio_chunk(silent_data)
            mock_handle_silence.assert_called_once()
    
    def test_process_audio_chunk_music(self, mock_config, mock_pyaudio):
        """Test processing audio chunk with music."""
        processor = AudioProcessor()
        
        # Create music audio data (non-zero)
        music_data = np.random.randint(-1000, 1000, 1024, dtype=np.int16)
        
        with patch.object(processor, '_handle_music') as mock_handle_music:
            processor._process_audio_chunk(music_data)
            mock_handle_music.assert_called_once()
    
    def test_process_audio_chunk_empty(self, mock_config, mock_pyaudio):
        """Test processing empty audio chunk."""
        processor = AudioProcessor()
        
        # Create empty audio data
        empty_data = np.array([], dtype=np.int16)
        
        with patch.object(processor, '_handle_silence') as mock_handle_silence:
            processor._process_audio_chunk(empty_data)
            mock_handle_silence.assert_called_once()
    
    def test_handle_silence_start_recording(self, mock_config, mock_pyaudio):
        """Test handling silence when recording should start."""
        processor = AudioProcessor()
        processor.is_recording = True
        processor.current_recording = [1, 2, 3]  # Some data
        processor.silence_start_time = time.time() - 3.0  # Silence for 3 seconds
        
        with patch.object(processor, '_finish_recording') as mock_finish:
            processor._handle_silence(time.time())
            mock_finish.assert_called_once()
    
    def test_handle_silence_not_long_enough(self, mock_config, mock_pyaudio):
        """Test handling silence when not long enough to finish recording."""
        processor = AudioProcessor()
        processor.is_recording = True
        processor.current_recording = [1, 2, 3]
        processor.silence_start_time = time.time() - 0.5  # Short silence
        
        with patch.object(processor, '_finish_recording') as mock_finish:
            processor._handle_silence(time.time())
            mock_finish.assert_not_called()
    
    def test_handle_music_start_recording(self, mock_config, mock_pyaudio):
        """Test handling music when recording should start."""
        processor = AudioProcessor()
        processor.last_track_end_time = time.time() - 5.0  # Enough time passed
        music_data = np.random.randint(-1000, 1000, 1024, dtype=np.int16)
        
        with patch.object(processor, '_start_recording') as mock_start:
            processor._handle_music(time.time(), music_data)
            mock_start.assert_called_once()
    
    def test_handle_music_continue_recording(self, mock_config, mock_pyaudio):
        """Test handling music when already recording."""
        processor = AudioProcessor()
        processor.is_recording = True
        processor.current_recording = [1, 2, 3]
        music_data = np.random.randint(-1000, 1000, 1024, dtype=np.int16)
        
        processor._handle_music(time.time(), music_data)
        assert len(processor.current_recording) > 3  # Should have added more data
    
    def test_handle_music_max_duration(self, mock_config, mock_pyaudio):
        """Test handling music when max duration is reached."""
        processor = AudioProcessor()
        processor.is_recording = True
        processor.current_recording = [1, 2, 3]
        processor.music_start_time = time.time() - 125.0  # Exceeds max duration
        music_data = np.random.randint(-1000, 1000, 1024, dtype=np.int16)
        
        with patch.object(processor, '_finish_recording') as mock_finish:
            processor._handle_music(time.time(), music_data)
            mock_finish.assert_called_once()
    
    def test_start_recording(self, mock_config, mock_pyaudio):
        """Test starting recording."""
        processor = AudioProcessor()
        processor.is_recording = False
        
        processor._start_recording()
        assert processor.is_recording is True
        assert processor.current_recording == []
    
    def test_start_recording_already_recording(self, mock_config, mock_pyaudio):
        """Test starting recording when already recording."""
        processor = AudioProcessor()
        processor.is_recording = True
        processor.current_recording = [1, 2, 3]
        
        processor._start_recording()
        assert processor.is_recording is True
        # When already recording, the method should not reset current_recording
        assert processor.current_recording == [1, 2, 3]  # Should NOT be reset
    
    def test_finish_recording_too_short(self, mock_config, mock_pyaudio):
        """Test finishing recording that's too short."""
        processor = AudioProcessor()
        processor.is_recording = True
        processor.current_recording = [1, 2, 3]  # Very short recording
        
        with patch.object(processor, '_save_recording') as mock_save:
            processor._finish_recording()
            mock_save.assert_not_called()
            assert processor.current_recording == []
    
    def test_finish_recording_success(self, mock_config, mock_pyaudio):
        """Test finishing recording successfully."""
        processor = AudioProcessor()
        processor.is_recording = True
        processor.sample_rate = 44100
        processor.channels = 2
        # Create recording with enough duration
        processor.current_recording = [1] * (44100 * 2 * 35)  # 35 seconds
        
        with patch.object(processor, '_save_recording') as mock_save:
            mock_save.return_value = '/tmp/test.wav'
            with patch.object(processor, 'on_track_detected') as mock_callback:
                processor._finish_recording()
                mock_save.assert_called_once()
                mock_callback.assert_called_once_with('/tmp/test.wav')
    
    def test_finish_recording_no_callback(self, mock_config, mock_pyaudio):
        """Test finishing recording without callback."""
        processor = AudioProcessor()
        processor.is_recording = True
        processor.on_track_detected = None
        processor.sample_rate = 44100
        processor.channels = 2
        processor.current_recording = [1] * (44100 * 2 * 35)
        
        with patch.object(processor, '_save_recording') as mock_save:
            mock_save.return_value = '/tmp/test.wav'
            processor._finish_recording()  # Should not raise exception
            mock_save.assert_called_once()
    
    def test_save_recording_success(self, mock_config, mock_pyaudio):
        """Test saving recording successfully."""
        processor = AudioProcessor()
        processor.sample_rate = 44100
        processor.channels = 2
        processor.format = 8  # paInt16
        
        audio_data = [1, 2, 3, 4, 5, 6, 7, 8]
        
        with patch('tempfile.mkstemp') as mock_mkstemp:
            mock_mkstemp.return_value = (123, '/tmp/test.wav')  # Valid file descriptor
            with patch('os.close') as mock_close:
                with patch('builtins.open', create=True):
                    with patch('wave.open') as mock_wave:
                        with patch.object(processor.audio, 'get_sample_size', return_value=2):
                            result = processor._save_recording(audio_data)
                            assert result == '/tmp/test.wav'
                            mock_wave.assert_called_once()
                            mock_close.assert_called_once_with(123)
    
    def test_save_recording_failure(self, mock_config, mock_pyaudio):
        """Test saving recording with failure."""
        processor = AudioProcessor()
        
        with patch('tempfile.mkstemp', side_effect=Exception("Save failed")):
            result = processor._save_recording([1, 2, 3])
            assert result is None
    
    def test_test_audio_input_success(self, mock_config, mock_pyaudio):
        """Test audio input testing successfully."""
        processor = AudioProcessor()
        processor.is_running = False
        
        # Mock stream and audio data with proper bytes
        mock_stream = Mock()
        mock_stream.read.return_value = b'\x00\x01\x02\x03' * 256  # Some audio data
        processor.stream = mock_stream
        
        with patch.object(processor, '_open_stream'):
            with patch.object(processor, '_close_stream'):
                success, message, stats = processor.test_audio_input(duration=1.0)
                
                assert success is True
                assert 'successful' in message
                assert stats is not None
                assert 'avg_level' in stats
    
    def test_test_audio_input_already_running(self, mock_config, mock_pyaudio):
        """Test audio input testing when already running."""
        processor = AudioProcessor()
        processor.is_running = True
        
        success, message, stats = processor.test_audio_input()
        
        assert success is False
        assert 'Cannot test while monitoring is active' in message
        assert stats is None
    
    def test_test_audio_input_no_audio(self, mock_config, mock_pyaudio):
        """Test audio input testing with no audio detected."""
        processor = AudioProcessor()
        processor.is_running = False
        
        # Mock stream with silent audio
        mock_stream = Mock()
        mock_stream.read.return_value = b'\x00\x00\x00\x00' * 256  # Silent audio
        processor.stream = mock_stream
        
        with patch.object(processor, '_open_stream'):
            with patch.object(processor, '_close_stream'):
                success, message, stats = processor.test_audio_input(duration=1.0)
                
                assert success is False
                assert 'No audio detected' in message
                assert stats is not None
    
    def test_test_audio_input_stream_error(self, mock_config, mock_pyaudio):
        """Test audio input testing with stream error."""
        processor = AudioProcessor()
        processor.is_running = False
        
        # Mock stream that raises exception
        mock_stream = Mock()
        mock_stream.read.side_effect = Exception("Stream error")
        processor.stream = mock_stream
        
        with patch.object(processor, '_open_stream'):
            with patch.object(processor, '_close_stream'):
                success, message, stats = processor.test_audio_input(duration=1.0)
                
                assert success is False
                assert 'failed' in message
                assert stats is None
    
    def test_audio_loop_exception(self, mock_config, mock_pyaudio):
        """Test audio loop with exception."""
        processor = AudioProcessor()
        
        with patch.object(processor, '_open_stream', side_effect=Exception("Open failed")):
            processor._audio_loop()  # Should handle exception gracefully
    
    def test_audio_loop_stream_inactive(self, mock_config, mock_pyaudio):
        """Test audio loop with inactive stream."""
        processor = AudioProcessor()
        processor.is_running = True
        
        # Mock inactive stream
        mock_stream = Mock()
        mock_stream.is_active.return_value = False
        processor.stream = mock_stream
        
        with patch.object(processor, '_open_stream'):
            with patch('time.sleep') as mock_sleep:
                # Set a limit to prevent infinite loop
                mock_sleep.side_effect = lambda x: setattr(processor, 'is_running', False)
                processor._audio_loop()
                mock_sleep.assert_called()
    
    def test_audio_loop_read_exception(self, mock_config, mock_pyaudio):
        """Test audio loop with read exception."""
        processor = AudioProcessor()
        processor.is_running = True
        
        # Mock stream that raises exception on read
        mock_stream = Mock()
        mock_stream.is_active.return_value = True
        mock_stream.read.side_effect = Exception("Read failed")
        processor.stream = mock_stream
        
        with patch.object(processor, '_open_stream'):
            with patch('time.sleep') as mock_sleep:
                # Set a limit to prevent infinite loop
                mock_sleep.side_effect = lambda x: setattr(processor, 'is_running', False)
                processor._audio_loop()
                mock_sleep.assert_called()
    
    def test_stop_monitoring_no_thread(self, mock_config, mock_pyaudio):
        """Test stopping monitoring when no thread exists."""
        processor = AudioProcessor()
        processor._audio_thread = None
        
        processor.stop_monitoring()  # Should not raise exception
    
    def test_stop_monitoring_thread_timeout(self, mock_config, mock_pyaudio):
        """Test stopping monitoring with thread timeout."""
        processor = AudioProcessor()
        processor._audio_thread = Mock()
        processor._audio_thread.is_alive.return_value = True
        processor._audio_thread.join.return_value = None  # Timeout
        
        processor.stop_monitoring()  # Should handle timeout gracefully
    
    def test_destructor(self, mock_config, mock_pyaudio):
        """Test destructor calls cleanup."""
        processor = AudioProcessor()
        
        with patch.object(processor, 'cleanup') as mock_cleanup:
            processor.__del__()
            mock_cleanup.assert_called_once()
    
    def test_initialize_audio_failure(self, mock_config, mock_pyaudio):
        """Test audio initialization failure."""
        # Create a new processor with different mock setup
        with patch('src.audio_processor.pyaudio') as mock_pyaudio_module:
            # Mock PyAudio constants
            mock_pyaudio_module.paInt16 = 8
            
            # Mock PyAudio class
            mock_audio_instance = Mock()
            mock_pyaudio_module.PyAudio.return_value = mock_audio_instance
            
            # Mock PyAudio failure
            mock_audio_instance.get_device_count.side_effect = Exception("PyAudio failed")
            
            # Should raise Exception when PyAudio fails (implementation raises original exception)
            with pytest.raises(Exception, match="PyAudio failed"):
                AudioProcessor()
    
    def test_initialize_audio_device_not_found(self, mock_config, mock_pyaudio):
        """Test audio initialization when device not found."""
        # Create a new processor with different mock setup
        with patch('src.audio_processor.pyaudio') as mock_pyaudio_module:
            # Mock PyAudio constants
            mock_pyaudio_module.paInt16 = 8
            
            # Mock PyAudio class
            mock_audio_instance = Mock()
            mock_pyaudio_module.PyAudio.return_value = mock_audio_instance
            
            # Mock no matching devices and no default device
            mock_audio_instance.get_device_count.return_value = 2
            mock_audio_instance.get_device_info_by_index.side_effect = [
                {'name': 'Other Device 1', 'maxInputChannels': 2},
                {'name': 'Other Device 2', 'maxInputChannels': 1}
            ]
            mock_audio_instance.get_default_input_device_info.side_effect = Exception("No default device")
            
            with pytest.raises(RuntimeError, match="Audio device 'Test Device' not found"):
                AudioProcessor() 