/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, useState, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

// ─── WorkcenterSelector ───────────────────────────────────────────────────────

class WorkcenterSelector extends Component {
    static template = "dnj_shopfloor.WorkcenterSelector";
    static props = ["workcenters", "onSelect"];
}

// ─── WorkOrderList ────────────────────────────────────────────────────────────

class WorkOrderList extends Component {
    static template = "dnj_shopfloor.WorkOrderList";
    static props = ["workorders", "workcenter", "onSelect", "onBack", "onRefresh"];

    setup() {
        this.barcodeRef = useRef("barcodeInput");
        onMounted(() => this.barcodeRef.el && this.barcodeRef.el.focus());
    }

    stateLabel(state) {
        const map = {
            pending: "Oczekuje",
            waiting: "W kolejce",
            ready: "Gotowe",
            progress: "W toku",
            done: "Ukończone",
            cancel: "Anulowane",
        };
        return map[state] || state;
    }

    stateBadge(state) {
        const map = {
            pending: "bg-secondary",
            waiting: "bg-warning text-dark",
            ready: "bg-success",
            progress: "bg-primary",
            done: "bg-dark",
            cancel: "bg-danger",
        };
        return "badge " + (map[state] || "bg-secondary");
    }

    onBarcodeKey(ev) {
        if (ev.key !== "Enter") return;
        const val = ev.target.value.trim();
        if (!val) return;
        const found = this.props.workorders.find(
            (w) => w.name === val || String(w.id) === val
        );
        if (found) {
            this.props.onSelect(found);
            ev.target.value = "";
        } else {
            ev.target.select();
        }
    }
}

// ─── WorkOrderDetail ──────────────────────────────────────────────────────────

class WorkOrderDetail extends Component {
    static template = "dnj_shopfloor.WorkOrderDetail";
    static props = ["workorder", "onStart", "onFinish", "onBack", "saving"];

    setup() {
        const remaining = this.props.workorder.qty_production - this.props.workorder.qty_produced;
        this.qty = useState({ value: Math.max(1, remaining) });
    }

    onQtyChange(ev) {
        this.qty.value = parseFloat(ev.target.value) || 0;
    }

    onFinishClick() {
        this.props.onFinish(this.qty.value);
    }
}

// ─── DnjShopfloorKiosk (root) ─────────────────────────────────────────────────

export class DnjShopfloorKiosk extends Component {
    static template = "dnj_shopfloor.KioskMain";
    static components = { WorkcenterSelector, WorkOrderList, WorkOrderDetail };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            screen: "workcenter",
            workcenters: [],
            workorders: [],
            selectedWorkcenter: null,
            selectedWorkorder: null,
            loading: false,
            saving: false,
        });
        this._loadWorkcenters();
    }

    // ── data loading ──────────────────────────────────────────────────────────

    async _loadWorkcenters() {
        this.state.loading = true;
        try {
            this.state.workcenters = await this.orm.searchRead(
                "mrp.workcenter",
                [["active", "=", true]],
                ["id", "name", "code"]
            );
        } catch {
            this._err("Nie można załadować listy maszyn");
        } finally {
            this.state.loading = false;
        }
    }

    async _loadWorkorders(wc) {
        this.state.loading = true;
        try {
            this.state.workorders = await this.orm.searchRead(
                "mrp.workorder",
                [
                    ["workcenter_id", "=", wc.id],
                    ["state", "in", ["pending", "waiting", "ready", "progress"]],
                ],
                [
                    "id", "name", "state",
                    "production_id", "product_id",
                    "qty_production", "qty_produced",
                    "date_planned_start",
                ],
                { order: "date_planned_start asc" }
            );
        } catch {
            this._err("Nie można załadować zleceń");
        } finally {
            this.state.loading = false;
        }
    }

    // ── navigation ────────────────────────────────────────────────────────────

    async selectWorkcenter(wc) {
        this.state.selectedWorkcenter = wc;
        await this._loadWorkorders(wc);
        this.state.screen = "workorders";
    }

    selectWorkorder(wo) {
        this.state.selectedWorkorder = wo;
        this.state.screen = "detail";
    }

    goBack() {
        if (this.state.screen === "detail") {
            this.state.screen = "workorders";
        } else {
            this.state.screen = "workcenter";
            this.state.selectedWorkcenter = null;
            this.state.workorders = [];
        }
    }

    async refreshWorkorders() {
        if (this.state.selectedWorkcenter) {
            await this._loadWorkorders(this.state.selectedWorkcenter);
        }
    }

    // ── workorder actions ─────────────────────────────────────────────────────

    async startWork() {
        this.state.saving = true;
        try {
            await this.orm.call(
                "mrp.workorder", "button_start",
                [[this.state.selectedWorkorder.id]]
            );
            await this._refreshCurrentWorkorder();
            this._ok("Praca rozpoczęta!");
        } catch (e) {
            this._err(e.data && e.data.message || "Błąd startu zlecenia");
        } finally {
            this.state.saving = false;
        }
    }

    async finishWork(qty) {
        this.state.saving = true;
        try {
            const id = this.state.selectedWorkorder.id;
            await this.orm.write("mrp.workorder", [id], { qty_produced: qty });
            await this.orm.call("mrp.workorder", "button_finish", [[id]]);
            this._ok("Zlecenie zakończone!");
            this.state.screen = "workorders";
            await this._loadWorkorders(this.state.selectedWorkcenter);
        } catch (e) {
            this._err(e.data && e.data.message || "Błąd zakończenia zlecenia");
        } finally {
            this.state.saving = false;
        }
    }

    async _refreshCurrentWorkorder() {
        const [updated] = await this.orm.read(
            "mrp.workorder",
            [this.state.selectedWorkorder.id],
            ["id", "name", "state", "production_id", "product_id", "qty_production", "qty_produced"]
        );
        this.state.selectedWorkorder = updated;
    }

    // ── helpers ───────────────────────────────────────────────────────────────

    _ok(msg) { this.notification.add(msg, { type: "success" }); }
    _err(msg) { this.notification.add(msg, { type: "danger" }); }
}

registry.category("actions").add("dnj_shopfloor_kiosk_action", DnjShopfloorKiosk);
