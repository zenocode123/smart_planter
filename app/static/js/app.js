/* Global Alpine.js Logic for Smart Planter */
document.addEventListener('alpine:init', () => {
    Alpine.data('appState', () => ({
        sidebarOpen: false,
        isRefreshing: false,
        disconnectModal: false,
        disconnectDismissed: false,
        isConnected: true,
        watering: false,
        
        toggleSidebar() {
            this.sidebarOpen = !this.sidebarOpen;
        },
        
        triggerRefresh() {
            this.isRefreshing = true;
            htmx.trigger('#sensor-container', 'load');
            setTimeout(() => { this.isRefreshing = false; }, 1000);
        },
        
        checkConnection(status) {
            if (!status || status === 'disconnected' || status === 'Connect Error') {
                this.isConnected = false;
                // 只在使用者尚未忽略的情況下彈出
                if (!this.disconnectDismissed) {
                    this.disconnectModal = true;
                }
            } else {
                this.isConnected = true;
                this.disconnectModal = false;
                // ESP32 恢復連線 → 重置旗標，下次斷線仍會提醒
                this.disconnectDismissed = false;
            }
        },
        
        dismissDisconnect() {
            this.disconnectModal = false;
            this.disconnectDismissed = true;
        }
    }));
});

// Toast Utility
window.showToast = (message, type = 'success') => {
    console.log(`Toast: [${type}] ${message}`);
    // 可以後續整合更好的 Toast 庫或自定義組件
};
