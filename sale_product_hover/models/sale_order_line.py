# -*- coding: utf-8 -*-
"""销售订单行悬浮卡片的后端数据装配。

需求：报价单 / 销售订单的订单行列表上，鼠标悬停某行时展示产品详情浮层。
前端不解析 any2one 数据格式、也不做货币 / 数量格式化，展示数据由本模块一次装配：

- 图片：``/web/image/product.product/<id>/image_256``（无图时前端降级为占位图标）
- 名称 / 型号 / 规格：产品显示名（``display_default_code=False``，不带
  ``[参考号]`` 前缀）、``default_code``、变体属性值（``display_name`` 形如
  ``颜色: 红``，即"规格"）
- 描述：``description_sale``
- 数量 / 单价：订单行数量（行上的计量单位）、本单单价（订单币种）；
  另附产品售价（公司币种，与单价不同时才由前端展示）
- 可用库存：``qty_available``（``stock`` 提供）+ 产品计量单位名；不跟踪库存的
  产品（如服务）不展示该项

有两条取数入口，最终都走 `_build_hover_payload()`：

- `_get_product_hover_payload()`：**已保存**的订单行，按行 id 批量装配；
- `_get_product_hover_draft_payload()`：**尚未保存**的新行（刚新增的产品行），
  没有数据库 id，改为由前端把表单里正在编辑的值传上来。

两条入口都不提升权限（不加 ``sudo``）：产品字段以当前用户身份读取
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
        return self._build_hover_payload(
            {
                line.id: {
                    "product_id": line.product_id.id,
                    "quantity": line.product_uom_qty,
                    "uom_name": line.product_uom_id.name,
                    "price_unit": line.price_unit,
                    "currency": line.currency_id,
                }
                for line in lines
            }
        )

    def _get_product_hover_draft_payload(self, drafts):
        """返回 ``{前端 key: {…浮层展示数据…}}``（**尚未保存**的新订单行）。

        新行还没有数据库 id（`sale.order.line` 记录未落库），浮层数据不可能按 id 反查，
        因此由前端把表单里**正在编辑**的值传上来：

        - ``key``：前端缓存用的键（未保存行的 Owl datapoint id，形如 ``datapoint_42``）；
        - ``product_id``：选中的产品；
        - ``quantity`` / ``uom_name`` / ``price_unit`` / ``currency_id``：行上当前的取值。

        传上来的数量与单价**只用于展示，不写库**；产品字段仍以当前用户身份读取并受记录规则
        约束，因此不存在越权风险（用户最多只能看到自己刚填的那些数字）。
        币种取不到时退回公司币种。
        """
        env = self.env
        company_currency = env.company.currency_id
        specs = {}
        currency_ids = set()
        for draft in drafts or []:
            if not isinstance(draft, dict):
                continue
            key = str(draft.get("key") or "").strip()
            product_id = draft.get("product_id")
            if isinstance(product_id, str) and product_id.isdigit():
                # 前端万一把 id 序列化成了字符串，这里兜一下，不要静默丢掉整行
                product_id = int(product_id)
            if not key or not isinstance(product_id, int) or isinstance(product_id, bool):
                # 静默丢弃会让前端「永远拿不到数据」且难以定位，故记一条服务端日志
                _logger.warning(
                    "sale_product_hover: dropping draft line %r "
                    "(key=%r, product_id=%r is not a valid product id)",
                    draft,
                    key,
                    draft.get("product_id"),
                )
                continue
            currency_id = draft.get("currency_id")
            if isinstance(currency_id, int) and not isinstance(currency_id, bool):
                currency_ids.add(currency_id)
            else:
                currency_id = None
            specs[key] = {
                "product_id": product_id,
                "quantity": self._hover_float(draft.get("quantity"), 1.0),
                "uom_name": str(draft.get("uom_name") or ""),
                "price_unit": self._hover_float(draft.get("price_unit"), 0.0),
                "currency": None,
                # 私有键：下面解析成 res.currency 记录集后删掉，避免混进 payload
                "_currency_id": currency_id,
            }
        if not specs:
            return {}
        currencies = (
            {
                currency.id: currency
                for currency in env["res.currency"].browse(sorted(currency_ids)).exists()
            }
            if currency_ids
            else {}
        )
        for spec in specs.values():
            spec["currency"] = currencies.get(spec.pop("_currency_id")) or company_currency
        return self._build_hover_payload(specs)

    def _build_hover_payload(self, specs):
        """按 ``{key: {product_id, quantity, uom_name, price_unit, currency}}`` 装配展示数据。

        已保存行与未保存的新行共用本方法，保证两种情况下浮层口径完全一致。
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

        # 用 search 而不是 browse：产品 id 可能来自前端（未保存的新行），
        # search 会应用记录规则并自动剔除当前用户读不到的产品，read 就不会整批抛 AccessError；
        # active_test=False 保证已归档产品（订单行上仍可能引用）也能取到展示数据。
        products = product_model.with_context(active_test=False).search(
            [("id", "in", sorted({spec["product_id"] for spec in specs.values()}))]
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
        for key, spec in specs.items():
            data = product_data.get(spec["product_id"])
            if not data:
                # 产品不存在 / 当前用户无权读取 → 不生成（前端表现为不弹浮层）
                _logger.info(
                    "sale_product_hover: product %s not found or not readable "
                    "for the current user, skipped",
                    spec["product_id"],
                )
                continue

            list_price = data.get("list_price") or 0.0
            # 本单单价（订单币种）与产品售价（公司币种）不同才单独展示，避免冗余
            order_currency = spec.get("currency") or company_currency
            show_list_price = (
                order_currency != company_currency
                or not order_currency.is_zero(spec["price_unit"] - list_price)
            )

            # 数量用行上的计量单位（订单行允许改单位）；可用库存是产品默认单位口径
            product_uom = data.get("uom_id")
            product_uom_name = product_uom[1] if product_uom else ""
            line_uom_name = spec.get("uom_name") or product_uom_name

            # 可用库存：仅为跟踪库存的产品展示（单位精度取 "Product Unit"）
            qty_text = ""
            if has_qty and data.get("is_storable"):
                qty_text = formatLang(env, data.get("qty_available") or 0.0, dp="Product Unit")

            payload[key] = {
                "line_id": key,
                "product_id": spec["product_id"],
                "name": data.get("display_name") or "",
                "reference": data.get("default_code") or "",
                "specification": specifications.get(spec["product_id"], ""),
                "image_url": "/web/image/product.product/%s/image_256" % spec["product_id"],
                "description": data.get("description_sale") or "",
                "qty_ordered_text": formatLang(env, spec["quantity"], dp="Product Unit"),
                "uom_name": line_uom_name,
                "unit_price_text": formatLang(env, spec["price_unit"], currency_obj=order_currency),
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

    @staticmethod
    def _hover_float(value, default):
        """把前端传来的数字收敛成 ``float``（JSON 里可能是 int / float / 字符串 / None）。"""
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
