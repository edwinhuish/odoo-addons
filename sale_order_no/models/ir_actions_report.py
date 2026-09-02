# -*- coding: utf-8 -*-
"""扩展 ir.actions.report，提供强制覆盖 print_report_name 的方法。

print_report_name 是 translate=True 字段，Odoo 19 用 JSONB 按语言存储。
直接 write({'print_report_name': '...'}) 只会写当前上下文 lang 对应的
JSONB key（XML 数据加载默认上下文是 en_US）。本模块提供
_force_order_no_print_name，逐语言切换上下文后写入，确保所有语言
的 print_report_name 都用 order_no 表达式。
"""

from odoo import models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _force_order_no_print_name(self, expression):
        """把给定表达式写入所有启用语言的 print_report_name。

        Odoo 19 的 translate=True 字段 write 方法只接受字符串值，
        会用当前上下文 lang 写入对应 JSONB key。要全语言覆盖，
        必须逐语言切换上下文后 write，每次只写一个 lang。
        """
        self.ensure_one()
        # XML 数据加载默认上下文是 en_US，先写 base 值
        self.with_context(lang='en_US').write({'print_report_name': expression})
        # 逐语言切换上下文写入（en_US 上面已写，这里跳过）
        for lang_code in self.env['res.lang'].search([]).mapped('code'):
            if lang_code == 'en_US':
                continue
            self.with_context(lang=lang_code).write({'print_report_name': expression})
        return True
