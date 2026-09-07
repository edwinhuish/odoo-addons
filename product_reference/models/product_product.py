# -*- coding: utf-8 -*-
"""扩展 product.product，保持 default_code 与内部参考行同步。

Odoo 的 ``product.template.default_code`` 是计算/存储/反写字段，最终落在
``product.product.default_code`` 上。用户除了在 General Information 修改 Reference，
也可能在「变体」相关界面直接编辑变体的 default_code；这里做一个薄层钩子，
让这种修改也能同步到 ``product.reference.code`` 的内部参考行。
"""

from odoo import models


class ProductProduct(models.Model):
    _inherit = "product.product"

    def write(self, vals):
        res = super().write(vals)
        if "default_code" in vals:
            # 一个变体写 default_code 时，模板侧的 default_code 会重新计算；
            # 调用 _sync_internal_reference_line 让内部参考行与最新值保持一致。
            self.product_tmpl_id._sync_internal_reference_line()
        return res
