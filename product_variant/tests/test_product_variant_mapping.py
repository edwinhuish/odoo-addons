# -*- coding: utf-8 -*-
"""「属性 ↔ 变体」映射表的自动化测试（服务端部分）。

覆盖的是映射表真正依赖的那几条判据：

1. 当前配置下每条变体都有组合（面板打开就是「已映射」）；
2. 加了属性之后，变体在新属性轴上没有取值 → **未映射**；
3. 用户在映射表里给变体选了取值 → 回到已映射；
4. 单取值轴与「按需生成」轴由 Odoo 自己补取值，不算未映射；
5. 会丢变体的改动（删取值）走不通，映射表拿到的是 blocked 而不是一堆未映射；
6. 还有未映射变体时，保存被拒绝且一个字都不写库；
7. 删掉唯一属性：带映射 → 那条变体原样留下（承载空组合）；不带映射 → 守卫照旧拦住；
8. 产品带归档变体时，哪怕是「不新增变体」的改动也不能走原生直写把归档变体悄悄激活。

跑法（本地开发环境）：

    task test -- product_variant --test-tags=/product_variant
"""

import json

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProductVariantMapping(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.color = cls.env["product.attribute"].create({
            "name": "Mapping Color",
            "value_ids": [(0, 0, {"name": "Map Red"}), (0, 0, {"name": "Map Blue"})],
        })
        cls.size = cls.env["product.attribute"].create({
            "name": "Mapping Size",
            "value_ids": [(0, 0, {"name": "Map M"}), (0, 0, {"name": "Map L"})],
        })
        cls.size_m = cls.size.value_ids.filtered(lambda value: value.name == "Map M")
        cls.size_l = cls.size.value_ids.filtered(lambda value: value.name == "Map L")
        cls.origin = cls.env["product.attribute"].create({
            "name": "Mapping Origin",
            "create_variant": "dynamic",
            "value_ids": [(0, 0, {"name": "Map CN"}), (0, 0, {"name": "Map US"})],
        })
        cls.origin_cn = cls.origin.value_ids.filtered(lambda value: value.name == "Map CN")

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    def _create_product(self, name="Mapping Product"):
        vals = {"name": name, "type": "consu"}
        if "is_storable" in self.env["product.template"]._fields:
            vals["is_storable"] = True
        return self.env["product.template"].create(vals)

    def _configure(self, product, attribute, values):
        """把属性配到产品上，走「预览 → 需要就确认归属」这条正常链路。"""
        commands = self._set_commands(product, attribute, values)
        preview = product.get_variant_conversion_preview(commands)
        self.assertFalse(preview["blocked"])
        if preview["required"]:
            mapping = [{
                "values": combination["values"],
                "origin_variant_id": combination["origin_variant_id"],
            } for combination in preview["combinations"]]
            product.write({
                "attribute_line_ids": commands,
                "variant_conversion_mapping": json.dumps(
                    {"mapping": mapping, "share_vendor_prices": False}),
            })
        else:
            product.write({"attribute_line_ids": commands})
        product.invalidate_recordset()
        return product

    def _set_commands(self, product, attribute, values):
        line = product.attribute_line_ids.filtered(lambda ptal: ptal.attribute_id == attribute)
        if line:
            return [(1, line.id, {"value_ids": [Command.set(values.ids)]})]
        return [(0, 0, {"attribute_id": attribute.id, "value_ids": [Command.set(values.ids)]})]

    def _axis(self, row, attribute):
        """取某一行在某个属性轴上的那一列。"""
        axes = [axis for axis in row["axes"] if axis["attribute_id"] == attribute.id]
        self.assertEqual(len(axes), 1, "attribute %s should have one column" % attribute.name)
        return axes[0]

    def _selection(self, product, attribute, values_by_variant):
        """按「变体 → 该属性轴上选中的取值」组装映射表会回传的选择。"""
        selection = {}
        for variant, value in values_by_variant.items():
            selection[str(variant.id)] = {str(attribute.id): value.id}
        return selection

    # ------------------------------------------------------------------
    # 当前配置：每条变体都有自己的组合
    # ------------------------------------------------------------------

    def test_current_configuration_maps_every_variant(self):
        product = self._configure(self._create_product(), self.color, self.color.value_ids)
        self.assertEqual(len(product.product_variant_ids), 2)
        preview = product.get_variant_mapping_preview()
        self.assertFalse(preview["blocked"])
        self.assertEqual(len(preview["rows"]), 2)
        self.assertEqual(preview["unmapped_count"], 0)
        for row in preview["rows"]:
            self.assertTrue(row["mapped"])
            self.assertEqual(self._axis(row, self.color)["value_id"] in self.color.value_ids.ids, True)

    def test_panel_initial_state_comes_from_the_preview(self):
        """面板挂载时拿到的初始状态就是 ``get_variant_mapping_preview()`` 的结果。

        ``variant_mapping_state`` 只是给 widget 一个挂载点：**不做 compute、不落库** ——
        做成 compute 会在每次 onchange 里被求值，而那时表单里还没保存的行带 ``NewId``，
        序列化会直接抛 ``TypeError``（见 AGENTS.md → L2 P4 陷阱 12）。
        """
        product = self._configure(self._create_product(), self.color, self.color.value_ids)
        preview = product.get_variant_mapping_preview()
        self.assertEqual(len(preview["rows"]), 2)
        self.assertEqual(preview["unmapped_count"], 0)

        field = self.env["product.template"]._fields["variant_mapping_state"]
        self.assertFalse(field.compute, "挂载点字段不能再做 compute")
        self.assertFalse(field.store, "挂载点字段不落库")

    # ------------------------------------------------------------------
    # 加属性：变体失去组合 → 未映射
    # ------------------------------------------------------------------

    def test_adding_an_attribute_leaves_every_variant_unmapped(self):
        product = self._configure(self._create_product(), self.color, self.color.value_ids)
        commands = self._set_commands(product, self.size, self.size.value_ids)
        preview = product.get_variant_mapping_preview(commands)
        self.assertFalse(preview["blocked"])
        self.assertEqual(preview["unmapped_count"], 2)
        for row in preview["rows"]:
            self.assertFalse(row["mapped"])
            self.assertFalse(self._axis(row, self.size)["value_id"])
            # 已有的属性轴保持原取值，只有新轴需要用户选
            self.assertTrue(self._axis(row, self.color)["value_id"])

    def test_picking_a_value_maps_the_variant_again(self):
        product = self._configure(self._create_product(), self.color, self.color.value_ids)
        commands = self._set_commands(product, self.size, self.size.value_ids)
        variants = product.product_variant_ids
        selection = self._selection(product, self.size, {
            variants[0]: self.size_m,
            variants[1]: self.size_l,
        })
        preview = product.get_variant_mapping_preview(commands, selection)
        self.assertEqual(preview["unmapped_count"], 0)
        by_variant = {row["variant_id"]: row for row in preview["rows"]}
        self.assertEqual(
            self._axis(by_variant[variants[0].id], self.size)["value_id"], self.size_m.id)
        self.assertEqual(
            self._axis(by_variant[variants[1].id], self.size)["value_id"], self.size_l.id)
        # 选完之后这次改动会新建的组合只剩「另一个取值」那两个
        self.assertEqual(len(preview["new_combinations"]), 2)

    def test_unmapped_variants_block_the_save(self):
        """还有变体未映射时保存被拒绝，且属性配置一个字都不写。"""
        product = self._configure(self._create_product(), self.color, self.color.value_ids)
        commands = self._set_commands(product, self.size, self.size.value_ids)
        with self.assertRaises(UserError):
            product.write({"attribute_line_ids": commands})
        product.invalidate_recordset()
        self.assertFalse(product.attribute_line_ids.filtered(
            lambda line: line.attribute_id == self.size))

    # ------------------------------------------------------------------
    # 由 Odoo 自己补取值的轴不算未映射
    # ------------------------------------------------------------------

    def test_single_value_attribute_is_filled_in(self):
        """单取值属性由 Odoo 写到所有变体上（不新增变体），不需要用户选。"""
        single = self.env["product.attribute"].create({
            "name": "Mapping Single",
            "value_ids": [(0, 0, {"name": "Map Only"})],
        })
        product = self._configure(self._create_product(), self.color, self.color.value_ids)
        commands = self._set_commands(product, single, single.value_ids)
        preview = product.get_variant_mapping_preview(commands)
        self.assertEqual(preview["unmapped_count"], 0)
        for row in preview["rows"]:
            axis = self._axis(row, single)
            self.assertTrue(axis["fixed"])
            self.assertEqual(axis["value_id"], single.value_ids.id)

    def test_on_demand_attribute_needs_an_explicit_mapping(self):
        """「按需生成」的轴同样要求用户显式映射，不替用户决定「保留哪个取值」。

        既有变体没有这个轴（本次新加）→ 未映射；用户挑一个取值后 → 已映射。
        （按需轴只是**不预建**它的其它取值，``T-039``，不代表可以自动选一个。）
        """
        product = self._configure(self._create_product(), self.color, self.color.value_ids)
        commands = self._set_commands(product, self.origin, self.origin.value_ids)
        preview = product.get_variant_mapping_preview(commands)
        self.assertTrue(preview["dynamic"])
        self.assertEqual(preview["unmapped_count"], 2, "新加的按需轴：既有变体都还没有取值")
        for row in preview["rows"]:
            axis = self._axis(row, self.origin)
            self.assertFalse(axis["fixed"])
            self.assertFalse(axis["value_id"])

        # 用户逐条挑好取值 → 未映射清零
        selection = self._selection(product, self.origin, {
            variant: self.origin.value_ids[index]
            for index, variant in enumerate(product.product_variant_ids)
        })
        mapped = product.get_variant_mapping_preview(commands, selection)
        self.assertEqual(mapped["unmapped_count"], 0)
        for row in mapped["rows"]:
            self.assertTrue(self._axis(row, self.origin)["value_id"])

    def test_snapshot_carries_variants_and_attribute_kinds(self):
        """快照 = 面板编辑期唯一的服务端数据：既有变体带的取值 + 各属性的变体生成方式。

        它只描述**已经保存的事实**，所以表单里那些没保存的行不会影响它 —— 面板据此在前端算。
        """
        product = self._configure(self._create_product(), self.color, self.color.value_ids)
        snapshot = product.get_variant_mapping_snapshot()
        self.assertEqual(len(snapshot["variants"]), 2)
        for variant in snapshot["variants"]:
            self.assertTrue(variant["label"])
            self.assertEqual(len(variant["values"]), 1, "既有变体只带着 Color 一个轴")
            self.assertEqual(list(variant["values"])[0], str(self.color.id))
        self.assertEqual(snapshot["attributes"][str(self.color.id)]["create_variant"], "always")
        self.assertEqual(snapshot["attributes"][str(self.origin.id)]["create_variant"], "dynamic")
        # 装没装 stock 都会给这个键（没装时为 None）
        self.assertIn("on_hand", snapshot["variants"][0])
        # 已保存的属性行基线：前端拿它 + getChanges 的命令拼出「当前编辑态」
        self.assertEqual(len(snapshot["lines"]), 1)
        self.assertEqual(snapshot["lines"][0]["attribute_id"], self.color.id)
        self.assertEqual(sorted(snapshot["lines"][0]["value_ids"]), sorted(self.color.value_ids.ids))
        # 取值字典：id → 名称 + 归属属性（前端手里只有 id，名称都从这里查）
        self.assertEqual(
            snapshot["values"][str(self.color.value_ids[0].id)]["attribute_id"], self.color.id)

    # ------------------------------------------------------------------
    # 会丢变体的改动：给面板的是 blocked，不是「未映射」
    # ------------------------------------------------------------------

    def test_dropping_a_value_is_reported_as_blocked(self):
        product = self._configure(self._create_product(), self.color, self.color.value_ids)
        commands = self._set_commands(product, self.color, self.color.value_ids[0])
        preview = product.get_variant_mapping_preview(commands)
        self.assertTrue(preview["blocked"])
        self.assertEqual(preview["rows"], [])
        self.assertEqual(preview["unmapped_count"], 0)

    # ------------------------------------------------------------------
    # 还没选属性的新行：不能报错，也不能被拿去试写
    # ------------------------------------------------------------------

    def test_attribute_line_without_attribute_is_skipped(self):
        """点 Add a line 后的第一态（只有 value_ids、没有 attribute_id）不该炸。

        这条命令写不进库（attribute_id 必填），拿去试写就会把
        「Missing required value for the field 'Attribute'」直接抛给用户，
        所以清洗时把它丢掉；剩下的命令为空 → 按「当前配置」算，正常返回。
        """
        product = self._configure(self._create_product(), self.color, self.color.value_ids)
        commands = [(0, 0, {"value_ids": [Command.set([])]})]

        self.assertEqual(product._sanitize_attribute_line_commands(commands), [])

        preview = product.get_variant_mapping_preview(commands)
        self.assertFalse(preview.get("incomplete"))
        self.assertFalse(preview["blocked"])
        self.assertEqual(len(preview["rows"]), 2, "被丢掉的是半成品行，当前配置照常算")

        legacy = product.get_variant_conversion_preview(commands)
        self.assertFalse(legacy["blocked"])
        self.assertFalse(legacy["required"])

    def test_clearing_the_attribute_of_a_line_keeps_the_native_message(self):
        """把已有行的属性清空：Odoo 原生会给出解释性报错，不能被试写吞掉。

        这一类不完整写法清洗不掉（不是「新建空行」），试写时由原生守卫先抛
        ``UserError``；我们只兜 ``NotNullViolation`` 那种裸的必填缺失，
        原生的解释性文案要原样透出去，否则用户看不懂为什么改不了。
        """
        product = self._configure(self._create_product(), self.color, self.color.value_ids)
        line = product.attribute_line_ids.filtered(lambda ptal: ptal.attribute_id == self.color)
        commands = [(1, line.id, {"attribute_id": False})]
        self.assertEqual(product._sanitize_attribute_line_commands(commands), commands)

        with self.assertRaises(UserError) as caught:
            product.get_variant_mapping_preview(commands)
        self.assertIn("cannot transform the attribute", str(caught.exception))

    def test_incomplete_line_does_not_hide_the_complete_ones(self):
        """半成品行被丢掉，同一次提交里的正常行照样参与分析。"""
        product = self._configure(self._create_product(), self.color, self.color.value_ids)
        commands = [
            (0, 0, {"value_ids": [Command.set([])]}),                       # 还没选属性
            self._set_commands(product, self.size, self.size.value_ids)[0],  # 完整的新属性行
        ]
        self.assertEqual(len(product._sanitize_attribute_line_commands(commands)), 1)
        preview = product.get_variant_mapping_preview(commands)
        self.assertFalse(preview.get("incomplete"))
        self.assertFalse(preview["blocked"])
        # 加了尺码：既有两条变体都缺这一轴 → 未映射
        self.assertEqual(preview["unmapped_count"], 2)

    # ------------------------------------------------------------------
    # 删掉唯一的属性：那条变体由映射继续承载「空组合」
    # ------------------------------------------------------------------

    def test_removing_the_only_attribute_keeps_the_existing_variant(self):
        """删掉产品上唯一的属性后，那条既有变体必须原样留下（只丢掉它带的取值）。

        原生写法会先删属性行，而 ``product_attribute_guards.py`` 里「不许删带着在用变体的
        属性行」的守卫会拦在那里。映射表已经说明「这条变体继续承载空组合」，所以带映射
        保存时守卫要放行 —— 前提（变体会被连坐删掉 / 归档）不成立。
        """
        product = self._create_product()
        self._configure(product, self.color, self.color.value_ids[0])
        variant = product.product_variant_ids
        self.assertEqual(len(variant), 1, "单取值配置：一条变体")
        line = product.attribute_line_ids
        self.assertTrue(variant.product_template_attribute_value_ids, "变体带着 Color 的取值")

        product.write({
            "attribute_line_ids": [Command.delete(line.id)],
            "variant_conversion_mapping": json.dumps({
                "mapping": [{"values": [], "origin_variant_id": variant.id}],
                "share_vendor_prices": False,
            }),
        })
        product.invalidate_recordset()
        variant.invalidate_recordset()

        self.assertFalse(product.attribute_line_ids, "属性行已删掉")
        self.assertEqual(product.product_variant_ids, variant, "还是原来那条变体，没有新建")
        self.assertTrue(variant.active, "变体没有被归档")
        self.assertFalse(
            variant.product_template_attribute_value_ids, "空组合：不再带任何取值")

    def test_removing_the_only_attribute_without_mapping_is_still_blocked(self):
        """没带映射时守卫照旧拦住：没人认领那条变体，不能替用户把它处理掉。"""
        product = self._create_product()
        self._configure(product, self.color, self.color.value_ids[0])
        line = product.attribute_line_ids
        with self.assertRaises(UserError) as caught:
            product.write({"attribute_line_ids": [Command.delete(line.id)]})
        self.assertIn("Removing the attribute", str(caught.exception))
        self.assertEqual(len(product.product_variant_ids), 1, "一个字都没写库")

    # ------------------------------------------------------------------
    # 「不生成变体」：某些组合这次不要变体
    # ------------------------------------------------------------------

    def test_skipped_combination_creates_no_variant(self):
        """映射表里标了「不生成变体」的组合，保存之后**不产出变体**。

        Odoo 原生会把「立即」轴的取值笛卡尔积**全部**建出来（``_create_variant_ids()``），
        本模块在转换末尾把标了的那一组合刚建出来的变体丢掉 —— 它是本次才建出来的，
        还没有任何库存 / 单据；既有变体一条都不碰。
        """
        product = self._configure(self._create_product(), self.color, self.color.value_ids)
        self.assertEqual(len(product.product_variant_ids), 2)
        red = self.color.value_ids.filtered(lambda value: value.name == "Map Red")

        # 加 Size(M / L)：4 个组合，既有两条变体按默认归属各占 Red/M 与 Blue/M
        commands = self._set_commands(product, self.size, self.size.value_ids)
        preview = product.get_variant_conversion_preview(commands)
        self.assertTrue(preview["required"])
        self.assertEqual(len(preview["combinations"]), 4)

        mapping = []
        for combination in preview["combinations"]:
            values = combination["values"]
            mapping.append({
                "values": values,
                "origin_variant_id": combination["origin_variant_id"],
                # Red + L 这一行标成「不生成变体」（没有既有变体占着它）
                "skip": red.id in values and self.size_l.id in values,
            })
        product.write({
            "attribute_line_ids": commands,
            "variant_conversion_mapping": json.dumps(
                {"mapping": mapping, "share_vendor_prices": False}),
        })
        product.invalidate_recordset()

        self.assertEqual(len(product.product_variant_ids), 3, "4 个组合里少了标了「不生成变体」的那个")
        combinations = [
            set(variant.product_template_attribute_value_ids.product_attribute_value_id.ids)
            for variant in product.product_variant_ids
        ]
        self.assertNotIn({red.id, self.size_l.id}, combinations, "Red + L 没有变体")
        self.assertIn({red.id, self.size_m.id}, combinations, "Red + M 还是原来那条变体")

    def test_skipping_a_combination_kept_by_an_existing_variant_is_refused(self):
        """既有变体占着的组合不能标「不生成变体」：那等于要删掉一条带着库存与单据的变体。"""
        product = self._configure(self._create_product(), self.color, self.color.value_ids)
        red = self.color.value_ids.filtered(lambda value: value.name == "Map Red")
        kept = product.product_variant_ids.filtered(
            lambda variant: red in variant.product_template_attribute_value_ids
                            .product_attribute_value_id)
        self.assertEqual(len(kept), 1)

        commands = self._set_commands(product, self.size, self.size.value_ids)
        preview = product.get_variant_conversion_preview(commands)
        mapping = []
        for combination in preview["combinations"]:
            values = combination["values"]
            mapping.append({
                "values": values,
                "origin_variant_id": combination["origin_variant_id"],
                # Red + M 正由那条既有变体保留着，却把它标成「不生成变体」
                "skip": red.id in values and self.size_m.id in values,
            })
        with self.assertRaises(UserError) as caught:
            with self.env.cr.savepoint():
                product.write({
                    "attribute_line_ids": commands,
                    "variant_conversion_mapping": json.dumps(
                        {"mapping": mapping, "share_vendor_prices": False}),
                })
        self.assertIn("cannot be marked as not created", str(caught.exception))

        product.invalidate_recordset()
        kept.invalidate_recordset()
        self.assertTrue(kept.exists(), "那条既有变体没有被删掉")
        self.assertEqual(len(product.product_variant_ids), 2, "整单回滚：变体数没变")

    # ------------------------------------------------------------------
    # 归档变体：不能靠「组合数没变」的原生直写把它悄悄激活
    # ------------------------------------------------------------------

    def test_archived_variants_cannot_slip_through_the_native_save(self):
        """产品带归档变体时，即便改动「不新增变体」也必须被拒绝，不能交给原生直写。

        原生的 ``_create_variant_ids()`` 匹配组合时会一并考虑归档变体（``active_test=False``），
        命中就 ``write({'active': True})`` —— 老变体会被悄悄复活，库存与单据重新暴露在界面上。

        拦住它靠的是这条**不变量**：归档变体若还带着某个活组合，那个组合必然计入
        ``expected_count``，而 ``before_count`` 只数**启用**变体，于是
        ``expected_count > before_count``，流程落到转换路径，由
        ``_check_variant_conversion_allowed()`` 以「先恢复或删除归档变体」拒绝。
        原生直写分支没有后置断言，所以这条用例把这个不变量钉住
        （见 ``models/product_template.py`` → ``write()`` 里的注释）。
        """
        product = self._configure(self._create_product(), self.color, self.color.value_ids)
        variants = product.product_variant_ids
        self.assertEqual(len(variants), 2)
        archived = variants[1]
        archived.write({"active": False})
        active = product.product_variant_ids
        self.assertEqual(len(active), 1, "归档后只剩一条启用变体")

        # 加一个单取值属性：组合数 2 = 1（Color 剩余取值）× 1（新属性），
        # 「不新增变体」的形态 —— 正是原生直写会走的形状
        single = self.env["product.attribute"].create({
            "name": "Mapping Single",
            "value_ids": [(0, 0, {"name": "Map One"})],
        })
        commands = self._set_commands(product, single, single.value_ids)
        payload = json.dumps({
            "mapping": [{
                "values": (active.product_template_attribute_value_ids
                           .product_attribute_value_id.ids + single.value_ids.ids),
                "origin_variant_id": active.id,
            }],
            "share_vendor_prices": False,
        })

        # 用保存点模拟 Web 层：UserError 抛出时整个请求回滚（否则 write() 里第①步
        # 「只写配置」已写的属性行会留在事务里 —— 那是调用方要不要回滚的问题，
        # 前端请求会因为报错整单回滚，这里用保存点还原同样的结果）
        with self.assertRaises(UserError) as caught:
            with self.env.cr.savepoint():
                product.write({
                    "attribute_line_ids": commands,
                    "variant_conversion_mapping": payload,
                })
        self.assertIn("archived variants", str(caught.exception))

        product.invalidate_recordset()
        archived.invalidate_recordset()
        self.assertEqual(len(product.product_variant_ids), 1, "归档变体没有被悄悄激活")
        self.assertEqual(
            len(product.with_context(active_test=False).product_variant_ids), 2,
            "两条变体都还在（一条启用、一条归档）")
        self.assertFalse(archived.active, "归档状态没有被改写")
        self.assertFalse(
            product.attribute_line_ids.filtered(lambda line: line.attribute_id == single),
            "整单回滚：新属性行没有留下")
