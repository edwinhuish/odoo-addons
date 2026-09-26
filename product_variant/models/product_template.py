# -*- coding: utf-8 -*-
"""product.template 扩展：多变体产品的安全「加属性 / 加取值」转换与变体归属谱系。

Odoo 原生在「属性与变体」页就写着警告：增删属性会删除并重建既有变体，可能丢失其自定义内容。
本模块提供的是安全路径，核心是三条事实（均已对照 Odoo 19 源码核实）：

1. ``product.template.write`` 与 ``product.template.attribute.line`` 都认 ``create_product_product``
   上下文开关：置为 ``False`` 时只写属性行与 ptav，不会触发 ``_create_variant_ids``，
   因此不会新建、也不会删除任何变体。
2. ``_create_variant_ids`` 用「变体已有的 ``product_template_attribute_value_ids`` 组合」
   去匹配所有可能组合：匹配上的变体被复用（激活），匹配不上的才新建，剩下的旧变体才被删/归档。
   所以只要把**每一个**既有变体都「锚定」到它转换后应当占有的组合上，既有变体就会被原样复用。
3. 既有单据与库存都指向 ``product.product`` 记录本身（销售 / 采购 / 发票行、库存量、
   库存移动明细等），只要这些记录不被删除重建，历史数据就不会错乱。

「归属」的显式记录：转换会写一条 ``product.variant.conversion`` 台账与每个变体一条
``product.variant.lineage`` 谱系行（谁派生自谁、这次加了哪些取值、原记录是否被保留），
并在 ``product.product`` 上留下可搜索的 ``variant_conversion_id`` / ``variant_origin_id``。

入口不在按钮上：用户照常在产品表单里改「属性与变体」并保存，``write`` 会先演练一次原生写法
（在保存点里跑一遍再回滚，见 ``_analyze_variant_conversion_write``），据此判断这次改动会不会
丢既有变体、会不会新增变体；前端（``FormController.onWillSaveRecord``）拿到结论后弹窗让用户
确认归属，未确认前不保存。详见 ``write`` 的注释。

**「按需生成变体」的属性（``create_variant == 'dynamic'``）不在本模块的处理范围内**：那种产品的
变体由 Odoo 按订单创建（``_create_variant_ids`` 遇到这种属性整段跳过，连「建产品」时都不建变体）。
``create`` 与 ``write`` 两处都拒绝这类改动，报错点名是哪个属性并给出可执行的出路
（见 ``_get_variant_conversion_dynamic_message``）。
"""

import itertools
import json

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # ------------------------------------------------------------------
    # 字段：转换台账与谱系（只读，供产品表单展示与追溯）
    # ------------------------------------------------------------------

    variant_conversion_ids = fields.One2many(
        comodel_name="product.variant.conversion",
        inverse_name="product_tmpl_id",
        string="Variant Conversions",
        readonly=True,
        copy=False,
        help="Conversions that added attributes to this product.",
    )
    variant_conversion_count = fields.Integer(
        string="# Variant Conversions",
        compute="_compute_variant_conversion_count",
        help="Number of conversions applied to this product.",
    )
    lineage_ids = fields.One2many(
        comodel_name="product.variant.lineage",
        inverse_name="product_tmpl_id",
        string="Variant Lineage",
        readonly=True,
        copy=False,
        help="Which variant derives from which original variant, per conversion.",
    )
    variant_conversion_mapping = fields.Text(
        string="Variant Conversion Mapping",
        copy=False,
        help="Technical field used by the product form. When an attribute change creates new variants, "
             "the form asks for the variant ownership and sends it here, together with the attribute "
             "change itself. It is cleared as soon as the conversion has been applied.",
    )

    @api.depends("variant_conversion_ids")
    def _compute_variant_conversion_count(self):
        for tmpl in self:
            tmpl.variant_conversion_count = len(tmpl.variant_conversion_ids)

    # ------------------------------------------------------------------
    # 入口
    # ------------------------------------------------------------------

    def action_open_variant_conversions(self):
        """打开该产品的转换台账列表。"""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "product_variant.product_variant_conversion_action")
        action["domain"] = [("product_tmpl_id", "=", self.id)]
        action["context"] = {"default_product_tmpl_id": self.id}
        return action

    # ------------------------------------------------------------------
    # 保存拦截：属性变更触发的归属确认
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        """建产品时挡住「按需生成变体」的属性，避免出现「有属性、没变体」的产品。

        原生 ``create()`` 末尾调的 ``_create_variant_ids()`` 一遇到按需生成的属性就**整段跳过**
        （见该方法里的 ``if not tmpl_id.has_dynamic_attributes()``），于是产品带着属性却一条变体都没有：
        卖不了，也进不了本模块的转换流程（转换的前提是「至少有一条既有变体可以保留」）。
        而在建产品的这一刻，这个属性**还没被任何产品使用**，Odoo 还允许改它的变体生成方式
        （``product.attribute.write()`` 只在属性已被产品使用时才拦），所以这里拒绝并把出路写清楚，
        用户改完属性设置重存即可 —— 比留一个没变体的产品好收拾。

        ``create_product_product=False`` 时放行：那是「调用方自己管变体」的沙盒模式，
        典型是产品导入（``product.product._load_records_create()`` 只带必填字段建模板、
        稍后自己建属性行与变体；它把新建属性设成按需生成是 Odoo 自己的设计，不归本模块管）。
        """
        templates = super().create(vals_list)
        if not self.env.context.get("create_product_product", True):
            return templates
        for template in templates:
            dynamic_attributes = template._get_variant_conversion_dynamic_attributes()
            if dynamic_attributes:
                raise UserError(template._get_variant_conversion_dynamic_message(
                    dynamic_attributes))
        return templates

    def write(self, vals):
        """拦截会动到既有变体的属性变更，改走「归属确认 + 安全转换」。

        用户照常在产品表单里改「属性与变体」并保存，前端（``FormController.onWillSaveRecord``）
        会先调 ``get_variant_conversion_preview()`` 问这次改动的影响；需要归属确认时弹窗，
        用户确认后才把归属映射放进 ``variant_conversion_mapping`` 一起提交。服务端按三种情况处理：

        1. 不影响既有变体也不新增变体（例如只加「不生成变体」的属性、只调顺序）→ 按原生写法保存；
        2. 会新增变体（加属性 / 加取值）→ 没有归属映射就**拦住保存**（等前端弹窗确认），
           有映射就先做安全转换（保住每条既有变体、只新增缺失组合），再把本次保存的其余内容原样落库；
        3. 会丢既有变体（删取值 / 删属性）→ 直接拒绝：本模块绝不静默删除既有变体。
        """
        # create_product_product=False 是模块自己的「只写配置、不碰变体」模式
        # （分析用的一次试写、以及 _convert_to_multi_variant 内部写属性行都走它），
        # 那条路上不可能触发变体的删旧建新，也不该被再次拦截（否则会无限递归）
        if "attribute_line_ids" not in vals or not self.env.context.get("create_product_product", True):
            return super().write(vals)

        vals = dict(vals)
        mapping_payload = vals.pop("variant_conversion_mapping", False)

        # 先锁住模板行再做分析：分析在前、锁在后的话，并发下可能拿到过期的结论（T-018）
        if len(self) == 1:
            self.env.cr.execute("SELECT id FROM product_template WHERE id = %s FOR UPDATE", (self.id,))

        if len(self) > 1:
            # 多记录写入表达不了「每条变体的归属」，只做安全判定：会动到变体就要求逐条保存
            for tmpl in self:
                affected = tmpl._analyze_variant_conversion_write(vals["attribute_line_ids"])
                if affected["lost_variant_ids"] or affected["expected_count"] > affected["before_count"]:
                    raise UserError(_(
                        "Changing the attributes of several products at once cannot keep track of the variant ownership of %(product)s. Save the products one by one from the product form.",
                        product=tmpl.display_name,
                    ))
            return super().write(vals)

        affected = self._analyze_variant_conversion_write(vals["attribute_line_ids"])
        if affected["lost_variant_ids"]:
            if affected.get("lost_values_archived"):
                raise UserError(_(
                    "The value %(values)s of %(product)s has been archived in the attribute settings while "
                    "%(count)s variants still carry it: the conversion cannot keep those combinations. "
                    "Restore the value in the attribute settings, or archive or delete those variants first.",
                    values=affected["lost_value_names"],
                    count=len(affected["lost_variant_ids"]),
                    product=self.display_name,
                ))
            raise UserError(_(
                "This attribute change removes values and would archive or delete %(count)s existing variants of %(product)s, which carry their own stock, orders and invoices. Nothing has been changed. Archive or delete those variants first if you really want to drop them.",
                count=len(affected["lost_variant_ids"]),
                product=self.display_name,
            ))
        if affected["expected_count"] < affected["before_count"]:
            raise UserError(_(
                "This attribute change would leave %(expected)s variants out of the %(existing)s variants of %(product)s: some of them would be archived or deleted. Nothing has been changed. Archive or delete the variants you do not need first.",
                expected=affected["expected_count"],
                existing=affected["before_count"],
                product=self.display_name,
            ))
        if affected["expected_count"] <= affected["before_count"]:
            # 既有变体一条不少、也不会新增变体（例如只加单取值属性、只加不生成变体的属性）→ 原生保存。
            # 例外：原生这次会把某条既有变体的组合判成「不完整」而删掉它（needs_anchoring，
            # 典型是给产品加一个**多取值**的「按需生成」属性行）→ 不能交给原生，
            # 往下走转换、用默认归属把每条既有变体的锚点写下去（没有新变体，所以不用弹窗确认）。
            if not affected["needs_anchoring"]:
                if not mapping_payload:
                    # 原生直写之所以安全，靠下面这条**不变量**（改上面判据时必须重验）：
                    # 走到这里说明「组合数 >= 启用变体数」且每条既有变体都带全了所有**多取值**
                    # 属性行的取值（否则 needs_anchoring），所以 `_create_variant_ids()` 不会把
                    # 任何启用变体判成多余。归档变体同样不会被悄悄激活：它若还带着某个**活组合**，
                    # 那个组合必然计入 expected_count，于是 expected_count > before_count
                    # （before_count 只数启用变体，见 `_analyze_variant_conversion_write()`），
                    # 流程会落到下面的转换路径，由 `_check_variant_conversion_allowed()` 以
                    # 「先恢复或删除归档变体」拒绝；若它的组合已不是活组合，`_create_variant_ids()`
                    # 用同一套排除规则也不会激活它。
                    # 注意：这条分支**没有**转换路径那样的后置断言，靠的就是上述推理。
                    # 用例：`test_archived_variants_cannot_slip_through_the_native_save`。
                    return super().write(vals)
                # 用户在映射表里给每条既有变体指定了组合后，删属性行 / 删取值是**有意为之**：
                # 典型是删掉产品上唯一的属性 —— 那条变体由映射继续承载「空组合」，不会被删。
                # 但原生写法会先删属性行，而 product_attribute_guards.py 里「不许删带着在用变体的
                # 属性行 / 取值」的守卫会在那里拦住它。守卫的前提是「变体会被连坐删掉或归档」，
                # 映射已经说明不会（每条既有变体都有组合），所以带上下文键放行。
                # 先解析一次映射，确认「每条既有变体都有组合」这条前提真的成立再放行。
                self._parse_variant_conversion_mapping(mapping_payload)
                vals["variant_conversion_mapping"] = False
                return super(
                    ProductTemplate,
                    self.with_context(variant_conversion_keeps_variants=True),
                ).write(vals)
        elif not mapping_payload:
            # 还有变体没有组合（映射表里处于「未映射」）：保存不放行。
            # 正常路径是用户在「属性与变体」页下方的映射表里逐条选好，由表单把映射
            # 随本次保存一起提交；走到这里说明没带映射（例如前端资源没生效），
            # 此时一个字都不写库，让用户回表单里补 —— 见 product_variant_mapping.py
            raise UserError(self._get_variant_mapping_blocked_message())
        # ① 先把用户那组属性命令写进去：create_product_product=False → 只写配置（属性行 + ptav），
        #    一条变体都不碰（原生写法在这一步就已经把既有变体删掉了）
        self.with_context(create_product_product=False).write({
            "attribute_line_ids": vals["attribute_line_ids"],
        })
        # ② 再做安全转换：按归属映射把每条既有变体锚定到它的组合上、只新增缺失的组合，
        #    并写下转换台账与谱系。此时配置已是目标配置，转换里那一步写属性行是幂等的。
        # 没有映射也走转换的唯一情况：本次不新增变体、但原生会丢变体（needs_anchoring，见上），
        # 这时不需要用户确认归属，用默认归属即可，所以 mapping 留空由 _convert_to_multi_variant 兜底
        variant_mapping, share_vendor_prices, skipped_combinations = (
            self._parse_variant_conversion_mapping(mapping_payload) if mapping_payload
            else ({}, False, set()))
        self._convert_to_multi_variant(
            self._get_variant_conversion_specification(),
            variant_mapping=variant_mapping,
            share_vendor_prices=share_vendor_prices,
            skipped_combinations=skipped_combinations,
            # 台账要记「本次真正新加了哪些属性」：属性行在第①步已写成目标配置，读不出来了
            added_attributes=affected["added_attributes"],
        )
        # ③ 本次保存的其余字段（价格等）照常落库；属性行已在①②处理完，不再重复写
        other_vals = {key: val for key, val in vals.items() if key != "attribute_line_ids"}
        other_vals["variant_conversion_mapping"] = False
        return super().write(other_vals)

    def get_variant_conversion_preview(self, attribute_line_ids):
        """把「这次属性改动会怎样影响既有变体」告诉产品表单。

        由 ``FormController.onWillSaveRecord`` 在保存前调用，``attribute_line_ids`` 就是本次
        保存要写的那组命令。返回值：

        - ``blocked``：非空字符串表示这次改动会丢既有变体（删取值 / 删属性），前端据此拦住保存；
        - ``required``：是否需要用户确认归属（会新增变体时为 True）；
        - ``variants``：既有变体（弹窗里「由谁继续承载」的候选项，含在手数量）；
        - ``dynamic``：产品是否带「按需生成」的属性（那种产品只展开「立即」轴，
          弹窗要据此提示「按需轴的其它取值不会被预建」并隐藏供应商价格勾选框）；
        - ``combinations``：改动后的组合，``origin_variant_id`` 是「什么都不指定时」的默认归属。
        """
        self.ensure_one()
        affected = self._analyze_variant_conversion_write(attribute_line_ids)
        if affected["lost_variant_ids"]:
            if affected.get("lost_values_archived"):
                return {
                    "blocked": _(
                        "The value %(values)s of this product has been archived in the attribute settings "
                        "while %(count)s variants still carry it: the conversion cannot keep those "
                        "combinations. Restore the value in the attribute settings, or archive or delete "
                        "those variants first.",
                        values=affected["lost_value_names"],
                        count=len(affected["lost_variant_ids"]),
                    ),
                    "required": False,
                    "variants": [],
                    "combinations": [],
                }
            return {
                "blocked": _(
                    "This attribute change removes values and would archive or delete %(count)s existing variants, which carry their own stock, orders and invoices. Archive or delete those variants first if you really want to drop them.",
                    count=len(affected["lost_variant_ids"]),
                ),
                "required": False,
                "variants": [],
                "combinations": [],
            }
        if affected["expected_count"] < affected["before_count"]:
            return {
                "blocked": _(
                    "This attribute change would leave %(expected)s variants out of the %(existing)s variants of this product: some of them would be archived or deleted. Archive or delete the variants you do not need first.",
                    expected=affected["expected_count"],
                    existing=affected["before_count"],
                ),
                "required": False,
                "variants": [],
                "combinations": [],
            }
        return {
            "blocked": False,
            "required": affected["expected_count"] > affected["before_count"],
            "dynamic": bool(affected["dynamic_attributes"]),
            "variants": self._get_variant_conversion_variant_options(),
            "combinations": affected["combinations"],
        }

    @api.model
    def _sanitize_attribute_line_commands(self, commands):
        """去掉「还没填属性」的新行，剩下的命令原样返回。

        产品表单里点「Add a line」但还没选属性时，前端会带上一条
        ``[0, 0, {"attribute_id": False}]`` 命令：它既写不进库（``attribute_id`` 必填），
        也不该参与试写分析 —— 否则用户**一点按钮**就会收到
        ``Missing required value for the field 'Attribute' (attribute_id)``
        （见模块 ``AGENTS.md`` → L2 P4 陷阱 11）。这类不完整的行直接跳过，
        等用户选好属性自然会再算一次。
        """
        cleaned = []
        for command in commands or []:
            if (
                isinstance(command, (list, tuple))
                and len(command) == 3
                and command[0] == 0
                and not (command[2] or {}).get("attribute_id")
            ):
                continue
            cleaned.append(command)
        return cleaned

    def _analyze_variant_conversion_write(self, attribute_line_ids):
        """试写一次属性行（只写配置、不碰变体，随即回滚），据此判断这次改动的影响。

        关键点：**不能用原生写法当判据**。原生写法在「加属性」时本来就会删掉既有变体
        （它们不再匹配任何新组合），那正是我们要防的结果，不是要测量的现象。所以这里用
        ``create_product_product=False`` 只写属性行与取值（ptav）：既有变体毫发无损，
        既没有「先删再回滚」的副作用，也能在同一份保存点里算出改动后的配置、组合与默认归属。

        :param list attribute_line_ids: 本次要写入 ``attribute_line_ids`` 的命令。
        :return: dict：
            ``lost_variant_ids`` 受删取值影响、无法再锚定的既有变体 id；
            ``expected_count`` / ``before_count`` 改动后的组合数与既有变体数；
            ``needs_anchoring`` 走原生保存会不会丢变体（变体缺某个多取值行的取值 → True，
            这时必须自己锚定，见 ``write()``）；
            ``combinations`` 改动后的组合（取值 id + 标签 + 默认归属），供弹窗使用；
            ``specification`` 改动后的变体生成配置（属性 + 取值），回滚后依然可用
            （它只引用属性与 product.attribute.value，这些记录是客户端保存前就建好的）；
            ``dynamic_attributes`` 产品上「按需生成变体」的属性记录（空记录集 = 没有这类属性）。
        """
        self.ensure_one()
        # 还没选属性的新行（点 Add a line 后的第一态）不能进试写：必填缺失会直接把错误抛给用户
        attribute_line_ids = self._sanitize_attribute_line_commands(attribute_line_ids)
        variants = self.product_variant_ids
        # 改动前的属性：写入后就读不到「原来是什么」了，而台账要记「本次真正新加了哪些属性」
        # （谱系判定不看属性行，它按各变体携带的取值认来源，见 _find_variant_conversion_origin）
        before_lines = self._get_variant_conversion_attribute_lines()
        before_attributes = before_lines.attribute_id
        before_values = {
            variant: [(ptav.attribute_id.id, ptav.product_attribute_value_id.id)
                      for ptav in variant.product_template_attribute_value_ids]
            for variant in variants
        }

        savepoint = self.env.cr.savepoint()
        with savepoint:
            self.with_context(create_product_product=False).write({
                "attribute_line_ids": attribute_line_ids,
            })
            attribute_lines = self._get_variant_conversion_attribute_lines()
            self._check_variant_conversion_combination_cap(attribute_lines)
            specification = self._get_variant_conversion_specification()
            spec_attributes = self.env["product.attribute"]
            for spec in specification:
                spec_attributes |= spec["attribute"]
            # 默认归属：什么都不指定时「每条既有变体占哪个组合」（已有属性保持原取值、
            # 新加属性取本次第一个取值），与 _convert_to_multi_variant 的默认规则同源
            default_mapping = self._get_variant_conversion_default_mapping(specification)
            origin_by_values = {
                frozenset(values.ids): variant.id
                for variant, values in default_mapping.items()
            }
            combinations = []
            for ptavs in self._get_variant_conversion_combinations(attribute_lines):
                pav_ids = ptavs.product_attribute_value_id.ids
                combinations.append({
                    "values": pav_ids,
                    "label": self._get_variant_conversion_combination_label(ptavs),
                    "origin_variant_id": origin_by_values.get(frozenset(pav_ids), False),
                })
            # 「能不能再锚定」只看取值有没有被删：属性行被删掉不影响（那只是少一个属性轴），
            # 但凡属性还在配置里、而变体带着的取值已不在，这条变体就会被丢掉
            spec_values = {
                spec["attribute"].id: set(spec["values"].ids) for spec in specification
            }
            lost = []
            lost_value_ids = set()
            for variant, pairs in before_values.items():
                for attribute_id, value_id in pairs:
                    kept_values = spec_values.get(attribute_id)
                    if kept_values is not None and value_id not in kept_values:
                        lost.append(variant.id)
                        lost_value_ids.add(value_id)
            lost_pavs = self.env["product.attribute.value"].browse(sorted(lost_value_ids))
            lost_values_archived = bool(lost_pavs) and all(not value.active for value in lost_pavs)
            lost_value_names = ", ".join(lost_pavs.mapped("name"))
            # 「原生写法会不会丢变体」：只要某条既有变体没带上某个**多取值**属性行的取值，
            # 原生 _create_variant_ids 就会把它的组合判成「不完整」并删掉它
            # （按需分支只激活命中组合的变体、不新建）；单取值行原生会自己补到所有变体上，
            # 不需要本模块介入。命中时不能走「原生保存」，必须自己把锚点写下去。
            needs_anchoring = False
            for variant in variants:
                carried_lines = variant.product_template_attribute_value_ids.attribute_line_id
                for line in attribute_lines:
                    if line in carried_lines:
                        continue
                    if len(line.product_template_value_ids._only_active()) > 1:
                        needs_anchoring = True
                        break
                if needs_anchoring:
                    break
            analysis = {
                "dynamic_attributes": self._get_variant_conversion_dynamic_attributes(),
                "lost_variant_ids": lost,
                "lost_values_archived": lost_values_archived,
                "lost_value_names": lost_value_names,
                "expected_count": len(combinations),
                "before_count": len(variants),
                "needs_anchoring": needs_anchoring,
                "combinations": combinations,
                "specification": specification,
                "added_attributes": spec_attributes - before_attributes,
            }
            savepoint.rollback()
        return analysis

    def _parse_variant_conversion_mapping(self, payload):
        """把表单映射表回传的归属映射（JSON）解析成服务端要的三样东西。

        前端格式（``skip`` 是后加的，缺省即 False，老载荷照样认）::

            {"mapping": [{"values": [取值 id, ...],
                          "origin_variant_id": 既有变体 id 或 false,
                          "skip": true/false}, ...],
             "share_vendor_prices": true/false}

        每条 mapping 的含义是「改动后的这个组合由哪条既有变体继续承载」，没指定来源的就是
        新变体；``skip`` 为真是「这个组合**不生成变体**」。两者互斥：既有变体带着自己的
        库存、单据与发票，不能因为「这个组合不生成变体」被删掉（这里按**载荷里的组合**
        先判一次，改动后的归属在 ``_check_variant_conversion_skipped()`` 里按锚点再判一次）。

        这里只做「每条既有变体恰好一次、取值必须存在」的校验，其余校验交给
        ``_check_variant_conversion_mapping``。

        :return: ``(mapping, share_vendor_prices, skipped)``：
            ``mapping`` 是 ``{既有变体: 取值集合}``；
            ``skipped`` 是「不生成变体」的组合集合（每项是一组
            ``product.attribute.value`` id 的 ``frozenset``）。
        """
        self.ensure_one()
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError):
            payload = None
        if not isinstance(payload, dict) or not isinstance(payload.get("mapping"), list):
            raise UserError(_(
                "The variant ownership sent by the form could not be read. Reload the page and save again."))

        rows = payload["mapping"]
        share_vendor_prices = bool(payload.get("share_vendor_prices"))
        originals = self.product_variant_ids
        mapping = {}
        skipped = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            values = self.env["product.attribute.value"].browse(row.get("values") or [])
            if len(values) != len(values.exists()):
                raise UserError(_(
                    "The form sent unknown attribute values for the combination %(values)s of %(product)s.",
                    values=", ".join(values.mapped("display_name")) or "-",
                    product=self.display_name,
                ))
            # 不生成变体：先把组合记下来（它不许由任何既有变体承载 —— 那条互斥在下面统查）
            if row.get("skip"):
                skipped.add(frozenset(values.ids))
            origin_id = row.get("origin_variant_id")
            if not origin_id:
                continue
            variant = originals.filtered(lambda original: original.id == origin_id)
            if not variant:
                raise UserError(_(
                    "The form sent an ownership for variant %(variant)s, which is not a variant of %(product)s.",
                    variant=origin_id,
                    product=self.display_name,
                ))
            if variant in mapping:
                raise UserError(_(
                    "Variant %(variant)s was given two combinations; keep one combination per existing variant.",
                    variant=variant.display_name,
                ))
            mapping[variant] = values

        unmapped = originals - self.env["product.product"].browse(
            [variant.id for variant in mapping])
        if unmapped:
            raise UserError(_(
                "Every existing variant must keep a combination: %(variants)s has no combination. Save the product form again to get the ownership dialog.",
                variants=", ".join(unmapped.mapped("display_name")),
            ))
        for variant, values in mapping.items():
            if frozenset(values.ids) in skipped:
                raise UserError(_(
                    "The combination %(values)s is kept by the existing variant %(variant)s and cannot be marked as not created: that variant carries its own stock, orders and invoices. Move it to another combination first.",
                    values=", ".join(values.mapped("display_name")) or "-",
                    variant=variant.display_name,
                ))
        return mapping, share_vendor_prices, skipped

    def _check_variant_conversion_combination_cap(self, attribute_lines):
        """本次转换会落到多少个变体（组合数）超过 ``product.dynamic_variant_limit`` 就拒绝。

        必须在 ``itertools.product`` 枚举**之前**做：超限的配置先拒绝，而不是先把几十万个
        组合枚举出来再拒绝（T-018）。只数取值个数，不生成任何组合。算法与
        ``_get_variant_conversion_combinations()`` 一致：

        - 只有「立即」属性：``各属性有效取值数的乘积``；
        - 还有「按需生成」属性：``既有变体数 × 各「立即」属性有效取值数的乘积`` ——
          按需轴不展开（每条既有变体在自己的按需取值上各展开一份），所以要多乘变体数。
        """
        self.ensure_one()
        cap = int(self.env["ir.config_parameter"].sudo().get_param(
            "product.dynamic_variant_limit", 1000))
        managed_lines, fixed_lines = self._split_variant_conversion_lines(attribute_lines)
        total = len(self.product_variant_ids) if fixed_lines else 1
        if not total:
            return                                      # 没有既有变体：转换走原生（没有可锚定的目标）
        for line in (managed_lines if fixed_lines else attribute_lines):
            count = len(line.product_template_value_ids._only_active())
            if not count:
                return                                  # 没有有效取值的属性不产生组合
            total *= count
        if total > cap:
            raise UserError(_(
                "This configuration would create %(count)s combinations, above the limit of %(limit)s "
                "set by the system parameter product.dynamic_variant_limit. Reduce the number of values.",
                count=total,
                limit=cap,
            ))

    def _get_variant_conversion_specification(self):
        """当前（或演练后的）变体生成配置：属性 + 有效取值。"""
        self.ensure_one()
        specification = []
        for line in self._get_variant_conversion_attribute_lines():
            values = line.product_template_value_ids._only_active().product_attribute_value_id
            if values:
                specification.append({"attribute": line.attribute_id, "values": values})
        return specification

    def _get_variant_conversion_variant_options(self):
        """给弹窗用的既有变体候选项：id、组合标签、在手数量。"""
        self.ensure_one()
        quantities = self._get_variant_conversion_on_hand_quantities()
        return [{
            "id": variant.id,
            "label": "%s (%s)" % (
                variant.display_name,
                self._get_variant_conversion_combination_label(
                    variant.product_template_attribute_value_ids),
            ),
            # 没装 stock（或无读权限）时为 None：前端据此决定要不要展示在手数量
            "on_hand": quantities.get(variant.id),
        } for variant in self.product_variant_ids]

    def _get_variant_conversion_on_hand_quantities(self):
        """既有变体的在手数量；没装 stock 或当前用户无权读取时返回空字典。"""
        self.ensure_one()
        if "stock.quant" not in self.env:
            return {}
        quants = self.env["stock.quant"]
        if not quants.check_access_rights("read", raise_exception=False):
            return {}
        groups = quants._read_group(
            [("product_id", "in", self.product_variant_ids.ids),
             ("location_id.usage", "=", "internal")],
            ["product_id"],
            ["quantity:sum"],
        )
        return {product.id: quantity for product, quantity in groups}

    # ------------------------------------------------------------------
    # 核心转换
    # ------------------------------------------------------------------

    def _convert_to_multi_variant(self, specification, variant_mapping=None, share_vendor_prices=False,
                                  added_attributes=None, skipped_combinations=None):
        """给产品追加属性 / 取值，生成缺失的变体，并保留全部既有变体。

        :param list specification: 每个属性一项，形如::

                {"attribute": <product.attribute>,
                 "values": <product.attribute.value 记录集>}

            ``values`` 必须包含该属性当前已配置的全部取值（只允许追加，不允许删除）。
        :param dict variant_mapping: 「既有变体 → 转换后它占有的取值」的显式归属表，
            形如 ``{<product.product>: <product.attribute.value 记录集>, ...}``：
            每个属性恰好一个取值，缺省时按 ``_get_variant_conversion_default_mapping()``
            的规则补默认值（已有属性保持原取值、新加属性取本次的第一个取值）。
        :param bool share_vendor_prices: 是否把仅适用于原变体的供应商价格改为
            「适用于本产品的全部变体」。
        :param skipped_combinations: 用户在映射表里标了「不生成变体」的组合，形如
            ``{frozenset(取值 id), ...}`` —— 这些组合**不产出变体**：本次刚建出来的
            那一条会被丢掉（既有变体不会碰，见 ``_check_variant_conversion_skipped()``）。
            只对本次转换生效：以后再改属性，映射表会重新把它们列出来。
        :param added_attributes: 本次真正新加的属性（写进转换台账）。留空时按当前配置推断。

        谱系判定不需要「改动前的属性行快照」：来源是按**转换前各变体携带的取值**（进入本方法
        时先拍下的 `old_values`）来认的，属性行那时已经被 ``write()`` 写成目标配置也不影响。
        
        :return: 新创建的 product.product 记录集（不含被保留的既有变体）。
        :rtype: product.product
        """
        self.ensure_one()
        self._check_variant_conversion_allowed()
        self._check_variant_conversion_specification(specification)

        originals = self.product_variant_ids
        default_mapping = self._get_variant_conversion_default_mapping(specification)
        mapping = {}
        for variant in originals:
            mapping[variant] = (variant_mapping or {}).get(variant) or default_mapping[variant]
        self._check_variant_conversion_mapping(specification, mapping, originals)

        variant_limit = int(self.env["ir.config_parameter"].sudo().get_param(
            "product.dynamic_variant_limit", 1000))
        inherit_variant_data = self._get_variant_conversion_inherit_variant_data()
        separate_variant_prices = self._get_variant_conversion_separate_variant_prices()
        if self._get_variant_conversion_dynamic_attributes():
            # 「按需生成」的产品以后还会被 Odoo 在订单里新建变体，而分离会把模板级的
            # 供应商价格 / 价格表规则拆到既有变体上并删掉原记录 —— 那些新变体就再也取不到价了。
            # 所以这类产品**不做分离**（价格记录保持模板级，对所有变体生效），台账如实记 False。
            separate_variant_prices = False

        # 同一产品的转换串行化：避免两个会话同时改属性行，导致前置换算与实际不符
        self.env.cr.execute(
            "SELECT id FROM product_template WHERE id = %s FOR UPDATE", (self.id,))

        commands = []
        for spec in specification:
            line = self.attribute_line_ids.filtered(
                lambda ptal: ptal.active and ptal.attribute_id == spec["attribute"])
            value_ids = spec["values"].ids
            if line:
                # 已有属性行：写入「现有取值 + 新增取值」（只增不减，见前置校验）
                commands.append(Command.update(line.id, {"value_ids": [Command.set(value_ids)]}))
            else:
                commands.append(Command.create({
                    "attribute_id": spec["attribute"].id,
                    "value_ids": [Command.set(value_ids)],
                }))

        with self.env.cr.savepoint():
            # 转换前的快照：各变体的取值组合（谱系判定按它认来源）、本次真正「新加」的属性
            # （先做组合数上限检查：超限的配置在枚举前就拒绝，见 T-018）
            self._check_variant_conversion_combination_cap(
                self._get_variant_conversion_attribute_lines())
            old_values = {
                variant: variant.product_template_attribute_value_ids for variant in originals
            }
            new_attributes = (added_attributes if added_attributes is not None
                              else self._get_variant_conversion_added_attributes(specification))

            # ① 只写属性行与取值（ptav）：create_product_product=False 让 Odoo 跳过
            #    _create_variant_ids，这一步不会新建 / 删除 / 归档任何变体
            self.with_context(create_product_product=False).write({
                "attribute_line_ids": commands,
            })

            # ② 预检：用 Odoo 自己的组合规则算出转换后会存在的变体数，并确认每个
            #    「归属组合」不会被属性配置排除、也不会两个原变体撞到同一个组合
            attribute_lines = self._get_variant_conversion_attribute_lines()
            expected_count = self._count_possible_variant_combinations(attribute_lines)
            if expected_count < len(originals):
                raise UserError(_(
                    "This configuration would keep only %(count)s variants out of the %(existing)s variants of %(product)s: the attribute configuration of the product excludes some combinations. Adjust the attribute values first.",
                    count=expected_count,
                    existing=len(originals),
                    product=self.display_name,
                ))
            if expected_count > variant_limit:
                raise UserError(_(
                    "This configuration would create %(count)s variants, above the limit of %(limit)s set by the system parameter product.dynamic_variant_limit. Reduce the number of values.",
                    count=expected_count,
                    limit=variant_limit,
                ))
            anchors = self._get_variant_conversion_anchor_values(
                specification, mapping, attribute_lines)
            self._check_variant_conversion_anchors(originals, anchors)
            # 「不生成变体」：把载荷里的取值 id 翻译成**本产品**的 ptav 组合，并确认
            # 没有任何既有变体会因此被丢掉（改动后的锚点是最终口径）
            skipped = self._resolve_variant_conversion_skipped(
                skipped_combinations, attribute_lines)
            self._check_variant_conversion_skipped(anchors, skipped)

            # ③ 把每个既有变体锚定到它的归属组合：让下一步的 _create_variant_ids 认出
            #    「既有变体 = 某个归属组合」从而逐个复用它们（既不新建也不删除）
            for variant, anchor in anchors.items():
                variant.write({
                    "product_template_attribute_value_ids": [Command.set(anchor.ids)],
                })

            # ④ 交给 Odoo 生成缺失的组合；组合匹配上的既有变体被复用。
            #    注意：产品带「按需生成」属性时 Odoo **一个变体都不会新建**
            #    （``_create_variant_ids()`` 在该分支只激活命中组合的既有变体），
            #    所以「展开『立即』轴」应当存在的那些组合要我们自己补（T-039）——
            #    按需轴的其它取值不在本次计划里，仍然留给订单去创建。
            self._create_variant_ids()
            new_variants = self._create_variant_conversion_missing_variants(
                attribute_lines) or (self.product_variant_ids - originals)

            # ④b 标了「不生成变体」的组合：把本次**刚建出来**的那条变体丢掉。
            #     既有变体一条都不碰（``_check_variant_conversion_skipped()`` 已拦住），
            #     所以这里丢的全是本次新建、还没有任何库存 / 单据的记录。
            dropped = self._drop_variant_conversion_skipped_variants(originals, skipped)

            # ⑤ 后置断言：任何不符合预期的情况都整单回滚，不留半成品
            #    （预期数量扣掉本次丢掉的那些「不生成变体」的组合）
            self._check_variant_conversion_result(anchors, expected_count - len(dropped))
            new_variants = self.product_variant_ids - originals

            # ⑥ 显式记录归属：转换台账 + 谱系行 + 变体上的来源字段
            self._create_variant_conversion_lineage(
                originals, anchors, old_values, new_variants,
                new_attributes, attribute_lines, share_vendor_prices,
                inherit_variant_data, separate_variant_prices)

            # ⑦ 新变体按谱系来源继承变体级数据（成本 / 体积 / 重量），可在系统参数里关掉
            if inherit_variant_data:
                self._apply_variant_data_inheritance(new_variants)

            # ⑧ 价格数据（供应商价格 / 价格表规则）的归属：默认按变体分离（改一个不影响别的），
            #    勾了「应用到全部变体」才把供应商价格统一成模板级一份
            if separate_variant_prices:
                self._separate_variant_prices(originals, new_variants, share_vendor_prices)
            elif share_vendor_prices:
                self._share_vendor_prices_with_variants(originals)

            # ⑨ 扩展点 + chatter 留痕（T-020）：用 `new_attributes`（推断后的实际值）而不是
            #    入参 `added_attributes` —— 程序化调用不传它时，chatter 会拿到 None 而报错
            self._post_variant_conversion_hook(originals, new_variants, anchors)
            self._log_variant_conversion(originals, new_variants, new_attributes)

        return new_variants

    def _create_variant_conversion_combination(self, combination):
        """用 Odoo 自己的入口建「这个组合」的变体，返回建出来的变体（失败时返回空记录集）。

        走 ``product.template._create_product_variant()`` —— 销售配置器建变体调的就是它，
        所以行为与「订单期创建」完全一致。

        一个坑：它内部用 ``_is_combination_possible()``（``ignore_no_variant=False``）校验组合，
        要求组合里带上「不生成变体」属性行的取值；而本模块的组合枚举是 ``ignore_no_variant=True``
        的口径（那些取值不参与变体）。所以这里给每条「不生成变体」的属性行补一个占位取值
        （第一个有效取值）让校验通过 —— Odoo 建变体时会用 ``_without_no_variant_attributes()``
        把它们丢掉，不会写进变体。
        """
        self.ensure_one()
        no_variant_values = self.env["product.template.attribute.value"]
        for line in self.valid_product_template_attribute_line_ids.filtered(
                lambda ptal: ptal.attribute_id.create_variant == "no_variant"):
            no_variant_values |= line.product_template_value_ids._only_active()[:1]
        return self._create_product_variant(combination | no_variant_values)

    def _create_variant_conversion_missing_variants(self, attribute_lines):
        """补上本次转换计划里「还没有变体」的组合（只对带「按需生成」属性的产品有效）。

        Odoo 的 ``_create_variant_ids()`` 一遇到按需生成的属性就整段跳过新建
        （见其 ``if not tmpl_id.has_dynamic_attributes()``），所以「展开『立即』轴」得到的
        组合必须自己建 —— 建法用 Odoo 自己的 ``_create_product_variant()``（订单期同款）。
        按需轴的其它取值**不在本次计划里**，仍然等订单创建（这正是「按需」的含义：
        前端会把全部组合列出来让人分配，但没被任何既有变体认领的按需取值不会被预建）。

        :param attribute_lines: 转换后的属性行（``_get_variant_conversion_attribute_lines()``）。
        :return: 本次新建的变体记录集（没有按需属性、或计划里没有缺失组合时为空）。
        :rtype: product.product
        """
        self.ensure_one()
        _, fixed_lines = self._split_variant_conversion_lines(attribute_lines)
        if not fixed_lines:
            return self.env["product.product"]

        planned = self._get_variant_conversion_combinations(attribute_lines)
        existing = {
            frozenset(variant.product_template_attribute_value_ids.ids)
            for variant in self.with_context(active_test=False).product_variant_ids
        }
        created = self.env["product.product"]
        for combination in planned:
            signature = frozenset(combination.ids)
            if signature in existing:
                continue
            variant = self._create_variant_conversion_combination(combination)
            if not variant:
                raise UserError(_(
                    "The combination %(values)s of %(product)s could not be created; nothing has been changed.",
                    values=self._get_variant_conversion_combination_label(combination),
                    product=self.display_name,
                ))
            existing.add(signature)
            created |= variant
        return created

    def _resolve_variant_conversion_skipped(self, skipped_combinations, attribute_lines):
        """把「不生成变体」的组合从**取值 id** 翻译成**本产品**的 ptav 组合。

        映射表回传的是 ``product.attribute.value`` id（前端手里只有它），而变体上挂的是
        ``product.template.attribute.value``（ptav）；两者靠当前属性行一一对应。
        载荷过期（某个取值已经不在属性行里）时那一行对应不到任何组合，直接忽略。

        :return: ``{frozenset(ptav id), ...}``
        """
        self.ensure_one()
        ptav_by_value = {
            ptav.product_attribute_value_id.id: ptav.id
            for ptav in attribute_lines.product_template_value_ids._only_active()
        }
        signatures = set()
        for values in skipped_combinations or ():
            ptav_ids = []
            for value_id in values:
                ptav_id = ptav_by_value.get(value_id)
                if not ptav_id:
                    ptav_ids = None
                    break
                ptav_ids.append(ptav_id)
            if ptav_ids:
                signatures.add(frozenset(ptav_ids))
        return signatures

    def _drop_variant_conversion_skipped_variants(self, originals, skipped):
        """丢掉「不生成变体」的组合在**本次转换里刚建出来**的那条变体。

        只丢 ``originals`` 之外的（本次新建的）：它们还没有任何库存、单据或价格；
        既有变体一条都不碰 —— 「不生成变体」与「由既有变体保留」互斥，那条互斥在
        ``_check_variant_conversion_skipped()`` 里已经拦住，这里是第二道保险。

        :return: 本次丢掉的变体记录集。
        :rtype: product.product
        """
        self.ensure_one()
        if not skipped:
            return self.env["product.product"]
        created = self.with_context(active_test=False).product_variant_ids - originals
        to_drop = created.filtered(
            lambda variant: frozenset(variant.product_template_attribute_value_ids.ids) in skipped
        )
        if not to_drop:
            return to_drop
        # create_product_product=False：只删变体本身，绝不因为「它是这个产品的最后一条变体」
        # 而把产品模板连带删掉（原生 product.product.unlink() 有这个分支）
        to_drop.with_context(create_product_product=False).unlink()
        # 变体数 / 变体清单是算出来的（可能还留在缓存里）：作废缓存，让后面的后置断言读到真值
        self.invalidate_recordset(["product_variant_ids", "product_variant_count"])
        return to_drop

    # ------------------------------------------------------------------
    # 校验
    # ------------------------------------------------------------------

    def _check_variant_conversion_allowed(self):
        """入口校验：非组合产品、有变体、无归档变体。

        「按需生成」的属性**不再拒绝**（`T-039`）：转换只展开「立即」轴，
        按需轴按每条既有变体现带的取值钉住，不预建它的其它取值（那些留给 Odoo 在订单里创建）。
        """
        self.ensure_one()
        if self.type == "combo":
            raise UserError(_("A combo product cannot be converted into a multi-variant product."))
        if not self.product_variant_ids:
            raise UserError(_(
                "The product %(product)s has no variant to keep.",
                product=self.display_name,
            ))
        archived = self.with_context(active_test=False).product_variant_ids - self.product_variant_ids
        if archived:
            raise UserError(_(
                "The product %(product)s has %(count)s archived variants. Restore or delete them first: the conversion works on the variants that are in use and must not silently reactivate older ones.",
                product=self.display_name,
                count=len(archived),
            ))

    def _check_variant_conversion_specification(self, specification):
        """校验属性 / 取值配置，重点是「只允许追加」这一条。"""
        self.ensure_one()
        if not specification:
            raise UserError(_("Add at least one attribute before converting the product."))

        attributes = self.env["product.attribute"]
        for spec in specification:
            attribute = spec["attribute"]
            values = spec["values"]

            if attribute in attributes:
                raise UserError(_(
                    "Attribute %(attribute)s is used twice; keep a single line per attribute.",
                    attribute=attribute.display_name,
                ))
            attributes |= attribute

            if attribute.create_variant == "no_variant":
                raise UserError(_(
                    "Attribute %(attribute)s never creates variants, so it cannot be used to convert the product.",
                    attribute=attribute.display_name,
                ))
            # 「按需生成」的属性（create_variant == 'dynamic'）是支持的：转换**不预建**它的其它取值
            # （那些变体由 Odoo 在订单里创建），只把每条既有变体现带的取值钉住；
            # 映射表会把它的全部取值组合列出来供人分配，但只有被既有变体认领的取值才会现在创建。
            if not values:
                raise UserError(_(
                    "Attribute %(attribute)s needs at least one value.",
                    attribute=attribute.display_name,
                ))

            archived_values = values.filtered(lambda value: not value.active)
            if archived_values:
                raise UserError(_(
                    "Value %(value)s of attribute %(attribute)s is archived; only active attribute values generate variants.",
                    value=archived_values[0].name,
                    attribute=attribute.display_name,
                ))

            lines = self.attribute_line_ids.filtered(
                lambda ptal: ptal.active and ptal.attribute_id == attribute)
            if len(lines) > 1:
                raise UserError(_(
                    "Attribute %(attribute)s is configured twice on the product; keep a single attribute line before converting.",
                    attribute=attribute.display_name,
                ))
            if lines:
                current_values = lines.product_template_value_ids._only_active().product_attribute_value_id
                removed_values = current_values - values
                if removed_values:
                    raise UserError(_(
                        "Value %(values)s of attribute %(attribute)s cannot be removed from here: this wizard only adds values, so that no existing variant is ever deleted. Remove it from the attribute line of the product form if you really need to.",
                        values=", ".join(removed_values.mapped("display_name")),
                        attribute=attribute.display_name,
                    ))

    def _check_variant_conversion_mapping(self, specification, mapping, originals):
        """校验「既有变体 → 归属取值」：取值属于本次处理的属性、每个属性恰好一个。"""
        self.ensure_one()
        values_by_attribute = {
            spec["attribute"]: spec["values"] for spec in specification
        }
        for variant, values in mapping.items():
            if variant not in originals:
                raise UserError(_(
                    "Variant %(variant)s is not a variant of %(product)s.",
                    variant=variant.display_name,
                    product=self.display_name,
                ))
            seen = self.env["product.attribute"]
            for value in values:
                attribute = value.attribute_id
                if attribute not in values_by_attribute:
                    raise UserError(_(
                        "Value %(value)s of attribute %(attribute)s is not handled by this conversion.",
                        value=value.name,
                        attribute=attribute.display_name,
                    ))
                if value not in values_by_attribute[attribute]:
                    raise UserError(_(
                        "Value %(value)s is not one of the values kept for attribute %(attribute)s.",
                        value=value.name,
                        attribute=attribute.display_name,
                    ))
                if attribute in seen:
                    raise UserError(_(
                        "Variant %(variant)s would get several values of attribute %(attribute)s; keep one value per attribute.",
                        variant=variant.display_name,
                        attribute=attribute.display_name,
                    ))
                seen |= attribute

    def _check_variant_conversion_anchors(self, originals, anchors):
        """确认归属组合互不重复，且不会被 Odoo 自己的排除规则过滤掉。

        被过滤掉意味着该变体不会出现在待激活组合中，会被当作多余变体删掉 / 归档，必须提前拦住。
        """
        self.ensure_one()
        seen = {}
        for variant, anchor in anchors.items():
            signature = frozenset(anchor.ids)
            if signature in seen:
                raise UserError(_(
                    "The original variants %(first)s and %(second)s would both become %(values)s; give every original variant its own combination.",
                    first=seen[signature].display_name,
                    second=variant.display_name,
                    values=self._get_variant_conversion_combination_label(anchor),
                ))
            seen[signature] = variant

        possible = set(self._filter_combinations_impossible_by_config(
            [tuple(anchor) for anchor in anchors.values()], ignore_no_variant=True))
        for variant, anchor in anchors.items():
            if anchor not in possible:
                raise UserError(_(
                    "The values chosen for the original variant %(variant)s (%(values)s) are excluded by the attribute configuration of this product; choose another combination.",
                    variant=variant.display_name,
                    values=self._get_variant_conversion_combination_label(anchor),
                ))

    def _check_variant_conversion_skipped(self, anchors, skipped):
        """「不生成变体」的组合不能是任何既有变体的归属组合。

        标了「不生成变体」等于「这个组合不要变体」；而既有变体带着自己的库存、单据与发票，
        一条都不能这样被丢掉（L1 约束 1）。所以用户在映射表里要先把那条变体挪到别的组合
        （把它那一行改回「(new variant)」让出来），才能把这个组合标成不生成。
        """
        self.ensure_one()
        if not skipped:
            return
        for variant, anchor in anchors.items():
            if frozenset(anchor.ids) in skipped:
                raise UserError(_(
                    "The combination %(values)s is kept by the existing variant %(variant)s and cannot be marked as not created: that variant carries its own stock, orders and invoices. Move it to another combination first, or set its row back to (new variant) to release it.",
                    values=self._get_variant_conversion_combination_label(anchor),
                    variant=variant.display_name,
                ))

    def _check_variant_conversion_result(self, anchors, expected_count):
        """转换后的断言。任何一条不成立都抛异常，由外层的 savepoint 整单回滚。"""
        self.ensure_one()
        for variant, anchor in anchors.items():
            if not variant.exists() or not variant.active:
                raise UserError(_(
                    "One of the original variants of %(product)s disappeared during the conversion; nothing has been changed.",
                    product=self.display_name,
                ))
            variant.invalidate_recordset(["product_template_attribute_value_ids"])
            if variant.product_template_attribute_value_ids != anchor:
                raise UserError(_(
                    "The original variant of %(product)s that should carry %(values)s does not; nothing has been changed.",
                    product=self.display_name,
                    values=self._get_variant_conversion_combination_label(anchor),
                ))
        if self.product_variant_count != expected_count:
            raise UserError(_(
                "The product %(product)s has %(count)s variants instead of the expected %(expected)s; nothing has been changed.",
                product=self.display_name,
                count=self.product_variant_count,
                expected=expected_count,
            ))

    # ------------------------------------------------------------------
    # 辅助：属性行、组合、归属取值
    # ------------------------------------------------------------------

    def _get_variant_conversion_attribute_lines(self):
        """返回真正参与变体生成的属性行（有效，且属性不是「不生成变体」）。"""
        self.ensure_one()
        return self.valid_product_template_attribute_line_ids._without_no_variant_attributes()

    def _get_variant_conversion_dynamic_attributes(self):
        """产品上「按需生成变体」（``create_variant == 'dynamic'``）的属性。

        与 Odoo 自己的 ``has_dynamic_attributes()`` 同源（都看 ``valid_product_template_attribute_line_ids``），
        区别是返回**属性记录本身**：报错要点名是哪个属性，用户才知道去哪里改。
        """
        self.ensure_one()
        return self.valid_product_template_attribute_line_ids.attribute_id.filtered(
            lambda attribute: attribute.create_variant == "dynamic")

    def _get_variant_conversion_dynamic_message(self, dynamic_attributes):
        """建产品时带「按需生成」属性的报错文案（``create()`` 用；`T-039` 起只在这一处用）。

        这种属性 Odoo 不会预建变体（变体在第一次下单时创建），所以**建产品**时带上它，
        产品会一条变体都没有 —— 既卖不了，也进不了本模块的转换流程（转换要求至少有一条既有变体）。
        出路必须是**能走通的**：先建产品（不带这个属性）、保存，再把属性加到产品上
        （本模块会按归属保住既有变体），或者把该属性的变体生成方式改成「立即」再一起建。
        """
        return _(
            "The attribute %(attributes)s of %(product)s creates its variants on demand: Odoo itself creates "
            "those variants from the orders, so a product saved with such an attribute gets no variant at all "
            "(the first one is created the first time it is ordered). Create the product without that "
            "attribute and add it to the product afterwards — the conversion then keeps the existing variants "
            "— or set its Variant Creation to Instantly before saving.",
            attributes=", ".join(dynamic_attributes.mapped("display_name")),
            product=self.display_name,
        )

    def _get_variant_conversion_added_attributes(self, specification):
        """本次转换真正新增（产品上原本没有有效属性行）的属性。"""
        self.ensure_one()
        existing_attributes = self.attribute_line_ids.filtered("active").attribute_id
        added = self.env["product.attribute"]
        for spec in specification:
            if spec["attribute"] not in existing_attributes:
                added |= spec["attribute"]
        return added

    def _split_variant_conversion_lines(self, attribute_lines):
        """把属性行分成「展开的」与「固定取值的」两类。

        - 展开的（``create_variant == 'always'``）：转换会对它们的取值做笛卡尔积；
        - 固定的（``create_variant == 'dynamic'``，即「按需生成」）：**不预建**它的其它取值 ——
          变体由 Odoo 在订单里创建，转换只把每条既有变体占有的取值「钉住」。
          映射表会把它的全部取值组合都列出来供人分配（用户要求「充分列举所有可能的组合」），
          但只有**被既有变体认领**的取值才会现在创建。
        """
        self.ensure_one()
        fixed = attribute_lines.filtered(
            lambda line: line.attribute_id.create_variant == "dynamic")
        return attribute_lines - fixed, fixed

    def _get_variant_conversion_fixed_values(self, variant, fixed_lines):
        """某条既有变体在「按需生成」各轴上被钉住的取值（每个固定轴恰好一个 ptav）。

        规则：变体已经带着该轴的取值就用它（**不动既有数据**）；没有（例如本次刚加上这个
        按需属性）就用该轴第一个有效取值 —— 与 ``_get_variant_conversion_default_mapping()``
        的默认规则同源。
        """
        self.ensure_one()
        values = self.env["product.template.attribute.value"]
        for line in fixed_lines:
            ptavs = line.product_template_value_ids._only_active()
            values |= (variant.product_template_attribute_value_ids & ptavs)[:1] or ptavs[:1]
        return values

    def _get_variant_conversion_combinations(self, attribute_lines):
        """列出这次转换会落到哪些组合（每个组合是一组 ptav）。

        - **只有「立即」属性**：所有属性的取值做笛卡尔积，再按 Odoo 的排除规则过滤 ——
          与 ``_create_variant_ids`` 内的算法一致，因此可以直接当作转换后的变体总数来断言；
        - **有「按需生成」属性**：按需轴**不展开**（它的其它取值由 Odoo 在订单里创建），
          只把每条既有变体现在带的按需取值钉住，然后在「立即」各轴上展开一份 ——
          即「每条既有变体 × 各『立即』属性的取值组合」，最后同样过一遍排除规则与去重。

        两种情况下这个集合都等于「转换后应当存在的变体集合」，所以既能当预期数量断言，
        也能拿来生成清单。注意它**小于**映射表列出的组合数：前端会把按需轴的全部取值都列出来
        （用户要求「充分列举所有可能的组合」），没被既有变体认领的那些按需取值属于「等订单创建」，
        不在这个集合里。
        """
        self.ensure_one()
        managed_lines, fixed_lines = self._split_variant_conversion_lines(attribute_lines)
        if not fixed_lines:
            combinations = itertools.product(
                *[line.product_template_value_ids._only_active() for line in managed_lines])
            return list(self._filter_combinations_impossible_by_config(
                combinations, ignore_no_variant=True))
        managed_combinations = list(itertools.product(
            *[line.product_template_value_ids._only_active() for line in managed_lines]))
        combinations = []
        seen = set()
        for variant in self.product_variant_ids:
            fixed_values = self._get_variant_conversion_fixed_values(variant, fixed_lines)
            for managed in managed_combinations:
                combination = fixed_values | self.env["product.template.attribute.value"].concat(*managed)
                signature = frozenset(combination.ids)
                if signature in seen:
                    continue
                seen.add(signature)
                combinations.append(combination)
        return list(self._filter_combinations_impossible_by_config(
            combinations, ignore_no_variant=True))

    def _count_possible_variant_combinations(self, attribute_lines):
        """转换后会存在的变体数（= 组合数）。"""
        self.ensure_one()
        return len(self._get_variant_conversion_combinations(attribute_lines))

    def _get_variant_conversion_default_mapping(self, specification):
        """给每个既有变体算出一组默认归属取值。

        规则：变体在该属性上已有取值 → 保持原取值（记录不变、库存归属不变）；
        产品上原本没有的属性 → 取该属性在本次转换里的第一个取值。
        向导用它把「归属表」显式填好并逐行展示，用户可再逐行修改。
        """
        self.ensure_one()
        mapping = {}
        for variant in self.product_variant_ids:
            values = self.env["product.attribute.value"]
            for spec in specification:
                current = variant.product_template_attribute_value_ids.filtered(
                    lambda ptav: ptav.attribute_id == spec["attribute"]
                    and ptav.attribute_line_id.active
                ).product_attribute_value_id & spec["values"]
                values |= current[:1] or spec["values"][:1]
            mapping[variant] = values
        return mapping

    def _get_variant_conversion_anchor_values(self, specification, mapping, attribute_lines):
        """算出每个既有变体转换后应当占有的 ptav 组合（「默认组合」的推广）。

        每个属性取一个取值：优先用归属表（或变体自身已有取值），属性行只有一个取值时
        直接用它（那不会新增变体）。
        """
        self.ensure_one()
        anchors = {}
        for variant in self.product_variant_ids:
            mapped_values = mapping.get(variant, self.env["product.attribute.value"])
            anchor = self.env["product.template.attribute.value"]
            for line in attribute_lines:
                values = line.product_template_value_ids._only_active()
                mapped = mapped_values.filtered(
                    lambda value: value.attribute_id == line.attribute_id)
                if mapped:
                    ptavs = values.filtered(
                        lambda ptav: ptav.product_attribute_value_id in mapped)
                else:
                    ptavs = variant.product_template_attribute_value_ids.filtered(
                        lambda ptav: ptav.attribute_line_id == line) & values
                    if not ptavs:
                        if len(values) != 1:
                            raise UserError(_(
                                "Variant %(variant)s has no value for attribute %(attribute)s; choose which value it gets.",
                                variant=variant.display_name,
                                attribute=line.attribute_id.display_name,
                            ))
                        ptavs = values
                if len(ptavs) != 1:
                    raise UserError(_(
                        "Variant %(variant)s must get exactly one value of attribute %(attribute)s.",
                        variant=variant.display_name,
                        attribute=line.attribute_id.display_name,
                    ))
                anchor |= ptavs
            anchors[variant] = anchor
        return anchors

    def _get_variant_conversion_combination_label(self, ptavs):
        """把一组 ptav 拼成「属性: 取值, 属性: 取值」的可读文本，便于放进提示里。

        取值这里用 ``.name`` 而不是 ``.display_name``：``product.attribute.value``
        的 display_name 本身就是「属性: 取值」，用它会出现「属性: 属性: 取值」。
        """
        return ", ".join(
            "%s: %s" % (ptav.attribute_id.display_name, ptav.product_attribute_value_id.name)
            for ptav in ptavs
        )

    # ------------------------------------------------------------------
    # 辅助：谱系与供应商价格
    # ------------------------------------------------------------------

    def _create_variant_conversion_lineage(self, originals, anchors, old_values,
                                           new_variants, added_attributes, attribute_lines,
                                           share_vendor_prices, inherit_variant_data,
                                           separate_variant_prices):
        """写转换台账 + 变体谱系，并在 product.product 上留可搜索的来源字段。

        「原变体」的判定见 ``_find_variant_conversion_origin()``：新变体在**转换前就存在的
        取值**上与哪个原变体重合，它就派生自哪个原变体。判定不唯一时宁可不指，也不乱指。
        """
        self.ensure_one()
        spec_ptavs = self.env["product.template.attribute.value"]
        for line in attribute_lines:
            spec_ptavs |= line.product_template_value_ids._only_active()

        # 「转换前就存在的取值」：判定来源只认这些 ptav。本次新加的取值（新属性带来的、
        # 或给已有属性新增的取值）不参与匹配 —— 加取值时新变体正是「老取值 + 一个新取值」，
        # 把新取值也纳入比较会让它匹配不上任何原变体。
        old_ptavs = self.env["product.template.attribute.value"]
        for values in old_values.values():
            old_ptavs |= values

        rows = []
        for variant in originals:
            previous = old_values[variant]
            rows.append({
                "product_tmpl_id": self.id,
                "origin_variant_id": variant.id,
                "result_variant_id": variant.id,
                "is_kept": True,
                "origin_summary": self._get_variant_conversion_combination_label(previous),
                "result_summary": self._get_variant_conversion_combination_label(anchors[variant]),
                "added_value_ids": [Command.set(((anchors[variant] & spec_ptavs) - previous).ids)],
            })
        for variant in new_variants:
            origin = self._find_variant_conversion_origin(variant, originals, old_ptavs)
            if not origin and len(originals) == 1:
                origin = originals
            previous = old_values.get(origin, self.env["product.template.attribute.value"])
            current = variant.product_template_attribute_value_ids
            rows.append({
                "product_tmpl_id": self.id,
                "origin_variant_id": origin.id if origin else False,
                "result_variant_id": variant.id,
                "is_kept": False,
                "origin_summary": self._get_variant_conversion_combination_label(previous),
                "result_summary": self._get_variant_conversion_combination_label(current),
                "added_value_ids": [Command.set(((current & spec_ptavs) - previous).ids)],
            })

        conversion = self.env["product.variant.conversion"].create({
            "product_tmpl_id": self.id,
            "product_variant_count_before": len(originals),
            "product_variant_count_after": self.product_variant_count,
            "new_variant_count": len(new_variants),
            "added_attribute_ids": [Command.set(added_attributes.ids)],
            "share_vendor_prices": share_vendor_prices,
            "inherit_variant_data": inherit_variant_data,
            "separate_variant_prices": separate_variant_prices,
            "lineage_ids": [Command.create(row) for row in rows],
        })

        # product.product 上的来源字段：刻意冗余，换来列表 / 搜索 / 其它模块视图的直接可用
        self.env["product.product"].browse(
            list(originals.ids) + list(new_variants.ids)
        ).write({"variant_conversion_id": conversion.id})
        for row in rows:
            if not row["is_kept"] and row["origin_variant_id"]:
                self.env["product.product"].browse(
                    row["result_variant_id"]).variant_origin_id = row["origin_variant_id"]
        return conversion

    def _get_variant_conversion_origin_key(self, variant, old_ptavs):
        """变体组合里属于「转换前就存在的取值」的那部分（一组 ``product.template.attribute.value``）。

        本次新加的取值不在 `old_ptavs` 里，因此天然被排除 —— 这正是「加取值」时还能认出
        新变体来自哪条原变体的关键。
        """
        return frozenset(variant.product_template_attribute_value_ids.filtered(
            lambda ptav: ptav in old_ptavs))

    def _find_variant_conversion_origin(self, variant, originals, old_ptavs):
        """给新变体找唯一来源变体；找不到或判定不唯一时返回空记录集。

        判定规则：只看新变体**保留着老取值**的那些属性轴，候选原变体在这些轴上的取值必须与之
        完全一致。一致的有多个时取「最具体」的（老取值最多的）那个，仍然并列就判为不唯一。

        举例（原变体 Red/S、Green/S，本次给 Size 加取值 M）：

        - 新变体 Red/M 的老取值是 `{Color: Red}`；`Red/S` 投影到 Color 轴也正好是 `{Color: Red}`，
          `Green/S` 则是 `{Color: Green}` → 唯一命中 `Red/S` ✓
        - 新变体 Blue/M（Color 与 Size 都加了新取值）老取值为空 → 无从判断 → 不指 ✓

        :param product.product variant: 本次转换新建的变体。
        :param product.product originals: 转换前的变体（已被原地保留）。
        :param product.template.attribute.value old_ptavs: 转换前各变体携带过的取值。
        :return: 来源变体；判定不唯一 / 无候选时为空记录集。
        :rtype: product.product
        """
        key = self._get_variant_conversion_origin_key(variant, old_ptavs)
        # 一个老取值都没保留（例如那条唯一的属性上取的是新加的值）：没有可比的轴，
        # 多条原变体时无从判断，直接判为不唯一。
        if not key and len(originals) > 1:
            return self.env["product.product"]
        axes = {ptav.attribute_line_id for ptav in key}
        best = self.env["product.product"]
        best_size = -1
        ambiguous = False
        for original in originals:
            origin_key = self._get_variant_conversion_origin_key(original, old_ptavs)
            if frozenset(ptav for ptav in origin_key if ptav.attribute_line_id in axes) != key:
                continue
            if len(origin_key) > best_size:
                best, best_size, ambiguous = original, len(origin_key), False
            elif len(origin_key) == best_size:
                ambiguous = True
        if ambiguous or best_size < 0:
            return self.env["product.product"]
        return best

    def _post_variant_conversion_hook(self, originals, new_variants, anchors):
        """转换完成后的扩展点（在保存点内、写完台账与继承之后调用）。

        其它模块想给新变体补数据（默认参考号、图片、通知……）就继承这个方法，
        **不要**在 ``_convert_to_multi_variant()`` 里插代码。默认什么都不做。

        :param product.product originals: 转换前就存在的变体（已原地保留）。
        :param product.product new_variants: 本次新建的变体。
        :param dict anchors: ``{原有变体: 它现在携带的 ptav 组合}``。
        """
        return

    def _log_variant_conversion(self, originals, new_variants, added_attributes):
        """在产品 chatter 里留一条转换记录：台账之外，业务侧一眼可见（T-020）。

        注意 ``added_attributes`` 可能是**两个以上**属性（一次保存里同时加 Color 与 Size），
        取值必须走 ``mapped("display_name")`` —— 对多记录集取 ``.display_name`` 会直接抛
        ``ValueError: Expected singleton``，而这一步在转换的最后、会连累整单回滚（见 AGENTS.md → L2 P3 陷阱 5）。
        """
        if "mail.thread" not in self.env or not hasattr(self, "message_post"):
            return
        self.message_post(body=_(
            "Variant conversion: %(kept)s existing variants kept, %(created)s new variants created "
            "(added attributes: %(attributes)s).",
            kept=len(originals),
            created=len(new_variants),
            attributes=", ".join(added_attributes.mapped("display_name")) or "-",
        ))

    def _get_variant_conversion_bool_parameter(self, name, default=True):
        """读 ``product_variant.<name>`` 系统参数（布尔），缺省按 ``default``。

        关闭可写 ``0`` / ``false`` / ``no`` / ``off``（空值按 default 处理）。

        旧模块名时期（``product_variant_conversion.<name>``）设过的值仍然生效：
        新参数没设过时回退读旧名，这样改模块名不会让已有的开关静默失效。
        """
        params = self.env["ir.config_parameter"].sudo()
        raw = params.get_param("product_variant.%s" % name, "")
        if not str(raw).strip():
            raw = params.get_param("product_variant_conversion.%s" % name, "")
        if not str(raw).strip():
            raw = "1" if default else "0"
        return str(raw).strip().lower() not in ("0", "false", "no", "off", "")

    def _get_variant_conversion_inherit_variant_data(self):
        """新变体是否按谱系继承变体级数据（成本 / 体积 / 重量），默认开启。

        系统参数 ``product_variant.inherit_variant_data``：留空或 ``1`` / ``true`` 为开启，
        ``0`` / ``false`` / ``no`` / ``off`` 为关闭（关闭时新变体保持 Odoo 默认的空 / 0，
        由用户自己填）。

        为什么只继承这三样，见模块 ``README.md`` →「新变体继承策略」：
        条码有唯一性约束（`product.product._check_barcode_uniqueness()`）不能复制，
        内部参考号按本仓库 `product_reference` 的 L1 约束「多变体不共用」不能复制。
        """
        return self._get_variant_conversion_bool_parameter("inherit_variant_data")

    def _get_variant_conversion_inherited_fields(self):
        """按谱系继承的变体级字段名。

        基础三项：成本 / 体积 / 重量。装了 `product_dimension` 时补上它的尺寸四件套
        （单位 + 长宽高）—— 尺寸是体积的来源，只继承体积、丢下尺寸会让新变体出现
        「有体积、没尺寸」的错位。这里按字段是否存在判断，不硬依赖那个模块。
        """
        names = ["standard_price", "volume", "weight"]
        dimension_fields = (
            "dimension_unit",
            "dimension_length",
            "dimension_width",
            "dimension_height",
        )
        variant_fields = self.env["product.product"]._fields
        if all(name in variant_fields for name in dimension_fields):
            names += list(dimension_fields)
        return names

    def _get_variant_conversion_inheritance_values(self, origin):
        """要按谱系复制给新变体的字段值（来源变体 → 新变体）。

        尺寸四件套只在来源的尺寸**齐全**（长宽高都大于 0）时才复制：`product_dimension`
        的规则是「尺寸不全就把 Volume 归 0」，而来源本来就没填尺寸时，把尺寸复制过去会把
        刚继承来的体积冲掉（新旧变体就不一致了）。
        """
        values = {name: origin[name] for name in self._get_variant_conversion_inherited_fields()}
        dimension_sizes = ("dimension_length", "dimension_width", "dimension_height")
        if any(name in values for name in dimension_sizes) and not all(
                values.get(name) for name in dimension_sizes):
            for name in ("dimension_unit",) + dimension_sizes:
                values.pop(name, None)
        return values

    def _apply_variant_data_inheritance(self, new_variants):
        """把新变体的变体级字段从它的谱系来源（``variant_origin_id``）复制过来。

        :param product.product new_variants: 本次转换新建的变体。
        :return: 实际复制过数据的变体记录集。

        来源为空（谱系判定不唯一）时跳过该变体 —— 宁可留空让人自己填，也不乱指一个来源。
        """
        self.ensure_one()
        inherited = self.env["product.product"]
        for variant in new_variants:
            origin = variant.variant_origin_id
            if not origin:
                continue
            variant.write(self._get_variant_conversion_inheritance_values(origin))
            inherited |= variant
        return inherited
