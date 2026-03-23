/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class KioskApp extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.state = useState({
            workcenters: [],
        });

        onWillStart(async () => {
            await this.loadWorkcenters();
        });
    }

    async loadWorkcenters() {
        try {
            // Звертаємося до нашого Python-контролера
            const result = await this.rpc("/dnj_shopfloor/get_workcenters", {});
            this.state.workcenters = result;
        } catch (error) {
            console.error("Помилка завантаження робочих центрів:", error);
        }
    }

    selectWorkcenter(id) {
        console.log("Обрано робочий центр з ID:", id);
        // Тут пізніше додамо перехід до завдань цієї машини
    }
}

KioskApp.template = "dnj_shopfloor.KioskApp";

// Реєструємо наш компонент як Client Action
registry.category("actions").add("dnj_shopfloor_kiosk_client_action", KioskApp);
