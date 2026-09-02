# -*- coding: utf-8 -*-
"""扩展 product.template，挂载型号明细并支持按型号搜索。

关键约束（详见模块 AGENTS.md L1）：
1. 型号用独立模型 + One2many，禁止逗号分隔塞单个 Char
2. 搜索在数据库层：冗余可存储字段 ``model_code_index`` + trigram 索引
3. ``_search_display_name`` 让 Many2one / 下拉 / 快速搜索命中型号
4. ``web_search_read`` 在列表请求 name 时附加「命中型号」提示
"""

from odoo import api, fields, models
from odoo.fields import Domain


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # ------------------------------------------------------------------
    # 字段定义
    # ------------------------------------------------------------------

    model_code_line_ids = fields.One2many(
        string="型号明细",
        comodel_name="product.model.code",
        inverse_name="product_tmpl_id",
        copy=False,
        help="该产品的所有型号（客户型号 / 工厂型号 / 别名）。",
    )
    model_code_count = fields.Integer(
        string="型号数量",
        compute="_compute_model_code_count",
    )
    # 冗余可搜索字段：把该产品所有型号拼成一个文本块，配 trigram 索引，
    # 使列表搜索框 / 快速搜索 / Many2one 下拉都能按任一型号命中本产品。
    # 由 product.model.code 的 create/write/unlink 负责同步。
    model_code_index = fields.Text(
        string="型号搜索索引",
        index="trigram",
        copy=False,
        store=True,
        help="该产品所有型号拼接后的搜索索引，由型号行增删改时自动维护，请勿手工编辑。",
    )

    @api.depends("model_code_line_ids")
    def _compute_model_code_count(self):
        for tmpl in self:
            tmpl.model_code_count = len(tmpl.model_code_line_ids)

    # ------------------------------------------------------------------
    # 显示名称：命中型号时附加「（命中型号：xxx）」便于区分
    # ------------------------------------------------------------------

    @api.depends("name", "default_code", "model_code_index")
    @api.depends_context("formatted_display_name", "display_default_code")
    def _compute_display_name(self):
        """原生展示为 ``[内部参考] 产品名``；本模块在命中型号搜索时不破坏原生逻辑。

        命中型号的提示由 ``_search_display_name`` 配合 ``web_search_read`` 在列表层处理，
        此处仅把 ``model_code_index`` 加入依赖，保证冗余字段变动后 display_name 刷新。
        """
        super()._compute_display_name()

    @api.model
    def _search_display_name(self, operator, value):
        """扩展 Many2one 下拉 / 搜索建议 / 快速搜索，使其可按任一型号命中产品。

        原生只按 name（及上下文里的 product_variant_ids）搜索；这里并入
        ``model_code_index`` 的子串匹配。否定操作符必须取交集，否则会查出所有
        非该型号的产品。
        """
        domain = super()._search_display_name(operator, value)
        if not (isinstance(value, str) and value):
            return domain
        extra = Domain("model_code_index", operator, value)
        if operator in Domain.NEGATIVE_OPERATORS:
            return Domain.AND([domain, extra])
        return Domain.OR([domain, extra])

    # ------------------------------------------------------------------
    # 列表 API：命中型号时，把 name 附加「（命中型号：xxx）」便于区分
    # ------------------------------------------------------------------

    @api.model
    @api.readonly
    def web_search_read(self, domain, specification, offset=0, limit=None,
                       order=None, count_limit=None):
        """列表视图返回的记录中，若搜索域命中了型号，则在 name 后附加命中型号提示。

        仅当请求了 name 字段、且搜索域含 ``model_code_index`` 条件时才做一次轻量查询。
        """
        result = super().web_search_read(
            domain, specification, offset=offset, limit=limit,
            order=order, count_limit=count_limit,
        )
        if "name" not in (specification or {}):
            return result

        # 提取搜索域中针对 model_code_index 的字面量
        search_terms = self._extract_model_code_search_terms(domain)
        if not search_terms:
            return result

        record_ids = [rec["id"] for rec in result.get("records", []) if rec.get("id")]
        if not record_ids:
            return result

        # 一次查回所有相关产品的型号拼串，避免逐记录查询
        templates = self.sudo().search_fetch([("id", "in", record_ids)], ["model_code_index"])
        for tmpl in templates:
            index = tmpl.model_code_index or ""
            hits = [t for t in search_terms if t and t in index]
            if not hits:
                continue
            for rec in result["records"]:
                if rec.get("id") != tmpl.id:
                    continue
                base = rec.get("name") or ""
                hint = "（命中型号：%s）" % " / ".join(hits)
                if hint not in base:
                    rec["name"] = base + hint
        return result

    @api.model
    def _extract_model_code_search_terms(self, domain):
        """从搜索域中抽取针对 ``model_code_index`` 的字面量。

        仅识别正向 ``ilike`` / ``like`` / ``=`` / ``in`` 中的字符串值，
        否定操作符和复杂表达式不参与提示拼接（仍参与搜索本身）。
        """
        terms = []
        if not domain:
            return terms
        # 支持 Domain 对象与原生 list 两种形式
        items = domain
        if hasattr(domain, "children"):
            items = [domain]
        for item in items:
            if isinstance(item, str):
                # Domain 对象的 logical connector ('&', '|', '!') 等
                continue
            if not (isinstance(item, (list, tuple)) and len(item) == 3):
                continue
            field_name, op, val = item
            if field_name != "model_code_index":
                continue
            if op in ("ilike", "like", "=", "in"):
                if isinstance(val, str):
                    terms.append(val)
                elif isinstance(val, (list, tuple)):
                    terms.extend(v for v in val if isinstance(v, str))
        return terms
