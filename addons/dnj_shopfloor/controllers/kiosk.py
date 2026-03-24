import logging
import werkzeug

from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)


class DnjKioskController(http.Controller):
    """
    JSON-RPC endpoints for the DNJ Shop Floor Kiosk.
    All routes require an authenticated Odoo session (auth='user').
    Data reads use sudo() so the shared kiosk Odoo account does not
    need MRP/stock group membership — operators authenticate via PIN.
    """

    # ── auth ──────────────────────────────────────────────────────────────────

    @http.route('/dnj_shopfloor/authenticate', type='json', auth='user')
    def authenticate(self, pin: str, workcenter_id: int):
        """Verify operator PIN. Returns operator info or error."""
        result = request.env['dnj.operator'].sudo().authenticate(pin, workcenter_id)
        _logger.info("PIN auth attempt workcenter_id=%s success=%s", workcenter_id, result.get('success'))
        return result

    # ── session ───────────────────────────────────────────────────────────────

    @http.route('/dnj_shopfloor/session/open', type='json', auth='user')
    def session_open(self, operator_id: int, workcenter_id: int):
        """Open a new kiosk session for the authenticated operator."""
        Session = request.env['dnj.kiosk.session'].sudo()
        old = Session.search([
            ('operator_id', '=', operator_id),
            ('workcenter_id', '=', workcenter_id),
            ('state', 'not in', ['done']),
        ])
        for s in old:
            s.action_logout()

        session = Session.create({
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
        session = request.env['dnj.kiosk.session'].sudo().browse(session_id)
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
        rows = request.env['mrp.workorder'].sudo().search_read(
            domain=[
                ('workcenter_id', '=', workcenter_id),
                ('state', 'in', ['pending', 'waiting', 'ready', 'progress']),
            ],
            fields=['id', 'name', 'state', 'production_id', 'product_id',
                    'qty_production', 'qty_produced', 'date_start', 'duration_expected'],
            order='date_start asc',
            limit=50,
        )
        return rows

    @http.route('/dnj_shopfloor/workcenters', type='json', auth='user')
    def get_workcenters(self):
        """Return all active workcenters (for kiosk machine selector)."""
        rows = request.env['mrp.workcenter'].sudo().search_read(
            domain=[('active', '=', True)],
            fields=['id', 'name', 'code'],
            order='name asc',
            limit=50,
        )
        return rows

    @http.route('/dnj_shopfloor/session/status', type='json', auth='user')
    def session_status(self, session_id: int):
        """Return current session state (for polling/refresh)."""
        session = request.env['dnj.kiosk.session'].sudo().browse(session_id)
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

    # ── auto-login entry point ─────────────────────────────────────────────────

    @http.route('/kiosk', type='http', auth='none', csrf=False)
    def kiosk_entry(self):
        """
        Tablet entry point — auto-login as the shared kiosk Odoo user and
        redirect to the fullscreen kiosk action.  Credentials are stored in
        ir.config_parameter so they can be changed without code changes:
          dnj_shopfloor.kiosk_login    (default: kiosk)
          dnj_shopfloor.kiosk_password (default: Kiosk2024)
        """
        if not request.session.uid:
            ICP = request.env['ir.config_parameter'].sudo()
            login    = ICP.get_param('dnj_shopfloor.kiosk_login',    'kiosk')
            password = ICP.get_param('dnj_shopfloor.kiosk_password', 'Kiosk2024')
            request.session.authenticate(request.db, login, password)

        return request.make_response(
            """<!DOCTYPE html><html><head><meta charset="utf-8">
            <meta name="viewport" content="width=device-width,initial-scale=1">
            <title>DNJ Kiosk</title></head><body>
            <script>window.location.replace('/web#action=dnj_shopfloor.action_dnj_shopfloor_kiosk');</script>
            </body></html>""",
            headers=[('Content-Type', 'text/html; charset=utf-8')]
        )

    # ── machine bridge heartbeat ───────────────────────────────────────────────

    @http.route('/dnj_shopfloor/machine/heartbeat', type='json', auth='user')
    def machine_heartbeat(self, machines: list):
        """
        Called by the machine_bridge service every N seconds.
        machines: [{workcenter_id, online, response_ms, ip_address}]
        Creates or updates dnj.machine.status records.
        """
        now = fields.Datetime.now()
        Status = request.env['dnj.machine.status'].sudo()
        for m in machines:
            wc_id = m.get('workcenter_id')
            if not wc_id:
                continue
            online = bool(m.get('online'))
            rec = Status.search([('workcenter_id', '=', wc_id)], limit=1)
            vals = {
                'online':      online,
                'response_ms': int(m.get('response_ms') or 0),
                'ip_address':  m.get('ip_address', ''),
                'last_check':  now,
            }
            if online:
                vals['last_online'] = now
            if rec:
                rec.write(vals)
            else:
                vals['workcenter_id'] = wc_id
                Status.create(vals)
        return {'ok': True, 'updated': len(machines)}

    # ── manager dashboard data ─────────────────────────────────────────────────

    @http.route('/dnj_shopfloor/dashboard', type='json', auth='user')
    def dashboard(self):
        """Return all workcenters with their live session data."""
        env = request.env
        workcenters = env['mrp.workcenter'].sudo().search(
            [('active', '=', True)], order='name')
        # Pre-load all machine statuses in one query
        statuses = {
            s.workcenter_id.id: s
            for s in env['dnj.machine.status'].sudo().search([])
        }

        result = []
        for wc in workcenters:
            session = env['dnj.kiosk.session'].sudo().search([
                ('workcenter_id', '=', wc.id),
                ('state', 'not in', ['done']),
            ], limit=1, order='create_date desc')

            sess_data = None
            if session:
                pause_min = sum(session.pause_ids.mapped('duration_minutes'))
                wo = session.workorder_id
                sess_data = {
                    'id':             session.id,
                    'state':          session.state,
                    'operator':       session.operator_id.name,
                    'workorder':      wo.name if wo else '',
                    'product':        wo.product_id.display_name if wo and wo.product_id else '',
                    'qty_produced':      session.qty_produced,
                    'qty_scrap':         session.qty_scrap,
                    'qty_production':    wo.qty_production if wo else 0,
                    'duration_expected': wo.duration_expected if wo else 0,
                    'work_start':        session.work_start_time.isoformat() if session.work_start_time else None,
                    'pause_minutes':     pause_min,
                }

            ms = statuses.get(wc.id)
            machine_status = {
                'monitored': bool(ms),
                'online':      ms.online if ms else None,
                'response_ms': ms.response_ms if ms else None,
                'last_check':  ms.last_check.isoformat() if ms and ms.last_check else None,
            }

            result.append({
                'id':             wc.id,
                'name':           wc.name,
                'code':           wc.code or '',
                'session':        sess_data,
                'machine_status': machine_status,
            })
        return result
