from odoo import fields, models, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_patient = fields.Boolean(string="Is Patient", default=True)
    visit_ids = fields.One2many(
        'patient.visit',
        'patient_id',
        string='Visits'
    )

    visit_count = fields.Integer(
        string='Visit Count',
        compute='_compute_visit_count'
    )
    payment_ids = fields.One2many('account.payment', 'visit_id', string='Payments')
    payment_count = fields.Integer(string='Payment Count', compute='_compute_payment_count')

    blood_group = fields.Selection([
        ('a+', 'A+'),
        ('a-', 'A-'),
        ('b+', 'B+'),
        ('b-', 'B-'),
        ('ab+', 'AB+'),
        ('ab-', 'AB-'),
        ('o+', 'O+'),
        ('o-', 'O-'),
    ], string='Blood Group')

    allergies = fields.Text(
        string='Allergies',
        help='List any known allergies (medications, food, environmental, etc.)'
    )

    chronic_conditions = fields.Text(
        string='Chronic Conditions',
        help='List any chronic or long-term medical conditions'
    )

    current_medications = fields.Text(
        string='Current Medications',
        help='List any medications the patient is currently taking'
    )

    medical_notes = fields.Text(
        string='Additional Medical Notes',
        help='Any other relevant medical history or notes'
    )

    def _compute_payment_count(self):
        for rec in self:
            rec.payment_count = len(rec.payment_ids)

    @api.depends('visit_ids')
    def _compute_visit_count(self):
        for record in self:
            record.visit_count = len(record.visit_ids)


    def action_view_visit(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Patient Visits',
            'res_model': 'patient.visit',
            'view_mode': 'tree,form',
            'domain': [('patient_id', '=', self.id)],
            'context': {'default_patient_id': self.id}
        }

    def action_view_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payments',
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('visit_id', '=', self.id)],
            'context': {
                'default_visit_id': self.id,
            }
        }