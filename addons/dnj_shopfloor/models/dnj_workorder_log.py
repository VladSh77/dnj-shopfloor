import logging

from odoo import models, fields

_logger = logging.getLogger(__name__)

EVENT_TYPES = [
    ('login', 'Login'),
    ('test_print', 'Test Print'),
    ('confirm_ready', 'Machine Confirmed Ready'),
    ('start', 'Production Start'),
    ('pause', 'Pause'),
    ('resume', 'Resume'),
    ('stop', 'Production Stop'),
    ('scrap', 'Scrap Registered'),
    ('logout', 'Logout'),
    ('error', 'Error'),
]


class DnjWorkorderLog(models.Model):
    """
    Immutable audit log of all kiosk events.
    One row per event — never updated, only created.
    Used for manager dashboard, reporting, and debugging.
    """
    _name = 'dnj.workorder.log'
    _description = 'DNJ Workorder Event Log'
    _order = 'timestamp desc'

    # ── who / where / when ───────────────────────────────────────────────────

    session_id = fields.Many2one(
        'dnj.kiosk.session', string='Session', ondelete='set null', index=True
    )
    operator_id = fields.Many2one(
        'dnj.operator', string='Operator', ondelete='set null', index=True
    )
    workcenter_id = fields.Many2one(
        'mrp.workcenter', string='Machine', ondelete='set null', index=True
    )
    workorder_id = fields.Many2one(
        'mrp.workorder', string='Work Order', ondelete='set null', index=True
    )
    timestamp = fields.Datetime(
        string='Timestamp', default=fields.Datetime.now, required=True, index=True
    )

    # ── what ─────────────────────────────────────────────────────────────────

    event_type = fields.Selection(
        selection=EVENT_TYPES,
        string='Event',
        required=True,
        index=True,
    )
    event_label = fields.Char(
        string='Event Label',
        compute='_compute_event_label',
        store=False,
    )
    note = fields.Char(string='Note')
    qty = fields.Float(string='Qty', default=0.0)

    def _compute_event_label(self):
        label_map = dict(EVENT_TYPES)
        for rec in self:
            rec.event_label = label_map.get(rec.event_type, rec.event_type)
