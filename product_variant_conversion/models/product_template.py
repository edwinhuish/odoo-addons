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
"""

import itertools
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command


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
            "product_variant_conversion.product_variant_conversion_action")
        action["domain"] = [("product_tmpl_id", "=", self.id)]
        action["context"] = {"default_product_tmpl_id": self.id}
        return action

    # ------------------------------------------------------------------
    # 保存拦截：属性变更触发的归属确认
    # ------------------------------------------------------------------

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
        if affected["dynamic_attributes"]:
            raise UserError(_(
                "This product has an attribute that creates its variants on demand, so Odoo itself creates the new variants and there is nothing to confirm here. Set that attribute's variant creation mode to instantly if you want to decide the variant ownership.",
            ))
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
            # 既有变体一条不少、也不会新增变体（例如只加单取值属性、只加不生成变体的属性）→ 原生保存
            if mapping_payload:
                vals["variant_conversion_mapping"] = False
            return super().write(vals)
        if not mapping_payload:
            raise UserError(_(
                "This attribute change creates new variants of %(product)s: every existing variant has to be told which combination it keeps, so the save is held back until the ownership is confirmed from the product form. Save again from the form to get the dialog; if it does not show up, reload the page (Ctrl+F5) so that the module's assets are up to date.",
                product=self.display_name,
            ))
        # ① 先把用户那组属性命令写进去：create_product_product=False → 只写配置（属性行 + ptav），
        #    一条变体都不碰（原生写法在这一步就已经把既有变体删掉了）
        self.with_context(create_product_product=False).write({
            "attribute_line_ids": vals["attribute_line_ids"],
        })
        # ② 再做安全转换：按归属映射把每条既有变体锚定到它的组合上、只新增缺失的组合，
        #    并写下转换台账与谱系。此时配置已是目标配置，转换里那一步写属性行是幂等的。
        variant_mapping, share_vendor_prices = self._parse_variant_conversion_mapping(
            mapping_payload)
        self._convert_to_multi_variant(
            self._get_variant_conversion_specification(),
            variant_mapping=variant_mapping,
            share_vendor_prices=share_vendor_prices,
            # 属性行在第①步已经写成目标配置了，谱系与台账要用改动前的快照
            previous_attribute_lines=affected["previous_attribute_lines"],
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
        - ``combinations``：改动后的组合，``origin_variant_id`` 是「什么都不指定时」的默认归属。
        """
        self.ensure_one()
        affected = self._analyze_variant_conversion_write(attribute_line_ids)
        if affected["dynamic_attributes"]:
            return {
                "blocked": _(
                    "This product has an attribute that creates its variants on demand, so Odoo itself creates the new variants and there is nothing to confirm here. Set that attribute's variant creation mode to instantly if you want to decide the variant ownership.",
                ),
                "required": False,
                "variants": [],
                "combinations": [],
            }
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
            "variants": self._get_variant_conversion_variant_options(),
            "combinations": affected["combinations"],
        }

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
            ``combinations`` 改动后的组合（取值 id + 标签 + 默认归属），供弹窗使用；
            ``specification`` 改动后的变体生成配置（属性 + 取值），回滚后依然可用
            （它只引用属性与 product.attribute.value，这些记录是客户端保存前就建好的）。
        """
        self.ensure_one()
        variants = self.product_variant_ids
        # 改动前的属性行 / 属性：写入后就读不到「原来是什么」了，而谱系要靠它判断
        # 「新变体派生自哪条既有变体」，台账也要记「本次真正新加了哪些属性」
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
            self._check_variant_conversion_combination_cap(
                self._get_variant_conversion_attribute_lines())
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
            for ptavs in self._get_variant_conversion_combinations(
                    self._get_variant_conversion_attribute_lines()):
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
            analysis = {
                "dynamic_attributes": self.has_dynamic_attributes(),
                "lost_variant_ids": lost,
                "lost_values_archived": lost_values_archived,
                "lost_value_names": lost_value_names,
                "expected_count": len(combinations),
                "before_count": len(variants),
                "combinations": combinations,
                "specification": specification,
                "previous_attribute_lines": before_lines,
                "added_attributes": spec_attributes - before_attributes,
            }
            savepoint.rollback()
        return analysis

    def _parse_variant_conversion_mapping(self, payload):
        """把表单弹窗回传的归属映射（JSON）解析成 ``({既有变体: 取值集合}, 是否共享供应商价格)``。

        前端格式::

            {"mapping": [{"values": [取值 id, ...], "origin_variant_id": 既有变体 id 或 false}, ...],
             "share_vendor_prices": true/false}

        每条 mapping 的含义是「改动后的这个组合由哪条既有变体继续承载」，没指定来源的就是
        新变体。这里只做「每条既有变体恰好一次、取值必须存在」的校验，其余校验交给
        ``_check_variant_conversion_mapping``。
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
        for row in rows:
            origin_id = row.get("origin_variant_id") if isinstance(row, dict) else False
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
            values = self.env["product.attribute.value"].browse(row.get("values") or [])
            if len(values) != len(values.exists()):
                raise UserError(_(
                    "The form sent unknown attribute values for variant %(variant)s.",
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
        return mapping, share_vendor_prices

    def _check_variant_conversion_combination_cap(self, attribute_lines):
        """组合总数（各属性有效取值数的乘积）超过 ``product.dynamic_variant_limit`` 就拒绝。

        必须在 ``itertools.product`` 枚举**之前**做：超限的配置先拒绝，而不是先把几十万个
        组合枚举出来再拒绝（T-018）。只数取值个数，不生成任何组合。
        """
        self.ensure_one()
        cap = int(self.env["ir.config_parameter"].sudo().get_param(
            "product.dynamic_variant_limit", 1000))
        total = 1
        for line in attribute_lines:
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
                                  previous_attribute_lines=None, added_attributes=None):
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
        :param previous_attribute_lines: 改动**前**的变体生成属性行。留空时按当前配置推断
            （程序化调用的常态）；``write()`` 会从改动前的快照传进来，因为那时属性行已经
            被写成目标配置了，而谱系要靠改动前的属性轴判断「新变体派生自哪条既有变体」。
        :param added_attributes: 本次真正新加的属性（写进转换台账）。留空时按当前配置推断。
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
            # 转换前的快照：属性行、各变体的取值组合、以及本次真正「新加」的属性
            # （先做组合数上限检查：超限的配置在枚举前就拒绝，见 T-018）
            self._check_variant_conversion_combination_cap(
                self._get_variant_conversion_attribute_lines())
            old_lines = (previous_attribute_lines if previous_attribute_lines is not None
                         else self._get_variant_conversion_attribute_lines())
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

            # ③ 把每个既有变体锚定到它的归属组合：让下一步的 _create_variant_ids 认出
            #    「既有变体 = 某个归属组合」从而逐个复用它们（既不新建也不删除）
            for variant, anchor in anchors.items():
                variant.write({
                    "product_template_attribute_value_ids": [Command.set(anchor.ids)],
                })

            # ④ 交给 Odoo 生成缺失的组合；组合匹配上的既有变体被复用
            self._create_variant_ids()

            # ⑤ 后置断言：任何不符合预期的情况都整单回滚，不留半成品
            self._check_variant_conversion_result(anchors, expected_count)

            # ⑥ 显式记录归属：转换台账 + 谱系行 + 变体上的来源字段
            new_variants = self.product_variant_ids - originals
            self._create_variant_conversion_lineage(
                originals, anchors, old_values, old_lines, new_variants,
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

            # ⑨ 扩展点 + chatter 留痕（T-020）
            self._post_variant_conversion_hook(originals, new_variants, anchors)
            self._log_variant_conversion(originals, new_variants, added_attributes)

        return new_variants

    # ------------------------------------------------------------------
    # 校验
    # ------------------------------------------------------------------

    def _check_variant_conversion_allowed(self):
        """入口校验：非组合产品、有变体、无按需生成属性、无归档变体。"""
        self.ensure_one()
        if self.type == "combo":
            raise UserError(_("A combo product cannot be converted into a multi-variant product."))
        if not self.product_variant_ids:
            raise UserError(_(
                "The product %(product)s has no variant to keep.",
                product=self.display_name,
            ))
        if self.has_dynamic_attributes():
            raise UserError(_(
                "The product %(product)s creates variants on demand (a dynamic attribute is configured), so its variants are handled by Odoo itself.",
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
            if attribute.create_variant != "always":
                raise UserError(_(
                    "Attribute %(attribute)s creates variants on demand; set its variant creation mode to instantly before converting the product.",
                    attribute=attribute.display_name,
                ))
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

    def _get_variant_conversion_added_attributes(self, specification):
        """本次转换真正新增（产品上原本没有有效属性行）的属性。"""
        self.ensure_one()
        existing_attributes = self.attribute_line_ids.filtered("active").attribute_id
        added = self.env["product.attribute"]
        for spec in specification:
            if spec["attribute"] not in existing_attributes:
                added |= spec["attribute"]
        return added

    def _get_variant_conversion_combinations(self, attribute_lines):
        """按 Odoo 自身的组合规则列出转换后会存在的组合（每个组合是一组 ptav）。

        与 ``_create_variant_ids`` 内的算法一致（同样的取值集合、同样的排除规则过滤），
        因此既能直接当作转换后的变体总数来断言，也能拿来生成确认弹窗里的组合清单。
        """
        self.ensure_one()
        combinations = itertools.product(
            *[line.product_template_value_ids._only_active() for line in attribute_lines])
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

    def _create_variant_conversion_lineage(self, originals, anchors, old_values, old_lines,
                                           new_variants, added_attributes, attribute_lines,
                                           share_vendor_prices, inherit_variant_data,
                                           separate_variant_prices):
        """写转换台账 + 变体谱系，并在 product.product 上留可搜索的来源字段。

        「原变体」的判定：新变体在**转换前就存在的属性轴**上的取值组合，与哪个原变体重合，
        它就派生自哪个原变体（这些属性轴正是转换前各变体互相区分的地方）。判定不唯一时
        宁可不指，也不乱指。
        """
        self.ensure_one()
        spec_ptavs = self.env["product.template.attribute.value"]
        for line in attribute_lines:
            spec_ptavs |= line.product_template_value_ids._only_active()

        def _signature(variant):
            return frozenset(variant.product_template_attribute_value_ids.filtered(
                lambda ptav: ptav.attribute_line_id in old_lines).ids)

        origin_by_signature = {}
        for variant in originals:
            signature = _signature(variant)
            origin_by_signature[signature] = (
                False if signature in origin_by_signature else variant)

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
            origin = origin_by_signature.get(_signature(variant))
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
        """在产品 chatter 里留一条转换记录：台账之外，业务侧一眼可见（T-020）。"""
        if "mail.thread" not in self.env or not hasattr(self, "message_post"):
            return
        self.message_post(body=_(
            "Variant conversion: %(kept)s existing variants kept, %(created)s new variants created "
            "(added attributes: %(attributes)s).",
            kept=len(originals),
            created=len(new_variants),
            attributes=added_attributes.display_name or "-",
        ))

    def _get_variant_conversion_bool_parameter(self, name, default=True):
        """读 ``product_variant_conversion.<name>`` 系统参数（布尔），缺省按 ``default``。

        关闭可写 ``0`` / ``false`` / ``no`` / ``off``（空值按 default 处理）。
        """
        raw = self.env["ir.config_parameter"].sudo().get_param(
            "product_variant_conversion.%s" % name, "1" if default else "0")
        return str(raw).strip().lower() not in ("0", "false", "no", "off", "")

    def _get_variant_conversion_inherit_variant_data(self):
        """新变体是否按谱系继承变体级数据（成本 / 体积 / 重量），默认开启。

        系统参数 ``product_variant_conversion.inherit_variant_data``：留空或 ``1`` / ``true`` 为开启，
        ``0`` / ``false`` / ``no`` / ``off`` 为关闭（关闭时新变体保持 Odoo 默认的空 / 0，
        由用户自己填）。

        为什么只继承这三样，见模块 ``README.md`` →「新变体继承策略」：
        条码有唯一性约束（`product.product._check_barcode_uniqueness()`）不能复制，
        内部参考号按本仓库 `product_reference` 的 L1 约束「多变体不共用」不能复制。
        """
        return self._get_variant_conversion_bool_parameter("inherit_variant_data")

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
            variant.write({
                "standard_price": origin.standard_price,
                "volume": origin.volume,
                "weight": origin.weight,
            })
            inherited |= variant
        return inherited
