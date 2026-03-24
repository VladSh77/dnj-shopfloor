/** @odoo-module **/
/**
 * DNJ Shop Floor — Manager Dashboard
 * Shows live status of all machines, refreshes every 30 s.
 */
import { registry }   from "@web/core/registry";
import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { useService }  from "@web/core/utils/hooks";

// ── helpers ──────────────────────────────────────────────────────────────────

function fmtTime(seconds) {
    if (!seconds || seconds < 0) return "00:00";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return h > 0
        ? `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
        : `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
}

function elapsedSec(isoStart, pauseMinutes) {
    if (!isoStart) return 0;
    const start  = new Date(isoStart + (isoStart.endsWith('Z') ? '' : 'Z')).getTime();
    const paused = (pauseMinutes || 0) * 60 * 1000;
    return Math.max(0, Math.floor((Date.now() - start - paused) / 1000));
}

function pct(produced, total) {
    if (!total) return 0;
    return Math.min(100, Math.round((produced / total) * 100));
}

// ── MachineCard ──────────────────────────────────────────────────────────────

class MachineCard extends Component {
    static template = "dnj_shopfloor.MachineCard";
    static props    = ["wc", "tick"];   // tick forces re-render every second

    get sess()       { return this.props.wc.session; }
    get isActive()   { return this.sess && this.sess.state === 'progress'; }
    get isPaused()   { return this.sess && this.sess.state === 'paused'; }
    get isIdle()     { return !this.sess || ['active','confirmed','test_print'].includes(this.sess.state); }

    get statusLabel() {
        if (!this.sess) return "Wolna";
        return { active:'Logowanie', confirmed:'Gotowa', test_print:'Test druku',
                 progress:'Praca', paused:'Pauza', done:'Zakończona' }[this.sess.state] || this.sess.state;
    }

    get statusColor() {
        if (!this.sess)                                    return '#555540';
        if (this.sess.state === 'progress')                return '#2D5C2D';
        if (this.sess.state === 'paused')                  return '#4A3A00';
        return '#1a1a2e';
    }

    get statusTextColor() {
        if (!this.sess)                                    return '#888870';
        if (this.sess.state === 'progress')                return '#60c060';
        if (this.sess.state === 'paused')                  return '#C9A227';
        return '#9090b0';
    }

    get timerSec() {
        if (!this.sess || this.sess.state !== 'progress') return 0;
        return elapsedSec(this.sess.work_start, this.sess.pause_minutes);
    }

    get progressPct() { return pct(this.sess?.qty_produced || 0, this.sess?.qty_production || 0); }

    get barColor() {
        const p = this.progressPct;
        return p >= 90 ? '#C9A227' : p >= 60 ? '#2D5C2D' : '#1e3050';
    }
}

// ── DnjShopfloorDashboard (root) ─────────────────────────────────────────────

export class DnjShopfloorDashboard extends Component {
    static template    = "dnj_shopfloor.Dashboard";
    static components  = { MachineCard };

    setup() {
        this.rpc   = useService("rpc");
        this.state = useState({
            machines:  [],
            loading:   true,
            lastUpdate: null,
            tick: 0,
        });

        this._refreshInterval = null;
        this._tickInterval    = null;

        onMounted(() => {
            this._load();
            this._refreshInterval = setInterval(() => this._load(), 30_000);
            this._tickInterval    = setInterval(() => { this.state.tick++; }, 1000);
        });
        onWillUnmount(() => {
            clearInterval(this._refreshInterval);
            clearInterval(this._tickInterval);
        });
    }

    async _load() {
        try {
            this.state.machines   = await this.rpc('/dnj_shopfloor/dashboard', {});
            this.state.lastUpdate = new Date().toLocaleTimeString('pl-PL');
        } catch {
            /* silently retry on next interval */
        } finally {
            this.state.loading = false;
        }
    }

    get activeCount()  { return this.state.machines.filter(m => m.session?.state === 'progress').length; }
    get pausedCount()  { return this.state.machines.filter(m => m.session?.state === 'paused').length; }
    get idleCount()    { return this.state.machines.filter(m => !m.session || m.session.state === 'done').length; }
}

registry.category("actions").add("dnj_shopfloor_dashboard_action", DnjShopfloorDashboard);
