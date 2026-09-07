# -*- coding: utf-8 -*-
"""``product_model`` → ``product_reference`` 改名迁移（19.0.2.0.0）。

覆盖范围（结构变更，按 AGENTS.md 必须配套迁移脚本）：

1. 模块自身：`ir_module_module` / `ir_model_data` 的模块名与 xmlid 前缀
2. 模型：`product.model.code` → `product.reference.code`
   （数据表、序列、索引、唯一约束、`ir_model` 等元数据）
3. 字段：`model_code` / `model_type` / `model_code_index`
   → `reference_code` / `reference_type` / `reference_code_index`
4. 引用：`ir_ui_view.model`、`ir_act_window.res_model`、`ir_model_data.model`、
   `ir_model_fields.model`、`ir_model_constraint` 等

设计约束：
- **幂等**：任何一步都可重复执行，已改名则跳过（生产库可能分多次升级）。
- **不依赖 ORM**：pre-migration 在模型加载前执行，只能裸 SQL。
- **不删数据**：只改名，不做任何 DELETE；旧译文由升级时重新导入的 .po 覆盖。

运维前置步骤（只做一次，见 README「从 product_model 升级」）：若目标库已安装
`product_model`，先把模块行改名，Odoo 才会把本次升级当成升级而非新装：

```sql
UPDATE ir_module_module SET name = 'product_reference' WHERE name = 'product_model';
UPDATE ir_model_data SET module = 'product_reference' WHERE module = 'product_model';
UPDATE ir_model_data SET name = 'module_product_reference'
 WHERE module = 'base' AND name = 'module_product_model';
```

本脚本对上述三步也会自行兜底（缺哪步补哪步），因此即便前置步骤漏做，
在「安装 product_reference」场景下也能把旧数据接上。
"""

import logging

_logger = logging.getLogger(__name__)

OLD_MODULE = "product_model"
NEW_MODULE = "product_reference"

OLD_MODEL = "product.model.code"
NEW_MODEL = "product.reference.code"

OLD_TABLE = "product_model_code"
NEW_TABLE = "product_reference_code"

# 字段改名：{表名: [(旧列名, 新列名), ...]}；两张表都列，保证中断后重跑也能完成
COLUMN_RENAMES = {
    OLD_TABLE: [("model_code", "reference_code"), ("model_type", "reference_type")],
    NEW_TABLE: [("model_code", "reference_code"), ("model_type", "reference_type")],
    "product_template": [("model_code_index", "reference_code_index")],
}

# 数据库对象改名（索引 / 唯一约束）：旧名 → 新名
# 索引名规则见 odoo.tools.sql.make_index_name：{表名}__{列名}_index
# 约束名规则见 odoo.orm.table_objects.TableObject.full_name：{表名}_{属性名}
INDEX_RENAMES = [
    ("product_model_code__model_code_index",
     "product_reference_code__reference_code_index"),
    ("product_model_code__model_type_index",
     "product_reference_code__reference_type_index"),
    ("product_model_code__product_tmpl_id_index",
     "product_reference_code__product_tmpl_id_index"),
    ("product_template__model_code_index_index",
     "product_template__reference_code_index_index"),
]
CONSTRAINT_RENAMES = [
    # 表名用 NEW_TABLE：改名脚本先改表名，再改约束名
    (NEW_TABLE,
     "product_model_code_model_code_unique_per_template",
     "product_reference_code_reference_code_unique_per_template"),
]

# xmlid 本地名改名规则（按顺序替换，与代码里的新命名一一对应）
XMLID_REPLACEMENTS = [
    ("product_model_code", "product_reference_code"),
    ("model_code", "reference_code"),
]


def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s)", (table,))
    return bool(cr.fetchone()[0])


def _column_exists(cr, table, column):
    cr.execute("""
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
    """, (table, column))
    return bool(cr.fetchone())


def _object_exists(cr, name):
    cr.execute("SELECT to_regclass(%s)", (name,))
    return bool(cr.fetchone()[0])


def _rename_module(cr):
    """模块改名兜底：把库中的旧模块名 / xmlid 前缀切到新名（幂等）。"""
    # 1. 模块行：仅在新名不存在时改名，避免误伤并存的两个模块
    cr.execute("SELECT id FROM ir_module_module WHERE name = %s", (NEW_MODULE,))
    if not cr.fetchone():
        cr.execute(
            "UPDATE ir_module_module SET name = %s WHERE name = %s",
            (NEW_MODULE, OLD_MODULE),
        )
        if cr.rowcount:
            _logger.info("renamed module %s -> %s", OLD_MODULE, NEW_MODULE)
    else:
        # 说明升级前没跑改名 SQL，Odoo 把本模块当新装：旧模块行会变成孤儿，需要手工清理
        cr.execute("SELECT state FROM ir_module_module WHERE name = %s",
                   (OLD_MODULE,))
        if cr.fetchone():
            _logger.warning(
                "module %s still exists in database; delete its row manually "
                "after the upgrade: DELETE FROM ir_module_module WHERE name = %s;",
                OLD_MODULE, OLD_MODULE,
            )

    # 2. 模块记录的 xmlid（base.module_xxx）
    cr.execute("""
        UPDATE ir_model_data
           SET name = %s
         WHERE module = 'base'
           AND name = %s
           AND NOT EXISTS (
               SELECT 1 FROM ir_model_data d
                WHERE d.module = 'base' AND d.name = %s
           )
    """, ("module_" + NEW_MODULE, "module_" + OLD_MODULE, "module_" + NEW_MODULE))

    # 3. 该模块所有外部 ID 的 module 列（撞名则跳过，由后续 xmlid 改名兜底）
    cr.execute("""
        UPDATE ir_model_data
           SET module = %s
         WHERE module = %s
           AND NOT EXISTS (
               SELECT 1 FROM ir_model_data d
                WHERE d.module = %s AND d.name = ir_model_data.name
           )
    """, (NEW_MODULE, OLD_MODULE, NEW_MODULE))
    if cr.rowcount:
        _logger.info("renamed %s ir_model_data rows to module %s",
                     cr.rowcount, NEW_MODULE)


def _rename_xmlid_names(cr):
    """xmlid 本地名按规则改名（model_xxx / field_xxx / 视图 / 动作 / 权限）。"""
    for old, new in XMLID_REPLACEMENTS:
        cr.execute("""
            UPDATE ir_model_data
               SET name = REPLACE(name, %s, %s)
             WHERE module = %s
               AND name LIKE %s
               AND NOT EXISTS (
                   SELECT 1 FROM ir_model_data d
                    WHERE d.module = ir_model_data.module
                      AND d.name = REPLACE(ir_model_data.name, %s, %s)
               )
        """, (old, new, NEW_MODULE, f"%{old}%", old, new))
        if cr.rowcount:
            _logger.info("renamed %s xmlid(s): %s -> %s", cr.rowcount, old, new)


def _rename_tables_and_columns(cr):
    """表 / 列 / 序列 / 索引 / 唯一约束改名（幂等）。"""
    if _table_exists(cr, OLD_TABLE) and not _table_exists(cr, NEW_TABLE):
        cr.execute(f'ALTER TABLE "{OLD_TABLE}" RENAME TO "{NEW_TABLE}"')
        _logger.info("renamed table %s -> %s", OLD_TABLE, NEW_TABLE)
        if _object_exists(cr, f"{OLD_TABLE}_id_seq") and not _object_exists(
                cr, f"{NEW_TABLE}_id_seq"):
            cr.execute(
                f'ALTER SEQUENCE "{OLD_TABLE}_id_seq" '
                f'RENAME TO "{NEW_TABLE}_id_seq"'
            )

    for table, renames in COLUMN_RENAMES.items():
        if not _table_exists(cr, table):
            continue
        for old, new in renames:
            if _column_exists(cr, table, old) and not _column_exists(cr, table, new):
                cr.execute(
                    f'ALTER TABLE "{table}" RENAME COLUMN "{old}" TO "{new}"'
                )
                _logger.info("renamed column %s.%s -> %s", table, old, new)

    for old, new in INDEX_RENAMES:
        if _object_exists(cr, old) and not _object_exists(cr, new):
            cr.execute(f'ALTER INDEX "{old}" RENAME TO "{new}"')
            _logger.info("renamed index %s -> %s", old, new)

    for table, old, new in CONSTRAINT_RENAMES:
        if not _table_exists(cr, table):
            continue
        if _constraint_exists(cr, table, old):
            try:
                with cr.savepoint(flush=False):
                    cr.execute(
                        f'ALTER TABLE "{table}" RENAME CONSTRAINT "{old}" TO "{new}"'
                    )
                    _logger.info("renamed constraint %s -> %s", old, new)
            except Exception:  # noqa: BLE001 - 约束已不存在或不可改名时忽略
                _logger.warning("could not rename constraint %s", old)


def _constraint_exists(cr, table, name):
    cr.execute("""
        SELECT 1
          FROM pg_constraint
         WHERE conrelid = to_regclass(%s) AND conname = %s
    """, (table, name))
    return bool(cr.fetchone())


def _rename_metadata(cr):
    """ir_* 元数据里的模型名 / 字段改名。"""
    # 模型名（新名已存在时跳过，避免撞唯一约束）
    cr.execute("""
        UPDATE ir_model
           SET model = %s
         WHERE model = %s
           AND NOT EXISTS (SELECT 1 FROM ir_model m WHERE m.model = %s)
    """, (NEW_MODEL, OLD_MODEL, NEW_MODEL))
    cr.execute("""
        UPDATE ir_model_fields
           SET model = %s
         WHERE model = %s
           AND NOT EXISTS (
               SELECT 1 FROM ir_model_fields f
                WHERE f.model = %s AND f.name = ir_model_fields.name
           )
    """, (NEW_MODEL, OLD_MODEL, NEW_MODEL))
    cr.execute("UPDATE ir_model_data SET model = %s WHERE model = %s",
               (NEW_MODEL, OLD_MODEL))

    # 字段改名（模型侧 + 产品模板侧冗余字段）
    field_renames = [
        (NEW_MODEL, "model_code", "reference_code"),
        (NEW_MODEL, "model_type", "reference_type"),
        ("product.template", "model_code_index", "reference_code_index"),
    ]
    for model, old, new in field_renames:
        cr.execute("""
            UPDATE ir_model_fields
               SET name = %s
             WHERE model = %s AND name = %s
               AND NOT EXISTS (
                   SELECT 1 FROM ir_model_fields f
                    WHERE f.model = ir_model_fields.model AND f.name = %s
               )
        """, (new, model, old, new))

    # 唯一约束记录（名称 + 定义）
    cr.execute("""
        UPDATE ir_model_constraint
           SET name = %s,
               definition = REPLACE(definition, 'model_code', 'reference_code')
         WHERE name = %s
    """, (
        "product_reference_code_reference_code_unique_per_template",
        "product_model_code_model_code_unique_per_template",
    ))

    # 视图与动作引用
    cr.execute("UPDATE ir_ui_view SET model = %s WHERE model = %s",
               (NEW_MODEL, OLD_MODEL))
    cr.execute("UPDATE ir_act_window SET res_model = %s WHERE res_model = %s",
               (NEW_MODEL, OLD_MODEL))


def migrate(cr, version):
    """Odoo 19 已移除 ``ir_translation`` 表（译文落在记录自身的 jsonb 列与 .po 文件里），
    因此这里无需处理译文：升级后由 ``i18n/zh_CN.po`` 重新导入即可。
    """
    _rename_module(cr)
    _rename_xmlid_names(cr)
    _rename_tables_and_columns(cr)
    _rename_metadata(cr)
