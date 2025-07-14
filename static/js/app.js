// Vinyl Recognition System - Main JavaScript

let socket;
let connectionStatus = false;

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    initializeWebSocket();
    updateConnectionStatus(false);
    
    // Request initial status update
    setTimeout(() => {
        if (socket && socket.connected) {
            socket.emit('request_status');
        }
    }, 1000);
});

// WebSocket initialization
function initializeWebSocket() {
    socket = io();
    
    socket.on('connect', function() {
        console.log('Connected to server');
        updateConnectionStatus(true);
        socket.emit('request_status');
    });
    
    socket.on('disconnect', function() {
        console.log('Disconnected from server');
        updateConnectionStatus(false);
    });
    
    socket.on('status_update', function(data) {
        updateSystemStatus(data);
    });
    
    socket.on('recent_scrobbles', function(data) {
        updateRecentScrobbles(data);
    });
    
    socket.on('error', function(error) {
        console.error('Socket error:', error);
        showNotification('WebSocket error: ' + error, 'error');
    });
}

// Update connection status indicator
function updateConnectionStatus(connected) {
    connectionStatus = connected;
    const statusElement = document.getElementById('connection-status');
    const statusText = document.getElementById('status-text');
    
    if (statusElement && statusText) {
        if (connected) {
            statusElement.className = 'navbar-text connected';
            statusText.textContent = 'Connected';
        } else {
            statusElement.className = 'navbar-text disconnected';
            statusText.textContent = 'Disconnected';
        }
    }
}

// Update system status display
function updateSystemStatus(status) {
    // System running status
    updateElement('system-running', status.running ? 'Running' : 'Stopped', 
                 status.running ? 'bg-success' : 'bg-danger');
    
    // Uptime
    if (status.uptime) {
        updateElement('system-uptime', formatUptime(status.uptime));
    }
    
    // Audio status
    if (status.audio) {
        updateElement('audio-device', status.audio.device_name || 'Unknown');
        updateElement('is-recording', status.audio.is_recording ? 'Yes' : 'No',
                     status.audio.is_recording ? 'bg-success' : 'bg-secondary');
        updateElement('music-detected', status.audio.music_detected ? 'Yes' : 'No',
                     status.audio.music_detected ? 'bg-success' : 'bg-secondary');
        updateElement('recording-duration', 
                     status.audio.recording_duration ? status.audio.recording_duration.toFixed(1) + 's' : '0s');
    }
    
    // Recognition providers
    if (status.recognition && status.recognition.provider_order) {
        updateElement('recognition-providers', status.recognition.provider_order.join(', '));
    }
    
    // Last.fm status
    if (status.scrobbling) {
        updateElement('lastfm-status', status.scrobbling.available ? 'Connected' : 'Disconnected',
                     status.scrobbling.available ? 'bg-success' : 'bg-danger');
        updateElement('queue-size', status.scrobbling.queue_size || 0);
    }
    
    // Statistics
    if (status.stats) {
        updateElement('tracks-processed', status.stats.tracks_processed || 0);
        updateElement('tracks-recognized', status.stats.tracks_recognized || 0);
        updateElement('stat-scrobbles', status.stats.tracks_scrobbled || 0);
        updateElement('stat-duplicates', status.stats.duplicates_detected || 0);
        updateElement('stat-errors', status.stats.errors || 0);
    }
    
    // System health (if available)
    updateSystemHealth(status);
}

// Update system health indicators
function updateSystemHealth(status) {
    // Try to get recent system stats
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            if (data.system_stats && data.system_stats.length > 0) {
                const latest = data.system_stats[0];
                
                if (latest.cpu_usage !== null) {
                    updateElement('cpu-usage', latest.cpu_usage.toFixed(1) + '%');
                    updateProgressBar('cpu-progress', latest.cpu_usage);
                }
                
                if (latest.memory_usage !== null) {
                    updateElement('memory-usage', latest.memory_usage.toFixed(1) + '%');
                    updateProgressBar('memory-progress', latest.memory_usage);
                }
                
                if (latest.temperature !== null) {
                    updateElement('temperature', latest.temperature.toFixed(1) + '°C');
                }
            }
        })
        .catch(error => {
            console.debug('Could not load system health data:', error);
        });
}

// Update recent scrobbles display
function updateRecentScrobbles(scrobbles) {
    if (typeof displayRecentScrobbles === 'function') {
        displayRecentScrobbles(scrobbles);
    }
}

// Utility functions
function updateElement(id, value, className = null) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;
        if (className) {
            element.className = element.className.replace(/bg-\w+/g, '') + ' ' + className;
        }
    }
}

function updateProgressBar(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.style.width = Math.min(value, 100) + '%';
        
        // Update color based on value
        element.className = 'progress-bar';
        if (value > 80) {
            element.classList.add('bg-danger');
        } else if (value > 60) {
            element.classList.add('bg-warning');
        } else {
            element.classList.add('bg-success');
        }
    }
}

function formatUptime(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (days > 0) {
        return `${days}d ${hours}h ${minutes}m`;
    } else if (hours > 0) {
        return `${hours}h ${minutes}m`;
    } else {
        return `${minutes}m`;
    }
}

// Notification system
function showNotification(message, type = 'info', duration = 5000) {
    const notification = document.createElement('div');
    notification.className = `notification alert alert-dismissible notification-${type}`;
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after duration
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, duration);
    
    // Enable Bootstrap dismiss functionality
    const dismissButton = notification.querySelector('.btn-close');
    if (dismissButton) {
        dismissButton.addEventListener('click', () => {
            notification.remove();
        });
    }
}

// API helper functions
function apiRequest(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
        },
    };
    
    return fetch(url, { ...defaultOptions, ...options })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        });
}

// Error handling
function handleApiError(error, defaultMessage = 'An error occurred') {
    console.error('API Error:', error);
    
    let message = defaultMessage;
    if (error.message) {
        message = error.message;
    }
    
    showNotification(message, 'error');
}

// Periodic status updates
setInterval(() => {
    if (socket && socket.connected) {
        socket.emit('request_status');
    }
}, 30000); // Update every 30 seconds

// Page visibility handling
document.addEventListener('visibilitychange', function() {
    if (!document.hidden && socket && socket.connected) {
        // Page became visible, request fresh data
        socket.emit('request_status');
        socket.emit('request_recent_scrobbles');
    }
});

// Global error handler
window.addEventListener('error', function(event) {
    console.error('Global error:', event.error);
});

// Utility: Format timestamp
function formatTimestamp(timestamp) {
    return new Date(timestamp * 1000).toLocaleString();
}

// Utility: Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Export functions for use in other scripts
window.VinylApp = {
    showNotification,
    apiRequest,
    handleApiError,
    formatTimestamp,
    formatFileSize,
    updateElement,
    updateProgressBar
};