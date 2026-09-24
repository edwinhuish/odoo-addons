# -*- coding: utf-8 -*-
"""「属性 ↔ 变体」映射表的自动化测试（服务端部分）。

覆盖的是映射表真正依赖的那几条判据：

1. 当前配置下每条变体都有组合（面板打开就是「已映射」）；
2. 加了属性之后，变体在新属性轴上没有取值 → **未映射**；
3. 用户在映射表里给变体选了取值 → 回到已映射；
4. 单取值轴与「按需生成」轴由 Odoo 自己补取值，不算未映射；
5. 会丢变体的改动（删取值）走不通，映射表拿到的是 blocked 而不是一堆未映射；
6. 还有未映射变体时，保存被拒绝且一个字都不写库。

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

    def test_mapping_state_field_feeds_the_panel(self):
        """``variant_mapping_state`` 是面板打开时用的初始状态：可解析的 JSON，内容同上。"""
        product = self._configure(self._create_product(), self.color, self.color.value_ids)
        state = json.loads(product.variant_mapping_state)
        self.assertEqual(len(state["rows"]), 2)
        self.assertEqual(state["unmapped_count"], 0)

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

    def test_on_demand_attribute_is_filled_in(self):
        """「按需生成」的轴按既有变体现带的取值钉住（没有就取第一个），不要求用户选。"""
        product = self._configure(self._create_product(), self.color, self.color.value_ids)
        commands = self._set_commands(product, self.origin, self.origin.value_ids)
        preview = product.get_variant_mapping_preview(commands)
        self.assertTrue(preview["dynamic"])
        self.assertEqual(preview["unmapped_count"], 0)
        for row in preview["rows"]:
            axis = self._axis(row, self.origin)
            self.assertTrue(axis["fixed"])
            self.assertTrue(axis["value_id"])

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
