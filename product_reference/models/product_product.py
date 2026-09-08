# -*- coding: utf-8 -*-
"""扩展 product.product（变体），挂载变体专属参考号与按参考号搜索的能力。

产品级共享参考号见 ``product_template.py``（``reference_code_line_ids``）；
``product.product`` 通过 ``_inherits = {'product.template': 'product_tmpl_id'}`` 也能读到它，
但**多变体产品的参考号不共用**：变体表单维护的是本变体自己的一组行
（``variant_reference_code_line_ids``，反向到 ``product_id``），与产品级共享行完全独立
（与 product_image 的「变体专属图库」同一思路）。

子行创建的坑（同 product_image）：从模板页进入变体表单时，其 act_window 的 context 携带
``default_product_tmpl_id``；变体参考号行经 ``(0, 0, ...)`` 创建时会被填进
``product_tmpl_id``，随后又被 One2many inverse 回填 ``product_id``，触发「参考号不能同时
归属产品与变体」的约束报错。故对变体参考号行的 create 命令无条件置空产品归属。
"""

from odoo import _, api, fields, models
from odoo.fields import Command, Domain


class ProductProduct(models.Model):
    _inherit = "product.product"

    # ------------------------------------------------------------------
    # 字段定义
    # ------------------------------------------------------------------

    variant_reference_code_line_ids = fields.One2many(
        string="Variant Reference Lines",
        comodel_name="product.reference.code",
        inverse_name="product_id",
        copy=False,
        help="References specific to this variant (customer / factory / alias). They are "
             "independent from the shared product references maintained on the product form: a "
             "product with several variants does not share its references between variants.",
    )
    # 冗余可搜索字段：拼接本变体的所有参考号，配 trigram 索引，
    # 使变体列表 / Many2one 下拉 / 快速搜索能按任一参考号命中本变体。
    # 由 product.reference.code 的 create/write/unlink 负责同步。
    variant_reference_code_index = fields.Text(
        string="Variant Reference Search Index",
        index="trigram",
        copy=False,
        store=True,
        help="Search index built by concatenating the references of this variant. It is "
             "maintained automatically when variant reference lines change; do not edit it "
             "manually.",
    )

    def _sync_variant_reference_index(self):
        """把本变体所有参考号拼接写入 ``variant_reference_code_index``（搜索索引）。

        由 ``product.reference.code`` 的 create / write / unlink 调用；删除行后必须按剩余行
        重算，因此实现放在变体侧（与产品侧 ``_sync_reference_index`` 对称）。
        """
        for product in self:
            codes = product.variant_reference_code_line_ids.mapped("reference_code")
            product.variant_reference_code_index = "\n".join(c for c in codes if c) or False

    # ------------------------------------------------------------------
    # create / write：变体参考号子行必须剥离产品归属默认值
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        self._strip_variant_reference_template_default(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        self._strip_variant_reference_template_default([vals])
        return super().write(vals)

    def _strip_variant_reference_template_default(self, vals_list):
        """把 ``variant_reference_code_line_ids`` 的 create 命令子行产品归属强制置空。"""
        for vals in vals_list:
            commands = vals.get("variant_reference_code_line_ids")
            if not commands:
                continue
            cleaned = []
            for cmd in commands:
                if isinstance(cmd, (list, tuple)) and len(cmd) == 3 and cmd[0] == Command.CREATE:
                    child_vals = dict(cmd[2])
                    child_vals["product_tmpl_id"] = False
                    cleaned.append(Command.create(child_vals))
                else:
                    cleaned.append(cmd)
            vals["variant_reference_code_line_ids"] = cleaned

    # ------------------------------------------------------------------
    # 搜索：Many2one 下拉 / 搜索建议 / 快速搜索按参考号命中变体
    # ------------------------------------------------------------------

    @api.model
    def _search_display_name(self, operator, value):
        """扩展变体的名称搜索：并入变体自己的参考号与所属产品的共享参考号。

        原生只按模板 name / 变体 default_code / barcode 等搜索；这里并入
        ``variant_reference_code_index``（变体级）与继承的 ``reference_code_index``
        （产品级共享）。否定操作符必须取交集，否则会查出所有非该参考号的变体。
        """
        domain = super()._search_display_name(operator, value)
        if not (isinstance(value, str) and value):
            return domain
        extra = Domain.OR([
            Domain("variant_reference_code_index", operator, value),
            Domain("reference_code_index", operator, value),
        ])
        if operator in Domain.NEGATIVE_OPERATORS:
            return Domain.AND([domain, extra])
        return Domain.OR([domain, extra])

    # ------------------------------------------------------------------
    # 列表 API：命中参考号时，把 name 附加「（命中参考号：xxx）」便于区分
    # ------------------------------------------------------------------

    @api.model
    @api.readonly
    def web_search_read(self, domain, specification, offset=0, limit=None,
                        order=None, count_limit=None):
        """变体列表返回的记录中，若搜索域命中了参考号，则在 name 后附加命中参考号提示。

        命中来源包括变体级参考号（``variant_reference_code_index``）与所属产品的共享
        参考号（``reference_code_index``）。仅当请求了 name 字段、且搜索域含对应条件时
        才做一次轻量查询。
        """
        result = super().web_search_read(
            domain, specification, offset=offset, limit=limit,
            order=order, count_limit=count_limit,
        )
        if "name" not in (specification or {}):
            return result

        search_terms = self.env["product.template"]._extract_reference_code_search_terms(
            domain, ("variant_reference_code_index", "reference_code_index"),
        )
        if not search_terms:
            return result

        record_ids = [rec["id"] for rec in result.get("records", []) if rec.get("id")]
        if not record_ids:
            return result

        variants = self.sudo().search_fetch(
            [("id", "in", record_ids)],
            ["variant_reference_code_index", "reference_code_index"],
        )
        for variant in variants:
            indexes = [
                variant.variant_reference_code_index or "",
                variant.reference_code_index or "",
            ]
            hits = [t for t in search_terms if t and any(t in idx for idx in indexes)]
            if not hits:
                continue
            for rec in result["records"]:
                if rec.get("id") != variant.id:
                    continue
                base = rec.get("name") or ""
                hint = _(" (Matching reference: %(codes)s)", codes=" / ".join(hits))
                if hint not in base:
                    rec["name"] = base + hint
        return result
