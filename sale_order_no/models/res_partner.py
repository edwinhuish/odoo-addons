# -*- coding: utf-8 -*-
"""客户编号（联系人内部参考 ref）的格式校验。"""

import re

from odoo import _, api, models
from odoo.exceptions import ValidationError

REF_PATTERN = r"^[A-Z]+$"


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.constrains("ref")
    def _check_ref_format(self):
        """客户编号格式校验：仅允许大写英文字母。

        该编号会作为订单编号的前缀，因此必须保持简短、无歧义。
        为空时不校验（内部联系人、收货地址等通常不需要客户编号）。
        """
        for record in self:
            ref = (record.ref or "").strip()
            if ref and not re.match(REF_PATTERN, ref):
                raise ValidationError(_(
                    "客户编号必须为大写英文字母，例如：DZ、DAZG。\n当前值：%s",
                ) % record.ref)

    @api.model_create_multi
    def create(self, vals_list):
        """创建联系人时自动去除首尾空格并转为大写。"""
        for vals in vals_list:
            if vals.get("ref"):
                vals["ref"] = vals["ref"].strip().upper()
        return super().create(vals_list)

    def write(self, vals):
        """修改联系人时自动去除首尾空格并转为大写。"""
        if vals.get("ref"):
            vals["ref"] = vals["ref"].strip().upper()
        return super().write(vals)
