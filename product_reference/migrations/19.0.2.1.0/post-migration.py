# -*- coding: utf-8 -*-
"""``19.0.2.1.0`` 后置迁移：为已有 default_code 的产品补建内部参考号行。

本模块 ``19.0.2.1.0`` 新增 ``product.reference.code.is_internal`` 字段，并把
``product.template.default_code``（General Information 的 Reference）镜像为
参考号页的第一行。对历史数据，升级后需要一次性为已填写 default_code 的产品
生成对应的内部参考行。
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # 包含 archived 产品，避免遗漏；_sync_internal_reference_line 自己会按 default_code 过滤
    templates = env["product.template"].with_context(active_test=False).search([
        ("default_code", "!=", False),
    ])
    _logger.info(
        "backfilling internal reference lines for %s products with default_code",
        len(templates),
    )
    if templates:
        templates._sync_internal_reference_line()
