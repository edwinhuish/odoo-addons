# -*- coding: utf-8 -*-
"""让存量数据满足新的产品编号契约（19.0.3.0.0）。

`19.0.3.0.0` 起，模板级 `default_code` 的 compute 改成「`base_reference` 优先」，
inverse 改成「单变体产品两处同值、多变体产品只写 `base_reference`」。因此存量数据要补齐两件事：

1. **单变体产品**：``base_reference`` 与该变体的 ``default_code`` 同值（产品表单写编号时
   两处一起写，这就是既成结果，不是猜测）；
2. **多变体产品**：``base_reference`` 有值时把存量 ``default_code`` 列对齐它 —— 升级前那列是
   原生桥接算出来的（多变体时为空），本身不会自动重算，不对齐就会出现
   「库里存着空、界面上按 compute 又能显示」的不一致（列表搜索走的是**存储列**）。

刻意不动的情况：
- 多变体产品的 ``base_reference`` 为空：没有可回填的来源，保持空、由人工在产品表单补录
  （缺它只影响「产品编号」这一栏，不影响其它功能）。

设计约束：
- 必须放 **post-migration**：从更早版本升上来时 ``base_reference`` 是本次才建的列，
  pre 阶段还没有它；
- **幂等**：两条 UPDATE 的条件在第二次执行时都不再成立；
- **不删数据**：只补 `base_reference` 与模板级 `default_code` 两个编号列，变体编号一个字节不动。
"""

import logging

_logger = logging.getLogger(__name__)

# ① 单变体产品：产品级编号 = 那条变体的编号
BACKFILL_SINGLE_VARIANT_SQL = """
    UPDATE product_template t
       SET base_reference = p.default_code
      FROM product_product p
     WHERE p.product_tmpl_id = t.id
       AND p.default_code IS NOT NULL
       AND p.default_code != ''
       AND (t.base_reference IS NULL OR t.base_reference = '')
       AND (
           SELECT count(*)
             FROM product_product q
            WHERE q.product_tmpl_id = t.id
       ) = 1
"""

# ② 产品级编号已有时，把存储列对齐（原生的多变体桥接算不出它）
ALIGN_DEFAULT_CODE_SQL = """
    UPDATE product_template t
       SET default_code = t.base_reference
     WHERE t.base_reference IS NOT NULL
       AND t.base_reference != ''
       AND (t.default_code IS NULL OR t.default_code != t.base_reference)
"""


def _column_exists(cr, table, column):
    cr.execute("""
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
    """, (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    """补齐产品级编号并让存储列与 compute 契约一致。

    :param version: 升级前的模块版本（新装时为 None，此时表里没有存量数据）。
    """
    if not _column_exists(cr, "product_template", "base_reference"):
        _logger.warning(
            "product_template.base_reference does not exist; skipping the product "
            "reference backfill")
        return

    cr.execute(BACKFILL_SINGLE_VARIANT_SQL)
    if cr.rowcount:
        _logger.info(
            "backfilled base_reference for %s single-variant product(s)", cr.rowcount)

    cr.execute(ALIGN_DEFAULT_CODE_SQL)
    if cr.rowcount:
        _logger.info(
            "aligned the stored default_code of %s product(s) with their base reference",
            cr.rowcount)
