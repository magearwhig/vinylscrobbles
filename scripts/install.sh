#!/bin/bash

# Vinyl Recognition System Installation Script
# For Raspberry Pi with Debian/Ubuntu-based systems

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/vinyl-recognition"
SERVICE_USER="pi"
PYTHON_VERSION="python3"
VENV_DIR="$INSTALL_DIR/venv"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

check_system() {
    log_info "Checking system compatibility..."
    
    # Check OS
    if ! command -v apt &> /dev/null; then
        log_error "This script requires a Debian/Ubuntu-based system with apt"
        exit 1
    fi
    
    # Check Python
    if ! command -v $PYTHON_VERSION &> /dev/null; then
        log_error "Python 3 is required but not installed"
        exit 1
    fi
    
    # Check architecture (Raspberry Pi)
    ARCH=$(uname -m)
    if [[ $ARCH != "armv"* ]] && [[ $ARCH != "aarch64" ]]; then
        log_warning "This system is not a Raspberry Pi. Some features may not work."
    fi
    
    log_success "System compatibility check passed"
}

install_system_dependencies() {
    log_info "Installing system dependencies..."
    
    # Update package list
    apt update
    
    # Install required packages
    apt install -y \
        python3-pip \
        python3-venv \
        python3-dev \
        libasound2-dev \
        portaudio19-dev \
        git \
        nginx \
        sqlite3 \
        alsa-utils \
        alsa-tools \
        build-essential \
        pkg-config \
        libffi-dev \
        libssl-dev
    
    log_success "System dependencies installed"
}

configure_audio() {
    log_info "Configuring audio system..."
    
    # Disable built-in audio (Raspberry Pi)
    if [[ -f /boot/config.txt ]]; then
        if ! grep -q "dtparam=audio=off" /boot/config.txt; then
            echo "dtparam=audio=off" >> /boot/config.txt
            log_info "Disabled built-in audio in /boot/config.txt"
        fi
    fi
    
    # Create ALSA configuration
    cat > /etc/asound.conf << 'EOF'
# Default to USB Audio
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
    usermod -a -G audio $SERVICE_USER
    
    log_success "Audio system configured"
}

create_user_and_directories() {
    log_info "Creating directories and setting permissions..."
    
    # Create installation directory
    mkdir -p $INSTALL_DIR/{config,logs,data,scripts}
    
    # Set ownership
    chown -R $SERVICE_USER:$SERVICE_USER $INSTALL_DIR
    
    # Set permissions
    chmod 755 $INSTALL_DIR
    chmod 700 $INSTALL_DIR/config
    chmod 755 $INSTALL_DIR/logs
    chmod 755 $INSTALL_DIR/data
    
    log_success "Directories created and configured"
}

install_python_application() {
    log_info "Installing Python application..."
    
    # Copy application files
    if [[ -f vinyl_recognizer.py ]]; then
        # Running from source directory
        cp -r . $INSTALL_DIR/
    else
        log_error "Application files not found. Run this script from the project directory."
        exit 1
    fi
    
    # Create virtual environment
    sudo -u $SERVICE_USER $PYTHON_VERSION -m venv $VENV_DIR
    
    # Install Python dependencies
    sudo -u $SERVICE_USER $VENV_DIR/bin/pip install --upgrade pip
    sudo -u $SERVICE_USER $VENV_DIR/bin/pip install -r $INSTALL_DIR/requirements.txt
    
    # Make main script executable
    chmod +x $INSTALL_DIR/vinyl_recognizer.py
    
    log_success "Python application installed"
}

configure_systemd_service() {
    log_info "Configuring systemd service..."
    
    # Copy service file
    cp $INSTALL_DIR/systemd/vinyl-recognition.service /etc/systemd/system/
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable service
    systemctl enable vinyl-recognition.service
    
    log_success "Systemd service configured"
}

configure_nginx() {
    log_info "Configuring nginx for web interface..."
    
    # Create nginx configuration
    cat > /etc/nginx/sites-available/vinyl-recognition << 'EOF'
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF
    
    # Enable site
    ln -sf /etc/nginx/sites-available/vinyl-recognition /etc/nginx/sites-enabled/
    
    # Remove default site
    rm -f /etc/nginx/sites-enabled/default
    
    # Test nginx configuration
    nginx -t
    
    # Restart nginx
    systemctl restart nginx
    systemctl enable nginx
    
    log_success "Nginx configured"
}

setup_configuration() {
    log_info "Setting up configuration files..."
    
    # Copy example configuration if config doesn't exist
    if [[ ! -f $INSTALL_DIR/config/config.json ]]; then
        sudo -u $SERVICE_USER cp $INSTALL_DIR/config/config.example.json $INSTALL_DIR/config/config.json
    fi
    
    # Set proper permissions on configuration
    chown $SERVICE_USER:$SERVICE_USER $INSTALL_DIR/config/config.json
    chmod 600 $INSTALL_DIR/config/config.json
    
    log_success "Configuration files set up"
}

setup_logrotate() {
    log_info "Setting up log rotation..."
    
    cat > /etc/logrotate.d/vinyl-recognition << 'EOF'
/opt/vinyl-recognition/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 644 pi pi
    postrotate
        systemctl reload vinyl-recognition.service || true
    endscript
}
EOF
    
    log_success "Log rotation configured"
}

display_next_steps() {
    log_success "Installation completed successfully!"
    echo
    echo -e "${BLUE}Next Steps:${NC}"
    echo "1. Configure API keys in: $INSTALL_DIR/config/secrets.env"
    echo "   - Copy from: $INSTALL_DIR/config/secrets.example.env"
    echo "   - Add your Last.fm and AudD API keys"
    echo
    echo "2. Test audio setup:"
    echo "   sudo -u $SERVICE_USER arecord -l"
    echo "   sudo -u $SERVICE_USER arecord -D hw:1,0 -d 5 /tmp/test.wav"
    echo
    echo "3. Start the service:"
    echo "   sudo systemctl start vinyl-recognition"
    echo "   sudo systemctl status vinyl-recognition"
    echo
    echo "4. View logs:"
    echo "   sudo journalctl -u vinyl-recognition -f"
    echo
    echo "5. Access web interface:"
    echo "   http://$(hostname -I | awk '{print $1}')"
    echo
    echo -e "${YELLOW}Important:${NC} Reboot recommended to ensure all audio changes take effect"
}

# Main installation process
main() {
    echo "🎵 Vinyl Recognition System Installer"
    echo "======================================"
    echo
    
    check_root
    check_system
    install_system_dependencies
    configure_audio
    create_user_and_directories
    install_python_application
    configure_systemd_service
    configure_nginx
    setup_configuration
    setup_logrotate
    
    display_next_steps
}

# Run main function
main "$@"