# 产品包装信息

Odoo 19 `product` 模块扩展，为产品增加外贸常用的包装/纸箱信息，包括装箱数、纸箱长宽高、毛重、净重、自动计算的 CBM，以及产品自身的长宽高（可自动填充原生 Volume），所有字段直接整合在产品表单的 Inventory 标签页中。

> 模块技术名：`product_packing`  
> 无前身模块，首次安装即可使用。

---

## 功能概述

- 在产品 Inventory 标签页原生 Logistics 组中新增产品 Dimension Unit 与 Dimensions
- 产品尺寸任一字段变化时，自动按所选单位重新计算并更新原生 Volume
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
| 与 Inventory 原生信息整合 | 继承 `product.product_template_form_view`，在原生 Logistics 组中把产品 Dimension Unit / Dimensions 放在 `Volume` 之前，并在 Logistics 组之后插入「纸箱与包装」组，不另开标签页，减少切换 |
| 单位配置放在产品级 | 每个产品单独选择厘米或米，避免全局单位与具体业务冲突；CBM / Volume 始终按立方米计算，保证跨产品可比 |
| 独立长宽高字段 | 分开三个 Float 字段便于后续报表、导出、接口直接读取，不依赖字符串解析 |
| 自动同步原生 Volume | 产品尺寸任一字段变化时，`@api.onchange` 实时更新表单 `volume`，`create` / `write` 同步更新数据库，保证表单与后台一致 |
| 计算字段 | `carton_cbm` 与 `carton_dimension_spec` 为 `store=True` 计算字段，列表视图可直接显示而不触发逐行计算 |
| 校验在模型层 | `@api.constrains` 统一校验纸箱字段，错误信息带具体数值，用户可直接看懂 |
| 最小依赖 | 仅依赖 `product`，不依赖 `stock` / `sale` / `purchase` |

---

## 模型字段

### `product.template`（扩展）

| 字段 | 类型 | 说明 |
|------|------|------|
| `product_dimension_unit` | `Selection`（`cm` / `m`） | 产品尺寸单位，默认厘米 |
| `product_length` | `Float` | 产品长度（按所选单位） |
| `product_width` | `Float` | 产品宽度（按所选单位） |
| `product_height` | `Float` | 产品高度（按所选单位） |
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

- **产品表单**：
  - 原生 Logistics 组内在 `Volume` 之前新增 `Dimension Unit` 与 `Dimensions`（长 × 宽 × 高）；产品尺寸变化时实时自动计算并更新原生 `Volume`
  - Logistics 组之后新增「纸箱与包装」组；CBM 只读，尺寸单位与长宽高编辑后实时重算
- **产品列表**：新增「纸箱」「CBM」两列，默认隐藏，用户可手动显示

---

## 国际化（i18n）

- **源语言：英文（`en_US`）**。Python / XML 中所有用户可见文本一律写英文，中文由译文文件提供。
- **中文译文：`i18n/zh_CN.po`**（简体中文 `zh_CN`）；模块默认展示英文，安装中文语言后界面切为中文。
- 覆盖范围：字段名称 / `help`、尺寸单位 selection 标签、`ValidationError` 报错、视图标题 / 列标题 / 占位提示 / 单位文本。
- **应用列表（Apps）元数据**：模块名 / 摘要 / 描述的中文由 `i18n/zh_CN.po` 的 `model:ir.module.module,shortdesc|summary|description:base.module_product_packing` 三条提供，分类另有 `model:ir.module.category,name:base.module_category_inventory_product` → 「产品」；改 `__manifest__.py` 的 `name` / `summary` / `description` 英文文案时必须同步这三条的 `msgid`，规范见根 [`AGENTS.md`](../AGENTS.md) 4.8。
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
2. 更新应用列表后安装模块：`Product Packing`
3. 打开任意产品表单，切换到 Inventory 标签页，在「纸箱与包装」组录入数据并保存

### CBM 计算示例

| 单位 | 长 | 宽 | 高 | CBM |
|------|----|----|----|-----|
| 厘米 | 50 | 40 | 30 | 0.060000 |
| 米 | 0.5 | 0.4 | 0.3 | 0.060000 |

### 操作要点

- 切换「尺寸单位」后，已录入的长宽高数值保持不变，CBM / Volume 会按新单位重新计算
- 任一尺寸为 0 或负数时，CBM 显示为 0
- 净重必须 ≤ 毛重；所有数值必须 ≥ 0
- 产品尺寸任一字段变化时，原生 `Volume` 会自动按最新尺寸重算；清空尺寸或全部置 0 后，`Volume` 会变为 0

---

## 验证清单

> 验收日期：2026-09-08，目标环境已验证（T-009）。
> `19.0.1.1.3`（2026-09-09，T-013）补应用列表（Apps）中文元数据（模块名 / 摘要 / 描述 + 分类「产品」，并修掉 `Dimension Unit` 重复 `msgid`），目标环境已验收通过；记录见 `CHANGELOG.md` →「验收记录（T-013）」。

| 验证项 | 期望 | 结果 |
|--------|------|------|
| 模块安装 | `odoo -d <db> -i product_packing --stop-after-init` 成功，无报错 | 通过 |
| Logistics 组产品尺寸 | 消费品产品表单 Logistics 组内可见 `Dimension Unit` 与 `Dimensions` | 通过 |
| Volume 自动更新 | 输入 50×40×30 cm 后 `Volume` 自动变为 0.06；切换单位为 m 后按新单位重算 | 通过 |
| Volume 清空尺寸归零 | 清空任一长宽高后 `Volume` 自动变为 0 | 通过 |
| 后台同步 | 通过导入或 API 更新尺寸后，`Volume` 同样被更新 | 通过 |
| Inventory 标签页纸箱组 | 消费品产品表单中可见「纸箱与包装」组 | 通过 |
| 字段录入与保存 | 装箱数、纸箱长宽高、单位、毛重、净重可正常输入并保存 | 通过 |
| CBM 自动计算（厘米） | 50×40×30 cm → CBM = 0.06 | 通过 |
| CBM 自动计算（米） | 0.5×0.4×0.3 m → CBM = 0.06 | 通过 |
| 单位切换 | cm 切到 m 后，CBM / Volume 按新单位重新计算 | 通过 |
| 校验：负数 | 保存负数时报中文/英文错误并带出具体值 | 通过 |
| 校验：净重 > 毛重 | 保存时报中文/英文错误 | 通过 |
| 列表可选列 | 产品列表可选显示「纸箱」「CBM」列 | 通过 |
| 中英双语 | 英文界面为英文，切换简体中文后字段标签、报错、单位为中文 | 通过 |
| 应用列表中文名（19.0.1.1.3） | 中文环境「应用」搜 `product_packing`，卡片标题显示「产品装箱」，摘要与详情描述为中文，左侧分类显示「库存 / 产品」；英文环境仍为英文 | 通过 |

## 交付记录（T-009）

### 任务目标

为产品 Inventory 标签页增加外贸必备数据字段，包括：

- 产品自身尺寸：Dimension Unit（cm / m）与长 / 宽 / 高，并自动同步原生 `Volume`。
- 纸箱与包装信息：装箱数、纸箱长 / 宽 / 高、尺寸单位、毛重、净重，以及根据尺寸自动计算的 CBM。

所有字段需与现有库存信息整合显示、可输入、可保存，不另开标签页；CBM 单位固定为立方米，尺寸单位可按产品配置。

### 实现方案

| 模块 | 关键实现 | 说明 |
|------|----------|------|
| `models/product_template.py` | 扩展 `product.template` | 新增产品尺寸字段、纸箱字段、计算字段与校验 |
| `models/product_template.py` | `_compute_carton_cbm` | 按 cm / m 自动换算为立方米 |
| `models/product_template.py` | `_compute_volume_from_dimensions` + `onchange` / `create` / `write` | 表单与后台同步更新原生 `volume` |
| `models/product_template.py` | `_check_carton_values` | 非负校验与净重 ≤ 毛重校验 |
| `views/product_template_views.xml` | 继承原生 `product_template_form_view` | 在 Logistics 组内 `Volume` 之前插入产品尺寸；之后新增「Carton & Packing」组 |
| `views/product_template_views.xml` | 继承 `product_template_tree_view` | 列表增加「Carton」「CBM」可选列 |
| `i18n/zh_CN.po` | 完整中英翻译 | 字段标签、help、selection、视图术语、报错信息 |

### 关键代码改动

- 新增产品尺寸字段并设置独立标签，避免与纸箱字段标签重复：

```python
# product_packing/models/product_template.py
product_dimension_unit = fields.Selection(
    string="Product Dimension Unit",
    selection=[("cm", "Centimeters"), ("m", "Meters")],
    default="cm",
    required=True,
)
product_length = fields.Float(string="Product Length", ...)
product_width  = fields.Float(string="Product Width",  ...)
product_height = fields.Float(string="Product Height", ...)
```

- 产品尺寸变化时始终同步 `volume`：

```python
@api.onchange("product_length", "product_width", "product_height", "product_dimension_unit")
def _onchange_product_dimensions(self):
    self._compute_volume_from_dimensions()

def create(self, vals_list):
    records = super().create(vals_list)
    # 若 vals 包含尺寸字段，则为每条记录重算 volume
    ...

def write(self, vals):
    res = super().write(vals)
    # 若 vals 包含尺寸字段，则为受影响记录重算 volume
    ...
```

- CBM 自动计算（store=True）：

```python
@api.depends("carton_length", "carton_width", "carton_height", "carton_dimension_unit")
def _compute_carton_cbm(self):
    for tmpl in self:
        length, width, height = ...
        if not (length > 0 and width > 0 and height > 0):
            tmpl.carton_cbm = 0.0
            continue
        factor = 1_000_000.0 if tmpl.carton_dimension_unit == "cm" else 1.0
        tmpl.carton_cbm = length * width * height / factor
```

### 测试结果

- 模块安装：成功，启动无 WARNING。
- 产品尺寸：输入 50 / 40 / 30 cm → `Volume` = 0.06 m³；切换单位为 m 后 `Volume` = 0.06 m³ 保持不变。
- 纸箱 CBM：输入 50 / 40 / 30 cm → `CBM` = 0.060000；输入 0.5 / 0.4 / 0.3 m → 同样 0.060000。
- 校验：负数保存被阻止，净重 > 毛重保存被阻止，报错中英文正常。
- 中文界面：字段标签、报错、单位文本全部翻译为中文。

### 遗留问题

- 无。T-009 全部验收项已通过。

### 后续计划

1. 可扩展支持更多尺寸单位（如 `inch`），只需扩展 selection 并更新换算因子。
2. 可考虑在产品报表 / 导出模板中增加 CBM、纸箱规格列，供物流报价使用。
3. 若业务需要，可额外增加「单件净重 / 单件毛重」或「每托盘装箱数」字段。

---

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
