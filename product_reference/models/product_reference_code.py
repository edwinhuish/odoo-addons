# -*- coding: utf-8 -*-
"""产品参考号明细模型。

一个产品可挂多条参考号（客户参考号 / 工厂参考号 / 别名）。
参考号本身是独立模型，有两种归属（二选一）：
- 产品级共享参考号：挂在 ``product.template``（``product_tmpl_id``），在产品表单维护
- 变体级参考号：挂在 ``product.product``（``product_id``），在变体表单维护，
  与产品级共享参考号完全独立（多变体产品的参考号不共用）

搜索能力由各自主人的冗余可存储字段（``product.template.reference_code_index`` /
``product.product.variant_reference_code_index``）与 ``_search_display_name`` 扩展
共同保证，详见 ``product_template.py`` / ``product_product.py``。
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductReferenceCode(models.Model):
    """产品参考号明细。

    设计要点：
    - 归属二选一：产品级共享（``product_tmpl_id``）或变体级（``product_id``），
      由 ``_check_single_owner`` 约束；多变体产品的参考号不共用，各变体维护各自的。
    - 同一主人内参考号不可重复（``UNIQUE(product_tmpl_id, reference_code)`` /
      ``UNIQUE(product_id, reference_code)``）；不同主人间允许同参考号，
      搜索命中时会显示「产品名（命中参考号：xxx）」便于区分。
    - 冗余搜索字段按主人分别拼接（产品 → ``reference_code_index``，
      变体 → ``variant_reference_code_index``），均配 trigram 索引，
      使列表搜索框、Many2one 下拉、快速搜索均可按参考号命中，无需 Python 侧全表过滤。
    - 删除产品 / 变体时参考号行随主人级联删除（``ondelete='cascade'``）。
    """

    _name = "product.reference.code"
    _description = "Product Reference"
    _order = "sequence, product_tmpl_id, id"
    _rec_name = "reference_code"

    # ------------------------------------------------------------------
    # 字段定义
    # ------------------------------------------------------------------

    reference_code = fields.Char(
        string="Reference",
        required=True,
        index=True,
        help="Reference code of the product. It cannot be repeated inside the "
             "same product, but the same code may be used by other products; "
             "when a search hits a reference, the result shows \"Product "
             "(Matching reference: xxx)\" to tell them apart.",
    )
    reference_type = fields.Selection(
        string="Reference Type",
        selection=[
            ("customer", "Customer Reference"),
            ("factory", "Factory Reference"),
            ("alias", "Alias"),
        ],
        default="customer",
        index=True,
        help="Purpose of this reference: customer references are used on "
             "outgoing documents, factory references for purchasing, aliases "
             "for historical or colloquial names.",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower values come first; both the list and the One2many lines are "
             "ordered by this value.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to disable a reference without deleting it, so history is "
             "kept.",
    )
    note = fields.Char(
        string="Note",
        help="Short description of this reference (customer, version, effective "
             "date, ...).",
    )

    product_tmpl_id = fields.Many2one(
        string="Product",
        comodel_name="product.template",
        ondelete="cascade",
        index=True,
        help="Product (shared references) this reference belongs to. Either this field or "
             "'Product Variant' must be set: shared references are maintained on the product "
             "form and are removed together with the product.",
    )
    product_id = fields.Many2one(
        string="Product Variant",
        comodel_name="product.product",
        ondelete="cascade",
        index=True,
        help="Product variant this reference belongs to (variant references, independent from "
             "the shared product references). Either this field or 'Product' must be set; the "
             "reference is removed together with the variant.",
    )

    # ------------------------------------------------------------------
    # 约束：必须且只能归属一个主人（产品 或 产品变体）；同一主人内参考号不可重复
    # ------------------------------------------------------------------

    _reference_code_unique_per_template = models.Constraint(
        "UNIQUE(product_tmpl_id, reference_code)",
        "Reference codes must be unique within the same product.",
    )
    _reference_code_unique_per_variant = models.Constraint(
        "UNIQUE(product_id, reference_code)",
        "Reference codes must be unique within the same product variant.",
    )

    @api.constrains("product_tmpl_id", "product_id")
    def _check_single_owner(self):
        """A reference belongs either to a product (shared) or to a product variant.

        Variant references are stored independently (only ``product_id``) so that the
        shared product references ``product_tmpl_id`` are never mixed with them; a
        reference without owner or with both owners is rejected with a readable error.
        """
        for record in self:
            if not record.product_tmpl_id and not record.product_id:
                raise ValidationError(_(
                    "A reference must belong either to a product (shared references) or to a "
                    "product variant (variant references)."
                ))
            if record.product_tmpl_id and record.product_id:
                raise ValidationError(_(
                    "A reference cannot belong to both a product and a product variant: choose "
                    "either the shared product references or the variant references."
                ))

    @api.constrains("reference_code", "product_tmpl_id", "product_id")
    def _check_reference_code_unique_per_owner(self):
        """同一主人的参考号不可重复：产品内 / 变体内分别去重，提示带出具体值与归属。

        数据库层已有 ``UNIQUE(product_tmpl_id, reference_code)`` 与
        ``UNIQUE(product_id, reference_code)`` 兜底，这里提供更友好的错误信息。
        """
        for record in self:
            if not record.reference_code:
                continue
            if record.product_id:
                domain = [
                    ("product_id", "=", record.product_id.id),
                    ("reference_code", "=", record.reference_code),
                    ("id", "!=", record.id),
                ]
                owner = record.product_id.display_name
            elif record.product_tmpl_id:
                domain = [
                    ("product_tmpl_id", "=", record.product_tmpl_id.id),
                    ("reference_code", "=", record.reference_code),
                    ("id", "!=", record.id),
                ]
                owner = record.product_tmpl_id.display_name
            else:
                # 归属校验由 _check_single_owner 负责，此处避免重复报错
                continue
            duplicate = self.sudo().search(domain, limit=1)
            if duplicate:
                raise ValidationError(_(
                    'The reference "%(code)s" already exists for product '
                    '"%(product)s". Reference codes must be unique within the '
                    "same product.",
                    code=record.reference_code,
                    product=owner,
                ))

    # ------------------------------------------------------------------
    # 写入：维护产品的冗余可搜索字段
    # ------------------------------------------------------------------

    def _sync_owners_index(self):
        """参考号增删改后，把所有参考号拼接写入所属主人的冗余搜索字段。

        这是搜索能力的核心：列表搜索框 / Many2one 下拉 / 快速搜索都不直接查
        ``product.reference.code``，而是走冗余字段 + ``_search_display_name``：
        - 产品级共享参考号 → ``product.template.reference_code_index``
        - 变体级参考号 → ``product.product.variant_reference_code_index``
        拼接逻辑分别实现在 ``product.template._sync_reference_index`` 与
        ``product.product._sync_variant_reference_index``（删除行后仍需按剩余行重算，
        只能在主人侧取数）。
        """
        self.mapped("product_tmpl_id")._sync_reference_index()
        self.mapped("product_id")._sync_variant_reference_index()

    # ------------------------------------------------------------------
    # create / write / unlink：触发冗余字段同步
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_owners_index()
        return records

    def write(self, vals):
        res = super().write(vals)
        # 仅当影响拼接内容的字段变动时才同步，避免无谓写入
        if any(k in vals for k in (
            "reference_code", "product_tmpl_id", "product_id", "active", "sequence",
        )):
            self._sync_owners_index()
        return res

    def unlink(self):
        templates = self.mapped("product_tmpl_id")
        variants = self.mapped("product_id")
        res = super().unlink()
        templates._sync_reference_index()
        variants._sync_variant_reference_index()
        return res
