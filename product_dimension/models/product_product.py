# -*- coding: utf-8 -*-
"""变体侧：尺寸（单位 + 长宽高）的真身在这里，原生 Volume 由它同步算出。

归属这么定的理由：Odoo 里 `volume` / `weight` 本来就是**变体级**字段（模板侧那两个只是
「单变体桥接」）。尺寸是体积的来源，放在同一层才不会出现「模板有尺寸、变体各自有体积」
这种错位 —— 多变体产品里每条变体各填各的尺寸，各自算各自的 Volume。
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

DIMENSION_FIELDS = (
    "dimension_unit",
    "dimension_length",
    "dimension_width",
    "dimension_height",
)
# 立方厘米 → 立方米
CM3_PER_M3 = 1_000_000.0


class ProductProduct(models.Model):
    _inherit = "product.product"

    dimension_unit = fields.Selection(
        string="Dimension Unit",
        selection=[
            ("cm", "Centimeters"),
            ("m", "Meters"),
        ],
        default="cm",
        required=True,
        help="Unit used for the length, width and height of this variant. "
             "The native Volume is always expressed in cubic meters.",
    )
    dimension_length = fields.Float(
        string="Length",
        default=0.0,
        digits=(10, 2),
        help="Length of this variant, in the selected dimension unit.",
    )
    dimension_width = fields.Float(
        string="Width",
        default=0.0,
        digits=(10, 2),
        help="Width of this variant, in the selected dimension unit.",
    )
    dimension_height = fields.Float(
        string="Height",
        default=0.0,
        digits=(10, 2),
        help="Height of this variant, in the selected dimension unit.",
    )

    # ------------------------------------------------------------------
    # 尺寸 → 原生 Volume（表单与后台两条路都覆盖）
    # ------------------------------------------------------------------

    @api.onchange(*DIMENSION_FIELDS)
    def _onchange_dimension_fields(self):
        """表单里改尺寸时实时刷新 Volume，避免保存前后数值不一致。"""
        self._sync_volume_from_dimensions()

    @api.model_create_multi
    def create(self, vals_list):
        variants = super().create(vals_list)
        for vals, variant in zip(vals_list, variants):
            if any(name in vals for name in DIMENSION_FIELDS):
                variant._sync_volume_from_dimensions()
        return variants

    def write(self, vals):
        res = super().write(vals)
        if any(name in vals for name in DIMENSION_FIELDS):
            self._sync_volume_from_dimensions()
        return res

    def _sync_volume_from_dimensions(self):
        """按本变体的尺寸重算原生 `volume`（立方米）；尺寸不齐时归 0。"""
        for variant in self:
            length = variant.dimension_length or 0.0
            width = variant.dimension_width or 0.0
            height = variant.dimension_height or 0.0
            if not (length > 0 and width > 0 and height > 0):
                variant.volume = 0.0
                continue
            factor = CM3_PER_M3 if variant.dimension_unit == "cm" else 1.0
            variant.volume = length * width * height / factor

    # ------------------------------------------------------------------
    # 校验
    # ------------------------------------------------------------------

    @api.constrains(*DIMENSION_FIELDS[1:])
    def _check_dimension_values(self):
        """尺寸不允许为负：负体积会让运费与装载计算得出无意义的结果。"""
        for variant in self:
            for field_name, label in (
                ("dimension_length", _("Length")),
                ("dimension_width", _("Width")),
                ("dimension_height", _("Height")),
            ):
                value = variant[field_name] or 0.0
                if value < 0:
                    raise ValidationError(_(
                        "The %(label)s of %(product)s cannot be negative (%(value)s).",
                        label=label,
                        product=variant.display_name,
                        value=value,
                    ))
