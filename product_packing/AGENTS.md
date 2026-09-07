# AGENTS 工作指引

> 本文档用于指导 AI 助手或新开发者在维护、扩展本 Odoo 模块时的行为规范和关键上下文。
> L1 约束段每次加载必读；L2 踩坑档案按主题触发条件加载。

---

## 模块定位

- 模块名：产品包装信息
- 技术目录：`product_packing`
- 新建模型：无，纯 `_inherit` 扩展
- 继承模型：`product.template`
- 自定义组件（前端模块）：无
- 主依赖：`product`（不依赖 `stock` / `sale` / `purchase`）
- 当前版本：`19.0.1.0.0`

---

## L1：不可破坏的核心约束

每次修改代码必须保证以下行为不变。每条只列约束与违反后果，实现细节见 L2 踩坑档案。

1. **仅扩展 `product.template`**
   - 不新建独立模型，所有纸箱字段挂在 `product.template` 上
   - 违反后果：破坏「开箱即用、无需额外权限配置」的轻量设计

2. **CBM 必须自动计算且只读展示**
   - `carton_cbm` 由 `carton_length` / `carton_width` / `carton_height` / `carton_dimension_unit` 计算，用户不可直接编辑
   - 违反后果：用户手动输入错误 CBM，导致后续报价 / 物流计算不一致

3. **尺寸单位可配置，CBM 单位固定为立方米**
   - `carton_dimension_unit` 是产品级选择（`cm` / `m`），但 `carton_cbm` 始终为立方米
   - 违反后果：跨产品 CBM 不可比，报表汇总出现数量级错误

4. **所有用户可见文本源语言为英文（`en_US`）**
   - Python / XML 中不写中文界面文案；中文只放在 `i18n/zh_CN.po` 的 `msgstr`
   - 违反后果：默认英文界面出现中文，切换语言后译文失效或重复 `msgid` 导致整份 po 解析失败

5. **校验信息必须带具体数值且可翻译**
   - 使用 `@api.constrains` + `ValidationError`，占位符用 `%(name)s`
   - 违反后果：用户看不懂报错位置；译者无法调整语序

---

## 国际化约束（i18n）

每处用户可见文本都必须满足（通用规则见根 `AGENTS.md` 第 4 节）：

1. **源语言是英文（`en_US`）**：Python / XML 里一律写英文；中文只能出现在 `i18n/zh_CN.po` 的 `msgstr` 里，禁止写回源码。
2. **可翻译入口正确**：见根 `AGENTS.md` 4.2「可翻译入口对照表」（`model:` / `model_terms:` / `code:` 三类键名）。
3. **禁止拼接句子**：占位符统一 `%(name)s`，禁止按位置 `%s` 或 JS `+` 拼接；模板里夹子元素的句子拆到 JS 侧 `_t()`。
4. **收尾动作**：改英文源文本 → 同步 `i18n/zh_CN.po` → 提升版本 → `-u` 升级 + 强刷浏览器，中英文各验一遍。
5. **代码注释保持中文**，不为 i18n 改英文。

---

## 文件职责

| 文件 | 职责 |
|------|------|
| `__manifest__.py` | 模块元数据、版本、依赖、数据文件登记 |
| `models/product_template.py` | 扩展 `product.template`，定义纸箱字段、CBM / 尺寸规格计算、数值校验 |
| `views/product_template_views.xml` | 继承产品表单与列表视图，集成 Inventory 标签页与列表可选列 |
| `i18n/zh_CN.po` | 简体中文译文（源语言 `en_US` 写在代码里，无需 `en_US.po`；`i18n/` 不进 `data`） |
| `README.md` | 用户可见功能、字段表、安装与使用步骤、验证清单 |
| `CHANGELOG.md` | 逐版本「变更 / 影响 / 文档」记录 |
| `AGENTS.md` | 本文件：核心约束、i18n 规则、文件职责、变更规范 |

---

## 常见扩展场景

### 新增纸箱相关字段

- 在 `models/product_template.py` 新增字段
- 在 `views/product_template_views.xml` 的 `group_carton_packing` 内放置字段
- 更新 `i18n/zh_CN.po`：字段标签 / help / 视图术语
- 更新 `README.md` 字段表与 `CHANGELOG.md`

### 修改 CBM 计算方式

- 只改 `_compute_carton_cbm`
- `carton_cbm` 为 `store=True` compute，升级后会自动为所有记录重算
- 若涉及新增依赖字段，同步更新 `@api.depends`

### 新增尺寸单位（如 inch）

- 扩展 `carton_dimension_unit` 的 `selection`
- 在 `_compute_carton_cbm` 中加入 inch → 立方米的换算因子
- 同步更新 `i18n/zh_CN.po` 的 selection 译文与 `README.md` 示例

---

## 调试建议

- CBM 不更新：检查 `@api.depends` 是否包含 `carton_dimension_unit`；`store=True` 字段在升级后会自动计算
- 报错信息未翻译：检查 `i18n/zh_CN.po` 中 `code:` 条目的 `msgid` 与源码 `_()` 文本是否一字不差
- 视图未生效：确认 `__manifest__.py` 的 `data` 中登记了视图文件，并执行了 `-u` 升级
- 校验未触发：`@api.constrains` 只在 create / write 时触发；批量导入时同样会触发

---

## 变更记录规范

每次功能修改后必须更新：
- `__manifest__.py` 的 `version`（遵循 `19.0.x.y.z`）
- `CHANGELOG.md` 的版本说明（变更 / 影响 / 文档）
- 本 `AGENTS.md` 的相关约束（若涉及行为变更）
- `README.md` 的功能说明（若涉及用户可见功能）

版本号建议：
- 破坏性变更或架构调整：升第二位，如 `19.0.2.0.0`
- 功能新增：升第三位，如 `19.0.1.1.0`
- 修复或文档：升第四位，如 `19.0.1.0.1`

---
