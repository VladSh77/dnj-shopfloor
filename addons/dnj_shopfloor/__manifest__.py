{
    'name': 'DNJ Shop Floor Kiosk',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Interfejs tabletowy Kiosk dla operatorów maszyn',
    'author': 'Fayna Digital',
    'depends': ['base', 'mrp'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'dnj_shopfloor/static/src/**/*',
        ],
    },
    'installable': True,
    'application': True,
}
