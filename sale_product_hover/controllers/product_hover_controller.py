# -*- coding: utf-8 -*-
"""销售订单行悬浮卡片的 JSON 数据接口。"""

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# 与 __manifest__.py 的 version 保持一致（**三处同步**：manifest / 本文件 / 
# static/src/js/product_hover_list_patch.js 的 MODULE_VERSION）。
# 接口会把它回显给前端（保留键 ``__server_version``），前端与自己的资源版本比对：
# 不一致或缺失就说明「服务端 Python 还没升级 / 前端资源没重建」——这是本模块排障里
# 最常踩的坑，前端据此直接给出可执行的提示。
MODULE_VERSION = "19.0.1.3.1"

# 保留键：只在响应里携带服务端版本，不参与任何行的取值（订单行 id 是数字、
# 未保存新行的键是 `datapoint_N`，都不会与它冲突）
SERVER_VERSION_KEY = "__server_version"


class SaleProductHoverController(http.Controller):
    """按订单行 id（以及尚未保存的新行）批量返回产品详情，供前端列表页预取并缓存。"""

    @http.route(
        "/sale_product_hover/payload",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def sale_product_hover_payload(self, line_ids=None, drafts=None, version=None):
        """返回 ``{key: {…展示数据…}}``（另含保留键 ``__server_version``）。

        - ``line_ids``：**已保存**订单行的 id 列表，返回值的键是行 id；
        - ``drafts``：**尚未保存**的新行（刚新增的产品行），每项形如
          ``{key, product_id, quantity, uom_name, price_unit, currency_id}``，
          返回值的键就是传进来的 ``key``；
        - ``version``：前端资源版本，仅用于服务端日志比对（不一致时提示重跑 ``-u``）。

        两者都以当前用户身份读取（不 ``sudo``）：前端只会传当前列表页可见的订单行，
        以及用户自己刚在表单里填的值；产品字段受记录规则与访问权约束，
        返回内容仅为产品展示字段与该行单价。
        """
        if version and version != MODULE_VERSION:
            _logger.warning(
                "sale_product_hover: front-end assets %s do not match the installed "
                "module version %s; run `-u sale_product_hover` and hard refresh "
                "(Ctrl+Shift+R).",
                version,
                MODULE_VERSION,
            )
        ids = [
            int(line_id)
            for line_id in (line_ids or [])
            if isinstance(line_id, int) or str(line_id).isdigit()
        ]
        if not ids and not drafts:
            return {SERVER_VERSION_KEY: MODULE_VERSION}
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
            payload[SERVER_VERSION_KEY] = MODULE_VERSION
            return payload
        except Exception:
            # 兜底：接口异常不应打断用户操作，只表现为「没有浮层」，
            # 因此在此记录服务端日志便于排查（前端另有 console.warn）。
            _logger.exception(
                "sale_product_hover: unable to build hover payload for lines %s / drafts %s",
                ids,
                len(drafts or []),
            )
            # 仍然回显版本：前端据此区分「后端报错」与「后端未升级」
            return {SERVER_VERSION_KEY: MODULE_VERSION}
