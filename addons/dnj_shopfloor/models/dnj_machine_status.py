import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)


class DnjMachineStatus(models.Model):
    """
    Network / Modbus status for each monitored workcenter.

    Admin configures:  ip_address, modbus_enabled, modbus_port
    Bridge writes:     online, response_ms, last_check, last_online,
                       machine_running, machine_speed, machine_counter
    """
    _name = 'dnj.machine.status'
    _description = 'DNJ Machine Monitoring'
    _order = 'workcenter_id'

    # ── admin-configurable ────────────────────────────────────────────────────

    workcenter_id = fields.Many2one(
        'mrp.workcenter', string='Machine', required=True,
        ondelete='cascade', index=True,
    )
    ip_address = fields.Char(
        string='IP Address',
        help='IPv4 address of the machine on the factory network. '
             'The bridge will ping this address and optionally read Modbus data.',
    )
    modbus_enabled = fields.Boolean(
        string='Modbus TCP',
        default=False,
        help='Enable Modbus TCP polling for live production data (speed, counter, status).',
    )
    modbus_port = fields.Integer(
        string='Modbus Port',
        default=502,
        help='TCP port of the Modbus server on the machine (default: 502).',
    )
    notes = fields.Text(string='Notes', help='Machine model, connection instructions, etc.')

    # ── live status (written by bridge) ───────────────────────────────────────

    online = fields.Boolean(string='Online', default=False, readonly=True)
    response_ms = fields.Integer(string='Ping (ms)', default=0, readonly=True)
    last_check = fields.Datetime(string='Last Check', readonly=True)
    last_online = fields.Datetime(string='Last Online', readonly=True)

    # Modbus live data
    machine_running = fields.Boolean(string='Running', default=False, readonly=True)
    machine_speed = fields.Integer(
        string='Speed (sh/h)', default=0, readonly=True,
        help='Sheets per hour read from Modbus register.',
    )
    machine_counter = fields.Integer(
        string='Counter', default=0, readonly=True,
        help='Sheet counter read from Modbus register.',
    )

    _sql_constraints = [
        ('workcenter_unique', 'UNIQUE(workcenter_id)',
         'Only one monitoring record per workcenter.'),
    ]

    def name_get(self):
        return [(r.id, r.workcenter_id.name) for r in self]
