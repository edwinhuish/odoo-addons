# 产品多型号

Odoo 19 产品模块扩展，用于在外贸 SOHO 场景下为一个产品挂载多个型号，并支持按任一型号搜索到对应产品。

---

## 功能概述

- 一个产品可挂多个型号（客户型号 / 工厂型号 / 别名）
- 型号用独立明细模型 + `One2many` 挂在 `product.template` 上
- 同一产品内型号不可重复；不同产品间允许同型号，重复时命中提示区分
- 搜索能力在数据库层实现：冗余可存储字段 `model_code_index` + trigram 索引
- 产品列表搜索框、Many2one 下拉、搜索建议、快速搜索均可按型号命中
- 命中型号时，列表结果显示「产品名（命中型号：xxx）」便于区分
- 型号行支持增删改排序，支持在列表内直接批量录入

---

## 核心设计

| 设计点 | 说明 |
|--------|------|
| 独立明细模型 | 型号存于 `product.model.code`，禁止逗号分隔塞进单个 `Char` |
| 数据库层搜索 | 冗余字段 `model_code_index`（`Text` + trigram 索引）拼接所有型号，由型号行增删改时自动同步 |
| `_search_display_name` 扩展 | Many2one 下拉、搜索建议、快速搜索按 `model_code_index` 命中产品 |
| `web_search_read` 提示 | 列表请求 `name` 且搜索域命中型号时，在 `name` 后附加「命中型号：xxx」 |
| 同产品去重 | `@api.constrains` 中文提示 + 数据库 `UNIQUE(product_tmpl_id, model_code)` 兜底 |
| 级联清理 | 删除产品时型号行 `ondelete='cascade'`，无孤儿数据 |

---

## 模型字段

### `product.template`（扩展）

| 字段 | 类型 | 说明 |
|------|------|------|
| `model_code_line_ids` | `One2many` → `product.model.code` | 该产品的所有型号明细 |
| `model_code_count` | `Integer`（compute） | 型号数量 |
| `model_code_index` | `Text`（store + trigram 索引） | 所有型号拼接的搜索索引，自动维护，勿手工编辑 |

### `product.model.code`（新建）

| 字段 | 类型 | 说明 |
|------|------|------|
| `model_code` | `Char`（required, index） | 型号，同产品内不可重复 |
| `model_type` | `Selection` | 客户型号 / 工厂型号 / 别名 |
| `sequence` | `Integer` | 排序，数值小的在前 |
| `active` | `Boolean` | 启用状态，可停用而不删除 |
| `note` | `Char` | 备注（对应客户、版本、生效日期等） |
| `product_tmpl_id` | `Many2one` → `product.template`（required, index, cascade） | 所属产品 |

---

## 视图

- **产品表单**：「常规信息」页之后新增「型号」页，内嵌 One2many 行，可增删改排序
- **产品列表**：新增「型号」列（可选显示），展示 `model_code_index` 拼接结果
- **产品搜索**：顶部搜索框并入型号搜索；新增独立的「型号」搜索项
- **型号独立视图**：`产品型号` 菜单动作，供管理员批量检索与维护

---

## 依赖

- `product`（产品模块，最小化依赖，不依赖 `sale`）

---

## 安装与使用

1. 将 `product_model` 目录放入 Odoo 19 的 `addons_path`
2. 更新应用列表后安装模块：`产品多型号`
3. 打开任意产品表单，在「型号」页新增型号行
4. 在产品列表搜索框输入型号，或销售订单行选产品时输入型号，均可命中对应产品

### 批量录入型号

在产品表单的「型号」页 One2many 列表中，可直接逐行新增型号；列表为 `editable="bottom"`，支持快速连续录入。

---

## 验证清单

> 验收日期：2026-09-02，目标环境验证通过。

| 验证项 | 期望 | 结果 |
|--------|------|------|
| 产品表单型号页 | 可增删改排序型号行 | 通过 |
| 同产品重复型号 | 阻止并给中文提示，带出具体值与产品名 | 通过 |
| 产品列表搜索框输入型号 | 命中对应产品，`name` 显示「产品名（命中型号：xxx）」 | 通过 |
| 销售订单行选产品输入型号 | 命中对应产品 | 通过 |
| 型号批量录入 | One2many 列表连续录入可用 | 通过 |
| 删除产品 | 型号行随之级联清理 | 通过 |

### 执行流程

1. 首次安装：`odoo -d <db> -i product_model --stop-after-init`
   自动建表、建列与 trigram 索引、加载权限
2. 产品表单「型号」页新增型号行，保存后 `model_code_index` 自动同步
3. 产品列表搜索框输入型号验证命中与提示
4. 销售订单行选产品处输入型号验证 Many2one 命中
5. 同产品录重复型号验证去重提示
6. 删除产品验证级联清理

### 异常情况与处理

- 历史产品无型号：`model_code_index` 为空，搜索框输入型号不命中（预期行为）
- 同产品重复型号：`@api.constrains` 阻止 + DB `UNIQUE` 兜底
- 不同产品同型号：允许，列表 `name` 附加「命中型号：xxx」区分
- 索引与型号行不一致：shell 执行 `env['product.model.code'].search([])._sync_template_index()`

### 后续维护

- 改拼接分隔符只改 `_sync_template_index`，改后触发一次同步
- 新增型号类型只改 `model_type` 的 `selection`
- 其他单据 Many2one 指向 `product.template` 即自动支持型号搜索，无需额外改动

---

## 许可证

LGPL-3
