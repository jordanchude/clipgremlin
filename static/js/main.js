/**
 * ClipGremlin Web Application JavaScript
 * Main functionality and interactions
 */

// Global app object
window.ClipGremlin = {
    // Configuration
    config: {
        apiBaseUrl: '/api',
        refreshInterval: 30000, // 30 seconds
        animationDelay: 100
    },
    
    // State
    state: {
        isLoading: false,
        lastActivityRefresh: null
    },
    
    // Initialize the application
    init: function() {
        this.setupEventListeners();
        this.initializeAnimations();
        this.startPeriodicRefresh();
        
        console.log('ClipGremlin web app initialized');
    },
    
    // Set up global event listeners
    setupEventListeners: function() {
        // Handle form submissions
        document.addEventListener('submit', this.handleFormSubmit.bind(this));
        
        // Handle API errors globally
        window.addEventListener('error', this.handleError.bind(this));
        
        // Handle visibility changes for refresh optimization
        document.addEventListener('visibilitychange', this.handleVisibilityChange.bind(this));
    },
    
    // Initialize scroll animations
    initializeAnimations: function() {
        if (typeof IntersectionObserver === 'undefined') {
            return; // Skip animations if not supported
        }
        
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry, index) => {
                if (entry.isIntersecting) {
                    setTimeout(() => {
                        entry.target.classList.add('fade-in');
                        entry.target.style.opacity = '1';
                        entry.target.style.transform = 'translateY(0)';
                    }, index * this.config.animationDelay);
                }
            });
        }, observerOptions);
        
        // Observe elements that should animate
        document.querySelectorAll('.card, .feature-card, .step-number, .usage-icon').forEach(element => {
            element.style.opacity = '0';
            element.style.transform = 'translateY(20px)';
            element.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
            observer.observe(element);
        });
    },
    
    // Start periodic refresh for dashboard
    startPeriodicRefresh: function() {
        if (window.location.pathname === '/dashboard') {
            setInterval(() => {
                if (!document.hidden && !this.state.isLoading) {
                    this.refreshDashboardData();
                }
            }, this.config.refreshInterval);
        }
    },
    
    // Handle form submissions
    handleFormSubmit: function(event) {
        const form = event.target;
        if (form.classList.contains('ajax-form')) {
            event.preventDefault();
            this.submitFormAjax(form);
        }
    },
    
    // Handle global errors
    handleError: function(event) {
        console.error('Global error:', event.error);
        this.showNotification('An unexpected error occurred', 'error');
    },
    
    // Handle visibility changes
    handleVisibilityChange: function() {
        if (!document.hidden) {
            // Page became visible, refresh data if needed
            const timeSinceLastRefresh = Date.now() - (this.state.lastActivityRefresh || 0);
            if (timeSinceLastRefresh > this.config.refreshInterval) {
                this.refreshDashboardData();
            }
        }
    },
    
    // API helper methods
    api: {
        // Make API request with error handling
        request: async function(endpoint, options = {}) {
            const url = ClipGremlin.config.apiBaseUrl + endpoint;
            
            const defaultOptions = {
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            };
            
            const config = { ...defaultOptions, ...options };
            
            try {
                const response = await fetch(url, config);
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || `HTTP ${response.status}`);
                }
                
                return data;
            } catch (error) {
                console.error(`API request failed: ${endpoint}`, error);
                throw error;
            }
        },
        
        // Get bot status
        getBotStatus: async function() {
            return this.request('/bot/status');
        },
        
        // Toggle bot on/off
        toggleBot: async function() {
            return this.request('/bot/toggle', { method: 'POST' });
        },
        
        // Update settings
        updateSettings: async function(settings) {
            return this.request('/settings', {
                method: 'POST',
                body: JSON.stringify(settings)
            });
        },
        
        // Get activity
        getActivity: async function(page = 1) {
            return this.request(`/activity?page=${page}`);
        }
    },
    
    // Dashboard specific methods
    dashboard: {
        // Refresh all dashboard data
        refresh: async function() {
            try {
                ClipGremlin.state.isLoading = true;
                
                // Refresh activity feed
                await this.refreshActivity();
                
                ClipGremlin.state.lastActivityRefresh = Date.now();
            } catch (error) {
                console.error('Dashboard refresh failed:', error);
                ClipGremlin.showNotification('Failed to refresh dashboard data', 'error');
            } finally {
                ClipGremlin.state.isLoading = false;
            }
        },
        
        // Refresh activity feed
        refreshActivity: async function() {
            try {
                const data = await ClipGremlin.api.getActivity();
                this.updateActivityFeed(data.activities);
            } catch (error) {
                console.error('Activity refresh failed:', error);
            }
        },
        
        // Update activity feed UI
        updateActivityFeed: function(activities) {
            const feed = document.getElementById('activityFeed');
            if (!feed) return;
            
            if (activities.length === 0) {
                feed.innerHTML = `
                    <div class="list-group-item text-center py-5">
                        <i class="fas fa-robot fa-3x text-muted mb-3"></i>
                        <h5 class="text-muted">No activity yet</h5>
                        <p class="text-muted mb-0">Start your bot to see activity here!</p>
                    </div>
                `;
                return;
            }
            
            const activityHtml = activities.map(activity => {
                const iconMap = {
                    'prompt_sent': 'fas fa-comment text-success',
                    'stream_start': 'fas fa-play text-primary',
                    'stream_end': 'fas fa-stop text-danger',
                    'bot_paused': 'fas fa-pause text-warning',
                    'bot_resumed': 'fas fa-play text-success'
                };
                
                const icon = iconMap[activity.type] || 'fas fa-info text-info';
                const timeAgo = this.formatTimeAgo(new Date(activity.timestamp));
                
                return `
                    <div class="list-group-item activity-item">
                        <div class="d-flex w-100 justify-content-between align-items-start">
                            <div class="flex-grow-1">
                                <div class="d-flex align-items-center mb-1">
                                    <i class="${icon} me-2"></i>
                                    <strong>${this.formatActivityType(activity.type)}</strong>
                                    ${activity.language ? `<span class="badge bg-secondary ms-2">${activity.language}</span>` : ''}
                                </div>
                                ${activity.message ? `<p class="mb-1 text-dark">${this.escapeHtml(activity.message)}</p>` : ''}
                            </div>
                            <small class="text-muted ms-3">${timeAgo}</small>
                        </div>
                    </div>
                `;
            }).join('');
            
            feed.innerHTML = activityHtml;
        },
        
        // Format activity type for display
        formatActivityType: function(type) {
            return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        },
        
        // Format time ago
        formatTimeAgo: function(date) {
            const now = new Date();
            const diffInSeconds = Math.floor((now - date) / 1000);
            
            if (diffInSeconds < 60) return 'Just now';
            if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
            if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
            return `${Math.floor(diffInSeconds / 86400)}d ago`;
        }
    },
    
    // Refresh dashboard data
    refreshDashboardData: function() {
        if (window.location.pathname === '/dashboard') {
            this.dashboard.refresh();
        }
    },
    
    // Submit form via AJAX
    submitFormAjax: async function(form) {
        try {
            this.state.isLoading = true;
            this.showLoadingState(form, true);
            
            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());
            
            const response = await this.api.request(form.action.replace(window.location.origin, ''), {
                method: form.method || 'POST',
                body: JSON.stringify(data)
            });
            
            this.showNotification(response.message || 'Success!', 'success');
            
            // Trigger custom event
            form.dispatchEvent(new CustomEvent('formSubmitted', { detail: response }));
            
        } catch (error) {
            this.showNotification(error.message || 'Form submission failed', 'error');
        } finally {
            this.state.isLoading = false;
            this.showLoadingState(form, false);
        }
    },
    
    // Show/hide loading state
    showLoadingState: function(element, loading) {
        if (loading) {
            element.classList.add('loading');
            const submitBtn = element.querySelector('[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Loading...';
            }
        } else {
            element.classList.remove('loading');
            const submitBtn = element.querySelector('[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = submitBtn.dataset.originalText || 'Submit';
            }
        }
    },
    
    // Show notification
    showNotification: function(message, type = 'info', duration = 5000) {
        const alertClass = type === 'error' ? 'danger' : type;
        
        const alertHtml = `
            <div class="alert alert-${alertClass} alert-dismissible fade show notification-alert" role="alert">
                <i class="fas fa-${this.getNotificationIcon(type)} me-2"></i>
                ${this.escapeHtml(message)}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        // Find or create notification container
        let container = document.querySelector('.notification-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'notification-container position-fixed top-0 end-0 p-3';
            container.style.zIndex = '9999';
            document.body.appendChild(container);
        }
        
        container.insertAdjacentHTML('beforeend', alertHtml);
        
        // Auto-dismiss after duration
        if (duration > 0) {
            setTimeout(() => {
                const alert = container.querySelector('.notification-alert');
                if (alert && alert.parentNode === container) {
                    const bsAlert = new bootstrap.Alert(alert);
                    bsAlert.close();
                }
            }, duration);
        }
    },
    
    // Get notification icon
    getNotificationIcon: function(type) {
        const icons = {
            success: 'check-circle',
            error: 'exclamation-triangle',
            warning: 'exclamation-circle',
            info: 'info-circle'
        };
        return icons[type] || 'info-circle';
    },
    
    // Escape HTML to prevent XSS
    escapeHtml: function(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
    
    // Utility methods
    utils: {
        // Debounce function calls
        debounce: function(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        },
        
        // Throttle function calls
        throttle: function(func, limit) {
            let inThrottle;
            return function() {
                const args = arguments;
                const context = this;
                if (!inThrottle) {
                    func.apply(context, args);
                    inThrottle = true;
                    setTimeout(() => inThrottle = false, limit);
                }
            };
        },
        
        // Copy text to clipboard
        copyToClipboard: async function(text) {
            try {
                await navigator.clipboard.writeText(text);
                ClipGremlin.showNotification('Copied to clipboard!', 'success', 2000);
            } catch (error) {
                console.error('Failed to copy to clipboard:', error);
                ClipGremlin.showNotification('Failed to copy to clipboard', 'error');
            }
        },
        
        // Format file size
        formatFileSize: function(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        },
        
        // Validate email
        isValidEmail: function(email) {
            const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            return re.test(email);
        }
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    ClipGremlin.init();
});

// Global functions for template use
window.refreshActivity = function() {
    ClipGremlin.dashboard.refreshActivity();
};

window.copyToClipboard = function(text) {
    ClipGremlin.utils.copyToClipboard(text);
};

// Export for modules if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ClipGremlin;
}
