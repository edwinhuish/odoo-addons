# -*- coding: utf-8 -*-
"""product.product 扩展：把「变体来源」落到可搜索字段上。

谱系明细在 ``product.variant.lineage``（台账），这里是刻意冗余出来的两个字段：
它们有索引、可直接进列表 / 搜索 / 其它模块的视图，让「下单、查询、管理」时能一眼看到
变体来自哪次转换、派生自哪个原变体。
"""

from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    variant_conversion_id = fields.Many2one(
        comodel_name="product.variant.conversion",
        string="Variant Conversion",
        readonly=True,
        copy=False,
        index=True,
        ondelete="set null",
        help="Conversion that added attributes to this product. Set on the variants that existed "
             "before the conversion and on the variants it created.",
    )
    variant_origin_id = fields.Many2one(
        comodel_name="product.product",
        string="Derived From",
        readonly=True,
        copy=False,
        index=True,
        ondelete="set null",
        help="Original variant this variant was created from during a conversion: the record that "
             "kept the stock, the orders and the invoices. Empty for the variants that existed "
             "before the conversion (they are the origins themselves) and for manually created ones.",
    )
