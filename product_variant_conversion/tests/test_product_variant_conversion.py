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
from unittest import mock

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

    # ------------------------------------------------------------------
    # 字段归属（T-016）：谁是真身、谁是桥接，以及转换后值落在哪
    # ------------------------------------------------------------------

    def test_field_storage_layers_match_the_audit(self):
        """把「属性归属审计」钉成升级闸门：Odoo 一旦改动存储层级，这里必须先失败。

        结论（对照模块 README →「属性归属审计」）：
        - 条码 / 内部参考号 / 成本 / 体积 / 重量：**真身在变体上**（存储字段），
          模板侧那几个是「单变体桥接」（compute + inverse，只在单变体时落到变体）；
        - 销售价：**只有模板级**（变体上的 `lst_price` 是计算值，写回模板）。
        """
        template_fields = self.env["product.template"]._fields
        variant_fields = self.env["product.product"]._fields

        for name in ("barcode", "default_code", "standard_price", "volume", "weight"):
            with self.subTest(field=name):
                self.assertFalse(
                    variant_fields[name].compute,
                    "%s 在变体上应当是存储字段（真身）" % name,
                )
                self.assertTrue(
                    template_fields[name].compute,
                    "%s 在模板上应当是 compute 出来的桥接字段" % name,
                )
                self.assertTrue(
                    template_fields[name].inverse,
                    "%s 在模板上应当有 inverse（写回唯一变体）" % name,
                )

        # 销售价没有变体级存储：变体上的 list_price 是 _inherits 委托（related 到模板）来的，
        # 变体上真正可写的是 lst_price（计算值 = 模板价 + 属性加价，写回模板）
        self.assertEqual(
            self.env["product.product"]._inherits,
            {"product.template": "product_tmpl_id"},
        )
        list_price_variant = variant_fields["list_price"]
        self.assertEqual(list_price_variant.related, "product_tmpl_id.list_price")
        self.assertFalse(list_price_variant.store)
        self.assertTrue(variant_fields["lst_price"].compute)
        self.assertFalse(template_fields["list_price"].compute)

    def test_variant_level_values_stay_on_the_kept_variant(self):
        """单变体产品里「看起来挂在产品上」的那些字段，转换后仍在原记录（默认变体）上。

        这正是本模块**不需要任何数据迁移**的原因：值本来就在那条唯一的 ``product.product``
        记录上，而转换只做「保留原记录 + 新增缺失组合」，一个字节都不搬。
        """
        product = self._create_product()
        original = product.product_variant_id
        original.write({
            "barcode": "1234567890123",
            "default_code": "KEEP-001",
            "standard_price": 12.5,
            "volume": 0.25,
            "weight": 3.5,
        })
        product.list_price = 99.0

        commands = self._set_commands(product, self.size, self.size.value_ids)
        preview = self._preview(product, commands)
        rows = [
            self._row(self._combination_of(preview, self.size_m), original),
            self._row(self._combination_of(preview, self.size_l)),
        ]
        self._confirm(product, commands, self._payload(rows))
        product.invalidate_recordset()
        original.invalidate_recordset()

        new_variant = product.product_variant_ids - original
        self.assertEqual(len(new_variant), 1)

        # ① 默认变体 = 保留的那条原记录：变体级字段一个都没变
        self.assertEqual(original.barcode, "1234567890123")
        self.assertEqual(original.default_code, "KEEP-001")
        self.assertEqual(original.standard_price, 12.5)
        self.assertEqual(original.volume, 0.25)
        self.assertEqual(original.weight, 3.5)

        # ② 模板级字段全变体共享，转换不影响
        self.assertEqual(product.list_price, 99.0)

        # ③ 新变体：成本 / 体积 / 重量按谱系继承来源（默认开启，见「新变体继承策略」），
        #    参考号与条码刻意不复制（条码有唯一性约束、参考号按 product_reference 不共用）
        self.assertEqual(new_variant.variant_origin_id, original)
        self.assertEqual(new_variant.standard_price, 12.5)
        self.assertEqual(new_variant.volume, 0.25)
        self.assertEqual(new_variant.weight, 3.5)
        self.assertFalse(new_variant.barcode)
        self.assertFalse(new_variant.default_code)

        # ④ 多变体状态下，模板侧的桥接字段读出来是空 / 0 —— Odoo 原生语义
        #    （`_compute_template_field_from_variant_field` 只在单变体时镜像变体值），
        #    不是数据丢失：真值在上面那条变体上，前端去变体表单 / 变体列表看。
        self.assertFalse(product.barcode)
        self.assertFalse(product.default_code)
        self.assertEqual(product.volume, 0.0)
        self.assertEqual(product.weight, 0.0)
        self.assertEqual(product.standard_price, 0.0)

        # ⑤ 谱系行上的关联展示字段（前端「Variant Lineage」里看到的就是这些）：
        #    取值来自结果变体本身，所以保留的那条显示原值、新变体那行是空的
        kept_line = product.lineage_ids.filtered("is_kept")
        self.assertEqual(len(kept_line), 1)
        self.assertEqual(kept_line.result_default_code, "KEEP-001")
        self.assertEqual(kept_line.result_barcode, "1234567890123")
        self.assertEqual(kept_line.result_standard_price, 12.5)
        added_line = product.lineage_ids - kept_line
        self.assertEqual(len(added_line), 1)
        self.assertFalse(added_line.result_default_code)
        self.assertFalse(added_line.result_barcode)

    # ------------------------------------------------------------------
    # 新变体按谱系继承变体级数据（T-016）
    # ------------------------------------------------------------------

    def test_new_variants_inherit_variant_level_data(self):
        """新变体从谱系来源（Derived From）继承成本 / 体积 / 重量，但不碰参考号与条码。

        只继承这三样的理由（见模块 README →「新变体继承策略」）：
        条码有唯一性约束（`product.product._check_barcode_uniqueness()`）无法复制；
        内部参考号按本仓库 `product_reference` 的 L1 约束「多变体不共用」不能复制。
        """
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        red = self._variant_of(product, self.color_red)
        blue = self._variant_of(product, self.color_blue)
        red.write({
            "default_code": "RED-001", "barcode": "1111111111111",
            "standard_price": 10.0, "volume": 0.1, "weight": 1.0,
        })
        blue.write({
            "default_code": "BLUE-001", "barcode": "2222222222222",
            "standard_price": 20.0, "volume": 0.2, "weight": 2.0,
        })

        commands = self._set_commands(product, self.size, self.size.value_ids)
        preview = self._preview(product, commands)
        self._confirm(product, commands, self._payload(self._default_rows(preview)))

        new_variants = product.product_variant_ids - red - blue
        self.assertEqual(len(new_variants), 2)
        for variant in new_variants:
            origin = variant.variant_origin_id
            self.assertTrue(origin, "a new variant should always have a lineage origin")
            self.assertEqual(variant.standard_price, origin.standard_price)
            self.assertEqual(variant.volume, origin.volume)
            self.assertEqual(variant.weight, origin.weight)
            # 参考号与条码刻意不复制
            self.assertFalse(variant.default_code)
            self.assertFalse(variant.barcode)

        # 台账记下这次启用了继承；来源本身没有被改动
        self.assertTrue(product.variant_conversion_ids.sorted("id")[-1].inherit_variant_data)
        self.assertEqual(red.standard_price, 10.0)
        self.assertEqual(blue.volume, 0.2)
        self.assertEqual(blue.weight, 2.0)

    def test_shared_references_move_to_the_kept_variant_when_installed(self):
        """装了 product_reference 时：单变体产品上的「产品级共享参考号」交接给被保留的变体。

        产品表单在多变体时整块隐藏参考号区域（该模块 L1「多变体不共用」），不交接的话这些行
        既看不到也改不了 —— 用户会以为转换把参考号弄丢了。

        跑法：`task test -- product_variant_conversion,product_reference --test-tags=/product_variant_conversion`
        （本模块不硬依赖 product_reference，未安装时这条用例自动跳过）。
        """
        if "reference_code_line_ids" not in self.env["product.template"]._fields:
            self.skipTest("product_reference is not installed")
        product = self._create_product()
        original = product.product_variant_id
        product.reference_code_line_ids = [Command.create({"reference_code": "CUST-SHARED"})]
        original.variant_reference_code_line_ids = [
            Command.create({"reference_code": "VAR-OWN"})
        ]

        commands = self._set_commands(product, self.size, self.size.value_ids)
        preview = self._preview(product, commands)
        rows = [
            self._row(self._combination_of(preview, self.size_m), original),
            self._row(self._combination_of(preview, self.size_l)),
        ]
        self._confirm(product, commands, self._payload(rows))

        new_variant = product.product_variant_ids - original
        self.assertEqual(len(new_variant), 1)
        self.assertEqual(
            set(original.variant_reference_code_line_ids.mapped("reference_code")),
            {"CUST-SHARED", "VAR-OWN"},
        )
        self.assertFalse(new_variant.variant_reference_code_line_ids)
        self.assertFalse(product.reference_code_line_ids)
        self.assertFalse(product.reference_code_index)
        self.assertEqual(
            set(original.variant_reference_code_index.split("\n")),
            {"CUST-SHARED", "VAR-OWN"},
        )

    def test_shared_reference_stays_when_variant_already_has_the_same_code(self):
        """变体上已有同码时，产品级那条留在原地：不删用户数据、也不撞唯一约束。"""
        if "reference_code_line_ids" not in self.env["product.template"]._fields:
            self.skipTest("product_reference is not installed")
        product = self._create_product()
        original = product.product_variant_id
        product.reference_code_line_ids = [Command.create({"reference_code": "DUP-CODE"})]
        original.variant_reference_code_line_ids = [
            Command.create({"reference_code": "DUP-CODE"})
        ]

        commands = self._set_commands(product, self.size, self.size.value_ids)
        preview = self._preview(product, commands)
        rows = [
            self._row(self._combination_of(preview, self.size_m), original),
            self._row(self._combination_of(preview, self.size_l)),
        ]
        self._confirm(product, commands, self._payload(rows))

        self.assertEqual(product.reference_code_line_ids.mapped("reference_code"), ["DUP-CODE"])
        self.assertEqual(
            original.variant_reference_code_line_ids.mapped("reference_code"), ["DUP-CODE"]
        )

    def test_new_variants_inherit_variant_dimensions_when_installed(self):
        """装了 product_dimension 时：新变体的尺寸（单位 + 长宽高）也随谱系继承。

        跑法：`task test -- product_variant_conversion,product_dimension --test-tags=/product_variant_conversion`
        （本模块不硬依赖 product_dimension，未安装时这条用例自动跳过）。
        """
        if "dimension_unit" not in self.env["product.product"]._fields:
            self.skipTest("product_dimension is not installed")
        product = self._create_product()
        original = product.product_variant_id
        original.write({
            "dimension_unit": "cm",
            "dimension_length": 50.0,
            "dimension_width": 40.0,
            "dimension_height": 30.0,
        })
        self.assertAlmostEqual(original.volume, 0.06, places=6)

        commands = self._set_commands(product, self.size, self.size.value_ids)
        preview = self._preview(product, commands)
        rows = [
            self._row(self._combination_of(preview, self.size_m), original),
            self._row(self._combination_of(preview, self.size_l)),
        ]
        self._confirm(product, commands, self._payload(rows))

        new_variant = product.product_variant_ids - original
        self.assertEqual(len(new_variant), 1)
        self.assertEqual(new_variant.dimension_unit, "cm")
        self.assertAlmostEqual(new_variant.dimension_length, 50.0)
        self.assertAlmostEqual(new_variant.dimension_width, 40.0)
        self.assertAlmostEqual(new_variant.dimension_height, 30.0)
        self.assertAlmostEqual(new_variant.volume, 0.06, places=6)

    def test_adding_a_value_maps_new_variants_to_the_right_origin(self):
        """给已有属性加取值：新变体按「另一个属性轴上的取值」准确挂到对应原变体上。

        这是最常见的一种转换。旧实现比对的是「转换前存在的属性轴上的取值组合」，而新变体身上
        那个**新加的取值**也落在这些轴上，于是它永远匹配不上任何原变体 —— 只有一条原变体时
        才靠兜底规则勉强指对，多条原变体时新变体就成了「无来源」。
        """
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        self._configure(product, self.size, self.size_m)
        red_m = self._variant_of(product, self.color_red + self.size_m)
        blue_m = self._variant_of(product, self.color_blue + self.size_m)
        self.assertEqual(len(product.product_variant_ids), 2)

        # 给 Size 加取值 L：新增 Red/L 与 Blue/L 两条变体
        commands = self._set_commands(product, self.size, self.size_m + self.size_l)
        preview = self._preview(product, commands)
        rows = [
            self._row(self._combination_of(preview, self.color_red + self.size_m), red_m),
            self._row(self._combination_of(preview, self.color_blue + self.size_m), blue_m),
            self._row(self._combination_of(preview, self.color_red + self.size_l)),
            self._row(self._combination_of(preview, self.color_blue + self.size_l)),
        ]
        self._confirm(product, commands, self._payload(rows))

        self.assertEqual(len(product.product_variant_ids), 4)
        red_l = self._variant_of(product, self.color_red + self.size_l)
        blue_l = self._variant_of(product, self.color_blue + self.size_l)
        # 来源按 Color 轴认出来：Red/L 来自 Red/M、Blue/L 来自 Blue/M
        self.assertEqual(red_l.variant_origin_id, red_m)
        self.assertEqual(blue_l.variant_origin_id, blue_m)

        # 台账里的谱系行与变体字段必须一致（归属可追溯）
        conversion = product.variant_conversion_ids.sorted("id")[-1]
        added = conversion.lineage_ids.filtered(lambda line: not line.is_kept)
        self.assertEqual(
            {line.result_variant_id: line.origin_variant_id for line in added},
            {red_l: red_m, blue_l: blue_m},
        )

    def test_adding_a_value_inherits_dimensions_from_the_right_variant(self):
        """承接上一条：新变体继承的是它**对应**那条原变体的尺寸与体积（装了 product_dimension 时）。

        跑法：`task test -- product_variant_conversion,product_dimension --test-tags=/product_variant_conversion`
        （本模块不硬依赖 product_dimension，未安装时这条用例自动跳过。）
        """
        if "dimension_unit" not in self.env["product.product"]._fields:
            self.skipTest("product_dimension is not installed")
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        self._configure(product, self.size, self.size_m)
        red_m = self._variant_of(product, self.color_red + self.size_m)
        blue_m = self._variant_of(product, self.color_blue + self.size_m)
        red_m.write({
            "dimension_unit": "cm",
            "dimension_length": 50.0,
            "dimension_width": 40.0,
            "dimension_height": 30.0,
        })
        blue_m.write({
            "dimension_unit": "m",
            "dimension_length": 1.0,
            "dimension_width": 1.0,
            "dimension_height": 1.0,
        })

        commands = self._set_commands(product, self.size, self.size_m + self.size_l)
        preview = self._preview(product, commands)
        rows = [
            self._row(self._combination_of(preview, self.color_red + self.size_m), red_m),
            self._row(self._combination_of(preview, self.color_blue + self.size_m), blue_m),
            self._row(self._combination_of(preview, self.color_red + self.size_l)),
            self._row(self._combination_of(preview, self.color_blue + self.size_l)),
        ]
        self._confirm(product, commands, self._payload(rows))

        red_l = self._variant_of(product, self.color_red + self.size_l)
        blue_l = self._variant_of(product, self.color_blue + self.size_l)
        # 尺寸落到**对应**的变体上，体积各算各的
        self.assertEqual(red_l.dimension_unit, "cm")
        self.assertAlmostEqual(red_l.dimension_length, 50.0)
        self.assertAlmostEqual(red_l.volume, 0.06, places=6)
        self.assertEqual(blue_l.dimension_unit, "m")
        self.assertAlmostEqual(blue_l.dimension_length, 1.0)
        self.assertAlmostEqual(blue_l.volume, 1.0, places=6)
        # 原变体的数据不被改动
        self.assertAlmostEqual(red_m.volume, 0.06, places=6)
        self.assertAlmostEqual(blue_m.volume, 1.0, places=6)

    def test_variant_data_inheritance_can_be_switched_off(self):
        """系统参数关掉后新变体不再继承：保持 Odoo 默认的空 / 0，台账记为未继承。"""
        self.env["ir.config_parameter"].sudo().set_param(
            "product_variant_conversion.inherit_variant_data", "0")
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        red = self._variant_of(product, self.color_red)
        red.write({"standard_price": 10.0, "volume": 0.1, "weight": 1.0})

        originals = product.product_variant_ids
        commands = self._set_commands(product, self.size, self.size.value_ids)
        preview = self._preview(product, commands)
        self._confirm(product, commands, self._payload(self._default_rows(preview)))

        new_variants = product.product_variant_ids - originals
        self.assertEqual(len(new_variants), 2)
        self.assertEqual(set(new_variants.mapped("standard_price")), {0.0})
        self.assertEqual(set(new_variants.mapped("volume")), {0.0})
        self.assertEqual(set(new_variants.mapped("weight")), {0.0})
        self.assertFalse(product.variant_conversion_ids.sorted("id")[-1].inherit_variant_data)

    # ------------------------------------------------------------------
    # 「原产品资料保留给指定变体」（T-023）
    # ------------------------------------------------------------------

    def _confirm_original_keeps_first_value(self, product, original):
        """给产品加 size 属性，并把**原记录**显式指定给「第一个取值」那个组合后保存。

        （模拟用户在弹窗里说「把原产品资料保留给这个变体」。）
        """
        commands = self._set_commands(product, self.size, self.size.value_ids)
        preview = self._preview(product, commands)
        rows = [
            self._row(self._combination_of(preview, self.size_m), original),
            self._row(self._combination_of(preview, self.size_l)),
        ]
        self._confirm(product, commands, self._payload(rows))
        product.invalidate_recordset()
        return product.product_variant_ids - original

    def test_product_data_stays_on_the_variant_that_keeps_the_product(self):
        """把原产品资料「保留给某个指定变体」＝保留原记录本身，资料本来就在它身上，无需转移。

        覆盖只装 `product` 就能验的四类：内部参考号 / 条码 / 按变体的供应商价格 / 按变体的价格表规则
        （补货规则需要 stock，见下一个测试）。「已属于该变体」的记录一律不动。
        """
        product = self._create_product()
        original = product.product_variant_id
        original.write({"default_code": "KEEP-002", "barcode": "9999999999999"})

        vendor = self.env["res.partner"].create({"name": "Test Vendor T-023"})
        variant_price = self.env["product.supplierinfo"].create({
            "partner_id": vendor.id,
            "product_tmpl_id": product.id,
            "product_id": original.id,
            "price": 7.5,
        })
        template_price = self.env["product.supplierinfo"].create({
            "partner_id": vendor.id,
            "product_tmpl_id": product.id,
            "product_id": False,
            "price": 9.5,
        })
        pricelist = self.env["product.pricelist"].create({
            "name": "Test Pricelist T-023",
            "currency_id": self.env.company.currency_id.id,
        })
        variant_rule = self.env["product.pricelist.item"].create({
            "pricelist_id": pricelist.id,
            "applied_on": "0_product_variant",
            "product_id": original.id,
            "compute_price": "fixed",
            "fixed_price": 88.0,
        })
        template_rule = self.env["product.pricelist.item"].create({
            "pricelist_id": pricelist.id,
            "applied_on": "1_product",
            "product_tmpl_id": product.id,
            "compute_price": "fixed",
            "fixed_price": 99.0,
        })

        new_variant = self._confirm_original_keeps_first_value(product, original)

        # ① 本来指向原记录的资料：仍指向它（「已属于该变体」就不动）
        self.assertEqual(original.default_code, "KEEP-002")
        self.assertEqual(original.barcode, "9999999999999")
        self.assertEqual(variant_price.product_id, original)
        self.assertEqual(variant_rule.product_id, original)

        # ② 模板级的记录不再被所有变体共用：按变体各拆一份（数值不变），原记录被删除
        self.assertFalse(template_price.exists())
        self.assertFalse(template_rule.exists())
        for variant in original + new_variant:
            self.assertEqual(self.env["product.supplierinfo"].search([
                ("product_id", "=", variant.id), ("partner_id", "=", vendor.id),
                ("price", "=", 9.5)]).price, 9.5)
            # 价格表侧：原记录自己在同一个「价格表 + 数量门槛」上已有 88.0 的规则，
            # 模板级那条 99.0 被它顶掉（本来也没在生效），新变体继承到的同样是 88.0
            self.assertEqual(self.env["product.pricelist.item"].search([
                ("applied_on", "=", "0_product_variant"), ("product_id", "=", variant.id),
                ("pricelist_id", "=", pricelist.id)]).fixed_price, 88.0)

        # ③ 新变体从谱系来源继承了价格数据（数值与来源一致），但参考号 / 条码不继承
        self.assertEqual(self.env["product.supplierinfo"].search([
            ("product_id", "=", new_variant.id), ("partner_id", "=", vendor.id),
            ("price", "=", 7.5)]).price, 7.5)
        self.assertEqual(self.env["product.pricelist.item"].search([
            ("applied_on", "=", "0_product_variant"), ("product_id", "=", new_variant.id),
            ("pricelist_id", "=", pricelist.id), ("fixed_price", "=", 88.0)]).fixed_price, 88.0)
        self.assertFalse(new_variant.default_code)
        self.assertFalse(new_variant.barcode)

    def test_variant_prices_are_separated_by_default(self):
        """默认把价格数据按变体分离：模板级记录拆到各变体一份（数值不变），不再被所有变体共用。"""
        product = self._create_product()
        original = product.product_variant_id
        vendor = self.env["res.partner"].create({"name": "Test Vendor T-024"})
        template_price = self.env["product.supplierinfo"].create({
            "partner_id": vendor.id,
            "product_tmpl_id": product.id,
            "product_id": False,
            "price": 30.0,
        })
        pricelist = self.env["product.pricelist"].create({
            "name": "Test Pricelist T-024",
            "currency_id": self.env.company.currency_id.id,
        })
        template_rule = self.env["product.pricelist.item"].create({
            "pricelist_id": pricelist.id,
            "applied_on": "1_product",
            "product_tmpl_id": product.id,
            "compute_price": "fixed",
            "fixed_price": 70.0,
        })

        new_variant = self._confirm_original_keeps_first_value(product, original)

        self.assertFalse(template_price.exists())
        self.assertFalse(template_rule.exists())
        for variant in original + new_variant:
            self.assertEqual(self.env["product.supplierinfo"].search([
                ("product_id", "=", variant.id), ("partner_id", "=", vendor.id)]).price, 30.0)
            self.assertEqual(self.env["product.pricelist.item"].search([
                ("applied_on", "=", "0_product_variant"), ("product_id", "=", variant.id),
                ("pricelist_id", "=", pricelist.id)]).fixed_price, 70.0)
        self.assertTrue(product.variant_conversion_ids.sorted("id")[-1].separate_variant_prices)

    def test_separated_variant_prices_are_edited_independently(self):
        """分离之后改一个变体的价格，不会影响别的变体 —— 这正是「价格要分离」的目的。"""
        product = self._create_product()
        original = product.product_variant_id
        vendor = self.env["res.partner"].create({"name": "Test Vendor T-024b"})
        template_price = self.env["product.supplierinfo"].create({
            "partner_id": vendor.id,
            "product_tmpl_id": product.id,
            "product_id": False,
            "price": 40.0,
        })

        new_variant = self._confirm_original_keeps_first_value(product, original)

        own_price = self.env["product.supplierinfo"].search([
            ("product_id", "=", original.id), ("partner_id", "=", vendor.id)])
        self.assertTrue(own_price)
        self.assertFalse(template_price.exists())
        self.assertEqual(original._select_seller(partner_id=vendor, quantity=1.0).price, 40.0)
        self.assertEqual(new_variant._select_seller(partner_id=vendor, quantity=1.0).price, 40.0)

        own_price.write({"price": 55.0})

        self.assertEqual(original._select_seller(partner_id=vendor, quantity=1.0).price, 55.0)
        self.assertEqual(new_variant._select_seller(partner_id=vendor, quantity=1.0).price, 40.0)

    def test_price_separation_can_be_switched_off(self):
        """系统参数关掉后保持原样：模板级记录仍是模板级（所有变体共用），台账记为未分离。"""
        self.env["ir.config_parameter"].sudo().set_param(
            "product_variant_conversion.separate_variant_prices", "0")
        product = self._create_product()
        original = product.product_variant_id
        vendor = self.env["res.partner"].create({"name": "Test Vendor T-024c"})
        template_price = self.env["product.supplierinfo"].create({
            "partner_id": vendor.id,
            "product_tmpl_id": product.id,
            "product_id": False,
            "price": 25.0,
        })

        self._confirm_original_keeps_first_value(product, original)

        self.assertTrue(template_price.exists())
        self.assertFalse(template_price.product_id)
        self.assertFalse(self.env["product.supplierinfo"].search([
            ("product_tmpl_id", "=", product.id), ("product_id", "!=", False)]))
        self.assertFalse(product.variant_conversion_ids.sorted("id")[-1].separate_variant_prices)

    def test_reordering_rules_stay_on_the_variant_that_keeps_the_product(self):
        """补货规则挂在变体上：转换后仍指向原来那条变体（被指定保留原产品资料的那条）。"""
        if "stock.warehouse.orderpoint" not in self.env:
            self.skipTest("stock is not installed")
        product = self._create_product()
        original = product.product_variant_id
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1)
        orderpoint = self.env["stock.warehouse.orderpoint"].create({
            "product_id": original.id,
            "location_id": warehouse.lot_stock_id.id,
            "product_min_qty": 2.0,
            "product_max_qty": 8.0,
        })

        new_variant = self._confirm_original_keeps_first_value(product, original)

        self.assertTrue(orderpoint.exists())
        self.assertEqual(orderpoint.product_id, original)
        self.assertFalse(self.env["stock.warehouse.orderpoint"].search(
            [("product_id", "=", new_variant.id)]))

    def test_sharing_vendor_prices_only_touches_variant_level_records(self):
        """共享时只改「product_id 指向既有变体」的记录；本来就模板级的记录不动。"""
        product = self._create_product()
        original = product.product_variant_id
        vendor = self.env["res.partner"].create({"name": "Test Vendor T-023b"})
        variant_price = self.env["product.supplierinfo"].create({
            "partner_id": vendor.id,
            "product_tmpl_id": product.id,
            "product_id": original.id,
            "price": 12.0,
        })
        template_price = self.env["product.supplierinfo"].create({
            "partner_id": vendor.id,
            "product_tmpl_id": product.id,
            "product_id": False,
            "price": 20.0,
        })

        touched = product._share_vendor_prices_with_variants(original)

        self.assertEqual(touched, variant_price)
        self.assertNotIn(template_price, touched)
        self.assertFalse(variant_price.product_id)
        self.assertEqual(variant_price.price, 12.0)
        self.assertFalse(template_price.product_id)
        self.assertEqual(template_price.price, 20.0)

    def test_sharing_vendor_prices_gives_every_variant_the_same_price(self):
        """勾选共享后（走正常转换链路）：所有变体 —— 含新建的 —— 取到同一数值。"""
        product = self._create_product()
        original = product.product_variant_id
        vendor = self.env["res.partner"].create({"name": "Test Vendor T-023c"})
        variant_price = self.env["product.supplierinfo"].create({
            "partner_id": vendor.id,
            "product_tmpl_id": product.id,
            "product_id": original.id,
            "price": 12.0,
        })

        commands = self._set_commands(product, self.size, self.size.value_ids)
        preview = self._preview(product, commands)
        rows = [
            self._row(self._combination_of(preview, self.size_m), original),
            self._row(self._combination_of(preview, self.size_l)),
        ]
        self._confirm(product, commands, self._payload(rows, share_vendor_prices=True))
        product.invalidate_recordset()

        self.assertEqual(len(product.product_variant_ids), 2)
        self.assertFalse(variant_price.product_id)
        for variant in product.product_variant_ids:
            seller = variant._select_seller(partner_id=vendor, quantity=1.0)
            self.assertEqual(seller, variant_price)
            self.assertEqual(seller.price, 12.0)

    # ------------------------------------------------------------------
    # 属性主数据路径的拦截（T-017）
    # ------------------------------------------------------------------

    def test_deleting_a_used_value_in_master_data_is_refused(self):
        """属性主数据里删取值：正被产品变体使用的取值不允许删。"""
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        with self.assertRaises(UserError):
            self.color_red.unlink()
        self.assertTrue(self.color_red.exists())

    def test_deleting_a_ptav_with_active_variants_is_refused(self):
        """删除取值记录（ptav）：还有在用变体带着它时不允许删。"""
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        ptav = product.attribute_line_ids.mapped("product_template_value_ids").filtered(
            lambda value: value.product_attribute_value_id == self.color_red)
        with self.assertRaises(UserError):
            ptav.unlink()
        self.assertTrue(ptav.exists())

    def test_deleting_an_attribute_line_directly_is_refused(self):
        """直接删属性行（不经产品表单）：带着该行取值的在用变体会失去归属，必须拒绝。"""
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        line = product.attribute_line_ids
        with self.assertRaises(UserError):
            line.unlink()
        self.assertTrue(line.exists())

    def test_removing_a_value_through_the_line_is_refused(self):
        """直接写属性行移走取值：在用变体还带着它时不允许（不经产品表单的路也被拦住）。"""
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        line = product.attribute_line_ids.filtered(lambda ptal: ptal.attribute_id == self.color)
        with self.assertRaises(UserError):
            line.write({"value_ids": [Command.set(self.color_red.ids)]})
        self.assertEqual(
            line.product_template_value_ids.mapped("product_attribute_value_id"),
            self.color.value_ids,
        )

    def test_value_deletion_works_once_the_variants_are_gone(self):
        """报错里给的出路：先把用到取值的产品处理掉，取值就能正常删。"""
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        product.unlink()
        self.color_red.unlink()
        self.assertFalse(self.color_red.exists())

    # ------------------------------------------------------------------
    # 未覆盖分支（T-019）：多记录 / combo / 归档变体 / dynamic 属性
    # ------------------------------------------------------------------

    def test_writing_several_products_at_once_is_refused(self):
        """一次改多个产品的属性：会动到变体时拒绝（多记录表达不了逐条归属）。"""
        product_a = self._create_product(attribute=self.color, values=self.color.value_ids)
        product_b = self._create_product(attribute=self.color, values=self.color.value_ids)
        commands = self._set_commands(product_a, self.size, self.size.value_ids)
        with self.assertRaises(UserError):
            (product_a + product_b).write({"attribute_line_ids": commands})
        self.assertFalse(product_a.attribute_line_ids.filtered(
            lambda ptal: ptal.attribute_id == self.size))

    def test_product_with_archived_variants_is_refused(self):
        """产品带归档变体时拒绝转换（避免老变体被悄悄复活）。"""
        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        self._variant_of(product, self.color_blue).active = False
        commands = self._set_commands(product, self.size, self.size.value_ids)
        preview = self._preview(product, commands)
        self.assertTrue(preview["required"])
        with self.assertRaises(UserError):
            self._confirm(product, commands, self._payload(self._default_rows(preview)))

    def test_dynamic_attribute_is_refused(self):
        """「按需生成变体」的属性拒绝走本流程（Odoo 自己创建变体，无需归属确认）。"""
        dynamic = self.Attribute.create({
            "name": "Test Dynamic",
            "create_variant": "dynamic",
            "value_ids": [(0, 0, {"name": "Test D1"}), (0, 0, {"name": "Test D2"})],
        })
        product = self._create_product()
        commands = self._set_commands(product, dynamic, dynamic.value_ids)
        preview = self._preview(product, commands)
        self.assertTrue(preview["blocked"])
        with self.assertRaises(UserError):
            product.write({"attribute_line_ids": commands})
        self.assertFalse(product.attribute_line_ids)

    # ------------------------------------------------------------------
    # 组合数前置上限（T-018）
    # ------------------------------------------------------------------

    def test_huge_combination_counts_are_refused_before_enumeration(self):
        """组合总数（各属性取值数乘积）超过 dynamic_variant_limit 时，先拒绝再枚举。"""
        big = self.Attribute.create({
            "name": "Test Big",
            "value_ids": [(0, 0, {"name": "Test Big %02d" % index}) for index in range(40)],
        })
        other = self.Attribute.create({
            "name": "Test Big 2",
            "value_ids": [(0, 0, {"name": "Test B2 %02d" % index}) for index in range(40)],
        })
        product = self._create_product()
        with self.assertRaises(UserError) as catch:
            self._configure(product, big, big.value_ids)
            self._configure(product, other, other.value_ids)
        self.assertIn("product.dynamic_variant_limit", str(catch.exception))

    # ------------------------------------------------------------------
    # 转换后钩子与 chatter 留痕（T-020）
    # ------------------------------------------------------------------

    def test_conversion_hook_is_called_and_chatter_is_written(self):
        """转换完成后调用扩展钩子，并在产品 chatter 里留下一条转换记录。"""
        calls = []

        def fake_hook(recordset, originals, new_variants, anchors):
            calls.append((originals, new_variants, anchors))

        product = self._create_product(attribute=self.color, values=self.color.value_ids)
        with mock.patch.object(
                type(product), "_post_variant_conversion_hook",
                side_effect=fake_hook, autospec=True):
            self._configure(product, self.size, self.size.value_ids)
        # 补丁只对打上之后的那次转换生效（建产品配 Color 的那次在补丁之前）
        self.assertEqual(len(calls), 1)
        originals, new_variants, anchors = calls[0]
        self.assertEqual(len(originals), 2)
        self.assertEqual(len(new_variants), 2)
        self.assertEqual(len(anchors), len(originals))
        self.assertTrue(product.message_ids)
