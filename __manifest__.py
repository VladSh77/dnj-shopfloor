{
    "name": "DNJ Shop Floor Kiosk",
    "version": "1.0",
    "category": "Manufacturing",
    "summary": "Kiosk interface for shop floor operators",
    "depends": ["base", "mrp", "web"],
    "data": [
        "views/kiosk_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "dnj_shopfloor/static/src/components/kiosk/kiosk.js",
            "dnj_shopfloor/static/src/components/kiosk/kiosk.xml",
        ],
    },
    "installable": True,
    "application": True,
    "license": "LGPL-3"
}
