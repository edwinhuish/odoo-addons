# 产品多参考号

Odoo 19 产品模块扩展，用于在外贸 SOHO 场景下为一个产品挂载多个参考号，并支持按任一参考号搜索到对应产品。

> 模块原名 `product_model`（`19.0.2.0.0` 起改名 `product_reference`），模型原名 `product.model.code`；
> 命名与 Odoo 原生「内部参考（Internal Reference）」保持一致，源码与界面文案统一用 `reference`。

---

## 功能概述

- 一个产品可挂多个参考号（客户参考号 / 工厂参考号 / 别名）
- 原生 Odoo `default_code`（Reference）输入框直接放在产品名下方（产品模板表单与产品变体表单都有），
  标签为 `Ref.`（中英界面一致）；输入框内右端「+」按钮以弹窗管理额外参考号
- 产品存在额外参考号时显示「+N」徽标，悬停徽标弹出参考号清单 tooltip
- **多变体产品的参考号不共用**：产品表单在 `product_variant_count > 1` 时整块隐藏该区域，
  每个变体各自维护一份参考号（变体专属行，与产品级共享行相互独立）
- 参考号用独立明细模型 + `One2many` 挂在 `product.template` 上
- 同一产品内参考号不可重复；不同产品间允许同参考号，重复时命中提示区分
- 搜索能力在数据库层实现：冗余可存储字段 `reference_code_index`（产品级）与
  `variant_reference_code_index`（变体级），均配 trigram 索引
- 产品列表搜索框、Many2one 下拉、搜索建议、快速搜索均可按参考号命中；
  产品级搜索同时覆盖其各变体的参考号（在变体里加的参考号，在 Products 里也能搜到）
- 命中参考号时，列表结果显示「产品名（命中参考号：xxx）」便于区分
- 参考号行支持增删改排序，支持在列表内直接批量录入

---

## 核心设计

| 设计点 | 说明 |
|--------|------|
| 原生 Reference 就在产品名下方 | 产品模板表单与产品变体表单的标题区（`oe_title`）内、产品名下方直接放置 Odoo 原生 `default_code`；标签固定 `Ref.`（中英界面一致，不做本地化翻译），复用原生 `CharField`，无需切页签 |
| 输入框内「+」管理额外参考号 | 「+」内置在输入框右端，点击打开管理弹窗，列表式增删改排序/停用；改动挂在产品表单 record 上，点产品「保存」才入库 |
| 徽标 + 原生 tooltip | 存在启用中的额外参考号时显示「+N」徽标，悬停弹出清单（Odoo 原生 `data-tooltip-template` + `data-tooltip-info`）；只读态同样保留 tooltip |
| 多变体不共用 | 参考号行有两种归属（二选一）：产品级共享（`product_tmpl_id`，产品表单维护）、变体级（`product_id`，变体表单维护）；多变体产品的产品表单整块隐藏该区域 |
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

### `product.product`（扩展，变体）

| 字段 | 类型 | 说明 |
|------|------|------|
| `variant_reference_code_line_ids` | `One2many` → `product.reference.code` | 本变体专属的参考号明细（与产品级共享行独立） |
| `variant_reference_code_index` | `Text`（store + trigram 索引） | 本变体参考号拼接的搜索索引，自动维护，勿手工编辑 |

### `product.reference.code`（新建）

| 字段 | 类型 | 说明 |
|------|------|------|
| `reference_code` | `Char`（required, index） | 参考号，同一主人（产品 / 变体）内不可重复 |
| `reference_type` | `Selection` | 客户参考号 / 工厂参考号 / 别名 |
| `sequence` | `Integer` | 排序，数值小的在前 |
| `active` | `Boolean` | 启用状态，可停用而不删除 |
| `note` | `Char` | 备注（对应客户、版本、生效日期等） |
| `product_tmpl_id` | `Many2one` → `product.template`（index, cascade） | 所属产品（共享参考号），与 `product_id` 二选一 |
| `product_id` | `Many2one` → `product.product`（index, cascade） | 所属产品变体（变体专属参考号），与 `product_tmpl_id` 二选一 |

---

## 视图

- **产品表单（模板 + 变体）**：产品名称下方直接放置原生 `default_code`（Reference）输入框，
  输入框内右端「+」打开额外参考号管理弹窗；不再新增任何页签，常规信息页 / Codes 组的原生
  Reference 隐藏避免重复；**多变体产品（`product_variant_count > 1`）整块隐藏**
- **变体表单维护变体专属行**：`options="{'lines_field': 'variant_reference_code_line_ids'}"`
  指定本表单维护的是变体自己的参考号，与产品表单的共享行互不干扰
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
- 前端术语（JS `_t`、QWeb 模板文本与 `title` / `aria-label` / `placeholder` 属性）走 `.po` 的
  `code:addons/product_reference/static/src/js/*.js:0` 与
  `code:addons/product_reference/static/src/xml/*.xml:0` 条目；升级后需强刷浏览器才生效。
- 改动流程：改英文源文本 → 在 `i18n/zh_CN.po` 补 `msgid` / `msgstr` → `odoo -d <db> -u product_reference --stop-after-init` 升级 → 刷新页面。
- 启用中文：设置 → 语言 → 安装「简体中文 (zh_CN)」。

---

## 依赖

- `product`（产品模块，最小化依赖，不依赖 `sale`）

---

## 安装与使用

1. 将 `product_reference` 目录放入 Odoo 19 的 `addons_path`（**替换**旧的 `product_model` 目录）
2. 更新应用列表后升级 / 安装模块：`产品多参考号`
3. 打开任意产品表单（或产品变体表单），在产品名下方直接编辑 Odoo `Reference`
4. 点击 Reference 输入框内右端的「+」，在弹窗里新增 / 修改 / 停用 / 删除 / 上下移动额外参考号，
   关闭弹窗后点产品「保存」一次性提交（未保存的新产品也能先录入）
5. 产品存在额外参考号时，输入框右侧出现「+N」徽标，鼠标悬停徽标即可查看参考号清单
6. 在产品列表搜索框输入参考号，或销售订单行选产品时输入参考号，均可命中对应产品
7. **多变体产品**：产品表单不再显示该区域；打开具体变体（产品变体列表，或模板上的「变体」按钮），
   在该变体的产品名下方维护它自己的参考号——变体之间的参考号互不共用

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

### 原生 Reference 在产品名下方编辑

- 产品表单与产品变体表单的标题区、产品名下方直接放置 Odoo 原生的 `default_code` 字段，标签 `Ref.`。
- 标签 `Ref.` 中英界面一致（`i18n/zh_CN.po` 中该条 `msgstr` 同样为 `Ref.`），不随语言变化。
- 它就是 Odoo 原生的内部参考字段：产品模板表单改的是模板级 `default_code`，变体表单改的是该变体
  自己的 `default_code`；多变体产品的产品表单不显示这一块（`product_variant_count > 1` 时隐藏），
  参考号在各变体上分别维护。
- 它不属于 `product.reference.code` 明细行，因此不占用参考号行的唯一约束，也不参与参考号行的排序。
- 常规信息页 / Codes 组里的原生 Reference 已隐藏，避免与标题区重复。

### 用「+」弹窗管理额外参考号

- 参考号 / 类型 / 启用 / 备注直接在弹窗行内改；右侧箭头调整顺序，垃圾桶删除行。
- 弹窗内的改动都作用在产品表单 record 上，**点产品「保存」才入库**；不保存则不落库，
  新建产品可以先录参考号再一起保存。
- 弹窗内不做去重校验，保存时由服务端 `@api.constrains` + `UNIQUE(product_tmpl_id, reference_code)` 兜底。

---

## 验证清单

> 目标环境已验证通过（2026-09-08，落地版本 `19.0.2.5.0`，T-011；
> `19.0.2.0.0` 完成 `product_model` → `product_reference` 改名与数据迁移，T-007；
> `19.0.2.2.0` 完成参考号页顶部原生 `Reference` 统一编辑，T-008）。
> 完整验收记录见 `CHANGELOG.md` →「验收记录（T-011）」/「交付记录（T-011）」。

| 验证项 | 期望 | 结果 |
|--------|------|------|
| 升级 | `odoo -d <db> -u product_reference --stop-after-init` 不报错（升级后强刷浏览器） | 通过 |
| 产品模板表单 | 产品名下方出现 `Ref.` 标签 + Reference 输入框，可编辑并保存；常规信息页不再重复出现 Reference | 通过 |
| 变体主表单 / 变体独立编辑表单 | 同样出现编辑器；常规信息 / Codes 组不再重复出现 Reference | 通过 |
| 输入框内「+」管理弹窗 | 新增 / 改值 / 改类型 / 停用 / 删除 / 上移下移均正常，关闭后徽标数量正确 | 通过 |
| 标签 `Ref.` | 中英界面输入框前都显示 `Ref.`（不随语言变化） | 通过 |
| 新建未保存产品 | 先加参考号再保存产品，保存后参考号落库且索引已同步 | 通过 |
| 徽标 tooltip | 悬停「+N」徽标显示参考号清单（中英双语各验一遍） | 通过 |
| 只读态 | 只显示 Reference 文本与徽标 tooltip，无输入框与「+」 | 通过 |
| 多变体不共用 | 多变体产品的产品表单整块隐藏；变体 A 加的参考号不出现在变体 B | 通过 |
| 变体新增行 | 变体表单新增参考号行不报「不能同时归属产品与变体」 | 通过 |
| 变体搜索 | 订单行选产品输入变体参考号 / 产品共享参考号都能命中；变体列表命中时 name 附加提示 | 通过 |
| 变体参考号在产品列表可搜 | 在变体里加的参考号，Products 搜索框 / 独立「参考号」搜索项 / Many2one 都能命中并附加提示 | 通过 |
| 删除变体 / 产品 | 对应参考号行级联清理，索引按剩余行重算 | 通过 |
| 回归 | 按参考号搜索与命中提示、同产品（变体）去重、删除产品级联清理均正常 | 通过 |
| 中英双语 | 英文界面 `Ref.` / `Reference` 系列文案，中文界面「参考号」系列文案 | 通过 |
| 索引与约束 | `product_template__reference_code_index_index`、`product_product__variant_reference_code_index_index`（trigram）与两条 `UNIQUE` 存在 | 通过 |

### 历史验收项（`19.0.2.2.0` 及更早，页签时代，仅供参考）

| 验证项 | 期望 | 结果 |
|--------|------|------|
| 升级后模块名 | 应用列表显示 `产品多参考号`（`product_reference`），无 `product_model` 残留 | 通过 |
| 历史数据 | 旧型号数据完整出现在产品「参考号」页与 `product_reference_code` 表 | 通过 |
| 产品表单参考号页 | 页顶可编辑 Odoo `Reference`；下方可增删改排序其他参考号行 | 通过 |
| Reference 统一编辑 | 在「参考号」页修改页顶 `Reference`，「常规信息」页同步变化，反之亦然 | 通过 |
| 同产品重复参考号 | 阻止并给提示，带出具体值与产品名 | 通过 |
| 产品列表搜索框输入参考号 | 命中对应产品，`name` 显示「产品名（命中参考号：xxx）」 | 通过 |
| 销售订单行选产品输入参考号 | 命中对应产品 | 通过 |
| 删除参考号行 | 不报错，列表 `reference_code_index` 按剩余行重算 | 通过 |
| 删除产品 | 参考号行随之级联清理 | 通过 |

### 执行流程

1. 备份数据库
2. 从 `product_model` 升级的库先执行改名 SQL（全新安装跳过，见「从 product_model 升级」）
3. `odoo -d <db> -u product_reference --stop-after-init`
4. 强刷浏览器（前端资源与译文有缓存），按上表逐项验证

### 异常情况与处理

- 历史产品无参考号：`reference_code_index` 为空，搜索框输入参考号不命中（预期行为）
- 同产品重复参考号：`@api.constrains` 阻止 + DB `UNIQUE` 兜底
- 不同产品同参考号：允许，列表 `name` 附加「命中参考号：xxx」区分
- 索引与参考号行不一致：shell 执行 `env['product.template'].search([])._sync_reference_index()`，
  变体侧执行 `env['product.product'].search([])._sync_variant_reference_index()`
- 变体里加的参考号在产品列表搜不到：先按上一条重算变体索引，再确认产品搜索视图的
  `filter_domain` 含 `product_variant_ids.variant_reference_code_index`（`19.0.2.5.0` 已修）
- 变体表单新增参考号行报「不能同时归属产品与变体」：子行被填进了 `product_tmpl_id`；
  正常入口由 `product.product.create/write` 自动剥离，自定义代码直接建子行时需自行置空
- 标题区编辑器 / 徽标不显示：前端资源未升级或浏览器未强刷（`-u` 后必须强刷）
- 弹窗里加的参考号保存后不见了：弹窗改动挂在表单 record 上，必须再点一次产品「保存」才入库
- 升级报「column model_code does not exist」类错误：说明改名 SQL 未生效或迁移未跑到，
  回滚备份后按「从 product_model 升级」重做

### 后续维护

- 改拼接分隔符只改 `_sync_reference_index`，改后触发一次同步
- 新增参考号类型只改 `reference_type` 的 `selection`
- 其他单据 Many2one 指向 `product.template` 即自动支持参考号搜索，无需额外改动
- 改产品名下方编辑器的交互：改 `static/src/js/product_reference_editor.js` 与
  `static/src/xml/product_reference_editor.xml`；改管理弹窗：改
  `static/src/js/product_reference_manage.js` 与 `static/src/xml/product_reference_manage.xml`
- 视图挂载点：产品模板表单（继承 `product.product_template_form_view`）、
  变体主表单（`product.product_normal_form_view`）、变体独立编辑表单
  （`product.product_variant_easy_edit_view`）——新增表单入口时需同步：挂 widget
  （变体用 `options="{'lines_field': 'variant_reference_code_line_ids'}"`）、
  声明不可见的参考号 One2many、隐藏该表单里重复的原生 Reference
- 改参考号归属 / 新增一类主人（如按公司维度）：先改 `product.reference.code` 的
  `_check_single_owner` 与两条 `UNIQUE`，再补对应主人的冗余索引字段与 `_search_display_name`
- 标签 `Ref.` 中英一致：不要给 `i18n/zh_CN.po` 里的 `Ref.` 换成中文译文
- 验收回归点（改完必跑）：多变体场景（产品表单整块隐藏 + 变体各自一份）、
  搜索覆盖（产品能搜到变体参考号、变体能搜到产品共享参考号）、
  删除产品 / 变体后参考号行级联清理与索引重算

---

## 许可证

LGPL-3
