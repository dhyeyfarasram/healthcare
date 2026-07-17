from odoo import fields, models


class DoctorDepartment(models.Model):
    _name = 'doctor.department'
    _description = 'Doctor Department'
    _order = 'name'

    name = fields.Char(string='Department Name', required=True)
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)

    doctor_ids = fields.One2many(
        'res.users',
        'department_id',
        string='Doctors'
    )
    doctor_count = fields.Integer(
        string='Doctors',
        compute='_compute_doctor_count'
    )

    def _compute_doctor_count(self):
        for rec in self:
            rec.doctor_count = len(rec.doctor_ids)