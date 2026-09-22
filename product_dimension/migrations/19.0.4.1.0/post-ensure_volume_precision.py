# -*- coding: utf-8 -*-
"""升级到 19.0.4.1.0：确保「Volume」小数精度够用。

老库是**升级**进来的，`post_init_hook` 不会跑，所以这里补一次（同一份逻辑，只升不降）。
"""

from odoo import SUPERUSER_ID, api

from odoo.addons.product_dimension.hooks import ensure_volume_precision


def migrate(cr, version):
    if not version:
        return
    ensure_volume_precision(api.Environment(cr, SUPERUSER_ID, {}))
