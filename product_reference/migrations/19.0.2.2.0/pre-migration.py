# -*- coding: utf-8 -*-
"""``19.0.2.2.0`` 前置迁移：清理上一版本遗留的内部参考行。

``19.0.2.1.0`` 曾在 ``product.reference.code`` 中创建 ``is_internal=True`` 的行来镜像
``product.template.default_code``。``19.0.2.2.0`` 改为仅在前端 References 标签页显示
原生的 ``default_code`` 字段，不再在参考号表中存储 Odoo Reference。因此需要在
``is_internal`` 列被 ORM 删除前，把上一版本遗留的内部参考行清理掉，避免保留无效的
``reference_type='internal'`` 数据。
"""

import logging

from odoo.tools import sql

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if sql.column_exists(cr, "product_reference_code", "is_internal"):
        cr.execute("""
            DELETE FROM product_reference_code
            WHERE is_internal = TRUE OR reference_type = 'internal'
        """)
        deleted = cr.rowcount
        _logger.info(
            "removed %s leftover internal reference lines in 19.0.2.2.0 pre-migration",
            deleted,
        )
