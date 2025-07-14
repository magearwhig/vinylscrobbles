# 🎶 Complete Raspberry Pi Vinyl Recognition System

A comprehensive guide to building a fully automated vinyl music recognition system that continuously monitors, identifies, and scrobbles music to Last.fm without user intervention.

---

## 🧱 Hardware Foundation and Initial Setup

- **Core components**:
  - Raspberry Pi 4 (4GB RAM minimum)
  - Behringer UMC22 USB Audio Interface

- **Features**:
  - Professional-grade ADC: 48kHz/16-bit
  - USB Audio Class 2.0 compliant
  - Real-time processing + RIAA equalization

---

## 🖥️ System Installation Overview

### Raspberry Pi OS Setup

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y alsa-utils alsa-tools libasound2-dev \
python3-pip python3-venv git nginx sqlite3 portaudio19-dev python3-dev
```

### ALSA Audio Configuration

Create `~/.asoundrc` and `/etc/asound.conf` to prioritize USB audio input. Disable built-in audio via:

```bash
sudo nano /etc/modprobe.d/raspi-blacklist.conf
```

Add:

```
blacklist snd_bcm2835
```

---

## 🐍 Python Environment and Application Setup

### Create Directory & Environment

```bash
sudo mkdir -p /opt/vinyl-recognition/{config,logs,scripts,data}
cd /opt/vinyl-recognition
python3 -m venv venv
source venv/bin/activate
```

### Install Packages

```bash
pip install pyaudio requests pylast numpy scipy flask flask-socketio gunicorn
```

---

## 🎛️ Core Application Architecture

Structured into components:

- AudioProcessor
- MusicRecognizer
- LastFMScrobbler
- DuplicateDetector

Key logic:

- Monitors silence/music transitions
- Handles recognition and scrobbling
- Avoids duplicates
- Runs asynchronously with threading

---

## 🎧 Music Recognition via APIs

Supported APIs:

- [AudD API](https://audd.io/)
- [Shazam via shazamio](https://github.com/shazamio)

Recognition logic includes:

- Temporary WAV file creation
- API failover
- Confidence metrics

---

## 📻 Last.fm Scrobbling Logic

Implements:

- Local SQLite scrobble queue
- API authentication
- Retry mechanism
- Timestamp validation (30 seconds minimum play)

---

## ⚙️ Systemd Service Setup

Create `vinyl-recognition.service` for auto-start and resilience.

```ini
[Unit]
Description=Vinyl Music Recognition Service
After=network-online.target sound.target

[Service]
User=pi
WorkingDirectory=/opt/vinyl-recognition
ExecStart=/opt/vinyl-recognition/venv/bin/python /opt/vinyl-recognition/vinyl_recognizer.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable with:

```bash
sudo systemctl daemon-reload
sudo systemctl enable vinyl-recognition.service
```

---

## 🌐 Web Interface (Flask + WebSocket)

Real-time monitor dashboard:

- CPU, memory, temperature stats
- Recent scrobbles
- Manual service control
- Logs and troubleshooting

Available at: `http://<your-local-ip>:5000`

---

## 🛠️ Maintenance Automation

Create `maintenance.sh` to handle:

- Disk/memory/temperature checks
- Log rotation and cleanup
- Configuration backups
- Monthly system updates

Add to `crontab`:

```
0 2 * * * /opt/vinyl-recognition/scripts/maintenance.sh  # Daily health
0 3 * * 0 /opt/vinyl-recognition/scripts/maintenance.sh  # Weekly maintenance
```

---

## 🔁 Watchdog Configuration

Enable hardware watchdog recovery:

```bash
echo 'dtparam=watchdog=on' | sudo tee -a /boot/config.txt
sudo apt install watchdog
```

Modify `/etc/watchdog.conf` with:

```
watchdog-device = /dev/watchdog
watchdog-timeout = 15
ping = 8.8.8.8
```

---

## 🧪 Troubleshooting Workflow

### Audio Issues

- Run `lsusb`, `aplay -l`, `arecord -l`
- Use `arecord` test to validate capture
- Monitor logs via:

```bash
journalctl -u vinyl-recognition -f
```

---

## ✅ Conclusion

This system offers:

- Fully automated vinyl music recognition
- Continuous scrobbling to Last.fm
- Self-healing, headless, and remotely accessible monitoring
- Extensible architecture with modular components

Once configured, it provides a “set it and forget it” solution with professional-grade results.
