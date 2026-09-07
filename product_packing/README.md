# 产品包装信息

Odoo 19 `product` 模块扩展，为产品增加外贸常用的包装/纸箱信息，包括装箱数、纸箱长宽高、毛重、净重与自动计算的 CBM，所有字段直接整合在产品表单的 Inventory 标签页中。

> 模块技术名：`product_packing`  
> 无前身模块，首次安装即可使用。

---

## 功能概述

- 在产品 Inventory 标签页新增「纸箱与包装（Carton & Packing）」分组
- 支持录入每个纸箱的装箱数（Units per Carton）
- 纸箱长、宽、高分为三个独立字段，单位可在厘米 / 米之间按产品配置
- 支持录入纸箱毛重与净重（千克）
- CBM 根据长宽高自动计算并展示，单位固定为立方米
- 产品列表增加「纸箱规格」与「CBM」可选列
- 自动校验：数值非负、净重不超过毛重

---

## 核心设计

| 设计点 | 说明 |
|--------|------|
| 与 Inventory 原生信息整合 | 继承 `product.product_template_form_view`，在原 Logistics 组之后插入新分组，不另开标签页，减少切换 |
| 单位配置放在产品级 | 每个产品单独选择厘米或米，避免全局单位与具体业务冲突；CBM 始终按立方米计算，保证跨产品可比 |
| 独立长宽高字段 | 分开三个 Float 字段便于后续报表、导出、接口直接读取，不依赖字符串解析 |
| 计算字段 | `carton_cbm` 与 `carton_dimension_spec` 为 `store=True` 计算字段，列表视图可直接显示而不触发逐行计算 |
| 校验在模型层 | `@api.constrains` 统一校验，错误信息带具体数值，用户可直接看懂 |
| 最小依赖 | 仅依赖 `product`，不依赖 `stock` / `sale` / `purchase` |

---

## 模型字段

### `product.template`（扩展）

| 字段 | 类型 | 说明 |
|------|------|------|
| `carton_qty_per_carton` | `Integer` | 每个纸箱可装的产品数量 |
| `carton_dimension_unit` | `Selection`（`cm` / `m`） | 纸箱长宽高单位，默认厘米 |
| `carton_length` | `Float` | 纸箱长度（按所选单位） |
| `carton_width` | `Float` | 纸箱宽度（按所选单位） |
| `carton_height` | `Float` | 纸箱高度（按所选单位） |
| `carton_gross_weight` | `Float` | 纸箱毛重（千克） |
| `carton_net_weight` | `Float` | 纸箱净重（千克） |
| `carton_cbm` | `Float`（compute, store） | 纸箱立方米数，按单位自动换算 |
| `carton_dimension_spec` | `Char`（compute, store） | 可读尺寸文本，如 `50 x 40 x 30 cm` |

---

## 视图

- **产品表单**：Inventory 页新增「纸箱与包装」组，放在原生 Logistics 组之后；CBM 只读，尺寸单位与长宽高编辑后实时重算
- **产品列表**：新增「纸箱」「CBM」两列，默认隐藏，用户可手动显示

---

## 国际化（i18n）

- **源语言：英文（`en_US`）**。Python / XML 中所有用户可见文本一律写英文，中文由译文文件提供。
- **中文译文：`i18n/zh_CN.po`**（简体中文 `zh_CN`）；模块默认展示英文，安装中文语言后界面切为中文。
- 覆盖范围：字段名称 / `help`、尺寸单位 selection 标签、`ValidationError` 报错、视图标题 / 列标题 / 占位提示 / 单位文本。
- 占位符统一用命名形式 `%(name)s`，禁止按位置 `%s` 拼接。
- 改动流程：改英文源文本 → 在 `i18n/zh_CN.po` 补 `msgid` / `msgstr` → `odoo -d <db> -u product_packing --stop-after-init` 升级 → 刷新页面。
- 启用中文：设置 → 语言 → 安装「简体中文 (zh_CN)」。

---

## 依赖

- `product`（产品模块，最小化依赖，不依赖 `stock` / `sale` / `purchase`）

---

## 安装与使用

### 全新安装

1. 将 `product_packing` 目录放入 Odoo 19 的 `addons_path`
2. 更新应用列表后安装模块：`产品纸箱尺寸`
3. 打开任意产品表单，切换到 Inventory 标签页，在「纸箱与包装」组录入数据并保存

### CBM 计算示例

| 单位 | 长 | 宽 | 高 | CBM |
|------|----|----|----|-----|
| 厘米 | 50 | 40 | 30 | 0.060000 |
| 米 | 0.5 | 0.4 | 0.3 | 0.060000 |

### 操作要点

- 切换「尺寸单位」后，已录入的长宽高数值保持不变，CBM 会按新单位重新计算
- 任一尺寸为 0 或负数时，CBM 显示为 0
- 净重必须 ≤ 毛重；所有数值必须 ≥ 0

---

## 验证清单

> 验收日期：2026-09-07，目标环境验证待验证。

| 验证项 | 期望 | 结果 |
|--------|------|------|
| 模块安装 | `odoo -d <db> -i product_packing --stop-after-init` 成功，无报错 | 待验证 |
| Inventory 标签页 | 消费品（`type = consu`）产品表单中可见「纸箱与包装」组 | 待验证 |
| 字段录入与保存 | 装箱数、长宽高、单位、毛重、净重可正常输入并保存 | 待验证 |
| CBM 自动计算（厘米） | 50×40×30 cm → CBM = 0.06 | 待验证 |
| CBM 自动计算（米） | 0.5×0.4×0.3 m → CBM = 0.06 | 待验证 |
| 单位切换 | cm 切到 m 后，CBM 按米重新计算 | 待验证 |
| 校验：负数 | 保存负数时报中文/英文错误并带出具体值 | 待验证 |
| 校验：净重 > 毛重 | 保存时报中文/英文错误 | 待验证 |
| 列表可选列 | 产品列表可选显示「纸箱」「CBM」列 | 待验证 |
| 中英双语 | 英文界面为英文，切换简体中文后字段标签、报错、单位为中文 | 待验证 |

### 回滚方式

- 首次安装：在 Odoo 后台卸载模块 `product_packing` 即可，新增字段会被清理
- 升级失败：恢复升级前的数据库备份，并确认 `product_packing` 目录为升级前版本

### 后续维护

- 新增纸箱字段：扩展 `product.template` 并同步更新视图、i18n、README 字段表
- 修改 CBM 计算逻辑：只改 `_compute_carton_cbm`，`carton_cbm` 为 stored compute，升级后会自动重算
- 新增/修改校验：同步更新 `i18n/zh_CN.po` 中的报错译文

---

## 许可证

LGPL-3
