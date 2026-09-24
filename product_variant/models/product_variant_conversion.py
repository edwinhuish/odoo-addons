# -*- coding: utf-8 -*-
"""转换记录与变体谱系。

- ``product.variant.conversion``：一次转换的台账（谁、什么时候、给产品加了哪些属性、变体数怎么变）。
- ``product.variant.lineage``：一条「结果变体 ← 原变体」的谱系行，其中 ``is_kept`` 标记
  该结果变体是否就是原来那条 ``product.product`` 记录（保留下来的默认/原变体）。

``product.product`` 上另有可搜索的 ``variant_conversion_id`` / ``variant_origin_id``
（由转换过程写入），用于在下单、查询、管理时直接按「来自哪次转换 / 来自哪个原变体」筛选。
"""

from odoo import api, fields, models


class ProductVariantConversion(models.Model):
    _name = "product.variant.conversion"
    # 模型描述刻意与模块名区分：模块名要进「应用」列表（英文 Product Variant Conversion），
    # 两者同字面会撞成同一个 po msgid，见模块 AGENTS.md → L2 P2
    _description = "Variant Conversion Log"
    _rec_name = "product_tmpl_id"
    _order = "create_date desc, id desc"

    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Product",
        required=True,
        readonly=True,
        ondelete="cascade",
        index=True,
    )
    product_variant_count_before = fields.Integer(
        string="Variants Before",
        readonly=True,
        help="Number of variants the product had before the conversion.",
    )
    product_variant_count_after = fields.Integer(
        string="Variants After",
        readonly=True,
        help="Number of variants the product had once the conversion was applied.",
    )
    new_variant_count = fields.Integer(
        string="New Variants",
        readonly=True,
        help="Number of variants created by the conversion; every variant that existed before is kept as is.",
    )
    added_attribute_ids = fields.Many2many(
        comodel_name="product.attribute",
        string="Added Attributes",
        readonly=True,
        help="Attributes that were not configured on the product before this conversion.",
    )
    share_vendor_prices = fields.Boolean(
        string="Vendor Prices Shared",
        readonly=True,
        help="Whether the vendor prices of the original variants were shared with all the variants of the product.",
    )
    inherit_variant_data = fields.Boolean(
        string="Variant Data Inherited",
        readonly=True,
        help="Whether the variants created by this conversion inherited the cost, the volume and the weight of the "
             "variant they derive from. Configure it with the system parameter "
             "product_variant.inherit_variant_data.",
    )
    separate_variant_prices = fields.Boolean(
        string="Variant Prices Separated",
        readonly=True,
        help="Whether the vendor prices and the pricelist rules of this product were spread over its variants, so "
             "that every variant can be priced on its own (changing one variant does not touch the others). "
             "Configure it with the system parameter product_variant.separate_variant_prices.",
    )
    lineage_ids = fields.One2many(
        comodel_name="product.variant.lineage",
        inverse_name="conversion_id",
        string="Variant Lineage",
        readonly=True,
        help="One line per variant that took part in the conversion: which variant it was before and which combination it carries now.",
    )


class ProductVariantLineage(models.Model):
    _name = "product.variant.lineage"
    _description = "Product Variant Lineage"
    _rec_name = "result_variant_id"
    _order = "product_tmpl_id, id"

    conversion_id = fields.Many2one(
        comodel_name="product.variant.conversion",
        string="Conversion",
        required=True,
        readonly=True,
        ondelete="cascade",
        index=True,
    )
    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Product",
        required=True,
        readonly=True,
        ondelete="cascade",
        index=True,
    )
    origin_variant_id = fields.Many2one(
        comodel_name="product.product",
        string="Original Variant",
        readonly=True,
        ondelete="cascade",
        index=True,
        help="Variant that carried the stock, the orders and the invoices before the conversion. Left empty when the conversion could not point at a single original variant.",
    )
    result_variant_id = fields.Many2one(
        comodel_name="product.product",
        string="Resulting Variant",
        required=True,
        readonly=True,
        ondelete="cascade",
        index=True,
        help="Variant that exists after the conversion for this combination.",
    )
    is_kept = fields.Boolean(
        string="Original Record Kept",
        readonly=True,
        help="Set when the resulting variant is the very same product variant record as the original one: no record was created nor deleted for this combination.",
    )
    origin_summary = fields.Char(
        string="Combination Before",
        readonly=True,
        help="Attribute values of the original variant before the conversion.",
    )
    result_summary = fields.Char(
        string="Combination After",
        readonly=True,
        help="Attribute values of the resulting variant after the conversion.",
    )
    added_value_ids = fields.Many2many(
        comodel_name="product.template.attribute.value",
        string="Values Added",
        readonly=True,
        help="Values that the resulting variant carries and the original variant did not: what the conversion added for this variant.",
    )

    # ------------------------------------------------------------------
    # 结果变体上的变体级属性（只读关联展示，不落库）
    #
    # 参考号 / 条码 / 成本的真身在变体上（见模块 README →「属性归属审计」）：
    # 转换不搬任何数据，所以这里只是把它们「关联显示」出来，让用户在转换后
    # 一眼看到每条结果变体（尤其是保留了原记录的那条）到底带着什么值。
    # 非存储 related → 不新增数据库列、不需要迁移。
    # ------------------------------------------------------------------
    result_default_code = fields.Char(
        string="Reference (After)",
        related="result_variant_id.default_code",
        readonly=True,
        help="Internal reference of the resulting variant. It belongs to the variant: the "
             "conversion never changes it.",
    )
    result_barcode = fields.Char(
        string="Barcode (After)",
        related="result_variant_id.barcode",
        readonly=True,
        help="Barcode of the resulting variant. It belongs to the variant: the conversion never changes it.",
    )
    result_standard_price = fields.Float(
        string="Cost (After)",
        related="result_variant_id.standard_price",
        readonly=True,
        groups="base.group_user",
        help="Cost of the resulting variant. It belongs to the variant: the conversion never changes it.",
    )

    @api.depends("origin_variant_id", "result_variant_id")
    def _compute_display_name(self):
        for lineage in self:
            lineage.display_name = "%s -> %s" % (
                lineage.origin_variant_id.display_name or "-",
                lineage.result_variant_id.display_name or "-",
            )
