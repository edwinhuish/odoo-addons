# -*- coding: utf-8 -*-
"""扩展 Odoo 的 PWA webmanifest，为多标签栏启用 Window Controls Overlay。

采用 Odoo 标准的控制器继承：`odoo.http._generate_routing_rules()` 会按控制器
继承树取「叶子」实现（类名为 `WebManifest (extended by WebManifestMultiTabs)`），
因此重写 `_get_webmanifest()` 即可生效，无需 monkey-patch 核心类。

不覆盖 `scope` / `start_url`：核心 `WebManifest._get_webmanifest()` 已经写入
`scope="/odoo"` 与 `start_url="/odoo"`；把 scope 放宽到 `/` 会与核心
`/scoped_app` 的独立 PWA 作用域冲突。启动入口差异（`/odoo/` 与 `/odoo`）由
前端 `normalizeUrl()` 统一，见 static/src/js/multi_tabs.js。
"""

from odoo.addons.web.controllers.webmanifest import WebManifest


class WebManifestMultiTabs(WebManifest):
    """给 PWA manifest 注入 `display_override`，让标签栏能占据标题栏区域。"""

    def _get_webmanifest(self):
        manifest = super()._get_webmanifest()
        # window-controls-overlay：隐藏原生标题栏，由标签栏接管顶部区域（可拖动）
        manifest["display_override"] = ["window-controls-overlay"]
        return manifest
