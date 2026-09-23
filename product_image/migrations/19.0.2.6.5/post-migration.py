# -*- coding: utf-8 -*-
"""升级到 19.0.2.6.5：把产品列表「Images」列的 zh_CN 译文刷成「图片」。

列标题的**英文源文本没有变**（仍是 `Images`），只是这一列的语义从「图库图片数量」改成了
「产品主图」，译文要跟着从「图片数」改成「图片」。而 po 导入只补齐缺失语种、**不覆盖库里已有的
译文** —— 所以单靠 `-u` 不会改掉旧值（同根 `AGENTS.md` 4.7 / 4.8 第 9 条；也可用
`task i18n -- zh_CN product_image` 强制刷新）。这里对该视图 `arch_db` 的术语做一次定向刷新，
让「只升级模块」也能得到正确的中文列标题。

幂等：术语不存在或译文已是目标值时都不会有副作用；未安装 zh_CN 的库直接跳过。
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        # 全新安装：po 在安装时导入，术语本来就是新译文，无需处理
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    installed_langs = {code for code, _name in env["res.lang"].get_installed()}
    if "zh_CN" not in installed_langs:
        return
    view = env.ref("product_image.product_template_list_inherit", raise_if_not_found=False)
    if not view:
        # 视图记录是 noupdate 之外的数据，正常存在；缺失说明库状态异常，不做处理
        return
    # `arch_db` 是 xml_translate（field.translate 为 callable）→ 译文按「源术语: 译文」给
    view.update_field_translations("arch_db", {"zh_CN": {"Images": "图片"}})
