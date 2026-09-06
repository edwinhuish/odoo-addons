# -*- coding: utf-8 -*-
"""产品型号明细模型。

一个产品可挂多条型号（客户型号 / 工厂型号 / 别名）。
型号本身是独立模型，通过 One2many 挂在 product.template 上。
搜索能力由 product.template 侧的冗余可存储字段 ``model_code_index`` 与
``_search_display_name`` 扩展共同保证，详见 ``product_template.py``。
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductModelCode(models.Model):
    """产品型号明细。

    设计要点：
    - 同一产品内型号不可重复（``model_code_unique_per_template``）；
      不同产品间允许同型号，但搜索命中时会显示「产品名（命中型号：xxx）」便于区分。
    - ``model_code_index`` 冗余存储到产品模板上，并配 trigram 索引，
      使列表搜索框、Many2one 下拉、快速搜索均可按型号命中，无需 Python 侧全表过滤。
    - 删除产品时型号行随产品级联删除（``ondelete='cascade'``）。
    """

    _name = "product.model.code"
    _description = "Product Model"
    _order = "sequence, product_tmpl_id, id"
    _rec_name = "model_code"

    # ------------------------------------------------------------------
    # 字段定义
    # ------------------------------------------------------------------

    model_code = fields.Char(
        string="Model",
        required=True,
        index=True,
        help="Model code of the product. It cannot be repeated inside the same "
             "product, but the same code may be used by other products; when a "
             "search hits a model, the result shows \"Product (Matching model: "
             "xxx)\" to tell them apart.",
    )
    model_type = fields.Selection(
        string="Model Type",
        selection=[
            ("customer", "Customer Model"),
            ("factory", "Factory Model"),
            ("alias", "Alias"),
        ],
        default="customer",
        index=True,
        help="Purpose of this model: customer models are used on outgoing "
             "documents, factory models for purchasing, aliases for historical "
             "or colloquial names.",
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
        help="Uncheck to disable a model without deleting it, so history is kept.",
    )
    note = fields.Char(
        string="Note",
        help="Short description of this model (customer, version, effective "
             "date, ...).",
    )

    product_tmpl_id = fields.Many2one(
        string="Product",
        comodel_name="product.template",
        ondelete="cascade",
        required=True,
        index=True,
        help="Product template this model belongs to; models are removed "
             "together with the product.",
    )

    # ------------------------------------------------------------------
    # 约束：同一产品内型号不可重复
    # ------------------------------------------------------------------

    _model_code_unique_per_template = models.Constraint(
        "UNIQUE(product_tmpl_id, model_code)",
        "Model codes must be unique within the same product.",
    )

    @api.constrains("model_code", "product_tmpl_id")
    def _check_model_code_unique_per_template(self):
        """同一产品内型号重复时给出可读的中文提示，并带出具体值与归属。

        数据库层已有 ``UNIQUE(product_tmpl_id, model_code)`` 兜底，
        这里提供更友好的错误信息（含产品名与重复型号）。
        """
        for record in self:
            if not record.model_code or not record.product_tmpl_id:
                continue
            duplicate = self.sudo().search([
                ("product_tmpl_id", "=", record.product_tmpl_id.id),
                ("model_code", "=", record.model_code),
                ("id", "!=", record.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'The model "%(code)s" already exists for product "%(product)s". '
                    "Model codes must be unique within the same product.",
                    code=record.model_code,
                    product=record.product_tmpl_id.display_name,
                ))

    # ------------------------------------------------------------------
    # 写入：维护产品的冗余可搜索字段
    # ------------------------------------------------------------------

    def _sync_template_index(self):
        """型号增删改后，把所有型号拼接写入 product.template.model_code_index。

        这是搜索能力的核心：列表搜索框 / Many2one 下拉 / 快速搜索都不直接查
        ``product.model.code``，而是走产品模板的冗余字段 + ``_search_display_name``。
        """
        templates = self.mapped("product_tmpl_id")
        for tmpl in templates:
            codes = tmpl.model_code_line_ids.mapped("model_code")
            tmpl.model_code_index = "\n".join(c for c in codes if c) or False

    # ------------------------------------------------------------------
    # create / write / unlink：触发冗余字段同步
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_template_index()
        return records

    def write(self, vals):
        res = super().write(vals)
        # 仅当影响拼接内容的字段变动时才同步，避免无谓写入
        if any(k in vals for k in ("model_code", "product_tmpl_id", "active", "sequence")):
            self._sync_template_index()
        return res

    def unlink(self):
        templates = self.mapped("product_tmpl_id")
        res = super().unlink()
        templates._sync_template_index()
        return res
