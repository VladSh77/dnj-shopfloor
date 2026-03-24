import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class DnjKioskPause(models.Model):
    """
    Single pause record within a kiosk session.
    Multiple pauses per session are allowed.
    """
    _name = 'dnj.kiosk.pause'
    _description = 'DNJ Kiosk Pause'
    _order = 'start_time desc'

    session_id = fields.Many2one(
        'dnj.kiosk.session', string='Session', required=True, ondelete='cascade', index=True
    )
    start_time = fields.Datetime(string='Pause Start', required=True, default=fields.Datetime.now)
    end_time = fields.Datetime(string='Pause End')

    reason = fields.Selection(
        selection=[
            ('pause', 'Short Break'),
            ('coffee', 'Coffee Break'),
            ('maintenance', 'Machine Maintenance'),
            ('material', 'Waiting for Material'),
            ('other', 'Other'),
        ],
        string='Reason',
        default='pause',
        required=True,
    )
    note = fields.Char(string='Note')

    duration_minutes = fields.Float(
        string='Duration (min)',
        compute='_compute_duration',
        store=True,
    )

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.start_time:
                end = rec.end_time or now
                rec.duration_minutes = round(
                    (end - rec.start_time).total_seconds() / 60, 1
                )
            else:
                rec.duration_minutes = 0.0
