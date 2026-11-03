// Mandi ERP Universal Real-Time Live Sync Client
// Provides bi-directional WebSockets, audio chimes, non-blocking toast alerts, and status pill indicators.
(function() {
    window.MandiLiveSync = {
        ws: null,
        handlers: {},
        statusListeners: [],
        isConnected: false,
        reconnectAttempts: 0,
        maxReconnectDelay: 10000,
        heartbeatInterval: null,

        on: function(eventType, callback) {
            if (!this.handlers[eventType]) {
                this.handlers[eventType] = [];
            }
            this.handlers[eventType].push(callback);
        },

        onStatusChange: function(callback) {
            this.statusListeners.push(callback);
        },

        notifyStatus: function(connected) {
            this.isConnected = connected;
            const indicators = document.querySelectorAll('.live-sync-indicator, #liveSyncStatus');
            indicators.forEach(el => {
                if (connected) {
                    el.innerHTML = '<span class="live-dot-pulse"></span> <span class="live-status-text">Live Synced</span>';
                    el.classList.add('live-synced-active');
                    el.classList.remove('live-synced-offline');
                } else {
                    el.innerHTML = '<span class="live-dot-offline"></span> <span class="live-status-text">Reconnecting...</span>';
                    el.classList.add('live-synced-offline');
                    el.classList.remove('live-synced-active');
                }
            });
            this.statusListeners.forEach(cb => {
                try { cb(connected); } catch(e) {}
            });
        },

        checkCloudSyncStatus: async function() {
            try {
                const resp = await fetch('/api/supabase/status', { cache: 'no-store' });
                const data = await resp.json();
                const isSynced = (data.status === 'CONNECTED' || data.online);
                const badges = document.querySelectorAll('.cloud-sync-badge, #cloudSyncBadge, #cloudSyncStatusBadge');
                
                badges.forEach(b => {
                    b.style.cursor = 'pointer';
                    b.setAttribute('onclick', 'window.MandiLiveSync ? window.MandiLiveSync.triggerCloudSync() : null');
                    if (isSynced) {
                        b.innerHTML = '<span class="cloud-dot-pulse" style="display:inline-block; width:7px; height:7px; border-radius:50%; background:#10b981; box-shadow:0 0 6px #10b981;"></span> <span class="cloud-status-text" style="font-weight:700;">Cloud: Synced</span>';
                        b.style.background = '#ecfdf5';
                        b.style.color = '#065f46';
                        b.style.borderColor = '#a7f3d0';
                        b.title = `Supabase PostgreSQL Connected (${data.project_ref || 'dbhcpebchoyjyffqjgih'}) • Click to sync now`;
                    } else {
                        b.innerHTML = '<span class="cloud-dot-offline" style="display:inline-block; width:7px; height:7px; border-radius:50%; background:#f59e0b;"></span> <span class="cloud-status-text" style="font-weight:700;">Cloud: Local Offline</span>';
                        b.style.background = '#fef3c7';
                        b.style.color = '#92400e';
                        b.style.borderColor = '#fde68a';
                        b.title = 'Edge SQLite mode active (Supabase offline) • Click to retry sync';
                    }
                });
            } catch(e) {
                const badges = document.querySelectorAll('.cloud-sync-badge, #cloudSyncBadge, #cloudSyncStatusBadge');
                badges.forEach(b => {
                    b.innerHTML = '<span class="cloud-dot-offline" style="display:inline-block; width:7px; height:7px; border-radius:50%; background:#f59e0b;"></span> <span class="cloud-status-text" style="font-weight:700;">Cloud: Local Offline</span>';
                    b.style.background = '#fef3c7';
                    b.style.color = '#92400e';
                    b.style.borderColor = '#fde68a';
                });
            }
        },

        triggerCloudSync: async function() {
            const self = this;
            self.toast('⚡ Cloud Sync Initiated', 'Syncing local transactions and master records with Supabase PostgreSQL...', 'info');
            try {
                const resp = await fetch('/api/admin/supabase/sync', { method: 'POST' });
                const data = await resp.json();
                if (data.success) {
                    self.toast('✓ Cloud Sync Completed', `${data.message || 'Transactions and corridors synchronized'}`, 'success');
                    self.checkCloudSyncStatus();
                } else {
                    self.toast('⚠️ Cloud Sync Notice', `${data.message || 'Operating in offline local cache'}`, 'warning');
                }
            } catch(e) {
                self.toast('⚠️ Cloud Sync Notice', 'Local offline mode active. Transactions queued for sync.', 'warning');
            }
        },

        playChime: function(type) {
            try {
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                if (ctx.state === 'suspended') {
                    ctx.resume();
                }
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = 'sine';
                if (type === 'urgent') {
                    osc.frequency.setValueAtTime(659.25, ctx.currentTime); // E5
                    osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.12); // A5
                } else {
                    osc.frequency.setValueAtTime(523.25, ctx.currentTime); // C5
                    osc.frequency.exponentialRampToValueAtTime(659.25, ctx.currentTime + 0.15); // E5
                }
                gain.gain.setValueAtTime(0.08, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.28);
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start();
                osc.stop(ctx.currentTime + 0.28);
            } catch(e) {}
        },

        toast: function(title, message, type) {
            let container = document.getElementById('mandiLiveToastContainer');
            if (!container) {
                container = document.createElement('div');
                container.id = 'mandiLiveToastContainer';
                container.style.cssText = 'position:fixed; top:20px; right:20px; z-index:999999; display:flex; flex-direction:column; gap:10px; max-width:380px; pointer-events:none;';
                document.body.appendChild(container);
            }
            const toast = document.createElement('div');
            const borderColor = type === 'success' ? '#10b981' : (type === 'warning' ? '#f59e0b' : (type === 'urgent' ? '#ef4444' : '#3b82f6'));

            toast.style.cssText = `
                pointer-events:auto; background:#ffffff; border-left:4px solid ${borderColor};
                box-shadow:0 12px 28px -4px rgba(15,23,42,0.18), 0 4px 10px -2px rgba(15,23,42,0.08);
                border-radius:10px; padding:12px 16px; font-family:system-ui, -apple-system, sans-serif;
                border-top:1px solid #e2e8f0; border-right:1px solid #e2e8f0; border-bottom:1px solid #e2e8f0;
                transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.3s ease;
                transform: translateY(-8px); opacity: 0;
            `;
            toast.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                    <div style="font-weight:800; font-size:13px; color:#0f172a; display:flex; align-items:center; gap:6px;">
                        <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${borderColor};"></span>
                        ${title}
                    </div>
                    <button style="border:none; background:transparent; cursor:pointer; font-size:16px; color:#94a3b8; padding:0 4px;" onclick="this.closest('div').parentElement.remove()">&times;</button>
                </div>
                <div style="font-size:12px; color:#475569; line-height:1.45; font-weight:500;">${message}</div>
            `;
            container.appendChild(toast);
            requestAnimationFrame(() => {
                toast.style.transform = 'translateY(0)';
                toast.style.opacity = '1';
            });
            this.playChime(type === 'urgent' ? 'urgent' : 'default');

            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateY(-10px)';
                setTimeout(() => toast.remove(), 350);
            }, 6000);
        },

        init: function() {
            const self = this;
            if (self.ws && (self.ws.readyState === WebSocket.OPEN || self.ws.readyState === WebSocket.CONNECTING)) {
                return;
            }

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/live`;

            try {
                self.ws = new WebSocket(wsUrl);
            } catch(e) {
                console.error('WebSocket creation error:', e);
                self.scheduleReconnect();
                return;
            }

            self.ws.onopen = function() {
                console.log('⚡ Mandi ERP Live Sync Connected');
                self.reconnectAttempts = 0;
                self.notifyStatus(true);
                self.checkCloudSyncStatus();
                if (self.heartbeatInterval) clearInterval(self.heartbeatInterval);
                self.heartbeatInterval = setInterval(() => {
                    if (self.ws && self.ws.readyState === WebSocket.OPEN) {
                        self.ws.send('ping');
                    }
                }, 25000);

                if (!self._cloudSyncTimer) {
                    self._cloudSyncTimer = setInterval(() => self.checkCloudSyncStatus(), 30000);
                }

                // Register cloud sync event listener
                if (!self._cloudSyncRegistered) {
                    self._cloudSyncRegistered = true;
                    self.on('cloud_sync_completed', function(data) {
                        self.checkCloudSyncStatus();
                    });
                }

                // Register system update receiver if not already registered
                if (!self._systemUpdateRegistered) {
                    self._systemUpdateRegistered = true;
                    self.on('system_update_broadcast', function(data) {
                        const note = data.patch_note || 'Software update deployed from Master PC.';
                        const delayMs = data.reload_delay_ms || 3000;
                        self.toast('🚀 System Update Deployed', `${note} Updating application in ${Math.round(delayMs/1000)}s...`, 'urgent');
                        setTimeout(() => {
                            try {
                                if ('caches' in window) {
                                    caches.keys().then(names => {
                                        names.forEach(name => caches.delete(name));
                                    });
                                }
                            } catch(e) {}
                            window.location.reload(true);
                        }, delayMs);
                    });
                }
            };

            self.ws.onmessage = function(event) {
                if (event.data === 'pong') return;
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.type && self.handlers[msg.type]) {
                        self.handlers[msg.type].forEach(cb => {
                            try { cb(msg.data, msg); } catch(err) { console.error('Handler error:', err); }
                        });
                    }
                    if (self.handlers['*']) {
                        self.handlers['*'].forEach(cb => {
                            try { cb(msg); } catch(err) { console.error('Wildcard handler error:', err); }
                        });
                    }
                } catch(e) {
                    console.error('Invalid live sync frame:', e);
                }
            };

            self.ws.onclose = function() {
                if (self.heartbeatInterval) clearInterval(self.heartbeatInterval);
                self.notifyStatus(false);
                self.scheduleReconnect();
            };

            self.ws.onerror = function() {
                self.notifyStatus(false);
            };
        },

        scheduleReconnect: function() {
            const self = this;
            self.reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(1.5, self.reconnectAttempts), self.maxReconnectDelay);
            setTimeout(function() {
                self.init();
            }, delay);
        }
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => window.MandiLiveSync.init());
    } else {
        window.MandiLiveSync.init();
    }
})();
