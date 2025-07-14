#!/bin/bash

# Vinyl Recognition System Maintenance Script
# Performs regular maintenance tasks

set -e

# Configuration
INSTALL_DIR="/opt/vinyl-recognition"
LOG_DIR="$INSTALL_DIR/logs"
DATA_DIR="$INSTALL_DIR/data"
CONFIG_DIR="$INSTALL_DIR/config"
BACKUP_DIR="$INSTALL_DIR/backups"
SERVICE_NAME="vinyl-recognition"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Functions
log_info() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] INFO:${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS:${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

check_disk_space() {
    log_info "Checking disk space..."
    
    # Check root filesystem
    DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    
    if [[ $DISK_USAGE -gt 90 ]]; then
        log_error "Disk space critically low: ${DISK_USAGE}% used"
        return 1
    elif [[ $DISK_USAGE -gt 80 ]]; then
        log_warning "Disk space high: ${DISK_USAGE}% used"
    else
        log_success "Disk space OK: ${DISK_USAGE}% used"
    fi
    
    return 0
}

check_memory_usage() {
    log_info "Checking memory usage..."
    
    # Get memory usage percentage
    MEM_USAGE=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    
    if [[ $MEM_USAGE -gt 90 ]]; then
        log_error "Memory usage critically high: ${MEM_USAGE}%"
        return 1
    elif [[ $MEM_USAGE -gt 80 ]]; then
        log_warning "Memory usage high: ${MEM_USAGE}%"
    else
        log_success "Memory usage OK: ${MEM_USAGE}%"
    fi
    
    return 0
}

check_temperature() {
    log_info "Checking system temperature..."
    
    # Check CPU temperature (Raspberry Pi)
    if [[ -f /sys/class/thermal/thermal_zone0/temp ]]; then
        TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)
        TEMP_C=$((TEMP / 1000))
        
        if [[ $TEMP_C -gt 80 ]]; then
            log_error "CPU temperature critically high: ${TEMP_C}°C"
            return 1
        elif [[ $TEMP_C -gt 70 ]]; then
            log_warning "CPU temperature high: ${TEMP_C}°C"
        else
            log_success "CPU temperature OK: ${TEMP_C}°C"
        fi
    else
        log_info "Temperature monitoring not available"
    fi
    
    return 0
}

check_service_status() {
    log_info "Checking service status..."
    
    if systemctl is-active --quiet $SERVICE_NAME; then
        log_success "Service is running"
        
        # Check if service is responding
        if curl -f -s http://localhost:5000/api/status > /dev/null; then
            log_success "Service is responding to HTTP requests"
        else
            log_warning "Service is running but not responding to HTTP requests"
        fi
    else
        log_error "Service is not running"
        
        # Try to restart service
        log_info "Attempting to restart service..."
        if systemctl restart $SERVICE_NAME; then
            log_success "Service restarted successfully"
        else
            log_error "Failed to restart service"
            return 1
        fi
    fi
    
    return 0
}

rotate_logs() {
    log_info "Rotating logs..."
    
    # Find logs older than 30 days and compress them
    find $LOG_DIR -name "*.log" -type f -mtime +30 ! -name "*.gz" -exec gzip {} \;
    
    # Remove compressed logs older than 90 days
    find $LOG_DIR -name "*.log.gz" -type f -mtime +90 -delete
    
    # Truncate current log if it's too large (>100MB)
    if [[ -f "$LOG_DIR/vinyl_recognizer.log" ]]; then
        LOG_SIZE=$(stat -f%z "$LOG_DIR/vinyl_recognizer.log" 2>/dev/null || stat -c%s "$LOG_DIR/vinyl_recognizer.log" 2>/dev/null || echo 0)
        if [[ $LOG_SIZE -gt 104857600 ]]; then  # 100MB
            log_info "Truncating large log file (${LOG_SIZE} bytes)"
            tail -n 10000 "$LOG_DIR/vinyl_recognizer.log" > "$LOG_DIR/vinyl_recognizer.log.tmp"
            mv "$LOG_DIR/vinyl_recognizer.log.tmp" "$LOG_DIR/vinyl_recognizer.log"
        fi
    fi
    
    log_success "Log rotation completed"
}

backup_configuration() {
    log_info "Backing up configuration..."
    
    # Create backup directory
    mkdir -p $BACKUP_DIR
    
    # Create timestamped backup
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$BACKUP_DIR/config_backup_$TIMESTAMP.tar.gz"
    
    # Backup configuration and database
    tar -czf $BACKUP_FILE -C $INSTALL_DIR config data
    
    # Remove backups older than 30 days
    find $BACKUP_DIR -name "config_backup_*.tar.gz" -type f -mtime +30 -delete
    
    log_success "Configuration backed up to $BACKUP_FILE"
}

clean_temporary_files() {
    log_info "Cleaning temporary files..."
    
    # Remove old temporary audio files
    find /tmp -name "vinyl_track_*.wav" -type f -mtime +1 -delete 2>/dev/null || true
    
    # Clean up any core dumps
    find $INSTALL_DIR -name "core.*" -type f -delete 2>/dev/null || true
    
    # Remove old Python cache files
    find $INSTALL_DIR -name "*.pyc" -type f -delete 2>/dev/null || true
    find $INSTALL_DIR -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    
    log_success "Temporary files cleaned"
}

optimize_database() {
    log_info "Optimizing database..."
    
    if [[ -f "$DATA_DIR/vinyl_recognizer.db" ]]; then
        # Vacuum database to reclaim space
        sqlite3 "$DATA_DIR/vinyl_recognizer.db" "VACUUM;"
        
        # Analyze tables for query optimization
        sqlite3 "$DATA_DIR/vinyl_recognizer.db" "ANALYZE;"
        
        log_success "Database optimized"
    else
        log_info "No database file found, skipping optimization"
    fi
}

update_system_packages() {
    log_info "Updating system packages..."
    
    # Only run on Sundays (weekly update)
    if [[ $(date +%u) -eq 7 ]]; then
        apt update
        
        # Check for upgrades
        UPGRADES=$(apt list --upgradable 2>/dev/null | grep -c upgradable || echo 0)
        
        if [[ $UPGRADES -gt 0 ]]; then
            log_info "Found $UPGRADES package updates available"
            
            # Perform upgrade
            apt upgrade -y
            
            # Clean package cache
            apt autoremove -y
            apt autoclean
            
            log_success "System packages updated"
            
            # Check if reboot is needed
            if [[ -f /var/run/reboot-required ]]; then
                log_warning "System reboot required after updates"
            fi
        else
            log_success "System packages are up to date"
        fi
    else
        log_info "Skipping package update (not Sunday)"
    fi
}

generate_health_report() {
    log_info "Generating health report..."
    
    REPORT_FILE="$LOG_DIR/health_report_$(date +%Y%m%d).log"
    
    {
        echo "=== Vinyl Recognition System Health Report ==="
        echo "Generated: $(date)"
        echo
        
        echo "=== System Information ==="
        echo "Hostname: $(hostname)"
        echo "OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)"
        echo "Kernel: $(uname -r)"
        echo "Architecture: $(uname -m)"
        echo
        
        echo "=== Resource Usage ==="
        echo "CPU Usage: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)%"
        echo "Memory Usage: $(free | awk 'NR==2{printf "%.1f%%", $3*100/$2}')"
        echo "Disk Usage: $(df / | awk 'NR==2 {print $5}')"
        
        if [[ -f /sys/class/thermal/thermal_zone0/temp ]]; then
            TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)
            echo "CPU Temperature: $((TEMP / 1000))°C"
        fi
        echo
        
        echo "=== Service Status ==="
        systemctl status $SERVICE_NAME --no-pager
        echo
        
        echo "=== Recent Errors ==="
        journalctl -u $SERVICE_NAME --since "24 hours ago" -p err --no-pager | tail -20
        
    } > $REPORT_FILE
    
    log_success "Health report saved to $REPORT_FILE"
}

# Main maintenance function
run_maintenance() {
    local MAINTENANCE_TYPE=${1:-"daily"}
    
    log_info "Starting $MAINTENANCE_TYPE maintenance..."
    
    # Always run these checks
    check_disk_space
    check_memory_usage
    check_temperature
    check_service_status
    clean_temporary_files
    
    # Daily maintenance
    if [[ $MAINTENANCE_TYPE == "daily" ]] || [[ $MAINTENANCE_TYPE == "weekly" ]]; then
        rotate_logs
        optimize_database
        generate_health_report
    fi
    
    # Weekly maintenance
    if [[ $MAINTENANCE_TYPE == "weekly" ]]; then
        backup_configuration
        update_system_packages
    fi
    
    log_success "$MAINTENANCE_TYPE maintenance completed"
}

# Script usage
usage() {
    echo "Usage: $0 [daily|weekly|check]"
    echo
    echo "  daily   - Run daily maintenance tasks (default)"
    echo "  weekly  - Run weekly maintenance tasks"
    echo "  check   - Run system health checks only"
    echo
}

# Main script execution
main() {
    case ${1:-daily} in
        daily)
            run_maintenance "daily"
            ;;
        weekly)
            run_maintenance "weekly"
            ;;
        check)
            check_disk_space
            check_memory_usage
            check_temperature
            check_service_status
            ;;
        -h|--help)
            usage
            ;;
        *)
            log_error "Unknown maintenance type: $1"
            usage
            exit 1
            ;;
    esac
}

# Run if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi