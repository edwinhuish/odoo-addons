# -*- coding: utf-8 -*-
"""母型号 `base_reference` 的接口契约测试（本模块是「提供方」）。

另外两个模块**可选地**消费这个字段：`product_variant_conversion` 在「单变体 → 多变体」时把
编号上移进来，`product_card_view` 在多变体产品的卡片上显示它。因此本文件只钉住对外契约，
不测它们的行为（各自在自己的测试里覆盖）：

1. **单变体产品不写它**：写 `default_code` 不会在产品侧留下副本 —— 没有镜像就不存在
   「两处不同步」，这是本模块 L1.3 的核心约定；
2. **两个字段互不驱动**：写谁都不会顺手改另一个（单变体 / 多变体各验一遍）；
3. **母型号参与搜索**：产品与变体都能在 `display_name` 搜索里按母型号命中
   （多变体产品的模板级 `default_code` 是空的，搜索只能靠这个字段）。

跑法：`task test -- product_reference --test-tags=/product_reference`
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestBaseReferenceContract(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.attribute = cls.env["product.attribute"].create({
            "name": "Test Base Ref Color",
            "value_ids": [
                (0, 0, {"name": "Test Base Ref Red"}),
                (0, 0, {"name": "Test Base Ref Blue"}),
            ],
        })

    def _create_product(self, name="Test Base Ref Product", attribute=False):
        """建产品；`attribute=True` 时带上一个两取值的属性（得到两个变体）。

        属性行放在 ``create`` 里而不是后补 ``write``：`product_variant_conversion` 装了之后会
        拦截「写 `attribute_line_ids`」这类改属性的保存（要求先确认变体归属），而 `create`
        不受拦截 —— 本模块的测试不该被另一个模块的可选行为绊住。
        """
        vals = {"name": name, "type": "consu"}
        if attribute:
            vals["attribute_line_ids"] = [(0, 0, {
                "attribute_id": self.attribute.id,
                "value_ids": [(6, 0, self.attribute.value_ids.ids)],
            })]
        return self.env["product.template"].create(vals)

    # ------------------------------------------------------------------
    # 1. 单变体产品不写母型号（没有镜像）
    # ------------------------------------------------------------------

    def test_single_variant_reference_is_not_mirrored(self):
        """单变体产品写编号：真身落在变体上，产品侧保持为空。"""
        product = self._create_product()
        product.default_code = "G001"

        self.assertEqual(product.product_variant_id.default_code, "G001")
        self.assertFalse(product.base_reference)

    def test_writing_the_base_reference_does_not_touch_the_variant_reference(self):
        """反向同理：写母型号不会顺手给变体编号。"""
        product = self._create_product()
        product.base_reference = "G001"

        self.assertFalse(product.product_variant_id.default_code)

    # ------------------------------------------------------------------
    # 2. 多变体产品：两个字段各管一层，互不驱动
    # ------------------------------------------------------------------

    def test_the_two_fields_do_not_drive_each_other(self):
        product = self._create_product(attribute=True)
        red, blue = product.product_variant_ids

        product.base_reference = "G001"
        self.assertFalse(red.default_code)

        red.default_code = "G001-WT"
        self.assertEqual(product.base_reference, "G001")     # 改变体编号不动母型号
        self.assertFalse(blue.default_code)                  # 也不会扩散到别的变体
        self.assertFalse(product.default_code)               # 模板级 default_code 仍是原生空桥接

    # ------------------------------------------------------------------
    # 3. 搜索：母型号必须能被搜到（产品层与变体层）
    # ------------------------------------------------------------------

    def test_base_reference_is_searchable_on_products_and_variants(self):
        product = self._create_product(attribute=True)
        product.base_reference = "G001"

        found_templates = self.env["product.template"].search(
            [("display_name", "ilike", "G001")])
        self.assertIn(product, found_templates)

        found_variants = self.env["product.product"].search(
            [("display_name", "ilike", "G001")])
        self.assertEqual(found_variants, product.product_variant_ids)
