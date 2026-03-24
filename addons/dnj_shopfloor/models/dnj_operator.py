import hashlib
import logging

from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class DnjOperator(models.Model):
    """
    Kiosk operator identified by PIN code.
    Does NOT require a separate Odoo user account.
    PIN is stored as SHA-256 hash for security.
    """
    _name = 'dnj.operator'
    _description = 'DNJ Kiosk Operator'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    pin_hash = fields.Char(
        string='PIN Hash',
        required=True,
        help='SHA-256 hash of the PIN. Never store raw PIN.'
    )
    workcenter_ids = fields.Many2many(
        'mrp.workcenter',
        string='Allowed Machines',
        help='Leave empty to allow all machines.'
    )
    active = fields.Boolean(default=True)
    note = fields.Text(string='Notes')

    session_ids = fields.One2many('dnj.kiosk.session', 'operator_id', string='Sessions')
    session_count = fields.Integer(
        string='Total Sessions',
        compute='_compute_session_count',
        store=True,
    )
    last_session_date = fields.Datetime(
        string='Last Activity',
        compute='_compute_session_count',
        store=True,
    )

    # ── constraints ───────────────────────────────────────────────────────────

    @api.constrains('pin_hash')
    def _check_pin_hash(self):
        for rec in self:
            if rec.pin_hash and len(rec.pin_hash) != 64:
                raise ValidationError(
                    "PIN hash must be a valid SHA-256 hex string (64 chars). "
                    "Use the 'Set PIN' button."
                )

    # ── computed ──────────────────────────────────────────────────────────────

    @api.depends('session_ids', 'session_ids.start_time')
    def _compute_session_count(self):
        for rec in self:
            sessions = rec.session_ids
            rec.session_count = len(sessions)
            rec.last_session_date = max(sessions.mapped('start_time'), default=False)

    # ── business logic ────────────────────────────────────────────────────────

    def _hash_pin(self, pin: str) -> str:
        return hashlib.sha256(str(pin).strip().encode()).hexdigest()

    def set_pin(self, pin: str):
        """Set operator PIN (hashed). Call from form or wizard."""
        self.ensure_one()
        if not pin or not str(pin).strip().isdigit() or not (4 <= len(str(pin).strip()) <= 6):
            raise ValidationError("PIN must be 4–6 digits.")
        self.pin_hash = self._hash_pin(pin)
        _logger.info("PIN updated for operator %s (id=%s)", self.name, self.id)

    @api.model
    def authenticate(self, pin: str, workcenter_id: int) -> dict:
        """
        Verify PIN and workcenter access.
        Returns {'success': True, 'operator_id': id, 'name': name}
        or      {'success': False, 'error': message}
        """
        if not pin:
            return {'success': False, 'error': 'PIN required'}

        pin_hash = self._hash_pin(pin)
        operator = self.sudo().search(
            [('pin_hash', '=', pin_hash), ('active', '=', True)],
            limit=1,
        )
        if not operator:
            _logger.warning("Failed PIN attempt for workcenter_id=%s", workcenter_id)
            return {'success': False, 'error': 'Invalid PIN'}

        # workcenter restriction
        if operator.workcenter_ids and workcenter_id not in operator.workcenter_ids.ids:
            _logger.warning(
                "Operator %s not allowed on workcenter_id=%s", operator.name, workcenter_id
            )
            return {'success': False, 'error': 'Not authorized for this machine'}

        _logger.info("Operator %s (id=%s) authenticated on workcenter_id=%s",
                     operator.name, operator.id, workcenter_id)
        return {'success': True, 'operator_id': operator.id, 'name': operator.name}
