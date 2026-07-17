from odoo import fields, models, api
from odoo.exceptions import ValidationError


class PatientPrescriptionLine(models.Model):
    _name = 'patient.prescription.line'
    _description = 'Patient Prescription Line'

    visit_id = fields.Many2one('patient.visit', string='Visit_id', required=True, ondelete='cascade')
    medicine_id = fields.Many2one('product.product', string='Medicine_id', required=True)
    dosage = fields.Float(string='Dosage (mg)', digits=(6, 2))
    instructions = fields.Text(string='Instructions')

    @api.constrains('dosage')
    def _check_dosage(self):
        for rec in self:
            if rec.dosage <= 0:
                raise ValidationError(
                    f"Dosage must be a positive value for '{rec.medicine_id.name}'."
                )
            if rec.dosage > 10000:
                raise ValidationError(
                    f"Dosage value {rec.dosage}mg is unrealistically large for "
                    f"'{rec.medicine_id.name}'. Maximum allowed is 10,000mg."
                )

    @api.constrains('visit_id', 'medicine_id')
    def _check_duplicate_medicine(self):
        for rec in self:
            duplicate = self.search([
                ('visit_id', '=', rec.visit_id.id),
                ('medicine_id', '=', rec.medicine_id.id),
                ('id', '!=', rec.id),
            ])
            if duplicate:
                raise ValidationError(
                    f"Medicine '{rec.medicine_id.name}' is already prescribed "
                    f"for this visit. Please update the existing line instead."
                )