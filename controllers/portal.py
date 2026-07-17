import base64
import logging
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class PatientPortal(CustomerPortal):

    # -----------------------------
    # Helper: Generate time slots
    # -----------------------------
    def _get_time_slots(self):
        """Generate 30-minute slots from 8:00 AM to 6:00 PM"""
        slots = []
        hour = 8.0
        while hour < 18.0:
            h = int(hour)
            m = int(round((hour - h) * 60))
            label = f"{h:02d}:{m:02d}"
            slots.append({'value': str(hour), 'label': label})
            hour += 0.5
        return slots

    # -----------------------------
    # Portal Home Counter
    # -----------------------------
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id
        if 'visit_count' in counters:
            values['visit_count'] = request.env['patient.visit'].sudo().search_count([
                ('patient_id', '=', partner.id)
            ])
        return values

    # -----------------------------
    # My Appointments Page (with pager)
    # -----------------------------
    @http.route(['/my/appointments', '/my/appointments/page/<int:page>'],
                type='http', auth="user", website=True)
    def portal_my_appointments(self, page=1, **kwargs):
        partner = request.env.user.partner_id
        step = 10

        visit_count = request.env['patient.visit'].sudo().search_count([
            ('patient_id', '=', partner.id)
        ])

        pager = portal_pager(
            url='/my/appointments',
            total=visit_count,
            page=page,
            step=step,
        )

        visits = request.env['patient.visit'].sudo().search([
            ('patient_id', '=', partner.id)
        ], order='visit_date desc', limit=step, offset=pager['offset'])

        return request.render('patients.portal_my_appointments', {
            'visits': visits,
            'pager': pager,
            'page_name': 'appointments',
        })

    # -----------------------------
    # Appointment Form (GET)
    # -----------------------------
    @http.route(['/my/appointments/new'], type='http', auth="user", website=True)
    def portal_new_appointment(self, department_id=None, **kwargs):
        import datetime

        doctor_group = request.env.ref('patients.group_patient_doctor').sudo()
        all_doctors = doctor_group.user_ids

        departments = request.env['doctor.department'].sudo().search([
            ('id', 'in', all_doctors.mapped('department_id').ids),
            ('active', '=', True),
        ])

        if department_id:
            doctors = all_doctors.filtered(
                lambda d: d.department_id.id == int(department_id)
            )
        else:
            doctors = all_doctors

        return request.render('patients.portal_appointment_form', {
            'doctors': doctors,
            'departments': departments,
            'selected_department_id': int(department_id) if department_id else None,
            'time_slots': self._get_time_slots(),
            'min_date': datetime.date.today().strftime('%Y-%m-%d'),
            'error': kwargs.get('error'),
            'error_fields': kwargs.get('error_fields', ''),
            'page_name': 'new_appointment',
        })

    # -----------------------------
    # Appointment Create (POST)
    # -----------------------------
    @http.route(['/my/appointments/create'], type='http', auth="user",
                website=True, methods=['POST'], csrf=False)
    def portal_create_appointment(self, **post):
        import datetime
        partner = request.env.user.partner_id

        doctor_id = int(post.get('doctor_id', 0))
        visit_date = post.get('visit_date', '').strip()
        notes = post.get('notes', '')
        visit_time_raw = post.get('visit_time', '').strip()

        # --- Validate inputs ---
        if not doctor_id or not visit_date or not visit_time_raw:
            return request.redirect('/my/appointments/new?error=Please+fill+in+all+required+fields.')

        # --- Validate visit_time is a valid selection key ---
        valid_times = [
            v[0] for v in request.env['patient.visit']._fields['visit_time'].selection
        ]
        if visit_time_raw not in valid_times:
            return request.redirect('/my/appointments/new?error=Invalid+time+selected.')

        # --- Validate date is not in the past ---
        try:
            selected_date = datetime.datetime.strptime(visit_date, '%Y-%m-%d').date()
            if selected_date < datetime.date.today():
                return request.redirect(
                    '/my/appointments/new?error=Cannot+book+appointments+for+past+dates.'
                )
        except ValueError:
            return request.redirect('/my/appointments/new?error=Invalid+date+selected.')

        # --- Double booking check (only block scheduled visits) ---
        existing = request.env['patient.visit'].sudo().search([
            ('doctor_id', '=', doctor_id),
            ('visit_date', '=', visit_date),
            ('visit_time', '=', visit_time_raw),
            ('state', 'not in', ['cancelled', 'pending_payment', 'draft']),
        ], limit=1)

        if existing:
            time_label = dict(
                request.env['patient.visit']._fields['visit_time'].selection
            ).get(visit_time_raw, visit_time_raw)
            doctor = request.env['res.users'].sudo().browse(doctor_id)
            booking_error = (
                f"Dr. {doctor.name} already has an appointment at "
                f"{time_label} on {visit_date}. Please choose a different time slot."
            )
            return request.redirect(
                f'/my/appointments/new?error={booking_error.replace(" ", "+")}'
            )

        # --- Create the visit ---
        visit = request.env['patient.visit'].sudo().create({
            'name': request.env['ir.sequence'].next_by_code('patient.visit') or 'New Visit',
            'patient_id': partner.id,
            'doctor_id': doctor_id,
            'visit_date': visit_date,
            'visit_time': visit_time_raw,  # always a string e.g. '16.0'
            'notes': notes,
            'state': 'pending_payment',
        })

        # --- Handle file upload ---
        file = post.get('report')
        if file and hasattr(file, 'filename') and file.filename:
            if not file.filename.lower().endswith(('.pdf', '.jpg', '.png')):
                raise AccessError("Invalid file type")
            request.env['ir.attachment'].sudo().create({
                'name': file.filename,
                'type': 'binary',
                'datas': base64.b64encode(file.read()).decode('utf-8'),
                'res_model': 'patient.visit',
                'res_id': visit.id,
            })

        return request.redirect(f"/my/appointments/pay/{visit.id}")

    # -----------------------------
    # Cancel Appointment
    # -----------------------------
    @http.route(['/my/appointments/cancel/<int:visit_id>'], type='http', auth="user", website=True)
    def portal_cancel_appointment(self, visit_id, **kwargs):
        partner = request.env.user.partner_id
        visit = request.env['patient.visit'].sudo().browse(visit_id)

        if not visit.exists() or visit.patient_id.id != partner.id:
            return request.redirect('/my/appointments')

        if visit.state not in ('draft', 'pending_payment', 'scheduled'):
            return request.redirect(f'/my/appointments/{visit_id}')

        visit.write({'state': 'cancelled'})
        return request.redirect('/my/appointments')

    # -----------------------------
    # Payment Page
    # -----------------------------
    @http.route(['/my/appointments/pay/<int:visit_id>'], type='http', auth="user", website=True)
    def portal_pay_visit(self, visit_id, **kwargs):
        visit = request.env['patient.visit'].sudo().browse(visit_id)
        partner = request.env.user.partner_id

        if not visit.exists() or visit.patient_id.id != partner.id:
            return request.redirect('/my')

        if visit.state != 'pending_payment':
            return request.redirect(f'/my/appointments/{visit.id}')

        return request.render('patients.portal_payment_page', {
            'visit': visit,
            'page_name': 'payment',
        })

    # -----------------------------
    # Confirm Payment
    # -----------------------------
    @http.route(['/my/appointments/confirm_payment/<int:visit_id>'],
                type='http', auth="user", website=True)
    def portal_confirm_payment(self, visit_id, **post):
        visit = request.env['patient.visit'].sudo().browse(visit_id)
        visit.write({
            'is_paid': True,
            'payment_reference': 'TOKEN-' + str(visit.id),
        })
        return request.redirect('/my/appointments')

    # -----------------------------
    # Visit Detail
    # -----------------------------
    @http.route(['/my/appointments/<int:visit_id>'], type='http', auth="user", website=True)
    def portal_visit_detail(self, visit_id, **kwargs):
        partner = request.env.user.partner_id
        visit = request.env['patient.visit'].sudo().browse(visit_id)

        if visit.patient_id.id != partner.id:
            return request.redirect('/my')

        return request.render('patients.portal_visit_detail', {
            'visit': visit,
            'page_name': 'visit_detail',
        })

    # -----------------------------
    # Download Receipt
    # -----------------------------
    @http.route(['/my/patient/visit/<int:visit_id>/receipt'], type='http', auth='user')
    def download_receipt(self, visit_id, **kwargs):
        visit = request.env['patient.visit'].sudo().browse(visit_id)

        if not visit.exists():
            raise AccessError("Invalid record")

        if visit.patient_id.id != request.env.user.partner_id.id:
            raise AccessError("You are not allowed to access this receipt")

        pdf, _ = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'patients.action_report_patient_visit',
            [visit.id]
        )

        return request.make_response(pdf, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf)),
            ('Content-Disposition', f'attachment; filename="receipt_{visit.id}.pdf"'),
        ])