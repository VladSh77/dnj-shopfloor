/** @odoo-module **/
/**
 * DNJ Shop Floor Kiosk — main OWL application
 *
 * Screen flow:
 *   pin ──► machine ──► queue ──► test_print ──► confirm ──► work ──► (back to queue)
 *                                    ▲                         │
 *                                    └─────── pause ◄──────────┘
 */
import { registry } from "@web/core/registry";
import { Component, useState, onWillUnmount, useRef, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

// ─── helpers ──────────────────────────────────────────────────────────────────

function fmtTime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return h > 0
        ? `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
        : `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function progress(produced, total) {
    if (!total) return 0;
    return Math.min(100, Math.round((produced / total) * 100));
}

// ─── PinScreen ────────────────────────────────────────────────────────────────

class PinScreen extends Component {
    static template = "dnj_shopfloor.PinScreen";
    static props = ["workcenter", "onAuth", "onBack"];

    setup() {
        this.rpc = useService("rpc");
        this.state = useState({ pin: "", error: "", loading: false });
    }

    onKey = (key) => {
        if (this.state.loading) return;
        if (key === "⌫") {
            this.state.pin = this.state.pin.slice(0, -1);
            this.state.error = "";
        } else if (key === "✓") {
            this._submit();
        } else if (this.state.pin.length < 6) {
            this.state.pin += String(key);
            this.state.error = "";
            if (this.state.pin.length === 4) this._submit();  // auto-submit on 4 digits
        }
    }

    async _submit() {
        if (this.state.pin.length < 4) return;
        this.state.loading = true;
        try {
            const result = await this.rpc('/dnj_shopfloor/authenticate', {
                pin: this.state.pin,
                workcenter_id: this.props.workcenter.id,
            });
            if (result.success) {
                this.props.onAuth({ id: result.operator_id, name: result.name });
            } else {
                this.state.error = result.error || "Nieprawidłowy PIN";
                this.state.pin = "";
            }
        } catch {
            this.state.error = "Błąd połączenia";
            this.state.pin = "";
        } finally {
            this.state.loading = false;
        }
    }
}

// ─── WorkcenterSelector ───────────────────────────────────────────────────────

class WorkcenterSelector extends Component {
    static template = "dnj_shopfloor.WorkcenterSelector";
    static props = ["workcenters", "onSelect", "loading"];
}

// ─── WorkOrderQueue ───────────────────────────────────────────────────────────

class WorkOrderQueue extends Component {
    static template = "dnj_shopfloor.WorkOrderQueue";
    static props = ["workorders", "operator", "workcenter", "onSelect", "onRefresh", "onLogout", "loading"];

    setup() {
        this.barcodeRef = useRef("barcode");
        onMounted(() => this.barcodeRef.el && this.barcodeRef.el.focus());
    }

    stateLabel(state) {
        return { pending: "Oczekuje", waiting: "W kolejce", ready: "Gotowe", progress: "W toku" }[state] || state;
    }

    stateCls(state) {
        return { pending: "secondary", waiting: "warning", ready: "success", progress: "primary" }[state] || "secondary";
    }

    onBarcodeKey(ev) {
        if (ev.key !== "Enter") return;
        const val = ev.target.value.trim();
        if (!val) return;
        const found = this.props.workorders.find(w => w.name === val || String(w.id) === val);
        if (found) {
            this.props.onSelect(found);
            ev.target.value = "";
        } else {
            ev.target.select();
        }
    }

    progressPct(wo) { return progress(wo.qty_produced, wo.qty_production); }
}

// ─── TestPrintScreen ──────────────────────────────────────────────────────────

class TestPrintScreen extends Component {
    static template = "dnj_shopfloor.TestPrintScreen";
    static props = ["workorder", "operator", "workcenter", "onConfirm", "onBack", "saving"];

    setup() {
        this.qty = useState({ value: 5 });
    }

    onChange(ev) { this.qty.value = parseFloat(ev.target.value) || 0; }
}

// ─── WorkScreen ───────────────────────────────────────────────────────────────

class WorkScreen extends Component {
    static template = "dnj_shopfloor.WorkScreen";
    static props = ["workorder", "operator", "workcenter", "sessionState",
                    "timerSec", "onStart", "onPause", "onResume", "onStop", "saving"];

    setup() {
        this.finish = useState({ qty: this.props.workorder.qty_production, scrap: 0 });
    }

    onQtyChange(ev) { this.finish.qty = parseFloat(ev.target.value) || 0; }
    onScrapChange(ev) { this.finish.scrap = parseFloat(ev.target.value) || 0; }

    fmtTimer(sec) { return fmtTime(sec); }

    get progressPct() { return progress(this.props.workorder.qty_produced, this.props.workorder.qty_production); }
    get progressCls() {
        const p = this.progressPct;
        return p >= 90 ? "bg-success" : p >= 60 ? "bg-warning" : "bg-danger";
    }

    onStop() { this.props.onStop(this.finish.qty, this.finish.scrap); }
}

// ─── PauseModal ───────────────────────────────────────────────────────────────

class PauseModal extends Component {
    static template = "dnj_shopfloor.PauseModal";
    static props = ["onSelect", "onCancel"];

    REASONS = [
        { key: "coffee",      label: "☕ Przerwa kawowa" },
        { key: "maintenance", label: "🔧 Konserwacja maszyny" },
        { key: "material",    label: "📦 Oczekiwanie na materiał" },
        { key: "other",       label: "⏸ Inna przyczyna" },
    ];
}

// ─── DnjShopfloorKiosk (root) ─────────────────────────────────────────────────

export class DnjShopfloorKiosk extends Component {
    static template = "dnj_shopfloor.KioskMain";
    static components = {
        WorkcenterSelector, PinScreen, WorkOrderQueue,
        TestPrintScreen, WorkScreen, PauseModal,
    };

    setup() {
        this.notification = useService("notification");
        this.rpc = useService("rpc");
        this.state = useState({
            screen: "machine",      // machine | pin | queue | test_print | work
            workcenters: [],
            workorders: [],
            workcenter: null,
            operator: null,
            sessionId: null,
            sessionState: null,
            workorder: null,
            loading: false,
            saving: false,
            showPauseModal: false,
            timerSec: 0,
            workStartTs: null,      // JS timestamp (ms)
            pausedMs: 0,            // total paused milliseconds
        });

        this._timerInterval = null;

        onWillUnmount(() => this._stopTimer());
        this._loadWorkcenters();
    }

    // ── data ──────────────────────────────────────────────────────────────────

    async _loadWorkcenters() {
        this.state.loading = true;
        try {
            const rows = await this.rpc('/web/dataset/call_kw', {
                model: 'mrp.workcenter',
                method: 'search_read',
                args: [[['active', '=', true]]],
                kwargs: { fields: ['id', 'name', 'code'], limit: 50 },
            });
            this.state.workcenters = rows;
        } catch { this._err("Błąd ładowania maszyn"); }
        finally { this.state.loading = false; }
    }

    async _loadWorkorders() {
        this.state.loading = true;
        try {
            this.state.workorders = await this.rpc('/dnj_shopfloor/workorders', {
                workcenter_id: this.state.workcenter.id,
            });
        } catch { this._err("Błąd ładowania zleceń"); }
        finally { this.state.loading = false; }
    }

    // ── navigation ────────────────────────────────────────────────────────────

    async selectWorkcenter(wc) {
        this.state.workcenter = wc;
        this.state.screen = "pin";
    }

    async onAuth(operator) {
        this.state.operator = operator;
        this.state.saving = true;
        try {
            const res = await this.rpc('/dnj_shopfloor/session/open', {
                operator_id: operator.id,
                workcenter_id: this.state.workcenter.id,
            });
            this.state.sessionId = res.session_id;
            this.state.sessionState = res.state;
            await this._loadWorkorders();
            this.state.screen = "queue";
            this._ok(`Witaj, ${operator.name}!`);
        } catch { this._err("Błąd tworzenia sesji"); }
        finally { this.state.saving = false; }
    }

    async selectWorkorder(wo) {
        this.state.workorder = wo;
        await this._sessionAction('select_workorder', { workorder_id: wo.id });
        this.state.screen = "test_print";
    }

    async onTestPrintConfirm(qty) {
        this.state.saving = true;
        try {
            await this._sessionAction('test_print', { qty });
            await this._sessionAction('confirm_machine');
            this.state.screen = "work";
        } catch (e) { this._err(e); }
        finally { this.state.saving = false; }
    }

    async startWork() {
        this.state.saving = true;
        try {
            await this._sessionAction('start_work');
            this.state.sessionState = 'progress';
            this._startTimer();
            this._ok("Praca rozpoczęta!");
        } catch (e) { this._err(e); }
        finally { this.state.saving = false; }
    }

    async pauseWork(reason) {
        this.state.showPauseModal = false;
        this.state.saving = true;
        try {
            await this._sessionAction('pause', { reason });
            this.state.sessionState = 'paused';
            this.state.pausedMs += 0;             // mark pause start
            this._stopTimer();
        } catch (e) { this._err(e); }
        finally { this.state.saving = false; }
    }

    async resumeWork() {
        this.state.saving = true;
        try {
            await this._sessionAction('resume');
            this.state.sessionState = 'progress';
            this._startTimer();
            this._ok("Praca wznowiona!");
        } catch (e) { this._err(e); }
        finally { this.state.saving = false; }
    }

    async stopWork(qtyProduced, qtyScrap) {
        this.state.saving = true;
        try {
            await this._sessionAction('stop', { qty_produced: qtyProduced, qty_scrap: qtyScrap });
            this._stopTimer();
            this._ok("Zlecenie zakończone!");
            await this._loadWorkorders();
            this.state.screen = "queue";
            this.state.workorder = null;
            this.state.sessionState = 'active';
        } catch (e) { this._err(e); }
        finally { this.state.saving = false; }
    }

    async logout() {
        this.state.saving = true;
        try {
            await this._sessionAction('logout');
        } catch { /* ignore */ }
        finally { this.state.saving = false; }
        this._stopTimer();
        this.state.screen = "pin";
        this.state.operator = null;
        this.state.sessionId = null;
        this.state.workorder = null;
        this.state.workorders = [];
        this.state.timerSec = 0;
    }

    // ── timer ─────────────────────────────────────────────────────────────────

    _startTimer() {
        this._stopTimer();
        const base = this.state.timerSec;
        const start = Date.now() - base * 1000;
        this._timerInterval = setInterval(() => {
            this.state.timerSec = Math.floor((Date.now() - start) / 1000);
        }, 1000);
    }

    _stopTimer() {
        if (this._timerInterval) {
            clearInterval(this._timerInterval);
            this._timerInterval = null;
        }
    }

    // ── helpers ───────────────────────────────────────────────────────────────

    async _sessionAction(action, kwargs = {}) {
        const res = await this.rpc('/dnj_shopfloor/session/action', {
            session_id: this.state.sessionId,
            action,
            ...kwargs,
        });
        if (!res.success) throw res.error || "Błąd akcji";
        if (res.state) this.state.sessionState = res.state;
        return res;
    }

    _ok(msg) { this.notification.add(msg, { type: "success" }); }
    _err(msg) { this.notification.add(String(msg), { type: "danger" }); }
}

registry.category("actions").add("dnj_shopfloor_kiosk_action", DnjShopfloorKiosk);
