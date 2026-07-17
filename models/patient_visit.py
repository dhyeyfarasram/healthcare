from odoo import fields, models, api
from odoo.exceptions import UserError, ValidationError
import datetime
import uuid
import logging
_logger = logging.getLogger(__name__)


class PatientVisit(models.Model):
    _name = 'patient.visit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Patient Visit'
    _order = 'visit_date desc'

    name = fields.Char(string='Name', required=True, copy=False, default='New Visit')
    prescription_line_ids = fields.One2many(
        'patient.prescription.line',
        'visit_id',
        string='Prescriptions',
        tracking=True
    )
    patient_id = fields.Many2one(
        'res.partner',
        string='Patient',
        required=True,
        domain=[('is_patient', '=', True)]
    )
    doctor_id = fields.Many2one(
        'res.users',
        string='Doctor',
        required=True,
        tracking=True
    )
    doctor_department_id = fields.Many2one(
        related='doctor_id.department_id',
        string='Department',
        store=True,
        readonly=True,
    )

    visit_date = fields.Date(string='Visit Date', required=True, tracking=True)
    visit_time = fields.Selection([
        ('8.0', '08:00'), ('8.5', '08:30'),
        ('9.0', '09:00'), ('9.5', '09:30'),
        ('10.0', '10:00'), ('10.5', '10:30'),
        ('11.0', '11:00'), ('11.5', '11:30'),
        ('12.0', '12:00'), ('12.5', '12:30'),
        ('13.0', '13:00'), ('13.5', '13:30'),
        ('14.0', '14:00'), ('14.5', '14:30'),
        ('15.0', '15:00'), ('15.5', '15:30'),
        ('16.0', '16:00'), ('16.5', '16:30'),
        ('17.0', '17:00'), ('17.5', '17:30'),
    ], string='Visit Time', required=True)

    patient_blood_group = fields.Selection(
        related='patient_id.blood_group',
        string='Blood Group',
        readonly=True,
    )
    patient_allergies = fields.Text(
        related='patient_id.allergies',
        string='Allergies',
        readonly=True,
    )
    patient_chronic_conditions = fields.Text(
        related='patient_id.chronic_conditions',
        string='Chronic Conditions',
        readonly=True,
    )
    patient_current_medications = fields.Text(
        related='patient_id.current_medications',
        string='Current Medications',
        readonly=True,
    )
    patient_last_visit_summary = fields.Text(
        string='Last Visit Summary',
        compute='_compute_patient_last_visit_summary',
    )


    notes = fields.Text(string='Notes', tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending_payment', 'Pending Payment'),
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True)

    token_amount = fields.Float(string='Token Amount', default=50.0)
    is_paid = fields.Boolean(string='Is Paid', default=False, tracking=True, required=True)
    payment_reference = fields.Char(string='Payment Reference', tracking=True)
    is_locked = fields.Boolean(compute='_compute_is_locked')
    is_locked_scheduled = fields.Boolean(compute='_compute_is_locked_scheduled')
    past_date_email_sent = fields.Boolean(
        string='Past Date Email Sent',
        default=False,
        help='Tracks whether the past-date reminder email has already been sent.'
    )
    followup_ids = fields.One2many(
        'patient.followup',
        'visit_id',
        string='Follow-ups'
    )

    # --------------------------------------------------
    # Constraints
    # --------------------------------------------------
    @api.depends('patient_id', 'patient_id.visit_ids')
    def _compute_patient_last_visit_summary(self):
        for rec in self:
            # Get previous visits excluding the current one
            previous = rec.patient_id.visit_ids.filtered(
                lambda v: v.id != rec.id
            ).sorted('visit_date', reverse=True)[:1]

            if previous:
                last = previous[0]
                prescriptions = last.prescription_line_ids
                rx_lines = '\n'.join(
                    f"  - {p.medicine_id.name} | {p.dosage} | {p.instructions or ''}"
                    for p in prescriptions
                ) or '  None'
                rec.patient_last_visit_summary = (
                    f"Visit: {last.name}\n"
                    f"Date: {last.visit_date}\n"
                    f"Doctor: {last.doctor_id.name}\n"
                    f"Notes: {last.notes or 'None'}\n"
                    f"Prescriptions:\n{rx_lines}"
                )
            else:
                rec.patient_last_visit_summary = 'No previous visits.'

    @api.constrains('doctor_id', 'visit_date', 'visit_time', 'state')
    def _check_double_booking(self):
        slot_duration = 0.5

        for rec in self:
            if rec.state == 'cancelled':
                continue
            slot_start = float(rec.visit_time)
            slot_end = slot_start + slot_duration

            conflicts = self.search([
                ('id', '!=', rec.id),
                ('doctor_id', '=', rec.doctor_id.id),
                ('visit_date', '=', rec.visit_date),
                ('state', 'not in', ['cancelled', 'pending_payment', 'draft']),
            ])
            for conflict in conflicts:
                conflict_start = float(conflict.visit_time)
                conflict_end = conflict_start + slot_duration
                if slot_start < conflict_end and slot_end > conflict_start:
                    raise ValidationError(
                        f"Doctor {rec.doctor_id.name} already has an appointment at "
                        f"{conflict.visit_time} on {rec.visit_date}. "
                        f"(Ref: {conflict.name})"
                    )

    @api.constrains('visit_date')
    def _check_visit_date(self):
        for rec in self:
            if rec.visit_date and rec.visit_date < datetime.date.today():
                raise ValidationError("Cannot schedule appointments for past dates.")

    # --------------------------------------------------
    # Computed fields
    # --------------------------------------------------
    @api.depends('state')
    def _compute_is_locked(self):
        for rec in self:
            rec.is_locked = rec.state in ['completed', 'cancelled']
    @api.depends('state')
    def _compute_is_locked_scheduled(self):
        for rec in self:
            rec.is_locked_scheduled = rec.state in ['draft', 'pending_payment','completed', 'cancelled']

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def _format_time(self, float_time):
        hours = int(float_time)
        minutes = int(round((float_time - hours) * 60))
        return f"{hours:02d}:{minutes:02d}"

    def _get_mail_server(self):
        mail_server = self.env['ir.mail_server'].search([], limit=1, order='sequence asc')
        if not mail_server:
            _logger.error("EMAIL: No outgoing mail server configured")
            return None
        return mail_server

    def _send_email(self, subject, html_body, recipient_email):
        """Generic email sender using the configured mail server."""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        mail_server = self._get_mail_server()
        if not mail_server or not recipient_email:
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = mail_server.smtp_user
            msg['To'] = recipient_email
            msg.attach(MIMEText(html_body, 'html'))

            smtp = mail_server._connect__(
                host=mail_server.smtp_host,
                port=mail_server.smtp_port,
                user=mail_server.smtp_user,
                password=mail_server.smtp_pass,
                encryption=mail_server.smtp_encryption,
                smtp_debug=False,
            )
            with smtp:
                smtp.sendmail(mail_server.smtp_user, [recipient_email], msg.as_string())
            return True
        except Exception as e:
            _logger.error("EMAIL: Failed sending to %s: %s", recipient_email, str(e))
            return False

    # --------------------------------------------------
    # Email: Appointment Scheduled
    # --------------------------------------------------
    def _send_scheduled_email(self):
        for rec in self:
            if not rec.patient_id.email:
                _logger.warning("EMAIL: No email for patient %s", rec.patient_id.name)
                continue

            time_label = dict(rec._fields['visit_time'].selection).get(rec.visit_time, rec.visit_time)
            subject = f'Your Appointment is Scheduled - {rec.name}'
            html_body = f"""
            <div style="font-family: Arial, sans-serif; padding: 20px;">
                <p>Hello <strong>{rec.patient_id.name}</strong>,</p>
                <p>Your appointment has been <strong>scheduled</strong>.</p>
                <ul>
                    <li><strong>Visit Ref:</strong> {rec.name}</li>
                    <li><strong>Date:</strong> {rec.visit_date}</li>
                    <li><strong>Time:</strong> {time_label}</li>
                    <li><strong>Doctor:</strong> {rec.doctor_id.name}</li>
                    <li><strong>Payment Ref:</strong> {rec.payment_reference or 'N/A'}</li>
                </ul>
                <p>Thank you for choosing our clinic.</p>
            </div>
            """
            sent = rec._send_email(subject, html_body, rec.patient_id.email)
            if sent:
                _logger.info("EMAIL: Scheduled email sent to %s for %s", rec.patient_id.email, rec.name)

    # --------------------------------------------------
    # Email: Appointment Cancelled
    # --------------------------------------------------
    def _send_cancellation_email(self):
        for rec in self:
            if not rec.patient_id.email:
                continue
            time_label = dict(rec._fields['visit_time'].selection).get(rec.visit_time, rec.visit_time)
            subject = f'Your Appointment Has Been Cancelled - {rec.name}'
            html_body = f"""
            <div style="font-family: Arial, sans-serif; padding: 20px;">
                <p>Hello <strong>{rec.patient_id.name}</strong>,</p>
                <p>Your appointment has been <strong>cancelled</strong>.</p>
                <ul>
                    <li><strong>Visit Ref:</strong> {rec.name}</li>
                    <li><strong>Date:</strong> {rec.visit_date}</li>
                    <li><strong>Time:</strong> {time_label}</li>
                    <li><strong>Doctor:</strong> {rec.doctor_id.name}</li>
                </ul>
                <p>If you would like to book a new appointment, please visit our portal.</p>
                <p>
                    <a href="http://localhost:8069/my/appointments/new"
                       style="background:#007bff;color:#fff;padding:10px 20px;
                              text-decoration:none;border-radius:4px;">
                        Book New Appointment
                    </a>
                </p>
                <p>If you believe this was a mistake, please contact us.</p>
            </div>
            """
            sent = rec._send_email(subject, html_body, rec.patient_id.email)
            if sent:
                _logger.info("EMAIL: Cancellation email sent to %s for %s", rec.patient_id.email, rec.name)

    # --------------------------------------------------
    # Email: Past Date Reminder (rebook or cancel)
    # --------------------------------------------------
    def _send_past_date_email(self):
        for rec in self:
            if not rec.patient_id.email:
                continue

            time_label = dict(rec._fields['visit_time'].selection).get(rec.visit_time, rec.visit_time)
            subject = f'Action Required: Your Appointment Date Has Passed - {rec.name}'
            html_body = f"""
            <div style="font-family: Arial, sans-serif; padding: 20px;">
                <p>Hello <strong>{rec.patient_id.name}</strong>,</p>
                <p>
                    Your appointment <strong>{rec.name}</strong> was scheduled for
                    <strong>{rec.visit_date}</strong> at
                    <strong>{time_label}</strong>
                    with Dr. <strong>{rec.doctor_id.name}</strong>,
                    but the date has now passed.
                </p>
                <p>Please choose one of the following options:</p>
                <div style="margin: 20px 0;">
                    <a href="http://localhost:8069/my/appointments"
                       style="background:#28a745;color:#fff;padding:10px 20px;
                              text-decoration:none;border-radius:4px;margin-right:10px;">
                        &#128197; Rebook Appointment
                    </a>
                    <a href="http://localhost:8069/my/appointments/cancel/{rec.id}"
                       style="background:#dc3545;color:#fff;padding:10px 20px;
                              text-decoration:none;border-radius:4px;">
                        &#10005; Cancel Appointment
                    </a>
                </div>
                <p style="color:#888;font-size:13px;">
                    If you have already attended or resolved this, please ignore this email.
                </p>
            </div>
            """
            sent = rec._send_email(subject, html_body, rec.patient_id.email)
            if sent:
                rec.past_date_email_sent = True
                _logger.info("EMAIL: Past date email sent to %s for %s", rec.patient_id.email, rec.name)

    # --------------------------------------------------
    # Cron: Check for past-date appointments daily
    # --------------------------------------------------
    @api.model
    def _cron_check_past_appointments(self):
        today = datetime.date.today()
        past_visits = self.search([
            ('visit_date', '<', today),
            ('state', 'in', ['scheduled', 'pending_payment']),
            ('past_date_email_sent', '=', False),
        ])
        _logger.info("CRON: Found %d past-date appointments to notify", len(past_visits))
        past_visits._send_past_date_email()

    @api.model
    def _cron_cancel_unpaid_visits(self):
        """Cancel visits that have been pending payment for more than 30 minutes."""
        expiry = datetime.datetime.now() - datetime.timedelta(minutes=30)
        unpaid = self.search([
            ('state', '=', 'pending_payment'),
            ('create_date', '<', expiry),
        ])
        if unpaid:
            _logger.info("CRON: Auto-cancelling %d unpaid visits", len(unpaid))
            unpaid.write({'state': 'cancelled'})

    # --------------------------------------------------
    # ORM overrides
    # --------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New Visit') == 'New Visit':
                vals['name'] = self.env['ir.sequence'].next_by_code('patient.visit') or 'New Visit'
        return super().create(vals_list)

    @api.onchange('is_paid')
    def _onchange_is_paid(self):
        for rec in self:
            if rec.is_paid:
                if not rec.payment_reference:
                    rec.payment_reference = 'TOKEN-' + str(uuid.uuid4())[:8].upper()
            else:
                rec.payment_reference = False
                if rec.state == 'scheduled':
                    rec.state = 'pending_payment'

    def write(self, vals):
        is_doctor_only = (
            self.env.user.has_group('patients.group_patient_doctor') and
            not self.env.user.has_group('patients.group_patient_administrator')
        )

        if is_doctor_only:
            if 'patient_id' in vals:
                raise UserError("Doctors are not allowed to change the patient details.")
            for rec in self:
                if rec.doctor_id.id != self.env.user.id:
                    raise UserError("You can only edit visits assigned to you.")

        previously_not_scheduled = {rec.id for rec in self if rec.state != 'scheduled'}
        previously_not_cancelled = {rec.id for rec in self if rec.state != 'cancelled'}

        res = super().write(vals)

        # Auto-transition state based on is_paid
        if 'is_paid' in vals:
            for rec in self:
                if rec.is_paid:
                    token = rec.payment_reference or 'TOKEN-' + str(uuid.uuid4())[:8].upper()
                    if rec.state in ('draft', 'pending_payment'):
                        super(PatientVisit, rec).write({
                            'state': 'scheduled',
                            'payment_reference': token,
                        })
                    else:
                        super(PatientVisit, rec).write({'payment_reference': token})
                else:
                    if rec.state == 'scheduled':
                        super(PatientVisit, rec).write({
                            'state': 'pending_payment',
                            'payment_reference': False,
                        })

        # Send scheduled email to records that just became scheduled
        newly_scheduled = self.filtered(
            lambda r: r.state == 'scheduled' and r.id in previously_not_scheduled
        )
        if newly_scheduled:
            newly_scheduled._send_scheduled_email()

        # Send cancellation email to records that just became cancelled
        newly_cancelled = self.filtered(
            lambda r: r.state == 'cancelled' and r.id in previously_not_cancelled
        )
        if newly_cancelled:
            newly_cancelled._send_cancellation_email()

        return res

    def copy(self, default=None):
        is_doctor_only = (
            self.env.user.has_group('patients.group_patient_doctor') and
            not self.env.user.has_group('patients.group_patient_administrator')
        )
        if is_doctor_only and self.doctor_id.id != self.env.user.id:
            raise UserError("You cannot duplicate a visit assigned to another doctor.")
        return super().copy(default=default)

    # --------------------------------------------------
    # Header buttons
    # --------------------------------------------------
    def action_schedule(self):
        for rec in self:
            if not rec.is_paid:
                raise UserError("Please complete payment before scheduling.")
            if rec.state != 'scheduled':
                rec.write({'state': 'scheduled'})
            rec._send_scheduled_email()

    def action_complete(self):
        for rec in self:
            rec.write({'state': 'completed'})

    def action_cancel(self):
        for rec in self:
            if rec.state in ('completed', 'cancelled'):
                raise UserError("Cannot cancel a completed or already cancelled visit.")
            rec.write({'state': 'cancelled'})