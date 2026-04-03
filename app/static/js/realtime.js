/**
 * UEBA Real-Time Synchronization Module
 * Handles Global WebSockets & Dynamic "Time Ago" updates
 */

const RealTime = {
    socket: null,
    updateInterval: null,

    init() {
        console.log("⚡ UEBA Real-Time System Initializing...");
        this.connectWebSocket();
        this.startClockLoop();
    },

    /**
     * Establish WebSocket Connection
     */
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        // We use /ws/location as the primary event hub since it's already implemented
        this.socket = new WebSocket(`${protocol}//${window.location.host}/ws/location`);

        this.socket.onopen = () => {
            console.log("✅ Real-Time Sync Active");
            document.dispatchEvent(new CustomEvent('rt-connected'));
        };

        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log("🔭 Real-Time Event:", data.type, data);
                
                // Dispatch a global event for page-specific listeners
                document.dispatchEvent(new CustomEvent('rt-event', { detail: data }));
                
                // Specific convenience events
                if (data.type === 'login') document.dispatchEvent(new CustomEvent('rt-login', { detail: data }));
                if (data.type === 'alert') document.dispatchEvent(new CustomEvent('rt-alert', { detail: data }));
                if (data.type === 'location_update') document.dispatchEvent(new CustomEvent('rt-location', { detail: data }));
                
            } catch (e) {
                console.error("❌ Real-Time Data Error:", e);
            }
        };

        this.socket.onclose = () => {
            console.warn("⚠️ Real-Time Sync Lost. Retrying in 5s...");
            setTimeout(() => this.connectWebSocket(), 5000);
        };
    },

    /**
     * Relative Time Calculation (Time Ago)
     */
    timeAgo(date) {
        if (!date) return "...";
        const now = new Date();
        const seconds = Math.floor((now - new Date(date)) / 1000);

        if (seconds < 5) return "just now";
        if (seconds < 60) return `${seconds}s ago`;
        
        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) return `${minutes}m ago`;
        
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return `${hours}h ago`;
        
        return new Date(date).toLocaleDateString();
    },

    /**
     * Update all elements with class 'rt-time'
     */
    updateClocks() {
        document.querySelectorAll('.rt-time').forEach(el => {
            const timestamp = el.getAttribute('data-timestamp');
            if (timestamp) {
                el.innerText = this.timeAgo(timestamp);
            }
        });
    },

    startClockLoop() {
        this.updateClocks();
        if (this.updateInterval) clearInterval(this.updateInterval);
        this.updateInterval = setInterval(() => this.updateClocks(), 30000); // Every 30s
    }
};

// Auto-init on load
document.addEventListener('DOMContentLoaded', () => RealTime.init());
window.RealTime = RealTime;
