# -*- coding: utf-8 -*-
"""扩展 product.template，增加外贸常用的装箱与纸箱尺寸字段。"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # ------------------------------------------------------------------
    # 字段定义
    # ------------------------------------------------------------------

    carton_qty_per_carton = fields.Integer(
        string="Units per Carton",
        default=0,
        help="Number of product units packed in one carton.",
    )
    carton_dimension_unit = fields.Selection(
        string="Dimension Unit",
        selection=[
            ("cm", "Centimeters"),
            ("m", "Meters"),
        ],
        default="cm",
        required=True,
        help="Unit used for carton length, width and height. CBM is always "
             "calculated in cubic meters.",
    )
    carton_length = fields.Float(
        string="Length",
        default=0.0,
        digits=(10, 2),
        help="Carton length in the selected dimension unit.",
    )
    carton_width = fields.Float(
        string="Width",
        default=0.0,
        digits=(10, 2),
        help="Carton width in the selected dimension unit.",
    )
    carton_height = fields.Float(
        string="Height",
        default=0.0,
        digits=(10, 2),
        help="Carton height in the selected dimension unit.",
    )
    carton_gross_weight = fields.Float(
        string="Gross Weight",
        default=0.0,
        digits=(10, 3),
        help="Carton gross weight in kilograms.",
    )
    carton_net_weight = fields.Float(
        string="Net Weight",
        default=0.0,
        digits=(10, 3),
        help="Carton net weight in kilograms.",
    )
    carton_cbm = fields.Float(
        string="CBM",
        compute="_compute_carton_cbm",
        store=True,
        digits=(12, 6),
        help="Carton cubic meters, automatically calculated from dimensions.",
    )
    carton_dimension_spec = fields.Char(
        string="Carton Dimensions",
        compute="_compute_carton_dimension_spec",
        store=True,
        help="Human-readable carton dimensions, e.g. 50 x 40 x 30 cm.",
    )

    # ------------------------------------------------------------------
    # 计算字段
    # ------------------------------------------------------------------

    @api.depends(
        "carton_length", "carton_width", "carton_height", "carton_dimension_unit",
    )
    def _compute_carton_cbm(self):
        """按所选尺寸单位把长宽高换算成立方米（CBM）。"""
        for tmpl in self:
            length = tmpl.carton_length or 0.0
            width = tmpl.carton_width or 0.0
            height = tmpl.carton_height or 0.0
            if not (length > 0 and width > 0 and height > 0):
                tmpl.carton_cbm = 0.0
                continue

            # 厘米 → 米：除以 1,000,000；米直接相乘。
            factor = 1_000_000.0 if tmpl.carton_dimension_unit == "cm" else 1.0
            tmpl.carton_cbm = length * width * height / factor

    @api.depends(
        "carton_length", "carton_width", "carton_height", "carton_dimension_unit",
    )
    def _compute_carton_dimension_spec(self):
        """生成可读的尺寸规格文本，如 "50 x 40 x 30 cm"。"""
        for tmpl in self:
            length = tmpl.carton_length or 0.0
            width = tmpl.carton_width or 0.0
            height = tmpl.carton_height or 0.0
            unit = tmpl.carton_dimension_unit or ""
            if length or width or height:
                tmpl.carton_dimension_spec = f"{length:g} x {width:g} x {height:g} {unit}"
            else:
                tmpl.carton_dimension_spec = False

    # ------------------------------------------------------------------
    # 校验
    # ------------------------------------------------------------------

    @api.constrains(
        "carton_qty_per_carton",
        "carton_length", "carton_width", "carton_height",
        "carton_gross_weight", "carton_net_weight",
    )
    def _check_carton_values(self):
        """保证装箱数、尺寸、重量为非负数，且净重不超过毛重。"""
        for tmpl in self:
            qty = tmpl.carton_qty_per_carton or 0
            if qty < 0:
                raise ValidationError(_(
                    "Units per carton cannot be negative (%(qty)s).",
                    qty=qty,
                ))

            length = tmpl.carton_length or 0.0
            width = tmpl.carton_width or 0.0
            height = tmpl.carton_height or 0.0
            if length < 0 or width < 0 or height < 0:
                raise ValidationError(_(
                    "Carton dimensions cannot be negative "
                    "(length=%(length)s, width=%(width)s, height=%(height)s).",
                    length=length,
                    width=width,
                    height=height,
                ))

            gross = tmpl.carton_gross_weight or 0.0
            net = tmpl.carton_net_weight or 0.0
            if gross < 0 or net < 0:
                raise ValidationError(_(
                    "Carton weights cannot be negative "
                    "(gross=%(gross)s, net=%(net)s).",
                    gross=gross,
                    net=net,
                ))
            if gross > 0 and net > gross:
                raise ValidationError(_(
                    "Net weight (%(net)s kg) cannot exceed gross weight "
                    "(%(gross)s kg).",
                    net=net,
                    gross=gross,
                ))
