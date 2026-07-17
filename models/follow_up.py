from odoo import fields, models, api


class PatientFollowup(models.Model):
    _name = 'patient.followup'
    _description = 'Patient Follow-up'
    _order = 'followup_date asc'

    visit_id = fields.Many2one(
        'patient.visit',
        string='Visit',
        required=True,
        ondelete='cascade'
    )
    followup_date = fields.Date(string='Follow-up Date', required=True)
    notes = fields.Text(string='Notes')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='pending', required=True)
    doctor_id = fields.Many2one(
        related='visit_id.doctor_id',
        string='Doctor',
        store=True,
        readonly=True
    )
    patient_id = fields.Many2one(
        related='visit_id.patient_id',
        string='Patient',
        store=True,
        readonly=True
    )
