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
    _description = "产品型号"
    _order = "sequence, product_tmpl_id, id"
    _rec_name = "model_code"

    # ------------------------------------------------------------------
    # 字段定义
    # ------------------------------------------------------------------

    model_code = fields.Char(
        string="型号",
        required=True,
        index=True,
        help="产品型号，同一产品内不可重复；不同产品间可重复，"
             "搜索时命中会显示「产品名（命中型号：xxx）」以区分。",
    )
    model_type = fields.Selection(
        string="型号类型",
        selection=[
            ("customer", "客户型号"),
            ("factory", "工厂型号"),
            ("alias", "别名"),
        ],
        default="customer",
        index=True,
        help="区分该型号的用途：客户型号用于对外单据，工厂型号用于采购，"
             "别名用于历史/俗称匹配。",
    )
    sequence = fields.Integer(
        string="排序",
        default=10,
        help="数值小的排在前面，列表与 One2many 行均按此排序。",
    )
    active = fields.Boolean(
        string="启用",
        default=True,
        help="取消勾选可停用某条型号而不删除，便于保留历史。",
    )
    note = fields.Char(
        string="备注",
        help="对该型号的简短说明（如对应客户、版本、生效日期等）。",
    )

    product_tmpl_id = fields.Many2one(
        string="产品",
        comodel_name="product.template",
        ondelete="cascade",
        required=True,
        index=True,
        help="该型号所属的产品模板；删除产品时型号行随之级联清理。",
    )

    # ------------------------------------------------------------------
    # 约束：同一产品内型号不可重复
    # ------------------------------------------------------------------

    _model_code_unique_per_template = models.Constraint(
        "UNIQUE(product_tmpl_id, model_code)",
        "同一产品内型号不可重复。",
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
                    "型号“%s”在产品“%s”中已存在，同一产品内型号不可重复。"
                ) % (
                    record.model_code,
                    record.product_tmpl_id.display_name,
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
