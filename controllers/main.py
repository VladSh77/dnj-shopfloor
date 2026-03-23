from odoo import http
from odoo.http import request


class ShopFloorKiosk(http.Controller):
    @http.route("/dnj_shopfloor/get_workcenters", type="json", auth="user")
    def get_workcenters(self):
        # Додано sudo() для обходу прав та limit для продуктивності
        workcenters = (
            request.env["mrp.workcenter"]
            .sudo()
            .search_read(domain=[], fields=["id", "name"], limit=100)
        )
        return workcenters
