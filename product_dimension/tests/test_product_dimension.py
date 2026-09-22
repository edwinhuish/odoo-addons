# -*- coding: utf-8 -*-
"""尺寸字段的归属与 Volume 同步。

重点锁两件事：
1. 尺寸的真身在**变体**上，每条变体各算各的 Volume（这是 T-021 要解决的问题）；
2. 模板侧只是「单变体桥接」：单变体时读写都落到那条变体，多变体时读出空值、写入不动任何变体
   （与原生 `volume` / `weight` 同构）。
"""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProductDimension(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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
