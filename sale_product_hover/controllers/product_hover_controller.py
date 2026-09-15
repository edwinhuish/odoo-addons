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
from odoo.modules.module import get_manifest

_logger = logging.getLogger(__name__)

# 本模块的版本号**只有一个来源**：``__manifest__.py`` 的 ``"version"``，这里直接读它，
# 不再手写第二份常量（手写时改版本容易漏改，会让前后端版本自证误报）。
#
# `get_manifest()` 按 addons_path 找到本模块并解析清单文件，返回 `Manifest`（dict-like）；
# 模块找不到时返回空 dict（正常不可能发生——本文件能被导入就说明模块在 addons_path 里）。
# 注意：它读的是**进程启动时**扫到的清单（`Manifest` 内部有缓存），改了
# `__manifest__.py` 仍要 `-u` / 重启进程才生效。
#
# 接口会把它回显给前端（保留键 ``__server_version``），前端据此判断服务端 Python
# 是否已升级——本模块踩过多次「静态资源已更新、后端没升级」的坑。
try:
    MODULE_VERSION = get_manifest("sale_product_hover").get("version")
except Exception:  # noqa: BLE001 — 读版本失败绝不能让服务起不来
    MODULE_VERSION = None
if not MODULE_VERSION:
    _logger.warning(
        "sale_product_hover: unable to read 'version' from __manifest__.py; "
        "the front-end version self-check will report a mismatch"
    )
    MODULE_VERSION = "unknown"

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
