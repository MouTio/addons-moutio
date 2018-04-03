# -*- coding: utf-8 -*-

from openerp import api
from openerp import models, fields
from openerp.exceptions import ValidationError


class ProductTemplateExtend(models.Model):
    _inherit = ['product.template']

    default_code = fields.Char(related='product_variant_ids.default_code', string='Internal Reference')

    @api.one
    @api.constrains('default_code')
    def _check_unique_default_code_constraint(self):
        if self.default_code is not False and len(self.search([('default_code', '=', self.default_code)])) > 1:
            # raise ValidationError("The same 'default_code' exists in another product.")
            raise ValidationError("Ya existe un producto con esa referencia interna.")

    @api.onchange('categ_id')
    def set_default_code_of_categ_id(self):
        if self.categ_id.sequence_id:
            seq_id = self.categ_id.sequence_id
            next_char = seq_id.get_next_char(self.categ_id.sequence_id.number_next)
            while self.search([('default_code', '=', next_char), ('id', '!=', self._origin.id)]).exists():
                # It exists already. Get next value
                next_char = self.categ_id.sequence_id._next()  # Value of sequence increments here
            self.default_code = next_char


class ProductCategoryExtend(models.Model):
    _inherit = ['product.category']

    sequence_id = fields.Many2one('ir.sequence', 'Secuencia', required=False, copy=False, help="Secuencia asociada.")
