# -*- coding: utf-8 -*-
"""「属性 ↔ 变体」映射：产品表单「属性与变体」页下方的那张映射表。

为什么要有它
------------

Odoo 原生在改属性时会把既有变体删掉重建（库存与单据跟着遭殃），本模块接管了这条
写入路（见 ``models/product_template.py``）。接管之后必须回答一个问题：**每条既有
变体在这次改动之后带哪个组合**。本文件把这个问题显式化：

- ``_get_variant_mapping_rows()``：给每条既有变体算一行 —— 它带的组合、每个属性轴
  上有哪些取值可选、缺哪个轴的取值。纯读，不写库；
- ``get_variant_mapping_preview()``：产品表单在**保存之前**以及**属性行一改**时就调
  它，把「这次改动之后」的映射状态算出来。它复用 ``_analyze_variant_conversion_write()``
  的「只写配置、不碰变体」试写（写完即回滚），所以既有变体毫发无损；
- ``variant_mapping_state``：非存储计算字段，表单打开时就把当前（已保存的）映射交给
  前端，省掉一次 RPC。

「未映射」的判据
----------------

某个属性轴有多个取值、且这条变体在该轴上没有取值（既不是它自己带着的、也不是用户
刚选的）→ 这条变体**未映射**，保存会被拦住（见 ``write()`` 与前端保存钩子）。

两类轴不需要用户选，因此永远不算未映射：

- **单取值轴**：Odoo 会把那唯一的取值自动写到所有变体上（``_create_variant_ids()``
  的 ``single_value_lines`` 分支），加了它不会重建变体；
- **「按需生成」轴**（``create_variant == 'dynamic'``）：变体由 Odoo 按订单创建，
  转换只把每条变体现带的取值钉住（没有就取第一个），见 ``T-039``。
"""

import json

from odoo import _, api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # ------------------------------------------------------------------
    # 字段：给产品表单的映射表用的初始状态（非存储，随算随用）
    # ------------------------------------------------------------------

    variant_mapping_state = fields.Text(
        string="Attribute / Variant Mapping",
        compute="_compute_variant_mapping_state",
        help="Technical field that feeds the mapping table shown under the attribute lines of the "
             "product form: one row per existing variant, with the combination it carries. It is "
             "computed on the fly and never stored.",
    )

    @api.depends("attribute_line_ids", "attribute_line_ids.value_ids")
    def _compute_variant_mapping_state(self):
        for tmpl in self:
            tmpl.variant_mapping_state = json.dumps(
                tmpl._get_variant_mapping_payload(tmpl._get_variant_conversion_specification())
            )

    # ------------------------------------------------------------------
    # 入口：产品表单要的「映射状态」
    # ------------------------------------------------------------------

    def get_variant_mapping_preview(self, attribute_line_ids=None, selection=None):
        """把「这次属性改动之后每条变体带哪个组合」告诉产品表单。

        由表单里的映射表（保存之前、以及属性行一改）调用。

        :param list attribute_line_ids: 本次要写入 ``attribute_line_ids`` 的命令；
            为空表示「按当前已保存的配置算」，用于表单刚打开时。
        :param dict selection: 用户在映射表里已经选好的取值，
            形如 ``{变体 id: {属性 id: 取值 id}}``（JSON 的键是字符串）。
        :return: dict：
            ``blocked`` 非空字符串表示这次改动会丢既有变体，改不了也没法映射；
            ``rows`` 每条既有变体一行（见 ``_get_variant_mapping_rows()``）；
            ``unmapped_count`` 还没有组合的变体数（大于 0 就不许保存）；
            ``new_combinations`` 本次会新建出来的组合（纯展示）；
            ``dynamic`` / ``required`` 沿用 ``get_variant_conversion_preview()`` 的口径。
        """
        self.ensure_one()
        commands = attribute_line_ids or []
        # 「会不会丢变体」的结论与文案完全沿用现有预览，避免两处判断分叉
        preview = self.get_variant_conversion_preview(commands)
        if preview.get("blocked"):
            return {
                "blocked": preview["blocked"],
                "required": False,
                "dynamic": False,
                "rows": [],
                "unmapped_count": 0,
                "new_combinations": [],
            }
        affected = self._analyze_variant_conversion_write(commands)
        payload = self._get_variant_mapping_payload(
            affected["specification"], selection, affected)
        payload["required"] = preview.get("required", False)
        return payload

    def _get_variant_mapping_payload(self, specification, selection=None, affected=None):
        """把「变体 → 组合」的映射打包成前端要的结构。"""
        self.ensure_one()
        rows = self._get_variant_mapping_rows(specification, selection)
        # 「按需生成」的属性要按**目标配置**（试写时的快照）判断：试写回滚后读产品
        # 拿到的是改动前的属性行，会漏掉本次新加的按需属性
        dynamic = (affected or {}).get("dynamic_attributes")
        if dynamic is None:
            dynamic = self._get_variant_conversion_dynamic_attributes()
        return {
            "blocked": False,
            "dynamic": bool(dynamic),
            "rows": rows,
            "unmapped_count": sum(1 for row in rows if not row["mapped"]),
            # 本次会新建的组合：默认归属没被任何既有变体占住的那几个
            "new_combinations": [
                combination["label"] for combination in (affected or {}).get("combinations", [])
                if not combination["origin_variant_id"]
            ],
        }

    def _get_variant_mapping_rows(self, specification, selection=None):
        """给每条既有变体算一行「它带哪个组合」（纯读，不写库）。

        :param list specification: ``_get_variant_conversion_specification()`` 的结果
            （每个属性一项：属性 + 有效取值）。可以是**当前配置**，也可以是试写出来的
            **目标配置** —— 两者都只引用真实记录，试写回滚后照样可用。
        :param dict selection: 用户已选的取值 ``{变体 id: {属性 id: 取值 id}}``。
        :return: list of dict，每项：
            ``variant_id`` / ``label`` / ``on_hand``（没装 stock 时为 None）；
            ``axes`` 每个属性轴一项（``attribute_id`` / ``attribute_label`` /
            ``value_id`` / ``options`` / ``fixed`` 是否由 Odoo 自己补）；
            ``mapped`` 该变体是否每个轴都有取值。
        """
        self.ensure_one()
        selection = selection or {}
        quantities = self._get_variant_conversion_on_hand_quantities()
        pav_model = self.env["product.attribute.value"]
        rows = []
        for variant in self.product_variant_ids:
            # JSON 的键一律是字符串，这里两种都认（服务端调用方可能直接传 int）
            variant_selection = selection.get(str(variant.id), selection.get(variant.id)) or {}
            carried = variant.product_template_attribute_value_ids.product_attribute_value_id
            axes = []
            mapped = True
            for spec in specification:
                attribute = spec["attribute"]
                values = spec["values"]
                selected_id = variant_selection.get(
                    str(attribute.id), variant_selection.get(attribute.id))
                value = pav_model.browse(int(selected_id)) & values if selected_id else pav_model
                if not value:
                    value = carried.filtered(
                        lambda pav: pav.attribute_id == attribute and pav in values)[:1]
                # 单取值轴与「按需生成」轴由 Odoo 自己补上取值，不需要用户选
                fixed = len(values) == 1 or attribute.create_variant == "dynamic"
                if not value and fixed:
                    value = values[:1]
                if not value:
                    mapped = False
                axes.append({
                    "attribute_id": attribute.id,
                    "attribute_label": attribute.display_name,
                    "value_id": value.id if value else False,
                    "options": [{"id": pav.id, "name": pav.name} for pav in values],
                    "fixed": fixed,
                })
            rows.append({
                "variant_id": variant.id,
                "label": variant.display_name,
                "on_hand": quantities.get(variant.id),
                "axes": axes,
                "mapped": mapped,
            })
        return rows

    # ------------------------------------------------------------------
    # 保存兜底：还有变体没有组合时的报错文案（前端映射表也用同一段提示）
    # ------------------------------------------------------------------

    def _get_variant_mapping_blocked_message(self):
        """还有变体没映射到任何组合时的提示（保存被拦住时给用户看）。"""
        return _(
            "Some variants of %(product)s have no combination after this attribute change: pick the "
            "combination each of them keeps in the mapping table below the attribute lines, then "
            "save again.",
            product=self.display_name,
        )
