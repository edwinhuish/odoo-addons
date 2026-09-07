# 变更日志

> 倒序排列，最新版本在最前。每版本固定三段式：变更 / 影响 / 文档。
> 版本号规则见根 `AGENTS.md` 第 3 节：架构/破坏性 +x，功能新增 +y，修复 / 文档 +z。

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
