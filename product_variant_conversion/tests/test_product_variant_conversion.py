# -*- coding: utf-8 -*-
"""转换逻辑的自动化测试。

这一版的重点是「保存时拦截 + 归属确认」这条链路（服务端部分完全可以自动化）：

1. 属性变更会不会动到既有变体，由 ``get_variant_conversion_preview()`` 在保存前给出结论；
2. 会新增变体时，没有归属映射的写入必须被拦住（保存不会继续），
   带映射的写入则必须保住每一条既有 ``product.product`` 记录（id 不变）；
3. 会丢变体的改动（删取值 / 删属性）必须被拒绝，绝不静默删除；
4. 归属关系要能追溯：转换台账 + 谱系行 + ``product.product`` 上的来源字段。

跑法（本地开发环境）：

    task test -- product_variant_conversion --test-tags=/product_variant_conversion
    # 连库存 / 销售一起验证（把 stock、sale_management 一起装上）：
    task test -- product_variant_conversion,stock,sale_management --test-tags=/product_variant_conversion
"""

import json

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProductVariantConversion(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Attribute = cls.env["product.attribute"]

        cls.color = cls.Attribute.create({
            "name": "Test Color",
            "value_ids": [(0, 0, {"name": "Test Red"}), (0, 0, {"name": "Test Blue"})],
        })
        cls.color_red = cls.color.value_ids.filtered(lambda value: value.name == "Test Red")
        cls.color_blue = cls.color.value_ids.filtered(lambda value: value.name == "Test Blue")

        cls.size = cls.Attribute.create({
            "name": "Test Size",
            "value_ids": [(0, 0, {"name": "Test M"}), (0, 0, {"name": "Test L"})],
        })
        cls.size_m = cls.size.value_ids.filtered(lambda value: value.name == "Test M")
        cls.size_l = cls.size.value_ids.filtered(lambda value: value.name == "Test L")

        cls.material = cls.Attribute.create({
            "name": "Test Material",
            "create_variant": "no_variant",
            "value_ids": [(0, 0, {"name": "Test Steel"})],
        })
        cls.material_steel = cls.material.value_ids

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    def _create_product(self, name="Test Variant Product", attribute=None, values=None):
        """建产品；给了属性就顺带配上（配上两个取值即得到两个变体）。

        ``is_storable`` 由 stock 模块提供：没装 stock 时（本模块只依赖 product）
        不能带这个字段，否则建产品就报错。
        """
        vals = {"name": name, "type": "consu"}
        if "is_storable" in self.env["product.template"]._fields:
            vals["is_storable"] = True
        product = self.env["product.template"].create(vals)
        if attribute is not None:
            self._configure(product, attribute, values)
        return product

    def _configure(self, product, attribute, values):
        """把某个属性配到产品上：走「预览 → 需要就用预览的默认归属确认」这条正常链路。

        新建产品时 Odoo 已经建了 1 个变体，所以给它加多取值属性同样会触发归属确认，
        测试里也得按真实链路走一遍（这正是本模块要拦住的场景）。
        """
        commands = self._set_commands(product, attribute, values)
        preview = self._preview(product, commands)
        self.assertFalse(preview["blocked"])
        if preview["required"]:
            self._confirm(product, commands, self._payload(self._default_rows(preview)))
        else:
            product.write({"attribute_line_ids": commands})
            product.invalidate_recordset()
        return product

    def _variant_of(self, product, values):
        """按属性取值找变体（``values`` 为变体必须带上的 pav 记录集）。"""
        return product.product_variant_ids.filtered(
            lambda variant: variant.product_template_attribute_value_ids.product_attribute_value_id & values == values)

    def _set_commands(self, product, attribute, values):
        """把某个属性配成指定取值：已有属性行就更新，没有就新增一行。"""
        line = product.attribute_line_ids.filtered(lambda ptal: ptal.attribute_id == attribute)
        if line:
            return [(1, line.id, {"value_ids": [Command.set(values.ids)]})]
        return [(0, 0, {"attribute_id": attribute.id, "value_ids": [Command.set(values.ids)]})]

    def _preview(self, product, commands):
        return product.get_variant_conversion_preview(commands)

    def _combination_of(self, preview, values):
        """按取值集合从预览里取出对应的组合行。"""
        expected = frozenset(values.ids)
        matches = [
            combination for combination in preview["combinations"]
            if frozenset(combination["values"]) == expected
        ]
        self.assertEqual(
            len(matches), 1,
            "the combination %s should appear exactly once in the preview" % values)
        return matches[0]

    def _row(self, combination, origin=False):
        return {
            "values": combination["values"],
            "origin_variant_id": origin.id if origin else False,
        }

    def _payload(self, rows, share_vendor_prices=False):
        return {"mapping": rows, "share_vendor_prices": share_vendor_prices}

    def _confirm(self, product, commands, payload):
        """模拟「用户在弹窗里确认归属后保存」：属性变更与归属映射在同一次写入里提交。"""
        product.write({
            "attribute_line_ids": commands,
            "variant_conversion_mapping": json.dumps(payload),
        })
        product.invalidate_recordset()

    def _default_rows(self, preview):
        """按预览给的默认归属组装弹窗会回传的 mapping。"""
        return [
            self._row(combination, origin=self.env["product.product"].browse(
                combination["origin_variant_id"]))
            for combination in preview["combinations"]
        ]

    # ------------------------------------------------------------------
    # 保存拦截：需要归属确认
    # ------------------------------------------------------------------

    def test_adding_an_attribute_requires_the_ownership_mapping(self):
        """加属性会新增变体：没有归属映射时写入被拦住，且不改库。"""
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        with self.assertRaises(UserError):
            product.write({
                "attribute_line_ids": self._set_commands(product, self.size, self.size.value_ids),
            })
        self.assertFalse(product.attribute_line_ids.filtered(
            lambda ptal: ptal.attribute_id == self.size))
        self.assertEqual(product.product_variant_count, 2)

    def test_preview_reports_combinations_and_default_ownership(self):
        """预览要给出：是否需要确认、改动后的组合、既有变体的默认归属，且自己不改库。"""
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        red_original = self._variant_of(product, self.color_red)
        blue_original = self._variant_of(product, self.color_blue)

        preview = self._preview(
            product, self._set_commands(product, self.size, self.size.value_ids))

        self.assertFalse(preview["blocked"])
        self.assertTrue(preview["required"])
        self.assertEqual(len(preview["combinations"]), 4)
        self.assertEqual(len(preview["variants"]), 2)
        # 默认归属：已有属性保持原取值、新加属性取第一个取值（Test M）
        self.assertEqual(
            self._combination_of(preview, self.color_red + self.size_m)["origin_variant_id"],
            red_original.id,
        )
        self.assertEqual(
            self._combination_of(preview, self.color_blue + self.size_m)["origin_variant_id"],
            blue_original.id,
        )
        self.assertFalse(
            self._combination_of(preview, self.color_red + self.size_l)["origin_variant_id"])
        # 预览只是试写 + 回滚，不能真的改库
        self.assertFalse(product.attribute_line_ids.filtered(
            lambda ptal: ptal.attribute_id == self.size))
        self.assertEqual(product.product_variant_count, 2)

    def test_confirmed_ownership_keeps_every_original_variant(self):
        """确认归属后：两条原记录各自保留自己的组合，另外两个组合是新记录。"""
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        red_original = self._variant_of(product, self.color_red)
        blue_original = self._variant_of(product, self.color_blue)
        commands = self._set_commands(product, self.size, self.size.value_ids)

        preview = self._preview(product, commands)
        self._confirm(product, commands, self._payload(self._default_rows(preview)))

        self.assertEqual(product.product_variant_count, 4)
        self.assertTrue(red_original.exists() and blue_original.exists())
        self.assertEqual(red_original, self._variant_of(product, self.color_red + self.size_m))
        self.assertEqual(blue_original, self._variant_of(product, self.color_blue + self.size_m))
        self.assertEqual(
            product.product_variant_ids - red_original - blue_original,
            self._variant_of(product, self.color_red + self.size_l)
            + self._variant_of(product, self.color_blue + self.size_l),
        )

    def test_ownership_can_be_mapped_per_variant(self):
        """归属可以逐条交叉指定：Blue 那条记录改成 Blue + Test L。"""
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        red_original = self._variant_of(product, self.color_red)
        blue_original = self._variant_of(product, self.color_blue)
        commands = self._set_commands(product, self.size, self.size.value_ids)

        preview = self._preview(product, commands)
        rows = [
            self._row(self._combination_of(preview, self.color_red + self.size_m), red_original),
            self._row(self._combination_of(preview, self.color_blue + self.size_l), blue_original),
            self._row(self._combination_of(preview, self.color_red + self.size_l)),
            self._row(self._combination_of(preview, self.color_blue + self.size_m)),
        ]
        self._confirm(product, commands, self._payload(rows))

        self.assertEqual(product.product_variant_count, 4)
        self.assertEqual(blue_original, self._variant_of(product, self.color_blue + self.size_l))
        self.assertEqual(red_original, self._variant_of(product, self.color_red + self.size_m))

    def test_ownership_must_cover_every_existing_variant(self):
        """归属表必须覆盖每一条既有变体，少一条就拒绝。"""
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        commands = self._set_commands(product, self.size, self.size.value_ids)
        preview = self._preview(product, commands)
        rows = [
            self._row(combination)
            for combination in preview["combinations"]
            if not combination["origin_variant_id"]
        ]
        with self.assertRaises(UserError):
            self._confirm(product, commands, self._payload(rows))
        self.assertEqual(product.product_variant_count, 2)

    def test_two_originals_cannot_share_a_combination(self):
        """同一条既有变体被指定了两个组合时必须拒绝。"""
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        red_original = self._variant_of(product, self.color_red)
        commands = self._set_commands(product, self.size, self.size.value_ids)
        preview = self._preview(product, commands)
        rows = [
            self._row(self._combination_of(preview, self.color_red + self.size_m), red_original),
            self._row(self._combination_of(preview, self.color_red + self.size_l), red_original),
        ]
        with self.assertRaises(UserError):
            self._confirm(product, commands, self._payload(rows))
        self.assertEqual(product.product_variant_count, 2)

    def test_adding_a_value_needs_the_ownership_mapping(self):
        """给已有属性追加取值同样会新增变体，也要先确认归属。"""
        product = self._create_product()
        original = product.product_variant_id
        product.write({
            "attribute_line_ids": [(0, 0, {
                "attribute_id": self.size.id,
                "value_ids": [Command.set(self.size_m.ids)],
            })],
        })
        commands = self._set_commands(product, self.size, self.size_m + self.size_l)

        with self.assertRaises(UserError):
            product.write({"attribute_line_ids": commands})

        preview = self._preview(product, commands)
        self.assertTrue(preview["required"])
        rows = [
            self._row(self._combination_of(preview, self.size_m), original),
            self._row(self._combination_of(preview, self.size_l)),
        ]
        self._confirm(product, commands, self._payload(rows))

        self.assertEqual(product.product_variant_count, 2)
        self.assertEqual(original, self._variant_of(product, self.size_m))
        self.assertEqual(
            product.product_variant_ids - original, self._variant_of(product, self.size_l))

    def test_adding_a_single_value_attribute_needs_no_mapping(self):
        """只加一个取值的属性不会新增变体，也就不该弹窗，直接保存即可。"""
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        originals = product.product_variant_ids
        commands = self._set_commands(product, self.size, self.size_m)

        preview = self._preview(product, commands)
        self.assertFalse(preview["blocked"])
        self.assertFalse(preview["required"])

        product.write({"attribute_line_ids": commands})
        product.invalidate_recordset()
        self.assertEqual(product.product_variant_ids, originals)
        self.assertEqual(
            originals.product_template_attribute_value_ids.filtered(
                lambda ptav: ptav.attribute_id == self.size).product_attribute_value_id,
            self.size_m,
        )

    def test_non_variant_attribute_needs_no_mapping(self):
        """「不生成变体」的属性不影响变体，不该弹窗。"""
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        originals = product.product_variant_ids
        commands = self._set_commands(product, self.material, self.material_steel)

        preview = self._preview(product, commands)
        self.assertFalse(preview["blocked"])
        self.assertFalse(preview["required"])

        product.write({"attribute_line_ids": commands})
        product.invalidate_recordset()
        self.assertTrue(product.attribute_line_ids.filtered(
            lambda ptal: ptal.attribute_id == self.material))
        self.assertEqual(product.product_variant_ids, originals)

    def test_same_configuration_needs_no_mapping(self):
        """配置没变（只是重新提交同一组取值）时不需要确认。"""
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        commands = self._set_commands(product, self.color, self.color.value_ids)
        preview = self._preview(product, commands)
        self.assertFalse(preview["blocked"])
        self.assertFalse(preview["required"])
        product.write({"attribute_line_ids": commands})
        self.assertEqual(product.product_variant_count, 2)

    # ------------------------------------------------------------------
    # 保存拦截：会丢变体的改动一律拒绝
    # ------------------------------------------------------------------

    def test_removing_a_value_is_refused(self):
        """删取值会让带着它的变体失去归属，必须拒绝。"""
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        commands = self._set_commands(product, self.color, self.color_red)

        preview = self._preview(product, commands)
        self.assertTrue(preview["blocked"])
        with self.assertRaises(UserError):
            product.write({"attribute_line_ids": commands})
        self.assertEqual(product.product_variant_count, 2)
        self.assertEqual(
            product.attribute_line_ids.product_template_value_ids._only_active()
            .product_attribute_value_id, self.color.value_ids)

    def test_removing_an_attribute_line_is_refused(self):
        """删属性行会让变体数变少，同样拒绝（既有变体绝不静默删除）。"""
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        line = product.attribute_line_ids
        commands = [(2, line.id)]

        preview = self._preview(product, commands)
        self.assertTrue(preview["blocked"])
        with self.assertRaises(UserError):
            product.write({"attribute_line_ids": commands})
        self.assertEqual(product.product_variant_count, 2)

    # ------------------------------------------------------------------
    # 归属谱系（可追溯）
    # ------------------------------------------------------------------

    def test_conversion_and_lineage_are_recorded(self):
        """转换台账与谱系行要记清：谁被保留、谁派生自谁、这次加了什么取值。"""
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        red_original = self._variant_of(product, self.color_red)
        blue_original = self._variant_of(product, self.color_blue)
        commands = self._set_commands(product, self.size, self.size.value_ids)
        preview = self._preview(product, commands)
        self._confirm(product, commands, self._payload(self._default_rows(preview)))

        # 建产品时配 Color 那一步本身就是一次转换（原变体成了 Test Red），这里看最后一次
        self.assertEqual(len(product.variant_conversion_ids), 2)
        conversion = product.variant_conversion_ids.sorted("id")[-1]
        self.assertEqual(conversion.product_variant_count_before, 2)
        self.assertEqual(conversion.product_variant_count_after, 4)
        self.assertEqual(conversion.new_variant_count, 2)
        self.assertEqual(conversion.added_attribute_ids, self.size)

        kept = conversion.lineage_ids.filtered("is_kept")
        self.assertEqual(len(kept), 2)
        self.assertEqual(kept.origin_variant_id, kept.result_variant_id)
        self.assertEqual(
            kept.filtered(lambda line: line.result_variant_id == red_original)
            .added_value_ids.product_attribute_value_id,
            self.size_m,
        )

        added = conversion.lineage_ids - kept
        self.assertEqual(len(added), 2)
        for line in added:
            self.assertFalse(line.is_kept)
            # 新变体在「改动前就存在的属性轴」（这里只有 Color）上与来源变体一致
            self.assertEqual(
                line.origin_variant_id.product_template_attribute_value_ids.filtered(
                    lambda ptav: ptav.attribute_id == self.color).product_attribute_value_id,
                line.result_variant_id.product_template_attribute_value_ids.filtered(
                    lambda ptav: ptav.attribute_id == self.color).product_attribute_value_id,
            )
            self.assertEqual(line.added_value_ids.product_attribute_value_id, self.size_l)

        # product.product 上的来源字段：来源变体 / 所属转换都可直接搜索
        self.assertEqual(red_original.variant_conversion_id, conversion)
        self.assertEqual(blue_original.variant_conversion_id, conversion)
        self.assertEqual(added.result_variant_id.variant_conversion_id, conversion)
        self.assertFalse(red_original.variant_origin_id)
        for variant in added.result_variant_id:
            self.assertEqual(
                variant.variant_origin_id.product_template_attribute_value_ids.filtered(
                    lambda ptav: ptav.attribute_id == self.color).product_attribute_value_id,
                variant.product_template_attribute_value_ids.filtered(
                    lambda ptav: ptav.attribute_id == self.color).product_attribute_value_id,
            )

    # ------------------------------------------------------------------
    # 供应商价格
    # ------------------------------------------------------------------

    def test_vendor_prices_can_be_shared_with_all_variants(self):
        """弹窗里勾选后，仅挂在既有变体上的供应商价格改为适用于全部变体。"""
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        vendor_price = self.env["product.supplierinfo"].create({
            "partner_id": self.env["res.partner"].create({"name": "Test Vendor"}).id,
            "product_tmpl_id": product.id,
            "product_id": self._variant_of(product, self.color_red).id,
            "price": 10.0,
        })
        commands = self._set_commands(product, self.size, self.size.value_ids)
        preview = self._preview(product, commands)
        self._confirm(
            product, commands,
            self._payload(self._default_rows(preview), share_vendor_prices=True),
        )
        self.assertFalse(vendor_price.product_id)

    def test_vendor_prices_stay_on_the_variant_by_default(self):
        """不勾选时供应商价格仍只挂在原来那条变体上。"""
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        red_original = self._variant_of(product, self.color_red)
        vendor_price = self.env["product.supplierinfo"].create({
            "partner_id": self.env["res.partner"].create({"name": "Test Vendor"}).id,
            "product_tmpl_id": product.id,
            "product_id": red_original.id,
            "price": 10.0,
        })
        commands = self._set_commands(product, self.size, self.size.value_ids)
        preview = self._preview(product, commands)
        self._confirm(product, commands, self._payload(self._default_rows(preview)))
        self.assertEqual(vendor_price.product_id, red_original)

    # ------------------------------------------------------------------
    # 历史数据（装了 stock / sale 才会跑）
    # ------------------------------------------------------------------

    def test_stock_quant_stays_on_the_variant_it_belongs_to(self):
        """两个变体各有库存：转换后库存仍分别挂在原来那条记录上。"""
        if "stock.quant" not in self.env:
            self.skipTest("stock is not installed")
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        red_original = self._variant_of(product, self.color_red)
        blue_original = self._variant_of(product, self.color_blue)
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1)
        red_quant = self.env["stock.quant"].create({
            "product_id": red_original.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 12.0,
        })
        blue_quant = self.env["stock.quant"].create({
            "product_id": blue_original.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 5.0,
        })
        commands = self._set_commands(product, self.size, self.size.value_ids)
        preview = self._preview(product, commands)
        # 预览里能看到既有变体的在手数量，方便判断库存归属
        self.assertEqual(
            {option["id"]: option["on_hand"] for option in preview["variants"]},
            {red_original.id: 12.0, blue_original.id: 5.0},
        )
        self._confirm(product, commands, self._payload(self._default_rows(preview)))

        self.assertTrue(red_quant.exists() and blue_quant.exists())
        self.assertEqual(red_quant.product_id, red_original)
        self.assertEqual(blue_quant.product_id, blue_original)
        self.assertEqual(red_quant.quantity, 12.0)
        self.assertEqual(blue_quant.quantity, 5.0)
        self.assertEqual(
            self.env["stock.quant"].search_count([("product_id", "=", red_original.id)]), 1)

    def test_sales_order_line_stays_on_the_kept_variant(self):
        """销售订单行仍指向原来那条变体（不再是「已删除的变体」）。"""
        if "sale.order.line" not in self.env:
            self.skipTest("sale is not installed")
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        red_original = self._variant_of(product, self.color_red)
        order = self.env["sale.order"].create({
            "partner_id": self.env["res.partner"].create({"name": "Test Customer"}).id,
            "order_line": [(0, 0, {"product_id": red_original.id, "product_uom_qty": 3.0})],
        })
        commands = self._set_commands(product, self.size, self.size.value_ids)
        preview = self._preview(product, commands)
        self._confirm(product, commands, self._payload(self._default_rows(preview)))

        self.assertEqual(order.order_line.product_id, red_original)
        self.assertTrue(order.order_line.product_id.exists())
