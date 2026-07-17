from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    department_id = fields.Many2one(
        'doctor.department',
        string='Department',
    )
    is_doctor = fields.Boolean(string="Is Doctor")