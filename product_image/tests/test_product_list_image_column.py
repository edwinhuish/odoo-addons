# -*- coding: utf-8 -*-
"""产品列表「Images」列（只显示主图）的回归用例。

需求：产品列表勾选「Images」列后要能显示产品图片（**仅主图**），并在三处入口都生效：

- 库存 / 产品：`stock.product_template_action_product`（动作未指定列表视图 → 模型默认列表视图）
- 销售 / 产品：`sale.product_template_action`（列表视图 `account.product_template_list_view_sellable_inherit`）
- 采购 / 产品：`purchase.product_normal_action_puchased`（列表视图 `account.product_template_list_view_purchasable_inherit`）

三个列表视图都是原生 `product.product_template_tree_view` 的后代，本模块只继承该基础视图，
因此三处应当同时生效（下面的用例逐个用 `get_view` 取「界面实际使用的列表视图」合成 arch 来核对）。

可选模块（`stock` / `sale` / `purchase`）未安装时按配置 `skipTest` —— 本模块 `depends` 只有
`product`，必须能单独安装（根 `AGENTS.md` 第 3 节「模块间可选集成必须解耦」）。

跑法：

    task test -- product_image
    task test -- product_image,stock,sale_management,purchase --test-tags=/product_image
"""

import unittest

from lxml import etree

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# 8×8 纯色 PNG：合法图片，够走通 image.mixin 的多尺寸 related 链路
PNG_8PX_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAEUlEQVR42mM4YWODFTEMLQkA"
    "ZZlQAS/gME0AAAAASUVORK5CYII="
)

IMAGE_COLUMN = "image_128"
COLUMN_LABEL = "Images"


@tagged("post_install", "-at_install")
class TestProductListImageColumn(TransactionCase):
    """列表图片列的 arch 契约 + 数据绑定。"""

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    def _get_list_arch(self, view_id=None):
        """取 `product.template` 列表视图的合成 arch（含全部继承视图）。"""
        result = self.env["product.template"].get_view(view_id or None, "list")
        return etree.fromstring(result["arch"])

    def _get_page_list_arch(self, action):
        """取动作在界面上实际使用的列表视图的合成 arch。

        动作显式指定了列表视图就用它，否则传 `None` 让 Odoo 走默认列表视图
        （与前端打开该动作时的解析一致）。
        """
        list_view = action.view_ids.filtered(lambda view: view.view_mode == "list")[:1]
        return self._get_list_arch(list_view.view_id.id)

    def _assert_has_main_image_column(self, arch, where):
        """断言某列表视图里有且只有一个「主图」列，且默认隐藏、可切换。"""
        nodes = arch.xpath("//field[@name='%s']" % IMAGE_COLUMN)
        self.assertEqual(
            len(nodes), 1,
            "%s: the list view must have exactly one `%s` column" % (where, IMAGE_COLUMN),
        )
        node = nodes[0]
        self.assertEqual(
            node.get("string"), COLUMN_LABEL,
            "%s: the column label must be `%s`" % (where, COLUMN_LABEL),
        )
        self.assertEqual(
            node.get("widget"), "image",
            "%s: column `%s` must use the image widget" % (where, IMAGE_COLUMN),
        )
        self.assertTrue(
            node.get("readonly"),
            "%s: the image column must be readonly in the list" % where,
        )
        # optional="hide" = 默认隐藏、可由列表右上角「可选列」勾选显示；
        # column_invisible 则是彻底不渲染、无法切换 —— 两者语义不同，后者是错的。
        self.assertEqual(
            node.get("optional"), "hide",
            "%s: the image column must be an optional column (hidden by default)" % where,
        )
        self.assertFalse(
            node.get("column_invisible"),
            "%s: the image column must not use column_invisible (it could not be toggled)" % where,
        )
        # 位置：在 `default_code` 之后（XPath union 按文档顺序返回）
        order = [
            field.get("name")
            for field in arch.xpath(
                "//field[@name='default_code'] | //field[@name='%s']" % IMAGE_COLUMN
            )
        ]
        self.assertEqual(
            order, ["default_code", IMAGE_COLUMN],
            "%s: the image column must come after `default_code`" % where,
        )

    def _assert_page(self, module, action_xmlid):
        action = self.env.ref(action_xmlid, raise_if_not_found=False)
        if not action:
            raise unittest.SkipTest("%s is not installed" % module)
        self._assert_has_main_image_column(
            self._get_page_list_arch(action), action_xmlid)

    # ------------------------------------------------------------------
    # 基础列表视图（不依赖任何可选模块）
    # ------------------------------------------------------------------

    def test_default_list_view_has_the_main_image_column(self):
        """产品模板默认列表视图带「主图」列（库存入口走的就是它）。"""
        self._assert_has_main_image_column(
            self._get_list_arch(), "product.template default list view")

    def test_list_column_is_not_the_gallery_counter_anymore(self):
        """「Images」列不再绑图库计数（原实现只显示数字，看不到图片）。"""
        arch = self._get_list_arch()
        self.assertFalse(
            arch.xpath("//field[@name='image_gallery_count']"),
            "`image_gallery_count` must not be used as a list column anymore",
        )

    def test_column_is_bound_to_the_native_main_image(self):
        """列绑原生 `image_128`（`image.mixin`，related → `image_1920` = 产品主图）。"""
        field = self.env["product.template"]._fields[IMAGE_COLUMN]
        self.assertEqual(field.type, "binary")
        self.assertEqual(field.related, "image_1920")
        self.assertTrue(self.env["product.template"]._fields["image_1920"].store)

    def test_only_the_main_image_is_shown(self):
        """只有图库补充图时列是空的；设了主图后列才有值（仅主图，不含补充图）。"""
        product = self.env["product.template"].create({"name": "Test list image column"})
        self.env["product.image.gallery"].create({
            "product_tmpl_id": product.id,
            "name": "Gallery extra image",
            "image_1920": PNG_8PX_B64,
        })
        product.invalidate_recordset()
        self.assertFalse(
            product.image_128,
            "with only gallery images and no main image, the column must stay empty",
        )

        product.image_1920 = PNG_8PX_B64
        product.invalidate_recordset()
        self.assertTrue(product.image_128, "the column must show the main image once set")

    # ------------------------------------------------------------------
    # 三处入口（可选模块未安装时跳过）
    # ------------------------------------------------------------------

    def test_inventory_products_page(self):
        """库存 / 产品：列表带「主图」列。"""
        self._assert_page("stock", "stock.product_template_action_product")

    def test_sales_products_page(self):
        """销售 / 产品：列表带「主图」列。"""
        self._assert_page("sale", "sale.product_template_action")

    def test_purchase_products_page(self):
        """采购 / 产品：列表带「主图」列。"""
        self._assert_page("purchase", "purchase.product_normal_action_puchased")
