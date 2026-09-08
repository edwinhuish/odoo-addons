# -*- coding: utf-8 -*-
"""产品卡片视图 JSON 数据接口。"""

from odoo import http
from odoo.http import request


class ProductCardController(http.Controller):
    """向瀑布流卡片视图提供整页 payload，避免每个卡片单独发请求。"""

    @http.route(
        "/product_card/payload",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def product_card_payload(self, template_ids):
        """返回 {template_id: {..卡片数据..}}。

        使用 sudo 读取库存在手等字段，保证对普通有产品/库存读权限的
        内部用户也能获得完整数据；payload 本身不含敏感信息。
        """
        templates = (
            request.env["product.template"]
            .sudo()
            .browse([int(tid) for tid in (template_ids or [])])
        )
        return templates._get_product_card_view_payload()
