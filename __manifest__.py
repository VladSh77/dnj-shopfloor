{
    "name": "DNJ Shop Floor Kiosk",
    "version": "17.0.1.0.0",
    "author": "DNJ",
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
    "license": "LGPL-3",
}
