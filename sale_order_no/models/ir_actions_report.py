# -*- coding: utf-8 -*-
"""扩展 ir.actions.report，提供强制覆盖 print_report_name 的方法。

print_report_name 是 translate=True 字段，Odoo 19 用 JSONB 按语言存储。
直接 write({'print_report_name': '...'}) 只会写当前 lang 对应的 key，
其他语言（如 zh_CN）仍是旧表达式。本模块提供 _force_order_no_print_name，
在所有启用语言上写入相同表达式，确保任意语言下 PDF 文件名都用 order_no。
"""

from odoo import models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _force_order_no_print_name(self, expression):
        """把给定表达式写入所有启用语言的 print_report_name 翻译值。

        用 write({...: expression}) 形式写入，绕过 Odoo 默认只写当前 lang 的行为。
        XML 数据加载默认上下文是 en_US，直接 write 会留下其他语言旧值，
        必须显式按语言全覆盖。
        """
        self.ensure_one()
        # 构造 {lang_code: value} 形式的 dict，Odoo 19 的 translate 字段
        # 在收到这种 dict 时会写入对应 lang 的 JSONB key
        langs = self.env['res.lang'].search([]).mapped('code')
        if not langs:
            langs = ['en_US']
        # write 接受 {field: {lang: value}} 形式的多语言 dict
        self.with_context(lang=None).write({
            'print_report_name': {lang: expression for lang in langs},
        })
        return True
