# 🎵 Vinyl Recognition System - Development Plan

## Project Overview
Complete automated vinyl music recognition system for Raspberry Pi that continuously monitors turntable audio, identifies tracks, and scrobbles to Last.fm without user intervention.

## Hardware Target
- **Primary**: Pro-Ject Debut Carbon EVO + Tube Box S2 + Behringer UMC22 + Raspberry Pi 4
- **Adaptable**: Any turntable → preamp → USB audio interface → Raspberry Pi setup

## Core Architecture

### 1. Audio Processing Layer (`audio_processor.py`)
- Real-time audio capture from USB interface
- Silence/music detection algorithms
- Audio buffering and preprocessing
- Level monitoring and automatic gain control

### 2. Music Recognition Layer (`music_recognizer.py`)
- Multi-provider API support (configurable priority):
  - AudD API (audd.io)
  - Shazam API (via shazamio)
  - ACRCloud (optional future addition)
- Failover logic between services
- Confidence scoring and validation
- Rate limiting and error handling

### 3. Scrobbling Layer (`lastfm_scrobbler.py`)
- Last.fm API integration
- Local SQLite queue for offline resilience
- Retry mechanism with exponential backoff
- Timestamp validation (minimum 30s play time)

### 4. Duplicate Detection (`duplicate_detector.py`)
- Track fingerprinting
- Time-based duplicate prevention
- Database persistence for session memory
- Configurable duplicate time windows

### 5. Web Interface (`web_interface.py`)
- Real-time dashboard with WebSocket updates
- System monitoring (CPU, memory, temperature)
- Configuration management interface
- Recent scrobbles display
- Service control (start/stop/restart)
- Log viewing and troubleshooting

### 6. Main Application (`vinyl_recognizer.py`)
- Threading coordination
- Event loop management
- Configuration loading
- Graceful shutdown handling
- Error recovery and logging

## Configuration System

### File Structure
```
config/
├── config.json              # Main configuration (non-sensitive)
├── secrets.env              # API keys and sensitive data (gitignored)
└── config.example.json      # Example configuration template
```

### Configuration Categories
1. **Audio Settings**: Sample rate, buffer size, silence detection thresholds
2. **Recognition Services**: Provider priority, API endpoints, timeout settings
3. **Scrobbling**: Last.fm settings, queue size, retry intervals
4. **Web Interface**: Port, authentication, update intervals
5. **Logging**: Log levels, rotation settings, destinations

### Web-Based Configuration Management
- Real-time configuration editing via web interface
- Input validation and testing
- Configuration backup and restore
- Service restart coordination

## Security & Privacy

### Git Safety
- `.gitignore` for all sensitive files
- `secrets.env` for API keys
- Example configuration files only
- No hardcoded credentials anywhere

### API Key Management
- Environment variable loading
- Secure file permissions (600)
- Clear documentation on key placement
- Validation and testing endpoints

## Database Schema (SQLite)

### Tables
1. **scrobble_queue**: Pending scrobbles with retry logic
2. **scrobble_history**: Successfully scrobbled tracks
3. **duplicate_cache**: Recent track fingerprints
4. **system_stats**: Historical monitoring data
5. **configuration**: Dynamic configuration storage

## Development Tasks

### Phase 1: Core Foundation ✅
- [x] Development plan creation
- [ ] Project structure setup
- [ ] .gitignore and security setup
- [ ] Configuration system implementation
- [ ] Database schema creation

### Phase 2: Audio & Recognition 🔄
- [ ] AudioProcessor implementation
- [ ] MusicRecognizer with multi-API support
- [ ] Audio testing and calibration tools
- [ ] Recognition accuracy testing

### Phase 3: Scrobbling & Data 🔄
- [ ] LastFMScrobbler implementation
- [ ] DuplicateDetector implementation
- [ ] SQLite database integration
- [ ] Queue management and retry logic

### Phase 4: Integration 🔄
- [ ] Main application coordination
- [ ] Threading and event management
- [ ] Error handling and recovery
- [ ] Logging system implementation

### Phase 5: Web Interface 🔄
- [ ] Flask application structure
- [ ] WebSocket real-time updates
- [ ] Configuration management UI
- [ ] System monitoring dashboard
- [ ] Mobile-responsive design

### Phase 6: Deployment 🔄
- [ ] Systemd service configuration
- [ ] Installation scripts
- [ ] Hardware setup documentation
- [ ] Maintenance automation
- [ ] Backup and recovery procedures

### Phase 7: Testing & Polish 🔄
- [ ] End-to-end testing
- [ ] Performance optimization
- [ ] Documentation completion
- [ ] Hardware compatibility testing

## File Structure

```
vinylscrobbles/
├── README.md                 # Main documentation and setup guide
├── DEVELOPMENT_PLAN.md       # This file
├── requirements.txt          # Python dependencies
├── setup.sh                  # Automated installation script
├── .gitignore               # Git ignore rules
├── vinyl_recognizer.py      # Main application entry point
├── config/
│   ├── config.example.json  # Configuration template
│   ├── secrets.example.env  # API key template
│   └── alsa/               # ALSA configuration files
├── src/
│   ├── __init__.py
│   ├── audio_processor.py   # Audio capture and processing
│   ├── music_recognizer.py  # Multi-API recognition
│   ├── lastfm_scrobbler.py  # Last.fm integration
│   ├── duplicate_detector.py # Duplicate prevention
│   ├── database.py          # SQLite database management
│   ├── config_manager.py    # Configuration handling
│   └── web_interface.py     # Flask web application
├── static/                  # Web interface assets
│   ├── css/
│   ├── js/
│   └── img/
├── templates/               # Flask HTML templates
├── scripts/
│   ├── install.sh          # System installation
│   ├── maintenance.sh      # Automated maintenance
│   └── backup.sh           # Configuration backup
├── systemd/
│   └── vinyl-recognition.service # Systemd service file
├── docs/
│   ├── hardware-setup.md   # Hardware configuration guide
│   ├── api-setup.md        # API key configuration
│   └── troubleshooting.md  # Common issues and solutions
└── tests/
    ├── test_audio.py       # Audio processing tests
    ├── test_recognition.py # Recognition tests
    └── test_integration.py # End-to-end tests
```

## API Integration Details

### AudD API (audd.io)
- RESTful API with audio file upload
- Returns track metadata with confidence scores
- Rate limits: Free tier limitations
- Required: API key from audd.io

### Shazam API (shazamio)
- Python library wrapper
- No API key required for basic usage
- Good recognition accuracy
- Rate limits: Library dependent

### Last.fm API
- Scrobbling and metadata retrieval
- Required: API key, secret, and user authentication
- Session-based authentication flow
- Standard rate limiting

## Performance Targets

### System Requirements
- **CPU**: <20% average on Raspberry Pi 4
- **Memory**: <512MB RAM usage
- **Storage**: <1GB for application + logs
- **Network**: <10MB/hour for API calls

### Recognition Performance
- **Latency**: <10 seconds from track start to identification
- **Accuracy**: >90% for clear vinyl recordings
- **Reliability**: <1% false positive rate
- **Availability**: 99% uptime with automatic recovery

## Deployment Considerations

### Raspberry Pi Optimization
- USB audio interface configuration
- ALSA/PulseAudio setup
- Hardware watchdog integration
- Temperature monitoring
- Automatic log rotation

### Network Resilience
- Offline operation capabilities
- Automatic reconnection logic
- Queue persistence during outages
- Graceful degradation

### Maintenance Automation
- Daily health checks
- Weekly maintenance routines
- Monthly system updates
- Configuration backups
- Log archival

## Success Criteria

1. **Functional**: Successfully recognizes and scrobbles vinyl tracks
2. **Reliable**: Runs unattended for weeks without intervention
3. **Configurable**: Easy setup via web interface
4. **Secure**: No API keys or secrets in public repositories
5. **Documented**: Clear installation and troubleshooting guides
6. **Extensible**: Modular design for easy feature additions

## Current Status: Phase 1 - Foundation
**Next Steps**: Create project structure and implement configuration system

---

*Last Updated: 2025-07-14*
*Status: Planning Complete - Ready for Implementation*