# -*- coding: utf-8 -*-
"""清理 ``19.0.2.6.0`` 在单变体产品上留下的母型号镜像值（19.0.2.7.0）。

背景：`19.0.2.6.0` 曾让单变体产品的型号**同时**写进变体的 ``default_code`` 与产品的
``base_reference``（两处同值）。同一份数据写两处，只要有一条写入路径漏掉就会不一致，
因此 `19.0.2.7.0` 改成：单变体产品**只写变体的 ``default_code``**（真身），
``base_reference`` 只在「单变体 → 多变体」时由 `product_variant_conversion`
把编号上移过来（见模块 AGENTS.md L1.3 与 ``README.md`` →「母型号 Base Reference」）。

本脚本清掉旧策略留下的镜像值：**单变体产品**上 ``base_reference`` 恰好等于该变体
``default_code`` 的行一律置空 —— 那正是镜像写法的结果，不是用户独立录入的母型号。

刻意不动的情况：
- **多变体产品**：``base_reference`` 在那里就是真正的产品母型号，必须保留；
- 单变体但 ``base_reference`` 与变体编号**不同**的行（例如「多变体退回单变体」后残留的
  母型号）：无从判断是谁写的，保留比误删安全（下次转换会用变体编号覆盖它）。

设计约束：
- 必须放 **post-migration**：从更早版本（如 `19.0.2.5.3`）直接升上来时，``base_reference``
  是本次才建的列，pre 阶段还没有它；
- **幂等**：清过的行第二次执行条件不再成立；
- **不删数据**：只把一个冗余镜像列置空，真值（变体的 ``default_code``）一个字节不动。
"""

import logging

_logger = logging.getLogger(__name__)

# 只清「单变体 + 母型号与变体编号同值」的行：这就是旧镜像写入的指纹。
CLEANUP_SQL = """
    UPDATE product_template t
       SET base_reference = NULL
      FROM product_product p
     WHERE p.product_tmpl_id = t.id
       AND t.base_reference IS NOT NULL
       AND t.base_reference != ''
       AND t.base_reference = p.default_code
       AND (
           SELECT count(*)
             FROM product_product q
            WHERE q.product_tmpl_id = t.id
       ) = 1
"""


def _column_exists(cr, table, column):
    cr.execute("""
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
    """, (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    """清掉单变体产品上遗留的母型号镜像值。

    :param version: 升级前的模块版本（新装时为 None，此时表里没有存量数据）。
    """
    if not _column_exists(cr, "product_template", "base_reference"):
        _logger.warning(
            "product_template.base_reference does not exist; skipping the base "
            "reference mirror cleanup")
        return

    cr.execute(CLEANUP_SQL)
    if cr.rowcount:
        _logger.info(
            "cleared the mirrored base_reference of %s single-variant product(s); "
            "the model stays on the variant reference until the product gains variants",
            cr.rowcount)
