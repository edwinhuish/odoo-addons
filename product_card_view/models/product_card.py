# -*- coding: utf-8 -*-
"""产品卡片视图后端数据装配。

为前端瀑布流卡片提供一次 JSON payload（一次性查询，避免逐卡请求）：
- 模板层：标题 / 编号（default_code）/ 全部变体在手总量；
  图片 = 模板主图（product.template.image_512）+ 模板共享图库（product.image.gallery，
  product_image 可选：未安装则 env.get 返回 None，图库留空，前端只展示主图）。
- 变体层：每个 product.product 的编号 / 在手；图片 = 变体主图（无则原生回退模板主图）
  + 变体专属图库（product_image 安装时才有）。
- 变体按钮行：只保留真正出现在现有变体组合里的属性与值，避免点出"不存在的组合"。
"""

from collections import defaultdict

from odoo import api, fields, models


class IrUiView(models.Model):
    _inherit = "ir.ui.view"

    # 扩展 view type Selection，新增 'card'（卡片瀑布流视图）
    type = fields.Selection(selection_add=[("card", "Card")], ondelete={"card": "cascade"})


class IrActionsActWindowView(models.Model):
    _inherit = "ir.actions.act_window.view"

    # 扩展 view_mode Selection，新增 'card'（让 ir.actions.act_window.view 记录可用 card）
    view_mode = fields.Selection(selection_add=[("card", "Card")], ondelete={"card": "cascade"})

    @api.model
    def _sync_product_card_views(self):
        """条件性注入 card 视图到 sale / purchase 的产品动作。

        sale / purchase 为可选依赖（不在 __manifest__.depends 中）：仅当对应
        模块已安装（其 act_window xmlid 可解析）时才创建 act_window.view 记录，
        未安装则跳过。由 product_card_views.xml 的 <function> 在 install/upgrade
        时调用，幂等——已存在 card 记录则跳过。
        """
        card_view = self.env.ref(
            "product_card_view.product_template_card_view", raise_if_not_found=False
        )
        if not card_view:
            return
        # (本模块登记的 ir.model.data name, 目标 action 的完整 xmlid)
        targets = (
            ("product_template_action_sale_card_view", "sale.product_template_action"),
            ("product_normal_action_puchased_card_view", "purchase.product_normal_action_puchased"),
        )
        for rec_name, action_xmlid in targets:
            action = self.env.ref(action_xmlid, raise_if_not_found=False)
            if not action:
                continue  # 对应模块未安装，跳过
            if self.search_count(
                [("act_window_id", "=", action.id), ("view_mode", "=", "card")]
            ):
                continue  # 已存在，幂等跳过
            rec = self.create(
                {
                    "act_window_id": action.id,
                    "view_id": card_view.id,
                    "view_mode": "card",
                    "sequence": 3,
                }
            )
            self.env["ir.model.data"].create(
                {
                    "name": rec_name,
                    "module": "product_card_view",
                    "model": "ir.actions.act_window.view",
                    "res_id": rec.id,
                    "noupdate": True,
                }
            )
        return True


class ProductTemplate(models.Model):
    """扩展 product.template，提供卡片视图数据，不新增字段。"""

    _inherit = "product.template"

    def _get_product_card_view_payload(self):
        """返回本 recordset（product.template）的卡片数据映射 {template_id: {...}}。"""
        if not self:
            return {}
        templates = self
        env = self.env
        tpl_ids = templates.ids

        # ---- 库存字段在运行时是否可用（模块内建 stock，防御性判断便于复用） ----
        has_qty = "qty_available" in env["product.product"]._fields
        has_storable = "is_storable" in env["product.template"]._fields

        # ---- 变体（仅 active 变体参与按钮选择与在手上报） ----
        # 按 (product_tmpl_id, id) 排序：后续按模板分组时各模板内变体天然按 id 升序，
        # 省去构造 payload 时每模板再 sorted 一次。
        variants = env["product.product"].search(
            [("product_tmpl_id", "in", tpl_ids)], order="product_tmpl_id, id"
        )
        variant_ids = variants.ids

        # 变体在手数量：一次 read 触发一次计算，避免逐行重算
        variant_qty = {}
        if has_qty:
            for row in variants.read(["qty_available"]):
                variant_qty[row["id"]] = row["qty_available"]

        # ---- 收集每个变体的 属性->属性值 映射，并反推每个模板用到的 {attr_id: [value_id]} ----
        variants_by_tpl = defaultdict(list)
        variant_attr_map = {}                       # variant id -> {attribute_id: value_id}
        tpl_attr_values = defaultdict(dict)         # tpl id -> {attribute_id: [value_id...]}
        all_attr_ids = set()
        all_value_ids = set()
        for variant in variants:
            tpl_id = variant.product_tmpl_id.id
            variants_by_tpl[tpl_id].append(variant)
            attr_map = {}
            # Odoo 19: 变体属性经 product.template.attribute.value（PTAV）关联，
            # PTAV.attribute_id 指向属性，PTAV.product_attribute_value_id 指向属性值。
            for ptav in variant.product_template_attribute_value_ids:
                attr_id = ptav.attribute_id.id
                value_id = ptav.product_attribute_value_id.id
                attr_map[attr_id] = value_id
                all_attr_ids.add(attr_id)
                all_value_ids.add(value_id)
                # 由变体映射反推每个模板的 {attr_id: [value_id]}，顺序可控且去重
                value_list = tpl_attr_values[tpl_id].setdefault(attr_id, [])
                if value_id not in value_list:
                    value_list.append(value_id)
            variant_attr_map[variant.id] = attr_map

        # ---- 属性 / 属性值名称与排序键：一次 browse 缓存 ----
        attr_records = env["product.attribute"].browse(sorted(all_attr_ids))
        attr_name = {attr.id: attr.name for attr in attr_records}
        attr_type = {attr.id: attr.display_type for attr in attr_records}
        attr_order = {attr.id: (attr.sequence, attr.id) for attr in attr_records}
        value_records = env["product.attribute.value"].browse(sorted(all_value_ids))
        value_name = {value.id: value.name for value in value_records}
        value_html_color = {value.id: value.html_color for value in value_records}
        value_order = {value.id: (value.sequence, value.id) for value in value_records}

        # ---- 图库补充图：product.image.gallery（product_image 可选模块） ----
        # 未安装 product_image 时该模型不存在，env.get 返回 None，
        # tmpl/variant 图库留空，前端只展示主图（record.js images getter 已兼容）。
        tmpl_gallery_ids = defaultdict(list)
        variant_gallery_ids = defaultdict(list)
        Gallery = env.get("product.image.gallery")
        if Gallery is not None:
            galleries = Gallery.search(
                ["|", ("product_tmpl_id", "in", tpl_ids), ("product_id", "in", variant_ids)]
            )
            for gallery in galleries.sorted(key=lambda g: (g.sequence, g.id)):
                if gallery.product_id:
                    variant_gallery_ids[gallery.product_id.id].append(gallery.id)
                elif gallery.product_tmpl_id:
                    tmpl_gallery_ids[gallery.product_tmpl_id.id].append(gallery.id)

        # ---- 构造每个模板的 payload ----
        payload = {}
        for template in templates:
            tpl_id = template.id
            # variants 已按 (product_tmpl_id, id) 排序，此处直接取即 id 升序
            tpl_variants = variants_by_tpl.get(tpl_id, [])
            tpl_default_code = template.default_code
            tracked = template.is_storable if has_storable else False
            on_hand_total = None
            if has_qty:
                on_hand_total = sum(variant_qty.get(v.id, 0.0) for v in tpl_variants)

            # 变体按钮行：属性按 attribute.sequence 排，值按 value.sequence 排
            attr_values = tpl_attr_values.get(tpl_id, {})
            rows = []
            for attr_id, value_ids in sorted(attr_values.items(), key=lambda kv: attr_order.get(kv[0], (0, kv[0]))):
                values = sorted(
                    value_ids,
                    key=lambda v_id: (value_order.get(v_id, (0, v_id)), v_id),
                )
                rows.append(
                    {
                        "attr_id": attr_id,
                        "attr_name": attr_name.get(attr_id, ""),
                        "attr_type": attr_type.get(attr_id, "radio"),
                        "values": [
                            {
                                "id": v_id,
                                "name": value_name.get(v_id, ""),
                                "html_color": value_html_color.get(v_id, ""),
                            }
                            for v_id in values
                        ],
                    }
                )

            variants_payload = []
            for variant in tpl_variants:
                variants_payload.append(
                    {
                        "id": variant.id,
                        "reference": variant.default_code or tpl_default_code or "",
                        "on_hand": variant_qty.get(variant.id) if has_qty else None,
                        "values": dict(variant_attr_map.get(variant.id, {})),
                    }
                )

            payload[tpl_id] = {
                "name": template.name,
                "reference": tpl_default_code or "",
                "tracked": tracked,
                "has_stock": has_qty,
                "on_hand_total": on_hand_total,
                "rows": rows,
                "variants": variants_payload,
                "template_images": tmpl_gallery_ids.get(tpl_id, []),
                "variant_images": {
                    variant.id: variant_gallery_ids.get(variant.id, [])
                    for variant in tpl_variants
                },
            }
        return payload
