import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)


class DnjMachineStatus(models.Model):
    """
    Network ping status for each workcenter.
    Written by the machine_bridge service via /dnj_shopfloor/machine/heartbeat.
    One record per workcenter (upserted by the bridge).
    """
    _name = 'dnj.machine.status'
    _description = 'DNJ Machine Network Status'
    _order = 'workcenter_id'

    workcenter_id = fields.Many2one(
        'mrp.workcenter', string='Machine', required=True,
        ondelete='cascade', index=True,
    )
    ip_address = fields.Char(string='IP Address')
    online = fields.Boolean(string='Online', default=False)
    response_ms = fields.Integer(string='Response (ms)', default=0)
    last_check = fields.Datetime(string='Last Check')
    last_online = fields.Datetime(string='Last Online')

    _sql_constraints = [
        ('workcenter_unique', 'UNIQUE(workcenter_id)',
         'Only one status record per workcenter.'),
    ]
