# 🎵 Vinyl Recognition System

A comprehensive automated vinyl music recognition system for Raspberry Pi that continuously monitors turntable audio, identifies tracks using multiple recognition APIs, and automatically scrobbles to Last.fm without user intervention.

## ✨ Features

- **Automated Audio Detection**: Continuously monitors turntable audio with silence/music detection
- **Multi-Provider Recognition**: Supports AudD and Shazam APIs with configurable priority and failover
- **Last.fm Scrobbling**: Automatic scrobbling with offline queue and retry logic
- **Duplicate Prevention**: Smart duplicate detection prevents re-scrobbling the same track
- **Web Interface**: Real-time monitoring dashboard with system stats and configuration
- **Hardware Optimized**: Designed for Raspberry Pi with USB audio interfaces
- **Self-Healing**: Automatic recovery, health monitoring, and maintenance
- **Secure**: API keys stored separately, never committed to version control

## 🔧 Hardware Requirements

### Tested Configuration
- **Turntable**: Pro-Ject Debut Carbon EVO (or any turntable with line output)
- **Preamp**: Tube Box S2 (or any phono preamp with line output)
- **Audio Interface**: Behringer UMC22 USB Audio Interface
- **Computer**: Raspberry Pi 4 (4GB RAM minimum)
- **Cables**: RCA Y-splitters and RCA-to-TRS adapters

### Compatible Alternatives
- Any turntable → preamp → USB audio interface → Raspberry Pi setup
- USB audio interfaces: Behringer UMC22, Focusrite Scarlett Solo, PreSonus AudioBox USB 96
- Computers: Raspberry Pi 3B+/4, or any Linux system with USB audio support

## 🎛️ Hardware Setup

### Signal Chain
```
Turntable → Preamp → Y-Splitter → [Main Amp + USB Audio Interface] → Raspberry Pi
```

### Detailed Connection Guide

1. **Turntable to Preamp**:
   - Connect turntable RCA outputs to preamp phono inputs
   - Connect turntable ground wire to preamp ground terminal

2. **Preamp to Audio Interface**:
   - Use RCA Y-splitters (Hosa CYA-103 or CYA-105) on preamp line outputs
   - One branch goes to your main amplifier (for listening)
   - Other branch goes to USB audio interface via RCA-to-TRS adapters (Hosa GPR-101)

3. **USB Audio Interface**:
   - Connect to Raspberry Pi via USB cable
   - Use line inputs (not mic inputs)
   - Keep gain settings low to avoid clipping

### Required Hardware Components
- **RCA Y-Splitters**: Hosa CYA-103 (3ft) or CYA-105 (5ft) - ~$15
- **RCA to TRS Adapters**: Hosa GPR-101 (2-pack) - ~$5
- **USB Cable**: Type A to Type B (usually included with audio interface)
- **Total additional cost**: ~$20-30

## 🚀 Installation

### Quick Start (Recommended)

1. **Download and run the automated installer**:
   ```bash
   git clone https://github.com/magearwhig/vinylscrobbles.git
   cd vinylscrobbles
   sudo ./scripts/install.sh
   ```

2. **Configure API keys**:
   ```bash
   # Copy example secrets file
   sudo cp /opt/vinyl-recognition/config/secrets.example.env /opt/vinyl-recognition/config/secrets.env
   
   # Add your Last.fm API key and secret
   sudo nano /opt/vinyl-recognition/config/secrets.env
   
   # Run Last.fm authentication (opens browser)
   cd /opt/vinyl-recognition
   sudo -u pi ./venv/bin/python scripts/lastfm_auth.py
   ```

3. **Start the service**:
   ```bash
   sudo systemctl start vinyl-recognition
   sudo systemctl status vinyl-recognition
   ```

4. **Access web interface**:
   Open `http://your-pi-ip-address` in a web browser

### Manual Installation

If you prefer manual installation or need to customize the setup:

1. **System Dependencies**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install -y python3-pip python3-venv python3-dev \
       libasound2-dev portaudio19-dev git nginx sqlite3 \
       alsa-utils alsa-tools build-essential
   ```

2. **Audio Configuration**:
   ```bash
   # Disable built-in audio (Raspberry Pi)
   echo "dtparam=audio=off" | sudo tee -a /boot/config.txt
   
   # Configure ALSA for USB audio
   sudo tee /etc/asound.conf << 'EOF'
   pcm.!default {
       type hw
       card 1
   }
   ctl.!default {
       type hw
       card 1
   }
   EOF
   
   # Add user to audio group
   sudo usermod -a -G audio $USER
   ```

3. **Application Installation**:
   ```bash
   sudo mkdir -p /opt/vinyl-recognition
   sudo chown $USER:$USER /opt/vinyl-recognition
   cd /opt/vinyl-recognition
   
   # Copy application files
   git clone https://github.com/magearwhig/vinylscrobbles.git .
   
   # Create virtual environment
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Configuration**:
   ```bash
   # Copy configuration templates
   cp config/config.example.json config/config.json
   cp config/secrets.example.env config/secrets.env
   
   # Edit configuration
   nano config/secrets.env  # Add your API keys
   nano config/config.json  # Adjust settings if needed
   ```

5. **Service Setup**:
   ```bash
   sudo cp systemd/vinyl-recognition.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable vinyl-recognition
   sudo systemctl start vinyl-recognition
   ```

## 🔑 API Configuration

### Required API Keys

1. **Last.fm API** (Required for scrobbling):
   - Go to https://www.last.fm/api/account/create
   - Create an application to get API key and secret
   - Add API credentials to `config/secrets.env`:
     ```
     LASTFM_API_KEY=your_api_key_here
     LASTFM_API_SECRET=your_api_secret_here
     ```
   - Run the authentication helper to get session key:
     ```bash
     cd /opt/vinyl-recognition
     source venv/bin/activate
     python scripts/lastfm_auth.py
     ```
   - This will open your browser to authorize the app and automatically save the session key

2. **AudD API** (Optional but recommended):
   - Go to https://audd.io/
   - Sign up for a free account to get API key
   - Add to `config/secrets.env`:
     ```
     AUDD_API_KEY=your_audd_api_key_here
     ```

3. **Flask Secret Key** (Generated automatically):
   ```bash
   # Generate a secure key
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   Add to `config/secrets.env`:
   ```
   FLASK_SECRET_KEY=your_generated_key_here
   ```

### Recognition Provider Configuration

The system supports multiple recognition providers with configurable priority:

- **AudD**: Commercial API with high accuracy, requires API key
- **Shazam**: Free recognition via shazamio library, no API key needed
- **Future**: Easy to add ACRCloud, Gracenote, or other providers

Configure provider order in `config/config.json`:
```json
{
  "recognition": {
    "providers": {
      "order": ["audd", "shazam"],
      "audd": {
        "enabled": true,
        "timeout": 30
      },
      "shazam": {
        "enabled": true,
        "timeout": 30
      }
    }
  }
}
```

## 🖥️ Web Interface

The system includes a comprehensive web dashboard accessible at `http://your-pi-ip-address`:

### Features
- **Real-time System Status**: CPU, memory, temperature monitoring
- **Audio Processing**: Live monitoring of recording and detection
- **Recent Scrobbles**: View recently recognized and scrobbled tracks
- **Configuration Management**: Edit settings via web interface
- **Service Control**: Start, stop, restart the recognition system
- **Component Testing**: Test audio input, recognition APIs, Last.fm connection
- **Log Viewing**: Real-time log monitoring with auto-refresh

### Mobile-Friendly
The web interface is responsive and works well on smartphones and tablets for remote monitoring.

## ⚙️ Configuration

### Key Configuration Options

**Audio Settings** (`config/config.json`):
```json
{
  "audio": {
    "device_name": "USB Audio CODEC",
    "sample_rate": 44100,
    "silence_threshold": 0.01,
    "silence_duration": 2.0,
    "recording_duration": 30.0
  }
}
```

**Recognition Settings**:
```json
{
  "recognition": {
    "min_confidence": 0.6,
    "providers": {
      "order": ["audd", "shazam"]
    }
  }
}
```

**Scrobbling Settings**:
```json
{
  "scrobbling": {
    "lastfm": {
      "min_play_time": 30,
      "max_queue_size": 1000,
      "retry_interval": 300
    }
  }
}
```

### Web-Based Configuration
Most settings can be adjusted through the web interface at `http://your-pi-ip/config`

## 🔧 Testing and Troubleshooting

### Audio Testing
```bash
# List audio devices
arecord -l

# Test USB audio input
arecord -D hw:1,0 -d 5 /tmp/test.wav
aplay /tmp/test.wav

# Test with the application
sudo systemctl stop vinyl-recognition
cd /opt/vinyl-recognition
source venv/bin/activate
python -c "from src.audio_processor import AudioProcessor; ap = AudioProcessor(); print(ap.test_audio_input(5))"
```

### Component Testing
Use the web interface at `http://your-pi-ip` and click "Test Components" to verify:
- Audio input functionality
- Recognition API connectivity
- Last.fm authentication
- Database operations

### Service Diagnostics
```bash
# Check service status
sudo systemctl status vinyl-recognition

# View real-time logs
sudo journalctl -u vinyl-recognition -f

# Check resource usage
htop
```

### Common Issues

1. **No audio detected**:
   - Check USB audio device connection
   - Verify audio levels with `alsamixer`
   - Test with `arecord` command above

2. **Recognition not working**:
   - Verify API keys in `config/secrets.env`
   - Check network connectivity
   - Test individual APIs via web interface

3. **Last.fm scrobbling fails**:
   - Verify Last.fm credentials
   - Check that tracks meet minimum play time (30 seconds)
   - Monitor scrobble queue in web interface

4. **High CPU/memory usage**:
   - Adjust audio buffer sizes in configuration
   - Check for memory leaks in logs
   - Consider reducing recognition frequency

## 🔄 Maintenance

### Automated Maintenance
The system includes automated maintenance scripts:

```bash
# Daily maintenance (run via cron)
/opt/vinyl-recognition/scripts/maintenance.sh daily

# Weekly maintenance
/opt/vinyl-recognition/scripts/maintenance.sh weekly

# Health check only
/opt/vinyl-recognition/scripts/maintenance.sh check
```

### Manual Maintenance
```bash
# Update system packages
sudo apt update && sudo apt upgrade

# Backup configuration
sudo cp -r /opt/vinyl-recognition/config /opt/vinyl-recognition/backups/config_$(date +%Y%m%d)

# View database statistics
sqlite3 /opt/vinyl-recognition/data/vinyl_recognizer.db ".tables"

# Clean up old logs
sudo find /opt/vinyl-recognition/logs -name "*.log" -mtime +30 -delete
```

### Cron Setup
Add to `/etc/crontab`:
```
# Daily maintenance at 2 AM
0 2 * * * root /opt/vinyl-recognition/scripts/maintenance.sh daily

# Weekly maintenance on Sunday at 3 AM
0 3 * * 0 root /opt/vinyl-recognition/scripts/maintenance.sh weekly
```

## 🔒 Security

### API Key Protection
- API keys stored in `config/secrets.env` (gitignored)
- File permissions set to 600 (owner read/write only)
- Never committed to version control
- Web interface sanitizes sensitive data

### System Security
- Service runs as non-root user (`pi`)
- Systemd security restrictions enabled
- Web interface uses secure session management
- Database access restricted to application user

### Network Security
- Web interface bound to local network only by default
- No external ports opened by default
- Consider firewall rules for additional security

## 📊 Performance

### System Requirements
- **CPU**: <20% average on Raspberry Pi 4
- **Memory**: <512MB RAM usage
- **Storage**: <1GB for application + logs
- **Network**: <10MB/hour for API calls

### Optimization Tips
1. **Audio Buffer Tuning**: Adjust `chunk_size` for your hardware
2. **Recognition Frequency**: Balance accuracy vs. resource usage
3. **Database Maintenance**: Regular VACUUM and cleanup
4. **Log Rotation**: Automatic log management prevents disk filling

## 🔧 Development

### Project Structure
```
vinylscrobbles/
├── vinyl_recognizer.py          # Main application entry point
├── src/                         # Core application modules
│   ├── audio_processor.py       # Audio capture and processing
│   ├── music_recognizer.py      # Multi-API recognition
│   ├── lastfm_scrobbler.py      # Last.fm integration
│   ├── duplicate_detector.py    # Duplicate prevention
│   ├── database.py              # SQLite database management
│   ├── config_manager.py        # Configuration handling
│   └── web_interface.py         # Flask web application
├── templates/                   # HTML templates
├── static/                      # CSS, JavaScript, images
├── config/                      # Configuration files
├── scripts/                     # Installation and maintenance
├── systemd/                     # Service configuration
└── requirements.txt             # Python dependencies
```

### Adding Recognition Providers
To add a new recognition provider:

1. Create a new provider class in `music_recognizer.py`:
   ```python
   class NewProvider(BaseRecognitionProvider):
       def __init__(self, config):
           super().__init__('newprovider', config)
       
       async def recognize(self, audio_file):
           # Implementation here
           pass
   ```

2. Add provider to configuration
3. Update provider initialization in `MusicRecognizer`

### Testing
```bash
# Run unit tests
python -m pytest tests/

# Test specific component
python -m pytest tests/test_audio.py

# Integration test
python -m pytest tests/test_integration.py
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

### Development Setup
```bash
git clone https://github.com/magearwhig/vinylscrobbles.git
cd vinylscrobbles
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

The MIT License is particularly suitable for this project as it:
- Allows commercial use and modification
- Requires only that the license and copyright notice be preserved
- Provides no warranty (appropriate for AI-generated code)
- Is compatible with most other open-source licenses

## 🙏 Acknowledgments

- **Hardware Documentation**: Based on Pro-Ject and Behringer integration guides
- **Recognition APIs**: AudD.io and Shazam for music identification services
- **Last.fm**: For scrobbling API and music metadata
- **Open Source Libraries**: PyAudio, Flask, SQLite, and many others

## 📞 Support

### Getting Help
1. Check the troubleshooting section above
2. Review logs via web interface or `journalctl`
3. Test components individually via web interface
4. Check GitHub issues for similar problems

### Reporting Issues
When reporting issues, please include:
- Hardware configuration (turntable, preamp, audio interface, Pi model)
- Software versions (`git rev-parse HEAD`, `python --version`)
- Relevant log entries
- Steps to reproduce the issue

### Feature Requests
We welcome feature requests! Please describe:
- Use case and motivation
- Proposed implementation approach
- Any relevant examples or references

---

**🎵 Happy vinyl listening and automatic scrobbling! 🎵**