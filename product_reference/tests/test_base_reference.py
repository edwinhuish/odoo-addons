# -*- coding: utf-8 -*-
"""产品级编号（`base_reference`）的接口契约测试（本模块是「提供方」）。

本模块把**产品这一层的编号**放在自有字段 `product.template.base_reference` 上，再把它
**叠加**进模板级 `default_code` 的 compute（`base_reference` 优先，其次原生单变体桥接）。
消费方（`product_card_view` 等）只读原生 `default_code`，因此这里必须钉住四条对外契约：

1. **单变体产品：两处同值** —— 写模板编号 → 落到 `base_reference` + 那条变体；
   从变体侧改编号 → `base_reference` 跟着走；
2. **多变体产品：只写产品级编号** —— 改模板编号只落 `base_reference`，各变体编号原样不动
   （反之亦然）；
3. **模板级 `default_code` 读到的是产品编号** —— `base_reference` 有值时优先于原生桥接，
   清空后回落到原生口径；
4. **可被搜索** —— 产品列表按产品编号命中；订单行等变体层由本模块的
   `_search_display_name` 扩展按委托字段 `base_reference` 命中。

跑法：`task test -- product_reference --test-tags=/product_reference`
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestBaseReferenceContract(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.attribute = cls.env["product.attribute"].create({
            "name": "Test Base Reference Color",
            "value_ids": [
                (0, 0, {"name": "Test Base Reference Red"}),
                (0, 0, {"name": "Test Base Reference Blue"}),
            ],
        })

    def _create_product(self, name="Test Base Reference", attribute=False):
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
    # 1. 单变体产品：两处同值（写模板 / 写变体两个方向）
    # ------------------------------------------------------------------

    def test_single_variant_main_reference_updates_both_places(self):
        product = self._create_product()
        variant = product.product_variant_id

        product.default_code = "G001"

        self.assertEqual(product.base_reference, "G001")
        variant.invalidate_recordset(["default_code"])
        self.assertEqual(variant.default_code, "G001")

    def test_single_variant_variant_reference_updates_the_base_reference(self):
        product = self._create_product()
        variant = product.product_variant_id

        variant.default_code = "G002"

        self.assertEqual(product.base_reference, "G002")
        self.assertEqual(product.default_code, "G002")     # compute：base_reference 优先

    # ------------------------------------------------------------------
    # 2. 多变体产品：只写产品级编号，变体编号各归各的
    # ------------------------------------------------------------------

    def test_multi_variant_main_reference_only_updates_the_base_reference(self):
        product = self._create_product(attribute=True)
        red, blue = product.product_variant_ids

        product.default_code = "G001"

        self.assertEqual(product.base_reference, "G001")
        self.assertEqual(product.default_code, "G001")     # compute：base_reference 优先
        self.assertFalse(red.default_code)                 # 各变体编号原样不动
        self.assertFalse(blue.default_code)

    def test_multi_variant_variant_reference_does_not_touch_the_base_reference(self):
        product = self._create_product(attribute=True)
        product.base_reference = "G001"

        product.product_variant_ids[0].default_code = "G001-WT"

        self.assertEqual(product.base_reference, "G001")
        self.assertEqual(product.default_code, "G001")

    # ------------------------------------------------------------------
    # 3. 模板级 default_code 的口径：产品编号优先，清空后回落原生
    # ------------------------------------------------------------------

    def test_template_reference_prefers_the_base_reference(self):
        product = self._create_product(attribute=True)
        product.base_reference = "G001"

        self.assertEqual(product.default_code, "G001")

        product.base_reference = False
        product._compute_default_code()                    # 原生实现：多变体赋空
        self.assertFalse(product.default_code)

    # ------------------------------------------------------------------
    # 4. 搜索：产品层与变体层都能按产品编号命中
    # ------------------------------------------------------------------

    def test_base_reference_is_searchable_on_products_and_variants(self):
        product = self._create_product(attribute=True)
        product.base_reference = "G001"

        found_templates = self.env["product.template"].search(
            [("display_name", "ilike", "G001")])
        self.assertIn(product, found_templates)

        # 变体层：由本模块 `_search_display_name` 的 base_reference 分支命中
        found_variants = self.env["product.product"].search(
            [("display_name", "ilike", "G001")])
        self.assertEqual(found_variants, product.product_variant_ids)
