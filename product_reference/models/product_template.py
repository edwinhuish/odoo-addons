# -*- coding: utf-8 -*-
"""扩展 product.template，挂载参考号明细并支持按参考号搜索。

关键约束（详见模块 AGENTS.md L1）：
1. 参考号用独立模型 + One2many，禁止逗号分隔塞单个 Char
2. 搜索在数据库层：冗余可存储字段 ``reference_code_index`` + trigram 索引
3. ``_search_display_name`` 让 Many2one / 下拉 / 快速搜索命中参考号
4. ``web_search_read`` 在列表请求 name 时附加「命中参考号」提示
"""

from odoo import _, api, fields, models
from odoo.fields import Domain


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # ------------------------------------------------------------------
    # 字段定义
    # ------------------------------------------------------------------

    reference_code_line_ids = fields.One2many(
        string="Reference Lines",
        comodel_name="product.reference.code",
        inverse_name="product_tmpl_id",
        copy=False,
        help="All references of this product (customer / factory / alias).",
    )
    reference_code_count = fields.Integer(
        string="Reference Count",
        compute="_compute_reference_code_count",
    )
    # 冗余可搜索字段：把该产品所有参考号拼成一个文本块，配 trigram 索引，
    # 使列表搜索框 / 快速搜索 / Many2one 下拉都能按任一参考号命中本产品。
    # 由 product.reference.code 的 create/write/unlink 负责同步。
    reference_code_index = fields.Text(
        string="Reference Search Index",
        index="trigram",
        copy=False,
        store=True,
        help="Search index built by concatenating all references of this "
             "product. It is maintained automatically when reference lines "
             "change; do not edit it manually.",
    )

    @api.depends("reference_code_line_ids")
    def _compute_reference_code_count(self):
        for tmpl in self:
            tmpl.reference_code_count = len(tmpl.reference_code_line_ids)

    def _sync_reference_index(self):
        """把所有参考号拼接写入 ``reference_code_index``（搜索索引）。

        由 ``product.reference.code`` 的 create / write / unlink 调用；删除行后必须
        按剩余行重算，因此实现放在产品模板侧。
        """
        for tmpl in self:
            codes = tmpl.reference_code_line_ids.mapped("reference_code")
            tmpl.reference_code_index = "\n".join(c for c in codes if c) or False

    # ------------------------------------------------------------------
    # 显示名称：命中参考号时附加「（命中参考号：xxx）」便于区分
    # ------------------------------------------------------------------

    @api.depends("name", "default_code", "reference_code_index")
    @api.depends_context("formatted_display_name", "display_default_code")
    def _compute_display_name(self):
        """原生展示为 ``[内部参考] 产品名``；本模块在命中参考号搜索时不破坏原生逻辑。

        命中参考号的提示由 ``_search_display_name`` 配合 ``web_search_read`` 在列表层处理，
        此处仅把 ``reference_code_index`` 加入依赖，保证冗余字段变动后 display_name 刷新。
        """
        super()._compute_display_name()

    @api.model
    def _search_display_name(self, operator, value):
        """扩展 Many2one 下拉 / 搜索建议 / 快速搜索，使其可按任一参考号命中产品。

        原生只按 name（及上下文里的 product_variant_ids）搜索；这里并入
        ``reference_code_index`` 的子串匹配。否定操作符必须取交集，否则会查出所有
        非该参考号的产品。
        """
        domain = super()._search_display_name(operator, value)
        if not (isinstance(value, str) and value):
            return domain
        # 产品级共享参考号 + 各变体的参考号（多变体产品的参考号不共用，
        # 但在产品列表 / Many2one 里按任一变体的参考号都应能找到这个产品）
        extra = Domain.OR([
            Domain("reference_code_index", operator, value),
            Domain("product_variant_ids", "any", [
                ("variant_reference_code_index", operator, value),
            ]),
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
        """列表视图返回的记录中，若搜索域命中了参考号，则在 name 后附加命中参考号提示。

        命中来源包括产品级共享参考号（``reference_code_index``）与各变体的参考号
        （``product_variant_ids.variant_reference_code_index``）。
        仅当请求了 name 字段、且搜索域含对应条件时才做一次轻量查询。
        """
        result = super().web_search_read(
            domain, specification, offset=offset, limit=limit,
            order=order, count_limit=count_limit,
        )
        if "name" not in (specification or {}):
            return result

        # 提取搜索域中针对参考号冗余字段的字面量（含变体路径）
        search_terms = self._extract_reference_code_search_terms(
            domain,
            ("reference_code_index", "product_variant_ids.variant_reference_code_index"),
        )
        if not search_terms:
            return result

        record_ids = [rec["id"] for rec in result.get("records", []) if rec.get("id")]
        if not record_ids:
            return result

        # 一次查回所有相关产品的参考号拼串与其变体参考号拼串，避免逐记录查询
        templates = self.sudo().search_fetch(
            [("id", "in", record_ids)], ["reference_code_index"],
        )
        variant_indexes = self._variant_reference_indexes_by_template(record_ids)
        for tmpl in templates:
            indexes = [tmpl.reference_code_index or "", *variant_indexes.get(tmpl.id, [])]
            hits = [t for t in search_terms if t and any(t in idx for idx in indexes)]
            if not hits:
                continue
            for rec in result["records"]:
                if rec.get("id") != tmpl.id:
                    continue
                base = rec.get("name") or ""
                hint = _(" (Matching reference: %(codes)s)", codes=" / ".join(hits))
                if hint not in base:
                    rec["name"] = base + hint
        return result

    @api.model
    def _extract_reference_code_search_terms(self, domain,
                                             field_names=("reference_code_index",)):
        """从搜索域中抽取参考号冗余字段（默认 ``reference_code_index``）上的字面量。

        ``field_names`` 供变体侧复用（``variant_reference_code_index`` 等）。
        支持三种写法：
        - 顶层三元组 ``('reference_code_index', 'ilike', 'ABC')``
        - 变体路径 ``('product_variant_ids', 'any', [('variant_reference_code_index', ...)])``
        - ``Domain`` 对象（递归其 ``children``）

        仅识别正向 ``ilike`` / ``like`` / ``=`` / ``in`` 中的字符串值，
        否定操作符和复杂表达式不参与提示拼接（仍参与搜索本身）。
        """
        terms = []
        if not domain:
            return terms
        # 支持 Domain 对象与原生 list 两种形式
        items = domain
        if hasattr(domain, "children"):
            items = domain.children
        for item in items:
            if isinstance(item, str):
                # Domain 对象的 logical connector ('&', '|', '!') 等
                continue
            if hasattr(item, "children"):
                terms.extend(self._extract_reference_code_search_terms(item, field_names))
                continue
            if not (isinstance(item, (list, tuple)) and len(item) == 3):
                continue
            field_name, op, val = item
            if field_name in field_names and op in ("ilike", "like", "=", "in"):
                if isinstance(val, str):
                    terms.append(val)
                elif isinstance(val, (list, tuple)):
                    terms.extend(v for v in val if isinstance(v, str))
            # 变体路径：('product_variant_ids', 'any', [('variant_reference_code_index', ...)])
            if op == "any" and isinstance(val, (list, tuple)):
                terms.extend(self._extract_reference_code_search_terms(list(val), field_names))
        return terms

    @api.model
    def _variant_reference_indexes_by_template(self, tmpl_ids):
        """返回 ``{产品模板 id: [变体参考号索引, ...]}``，供命中提示判断使用。

        变体参考号不写回产品的 ``reference_code_index``（多变体产品参考号不共用），
        因此命中提示需要单独把变体拼串取回来比对。
        """
        indexes = {}
        if not tmpl_ids:
            return indexes
        variants = self.env["product.product"].sudo().search_fetch(
            [("product_tmpl_id", "in", list(tmpl_ids))],
            ["variant_reference_code_index", "product_tmpl_id"],
        )
        for variant in variants:
            if variant.variant_reference_code_index:
                indexes.setdefault(variant.product_tmpl_id.id, []).append(
                    variant.variant_reference_code_index
                )
        return indexes
