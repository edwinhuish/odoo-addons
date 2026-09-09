# 变更日志

> 倒序排列，最新版本在最前。每版本固定三段式：变更 / 影响 / 文档。
> 版本号规则见根 `AGENTS.md` 第 3 节：架构/破坏性 +x，功能新增 +y，修复 / 文档 +z。

---

## [19.0.1.1.3] - 2026-09-09（验收通过）

### 变更（i18n / 文档）

- **应用列表（Apps）中文化**：`i18n/zh_CN.po` 补充「应用列表元数据」译文，中文环境下应用卡片与详情页显示中文模块名 / 摘要 / 描述。
  - `model:ir.module.module,shortdesc:base.module_product_packing` → 「产品装箱」
  - `model:ir.module.module,summary:base.module_product_packing`：摘要整句译文
  - `model:ir.module.module,description:base.module_product_packing`：`description` 整段译文（`translate=True` 整值翻译，`msgid` 与 `textwrap.dedent(manifest["description"])` 逐字符一致）
  - `model:ir.module.category,name:base.module_category_inventory_product` → 「产品」（`Inventory/Product` 的自定义子分类，官方 `base` 无译文）
- 修复 `i18n/zh_CN.po` 中 `Dimension Unit` 的**重复 `msgid`**（19.0.1.1.2 遗留）：字段标签与视图术语两条合并为一条多引用条目，符合根 `AGENTS.md` 4.4「同一 `msgid` 只能有一条」。

### 影响

- 纯译文改动，无模型 / 字段 / 视图 / 权限变更，**无需迁移脚本**。
- `odoo -d <db> -u product_packing --stop-after-init` 升级后，中文环境「应用」列表显示中文名称 / 摘要 / 描述与中文分类；英文环境不变。
- 这些记录归属 `base`（xmlid `base.module_*` / `base.module_category_*`、`noupdate=True`）：po 导入只补齐缺失语种，**不覆盖库中已有的 `zh_CN` 值**；后续改译文的强制刷新方式见根 `AGENTS.md` 4.8。

### 文档

- 同步 `__manifest__.py`（版本 19.0.1.1.3）、`README.md`（国际化节）、`AGENTS.md`（当前版本 + i18n 约束）、根 `README.md` / `AGENTS.md` / `TODO.md`。
- 规范沉淀：根 `AGENTS.md` 新增 4.8「应用列表元数据（模块名 / 摘要 / 描述 / 分类）翻译规范」，并更正 4.1 中「写在自研模块 po 里匹配不到、无效果」的错误说法。

### 验收记录（T-013）

- 验收日期：2026-09-09
- 验收环境：目标 Odoo 19 部署环境（已安装「简体中文 (zh_CN)」）
- 验收结果：6 项验收标准全部通过（中英文各验一遍）
  - [x] `odoo -d <db> -u product_packing --stop-after-init` 升级无报错
  - [x] 中文「应用」列表：卡片标题显示「产品装箱」，摘要为中文
  - [x] 中文「应用」详情：描述整段为中文
  - [x] 中文「应用」左侧分类：显示「库存 / 产品」——父级 `Inventory` 沿用官方译文，自定义段 `Product` → 「产品」由本模块提供
  - [x] 切回英文界面：名称 / 摘要 / 描述回到 `__manifest__.py` 的英文原文
  - [x] 仓库内自校验通过：无重复 `msgid`（顺带修掉 `Dimension Unit` 的重复条目）；`shortdesc` / `summary` / `description` 的 `msgid` 与 manifest 逐字符一致；源码无残留中文界面文本（脚本见根 `AGENTS.md` 4.6）

> 后续若只改译文（`msgstr`），这些记录是 `noupdate=True`，`-u` 不会覆盖库里已有的 `zh_CN`，
> 需按根 `AGENTS.md` 4.8 第 9 条用 `TranslationImporter.save(force_overwrite=True)` 或先清 `zh_CN` key 再升级。

---

## [19.0.1.1.2] - 2026-09-08（已验证）

### 变更

- 修复 Odoo 启动时 `ir.model` 的字段标签重复 WARNING：
  - 为产品自身尺寸字段 `product_dimension_unit` / `product_length` / `product_width` / `product_height`
    设置唯一字段标签（`Product Dimension Unit` / `Product Length` / `Product Width` / `Product Height`）
  - 纸箱尺寸字段保持原标签不变；视图中的 `<label>` 仍显示「Dimension Unit / Dimensions」，用户界面不变
- 同步拆分 `i18n/zh_CN.po` 中产品尺寸与纸箱尺寸的字段描述翻译条目
- 补充 `i18n/zh_CN.po` 中视图术语 `Dimension Unit` 的简体中文翻译，使产品表单中的「尺寸单位」标签在中文环境下正确显示

### 影响

- 无数据库结构变更、无业务逻辑变更，无需迁移脚本
- 视图/导出/高级搜索中产品尺寸字段的显示名从「Dimension Unit / Length / Width / Height」
  变为「Product Dimension Unit / Product Length / Product Width / Product Height」，纸箱字段不变
- `19.0.1.1.2` 直接替代 `19.0.1.1.1`

### 文档

- 同步更新 `__manifest__.py` 版本至 `19.0.1.1.2`
- 同步更新 `AGENTS.md` 当前版本，新增 T-009 开发复盘与关键经验
- 同步更新 `README.md`：修正 Volume 联动描述、补充完整 T-009 交付记录（目标 / 方案 / 关键代码 / 测试结果 / 后续计划）
- 同步更新 `CHANGELOG.md`，新增「交付记录（T-009）」
- 同步更新根目录 `README.md` / `AGENTS.md` / `TODO.md` 版本号与模块状态

---

## [19.0.1.1.1] - 2026-09-07（待验证）

### 变更

- 调整产品尺寸与原生 `volume` 的联动逻辑：
  - 由「仅当 `volume == 0` 时自动填充」改为「只要产品尺寸变化，就自动重算并更新 `volume`」
  - 增加 `create` / `write` 覆盖，保证通过导入、API 或表单保存时 `volume` 都能同步更新
  - 保留 `@api.onchange`，表单端实时可见
- 新增 `_compute_volume_from_dimensions` 辅助方法，统一厘米 / 米到立方米的换算逻辑
- 视图布局调整：把 `Dimension Unit` 与 `Dimensions` 放在原生 `Volume` 之前，更符合「先输入尺寸再得到体积」的操作习惯

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

## 交付记录（T-009）

- **需求**：为产品 Inventory 标签页增加产品自身尺寸（自动同步原生 Volume）与外贸纸箱字段（装箱数、长宽高、毛重、净重、自动 CBM），尺寸单位厘米 / 米可配置。
- **落地版本**：`19.0.1.1.2`
- **验收日期**：2026-09-08
- **验收结果**：全部通过
  - 安装无报错，启动无 `ir.model` 标签重复 WARNING。
  - 产品尺寸字段位于 Logistics 组 `Volume` 之前，输入后实时同步 `Volume`。
  - 纸箱字段位于 Logistics 组之后的「纸箱与包装」组，CBM 随尺寸自动重算。
  - 负数、净重大于毛重等非法保存被阻止，报错支持中英双语。
  - 列表视图可选显示「纸箱」「CBM」列。
  - 中文界面字段标签、报错、单位均正确翻译。
- **实现要点**：见 `README.md` →「交付记录（T-009）」。
- **遗留问题**：无。
- **后续计划**：可扩展英寸单位、增加单件重量字段、在报表/导出模板中加入 CBM 与纸箱规格。

---
