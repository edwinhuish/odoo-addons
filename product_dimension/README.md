# 产品尺寸

Odoo 19 `product` 模块扩展：为产品增加外贸物流用的**尺寸单位（厘米 / 米）与长宽高**，并据此自动维护原生的 `Volume`（立方米）。尺寸存放在**变体**上，所以多变体产品的每条变体各持一份尺寸与体积；产品表单上是「单变体桥接」，展示位置与原生 `Volume` / `Weight` 完全一致。

> 模块技术名：`product_dimension`
> 前身：`product_packing`（纸箱与包装）—— 本模块是它的替代，只保留物流尺寸，纸箱字段已移除。迁移方式见「从 product_packing 迁移」。

---

## 功能概述

- 在产品表单原生的 **Logistics** 组里（`Volume` 之前）新增 **Dimension Unit** 与 **Dimensions**（长 × 宽 × 高），不另开标签页
- 尺寸变化时按所选单位自动重算该变体的原生 `Volume`：厘米按 `cm³ / 1 000 000`、米按直接相乘，结果恒为立方米
- **尺寸与 Volume 都是变体级的**：多变体产品里每条变体各填各的尺寸、各算各的体积，互不影响
- 产品有多条变体时，产品表单上这些字段自动隐藏（与原生 `Volume` 字段的可见性规则一致），改到变体表单里逐条维护
- 配合 [`product_variant_conversion`](../product_variant_conversion/README.md) 做变体转换时，**尺寸随谱系继承**：新变体继承它来源变体的尺寸，体积随之算出
- 校验：尺寸不允许为负
- 最小依赖：仅 `product`

---

## 核心设计

| 设计点 | 说明 |
|--------|------|
| 尺寸真身在变体上 | `dimension_unit` / `dimension_length` / `dimension_width` / `dimension_height` 定义在 `product.product` 上。理由：Odoo 的 `volume` / `weight` 本来就是变体级字段，尺寸是体积的来源，放在同一层才不会出现「模板有尺寸、变体各自有体积」的错位（这是 `T-021` 要解决的问题） |
| 模板侧只是「单变体桥接」 | `product.template` 上的同名字段是 `compute` + `inverse` + `store=True` 的镜像：单变体时读 / 写都落在那条变体上，多条变体时读出空值、写入不牵动任何变体 —— 与原生 `volume` / `weight` 同构（`store=True` 让它们像原生字段一样可搜索 / 分组） |
| 可见性沿用原生规则 | 插入的字段与 `Volume` 一样带 `invisible="product_variant_count > 1 and not is_product_variant"`：单变体产品与变体表单上看得到，多变体产品的模板表单上隐藏，避免出现「填了却不生效」的静默失败 |
| Volume 同步覆盖两条路 | `@api.onchange`（表单实时预览）+ `create` / `write`（后台批量、导入、API），保证表单与数据库一致 |
| 校验在模型层 | `@api.constrains` 校验非负，报错带字段名、产品名与具体数值 |

---

## 模型字段

### `product.product`（扩展，真身）

| 字段 | 类型 | 说明 |
|------|------|------|
| `dimension_unit` | `Selection`（`cm` / `m`） | 本变体的尺寸单位，默认厘米，必填 |
| `dimension_length` | `Float`（10, 2） | 长度（按所选单位） |
| `dimension_width` | `Float`（10, 2） | 宽度（按所选单位） |
| `dimension_height` | `Float`（10, 2） | 高度（按所选单位） |
| `volume` | `Float`（原生） | 由上面四项算出，单位恒为立方米 |

### `product.template`（扩展，单变体桥接）

| 字段 | 类型 | 说明 |
|------|------|------|
| `dimension_unit` | `Selection`（compute + inverse, store） | 单变体时镜像该变体的单位；多变体时为空 |
| `dimension_length` / `dimension_width` / `dimension_height` | `Float`（compute + inverse, store） | 单变体时镜像该变体的值；多变体时为 0 |

### 方法

| 签名 | 说明 |
|------|------|
| `_sync_volume_from_dimensions()`（`product.product`） | 按本变体尺寸重算 `volume`；长宽高不齐（任一为 0）时归 0 |
| `_get_single_variant_dimension(field_name)`（`product.template`） | 单变体时取该变体的值，否则给空值（`False` / `0.0`） |
| `_set_dimension_to_variant(field_name)`（`product.template`） | 单变体时把模板上的值写回那条变体；多变体时不动 |

---

## 视图

- **产品表单**：在原生 Logistics 组的 `Volume` 之前插入 `Dimension Unit` 与 `Dimensions`（长 × 宽 × 高）；可见性规则与原生 `Volume` 相同
- 不新增列表列（前身的「纸箱」「CBM」列随纸箱字段一起移除）

---

## 已知限制

| 限制 | 说明 |
|------|------|
| `Volume` 只有 2 位小数 | 原生 `Volume` 按 Odoo 的「Volume」小数精度存储，**默认 2 位小数**（由 `product` 模块提供），所以小于 0.01 m³ 的体积会被舍入为 0（例如 10×10×10 cm）。产品确实这么小时，请在 设置 → 技术 → 小数精度 里把 `Volume` 调高（例如 6）。这是 Odoo 的原生设置，模块不会替你改全局精度。 |
| 尺寸不齐则体积归 0 | 长宽高任一为 0 时 `volume` 归 0（与前身模块的行为一致）；即「先填全尺寸，体积才成立」。 |
| 多变体产品的模板表单不显示尺寸 | 与原生 `Volume` / `Weight` 一致：此时模板上的桥接字段读出空值，写入也不生效（界面上已隐藏，正常操作碰不到）。通过 RPC 硬写模板字段不会影响任何变体。 |
| 归档 / 删除变体不清理尺寸 | 尺寸只是变体上的普通字段，随变体一起被归档或删除。 |

---

## 从 product_packing 迁移

前身模块把尺寸放在**模板**上（`product_dimension_unit` / `product_length` / `product_width` / `product_height`），本模块把它移到**变体**上，因此需要一次数据搬运：

1. **先安装 `product_dimension`**：安装前钩子（`hooks.py::pre_init_hook`）会检测 `product_template` 上的旧列，把它们复制给该模板的**全部**变体，并把尺寸齐全的变体按单位重算 `volume`。旧列不存在时什么都不做。
2. **确认变体侧数据**：打开产品 → 变体表单 / 变体列表，核对尺寸与 `Volume`。
3. **再卸载 `product_packing`**：DB 里残留的旧模块记录要卸掉，否则每次加载都会报 `module product_packing: not installable, skipped`。卸载会删掉旧的模板列——此时数据已在变体上，属预期。

> 搬运用的是 SQL 列名（旧模块代码已不在 addons 里，注册表里没有它的字段），所以只认上面四个列名；`COALESCE` + `ADD COLUMN IF NOT EXISTS` 保证可重复执行。

---

## 依赖

- `product`（最小化依赖，不依赖 `stock` / `sale` / `purchase`）
- 可选协同：装了 [`product_variant_conversion`](../product_variant_conversion/README.md) 时，转换出的新变体会按谱系继承尺寸（该模块按字段是否存在判断，不硬依赖本模块）

---

## 安装与使用

### 全新安装

1. 将 `product_dimension` 目录放入 Odoo 19 的 `addons_path`
2. 更新应用列表后安装模块：`Product Dimensions`
3. 打开任意消费品（Goods）产品 → Inventory 标签页 → Logistics 组，填 `Dimension Unit` 与 `Dimensions`

### 计算示例

| 单位 | 长 | 宽 | 高 | `Volume`（m³） |
|------|----|----|----|------------------|
| 厘米 | 50 | 40 | 30 | 0.06 |
| 米 | 0.5 | 0.4 | 0.3 | 0.06 |

### 操作要点

- 切换「尺寸单位」后，已录入的长宽高数值**保持不变**，`Volume` 按新单位重算
- 任一边长为 0 时 `Volume` 显示为 0
- 多变体产品：在产品表单上这些字段不显示，请到**变体表单 / 变体列表**逐条维护

---

## 验证清单

> 前身模块 `product_packing` 的验收记录见 `CHANGELOG.md` 的历史条目；本模块（改名 + 变体级尺寸）的验收状态见下表。

| 验证项 | 期望 | 结果 |
|--------|------|------|
| 模块安装 | `odoo -d <db> -i product_dimension --stop-after-init` 成功，无报错 | 待验证 |
| 旧数据搬运 | 开发库实测：旧模板列 `50 / 40 / 30 cm` → 变体侧 `cm / 50 / 40 / 30`，`volume = 0.06`（安装前钩子日志 `recomputed volume for 1 variants`） | 通过 |
| 单一产品表单显示 | 单变体消费品产品表单 Logistics 组内可见 `Dimension Unit` 与 `Dimensions` | 待验证 |
| Volume 自动更新（cm） | 50×40×30 cm → `Volume = 0.06` | 通过（自动化测试） |
| Volume 自动更新（m） | 1×0.5×0.4 m → `Volume = 0.2` | 通过（自动化测试） |
| 尺寸清空归零 | 任一边长置 0 → `Volume = 0` | 通过（自动化测试） |
| 单变体桥接 | 模板字段读写都落到那条变体上（读镜像、写回变体） | 通过（自动化测试） |
| 多变体各自独立 | 两条变体填不同尺寸 → 各自 `volume` 独立；模板侧读出空值、写入不牵动变体 | 通过（自动化测试） |
| 非负校验 | 负数尺寸被 `ValidationError` 拒绝 | 通过（自动化测试） |
| 转换后尺寸跟随变体 | 普通产品转多变体后，新变体继承来源变体的尺寸与体积 | 通过（自动化测试，见 `product_variant_conversion` 的 `test_new_variants_inherit_variant_dimensions_when_installed`） |
| 中英双语 | 字段标签 / 报错 / 占位符在中文环境为中文，英文环境为英文 | 通过（数据库核对：字段标签 / help / selection / 视图术语；运行期报错实测为中文）；界面待目标环境复验 |
| 应用列表中文名 | 中文环境「应用」搜 `product_dimension`：标题「产品尺寸」、摘要与描述为中文、分类「库存 / 产品」 | 通过（数据库核对 shortdesc / summary / description）；界面待目标环境复验 |

### 自动化测试跑法

```bash
task test -- product_dimension                                    # 本模块 6 项
task test -- product_variant_conversion,product_dimension \
     --test-tags=/product_variant_conversion                      # 含「尺寸随变体继承」的集成用例
```

---

## 国际化（i18n）

- **源语言：英文（`en_US`）**。Python / XML 中所有用户可见文本一律写英文，中文由译文文件提供。
- **中文译文：`i18n/zh_CN.po`**（简体中文 `zh_CN`）；模块默认展示英文，安装中文语言后界面切为中文。
- 覆盖范围：字段名称 / `help`、尺寸单位 selection 标签、`ValidationError` 报错、视图标题 / 占位提示。
- **应用列表（Apps）元数据**：模块名 / 摘要 / 描述的中文由 `model:ir.module.module,shortdesc|summary|description:base.module_product_dimension` 三条提供，分类另有 `model:ir.module.category,name:base.module_category_inventory_product` → 「产品」（与其它产品类模块合并成同一条 `msgid`）；改 `__manifest__.py` 的 `name` / `summary` / `description` 时必须同步这三条的 `msgid`，规范见根 [`AGENTS.md`](../AGENTS.md) 4.8。
- 改动流程：改英文源文本 → 在 `i18n/zh_CN.po` 补 `msgid` / `msgstr` → `task update -- product_dimension` 升级 → 刷新页面。
- 校验：`task check` 会检查 po 里重复 `msgid`、Apps 元数据 `msgid` 与 manifest 是否逐字符一致，以及 `#:` 引用行写法、`#. odoo-python` / `#. odoo-javascript` 标记、po 行结构合法性。
- **验收要看数据库**（「导入没报错」不等于生效）：`ir_model_fields.field_description->>'zh_CN'`、`ir_ui_view.arch_db->>'zh_CN'`、`ir_module_module.shortdesc->>'zh_CN'`；运行期 `_()` 文案用 `with_context(lang='zh_CN')` 触发一次报错核对。三类静默失效的排障见 `AGENTS.md` → L2 P5。

---

## 许可证

LGPL-3
