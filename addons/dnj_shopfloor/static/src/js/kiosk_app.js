/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

export class DnjShopfloorKiosk extends Component {
    static template = "dnj_shopfloor.KioskMain";
}

registry.category("actions").add("dnj_shopfloor_kiosk_action", DnjShopfloorKiosk);
