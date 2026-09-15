# -*- coding: utf-8 -*-
"""销售订单行悬浮卡片的 JSON 数据接口。

**只服务「已保存」的订单行**。未保存的新行（刚新增的产品行）不经过这里：
订单行还没落库、服务端没有这条记录，按行 id 反查必然查不到——那种情况由前端
**按 `product_id` 用标准 ORM 直接读产品**再装配卡片数据
（见 ``static/src/js/product_hover_cache.js``）。
"""

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# 与 __manifest__.py 的 version 保持一致（**三处同步**：manifest / 本文件 /
# static/src/js/product_hover_list_patch.js 的 MODULE_VERSION）。
# 接口会把它回显给前端（保留键 ``__server_version``），前端据此判断服务端 Python
# 是否已升级——本模块踩过多次「静态资源已更新、后端没升级」的坑。
MODULE_VERSION = "19.0.1.5.0"

# 保留键：只在响应里携带服务端版本，不参与任何行的取值（订单行 id 是数字，不会与它冲突）
SERVER_VERSION_KEY = "__server_version"


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
        """返回 ``{order_line_id: {…展示数据…}}``（另含保留键 ``__server_version``）。

        以当前用户身份读取（不 ``sudo``）：前端只会传当前列表页可见的订单行，
        产品字段受记录规则与访问权约束，返回内容**仅为产品的展示字段**
        （图片 / 名称 / 型号 / 规格 / 描述 / 产品售价 / 可用库存，不含行上的数量与单价）。

        **不要给这个接口加参数来「顺带处理新行」**：新行不在订单里，任何按行 id 的方案都
        无从下手；旧版本一旦收到它不认识的参数（如曾经的 ``drafts``）会整批报错，
        连已保存行的预览也会一起失效。
        """
        ids = [
            int(line_id)
            for line_id in (line_ids or [])
            if isinstance(line_id, int) or str(line_id).isdigit()
        ]
        if not ids:
            # 空请求也回显版本：前端用它探测服务端是否已升级（见 product_hover_cache.js）
            return {SERVER_VERSION_KEY: MODULE_VERSION}
        try:
            payload = (
                request.env["sale.order.line"]
                .browse(ids)
                .exists()
                ._get_product_hover_payload()
            )
            payload[SERVER_VERSION_KEY] = MODULE_VERSION
            return payload
        except Exception:
            # 兜底：接口异常不应打断用户操作，只表现为「没有浮层」，
            # 因此在此记录服务端日志便于排查（前端另有 console.error）。
            _logger.exception(
                "sale_product_hover: unable to build hover payload for lines %s", ids
            )
            # 仍然回显版本：前端据此区分「后端报错」与「后端未升级」
            return {SERVER_VERSION_KEY: MODULE_VERSION}
