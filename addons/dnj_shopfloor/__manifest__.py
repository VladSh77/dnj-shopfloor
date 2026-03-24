{
    "name": "DNJ Shop Floor Kiosk",
    "version": "17.0.2.0.0",
    "category": "Manufacturing",
    "summary": "Tablet kiosk for machine operators — PIN login, work queue, test print, timer, logs",
    "author": "Fayna Digital",
    "license": "LGPL-3",
    "depends": ["base", "mrp", "stock"],
    "data": [
        "security/ir.model.access.csv",
        "views/dnj_operator_views.xml",
        "views/kiosk_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "dnj_shopfloor/static/src/**/*",
        ],
    },
    "installable": True,
    "application": True,
}
