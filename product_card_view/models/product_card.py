# -*- coding: utf-8 -*-
"""产品卡片视图后端数据装配。

为前端瀑布流卡片提供一次 JSON payload（一次性查询，避免逐卡请求）：
- 模板层：标题 / 编号 / 全部变体在手总量；多变体产品的编号优先取产品母型号
  （base_reference，product_reference 可选模块），没有时回退原生 default_code
  （单变体产品不读母型号：它的编号真身在变体上）；
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

    # 扩展 view_mode Selection，新增 'card'（让 ir.actions.act_window.view 记录可用 card；
    # 本模块静态声明的 3 条 card 记录需要它，见 views/product_card_views.xml）
    view_mode = fields.Selection(selection_add=[("card", "Card")], ondelete={"card": "cascade"})


class IrActionsActWindow(models.Model):
    _inherit = "ir.actions.act_window"

    @api.depends("view_ids.view_mode", "view_mode", "view_id.type")
    def _compute_views(self):
        """把 card 视图放到所有 `product.template` 动作的 `views` 最前面。

        为什么在这里做（而不是往别的模块的 action 里建记录）：客户端切换器的条目与服务端算出来的
        `action.views` 一一对应，并且取 `views[0]` 作默认视图（见 `action_service.js::_executeActWindowAction`）。
        「给 action 建 `ir.actions.act_window.view` 记录」那条路有**安装顺序**问题：本模块装完时
        `sale` / `purchase` 往往还没装，那一刻的 `<function>` 看不到它们的 action，之后也没有重跑机会
        —— 全新安装（`task init -- --fresh`）就会漏掉销售 / 采购入口。改成读取时计算后，与安装顺序、
        模块组合都无关，也不再往别的模块的数据里写东西（本模块自己的 3 条静态声明仍保留）。

        依赖模块自带的 card 视图存在（`product_card_view.product_template_card_view`）；
        未加载时（例如注册表早期）直接跳过，不影响原生行为。
        """
        super()._compute_views()
        card_view = self.env.ref(
            "product_card_view.product_template_card_view", raise_if_not_found=False
        )
        if not card_view:
            return
        for action in self.filtered(lambda act: act.res_model == "product.template"):
            # 已经带了 card 的（静态声明那条）也重排到最前，保证「默认打开卡片视图」这一点一致
            others = [(view_id, mode) for view_id, mode in action.views if mode != "card"]
            action.views = [(card_view.id, "card")] + others


class ProductTemplate(models.Model):
    """扩展 product.template，提供卡片视图数据，不新增字段。"""

    _inherit = "product.template"

    def _get_optional_base_reference(self, template, variant_count):
        """模板层编号可用的「产品母型号」；不可用时返回 ``False``。

        母型号来自**可选模块** `product_reference`（不在本模块 `depends` 里），本模块对它的
        全部了解就收在这个方法里，三种情况都返回 ``False`` 并让调用方回退原生 `default_code`：

        - **未装该模块**：字段不存在（卡片编号一栏照常有值，只是少了母型号这一层）；
        - **装了但产品只有一条变体**：单变体产品的编号真身在那条变体上（该模块不在产品侧写
          镜像），产品上的残留值（旧版本产物 / 退回单变体的遗留 / 外部写入）不得盖掉变体编号；
        - 只有**多变体**产品才读它：那时模板级 `default_code` 恒为空，母型号是唯一有值的一层。

        对方改名或改字段时只需改这一处（约束见模块 AGENTS.md → L1 第 5 条）。
        """
        if variant_count <= 1:
            return False
        if "base_reference" not in self.env["product.template"]._fields:
            return False
        return template.base_reference

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
            # 母型号只在多变体产品上代表「产品编号」（可选模块，见 _get_optional_base_reference）
            tpl_base_reference = self._get_optional_base_reference(template, len(tpl_variants))
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
                        # 变体编号 → 产品母型号（多变体产品）→ 产品级 default_code
                        "reference": (
                            variant.default_code or tpl_base_reference or tpl_default_code or ""
                        ),
                        "on_hand": variant_qty.get(variant.id) if has_qty else None,
                        "values": dict(variant_attr_map.get(variant.id, {})),
                    }
                )

            payload[tpl_id] = {
                "name": template.name,
                # 模板层：单变体产品两处同值，多变体产品只有 base_reference 有值
                "reference": tpl_base_reference or tpl_default_code or "",
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
