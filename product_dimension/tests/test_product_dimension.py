# -*- coding: utf-8 -*-
"""尺寸字段的归属与 Volume 同步。

重点锁两件事：
1. 尺寸的真身在**变体**上，每条变体各算各的 Volume（这是 T-021 要解决的问题）；
2. 模板侧只是「单变体桥接」：单变体时读写都落到那条变体，多变体时读出空值、写入不动任何变体
   （与原生 `volume` / `weight` 同构）。
"""

from lxml import etree

import os
import shutil
import subprocess

from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

from odoo.addons.product_dimension.models.product_product import CM3_PER_M3


@tagged("post_install", "-at_install")
class TestProductDimension(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # 原生 Logistics 组（`volume` / `weight` 所在）带 `groups="uom.group_uom"` 的祖先组：
        # 没有该组的用户整块都看不到（连 `volume` 都看不到）。要断言尺寸块的挂载，先把这个组
        # 给到当前用户 —— 尺寸块的可见性本来就该跟 `volume` 走。
        cls.env.user.write({"group_ids": [Command.link(cls.env.ref("uom.group_uom").id)]})
        cls.env.invalidate_all()
        cls.product = cls.env["product.template"].create({
            "name": "Test Dimension Product",
            "type": "consu",
        })
        cls.variant = cls.product.product_variant_id

    # ------------------------------------------------------------------
    # 变体侧：尺寸 → 原生 Volume
    # ------------------------------------------------------------------

    def test_dimension_unit_defaults_to_centimeters(self):
        self.assertEqual(self.variant.dimension_unit, "cm")
        self.assertEqual(self.variant.dimension_length, 0.0)

    def test_volume_is_synced_from_variant_dimensions(self):
        """尺寸变化即重算 Volume，厘米与米两种单位都要得到同一个立方米值。"""
        self.variant.write({
            "dimension_unit": "cm",
            "dimension_length": 50.0,
            "dimension_width": 40.0,
            "dimension_height": 30.0,
        })
        self.assertAlmostEqual(self.variant.volume, 0.06, places=6)

        self.variant.write({
            "dimension_unit": "m",
            "dimension_length": 0.5,
            "dimension_width": 0.4,
            "dimension_height": 0.3,
        })
        self.assertAlmostEqual(self.variant.volume, 0.06, places=6)

    def test_clearing_a_dimension_zeroes_the_volume(self):
        self.variant.write({
            "dimension_length": 50.0, "dimension_width": 40.0, "dimension_height": 30.0,
        })
        self.assertAlmostEqual(self.variant.volume, 0.06, places=6)
        self.variant.write({"dimension_height": 0.0})
        self.assertEqual(self.variant.volume, 0.0)

    def test_negative_dimensions_are_refused(self):
        with self.assertRaises(ValidationError):
            self.variant.write({"dimension_length": -1.0})

    # ------------------------------------------------------------------
    # 前后端职责：体积在浏览器里算，后端不再重复算
    # ------------------------------------------------------------------

    def test_no_server_side_onchange_for_dimensions(self):
        """后端不再为尺寸注册 onchange：界面上的体积由前端算，RPC 里不该再返回它。

        这条同时守住「不再有服务端往返」：Odoo 只为注册过 onchange 的字段发 onchange 请求。
        """
        for model_name in ("product.product", "product.template"):
            onchange_methods = self.env[model_name]._onchange_methods
            for field_name in ("dimension_unit", "dimension_length", "dimension_width",
                               "dimension_height", "volume"):
                self.assertFalse(
                    onchange_methods.get(field_name),
                    "%s 上不应再为 %s 注册 onchange（已改由前端计算）" % (model_name, field_name),
                )

    def test_volume_sent_by_the_form_is_kept(self):
        """表单把算好的体积一起提交时，后端不再重算（同一件事不做两遍）。"""
        self.variant.write({
            "dimension_unit": "cm",
            "dimension_length": 50.0,
            "dimension_width": 40.0,
            "dimension_height": 30.0,
            "volume": 0.5,  # 前端算的（或用户手填的）值：原样保留
        })
        self.assertAlmostEqual(self.variant.volume, 0.5, places=6)

    def test_volume_is_filled_in_when_only_dimensions_are_written(self):
        """只写尺寸、没带体积的路径（导入 / API / 变体转换）由后端兜底补算，保证库里不落后。"""
        self.variant.write({
            "dimension_unit": "cm",
            "dimension_length": 50.0,
            "dimension_width": 40.0,
            "dimension_height": 30.0,
        })
        self.assertAlmostEqual(self.variant.volume, 0.06, places=6)

        imported = self.env["product.template"].create({"name": "Import Style Product", "type": "consu"})
        imported.product_variant_id.write({
            "dimension_unit": "m",
            "dimension_length": 1.0,
            "dimension_width": 1.0,
            "dimension_height": 1.0,
        })
        self.assertAlmostEqual(imported.product_variant_id.volume, 1.0, places=6)

    def test_the_sync_decision_is_shared_by_create_and_write(self):
        """`create` 与 `write` 用同一个判定：带了体积不算、只带尺寸才兜底。"""
        self.assertFalse(self.variant._should_sync_volume({"volume": 0.5, "dimension_length": 1.0}))
        self.assertTrue(self.variant._should_sync_volume({"dimension_length": 1.0}))
        self.assertFalse(self.variant._should_sync_volume({"name": "no dimensions"}))

    def test_frontend_computation_matches_the_backend_rules(self):
        """前端 JS 与后端共用同一套规则：只改一边时这条会先失败。

        这里是「规则声明」层面的守卫（字段名、换算常数与后端 `CM3_PER_M3` 一致）；
        规则**行为**由 `test_frontend_rules_produce_the_expected_volumes()` 用 node 真跑一遍。
        """
        source = self._read_frontend_rules()
        for field_name in ("dimension_unit", "dimension_length", "dimension_width",
                           "dimension_height", "volume"):
            self.assertIn('"%s"' % field_name, source, "前端规则缺少字段 %s" % field_name)
        self.assertIn(
            str(int(CM3_PER_M3)), source,
            "前端规则的换算常数与后端 volume_from_dimensions() 不一致")

    def _read_frontend_rules(self):
        """读前端的纯规则文件（它不依赖 Odoo，因此能直接交给 node 执行）。"""
        module_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        rules_path = os.path.join(
            module_root, "static", "src", "js", "dimension_volume_rules.js")
        return open(rules_path, encoding="utf-8").read()

    def test_frontend_rules_produce_the_expected_volumes(self):
        """用 node 真跑前端规则。

        为什么要专门测这个：前端逻辑不在 Odoo 测试框架里跑，曾出过一次真事故 ——
        JS 把 `roundPrecision()` 的第二参数当成「小数位数」传了 `2`，而它要的是**精度因子**
        （`0.01`），于是「按 2 的整数倍取整」，**任何小于 1 的体积都被算成 0**：
        界面显示 Volume = 0，保存下去也是 0（后端因为收到 `volume` 就不重算了）。
        """
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not available")
        script = self._read_frontend_rules().replace(
            "/** @odoo-module **/", "").replace("export ", "")
        script += """
const cases = [
    ["cm", 50, 40, 30, 6, 0.06],
    ["cm", 10, 10, 10, 6, 0.001],
    ["cm", 20, 20, 20, 6, 0.008],
    ["cm", 50, 40, 30, 2, 0.06],
    ["cm", 10, 10, 10, 2, 0],
    ["m", 1, 0.5, 0.4, 6, 0.2],
    ["cm", 50, 40, 0, 6, 0],
    ["m", 0, 0, 0, 6, 0],
];
for (const [unit, length, width, height, decimals, expected] of cases) {
    const actual = volumeFromDimensions(unit, length, width, height, decimals);
    if (actual !== expected) {
        console.error(`${unit} ${length}x${width}x${height} @${decimals} → ${actual}（期望 ${expected}）`);
        process.exit(1);
    }
}
console.log("ok");
"""
        result = subprocess.run([node, "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, (result.stderr or result.stdout).strip())

    def test_small_centimetre_volumes_keep_their_decimals(self):
        """cm 尺寸的小体积必须显示出来。

        Odoo 出厂的「Volume」精度是 2 位，20 × 20 × 20 cm（0.008 m³）会被舍成 0 ——
        用户只看到「Volume = 0」，以为没生效。模块在安装 / 升级时把精度提到 6 位。
        """
        self.assertGreaterEqual(
            self.env["decimal.precision"].precision_get("Volume"), 6,
            "安装 / 升级后「Volume」精度应不低于 6 位")
        self.variant.write({
            "dimension_unit": "cm",
            "dimension_length": 20.0,
            "dimension_width": 20.0,
            "dimension_height": 20.0,
        })
        self.assertAlmostEqual(self.variant.volume, 0.008, places=6)
        self.variant.write({
            "dimension_length": 10.0,
            "dimension_width": 10.0,
            "dimension_height": 10.0,
        })
        self.assertAlmostEqual(self.variant.volume, 0.001, places=6)

    # ------------------------------------------------------------------
    # 模板侧桥接：单变体
    # ------------------------------------------------------------------

    def test_single_variant_mirrors_template_reads_and_writes(self):
        """单变体产品：模板字段读的就是变体的值，写模板也会落到变体上。"""
        self.variant.write({
            "dimension_unit": "cm",
            "dimension_length": 50.0,
            "dimension_width": 40.0,
            "dimension_height": 30.0,
        })
        self.assertEqual(self.product.dimension_unit, "cm")
        self.assertAlmostEqual(self.product.dimension_length, 50.0)
        self.assertAlmostEqual(self.product.volume, 0.06, places=6)

        self.product.write({
            "dimension_unit": "m",
            "dimension_length": 1.0,
            "dimension_width": 0.5,
            "dimension_height": 0.4,
        })
        self.assertAlmostEqual(self.variant.dimension_length, 1.0)
        self.assertEqual(self.variant.dimension_unit, "m")
        self.assertAlmostEqual(self.variant.volume, 0.2, places=6)
        self.assertAlmostEqual(self.product.volume, 0.2, places=6)

    # ------------------------------------------------------------------
    # 多变体：每条变体各持一份尺寸
    # ------------------------------------------------------------------

    def test_each_variant_keeps_its_own_dimensions(self):
        """多变体产品：尺寸与 Volume 逐变体独立；模板侧读出空值、写入不牵动变体。"""
        second = self.env["product.product"].create({
            "product_tmpl_id": self.product.id,
            "dimension_unit": "m",
            "dimension_length": 1.0,
            "dimension_width": 1.0,
            "dimension_height": 1.0,
        })
        self.variant.write({
            "dimension_unit": "cm",
            "dimension_length": 50.0,
            "dimension_width": 40.0,
            "dimension_height": 30.0,
        })
        self.assertEqual(len(self.product.product_variant_ids), 2)
        self.assertAlmostEqual(self.variant.volume, 0.06, places=6)
        self.assertAlmostEqual(second.volume, 1.0, places=6)

        # 模板侧镜像：多条变体时给空值（与原生 volume 在多变体产品上的表现一致）
        self.assertFalse(self.product.dimension_unit)
        self.assertEqual(self.product.dimension_length, 0.0)

        # 在模板上写尺寸不会动到任何变体（界面上这些字段此时是隐藏的）
        self.product.write({"dimension_length": 99.0})
        self.assertAlmostEqual(self.variant.dimension_length, 50.0)
        self.assertAlmostEqual(second.dimension_length, 1.0)

    # ------------------------------------------------------------------
    # 挂载：尺寸字段必须在 product.product 的每个表单上都有挂载点
    # ------------------------------------------------------------------

    def test_dimension_fields_are_stored_on_the_variant(self):
        """真身必须在 `product.product` 上：存储字段、非 compute / related。

        模板侧同名字段必须是 compute（镜像），否则就成了第二份真数据 —— 也正是 T-021
        要避免的「模板有尺寸、变体各自有体积」的错位。
        """
        for field_name in ("dimension_unit", "dimension_length", "dimension_width", "dimension_height"):
            variant_field = self.env["product.product"]._fields[field_name]
            self.assertTrue(variant_field.store, "%s 必须存储在变体上" % field_name)
            self.assertFalse(variant_field.compute, "%s 在变体上不能是计算字段" % field_name)
            self.assertFalse(variant_field.related, "%s 在变体上不能是 related 字段" % field_name)

            template_field = self.env["product.template"]._fields[field_name]
            self.assertTrue(template_field.compute, "%s 在模板上必须是镜像桥接" % field_name)

    def test_dimension_block_is_mounted_on_every_variant_form(self):
        """三个表单都要挂上四个尺寸字段，缺一个用户就没法维护。

        - 产品表单（模板，单变体时可见）
        - 变体表单（`product_normal_form_view`，继承模板表单而来）
        - 变体快速编辑表单（`product_variant_easy_edit_view`，独立 primary 视图，
          产品的「变体」按钮用的就是它）
        """
        expected = {"dimension_unit", "dimension_length", "dimension_width", "dimension_height"}
        for label, model, kwargs in (
            ("产品表单", "product.template", {}),
            ("变体表单", "product.product", {}),
            ("变体快速编辑表单", "product.product",
             {"view_id": self.env.ref("product.product_variant_easy_edit_view").id}),
        ):
            arch = self.env[model].get_view(view_type="form", **kwargs)["arch"]
            fields = {node.get("name") for node in etree.fromstring(arch.encode()).iter("field")}
            self.assertTrue(
                expected <= fields,
                "%s 缺少尺寸字段：%s" % (label, expected - fields),
            )

    def test_dimension_block_visibility_matches_the_native_volume_rule(self):
        """可见性：多变体产品在**产品表单**上隐藏（与原生 volume 同款门控），
        在**变体表单**上必须可见 —— 那正是多变体产品维护尺寸的地方。"""
        second = self.env["product.product"].create({"product_tmpl_id": self.product.id})
        self.assertEqual(len(self.product.product_variant_ids), 2)

        arch = self.env["product.template"].get_view(view_type="form")["arch"]
        root = etree.fromstring(arch.encode())
        container = root.find(".//div[@name='dimension_dimensions']")
        self.assertTrue(container is not None, "产品表单上找不到尺寸块")
        gate = container.get("invisible") or container.get("modifiers") or ""
        self.assertIn("product_variant_count", gate)
        self.assertIn("is_product_variant", gate)
        # 门控在多变体产品的模板侧的取值：隐藏（与原生 volume 一致）
        self.assertTrue(self.product.product_variant_count > 1 and not self.product.is_product_variant)

        # 变体侧：同一条门控为假 → 字段可见、可编辑
        variant = self.product.product_variant_ids[0]
        self.assertTrue(variant.is_product_variant)
        self.assertFalse(variant.product_variant_count > 1 and not variant.is_product_variant)

        # 变体快速编辑表单不做单变体门控（它就是变体本身），别把产品表单的门控抄过来
        easy_arch = self.env["product.product"].get_view(
            view_type="form", view_id=self.env.ref("product.product_variant_easy_edit_view").id)["arch"]
        easy_container = etree.fromstring(
            easy_arch.encode()).find(".//div[@name='dimension_dimensions']")
        self.assertTrue(easy_container is not None, "变体快速编辑表单上找不到尺寸块")
        self.assertFalse(easy_container.get("invisible"))
        self.assertIn(second, self.product.product_variant_ids)

    def test_dimension_block_follows_the_logistics_group_gate(self):
        """尺寸块与原生 `volume` 同进同退（这才是「挂载正确」）。

        原生 Logistics 组带 `groups="uom.group_uom"` 的祖先组，而「只装 `product`」的环境里
        没有该组的用户整块都看不到（`volume` / `weight` 一并缺席；装了 `stock` 的环境这个门控
        被放开）。尺寸块就在同一个组里，两种环境下都必须和 `volume` 保持一致 —— 不允许出现
        「体积还在、尺寸没了」这种半截状态。
        """
        without_group = self.env["res.users"].create({
            "name": "Dimension Gate Probe",
            "login": "dimension_gate_probe",
            "group_ids": [Command.set([self.env.ref("base.group_user").id])],
        })
        arch = self.env["product.template"].with_user(without_group).get_view(
            view_type="form")["arch"]
        self.assertEqual(
            "dimension_length" in arch,
            'name="volume"' in arch,
            "尺寸块与原生 volume 的可见性必须一致（同进同退）",
        )

        # 当前用户已给 `uom.group_uom`：尺寸块与原生 volume 都在
        own_arch = self.env["product.template"].get_view(view_type="form")["arch"]
        self.assertIn('name="dimension_length"', own_arch)
        self.assertIn('name="volume"', own_arch)
