# -*- coding: utf-8 -*-
"""扩展 product.template，挂载参考号明细并支持按参考号搜索。

关键约束（详见模块 AGENTS.md L1）：
1. 参考号用独立模型 + One2many，禁止逗号分隔塞单个 Char
2. 搜索在数据库层：冗余可存储字段 ``reference_code_index`` + trigram 索引
3. ``_search_display_name`` 让 Many2one / 下拉 / 快速搜索命中参考号
4. ``web_search_read`` 在列表请求 name 时附加「命中参考号」提示
5. ``default_code``（General Information 的 Reference）在参考号页有镜像行，
   始终排在第一且不可删除，双向同步
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
        help="All references of this product (internal / customer / factory / alias)."
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

    def _sync_internal_reference_line(self, code=None):
        """把 ``default_code``（General Information 的 Reference）镜像为内部参考号行。

        内部参考行满足：
        - ``is_internal=True``、``reference_type='internal'``，始终排在参考号列表第一；
        - 不可删除，仅随 ``default_code`` 清空而被同步删除；
        - 修改它时会回写 ``product.template.default_code``；修改 ``default_code`` 时同步更新它。

        参数 ``code`` 在 ``product.template.write`` 场景下显式传入，避免读取尚未刷新的
        计算/存储字段旧值；为 ``None`` 时按各记录当前 ``default_code`` 同步。
        """
        Line = self.env["product.reference.code"].with_context(active_test=False)
        existing = Line.search([
            ("product_tmpl_id", "in", self.ids),
            ("is_internal", "=", True),
        ])
        by_tmpl = {}
        for line in existing:
            by_tmpl.setdefault(line.product_tmpl_id.id, []).append(line)

        to_create_vals = []
        for tmpl in self:
            desired = code
            if desired is None:
                desired = (tmpl.default_code or "").strip()

            lines = by_tmpl.get(tmpl.id, [])

            if not desired:
                # 清空 default_code 时，同步删除内部参考行（如其中某些是普通参考号
                # 因代码相同被“提升”而来，也一并删除；这是内部参考的镜像语义）。
                if lines:
                    Line.browse(sum((l.ids for l in lines), [])).with_context(
                        reference_sync=True,
                    ).unlink()
                continue

            if lines:
                keep = lines[0]
                for dup in lines[1:]:
                    dup.with_context(reference_sync=True).unlink()
                if keep.reference_code != desired:
                    keep.with_context(reference_sync=True).write({
                        "reference_code": desired,
                    })
            else:
                # 若已存在同代码的普通参考号行，直接提升为内部行，避免唯一约束冲突。
                adopt = Line.search([
                    ("product_tmpl_id", "=", tmpl.id),
                    ("reference_code", "=", desired),
                    ("is_internal", "=", False),
                ], limit=1)
                if adopt:
                    adopt.with_context(reference_sync=True).write({
                        "is_internal": True,
                        "reference_type": "internal",
                    })
                else:
                    to_create_vals.append({
                        "product_tmpl_id": tmpl.id,
                        "reference_code": desired,
                        "reference_type": "internal",
                        "is_internal": True,
                        "sequence": 0,
                    })

        if to_create_vals:
            Line.with_context(reference_sync=True).create(to_create_vals)

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
        extra = Domain("reference_code_index", operator, value)
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

        仅当请求了 name 字段、且搜索域含 ``reference_code_index`` 条件时才做一次轻量查询。
        """
        result = super().web_search_read(
            domain, specification, offset=offset, limit=limit,
            order=order, count_limit=count_limit,
        )
        if "name" not in (specification or {}):
            return result

        # 提取搜索域中针对 reference_code_index 的字面量
        search_terms = self._extract_reference_code_search_terms(domain)
        if not search_terms:
            return result

        record_ids = [rec["id"] for rec in result.get("records", []) if rec.get("id")]
        if not record_ids:
            return result

        # 一次查回所有相关产品的参考号拼串，避免逐记录查询
        templates = self.sudo().search_fetch(
            [("id", "in", record_ids)], ["reference_code_index"],
        )
        for tmpl in templates:
            index = tmpl.reference_code_index or ""
            hits = [t for t in search_terms if t and t in index]
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

    @api.model_create_multi
    def create(self, vals_list):
        templates = super().create(vals_list)
        templates._sync_internal_reference_line()
        return templates

    def write(self, vals):
        res = super().write(vals)
        if "default_code" in vals:
            # 显式传入 code，避免回读到计算/存储字段未刷新的旧值
            self._sync_internal_reference_line(code=vals.get("default_code"))
        return res

    @api.model
    def _extract_reference_code_search_terms(self, domain):
        """从搜索域中抽取针对 ``reference_code_index`` 的字面量。

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
            if field_name != "reference_code_index":
                continue
            if op in ("ilike", "like", "=", "in"):
                if isinstance(val, str):
                    terms.append(val)
                elif isinstance(val, (list, tuple)):
                    terms.extend(v for v in val if isinstance(v, str))
        return terms
