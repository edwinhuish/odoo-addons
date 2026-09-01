# -*- coding: utf-8 -*-
"""Pre-migration script for sale_order_no 19.0.1.3.0

本版本为 sale_order.order_no 增加了数据库层 UNIQUE 约束。
历史数据中若存在重复编号，添加约束会直接失败，因此在这里先行处理：

1. 把空字符串编号归一化为 NULL（NULL 不参与唯一性判断）。
2. 重复编号保留 id 最小的一条，其余追加 -DUP<n> 后缀，避免升级中断。

被改写的编号会写入 warning 日志，升级后应人工核对并修正。
"""

import logging

_logger = logging.getLogger(__name__)


def _table_exists(cr, table):
    cr.execute("""
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = %s;
    """, (table,))
    return bool(cr.fetchone())


def migrate(cr, version):
    if not _table_exists(cr, 'sale_order'):
        _logger.info("Table sale_order not found, skipping order_no deduplication.")
        return

    # 1. 空字符串归一化为 NULL
    cr.execute("""
        UPDATE sale_order
        SET order_no = NULL
        WHERE order_no IS NOT NULL AND btrim(order_no) = '';
    """)
    if cr.rowcount:
        _logger.info("Normalized %s empty order_no values to NULL.", cr.rowcount)

    # 2. 重复编号降级处理
    cr.execute("""
        SELECT order_no, array_agg(id ORDER BY id)
        FROM sale_order
        WHERE order_no IS NOT NULL
        GROUP BY order_no
        HAVING COUNT(*) > 1;
    """)
    duplicated = cr.fetchall()

    for order_no, order_ids in duplicated:
        _logger.warning(
            "订单编号 %s 被 %s 张单据重复使用（id: %s），保留 id=%s，其余追加 -DUP 后缀。",
            order_no, len(order_ids), order_ids, order_ids[0],
        )
        for index, order_id in enumerate(order_ids[1:], start=1):
            cr.execute(
                "UPDATE sale_order SET order_no = %s WHERE id = %s",
                (f"{order_no}-DUP{index}", order_id),
            )

    _logger.info("sale_order_no pre-migration to 19.0.1.3.0 completed.")
