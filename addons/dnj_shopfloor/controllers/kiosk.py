import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class DnjKioskController(http.Controller):
    """
    JSON-RPC endpoints for the DNJ Shop Floor Kiosk.
    All routes require an authenticated Odoo session (auth='user').
    Business logic is delegated to the Python models.
    """

    # ── auth ──────────────────────────────────────────────────────────────────

    @http.route('/dnj_shopfloor/authenticate', type='json', auth='user')
    def authenticate(self, pin: str, workcenter_id: int):
        """Verify operator PIN. Returns operator info or error."""
        result = request.env['dnj.operator'].authenticate(pin, workcenter_id)
        _logger.info("PIN auth attempt workcenter_id=%s success=%s", workcenter_id, result.get('success'))
        return result

    # ── session ───────────────────────────────────────────────────────────────

    @http.route('/dnj_shopfloor/session/open', type='json', auth='user')
    def session_open(self, operator_id: int, workcenter_id: int):
        """Open a new kiosk session for the authenticated operator."""
        env = request.env
        # Close any dangling active sessions for this operator+workcenter
        old = env['dnj.kiosk.session'].search([
            ('operator_id', '=', operator_id),
            ('workcenter_id', '=', workcenter_id),
            ('state', 'not in', ['done']),
        ])
        for s in old:
            s.action_logout()

        session = env['dnj.kiosk.session'].create({
            'operator_id': operator_id,
            'workcenter_id': workcenter_id,
        })
        session._log('login', 'Operator logged in')
        _logger.info("[Session %s] Opened operator_id=%s workcenter_id=%s",
                     session.id, operator_id, workcenter_id)
        return {'session_id': session.id, 'state': session.state}

    @http.route('/dnj_shopfloor/session/action', type='json', auth='user')
    def session_action(self, session_id: int, action: str, **kwargs):
        """
        Perform a lifecycle action on an existing session.
        actions: test_print | confirm_machine | select_workorder |
                 start_work | pause | resume | stop | logout
        """
        session = request.env['dnj.kiosk.session'].browse(session_id)
        if not session.exists():
            return {'success': False, 'error': 'Session not found'}
        try:
            if action == 'select_workorder':
                session.write({'workorder_id': kwargs.get('workorder_id')})
                return {'success': True, 'state': session.state}

            elif action == 'test_print':
                session.action_start_test_print(float(kwargs.get('qty', 0)))

            elif action == 'confirm_machine':
                session.action_confirm_machine()

            elif action == 'start_work':
                session.action_start_work()

            elif action == 'pause':
                session.action_pause(kwargs.get('reason', 'pause'))

            elif action == 'resume':
                session.action_resume()

            elif action == 'stop':
                session.action_stop_work(
                    float(kwargs.get('qty_produced', 0)),
                    float(kwargs.get('qty_scrap', 0)),
                )

            elif action == 'logout':
                session.action_logout()

            else:
                return {'success': False, 'error': f'Unknown action: {action}'}

            return {'success': True, 'state': session.state}

        except Exception as e:
            _logger.exception("[Session %s] action=%s failed", session_id, action)
            return {'success': False, 'error': str(e)}

    # ── data queries ──────────────────────────────────────────────────────────

    @http.route('/dnj_shopfloor/workorders', type='json', auth='user')
    def get_workorders(self, workcenter_id: int):
        """Return active work orders for the given workcenter."""
        rows = request.env['mrp.workorder'].search_read(
            domain=[
                ('workcenter_id', '=', workcenter_id),
                ('state', 'in', ['pending', 'waiting', 'ready', 'progress']),
            ],
            fields=['id', 'name', 'state', 'production_id', 'product_id',
                    'qty_production', 'qty_produced', 'date_planned_start'],
            order='date_planned_start asc',
            limit=50,
        )
        return rows

    @http.route('/dnj_shopfloor/session/status', type='json', auth='user')
    def session_status(self, session_id: int):
        """Return current session state (for polling/refresh)."""
        session = request.env['dnj.kiosk.session'].browse(session_id)
        if not session.exists():
            return {'found': False}
        pause_minutes = sum(session.pause_ids.mapped('duration_minutes'))
        return {
            'found': True,
            'state': session.state,
            'work_start_time': session.work_start_time and
                               session.work_start_time.isoformat() or False,
            'pause_minutes': pause_minutes,
            'qty_produced': session.qty_produced,
            'qty_scrap': session.qty_scrap,
        }
