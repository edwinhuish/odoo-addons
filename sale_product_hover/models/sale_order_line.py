# -*- coding: utf-8 -*-
"""销售订单行悬浮卡片的后端数据装配。

需求：报价单 / 销售订单的订单行列表上，鼠标悬停某行时展示产品详情浮层。
前端不解析 any2one 数据格式、也不做货币格式化，展示数据由本方法一次装配：

- 图片：``/web/image/product.product/<id>/image_256``（无图时前端降级为占位图标）
- 名称 / 型号 / 描述：产品显示名（``display_default_code=False``，不带
  ``[参考号]`` 前缀）、``default_code``、``description_sale``
- 价格：产品售价（公司币种）与本单单价（订单币种），用 ``formatLang``
  按用户语言与货币精度格式化，前端直接展示字符串
- 可用库存：``qty_available``（``stock`` 提供）+ 计量单位名；不跟踪库存的
  产品（如服务）不展示该项

本方法不提升权限（不加 ``sudo``）：调用方控制器以当前用户身份 browse，
前端只会传当前列表页可见的行，记录规则天然过滤越权访问。
"""

from odoo import models
from odoo.tools.misc import formatLang


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _get_product_hover_payload(self):
        """返回 ``{order_line_id: {…浮层展示数据…}}``。"""
        if not self:
            return {}
        env = self.env
        lines = self.exists().filtered("product_id")
        if not lines:
            return {}

        # 产品字段一次批量读取，避免逐行访问触发多次查询
        products = lines.product_id
        read_fields = ["display_name", "default_code", "description_sale", "list_price", "uom_id"]
        has_qty = "qty_available" in env["product.product"]._fields
        if has_qty:
            read_fields.append("qty_available")
        has_storable = "is_storable" in env["product.template"]._fields
        if has_storable:
            read_fields.append("is_storable")
        # display_default_code=False：名称里不重复带 "[参考号] " 前缀（型号单独展示）
        product_data = {
            row["id"]: row
            for row in products.with_context(display_default_code=False).read(read_fields)
        }

        company_currency = env.company.currency_id
        payload = {}
        for line in lines:
            data = product_data.get(line.product_id.id)
            if not data:
                continue

            # 本单单价（订单币种）与产品售价（公司币种）不同才单独展示，避免冗余
            order_currency = line.currency_id
            show_order_price = (
                order_currency != company_currency
                or not order_currency.is_zero(line.price_unit - data["list_price"])
            )

            # 可用库存：仅为跟踪库存的产品展示（单位精度取 "Product Unit"）
            qty_text = ""
            uom_name = data["uom_id"][1] if data.get("uom_id") else ""
            if has_qty and has_storable and data.get("is_storable"):
                qty_text = formatLang(env, data.get("qty_available") or 0.0, dp="Product Unit")

            payload[line.id] = {
                "line_id": line.id,
                "product_id": line.product_id.id,
                "name": data["display_name"] or "",
                "reference": data["default_code"] or "",
                "image_url": "/web/image/product.product/%s/image_256" % line.product_id.id,
                "description": data["description_sale"] or "",
                "sales_price_text": formatLang(env, data["list_price"], currency_obj=company_currency),
                "order_price_text": formatLang(env, line.price_unit, currency_obj=order_currency),
                "show_order_price": show_order_price,
                "qty_available_text": qty_text,
                "uom_name": uom_name,
            }
        return payload
