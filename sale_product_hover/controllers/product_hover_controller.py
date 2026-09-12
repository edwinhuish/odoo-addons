# -*- coding: utf-8 -*-
"""销售订单行悬浮卡片的 JSON 数据接口。"""

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SaleProductHoverController(http.Controller):
    """按订单行 id 批量返回产品详情，供前端列表页预取并缓存。"""

    @http.route(
        "/sale_product_hover/payload",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def sale_product_hover_payload(self, line_ids=None):
        """返回 ``{order_line_id: {…展示数据…}}``。

        以当前用户身份读取（不 ``sudo``）：前端只传当前列表页可见的订单行，
        读取时记录规则照常生效；返回内容仅为产品展示字段与该行单价。
        """
        ids = [
            int(line_id)
            for line_id in (line_ids or [])
            if isinstance(line_id, int) or str(line_id).isdigit()
        ]
        if not ids:
            return {}
        lines = request.env["sale.order.line"].browse(ids).exists()
        try:
            return lines._get_product_hover_payload()
        except Exception:
            # 兜底：接口异常不应打断用户操作，只表现为「没有浮层」，
            # 因此在此记录服务端日志便于排查（前端另有 console.warn）。
            _logger.exception("sale_product_hover: unable to build hover payload for lines %s", ids)
            return {}
