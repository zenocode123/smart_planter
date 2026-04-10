/* Global Alpine.js Logic for Smart Planter */
document.addEventListener('alpine:init', () => {
    Alpine.data('appState', () => ({
        sidebarOpen: false,
        isRefreshing: false,
        disconnectModal: false,
        disconnectDismissed: false,
        isConnected: true,
        watering: false,
        waterEmpty: false,
        wateringStarted: false,  // ESP32 已確認開始澆水的旗標
        _wateringPoll: null,     // 澆水期間的快速輪詢計時器

        init() {
            // 監聽 watering 狀態：澆水時啟動安全的遞迴輪詢
            this.$watch('watering', (isWatering) => {
                if (isWatering) {
                    let attempts = 0;
                    this.wateringStarted = false;
                    // 記錄開始輪詢前的時間戳 (秒)，用於跟後端 latest_update_time 比較
                    this.wateringRequestTime = Date.now() / 1000;

                    const poll = async () => {
                        if (!this.watering) return; // 已經被中斷或完成

                        attempts++;
                        try {
                            const resp = await fetch('/plants/watering-status');
                            const data = await resp.json();
                            
                            // 檢查 ESP32 是否有新的狀態被 MQTT 接收到 (更新時間大於我們按鈕按下的時間)
                            const isNewState = data.timestamp > this.wateringRequestTime;

                            if (data.watering) {
                                // ESP32 確認開始澆水 (抓到 watering = true)
                                this.wateringStarted = true;
                            } else if (this.wateringStarted || (attempts >= 3 && isNewState)) {
                                // 停止條件有兩種：
                                // 1. 曾經抓到 true，現在變成 false (標準流程)
                                // 2. 一開始沒抓到 true，但是 data.timestamp 已經更新且 watering 為 false (超短時間 1.0 秒給水，前端錯過 true 的瞬間，確定 ESP32 已經報平安)
                                console.log("[Watering] 澆水動作已完成 (或秒處理完畢)。");
                                this.watering = false;
                                this.wateringStarted = false;
                                return; // 結束輪詢
                            } else if (attempts > 30) {
                                // 等待超過 15 秒，網路不穩或掉包
                                console.warn("[Timeout] 尚未收到 ESP32 的澆水確認回復");
                                this.watering = false;
                                this.wateringStarted = false;
                                window.showToast("網路延遲或設備未回應，嘗試自動復原 UI", "warning");
                                return; // 結束輪詢
                            }
                        } catch (e) {
                            console.warn('Watering status check failed:', e);
                        }

                        // 如果還是 watering 狀態，等待 500ms 後發起下一次請求 (徹底避免請求重疊 pile-up)
                        if (this.watering) {
                            this._wateringTimer = setTimeout(poll, 500);
                        }
                    };

                    poll();
                } else {
                    // watering 被設回 false（例如手動關閉或完成）→ 取消計時器
                    if (this._wateringTimer) {
                        clearTimeout(this._wateringTimer);
                        this._wateringTimer = null;
                        this.wateringStarted = false;
                    }
                }
            });
        },
        
        toggleSidebar() {
            this.sidebarOpen = !this.sidebarOpen;
        },
        
        triggerRefresh() {
            if (this.isRefreshing) return; // 防止連續點擊造成多個請求衝突與動畫異常
            this.isRefreshing = true;
            
            // UX 優化：按下按鈕後先關閉彈窗並給予 Toast 提示，避免瞬間回覆導致畫面看似卡轉
            this.disconnectModal = false;
            this.disconnectDismissed = true; // 暫時抑制檢查連線的彈窗
            window.showToast("正在嘗試重新連線 ESP32...", "info");
            
            htmx.trigger('#sensor-container', 'load');
            
            // 給予 3 秒的緩衝時間讓使用者知道系統有在動。如果 3 秒後依然斷線，再把彈窗叫回來
            if (this.recheckTimer) clearTimeout(this.recheckTimer);
            this.recheckTimer = setTimeout(() => {
                this.disconnectDismissed = false;
                if (!this.isConnected) {
                    this.disconnectModal = true;
                    window.showToast("依然無法連線到 ESP32", "error");
                }
            }, 3000);

            // 最多等待 5 秒當作超時備用防護，並清除舊的計時器
            if (this.refreshTimer) clearTimeout(this.refreshTimer);
            this.refreshTimer = setTimeout(() => { this.isRefreshing = false; }, 5000);
        },
        
        checkConnection(status) {
            this.isRefreshing = false; // 接收到伺服器回應後立刻停止轉動動畫
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
    // 檢查畫面中是否已經有 toast 容器
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.style.position = 'fixed';
        container.style.bottom = '20px';
        container.style.right = '20px';
        container.style.zIndex = '9999';
        container.style.display = 'flex';
        container.style.flexDirection = 'column';
        container.style.gap = '10px';
        document.body.appendChild(container);
    }

    // 建立獨立的 Toast 氣泡
    const toast = document.createElement('div');
    toast.innerText = message;
    toast.style.padding = '12px 24px';
    toast.style.borderRadius = '8px';
    toast.style.color = '#fff';
    toast.style.fontSize = '14px';
    toast.style.fontWeight = '500';
    toast.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
    toast.style.transition = 'all 0.3s ease';
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(20px)';
    
    // 根據 type 設定顏色
    if (type === 'error') {
        toast.style.backgroundColor = '#ef4444'; // Red
    } else if (type === 'warning') {
        toast.style.backgroundColor = '#f59e0b'; // Orange
    } else if (type === 'info') {
        toast.style.backgroundColor = '#3b82f6'; // Blue
    } else {
        toast.style.backgroundColor = '#22c55e'; // Green (success)
    }

    container.appendChild(toast);

    // Fade in
    requestAnimationFrame(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateY(0)';
    });

    // Fade out and remove after 3 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(20px)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
};
