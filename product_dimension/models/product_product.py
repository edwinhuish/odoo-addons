# -*- coding: utf-8 -*-
"""变体侧：尺寸（单位 + 长宽高）的真身在这里，原生 Volume 由它同步算出。

归属这么定的理由：Odoo 里 `volume` / `weight` 本来就是**变体级**字段（模板侧那两个只是
「单变体桥接」）。尺寸是体积的来源，放在同一层才不会出现「模板有尺寸、变体各自有体积」
这种错位 —— 多变体产品里每条变体各填各的尺寸，各自算各自的 Volume。
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

DIMENSION_UNIT_FIELD = "dimension_unit"
DIMENSION_FIELDS = (
    DIMENSION_UNIT_FIELD,
    "dimension_length",
    "dimension_width",
    "dimension_height",
)
# 立方厘米 → 立方米
CM3_PER_M3 = 1_000_000.0


def volume_from_dimensions(dimension_unit, length, width, height):
    """按尺寸算体积（立方米）；长宽高任一为 0 时给 0（尺寸不齐则体积不成立）。

    **这是全模块唯一的换算口径**：变体侧的写库同步（`_sync_volume_from_dimensions()`）与
    模板侧的产品表单预览（`product.template._onchange_dimension_fields()`）都调它，
    免得两处各算一套、慢慢漂移。厘米按 ``cm³ / 1 000 000`` 换算，米直接相乘。
    """
    length = length or 0.0
    width = width or 0.0
    height = height or 0.0
    if not (length > 0 and width > 0 and height > 0):
        return 0.0
    factor = CM3_PER_M3 if dimension_unit == "cm" else 1.0
    return length * width * height / factor


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
    # 尺寸 → 原生 Volume（界面上由前端算，后端只兜底）
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        variants = super().create(vals_list)
        for vals, variant in zip(vals_list, variants):
            if variant._should_sync_volume(vals):
                variant._sync_volume_from_dimensions()
        return variants

    def write(self, vals):
        res = super().write(vals)
        if self._should_sync_volume(vals):
            self._sync_volume_from_dimensions()
        return res

    def _should_sync_volume(self, vals):
        """要不要由后端重算 `volume`。

        界面上的体积由前端算好并随表单一起提交（`static/src/js/dimension_volume.js`），
        所以**写入值里带了 `volume` 就不再算**：同一件事不重复做两遍，也免得两处口径分歧。
        只有「写了尺寸、没带体积」的路径才兜底 —— 导入 / API / RPC / 其它模块直接写尺寸
        （例如 `product_variant_conversion` 按谱系继承）全走这条，漏了它这些路径的体积
        就会停在旧值上。
        """
        if "volume" in vals:
            return False
        return any(name in vals for name in DIMENSION_FIELDS)

    def _sync_volume_from_dimensions(self):
        """按本变体的尺寸重算原生 `volume`（立方米）；尺寸不齐时归 0。"""
        for variant in self:
            variant.volume = volume_from_dimensions(
                variant.dimension_unit,
                variant.dimension_length,
                variant.dimension_width,
                variant.dimension_height,
            )

    # ------------------------------------------------------------------
    # 校验
    # ------------------------------------------------------------------

    @api.constrains(*DIMENSION_FIELDS[1:])
    def _check_dimension_values(self):
        """尺寸不允许为负：负体积会让运费与装载计算得出无意义的结果。"""
        labels = (_("Length"), _("Width"), _("Height"))
        for variant in self:
            for field_name, label in zip(DIMENSION_FIELDS[1:], labels):
                value = variant[field_name] or 0.0
                if value < 0:
                    raise ValidationError(_(
                        "The %(label)s of %(product)s cannot be negative (%(value)s).",
                        label=label,
                        product=variant.display_name,
                        value=value,
                    ))
