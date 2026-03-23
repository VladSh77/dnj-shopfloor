/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class KioskApp extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.state = useState({
            workcenters: [],
            isLoading: true, // Додано стан завантаження
        });

        onWillStart(async () => {
            await this.loadWorkcenters();
        });
    }

    async loadWorkcenters() {
        try {
            const result = await this.rpc("/dnj_shopfloor/get_workcenters", {});
            this.state.workcenters = result;
        } catch (error) {
            console.error("Помилка завантаження робочих центрів:", error);
        } finally {
            this.state.isLoading = false; // Вимикаємо спінер у будь-якому випадку
        }
    }

    selectWorkcenter(id) {
        // Поки що логуємо, пізніше тут буде виклик дії (action) Odoo
        console.log("Обрано робочий центр з ID:", id);
    }
}

KioskApp.template = "dnj_shopfloor.KioskApp";
registry.category("actions").add("dnj_shopfloor_kiosk_client_action", KioskApp);
