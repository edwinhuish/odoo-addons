# -*- coding: utf-8 -*-
"""销售订单行悬浮卡片的 JSON 数据接口。"""

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SaleProductHoverController(http.Controller):
    """按订单行 id（以及尚未保存的新行）批量返回产品详情，供前端列表页预取并缓存。"""

    @http.route(
        "/sale_product_hover/payload",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def sale_product_hover_payload(self, line_ids=None, drafts=None):
        """返回 ``{key: {…展示数据…}}``。

        - ``line_ids``：**已保存**订单行的 id 列表，返回值的键是行 id；
        - ``drafts``：**尚未保存**的新行（刚新增的产品行），每项形如
          ``{key, product_id, quantity, uom_name, price_unit, currency_id}``，
          返回值的键就是传进来的 ``key``。

        两者都以当前用户身份读取（不 ``sudo``）：前端只会传当前列表页可见的订单行，
        以及用户自己刚在表单里填的值；产品字段受记录规则与访问权约束，
        返回内容仅为产品展示字段与该行单价。
        """
        ids = [
            int(line_id)
            for line_id in (line_ids or [])
            if isinstance(line_id, int) or str(line_id).isdigit()
        ]
        if not ids and not drafts:
            return {}
        try:
            payload = {}
            if ids:
                lines = request.env["sale.order.line"].browse(ids).exists()
                payload.update(lines._get_product_hover_payload())
            if drafts:
                # 空记录集上调用即可（方法只用到 env），与已保存行的装配口径完全一致
                payload.update(
                    request.env["sale.order.line"]._get_product_hover_draft_payload(drafts)
                )
            return payload
        except Exception:
            # 兜底：接口异常不应打断用户操作，只表现为「没有浮层」，
            # 因此在此记录服务端日志便于排查（前端另有 console.warn）。
            _logger.exception(
                "sale_product_hover: unable to build hover payload for lines %s / drafts %s",
                ids,
                len(drafts or []),
            )
            return {}
