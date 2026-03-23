from odoo import http
from odoo.http import request


class ShopFloorKiosk(http.Controller):
    @http.route("/dnj_shopfloor/get_workcenters", type="json", auth="user")
    def get_workcenters(self):
        # Шукаємо всі робочі центри в базі даних Odoo
        workcenters = request.env["mrp.workcenter"].search_read([], ["id", "name"])
        return workcenters
