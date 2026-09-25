# -*- coding: utf-8 -*-
"""视图挂载契约：每个产品入口的标题区都只渲染**一个** `Ref.` 编辑器。

为什么需要这组用例（`19.0.3.1.2` 修的问题）：`product.product` 的完整表单
（`product_normal_form_view`）**继承**产品模板表单（`product.product_template_form_view`），
所以挂在模板表单标题区的**产品级**编辑器会随继承链自动出现在变体表单上；而变体表单同一位置
另有**变体级**编辑器。两块都渲染时，从产品变体列表（Product Variants）点进变体详情会看到
两个一模一样的 `Ref.` 输入框 —— 一个编产品级共享行、一个编变体专属行，界面上分不出哪个是哪个。

修法：产品级那块带 `invisible="is_product_variant"`（模板侧恒 False、变体侧恒 True），
在变体表单上被隐藏，让位给变体级编辑器。本用例把「三张表单各一个编辑器」「门控字段与
各自维护的参考号层级」钉住，避免以后有人在任一侧再挂一块。

跑法：`task test -- product_reference --test-tags=/product_reference`
"""

from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestReferenceEditorMounting(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.normal_view = cls.env.ref("product.product_normal_form_view")
        cls.easy_view = cls.env.ref("product.product_variant_easy_edit_view")

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------

    def _blocks(self, model, view_id=None):
        """取某表单合成 arch 里的全部 ``div[name=product_reference]``。"""
        arch = self.env[model].get_view(view_type="form", view_id=view_id)["arch"]
        return etree.fromstring(arch.encode()).findall(".//div[@name='product_reference']")

    @staticmethod
    def _gate(block):
        """块上的隐藏门控表达式（空 = 无门控、必渲染）。"""
        return (block.get("invisible") or "").strip()

    @staticmethod
    def _code_field(label, block):
        """取块内的 `Ref.` 输入框（`default_code`），找不到就带着表单名报错。"""
        field = block.find("field[@name='default_code']")
        if field is None:
            raise AssertionError("%s：找不到 Ref. 输入框（default_code）" % label)
        return field

    def _assert_variant_level(self, label, block):
        """变体侧编辑器必须维护「变体专属行」：入口指向它、且声明了它的元数据字段。"""
        options = self._code_field(label, block).get("options") or ""
        if "variant_reference_code_line_ids" not in options:
            raise AssertionError(
                "%s：Ref. 输入框的 options.lines_field 必须指向 variant_reference_code_line_ids" % label
            )
        if block.find("field[@name='variant_reference_code_line_ids']") is None:
            raise AssertionError("%s：缺少变体专属行的元数据字段" % label)

    # ------------------------------------------------------------------
    # 用例
    # ------------------------------------------------------------------

    def test_gate_field_value_on_both_sides(self):
        """门控字段的取值就是分层的依据：模板侧 False（显示产品级）、变体侧 True（隐藏它）。"""
        tmpl = self.env["product.template"].create({"name": "Reference Gate Probe", "type": "consu"})
        self.assertTrue(tmpl.product_variant_ids, "新建产品应带一条变体")
        self.assertFalse(tmpl.is_product_variant, "产品模板侧 is_product_variant 必须为 False")
        self.assertTrue(
            tmpl.product_variant_ids[0].is_product_variant,
            "变体侧 is_product_variant 必须为 True（产品级那块在变体表单上才会被隐藏）",
        )

    def test_product_forms_render_one_product_level_editor(self):
        """产品表单（模板表单 + 「只有模板」表单）：一个产品级编辑器。"""
        for label, view_id in (
            ("产品模板表单", None),
            ("产品「只有模板」表单", self.env.ref("product.product_template_only_form_view").id),
        ):
            blocks = self._blocks("product.template", view_id)
            self.assertEqual(len(blocks), 1, "%s：Ref. 编辑器块应恰好 1 个" % label)
            editor = blocks[0]
            # 产品表单上这块必须渲染：门控字段在模板侧恒 False
            self.assertEqual(
                self._gate(editor), "is_product_variant",
                "%s：产品级那块的隐藏门控应该是 is_product_variant（模板侧为假 → 显示）" % label,
            )
            options = self._code_field(label, editor).get("options") or ""
            self.assertNotIn(
                "variant_reference_code_line_ids", options,
                "%s：产品表单维护产品级共享行，不该指向变体专属行" % label,
            )
            self.assertIsNotNone(
                editor.find("field[@name='reference_code_line_ids']"),
                "%s：缺少产品级共享行的元数据字段" % label,
            )

    def test_variant_main_form_keeps_only_the_variant_level_editor(self):
        """`Product Variants` 点进变体详情用的默认表单（`product.product.form`）。

        继承来的产品级那块必须被 `is_product_variant` 门控隐藏，标题区只剩变体级编辑器。
        """
        got = self.env["product.product"].get_view(view_type="form")
        self.assertEqual(
            got["id"], self.normal_view.id,
            "变体默认表单不再是 product.product.form，本用例的前提需重新核对",
        )

        blocks = self._blocks("product.product", self.normal_view.id)
        hidden = [b for b in blocks if self._gate(b)]
        self.assertEqual(len(hidden), 1, "继承来的产品级那块应被隐藏（否则界面两个 Ref. 输入框）")
        self.assertIn(
            "is_product_variant", self._gate(hidden[0]),
            "隐藏产品级那块的门控必须是 is_product_variant",
        )
        shown = [b for b in blocks if not self._gate(b)]
        self.assertEqual(len(shown), 1, "变体主表单可见的 Ref. 编辑器应恰好 1 个")
        self._assert_variant_level("变体主表单", shown[0])

    def test_variant_easy_form_keeps_only_the_variant_level_editor(self):
        """产品的「变体」按钮用的快速编辑表单：独立 primary 视图，只有一个变体级编辑器。"""
        blocks = self._blocks("product.product", self.easy_view.id)
        self.assertEqual(len(blocks), 1, "变体快速编辑表单：Ref. 编辑器块应恰好 1 个")
        self._assert_variant_level("变体快速编辑表单", blocks[0])
