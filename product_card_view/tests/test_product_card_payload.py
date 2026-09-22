# -*- coding: utf-8 -*-
"""卡片 payload 的「可选集成」接口测试（编号这一层）。

`product_card_view` 不依赖任何自研模块（`depends` 只有 `stock`），卡片编号与图库都由可选模块
补强。本文件钉住编号层的**接口契约与降级行为** —— 装了 / 没装 `product_reference` 两种组合下
都必须成立：

1. 单变体产品：模板层与变体层都显示那条变体的 `default_code`；
2. 多变体产品：模板级 `default_code` 恒为空，**没有母型号时编号为空字符串**（前端显示 `—`）；
3. 多变体产品装了 `product_reference` 且填了母型号时：模板层显示母型号，变体层优先自己的
   `default_code`、为空则回退母型号；
4. **单变体产品上的残留母型号必须被忽略**：单变体产品的编号真身在那条变体上
   （`product_reference` 不在产品侧写镜像），卡片不得读到残留值。

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

    def _has_base_reference(self):
        """`product_reference` 是否安装（无法在本模块 `depends` 里声明，只能运行期判断）。"""
        return "base_reference" in self.env["product.template"]._fields

    # ------------------------------------------------------------------
    # 降级：不依赖 product_reference 也必须正确
    # ------------------------------------------------------------------

    def test_single_variant_product_shows_the_variant_reference(self):
        """单变体产品：模板层与变体层都显示那条变体的编号。"""
        product = self._create_product(default_code="S-001")
        data = self._payload(product)
        self.assertEqual(data["reference"], "S-001")
        self.assertEqual(
            self._references_by_variant(data), {product.product_variant_id.id: "S-001"})

    def test_multi_variant_product_without_a_model_shows_no_reference(self):
        """多变体产品没有母型号时（未装 `product_reference` / 没填）编号为空 —— 前端显示 `—`。

        这正是「缺可选模块」时允许的降级：卡片的其他信息（标题 / 图片 / 在手 / 变体按钮）
        一个都不少，只是编号那一栏没有值。
        """
        product = self._create_product(attribute=True)
        self.assertFalse(product.default_code)      # 多变体产品的模板级编号本来就是空的
        data = self._payload(product)
        self.assertEqual(data["reference"], "")
        self.assertEqual(set(self._references_by_variant(data).values()), {""})
        self.assertEqual(len(data["rows"]), 1)      # 变体按钮行照常
        self.assertEqual(len(data["variants"]), 2)

    def test_single_variant_product_ignores_a_leftover_base_reference(self):
        """残留母型号不得盖掉单变体产品的编号（该字段在单变体产品上不代表编号）。"""
        if not self._has_base_reference():
            self.skipTest("product_reference is not installed")
        product = self._create_product(default_code="S-002")
        product.base_reference = "STALE-001"
        data = self._payload(product)
        self.assertEqual(data["reference"], "S-002")
        self.assertEqual(
            self._references_by_variant(data), {product.product_variant_id.id: "S-002"})

    # ------------------------------------------------------------------
    # 可选集成：装了 product_reference 时的编号取值链
    # ------------------------------------------------------------------

    def test_multi_variant_product_shows_the_base_reference(self):
        """多变体产品：模板层显示母型号；变体层优先自己的编号、为空则回退母型号。"""
        if not self._has_base_reference():
            self.skipTest("product_reference is not installed")
        product = self._create_product(attribute=True)
        product.base_reference = "G001"
        red, blue = product.product_variant_ids
        red.default_code = "G001-WT"

        data = self._payload(product)
        self.assertEqual(data["reference"], "G001")
        self.assertEqual(
            self._references_by_variant(data),
            {red.id: "G001-WT", blue.id: "G001"},
        )
