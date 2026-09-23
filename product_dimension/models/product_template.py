# -*- coding: utf-8 -*-
"""模板侧：只做「单变体桥接」，与原生 `volume` / `weight` 完全同构。

- **读**：产品只有一条变体时给那条变体的值；有多条变体时给空值（0 / 未设置）——
  这正是原生 `volume` 在多变体产品上的表现；
- **写**：只有一条变体时写回那条变体；多变体时什么都不做（原生 `_set_product_variant_field`
  的同款语义，而界面上这些字段在多变体产品里本来就是隐藏的，用户碰不到）。

真身在 `product.product`（见 `product_product.py`），这里不存第二份真数据：
模板字段是 `store=True` 的镜像，随变体取值变化重算，因此可以像原生 `volume` 一样被搜索 / 分组。
"""

from odoo import api, fields, models

from .product_product import DEFAULT_DIMENSION_UNIT, DIMENSION_UNIT_FIELD

# 多变体时读出来的空值：Selection 用 False，Float 用 0.0
EMPTY_DIMENSION_VALUE = {DIMENSION_UNIT_FIELD: False}


class ProductTemplate(models.Model):
    _inherit = "product.template"

    dimension_unit = fields.Selection(
        string="Dimension Unit",
        selection=[
            ("cm", "Centimeters"),
            ("m", "Meters"),
        ],
        # 镜像字段也要自带默认值：全新产品的表单是「先有表单、后有变体」，而 `default_get()`
        # 只认 context / ir.default / field.default，**不会触发 compute** —— 没有这条，
        # 新建产品时「尺寸单位」下拉框默认是空的（变体侧有 default 所以它不空）。
        # 值取自真身文件里的同一个常量，两处不会漂移。
        default=DEFAULT_DIMENSION_UNIT,
        compute="_compute_dimension_unit",
        inverse="_set_dimension_unit",
        store=True,
        help="Dimension unit of the single variant. It is disabled as soon as the product has "
             "several variants (same behaviour as the native Volume field): set the unit on each "
             "variant instead.",
    )
    dimension_length = fields.Float(
        string="Length",
        digits=(10, 2),
        compute="_compute_dimension_length",
        inverse="_set_dimension_length",
        store=True,
        help="Length of the single variant, in the selected dimension unit.",
    )
    dimension_width = fields.Float(
        string="Width",
        digits=(10, 2),
        compute="_compute_dimension_width",
        inverse="_set_dimension_width",
        store=True,
        help="Width of the single variant, in the selected dimension unit.",
    )
    dimension_height = fields.Float(
        string="Height",
        digits=(10, 2),
        compute="_compute_dimension_height",
        inverse="_set_dimension_height",
        store=True,
        help="Height of the single variant, in the selected dimension unit.",
    )

    # ------------------------------------------------------------------
    # 读：单变体镜像
    # ------------------------------------------------------------------

    @api.depends("product_variant_ids.dimension_unit")
    def _compute_dimension_unit(self):
        for template in self:
            template.dimension_unit = template._get_single_variant_dimension(DIMENSION_UNIT_FIELD)

    @api.depends("product_variant_ids.dimension_length")
    def _compute_dimension_length(self):
        for template in self:
            template.dimension_length = template._get_single_variant_dimension("dimension_length")

    @api.depends("product_variant_ids.dimension_width")
    def _compute_dimension_width(self):
        for template in self:
            template.dimension_width = template._get_single_variant_dimension("dimension_width")

    @api.depends("product_variant_ids.dimension_height")
    def _compute_dimension_height(self):
        for template in self:
            template.dimension_height = template._get_single_variant_dimension("dimension_height")

    def _get_single_variant_dimension(self, field_name):
        """单变体时取这条变体的值，多变体时给空值（与原生 volume / weight 同构）。"""
        self.ensure_one()
        if len(self.product_variant_ids) == 1:
            return self.product_variant_ids[field_name]
        return EMPTY_DIMENSION_VALUE.get(field_name, 0.0)

    # ------------------------------------------------------------------
    # 写：单变体落回变体
    # ------------------------------------------------------------------

    def _set_dimension_unit(self):
        self._set_dimension_to_variant(DIMENSION_UNIT_FIELD)

    def _set_dimension_length(self):
        self._set_dimension_to_variant("dimension_length")

    def _set_dimension_width(self):
        self._set_dimension_to_variant("dimension_width")

    def _set_dimension_height(self):
        self._set_dimension_to_variant("dimension_height")

    def _set_dimension_to_variant(self, field_name):
        """单变体时把模板上的值写回那条变体；多变体时不动（原生同款语义）。"""
        for template in self:
            if len(template.product_variant_ids) == 1:
                template.product_variant_ids.write({field_name: template[field_name]})
