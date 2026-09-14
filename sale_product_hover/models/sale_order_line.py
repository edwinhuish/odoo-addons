# -*- coding: utf-8 -*-
"""销售订单行悬浮卡片的后端数据装配。

需求：报价单 / 销售订单的订单行列表上，鼠标悬停某行时展示产品详情浮层。
前端不解析 any2one 数据格式、也不做货币 / 数量格式化，展示数据由本方法一次装配：

- 图片：``/web/image/product.product/<id>/image_256``（无图时前端降级为占位图标）
- 名称 / 型号 / 规格：产品显示名（``display_default_code=False``，不带
  ``[参考号]`` 前缀）、``default_code``、变体属性值（``display_name`` 形如
  ``颜色: 红``，即"规格"）
- 描述：``description_sale``
- 数量 / 单价：订单行数量（行上的计量单位）、本单单价（订单币种）；
  另附产品售价（公司币种，与单价不同时才由前端展示）
- 可用库存：``qty_available``（``stock`` 提供）+ 产品计量单位名；不跟踪库存的
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

        # 产品字段一次批量读取，避免逐行访问触发多次查询；且只读模型上真实存在的
        # 字段（未装 stock / 字段改名时不会因 "Invalid field" 整批失败）
        product_model = env["product.product"]
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
        products = lines.product_id
        # display_default_code=False：名称里不重复带 "[参考号] " 前缀（型号单独展示）
        product_data = {
            row["id"]: row
            for row in products.with_context(display_default_code=False).read(read_fields)
        }
        specifications = self._get_hover_specifications(product_data)

        has_qty = "qty_available" in product_model._fields
        company_currency = env.company.currency_id
        payload = {}
        for line in lines:
            data = product_data.get(line.product_id.id)
            if not data:
                continue

            list_price = data.get("list_price") or 0.0
            # 本单单价（订单币种）与产品售价（公司币种）不同才单独展示，避免冗余
            order_currency = line.currency_id
            show_list_price = (
                order_currency != company_currency
                or not order_currency.is_zero(line.price_unit - list_price)
            )

            # 数量用行上的计量单位（订单行允许改单位）；可用库存是产品默认单位口径
            product_uom = data.get("uom_id")
            product_uom_name = product_uom[1] if product_uom else ""
            line_uom_name = line.product_uom_id.name or product_uom_name

            # 可用库存：仅为跟踪库存的产品展示（单位精度取 "Product Unit"）
            qty_text = ""
            if has_qty and data.get("is_storable"):
                qty_text = formatLang(env, data.get("qty_available") or 0.0, dp="Product Unit")

            payload[line.id] = {
                "line_id": line.id,
                "product_id": line.product_id.id,
                "name": data.get("display_name") or "",
                "reference": data.get("default_code") or "",
                "specification": specifications.get(line.product_id.id, ""),
                "image_url": "/web/image/product.product/%s/image_256" % line.product_id.id,
                "description": data.get("description_sale") or "",
                "qty_ordered_text": formatLang(env, line.product_uom_qty, dp="Product Unit"),
                "uom_name": line_uom_name,
                "unit_price_text": formatLang(env, line.price_unit, currency_obj=order_currency),
                "list_price_text": formatLang(env, list_price, currency_obj=company_currency),
                "show_list_price": show_list_price,
                "qty_available_text": qty_text,
                "available_uom_name": product_uom_name or line_uom_name,
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
