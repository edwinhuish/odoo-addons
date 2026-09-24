# -*- coding: utf-8 -*-
"""扩展 product.template，挂载参考号明细、产品级编号，并支持按参考号搜索。

关键约束（详见模块 AGENTS.md L1）：
1. 参考号用独立模型 + One2many，禁止逗号分隔塞单个 Char；产品级与变体级两层
   各自独立、都可见（不再按变体数隐藏）
2. 搜索在数据库层：冗余可存储字段 ``reference_code_index`` + trigram 索引
3. ``_search_display_name`` 让 Many2one / 下拉 / 快速搜索命中参考号（含变体层）
4. ``web_search_read`` 在列表请求 name 时附加「命中参考号」提示
5. 产品级编号存 ``base_reference``，并**叠加**在原生 ``default_code`` 的
   compute / inverse 之上（``base_reference`` 优先；单变体产品两处同值、多变体产品
   只写 ``base_reference``）—— 消费方（卡片视图等）因此只需读原生 ``default_code``，
   不必知道本模块存在
"""

from odoo import _, api, fields, models
from odoo.fields import Domain

from .reference_case import UPPERCASE_FIELDS, uppercase_reference_vals


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

    # ------------------------------------------------------------------
    # 模板级产品编号（base reference）
    # ------------------------------------------------------------------
    #
    # 多变体产品（G001-WT / G001-BK）的「产品编号」（G001）需要存在**产品**这一层：
    # 原生 `default_code` 是 `product.product` 的自有字段，模板侧在多变体时只是空桥接
    # （`_compute_template_field_from_variant_field` 只在单变体时镜像变体值）。
    #
    # 因此：
    # 1. 新增本字段存产品级编号（存储 + trigram 索引 + 复制时带走）；
    # 2. **重写模板级 `default_code` 的 compute 与 inverse**（见下面两个方法）：
    #    - 读：`base_reference` 优先，其次才是原生单变体桥接 —— 于是产品表单的 `Ref.`
    #      输入框、产品列表 / Many2one 的 `[编号] 名称`、列表搜索都自动带上产品编号；
    #    - 写：单变体产品同时写两处（`base_reference` + 那条变体的 `default_code`），
    #      多变体产品只写 `base_reference`（变体编号各归各的变体）。
    base_reference = fields.Char(
        string="Base Reference",
        index="trigram",
        copy=True,
        help="Product reference of the template itself, used by products with several variants "
             "(e.g. G001 for the variants G001-WT and G001-BK). The template reference "
             "(default_code) computes to this value when it is set, so the product form, the "
             "product list and the searches show it; on a single-variant product the template "
             "reference and the variant reference are kept equal.",
    )

    @api.depends("product_variant_ids.default_code", "base_reference")
    def _compute_default_code(self):
        """模板级 ``default_code``：``base_reference``（产品编号）优先，其次原生单变体桥接。

        原生实现只在单变体时镜像变体编号；这里在它之上叠加「产品级编号优先」，
        使多变体产品在**原生的**编号口径（表单 `Ref.`、列表 `[编号] 名称`、列表搜索、
        `display_name`）里也有值，而不必让消费方（卡片视图等）知道本模块存在。
        """
        super()._compute_default_code()
        for tmpl in self:
            if tmpl.base_reference:
                tmpl.default_code = tmpl.base_reference

    def _set_default_code(self):
        """写入模板级编号：单变体产品写回那条变体（原生），两处都记 ``base_reference``。

        - 单变体产品：原生 `_set_default_code()` 把值写到那条唯一的变体上（随后的
          变体 hook 会把 `base_reference` 一起同步），这里再兜一次底；
        - 多变体产品：原生写入不落任何变体（Odoo 语义），这里写入 `base_reference`。

        ⚠ 这里只写 `base_reference` 一个字段：**不要再顺手写 `default_code`**
        （那会再次触发本方法 → 无限递归）。变体侧的统一出口是
        `_sync_single_variant_default_code()`。
        """
        super()._set_default_code()
        for tmpl in self:
            if tmpl.base_reference != tmpl.default_code:
                tmpl.base_reference = tmpl.default_code

    def _sync_single_variant_default_code(self):
        """单变体产品：把产品级编号同步到那条变体的 ``default_code``。

        「直接写 `base_reference`」那条路（API / 脚本 / 数据导入）的收口：
        单变体产品两处必须同值；多变体产品的变体编号与产品编号无关，**不动**。
        写变体不会回头再触发本方法（变体侧 hook 只在两处不同时才写 `base_reference`），
        因此链路必然收敛。
        """
        for tmpl in self:
            variants = tmpl.product_variant_ids
            if len(variants) == 1 and variants.default_code != tmpl.base_reference:
                variants.default_code = tmpl.base_reference

    @api.model_create_multi
    def create(self, vals_list):
        # 型号一律大写：产品编号 `base_reference` 与产品表单的 `Ref.`（原生
        # `default_code`）同口径，避免出现「产品大写、变体小写」的半截数据
        for vals in vals_list:
            uppercase_reference_vals(vals, UPPERCASE_FIELDS[self._name])
        templates = super().create(vals_list)
        templates._sync_single_variant_default_code()
        return templates

    def write(self, vals):
        uppercase_reference_vals(vals, UPPERCASE_FIELDS[self._name])
        res = super().write(vals)
        if "base_reference" in vals:
            self._sync_single_variant_default_code()
        return res

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
        # 产品级共享参考号 + 各变体的参考号（两层各自独立，但在产品列表 / Many2one 里
        # 按任一变体的参考号都应能找到这个产品）。
        # 产品级编号（多变体产品的 base_reference）不必单独并入：它已经进了模板级
        # `default_code` 的 compute，原生那一支就能命中（见 `_compute_default_code`）
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
