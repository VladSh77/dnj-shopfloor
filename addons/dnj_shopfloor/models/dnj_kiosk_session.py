import logging
from datetime import timedelta

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DnjKioskSession(models.Model):
    """
    One session = one operator logged in at one machine.
    Tracks the full lifecycle: login → test print → work → pauses → logout.

    State machine:
        active  ──► test_print ──► confirmed ──► progress ──► done
                                                    ▲  │
                                                    └──┘  (via paused)
    """
    _name = 'dnj.kiosk.session'
    _description = 'DNJ Kiosk Session'
    _order = 'start_time desc'

    # ── identity ──────────────────────────────────────────────────────────────

    name = fields.Char(string='Session', compute='_compute_name', store=True)
    operator_id = fields.Many2one(
        'dnj.operator', string='Operator', required=True, ondelete='restrict', index=True
    )
    workcenter_id = fields.Many2one(
        'mrp.workcenter', string='Machine', required=True, ondelete='restrict', index=True
    )
    workorder_id = fields.Many2one(
        'mrp.workorder', string='Work Order', ondelete='set null', index=True
    )

    # ── state ─────────────────────────────────────────────────────────────────

    state = fields.Selection(
        selection=[
            ('active', 'Logged In'),          # operator logged in, no WO selected
            ('test_print', 'Test Print'),      # test print in progress
            ('confirmed', 'Machine Ready'),    # machine confirmed, waiting START
            ('progress', 'Working'),           # production running
            ('paused', 'Paused'),             # pause (coffee / maintenance)
            ('done', 'Done'),                 # session closed
        ],
        default='active',
        required=True,
        string='State',
        index=True,
    )

    # ── timing ────────────────────────────────────────────────────────────────

    start_time = fields.Datetime(
        string='Login', default=fields.Datetime.now, required=True
    )
    end_time = fields.Datetime(string='Logout')
    work_start_time = fields.Datetime(string='Work Start')
    work_end_time = fields.Datetime(string='Work End')

    duration_total = fields.Float(
        string='Total Time (min)', compute='_compute_durations', store=False
    )
    duration_net = fields.Float(
        string='Net Work (min)', compute='_compute_durations', store=False
    )
    duration_pause = fields.Float(
        string='Pause Time (min)', compute='_compute_durations', store=False
    )

    # ── test print ────────────────────────────────────────────────────────────

    test_print_qty = fields.Float(
        string='Test Print Qty', default=0.0,
        help='Number of sheets used for test print. Deducted from stock.'
    )
    test_print_confirmed = fields.Boolean(
        string='Machine OK', default=False,
        help='Operator confirmed machine produces clean output.'
    )
    test_print_stock_move_id = fields.Many2one(
        'stock.move', string='Test Print Stock Move', ondelete='set null'
    )

    # ── production ────────────────────────────────────────────────────────────

    qty_produced = fields.Float(string='Qty Produced', default=0.0)
    qty_scrap = fields.Float(string='Qty Scrap', default=0.0)

    # ── relations ─────────────────────────────────────────────────────────────

    pause_ids = fields.One2many('dnj.kiosk.pause', 'session_id', string='Pauses')
    log_ids = fields.One2many('dnj.workorder.log', 'session_id', string='Event Log')

    # ── computed ──────────────────────────────────────────────────────────────

    @api.depends('operator_id', 'workcenter_id', 'start_time')
    def _compute_name(self):
        for rec in self:
            dt = rec.start_time.strftime('%Y-%m-%d %H:%M') if rec.start_time else ''
            rec.name = f"{rec.operator_id.name or '?'} / {rec.workcenter_id.name or '?'} / {dt}"

    @api.depends('start_time', 'end_time', 'pause_ids.duration_minutes')
    def _compute_durations(self):
        now = fields.Datetime.now()
        for rec in self:
            if not rec.start_time:
                rec.duration_total = rec.duration_net = rec.duration_pause = 0.0
                continue
            end = rec.end_time or now
            total = (end - rec.start_time).total_seconds() / 60
            pause = sum(rec.pause_ids.mapped('duration_minutes'))
            rec.duration_total = round(total, 1)
            rec.duration_pause = round(pause, 1)
            rec.duration_net = round(total - pause, 1)

    # ── state transitions ─────────────────────────────────────────────────────

    def action_start_test_print(self, qty: float):
        """Operator starts test print phase."""
        self.ensure_one()
        if self.state not in ('active', 'confirmed'):
            raise UserError("Cannot start test print in current state.")
        self.write({'state': 'test_print', 'test_print_qty': qty})
        self._log('test_print', f'Test print started: {qty} sheets', qty=qty)
        _logger.info("[Session %s] Test print started qty=%.1f", self.id, qty)

    def action_confirm_machine(self):
        """Operator confirms machine is ready after test print."""
        self.ensure_one()
        if self.state != 'test_print':
            raise UserError("Machine can only be confirmed after test print.")
        self.write({'state': 'confirmed', 'test_print_confirmed': True})
        self._log('confirm_ready', 'Machine confirmed ready')
        _logger.info("[Session %s] Machine confirmed ready", self.id)

    def action_start_work(self):
        """Start actual production (START button)."""
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError("Machine must be confirmed ready before starting work.")
        if not self.workorder_id:
            raise UserError("No work order selected.")
        now = fields.Datetime.now()
        self.write({'state': 'progress', 'work_start_time': now})
        # Trigger Odoo workorder start
        if self.workorder_id.state not in ('progress', 'done'):
            self.workorder_id.button_start()
        self._log('start', 'Production started')
        _logger.info("[Session %s] Production started WO=%s", self.id, self.workorder_id.name)

    def action_pause(self, reason: str = ''):
        """Pause work (coffee break, maintenance, etc.)."""
        self.ensure_one()
        if self.state != 'progress':
            raise UserError("Can only pause while working.")
        self.env['dnj.kiosk.pause'].create({
            'session_id': self.id,
            'start_time': fields.Datetime.now(),
            'reason': reason or 'pause',
        })
        self.write({'state': 'paused'})
        self._log('pause', f'Paused: {reason}')
        _logger.info("[Session %s] Paused reason=%s", self.id, reason)

    def action_resume(self):
        """Resume work after pause."""
        self.ensure_one()
        if self.state != 'paused':
            raise UserError("Session is not paused.")
        # Close the latest open pause
        open_pause = self.pause_ids.filtered(lambda p: not p.end_time)[:1]
        if open_pause:
            open_pause.write({'end_time': fields.Datetime.now()})
        self.write({'state': 'progress'})
        self._log('resume', 'Work resumed')
        _logger.info("[Session %s] Resumed", self.id)

    def action_stop_work(self, qty_produced: float, qty_scrap: float = 0.0):
        """Stop production (STOP button). Record quantities."""
        self.ensure_one()
        if self.state not in ('progress', 'paused'):
            raise UserError("Session is not in progress.")
        now = fields.Datetime.now()
        # Close any open pause
        open_pause = self.pause_ids.filtered(lambda p: not p.end_time)[:1]
        if open_pause:
            open_pause.write({'end_time': now})
        self.write({
            'state': 'done',
            'work_end_time': now,
            'qty_produced': qty_produced,
            'qty_scrap': qty_scrap,
        })
        # Write back to Odoo workorder
        if self.workorder_id:
            self.workorder_id.write({'qty_produced': qty_produced})
            try:
                self.workorder_id.button_finish()
            except Exception as e:
                _logger.warning("[Session %s] button_finish failed: %s", self.id, e)
        self._log('stop', f'Work stopped. Produced={qty_produced}, Scrap={qty_scrap}',
                  qty=qty_produced)
        _logger.info("[Session %s] Work stopped produced=%.1f scrap=%.1f",
                     self.id, qty_produced, qty_scrap)

    def action_logout(self):
        """Operator logs out."""
        self.ensure_one()
        now = fields.Datetime.now()
        # Close any open pause
        open_pause = self.pause_ids.filtered(lambda p: not p.end_time)[:1]
        if open_pause:
            open_pause.write({'end_time': now})
        if self.state not in ('done',):
            self.write({'state': 'done', 'end_time': now})
        else:
            self.write({'end_time': now})
        self._log('logout', 'Operator logged out')
        _logger.info("[Session %s] Operator logged out", self.id)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _log(self, event_type: str, note: str = '', qty: float = 0.0):
        self.env['dnj.workorder.log'].create({
            'session_id': self.id,
            'operator_id': self.operator_id.id,
            'workcenter_id': self.workcenter_id.id,
            'workorder_id': self.workorder_id.id if self.workorder_id else False,
            'event_type': event_type,
            'note': note,
            'qty': qty,
        })
