# -*- coding: utf-8 -*-
"""销售订单行悬浮卡片的后端数据装配。

需求：报价单 / 销售订单的订单行列表上，鼠标悬停某行时展示产品详情浮层。
前端不解析 any2one 数据格式、也不做货币 / 数量格式化，展示数据由本模块一次装配：

- 图片：``/web/image/product.product/<id>/image_256``（无图时前端降级为占位图标）
- 名称 / 型号 / 规格：产品显示名（``display_default_code=False``，不带
  ``[参考号]`` 前缀）、``default_code``、变体属性值（``display_name`` 形如
  ``颜色: 红``，即"规格"）
- 描述：``description_sale``
- 产品售价：``list_price``（公司币种）
- 可用库存：``qty_available``（``stock`` 提供）+ 产品计量单位名；不跟踪库存的
  产品（如服务）不展示该项

卡片只展示**产品自身**的信息：**不含订单行上的数量（``product_uom_qty``）与本单单价
（``price_unit``）**——浮层的定位是"产品详情"，本单数据在订单行上本来就看得见。
因此这里既不需要读行的数量 / 单价 / 单位 / 币种，前端新行路径也只需要 ``product_id``。

**这里只装配「已保存」的订单行**（`_get_product_hover_payload()`，按行 id 批量）。
**尚未保存的新行不经过本模块的后端**：订单行还没落库、按行 id 反查必然查不到，
那种情况由前端**按 `product_id` 用标准 ORM 直接读产品**再装配
（见 ``static/src/js/product_hover_cache.js``），线上无需升级服务端即可生效。

不提升权限（不加 ``sudo``）：产品字段以当前用户身份读取
（``search`` 走记录规则，``read`` 再校验一次访问权），记录规则天然过滤越权访问。
"""

import logging

from odoo import models
from odoo.tools.misc import formatLang

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _get_product_hover_payload(self):
        """返回 ``{order_line_id: {…浮层展示数据…}}``（已保存的订单行）。"""
        lines = self.exists().filtered("product_id")
        if not lines:
            return {}
        return self._build_hover_payload({line.id: line.product_id.id for line in lines})

    def _build_hover_payload(self, specs):
        """按 ``{key: product_id}`` 装配展示数据（卡片只展示产品侧信息，不用行上的取值）。

        展示数据的口径集中在这里（产品字段 + 价格 / 库存格式化）。未保存的新行不走后端，
        前端 `product_hover_cache.js` 按同一口径在前端装配
        （`formatFloat` / `formatMonetary` 与这里的 `formatLang` 等价），改动时请两边同步。
        """
        if not specs:
            return {}
        env = self.env
        product_model = env["product.product"]
        # 只读模型上真实存在的字段（未装 stock / 字段改名时不会因 "Invalid field" 整批失败）
        wanted_fields = [
            "display_name",
            "default_code",
            "description_sale",
            "list_price",
            "uom_id",
            "product_template_attribute_value_ids",
        ]
        if "qty_available" in product_model._fields:
            wanted_fields.append("qty_available")
        if "is_storable" in product_model._fields:
            wanted_fields.append("is_storable")
        read_fields = [name for name in wanted_fields if name in product_model._fields]

        # 用 search 而不是 browse：search 会应用记录规则并自动剔除当前用户读不到的产品，
        # read 就不会因个别产品无权访问而整批抛 AccessError；
        # active_test=False 保证已归档产品（订单行上仍可能引用）也能取到展示数据。
        products = product_model.with_context(active_test=False).search(
            [("id", "in", sorted(set(specs.values())))]
        )
        # display_default_code=False：名称里不重复带 "[参考号] " 前缀（型号单独展示）
        product_data = {
            row["id"]: row
            for row in products.with_context(display_default_code=False).read(read_fields)
        }
        specifications = self._get_hover_specifications(product_data)

        has_qty = "qty_available" in product_model._fields
        company_currency = env.company.currency_id
        payload = {}
        for key, product_id in specs.items():
            data = product_data.get(product_id)
            if not data:
                # 产品不存在 / 当前用户无权读取 → 不生成（前端表现为不弹浮层）
                _logger.info(
                    "sale_product_hover: product %s not found or not readable "
                    "for the current user, skipped",
                    product_id,
                )
                continue

            product_uom = data.get("uom_id")

            # 可用库存：仅为跟踪库存的产品展示（单位精度取 "Product Unit"）
            qty_text = ""
            if has_qty and data.get("is_storable"):
                qty_text = formatLang(env, data.get("qty_available") or 0.0, dp="Product Unit")

            payload[key] = {
                "line_id": key,
                "product_id": product_id,
                "name": data.get("display_name") or "",
                "reference": data.get("default_code") or "",
                "specification": specifications.get(product_id, ""),
                "image_url": "/web/image/product.product/%s/image_256" % product_id,
                "description": data.get("description_sale") or "",
                "list_price_text": formatLang(
                    env, data.get("list_price") or 0.0, currency_obj=company_currency
                ),
                "qty_available_text": qty_text,
                "available_uom_name": product_uom[1] if product_uom else "",
            }
        return payload

    def _get_hover_specifications(self, product_data):
        """返回 ``{product_id: "颜色: 红, 尺寸: L"}`` —— 变体属性（规格）。

        取 ``product.template.attribute.value.display_name``（属性名 + 取值）：属性名与
        取值都是**产品数据**，随产品记录的语言展示，因此不进 ``i18n/zh_CN.po``；
        拼接分隔符是通用标点，也不做翻译。属性值一次全部读出，避免逐行查询。
        """
        ptav_ids = {
            ptav_id
            for data in product_data.values()
            for ptav_id in (data.get("product_template_attribute_value_ids") or [])
        }
        if not ptav_ids:
            return {}
        ptav_names = {
            row["id"]: row["display_name"]
            for row in self.env["product.template.attribute.value"]
            .browse(sorted(ptav_ids))
            .read(["display_name"])
        }
        return {
            product_id: ", ".join(
                ptav_names[ptav_id]
                for ptav_id in (data.get("product_template_attribute_value_ids") or [])
                if ptav_id in ptav_names
            )
            for product_id, data in product_data.items()
        }
