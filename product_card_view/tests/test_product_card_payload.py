# -*- coding: utf-8 -*-
"""卡片 payload 的编号契约测试。

本模块**不依赖任何自研模块**（`depends` 只有 `stock`），编号只读两个原生字段：

- 模板层 `product.template.default_code` —— 卡片编号栏显示的就是它；
- 变体层 `product.product.default_code` —— 已选组合行显示变体自己的编号。

因此这里只用**原生 API** 写编号（`product.default_code` / `variant.default_code`）：
多变体产品的产品编号由 `product_reference` 叠加进 `default_code` 的 compute，
装了它卡片自然就有值、没装就是空 —— 两种情况都要能跑（后一种的用例自动跳过）。

跑法（两种组合都要跑）：
  task test -- product_card_view
  task test -- product_card_view,product_reference
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProductCardPayloadReference(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.attribute = cls.env["product.attribute"].create({
            "name": "Test Card Color",
            "value_ids": [
                (0, 0, {"name": "Test Card Red"}),
                (0, 0, {"name": "Test Card Blue"}),
            ],
        })

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    def _create_product(self, name="Test Card Product", default_code=False, attribute=False):
        """建产品；`attribute=True` 时带上一个两取值的属性（得到两个变体）。

        属性行放在 ``create`` 里而不是后补 ``write``：`product_variant_conversion` 装了之后会
        拦截「写 `attribute_line_ids`」这类改属性的保存（要求先确认变体归属），而 `create`
        不受拦截 —— 本模块的测试不该被另一个模块的可选行为绊住。
        """
        vals = {"name": name, "type": "consu"}
        if "is_storable" in self.env["product.template"]._fields:
            vals["is_storable"] = True
        if attribute:
            vals["attribute_line_ids"] = [(0, 0, {
                "attribute_id": self.attribute.id,
                "value_ids": [(6, 0, self.attribute.value_ids.ids)],
            })]
        product = self.env["product.template"].create(vals)
        if default_code:
            product.default_code = default_code
        return product

    def _payload(self, template):
        return template._get_product_card_view_payload()[template.id]

    def _references_by_variant(self, data):
        return {row["id"]: row["reference"] for row in data["variants"]}

    def _multi_variant_product_can_carry_a_reference(self):
        """多变体产品能否有产品编号 —— 装了 `product_reference` 才行。

        卡片自身**不读**该模块的任何字段（只读原生 `default_code`）；这里判断它只是为了
        决定「多变体产品带产品编号」这个场景能不能测：没装那个模块时，原生 compute 对
        多变体产品的模板级 `default_code` 恒为空，没有可测的值。
        """
        return "base_reference" in self.env["product.template"]._fields

    # ------------------------------------------------------------------
    # 模板层编号（卡片编号栏）
    # ------------------------------------------------------------------

    def test_single_variant_product_shows_the_variant_reference(self):
        """单变体产品：编号栏显示那条变体的编号（原生单变体桥接）。"""
        product = self._create_product(default_code="S-001")
        data = self._payload(product)
        self.assertEqual(data["reference"], "S-001")
        self.assertEqual(
            self._references_by_variant(data), {product.product_variant_id.id: "S-001"})

    def test_multi_variant_product_without_a_product_reference_shows_nothing(self):
        """多变体产品没有产品编号时编号为空（前端显示 `—`），其余信息照常。

        未装 `product_reference` 时**永远**是这种情况 —— 这正是「缺可选模块」的降级：
        标题 / 图片 / 在手 / 变体按钮一个都不少，只有编号那一栏没有值。
        """
        product = self._create_product(attribute=True)
        self.assertFalse(product.default_code)      # 多变体产品的模板级编号本来就是空的
        data = self._payload(product)
        self.assertEqual(data["reference"], "")
        self.assertEqual(set(self._references_by_variant(data).values()), {""})
        self.assertEqual(len(data["rows"]), 1)      # 变体按钮行照常
        self.assertEqual(len(data["variants"]), 2)

    def test_multi_variant_product_shows_its_product_reference_when_installed(self):
        """多变体产品有产品编号时（装了 `product_reference`），编号栏显示它。"""
        if not self._multi_variant_product_can_carry_a_reference():
            self.skipTest("a multi-variant product cannot carry a product reference here")
        product = self._create_product(attribute=True)
        product.default_code = "G001"

        self.assertEqual(self._payload(product)["reference"], "G001")

    # ------------------------------------------------------------------
    # 变体层编号（已选组合行）
    # ------------------------------------------------------------------

    def test_variant_reference_falls_back_to_the_product_reference(self):
        """变体自己的编号优先；没填则回退产品编号。"""
        if not self._multi_variant_product_can_carry_a_reference():
            self.skipTest("a multi-variant product cannot carry a product reference here")
        product = self._create_product(attribute=True)
        product.default_code = "G001"
        red, blue = product.product_variant_ids
        red.default_code = "G001-WT"

        data = self._payload(product)
        self.assertEqual(
            self._references_by_variant(data),
            {red.id: "G001-WT", blue.id: "G001"},
        )
