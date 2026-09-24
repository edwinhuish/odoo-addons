# -*- coding: utf-8 -*-
"""型号自动转大写的契约测试（前端同一口径由 JS 保证，这里钉住后端写入）。

型号类字段在**写入时**统一转大写（见 ``models/reference_case.py``）：
- 额外参考号 ``product.reference.code.reference_code``
- 产品编号 ``product.template.base_reference`` 与产品表单的 ``Ref.``
  （``product.template.default_code``）
- 变体编号 ``product.product.default_code``

必须成立的四条边界：
1. **两层同口径** —— 单变体产品改任一处，另一处跟着变且都是大写（否则会出现
   「产品大写、变体小写」的半截数据）；
2. **多变体产品只动产品编号** —— 各变体编号原样不动；
3. **只归一大小写** —— 不裁剪空格、不改非字母字符，``False`` 也不会被变成字符串；
4. **大写不影响搜索** —— 用小写去搜仍能命中（``ilike``）。

存量数据不自动改写（会撞唯一约束的行无法自动消歧），故这里不测历史数据。

跑法：``task test -- product_reference --test-tags=/product_reference``
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestReferenceUppercase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.attribute = cls.env["product.attribute"].create({
            "name": "Test Uppercase Color",
            "value_ids": [
                (0, 0, {"name": "Test Uppercase Red"}),
                (0, 0, {"name": "Test Uppercase Blue"}),
            ],
        })

    def _create_product(self, name="Test Uppercase Product", attribute=False):
        """建产品；`attribute=True` 时带一个两取值的属性（得到两个变体）。

        属性行放在 ``create`` 里而不是后补 ``write``：`product_variant_conversion`
        装了之后会拦截「写 `attribute_line_ids`」这类改属性的保存（要求先确认变体
        归属），而 ``create`` 不受拦截 —— 本模块的测试不该被另一个模块的可选行为绊住。
        """
        vals = {"name": name, "type": "consu"}
        if attribute:
            vals["attribute_line_ids"] = [(0, 0, {
                "attribute_id": self.attribute.id,
                "value_ids": [(6, 0, self.attribute.value_ids.ids)],
            })]
        return self.env["product.template"].create(vals)

    # ------------------------------------------------------------------
    # 1. 额外参考号行：新增 / 修改都转大写，搜索索引同样是大写
    # ------------------------------------------------------------------

    def test_reference_code_is_uppercased_on_create(self):
        product = self._create_product()

        line = self.env["product.reference.code"].create({
            "product_tmpl_id": product.id,
            "reference_code": "abc-123",
        })

        self.assertEqual(line.reference_code, "ABC-123")

    def test_reference_code_is_uppercased_on_write(self):
        product = self._create_product()
        line = self.env["product.reference.code"].create({
            "product_tmpl_id": product.id,
            "reference_code": "abc-123",
        })

        line.write({"reference_code": "xyz-9"})

        self.assertEqual(line.reference_code, "XYZ-9")
        # 搜索索引由行同步而来，存的也必须是大写（列表按小写搜才搜得到）
        self.assertEqual(product.reference_code_index, "XYZ-9")

    def test_reference_code_only_normalizes_the_case(self):
        """只归一大小写：不裁剪空格、不改数字与符号。"""
        product = self._create_product()

        line = self.env["product.reference.code"].create({
            "product_tmpl_id": product.id,
            "reference_code": " a1-b2 ",
        })

        self.assertEqual(line.reference_code, " A1-B2 ")

    # ------------------------------------------------------------------
    # 2. 产品编号 / Ref.：两层同口径，多变体产品只动产品编号
    # ------------------------------------------------------------------

    def test_base_reference_is_uppercased(self):
        product = self._create_product(attribute=True)

        product.write({"base_reference": "g001"})

        self.assertEqual(product.base_reference, "G001")
        self.assertEqual(product.default_code, "G001")     # compute：产品编号优先

    def test_single_variant_reference_is_uppercased_on_both_levels(self):
        """单变体产品写 `Ref.`：产品编号与那条变体的编号两处同值、都是大写。"""
        product = self._create_product()
        variant = product.product_variant_id

        product.write({"default_code": "g001"})

        self.assertEqual(product.base_reference, "G001")
        self.assertEqual(product.default_code, "G001")
        variant.invalidate_recordset(["default_code"])
        self.assertEqual(variant.default_code, "G001")

    def test_variant_reference_is_uppercased_and_syncs_the_product(self):
        """从变体侧改编号：变体编号转大写，产品编号跟着走。"""
        product = self._create_product()
        variant = product.product_variant_id

        variant.write({"default_code": "g002"})

        self.assertEqual(variant.default_code, "G002")
        self.assertEqual(product.base_reference, "G002")
        self.assertEqual(product.default_code, "G002")

    def test_multi_variant_reference_is_uppercased_without_touching_variants(self):
        """多变体产品写 `Ref.`：只落产品编号，各变体编号原样不动。"""
        product = self._create_product(attribute=True)
        red, blue = product.product_variant_ids

        product.write({"default_code": "g003"})

        self.assertEqual(product.base_reference, "G003")
        self.assertEqual(product.default_code, "G003")
        self.assertFalse(red.default_code)
        self.assertFalse(blue.default_code)

    def test_clearing_the_reference_does_not_become_a_string(self):
        """清空编号时 ``False`` 不能被转大写函数变成 ``"FALSE"``。"""
        product = self._create_product()
        product.write({"base_reference": "g001"})

        product.write({"base_reference": False})

        self.assertFalse(product.base_reference)

    # ------------------------------------------------------------------
    # 3. 搜索：存成大写后，用小写仍能命中
    # ------------------------------------------------------------------

    def test_lowercase_search_still_finds_the_uppercased_reference(self):
        product = self._create_product(attribute=True)
        product.write({"base_reference": "g001"})

        found = self.env["product.template"].search(
            [("display_name", "ilike", "g001")])
        self.assertIn(product, found)
