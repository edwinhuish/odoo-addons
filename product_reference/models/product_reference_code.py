# -*- coding: utf-8 -*-
"""产品参考号明细模型。

一个产品可挂多条参考号（内部参考 / 客户参考号 / 工厂参考号 / 别名）。
参考号本身是独立模型，通过 One2many 挂在 product.template 上。
搜索能力由 product.template 侧的冗余可存储字段 ``reference_code_index`` 与
``_search_display_name`` 扩展共同保证，详见 ``product_template.py``。
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductReferenceCode(models.Model):
    """产品参考号明细。

    设计要点：
    - 同一产品内参考号不可重复（``reference_code_unique_per_template``）；
      不同产品间允许同参考号，但搜索命中时会显示「产品名（命中参考号：xxx）」便于区分。
    - ``reference_code_index`` 冗余存储到产品模板上，并配 trigram 索引，
      使列表搜索框、Many2one 下拉、快速搜索均可按参考号命中，无需 Python 侧全表过滤。
    - 删除产品时参考号行随产品级联删除（``ondelete='cascade'``）。
    - 标记 ``is_internal=True`` 的行是 Odoo ``default_code``（General Information 中的
      Reference）在产品「参考号」页里的镜像，始终排在第一且不可删除；修改它会同步回
      ``product.template.default_code``。
    """

    _name = "product.reference.code"
    _description = "Product Reference"
    _order = "is_internal desc, sequence, product_tmpl_id, id"
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
            ("internal", "Internal Reference"),
            ("customer", "Customer Reference"),
            ("factory", "Factory Reference"),
            ("alias", "Alias"),
        ],
        default="customer",
        index=True,
        help="Purpose of this reference: internal references mirror the "
             "General Information Reference field; customer references are "
             "used on outgoing documents; factory references for purchasing; "
             "aliases for historical or colloquial names.",
    )
    is_internal = fields.Boolean(
        string="Internal",
        default=False,
        index=True,
        copy=False,
        help="When checked, this row mirrors the product's Odoo Reference "
             "(default_code) from the General Information tab. It always "
             "appears first and cannot be deleted.",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower values come first; both the list and the One2many lines are "
             "ordered by this value. The internal reference is always pinned "
             "to the top regardless of this value.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to disable a reference without deleting it, so history is "
             "kept. The internal reference cannot be archived.",
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
        required=True,
        index=True,
        help="Product template this reference belongs to; references are removed "
             "together with the product.",
    )

    # ------------------------------------------------------------------
    # 约束：同一产品内参考号不可重复
    # ------------------------------------------------------------------

    _reference_code_unique_per_template = models.Constraint(
        "UNIQUE(product_tmpl_id, reference_code)",
        "Reference codes must be unique within the same product.",
    )

    @api.constrains("reference_code", "product_tmpl_id")
    def _check_reference_code_unique_per_template(self):
        """同一产品内参考号重复时给出可读的中文提示，并带出具体值与归属。

        数据库层已有 ``UNIQUE(product_tmpl_id, reference_code)`` 兜底，
        这里提供更友好的错误信息（含产品名与重复参考号）。
        """
        for record in self:
            if not record.reference_code or not record.product_tmpl_id:
                continue
            duplicate = self.sudo().search([
                ("product_tmpl_id", "=", record.product_tmpl_id.id),
                ("reference_code", "=", record.reference_code),
                ("id", "!=", record.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'The reference "%(code)s" already exists for product '
                    '"%(product)s". Reference codes must be unique within the '
                    "same product.",
                    code=record.reference_code,
                    product=record.product_tmpl_id.display_name,
                ))

    # ------------------------------------------------------------------
    # 写入：维护产品的冗余可搜索字段 + 内部参考回写
    # ------------------------------------------------------------------

    def _sync_template_index(self):
        """参考号增删改后，把所有参考号拼接写入 product.template.reference_code_index。

        这是搜索能力的核心：列表搜索框 / Many2one 下拉 / 快速搜索都不直接查
        ``product.reference.code``，而是走产品模板的冗余字段 + ``_search_display_name``。
        拼接逻辑本身实现在 ``product.template._sync_reference_index``（删除行后仍需按
        剩余行重算，只能在产品模板侧取数）。
        """
        self.mapped("product_tmpl_id")._sync_reference_index()

    # ------------------------------------------------------------------
    # create / write / unlink：触发冗余字段同步，并保护内部参考行
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_template_index()
        return records

    def write(self, vals):
        res = super().write(vals)

        # 内部参考行的代码变更需要同步回 product.template.default_code
        if "reference_code" in vals and not self.env.context.get("reference_sync"):
            for line in self.filtered("is_internal"):
                new_code = (line.reference_code or "").strip()
                if not new_code:
                    # 空代码不反向清空 default_code，避免在 write 过程中触发自我 unlink；
                    # 用户如需清空应通过 General Information 的 Reference 字段操作。
                    continue
                tmpl = line.product_tmpl_id
                if (tmpl.default_code or "").strip() != new_code:
                    tmpl.with_context(reference_sync=True).write({
                        "default_code": new_code,
                    })

        # 仅当影响拼接内容的字段变动时才同步，避免无谓写入
        if any(k in vals for k in (
            "reference_code", "product_tmpl_id", "active", "sequence",
        )):
            self._sync_template_index()
        return res

    def unlink(self):
        if (
            not self.env.context.get("reference_sync")
            and any(line.is_internal for line in self)
        ):
            raise ValidationError(_(
                "The internal reference row (Odoo Reference) cannot be deleted. "
                "Change or clear it in the General Information tab instead."
            ))
        templates = self.mapped("product_tmpl_id")
        res = super().unlink()
        templates._sync_reference_index()
        return res
