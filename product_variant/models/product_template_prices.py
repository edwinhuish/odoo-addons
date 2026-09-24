# -*- coding: utf-8 -*-
"""价格数据（供应商价格 / 价格表规则）按变体分离的实现（T-022 / T-018）。

从 ``product_template.py`` 拆出来：价格归属逻辑自成一块，避免那个文件过长。
这些方法与 ``product_template.py`` 的 ``_convert_to_multi_variant()`` 属于同一个模型
（同为 ``_inherit = "product.template"``），拆文件只整理代码、不改变行为。
"""

from odoo import _, api, models
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = "product.template"



    def _get_variant_conversion_separate_variant_prices(self):
        """是否把价格数据（供应商价格 / 价格表规则）按变体分离，默认开启。

        系统参数 ``product_variant.separate_variant_prices``。

        关闭时模板级的价格记录保持模板级（对所有变体生效）—— **改一条会影响全部变体**，
        这正是默认开启的原因：变体的价格要能各自独立地改。
        """
        return self._get_variant_conversion_bool_parameter("separate_variant_prices")


    def _share_vendor_prices_with_variants(self, originals):
        """把「仅适用于既有变体」的供应商价格改为「适用于本产品的全部变体」。

        ``product.supplierinfo.product_id`` 为空即对模板下所有变体生效（Odoo 原生语义），
        否则转换后只有部分变体有供应商价格，其余新变体采购时找不到价格。
        共享后所有变体取到的是**同一批价格数值**（同一供应商 / 最小数量 / 有效期）。

        **只动「product_id 指向既有变体」的记录**：本身就已经是模板级（对所有变体生效）的记录
        不动 —— 已属于全部变体就不需要转移；指向其它产品的记录也不动。
        返回本次改写过的记录集，便于调用方 / 测试核对到底动了哪些。
        """
        self.ensure_one()
        vendor_prices = self.env["product.supplierinfo"].search([
            ("product_id", "in", originals.ids),
        ])
        if vendor_prices:
            vendor_prices.write({"product_id": False})
        return vendor_prices

    # ------------------------------------------------------------------
    # 辅助：价格数据按变体分离（供应商价格 / 价格表规则）
    #
    # 为什么默认分离：模板级的价格记录是「一条记录被所有变体共用」，改一次就影响全部变体，
    # 与「变体的价格要各自独立」冲突。分离 = 每条变体各持一份自己的记录（数值不变、归属独立）。
    # ------------------------------------------------------------------

    @api.model
    def _variant_conversion_vendor_price_key(self, info):
        """供应商价格「是同一条」的判据：同一供应商 + 同一最小数量 + 同一价格。"""
        return (info.partner_id.id, info.min_qty, info.price)

    @api.model
    def _variant_conversion_pricelist_tier_key(self, item):
        """价格表规则「占住的位置」：同一价格表的同一数量门槛。

        变体自己已有的规则优先：拆模板级规则时，若该变体在这个位置上已有规则就不再复制过去，
        否则会凭空多出一条同档规则、把原来生效的那条挤掉 —— 等于静默改价。
        """
        return (item.pricelist_id.id, item.min_quantity)

    def _variant_conversion_vendor_price_signature(self, variants):
        """每条变体当前可用的供应商价格集合，用于「分离只改归属、不改数值」的守恒断言。

        元素是 ``(供应商 id, 最小数量, 价格)``；模板级（对本产品全部变体生效）的记录会算给每条变体，
        按变体的记录只算它自己那条。
        """
        self.ensure_one()
        suppliers = self.env["product.supplierinfo"]
        template_suppliers = suppliers.search([
            ("product_tmpl_id", "=", self.id), ("product_id", "=", False)])
        signature = {}
        for variant in variants:
            rows = template_suppliers | suppliers.search([("product_id", "=", variant.id)])
            signature[variant] = frozenset(
                (info.partner_id.id, info.min_qty, info.price) for info in rows)
        return signature

    def _variant_conversion_pricelist_prices(self, variants):
        """每条变体在各价格表 / 各数量门槛上**实际取到的售价**，用于价格表侧的守恒断言。

        比「规则集合相等」更贴近事实：拆分规则时真正要保证的是「卖价没变」。
        """
        self.ensure_one()
        rules = self.env["product.pricelist.item"].search([
            ("applied_on", "in", ("1_product", "0_product_variant")),
            "|", ("product_tmpl_id", "=", self.id), ("product_id", "in", variants.ids),
        ])
        quantities = sorted({item.min_quantity for item in rules} | {1.0})
        prices = {}
        for variant in variants:
            per_pricelist = {}
            for pricelist in rules.pricelist_id:
                per_pricelist[pricelist.id] = {
                    quantity: pricelist._get_product_price(variant, quantity)
                    for quantity in quantities
                }
            prices[variant] = per_pricelist
        return prices

    def _duplicate_vendor_prices(self, rows, variant):
        """把 ``rows`` 复制成「属于 variant」的供应商价格，跳过 variant 已有的同款。"""
        existing = {
            self._variant_conversion_vendor_price_key(info)
            for info in self.env["product.supplierinfo"].search([("product_id", "=", variant.id)])
        }
        for info in rows:
            key = self._variant_conversion_vendor_price_key(info)
            if key in existing:
                continue
            info.copy({"product_id": variant.id})
            existing.add(key)

    def _duplicate_pricelist_items(self, rows, variant):
        """把 ``rows`` 复制成「属于 variant」的价格表规则；该变体已占住同一价格表同一门槛就跳过。"""
        existing = {
            self._variant_conversion_pricelist_tier_key(item)
            for item in self.env["product.pricelist.item"].search([
                ("applied_on", "=", "0_product_variant"), ("product_id", "=", variant.id)])
        }
        for item in rows:
            key = self._variant_conversion_pricelist_tier_key(item)
            if key in existing:
                continue
            item.copy({
                "applied_on": "0_product_variant",
                "product_id": variant.id,
                "product_tmpl_id": False,
            })
            existing.add(key)

    def _separate_vendor_prices(self, originals, new_variants):
        """供应商价格：新变体先继承谱系来源的按变体记录，再把模板级记录拆到各变体后删除。"""
        self.ensure_one()
        suppliers = self.env["product.supplierinfo"]
        for variant in new_variants:
            origin = variant.variant_origin_id
            if origin and origin != variant:
                self._duplicate_vendor_prices(
                    suppliers.search([("product_id", "=", origin.id)]), variant)
        template_level = suppliers.search([
            ("product_tmpl_id", "=", self.id), ("product_id", "=", False)])
        for variant in originals | new_variants:
            self._duplicate_vendor_prices(template_level, variant)
        if template_level:
            template_level.unlink()

    def _separate_pricelist_rules(self, originals, new_variants):
        """价格表规则：新变体先继承谱系来源的按变体规则，再把本产品模板级规则拆到各变体后删除。

        只处理 ``applied_on = '1_product'``（本产品）与 ``'0_product_variant'``（本变体）：
        ``3_global``（所有产品）与 ``2_product_category``（按分类）的规则不属于本产品，绝不触碰。
        """
        self.ensure_one()
        rules = self.env["product.pricelist.item"]
        for variant in new_variants:
            origin = variant.variant_origin_id
            if origin and origin != variant:
                self._duplicate_pricelist_items(
                    rules.search([
                        ("applied_on", "=", "0_product_variant"), ("product_id", "=", origin.id)]),
                    variant)
        template_rules = rules.search([
            ("applied_on", "=", "1_product"), ("product_tmpl_id", "=", self.id)])
        for variant in originals | new_variants:
            self._duplicate_pricelist_items(template_rules, variant)
        if template_rules:
            template_rules.unlink()

    def _separate_variant_prices(self, originals, new_variants, share_vendor_prices):
        """让每条变体持有自己的价格数据，做到「改一个变体的价格不影响别的变体」。

        供应商价格：默认**分离**（模板级的拆到各变体、新变体从谱系来源补齐）；
        勾了「应用到全部变体」时改为**共享**（既有变体的记录提升为模板级，所有变体同一批数值）。
        价格表规则：始终按变体分离（与这个勾选框无关）。

        分离只改「归属」不改「数值」：由 ``_check_variant_price_separation()`` 后置断言兜住，
        不符即整单回滚。
        """
        self.ensure_one()
        variants = originals | new_variants
        before_vendor = self._variant_conversion_vendor_price_signature(variants)
        before_prices = self._variant_conversion_pricelist_prices(variants)

        if share_vendor_prices:
            self._share_vendor_prices_with_variants(originals)
        else:
            self._separate_vendor_prices(originals, new_variants)
        self._separate_pricelist_rules(originals, new_variants)

        self._check_variant_price_separation(before_vendor, before_prices, variants, originals)

    def _check_variant_price_separation(self, before_vendor, before_prices, variants, originals):
        """后置断言：谁的价格都没少、原有变体的售价一分未变、新变体的售价与其来源一致。

        供应商价格允许变多（勾选共享时，所有变体都会拿到原来只挂在某条变体上的价格），
        但不允许变少；价格表侧则连售价都必须严格不变（拆规则最怕悄悄改价）。
        """
        self.ensure_one()
        after_vendor = self._variant_conversion_vendor_price_signature(variants)
        after_prices = self._variant_conversion_pricelist_prices(variants)
        for variant in variants:
            if not before_vendor[variant] <= after_vendor[variant]:
                raise UserError(_(
                    "Spreading the price data of %(product)s over its variants would lose vendor prices on %(variant)s; nothing has been changed.",
                    product=self.display_name,
                    variant=variant.display_name,
                ))
            if variant in originals:
                if before_prices[variant] != after_prices[variant]:
                    raise UserError(_(
                        "Spreading the price data of %(product)s over its variants would change the prices available on %(variant)s; nothing has been changed.",
                        product=self.display_name,
                        variant=variant.display_name,
                    ))
                continue
            origin = variant.variant_origin_id
            if origin and origin in variants and after_prices[variant] != after_prices[origin]:
                raise UserError(_(
                    "The new variant %(variant)s of %(product)s would not be priced like the variant it derives from; nothing has been changed.",
                    product=self.display_name,
                    variant=variant.display_name,
                ))
