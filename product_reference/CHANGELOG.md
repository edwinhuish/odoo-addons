# 变更日志

## [19.0.2.5.0] - 2026-09-08（待验证）

### 变更（产品列表可按变体参考号搜索）

- **产品级搜索并入变体参考号**：`product.template._search_display_name` 在
  `reference_code_index` 之外并入 `product_variant_ids.variant_reference_code_index`
  （`any` 条件），产品列表 / Many2one 下拉 / 快速搜索输入任一变体的参考号都能找到该产品。
- **搜索视图同步**：顶部搜索框与独立「参考号」搜索项的 `filter_domain` 均加入变体参考号路径
  `('product_variant_ids.variant_reference_code_index', 'ilike', self)`。
- **命中提示覆盖变体参考号**：`_extract_reference_code_search_terms` 支持
  `('product_variant_ids', 'any', [...])` 子域与 `Domain` 对象递归；`web_search_read`
  命中判断同时比对产品拼串与其变体拼串（新增 `_variant_reference_indexes_by_template()`
  一次取回，避免逐记录查询）。
- 变体参考号仍**不**写回 `reference_code_index`（多变体产品参考号不共用），只是在搜索时纳入。

### 影响

- 在变体里新增的参考号，现在能在 Products 列表 / 选产品时按该参考号命中，
  命中时 `name` 同样附加「（命中参考号：xxx）」。
- 变体级搜索不变（本变体参考号 + 所属产品的共享参考号）。
- 仅需 `-u` 升级（无数据结构变更），升级后强刷浏览器。

### 待验证清单（目标环境）

1. `odoo -d <db> -u product_reference --stop-after-init` 升级不报错
2. 在多变体产品的某个变体里加 `ABC-123` → Products 搜索框输入 `ABC-123` 能搜到该产品
3. 搜索结果 `name` 附加「（命中参考号：ABC-123）」（中英各验一遍）
4. 独立「参考号」搜索项同样能命中变体参考号
5. 选产品（Many2one 指向 `product.template`）输入变体参考号能命中
6. 回归：产品共享参考号 / 名称 / barcode 搜索不受影响；否定条件（`not ilike`）不误伤

---

## [19.0.2.4.0] - 2026-09-08（待验证）

### 变更（多变体产品的参考号不共用）

- **参考号行新增变体归属**：`product.reference.code` 增加 `product_id`（产品变体），
  `product_tmpl_id` 改为非必填；新增 `_check_single_owner`（产品 / 变体二选一，不可双归属）
  与 `UNIQUE(product_id, reference_code)`；`_check_reference_code_unique_per_template`
  改为按主人去重的 `_check_reference_code_unique_per_owner`。
- **新增 `product.product` 扩展**（`models/product_product.py`）：`variant_reference_code_line_ids`
  （变体专属行）、`variant_reference_code_index`（trigram 索引）、`_sync_variant_reference_index()`；
  `_search_display_name` 并入变体参考号与其产品的共享参考号；`web_search_read` 命中变体参考号时
  同样在 `name` 后附加「（命中参考号：xxx）」。
- **widget 按主人分流**：产品模板表单 → `reference_code_line_ids`（共享行），
  变体表单 → `variant_reference_code_line_ids`（变体专属行，arch 用
  `options="{'lines_field': ...}"` 显式指定）。
- **多变体产品的模板表单整块隐藏**：Reference 区域 `invisible="product_variant_count > 1"`，
  参考号只在各变体上维护。
- **子行创建剥离模板默认**：`product.product.create/write` 对变体参考号行的 `(0, 0, ...)` 命令
  强制 `product_tmpl_id=False`，避免变体 action context 的 `default_product_tmpl_id`
  造成「同时归属产品与变体」报错（与 product_image 变体图库同一坑）。
- **i18n / 文档同步**。

### 影响

- 历史数据不受影响：已有的参考号行都只有 `product_tmpl_id`（产品级共享），`product_id` 为空，
  无需迁移脚本（新增列 + trigram 索引 + 唯一约束由 ORM 自动创建）。
- 多变体产品：产品表单不再显示 Reference 区域；每个变体各自维护一组参考号，互不共用。
- 单变体 / 无变体产品：产品表单维护共享行（原行为不变）；变体表单可另外维护变体专属行。
- 搜索：变体（Many2one 指向 `product.product`、变体列表）可按本变体参考号或其所属产品的共享
  参考号命中；产品级搜索仍只走 `reference_code_index`（不含变体专属参考号）。
- 升级后必须强刷浏览器。

### 待验证清单（目标环境）

1. `odoo -d <db> -u product_reference --stop-after-init` 升级不报错（新增列 / 索引 / 唯一约束自动创建）
2. 多变体产品：产品表单不显示 Reference 区域；打开某变体可维护自己的参考号
3. 变体 A 新增的参考号不会出现在变体 B（两套独立）
4. 单变体 / 无变体产品：产品表单维护共享行正常；变体表单维护变体行正常
5. 变体表单新增参考号行不报「不能同时归属产品与变体」
6. 搜索：订单行选产品（Many2one 指向变体）输入变体参考号 / 产品共享参考号都能命中
7. 变体列表按参考号搜索命中时 `name` 附加「（命中参考号：xxx）」
8. 删除变体 / 产品：对应参考号行级联清理，索引按剩余行重算

---

## [19.0.2.3.0] - 2026-09-08（待验证）

### 变更（界面改造：移除「参考号」页，Reference 上移到产品名称下方）

- **移除产品表单的「参考号（References）」页**：额外参考号不再以页签内 One2many 列表呈现，
  改为「产品名称下方 Reference 输入框 + 右侧「+」弹窗管理」，更贴近 SOHO「少点几下」的习惯。
- **原生 Reference 输入框移到产品名称下方**：产品模板表单与产品变体表单（变体主表单
  `product.product.form` 与变体独立编辑表单 `product_variant_easy_edit_view`）的 `oe_title` 内、
  产品名下方放置 Odoo 原生 `default_code`；输入框前标签固定为 `Ref.`
  （中文界面同样显示 `Ref.`，不做本地化翻译）；复用原生 `CharField` 组件渲染，
  编辑 / dirty / 校验体验与原生一致。
- **输入框内右端「+」按钮 → 额外参考号管理弹窗**：「+」内置在输入框右端（外层套原生 `.o_input`，
  嵌套 input 自动去边框），点击打开弹窗，列表式维护（参考号 / 类型 / 启用 / 备注 / 上移下移 / 删除），
  改动作用在产品表单 record 上，点产品「保存」才入库（未保存的新产品也能先录入参考号）；
  弹窗挂顶层 overlay（`main_components`），与表单渲染树解耦，不闪烁。
- **数量徽标 + tooltip**：产品存在启用中的额外参考号时显示「+N」徽标，悬停徽标弹出参考号清单
  （Odoo 原生 `data-tooltip-template` + `data-tooltip-info`）。
- **多变体模板**：模板级 Reference 由各变体维护，输入框位置显示提示文本，管理入口与徽标保留。
- **隐藏重复的原生 Reference**：常规信息页分类栏（模板 `product_template_only_form_view`、变体主表单
  `product_normal_form_view`）与变体独立编辑表单 Codes 组的原生 `default_code` 均隐藏。
- **新增前端资源**：`static/src/js/product_reference_editor.js`（字段 widget）、
  `static/src/js/product_reference_manage.js`（管理弹窗 + overlay 注册）、
  `static/src/xml/product_reference_editor.xml`、`static/src/xml/product_reference_manage.xml`、
  `static/src/scss/product_reference.scss`，走 `web.assets_backend`。
- **i18n**：新增弹窗 / tooltip / 徽标相关术语与 JS `_t` 文案；移除已删除页面的术语（`References`、
  `Reference Lines` 页内引用、页面提示段落）；`Product Reference` 合并为一条多引用条目。
- **文档同步**：`README.md`、`AGENTS.md`、根 `README.md` / `TODO.md`。

### 影响

- 产品表单不再有「参考号」页；历史数据不受影响（参考号行仍在 `product_reference_code` 表）。
- 额外参考号仍是**产品级**（挂在 `product.template` 上）；变体表单经 `_inherits` 委托读写同一组行，
  同一产品的多个变体共享同一份额外参考号。
- 弹窗内改动随产品表单「保存」提交：不保存则不入库；关闭弹窗不会回滚已在 record 上的改动。
- 只读态只显示 Reference 文本与徽标 tooltip，不再显示输入框与「+」按钮。
- 升级后必须强刷浏览器（前端资源有缓存）。

### 待验证清单（目标环境）

1. `odoo -d <db> -u product_reference --stop-after-init` 升级不报错
2. 产品模板表单：产品名下方可见 `Ref.` 标签与 Reference 输入框，可编辑并保存；常规信息页不再重复出现
3. 输入框内右端「+」打开管理弹窗：新增 / 改值 / 改类型 / 停用 / 删除 / 上移下移均正常，关闭后徽标数量正确
4. 未保存的新产品：先加参考号再保存产品，保存后参考号落库且 `reference_code_index` 已同步
5. 变体主表单与变体独立编辑表单：同样出现编辑器；常规信息 / Codes 组不再重复出现 Reference
6. 徽标悬停显示参考号清单 tooltip（中英双语各验一遍）
7. 标签：中英界面输入框前都显示 `Ref.`（不随语言变化）
8. 只读态：只显示 Reference 文本与徽标 tooltip
9. 多变体模板：显示「按变体维护」提示，管理入口可用
10. 回归：列表搜索框 / Many2one 下拉按参考号仍能命中并显示「（命中参考号：xxx）」；
   同产品重复参考号仍被阻止；删除产品级联清理

---

## [19.0.2.2.0] - 2026-09-07（验收通过）

### 变更（功能回退与简化）

- **不在参考号表中存储 Odoo Reference**：移除 `19.0.2.1.0` 引入的
  `product.reference.code.is_internal` 字段、`("internal", "Internal Reference")`
  selection 值以及所有双向同步逻辑（`_sync_internal_reference_line`、
  `product.template.create/write` 重写、`product.product.write` 钩子、内部行保护）。
- **前端直接显示原生 `default_code`**：在产品表单「参考号（References）」页顶部放置
  Odoo 原生 `default_code` 字段（标签 `Reference`），用户可在该页直接查看和修改，
  与「常规信息」页共享同一个字段，无需维护同步。
- **参考号明细行恢复纯扩展角色**：`product.reference.code` 只保存 customer / factory /
  alias 等额外参考号；`_order` 恢复为 `sequence, product_tmpl_id, id`。
- **清理历史内部行**：新增 `migrations/19.0.2.2.0/pre-migration.py`，在 ORM 删除
  `is_internal` 列前，先删除 `19.0.2.1.0` 遗留的 `is_internal = TRUE` 或
  `reference_type = 'internal'` 行（如该版本未部署则无影响）。
- **i18n 清理**：移除 `Internal` / `Internal Reference` / `Other References` 及内部行
  不可删除提示；恢复 `reference_type` help、active help、sequence help、页面提示等
  到 `19.0.2.0.0` 状态。
- **文档同步**：更新 `README.md`、`AGENTS.md`。

### 影响

- `default_code` 仍是 Odoo 原生字段，不进入 `product_reference_code` 表；
  修改它不会在参考号行列表中生成/删除任何记录。
- 已升级到 `19.0.2.1.0` 并产生内部参考行的库，再次升级到 `19.0.2.2.0` 时
  pre-migration 会自动清理这些行；请确保升级前已备份。
- 如果 `19.0.2.1.0` 从未部署，此版本升级与 `19.0.2.0.0` → `19.0.2.2.0` 等价，
  仅新增参考号页顶部的 `default_code` 字段。

### 验收记录（T-008）

- 验收日期：2026-09-07
- 验收环境：目标 Odoo 19 部署环境
- 验收结果：六项验收标准全部通过
  - [x] 「参考号」页顶部可见 `Reference` 字段，可查看和编辑
  - [x] 在「参考号」页修改 `Reference` 保存后，「常规信息」页同步变化
  - [x] 在「常规信息」页修改 `Reference` 保存后，「参考号」页同步变化
  - [x] `Reference` 为空时，参考号行列表不受影响，不会自动生成任何内部行
  - [x] 普通参考号行可正常增删改排序；同产品重复参考号仍被阻止
  - [x] 从 `19.0.2.1.0` 升级后，旧的 `is_internal` / `reference_type='internal'` 行被清理

### 交付记录（T-007 / T-008，2026-09-07）

- **完成日期 / 落地版本**：2026-09-07，`19.0.2.2.0`。
- **T-007 需求**：模块改名 `product_model` → `product_reference`（模型 `product.model.code` → `product.reference.code`，字段 `model_code*` → `reference_code*`），文案 `model` → `reference` 与 Odoo 原生「内部参考」语义对齐，配套幂等迁移脚本。落地版本 `19.0.2.0.0`。
- **T-008 需求**：产品「参考号」页顶部直接显示 Odoo 原生 `Reference`（`default_code`）供统一编辑。落地版本 `19.0.2.2.0`。
- **验收记录**：目标库执行改名 SQL 后 `odoo -d <db> -u product_reference --stop-after-init` 升级不报错；旧型号数据完整保留；应用列表无 `product_model` 残留；列表 / Many2one 按参考号命中且命中提示中英双语正确；同产品重复参考号报错带出具体值；删除参考号行与删除产品均正常；索引与唯一约束存在；参考号页顶部 `Reference` 可编辑且与「常规信息」页同步。
- **异常与后续维护**：
  - 模块改名必须先执行 README 中的改名 SQL，否则 Odoo 会把 `product_reference` 当成新模块安装。
  - 若从 `19.0.2.1.0`（内部参考行版本）升级，`pre-migration` 会自动清理 `is_internal` 行，升级前务必备份。
- **遗留**：无。

---

## [19.0.2.1.0] - 2026-09-07（待验证）

### 变更（功能）

- **新增内部参考行**：`product.reference.code` 增加 `is_internal` 字段，用于把
  `product.template.default_code`（General Information 中的 `Reference`）镜像到
  「参考号」页的第一行。
- **参考号类型扩展**：`reference_type` selection 增加 `("internal", "Internal Reference")`，
  排在 customer/factory/alias 之前，方便界面展示。
- **排序规则调整**：`_order` 改为 `is_internal desc, sequence, product_tmpl_id, id`，
  确保内部参考行始终置顶。
- **双向同步**：
  - 修改 `product.template.default_code` → `product.template.write()` 调用
    `_sync_internal_reference_line()`，自动创建 / 更新 / 删除内部参考行。
  - 修改内部参考行的 `reference_code` → `product.reference.code.write()` 回写
    `product.template.default_code`。
  - 变体 `product.product.default_code` 被直接修改时，也通过 `product.product.write()`
    钩子同步到模板侧。
- **保护内部参考行**：`product.reference.code.unlink()` 对 `is_internal=True` 的行
  抛出 `ValidationError`（同步上下文 `reference_sync=True` 除外）。
- **视图调整**：
  - 产品「参考号」页 One2many 列表：隐藏 `is_internal`，内部参考行的
    `sequence` / `reference_type` / `active` / `note` 均设为 readonly。
  - 参考号独立列表 / 表单：显示 `is_internal`，相关字段 readonly。
  - 搜索视图增加「Internal」与「Other References」筛选。
  - 页面提示更新，说明第一行为 Odoo Reference 镜像且不可删除。
- **数据回填**：新增 `migrations/19.0.2.1.0/post-migration.py`，升级后为所有
  `default_code` 非空的产品自动补建内部参考行。
- **i18n 同步**：新增 `Internal` / `Internal Reference` / `Other References` 及
  不可删除提示的 `msgid` / `msgstr`；更新 `reference_type` help、active help、
  sequence help、页面提示等中文译文。

### 影响

- 首次保存产品时，若 `default_code` 已填写，会自动在「参考号」页出现一条
  Internal Reference 行。
- 内部参考行不可删除、不可归档、不可改类型；只能通过「常规信息」页的
  `Reference` 字段间接维护。
- 若普通参考号行与 `default_code` 同码，同步时会自动提升为内部参考行，避免
  `UNIQUE(product_tmpl_id, reference_code)` 冲突。
- 升级 `19.0.2.1.0` 时，post-migration 会对所有 `default_code` 非空的产品执行一次
  回填；数据量大的库请安排在低峰期升级。

### 文档

- 同步更新 `README.md`、`AGENTS.md`。

### 待验证

- 产品表单的 `Reference` 与「参考号」页第一行双向同步，清空 `Reference` 后内部行消失。
- 内部参考行始终排在第一，删除时弹出中文提示。
- 独立参考号视图可筛选 Internal / Other References。
- 旧数据升级后，`default_code` 非空的产品自动出现 Internal Reference 行。

---

## [19.0.2.0.0] - 2026-09-07（验收通过）

### 变更（破坏性：模块 / 模型 / 字段改名）

- **模块改名**：`product_model` → `product_reference`（目录、模块技术名、`author` 归属不变）。
- **模型改名**：`product.model.code` → `product.reference.code`（表 `product_model_code` → `product_reference_code`）。
- **字段改名**：
  - `product.reference.code`：`model_code` → `reference_code`、`model_type` → `reference_type`
  - `product.template`：`model_code_line_ids` → `reference_code_line_ids`、
    `model_code_count` → `reference_code_count`、`model_code_index` → `reference_code_index`
- **约束改名**：`_model_code_unique_per_template` → `_reference_code_unique_per_template`
  （DB 唯一约束 `UNIQUE(product_tmpl_id, reference_code)`，提示语同步改为
  `Reference codes must be unique within the same product.`）。
- **方法改名**：`_compute_model_code_count` → `_compute_reference_code_count`、
  `_check_model_code_unique_per_template` → `_check_reference_code_unique_per_template`、
  `_extract_model_code_search_terms` → `_extract_reference_code_search_terms`。
- **外部 ID 改名**：模型 / 字段 / 视图 / 动作 / 权限的 xmlid 全部同步
  （如 `action_product_model_code` → `action_product_reference_code`、
  `access_product_model_code_user` → `access_product_reference_code_user`）。
- **文案语义**：源码与视图里所有 `model`（型号）改为 `reference`（参考号），与 Odoo 原生
  「内部参考 Internal Reference」语义一致；`i18n/zh_CN.po` 的 `msgid` / `msgstr` 同步
  （英文 `Reference` ↔ 中文「参考号」，命中提示 ` (Matching reference: %(codes)s)` ↔「（命中参考号：%(codes)s）」）。
- **新增迁移**：`migrations/19.0.2.0.0/pre-migration.py`，负责模块名、模型、字段、表、序列、
  索引、唯一约束与 `ir_*` 元数据的改名；脚本幂等，只改名不删数据。
- **顺带修复**：`product.reference.code.unlink()` 原来对 `product.template` 调用不存在的
  `_sync_template_index()`（删除参考号行会 `AttributeError`）。拼接逻辑下沉到
  `product.template._sync_reference_index()`，明细模型只负责调用。

### 影响

- **必须先在目标库执行改名 SQL 再升级**，否则 Odoo 会把 `product_reference` 当成新模块安装，
  旧数据不会自动接上：

  ```sql
  UPDATE ir_module_module SET name = 'product_reference' WHERE name = 'product_model';
  UPDATE ir_model_data SET module = 'product_reference' WHERE module = 'product_model';
  UPDATE ir_model_data SET name = 'module_product_reference'
   WHERE module = 'base' AND name = 'module_product_model';
  ```

  然后 `odoo -d <db> -u product_reference --stop-after-init`。
- 旧目录 `product_model` 必须删除（否则应用列表会出现两个模块）。
- 自定义代码 / 报表 / 搜索域若引用了 `model_code_index`、`model_code` 等旧字段名，需同步改为新名。
- 界面文案随源语言改动：英文界面为 `Reference` 系列，中文界面为「参考号」系列。
- 旧译文由升级时重新导入的 `i18n/zh_CN.po` 覆盖（Odoo 19 已无 `ir_translation` 表，译文落在记录自身）。

### 文档

- 同步 `README.md`（改名说明 + 升级步骤 + 验证清单）、`AGENTS.md`（命名语义与迁移约束）、
  根 `README.md` / `AGENTS.md` / `TODO.md` / `DOCS_TEMPLATE.md` 中的模块名与示例。

### 待验证

- 目标库执行改名 SQL 后 `-u product_reference` 不报错，历史型号数据完整保留。
- 应用列表只剩 `product_reference`，无 `product_model` 残留；`product_reference_code` 表有数据。
- 列表搜索框 / Many2one 下拉按参考号仍能命中，命中提示中英双语正确。
- 删除参考号行不再报错；删除产品仍级联清理。
- `product_template__reference_code_index_index`（trigram）与
  `product_reference_code_reference_code_unique_per_template` 存在。

---

## [19.0.1.1.0] - 2026-09-06（待验证）

### 变更（功能）

- **国际化（i18n）**：源码用户可见文本全部改为英文（源语言 `en_US`），新增 `i18n/zh_CN.po` 提供简体中文翻译，支持中英双语、默认英文。
  - 模型：`_description`、字段 `string` / `help`、selection 标签（客户型号 / 工厂型号 / 别名）、数据库约束消息、`ValidationError` 提示。
  - 列表命中提示「（命中型号：xxx）」改为 `_(" (Matching model: %(codes)s)")`，由 `zh_CN.po` 提供中文，不再硬编码中文。
  - `_()` 调用改用命名占位符 `%(xxx)s`。
  - 视图 / 动作：列表 / 表单 / 搜索视图 `string`、型号页标题、占位提示、页面底部提示段落、`ir.actions.act_window` 名称与空视图帮助文案。

### 影响

- **默认展示语言变为英文**：`-u` 升级后，未启用中文的数据库全部显示英文文案。
- 需要中文的库：设置 → 语言安装「简体中文 (zh_CN)」，`odoo -d <db> -u product_model --stop-after-init` 升级并强刷浏览器。
- 列表搜索命中型号时，英文界面显示 `产品名 (Matching model: xxx)`，中文界面显示 `产品名（命中型号：xxx）`;该提示写入列表 `name`，仅用于展示，不落库。
- 代码注释仍为中文（不参与翻译）。

### 文档

- 同步 `__manifest__.py`（版本 19.0.1.1.0、name / summary / description 英文化）、`README.md`、`AGENTS.md`、根 `README.md`。

### 待验证

- 英文界面：产品表单「Models」页、型号字段标签 / help、去重报错均为英文。
- 中文界面：上述内容显示为中文；搜索型号命中时列表 `name` 后缀为「（命中型号：xxx）」。
- 语言切换后无需重启服务，刷新页面即可生效。

---

## [19.0.1.0.0] - 2026-09-02（验收通过）

### 验收记录

- 验收日期：2026-09-02
- 验收环境：目标 Odoo 19 部署环境
- 验收结果：五项验收标准全部通过
  - [x] 产品表单可增/删/改/排序型号行
  - [x] 产品列表搜索框输入型号可命中对应产品
  - [x] 销售订单行选产品（Many2one 搜索）输入型号可命中
  - [x] 型号批量录入（粘贴多行）可用
  - [x] 删除产品时型号行级联清理，无孤儿数据

### 执行流程

1. 首次安装：`odoo -d <db> -i product_model --stop-after-init`
   自动创建 `product.model.code` 表、`product.template.model_code_index` 列与 trigram 索引、加载 `ir.model.access.csv` 权限
2. 在产品表单「型号」页逐条新增型号行；保存后 `model_code_index` 自动同步
3. 验证搜索：在产品列表搜索框输入型号 → 命中对应产品，`name` 附加「（命中型号：xxx）」
4. 验证 Many2one：在销售订单行选产品处输入型号 → 命中对应产品
5. 验证去重：同产品录入重复型号 → 阻止并中文提示带出具体值与产品名
6. 验证级联：删除产品 → 确认 `product.model.code` 中对应行随之删除

### 异常情况与处理

- 历史产品无型号：`model_code_index` 为空，搜索框输入型号不命中（预期行为，不影响原生按 name/default_code/barcode 搜索）
- 同产品重复型号：应用层 `@api.constrains` 阻止并中文提示，DB 层 `UNIQUE(product_tmpl_id, model_code)` 兜底并发与批量导入
- 不同产品间同型号：允许，列表 `name` 附加「命中型号：xxx」以区分归属
- `model_code_index` 与型号行不一致（手工改库等）：在 shell 执行
  `env['product.model.code'].search([])._sync_template_index()` 重建

### 后续维护说明

- 改变型号拼接分隔符：只改 `_sync_template_index`（当前用 `\n`），改后对历史数据触发一次同步
- 新增型号类型：只改 `model_type` 的 `selection`，无需改搜索逻辑
- 让型号出现在其他单据的 Many2one 下拉：无需额外改动，只要指向 `product.template`，
  `_search_display_name` 已让型号参与搜索

### 变更

- 初始版本，实现产品多型号 + 可搜索：
  - 新建 `product.model.code` 明细模型（型号 / 类型 / 排序 / 启用 / 备注 / 归属产品）
  - 扩展 `product.template`：`One2many` 挂型号行、冗余可存储字段 `model_code_index`（trigram 索引）
  - 同产品内型号不可重复：`@api.constrains` 中文提示 + 数据库 `UNIQUE(product_tmpl_id, model_code)` 兜底
  - 搜索能力在数据库层：`_search_display_name` 让 `model_code_index` 参与搜索，否定操作符取交集
  - `web_search_read` 在列表命中型号时，把 `name` 附加「命中型号：xxx」提示
  - 产品表单「常规信息」页之后新增「型号」页，One2many 行可增删改排序
  - 产品列表新增「型号」列；搜索框并入型号搜索，新增独立「型号」搜索项
  - 型号独立列表/表单/搜索视图与菜单动作，供管理员批量检索维护
  - 型号行 `ondelete='cascade'`，删除产品时无孤儿数据

### 影响

- 新增模型 `product.model.code`，需在目标环境安装后由 `ir.model.access.csv` 授权
- `product.template` 新增 `model_code_index` 字段（`Text` + trigram 索引），首次安装自动建列与索引
- 不修改 Odoo 核心源码，全部通过 `_inherit` 扩展
- 仅依赖 `product`，不依赖 `sale`

### 文档

- 同步更新 `__manifest__.py`、`README.md`、`AGENTS.md`
