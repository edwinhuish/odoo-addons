# 产品多参考号

Odoo 19 产品模块扩展，用于在外贸 SOHO 场景下为一个产品挂载多个参考号，并支持按任一参考号搜索到对应产品。

> 模块原名 `product_model`（`19.0.2.0.0` 起改名 `product_reference`），模型原名 `product.model.code`；
> 命名与 Odoo 原生「内部参考（Internal Reference）」保持一致，源码与界面文案统一用 `reference`。

---

## 功能概述

- 一个产品可挂多个参考号（客户参考号 / 工厂参考号 / 别名）
- 原生 Odoo `default_code`（General Information 的 `Reference`）在产品表单的「参考号」页顶部直接显示，可统一编辑
- 参考号用独立明细模型 + `One2many` 挂在 `product.template` 上
- 同一产品内参考号不可重复；不同产品间允许同参考号，重复时命中提示区分
- 搜索能力在数据库层实现：冗余可存储字段 `reference_code_index` + trigram 索引
- 产品列表搜索框、Many2one 下拉、搜索建议、快速搜索均可按参考号命中
- 命中参考号时，列表结果显示「产品名（命中参考号：xxx）」便于区分
- 参考号行支持增删改排序，支持在列表内直接批量录入

---

## 核心设计

| 设计点 | 说明 |
|--------|------|
| 原生 Reference 统一编辑 | 在产品「参考号」页顶部直接放置 Odoo 原生 `default_code` 字段，用户无需切回「常规信息」页 |
| 独立明细模型 | 参考号存于 `product.reference.code`，禁止逗号分隔塞进单个 `Char` |
| 数据库层搜索 | 冗余字段 `reference_code_index`（`Text` + trigram 索引）拼接所有参考号，由参考号行增删改时自动同步 |
| `_search_display_name` 扩展 | Many2one 下拉、搜索建议、快速搜索按 `reference_code_index` 命中产品 |
| `web_search_read` 提示 | 列表请求 `name` 且搜索域命中参考号时，在 `name` 后附加「命中参考号：xxx」 |
| 同产品去重 | `@api.constrains` 中文提示 + 数据库 `UNIQUE(product_tmpl_id, reference_code)` 兜底 |
| 级联清理 | 删除产品时参考号行 `ondelete='cascade'`，无孤儿数据 |

---

## 模型字段

### `product.template`（扩展）

| 字段 | 类型 | 说明 |
|------|------|------|
| `reference_code_line_ids` | `One2many` → `product.reference.code` | 该产品的所有参考号明细 |
| `reference_code_count` | `Integer`（compute） | 参考号数量 |
| `reference_code_index` | `Text`（store + trigram 索引） | 所有参考号拼接的搜索索引，自动维护，勿手工编辑 |

### `product.reference.code`（新建）

| 字段 | 类型 | 说明 |
|------|------|------|
| `reference_code` | `Char`（required, index） | 参考号，同产品内不可重复 |
| `reference_type` | `Selection` | 客户参考号 / 工厂参考号 / 别名 |
| `sequence` | `Integer` | 排序，数值小的在前 |
| `active` | `Boolean` | 启用状态，可停用而不删除 |
| `note` | `Char` | 备注（对应客户、版本、生效日期等） |
| `product_tmpl_id` | `Many2one` → `product.template`（required, index, cascade） | 所属产品 |

---

## 视图

- **产品表单**：「常规信息」页之后新增「参考号（References）」页，顶部放置原生 `default_code`（Reference）字段，下方内嵌 One2many 行，可增删改排序其他参考号
- **产品列表**：新增「参考号」列（可选显示），展示 `reference_code_index` 拼接结果
- **产品搜索**：顶部搜索框并入参考号搜索；新增独立的「参考号」搜索项
- **参考号独立视图**：`产品参考号` 菜单动作，供管理员批量检索与维护

---

## 国际化（i18n）

- **源语言：英文（`en_US`）**。Python / XML 中所有用户可见文本一律写英文，中文由译文文件提供。
- **中文译文：`i18n/zh_CN.po`**（简体中文 `zh_CN`）；模块默认展示英文，安装中文语言后界面切为中文。
- 覆盖范围：模型与字段名称 / `help`、参考号类型 selection 标签、唯一约束与 `ValidationError` 报错、视图标题 / 列标题 / 占位提示 / 页面提示 / 空视图帮助。
- 术语对照：英文 `reference` ↔ 中文「参考号」。
- 列表命中参考号的后缀提示由 `product_template.py` 的 `_(" (Matching reference: %(codes)s)")` 生成，中文译文为「（命中参考号：xxx）」。
- 占位符统一用命名形式 `%(name)s`，禁止按位置 `%s` 拼接。
- 改动流程：改英文源文本 → 在 `i18n/zh_CN.po` 补 `msgid` / `msgstr` → `odoo -d <db> -u product_reference --stop-after-init` 升级 → 刷新页面。
- 启用中文：设置 → 语言 → 安装「简体中文 (zh_CN)」。

---

## 依赖

- `product`（产品模块，最小化依赖，不依赖 `sale`）

---

## 安装与使用

1. 将 `product_reference` 目录放入 Odoo 19 的 `addons_path`（**替换**旧的 `product_model` 目录）
2. 更新应用列表后升级 / 安装模块：`产品多参考号`
3. 打开任意产品表单，切换到「参考号（References）」页，可直接在页顶编辑 Odoo `Reference`；下方继续添加客户参考号、工厂参考号、别名
4. 在「常规信息」页编辑 `Reference` 同样有效；两处修改的是同一个原生字段
5. 在产品列表搜索框输入参考号，或销售订单行选产品时输入参考号，均可命中对应产品

### 从 product_model 升级（已装旧模块的库必做）

Odoo 无法自行识别模块改名，升级前先对目标库执行一次（只做一次，可重复执行，无副作用）：

```sql
UPDATE ir_module_module SET name = 'product_reference' WHERE name = 'product_model';
UPDATE ir_model_data SET module = 'product_reference' WHERE module = 'product_model';
UPDATE ir_model_data SET name = 'module_product_reference'
 WHERE module = 'base' AND name = 'module_product_model';
```

然后：

```bash
odoo -d <db> -u product_reference --stop-after-init
```

模块自带 `migrations/19.0.2.0.0/pre-migration.py`，负责模型 `product.model.code` → `product.reference.code`、
字段 `model_code` / `model_type` / `model_code_index` → `reference_code` / `reference_type` / `reference_code_index`
以及表、索引、唯一约束、外部 ID 的改名；脚本幂等，重复升级不会重复改名或丢数据。

> 未执行上述 SQL 就直接安装 `product_reference`，会被 Odoo 当成新模块：旧 `product_model`
> 的数据不会自动接上。此时请回滚到升级前备份再按上面顺序重来。

### 原生 Reference 在参考号页统一编辑

- 产品表单的「参考号（References）」页顶部直接放置 Odoo 原生的 `default_code` 字段，标签显示为 `Reference`。
- 该字段与「常规信息」页的 `Reference` 是同一个字段，修改任意一处都会同步生效。
- 它不属于 `product.reference.code` 明细行，因此不占用参考号行的唯一约束，也不参与参考号行的排序。

### 批量录入参考号

在产品表单的「参考号」页 One2many 列表中，可直接逐行新增参考号；列表为 `editable="bottom"`，支持快速连续录入。

---

## 验证清单

> 目标环境已验证通过（2026-09-07，落地版本 `19.0.2.2.0`；`19.0.2.0.0` 完成 `product_model` → `product_reference` 改名与数据迁移，T-007；`19.0.2.2.0` 完成参考号页顶部原生 `Reference` 统一编辑，T-008）。

| 验证项 | 期望 | 结果 |
|--------|------|------|
| 升级后模块名 | 应用列表显示 `产品多参考号`（`product_reference`），无 `product_model` 残留 | 通过 |
| 历史数据 | 旧型号数据完整出现在产品「参考号」页与 `product_reference_code` 表 | 通过 |
| 产品表单参考号页 | 页顶可编辑 Odoo `Reference`；下方可增删改排序其他参考号行 | 通过 |
| Reference 统一编辑 | 在「参考号」页修改页顶 `Reference`，「常规信息」页同步变化，反之亦然 | 通过 |
| 同产品重复参考号 | 阻止并给中文提示，带出具体值与产品名 | 通过 |
| 产品列表搜索框输入参考号 | 命中对应产品，`name` 显示「产品名（命中参考号：xxx）」 | 通过 |
| 销售订单行选产品输入参考号 | 命中对应产品 | 通过 |
| 删除参考号行 | 不报错，列表 `reference_code_index` 按剩余行重算 | 通过 |
| 删除产品 | 参考号行随之级联清理 | 通过 |
| 中英双语 | 英文界面为 `Reference` 系列文案，中文界面为「参考号」系列文案 | 通过 |
| 索引 | `product_template__reference_code_index_index`（trigram）与 `product_reference_code_reference_code_unique_per_template` 存在 | 通过 |

### 执行流程

1. 备份数据库
2. 执行上面的改名 SQL
3. `odoo -d <db> -u product_reference --stop-after-init`
4. 刷新浏览器（前端有缓存），按上表逐项验证

### 异常情况与处理

- 历史产品无参考号：`reference_code_index` 为空，搜索框输入参考号不命中（预期行为）
- 同产品重复参考号：`@api.constrains` 阻止 + DB `UNIQUE` 兜底
- 不同产品同参考号：允许，列表 `name` 附加「命中参考号：xxx」区分
- 索引与参考号行不一致：shell 执行 `env['product.template'].search([])._sync_reference_index()`
- 升级报「column model_code does not exist」类错误：说明改名 SQL 未生效或迁移未跑到，
  回滚备份后按「从 product_model 升级」重做

### 后续维护

- 改拼接分隔符只改 `_sync_reference_index`，改后触发一次同步
- 新增参考号类型只改 `reference_type` 的 `selection`
- 其他单据 Many2one 指向 `product.template` 即自动支持参考号搜索，无需额外改动

---

## 许可证

LGPL-3
