# -*- coding: utf-8 -*-
"""模块钩子。

**安装前（`pre_init_hook`）**：把旧 `product_packing` 模块留在模板上的尺寸数据搬到变体上。
`product_packing` 是本模块的前身（已改名为 `product_dimension`），它把产品尺寸放在**模板**上；
本模块把尺寸改成**变体**级 —— 只有这样，多变体产品的每条变体才有自己的尺寸与 Volume
（这是 `T-021` 要解决的问题）。

模块改名后旧模块的字段定义就从注册表里消失了，它的数据列会以孤儿列的形式留在
`product_template` 上，只能读列名、不能读 ORM 字段。所以这里用 SQL 搬：

1. 给 `product_product` 补上本模块的尺寸列（若随后 Odoo 自己建列，会复用同名列）；
2. 把每条模板的尺寸值复制给它的**全部**变体（模板级的值原本就是全变体共享的，
   复制一份比丢掉安全）；
3. 长宽高都大于 0 时按单位重算变体的原生 `volume`，与模块运行时的行为保持一致。

只在旧列存在时执行，且可重复执行（`COALESCE` + `IF NOT EXISTS`）。

**安装后（`post_init_hook`）**：把全局「Volume」小数精度提到本模块需要的最低值（见下）。
升级路径由 `migrations/19.0.4.1.0/` 里的脚本负责（`post_init_hook` 只在安装时跑）。
"""

import logging

_logger = logging.getLogger(__name__)

# （本模块字段名, 旧模块在 product_template 上的列名, 列类型）
LEGACY_COLUMNS = (
    ("dimension_unit", "product_dimension_unit", "varchar"),
    ("dimension_length", "product_length", "numeric"),
    ("dimension_width", "product_width", "numeric"),
    ("dimension_height", "product_height", "numeric"),
)


def pre_init_hook(env):
    """把旧模块的模板级尺寸数据搬到变体上（没有旧数据时什么都不做）。"""
    cr = env.cr
    cr.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_name = 'product_template'
           AND column_name IN %s
        """,
        (tuple(legacy for _new, legacy, _type in LEGACY_COLUMNS),),
    )
    if not cr.fetchall():
        return

    for new_name, legacy_name, column_type in LEGACY_COLUMNS:
        cr.execute(
            'ALTER TABLE product_product ADD COLUMN IF NOT EXISTS "%s" %s'
            % (new_name, column_type)
        )
        cr.execute(
            """
            UPDATE product_product AS variant
               SET "%(new)s" = COALESCE(variant."%(new)s", template."%(legacy)s")
              FROM product_template AS template
             WHERE variant.product_tmpl_id = template.id
               AND template."%(legacy)s" IS NOT NULL
            """
            % {"new": new_name, "legacy": legacy_name}
        )
        _logger.info(
            "product_dimension: filled %s variant rows of %s from product_template.%s",
            cr.rowcount, new_name, legacy_name,
        )

    # 单位是必填的：旧列里为空的变体一律按厘米处理
    cr.execute("UPDATE product_product SET dimension_unit = 'cm' WHERE dimension_unit IS NULL")
    # 尺寸齐全的变体按单位重算原生 Volume（与 _sync_volume_from_dimensions 一致）
    cr.execute(
        """
        UPDATE product_product
           SET volume = dimension_length * dimension_width * dimension_height
                      / (CASE WHEN dimension_unit = 'm' THEN 1.0 ELSE 1000000.0 END)
         WHERE dimension_length > 0 AND dimension_width > 0 AND dimension_height > 0
        """
    )
    _logger.info("product_dimension: recomputed volume for %s variants", cr.rowcount)


#: 本模块需要的「Volume」小数位数。
#:
#: 为什么是 6：cm 尺寸下 1 cm³ = 0.000001 m³，而 Odoo 出厂的「Volume」精度是 **2 位** ——
#: 20 × 20 × 20 cm 这种很常见的体积（0.008 m³）会被舍成 0，用户看到「填了尺寸、体积是 0」。
#: 6 位正好能表示 1 cm³。
REQUIRED_VOLUME_PRECISION = 6


def ensure_volume_precision(env):
    """把全局「Volume」小数精度提到 `REQUIRED_VOLUME_PRECISION`（只升不降，幂等）。

    为什么动全局设置：`volume` 是 `digits='Volume'` 的原生字段，小数位来自这张全局表，
    Odoo 没有「只对本模块生效」的开关 —— 不改它，cm 尺寸的小体积在界面上永远是 0。
    只提升、不降低，所以管理员自己调更高的位数不会被模块覆盖；
    想改用更少位数，在 设置 → 技术 → 小数精度 里直接改（模块之后不再干预）。
    """
    precision = env["decimal.precision"].search([("name", "=", "Volume")], limit=1)
    if not precision or precision.digits >= REQUIRED_VOLUME_PRECISION:
        return
    _logger.info(
        "product_dimension: raising the Volume decimal precision from %s to %s "
        "(small centimetre volumes would otherwise be rounded to 0)",
        precision.digits, REQUIRED_VOLUME_PRECISION,
    )
    precision.digits = REQUIRED_VOLUME_PRECISION


def post_init_hook(env):
    """安装后：确保「Volume」精度够用（见 `ensure_volume_precision()`）。"""
    ensure_volume_precision(env)
