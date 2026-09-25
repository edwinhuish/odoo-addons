# -*- coding: utf-8 -*-
"""T-017：把「会丢变体就拒绝」挂到属性主数据与属性行的直接写路径上。

产品表单的归属确认挂在 ``product.template.write()`` 上，但下面几条路**不经过它**，
原生的删取值会让**在用变体**被 ``_unlink_or_archive()`` 删掉或归档（库存与单据跟着消失）：

1. ``product.template.attribute.value.unlink()`` —— 取值记录本体（属性主数据删取值时的级联删除也会走到这）；
2. ``product.attribute.value.unlink()`` —— 属性主数据里删取值，会破坏变体组合；
3. ``product.template.attribute.line.unlink()`` / ``.write()`` —— 直接写属性行：
   line 的 ``write()`` 自己会调 ``product_tmpl_id._create_variant_ids()``。

本模块的转换不受影响：它只**新增**取值 / 新建属性行，从不删取值。
要删取值的正确姿势（也是报错里给的出路）：先归档或删除用到它的变体，再删取值。

一个例外必须放行：**产品表单带着「归属映射」一起保存时**（``variant_conversion_mapping``，
即映射表里每条既有变体都指定了改动后它占哪个组合）。典型是「删掉产品上唯一的属性」：
那条变体由映射继续承载**空组合**，不会被删除也不会被归档 —— 守卫的前提（变体会被连坐）
不成立，再拦就是误伤。``product.template.write()`` 校验过映射之后会带上
``variant_conversion_keeps_variants`` 上下文键落库，本文件据此放行。
"""

from odoo import _, api, models
from odoo.exceptions import UserError

# 「映射已指定每条既有变体的归属组合」→ 删属性行 / 删取值不再连坐变体，守卫放行
KEEP_VARIANTS_KEY = "variant_conversion_keeps_variants"


class ProductTemplateAttributeValue(models.Model):
    _inherit = "product.template.attribute.value"

    def unlink(self):
        """删除取值记录前，确认没有在用变体会被连坐删除或归档。

        ``create_product_product=False`` 时放行：那是本模块「只写配置、不碰变体」的沙盒写入
        （试写分析 / 转换内部写入，在保存点里跑、随即回滚），与 L1 约束 10 同源。
        带 ``variant_conversion_keeps_variants`` 时也放行：映射已指定这些变体继续承载哪个
        组合（例如删掉唯一属性后由它承载空组合），不存在「连坐删除」。
        """
        if (self.env.context.get("create_product_product", True)
                and not self.env.context.get(KEEP_VARIANTS_KEY)):
            blocked = self.ptav_product_variant_ids.filtered("active")
            if blocked:
                sample = self[0]
                raise UserError(_(
                    "The value %(value)s of %(attribute)s is still carried by %(count)s active variants of "
                    "%(product)s, for example %(variant)s. Deleting it would delete or archive those variants "
                    "together with their stock, orders and invoices. Archive or delete those variants first, "
                    "then remove the value.",
                    value=sample.product_attribute_value_id.name,
                    attribute=sample.attribute_id.display_name,
                    count=len(blocked),
                    product=sample.product_tmpl_id.display_name,
                    variant=blocked[0].display_name,
                ))
        return super().unlink()


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    def unlink(self):
        """属性主数据里删取值：正被产品使用的取值不允许删（会破坏变体的属性组合）。"""
        used = self.filtered("is_used_on_products")
        if used:
            products = used.pav_attribute_line_ids.product_tmpl_id
            raise UserError(_(
                "The attribute value %(value)s is used on the products %(products)s. Deleting it would "
                "break those products' variants (they would lose the value from their combination). "
                "Remove it from the products' attribute lines — or archive or delete the variants that "
                "use it — first.",
                value=used[0].display_name,
                products=", ".join(products.mapped("display_name")[:5]),
            ))
        return super().unlink()


class ProductTemplateAttributeLine(models.Model):
    _inherit = "product.template.attribute.line"

    def unlink(self):
        """直接删属性行：带着这些取值的在用变体会失去归属（变体数坍缩），必须先处理变体。

        ``create_product_product=False`` 时放行（沙盒写入，见上面的说明）；
        带 ``variant_conversion_keeps_variants`` 时也放行：用户已在映射表里给每条既有变体
        指定了组合（删掉唯一属性时那条变体继续承载空组合），变体不会被删也不会被归档。
        """
        if (self.env.context.get("create_product_product", True)
                and not self.env.context.get(KEEP_VARIANTS_KEY)):
            blocked = self.env["product.product"]
            for line in self:
                blocked |= line.product_template_value_ids.ptav_product_variant_ids.filtered("active")
            if blocked:
                sample = blocked[0]
                raise UserError(_(
                    "Removing the attribute %(attribute)s from %(product)s would affect %(count)s active "
                    "variants, for example %(variant)s: they carry its values and keep the stock, the orders "
                    "and the invoices. Archive or delete those variants first, then remove the attribute.",
                    attribute=line.attribute_id.display_name,
                    product=line.product_tmpl_id.display_name,
                    count=len(blocked),
                    variant=sample.display_name,
                ))
        return super().unlink()

    def write(self, vals):
        if ("value_ids" in vals and self.env.context.get("create_product_product", True)
                and not self.env.context.get(KEEP_VARIANTS_KEY)):
            self._check_variant_conversion_value_removal(vals["value_ids"])
        return super().write(vals)

    def _check_variant_conversion_value_removal(self, commands):
        """属性行写 ``value_ids`` 时，若会移走在用变体携带的取值就拒绝。

        只识别 ``Command.set`` / ``Command.clear``（产品表单与本模块都生成这两种）；
        其余命令类型不在此拦 —— 删记录走 ``unlink()`` 的守卫。
        """
        pending = None
        for command in commands or []:
            if not isinstance(command, (list, tuple)) or len(command) < 2:
                continue
            if command[0] == 6:                       # Command.set
                pending = set(command[2] or [])
            elif command[0] == 5:                     # Command.clear
                pending = set()
            elif command[0] in (0, 1, 2, 3, 4):       # 其余：新建 / 关联 / 移除，交给 unlink 守卫
                return
        if pending is None:
            return

        value_model = self.env["product.attribute.value"]
        for line in self:
            lost = line.value_ids.filtered(
                lambda value: value.id not in pending)
            if not lost:
                continue
            variants = line.product_template_value_ids.filtered(
                lambda ptav: ptav.product_attribute_value_id in lost
            ).ptav_product_variant_ids.filtered("active")
            if variants:
                raise UserError(_(
                    "Removing the value %(value)s of %(attribute)s from %(product)s would affect "
                    "%(count)s active variants: they carry it and keep the stock, the orders and the "
                    "invoices. Archive or delete those variants first, then remove the value.",
                    value=lost[0].name,
                    attribute=line.attribute_id.display_name,
                    product=line.product_tmpl_id.display_name,
                    count=len(variants),
                ))
