# 变更日志

> 倒序排列，最新版本在最前。每版本固定三段式：变更 / 影响 / 文档。
> 版本号规则见根 `AGENTS.md` 第 3 节：架构/破坏性 +x，功能新增 +y，修复 / 文档 +z。

---

## [19.0.1.1.1] - 2026-09-07（待验证）

### 变更

- 调整产品尺寸与原生 `volume` 的联动逻辑：
  - 由「仅当 `volume == 0` 时自动填充」改为「只要产品尺寸变化，就自动重算并更新 `volume`」
  - 增加 `create` / `write` 覆盖，保证通过导入、API 或表单保存时 `volume` 都能同步更新
  - 保留 `@api.onchange`，表单端实时可见
- 新增 `_compute_volume_from_dimensions` 辅助方法，统一厘米 / 米到立方米的换算逻辑

### 影响

- 仍为纯 `product.template` 扩展，无数据库结构变更，无需迁移脚本
- 用户手工录入的 `volume` 会被产品尺寸覆盖；后续如需独立维护体积，需先将尺寸清空或单独扩展开关
- 19.0.1.1.1 直接替代 19.0.1.1.0，无需先验证旧逻辑

### 文档

- 同步更新 `__manifest__.py` 版本至 `19.0.1.1.1`
- 同步更新 `README.md` 操作要点与验证清单
- 同步更新 `AGENTS.md` L1 约束
- 同步更新根目录 `README.md` / `AGENTS.md` / `TODO.md` 版本与验收标准

---

## [19.0.1.1.0] - 2026-09-07（待验证）

### 变更

- 在产品表单的 Logistics 组中新增产品自身尺寸字段：
  - `product_dimension_unit`：产品尺寸单位（厘米 / 米）
  - `product_length` / `product_width` / `product_height`：产品长宽高
- 新增 `@api.onchange`：当原生 `volume` 字段为 0 且输入了有效长宽高时，自动按所选单位计算并填充 `volume`
- 视图继承原生 Logistics 组，将 Dimension Unit 与 Dimensions 放在 Volume 下方，保持与 Odoo 原生字段一致的显隐规则
- 更新 `i18n/zh_CN.po`，覆盖新增字段标签 / help / selection / 视图术语

### 影响

- 仍为纯 `product.template` 扩展，无新建模型，无数据库结构变更，无需迁移脚本
- 原生 `volume` 字段仅在当前值为 0 时被自动填充；已有非 0 体积不会被覆盖
- 19.0.1.0.0 与 19.0.1.1.0 可连续验证，无额外升级前置条件

### 文档

- 同步更新 `__manifest__.py` 版本至 `19.0.1.1.0`
- 同步更新 `README.md` 字段表、功能说明与验证清单
- 同步更新 `AGENTS.md` 当前版本与文件职责
- 同步更新根目录 `README.md` / `AGENTS.md` 模块一览表版本

---

## [19.0.1.0.0] - 2026-09-07（待验证）

### 变更

- 初始版本，新增 `product_packing` 模块
- 扩展 `product.template`，新增外贸常用纸箱字段：
  - `carton_qty_per_carton`：每个纸箱可装产品数
  - `carton_dimension_unit`：尺寸单位（厘米 / 米）
  - `carton_length` / `carton_width` / `carton_height`：纸箱长宽高
  - `carton_gross_weight` / `carton_net_weight`：纸箱毛重 / 净重（千克）
  - `carton_cbm`：根据长宽高自动计算的纸箱立方米数（store=True）
  - `carton_dimension_spec`：可读尺寸文本，如 `50 x 40 x 30 cm`（store=True）
- 继承 `product.product_template_form_view`，在 Inventory 标签页 Logistics 组后新增「纸箱与包装」组，CBM 只读展示
- 继承 `product.product_template_tree_view`，新增「纸箱」「CBM」可选列
- 增加 `@api.constrains` 校验：装箱数 / 尺寸 / 重量非负，净重不超过毛重
- 新增 `i18n/zh_CN.po`，覆盖字段标签、help、selection、校验报错与视图术语

### 影响

- 仅在产品模板上新增字段与视图继承，不涉及已有模型改名或数据迁移，无需 `migrations` 脚本
- 现有产品升级后新增字段为空，CBM 与纸箱规格显示为 0 / 空，用户按需补录
- 依赖最小化：仅 `product`，不引入 `stock` / `sale` / `purchase`

### 文档

- 同步更新 `__manifest__.py`、`README.md`、`AGENTS.md`
- 同步更新根目录 `TODO.md` / `README.md` / `AGENTS.md`

---
