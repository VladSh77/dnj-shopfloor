/** @odoo-module **/
/**
 * DNJ Shop Floor — Manager Dashboard
 * Shows live status of all machines, refreshes every 30 s.
 * Clicking a machine card opens a detail panel with today's stats,
 * recent sessions, operators, and machine monitoring data.
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

function fmtMins(min) {
    if (!min || min <= 0) return '—';
    const h = Math.floor(min / 60);
    const m = Math.round(min % 60);
    return h > 0 ? `${h}g ${m}m` : `${m}m`;
}

function elapsedSec(isoStart) {
    if (!isoStart) return 0;
    const start = new Date(isoStart + (isoStart.endsWith('Z') ? '' : 'Z')).getTime();
    return Math.max(0, Math.floor((Date.now() - start) / 1000));
}

function pct(produced, total) {
    if (!total) return 0;
    return Math.min(100, Math.round((produced / total) * 100));
}

// ── MachineCard ──────────────────────────────────────────────────────────────

class MachineCard extends Component {
    static template = "dnj_shopfloor.MachineCard";
    static props    = ["wc", "tick"];

    get sess()       { return this.props.wc.session; }
    get ms()         { return this.props.wc.machine_status; }
    fmtTime(sec)    { return fmtTime(sec); }
    get isActive()   { return this.sess && this.sess.state === 'progress'; }
    get isPaused()   { return this.sess && this.sess.state === 'paused'; }

    get isMonitored()    { return this.ms && this.ms.monitored; }
    get isOnline()       { return this.ms && this.ms.online === true; }
    get hasModbus()      { return this.ms && this.ms.modbus_enabled; }
    get pingLabel() {
        if (!this.isMonitored) return '';
        return this.isOnline ? `${this.ms.response_ms}ms` : 'offline';
    }
    get machineSpeed()   { return this.ms ? this.ms.machine_speed : 0; }
    get machineCounter() { return this.ms ? this.ms.machine_counter : 0; }
    get machineRunning() { return this.ms ? this.ms.machine_running : false; }

    get statusLabel() {
        if (!this.sess) return "Wolna";
        return { active:'Logowanie', confirmed:'Gotowa', test_print:'Test druku',
                 progress:'Praca', paused:'Pauza', done:'Zakończona' }[this.sess.state] || this.sess.state;
    }
    get statusColor() {
        if (!this.sess)                     return '#555540';
        if (this.sess.state === 'progress') return '#2D5C2D';
        if (this.sess.state === 'paused')   return '#4A3A00';
        return '#1a1a2e';
    }
    get statusTextColor() {
        if (!this.sess)                     return '#888870';
        if (this.sess.state === 'progress') return '#60c060';
        if (this.sess.state === 'paused')   return '#C9A227';
        return '#9090b0';
    }

    // Wall-clock from START — never subtracts pauses
    get timerSec() {
        if (!this.sess || this.sess.state !== 'progress') return 0;
        return elapsedSec(this.sess.work_start);
    }

    get progressPct() { return pct(this.sess?.qty_produced || 0, this.sess?.qty_production || 0); }

    get plannedSec()   { return (this.sess?.duration_expected || 0) * 60; }
    get timePct()      { return this.plannedSec ? Math.round((this.timerSec / this.plannedSec) * 100) : 0; }
    get timeBarWidth() { return Math.min(100, this.timePct); }
    get isOvertime()   { return this.plannedSec > 0 && this.timerSec > this.plannedSec; }
    get overtimeSec()  { return Math.max(0, this.timerSec - this.plannedSec); }
    get timeBarColor() {
        const p = this.timePct;
        if (p > 100) return '#c03030';
        if (p > 95)  return '#e06020';
        if (p > 80)  return '#C9A227';
        return '#2D5C2D';
    }
}

// ── MachineDetailPanel ────────────────────────────────────────────────────────

class MachineDetailPanel extends Component {
    static template = "dnj_shopfloor.MachineDetailPanel";
    static props    = ["wc", "stats", "statsLoading", "tick", "onClose"];

    get sess()     { return this.props.wc.session; }
    get ms()       { return this.props.wc.machine_status; }
    get today()    { return this.props.stats ? this.props.stats.today : null; }
    get ops()      { return this.props.stats ? this.props.stats.operators_7d : []; }
    get sessions() { return this.props.stats ? this.props.stats.recent_sessions : []; }

    get isActive() { return this.sess && this.sess.state === 'progress'; }
    get isPaused() { return this.sess && this.sess.state === 'paused'; }
    get hasSess()  { return !!this.sess && this.sess.state !== 'done'; }

    // Wall-clock timer (same logic as kiosk — never subtracts pauses)
    get timerSec() {
        if (!this.sess || !this.sess.work_start) return 0;
        return elapsedSec(this.sess.work_start);
    }
    // Net = wall-clock minus pauses
    get netSec()   { return Math.max(0, this.timerSec - (this.sess?.pause_minutes || 0) * 60); }
    get pauseSec() { return (this.sess?.pause_minutes || 0) * 60; }

    fmtTime(sec) { return fmtTime(sec); }
    fmtMins(min) { return fmtMins(min); }

    get progressPct() { return pct(this.sess?.qty_produced || 0, this.sess?.qty_production || 0); }
    get plannedSec()  { return (this.sess?.duration_expected || 0) * 60; }
    get timePct()     { return this.plannedSec ? Math.round((this.timerSec / this.plannedSec) * 100) : 0; }
    get timeBarWidth(){ return Math.min(100, this.timePct); }
    get isOvertime()  { return this.plannedSec > 0 && this.timerSec > this.plannedSec; }
    get overtimeSec() { return Math.max(0, this.timerSec - this.plannedSec); }
    get timeBarColor(){
        const p = this.timePct;
        if (p > 100) return '#c03030';
        if (p > 95)  return '#e06020';
        if (p > 80)  return '#C9A227';
        return '#2D5C2D';
    }

    get isMonitored() { return this.ms && this.ms.monitored; }
    get isOnline()    { return this.ms && this.ms.online === true; }
    get hasModbus()   { return this.ms && this.ms.modbus_enabled; }

    stateLabel(state) {
        return { active:'Logowanie', confirmed:'Gotowa', test_print:'Test druku',
                 progress:'Praca', paused:'Pauza', done:'Zakończona' }[state] || state;
    }
    stateTextColor(state) {
        return { progress:'#60c060', paused:'#C9A227', done:'#888870' }[state] || '#9090b0';
    }
    stateBg(state) {
        return { progress:'#1e4020', paused:'#2A2200', done:'#222218' }[state] || '#222218';
    }
}

// ── DnjShopfloorDashboard (root) ─────────────────────────────────────────────

export class DnjShopfloorDashboard extends Component {
    static template   = "dnj_shopfloor.Dashboard";
    static components = { MachineCard, MachineDetailPanel };

    setup() {
        this.rpc   = useService("rpc");
        this.state = useState({
            machines:     [],
            loading:      true,
            lastUpdate:   null,
            tick:         0,
            selectedWc:   null,
            selectedStats:  null,
            statsLoading:   false,
        });

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
            // Keep selected panel in sync with refreshed data
            if (this.state.selectedWc) {
                const fresh = this.state.machines.find(m => m.id === this.state.selectedWc.id);
                if (fresh) this.state.selectedWc = fresh;
            }
        } catch { /* silently retry */ }
        finally  { this.state.loading = false; }
    }

    async openDetail(wc) {
        this.state.selectedWc    = wc;
        this.state.selectedStats = null;
        this.state.statsLoading  = true;
        try {
            this.state.selectedStats = await this.rpc('/dnj_shopfloor/machine/stats', {
                workcenter_id: wc.id,
            });
        } catch { this.state.selectedStats = null; }
        finally  { this.state.statsLoading = false; }
    }

    closeDetail() {
        this.state.selectedWc    = null;
        this.state.selectedStats = null;
    }

    get activeCount() { return this.state.machines.filter(m => m.session?.state === 'progress').length; }
    get pausedCount() { return this.state.machines.filter(m => m.session?.state === 'paused').length; }
    get idleCount()   { return this.state.machines.filter(m => !m.session || m.session.state === 'done').length; }
}

registry.category("actions").add("dnj_shopfloor_dashboard_action", DnjShopfloorDashboard);
