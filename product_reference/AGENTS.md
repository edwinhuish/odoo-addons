# AGENTS 工作指引

> 本文档用于指导 AI 助手或新开发者在维护、扩展本 Odoo 模块时的行为规范和关键上下文。

---

## 模块定位

- 模块名：`产品多参考号`
- 技术目录：`product_reference`（原名 `product_model`，`19.0.2.0.0` 起改名，含数据迁移脚本）
- 新建模型：`product.reference.code`（原名 `product.model.code`）
- 继承模型：`product.template`
- 主依赖：`product`（最小化，不依赖 `sale`）
- 当前版本：`19.0.2.0.0`

> 命名语义：与 Odoo 原生一致，`default_code` 是「内部参考（Internal Reference）」，
> 本模块挂的是**额外的**参考号（客户 / 工厂 / 别名）。源码与用户可见文案一律用
> `reference`，**禁止再出现 `model` 指代参考号**（`model` 在 Odoo 里另有「模型」语义，易混淆）。

---

## L1：不可破坏的核心约束

每次修改代码必须保证以下行为不变。

1. **参考号用独立明细模型，禁止逗号分隔塞进单个 Char**
   - `product.reference.code` + `One2many` 挂在 `product.template` 上
   - 禁止为图省事把多个参考号拼到一个 `Char` 字段里

2. **搜索在数据库层实现，禁止 Python 侧全表过滤**
   - 冗余可存储字段 `reference_code_index`（`Text` + trigram 索引）拼接所有参考号
   - `_search_display_name` 扩展让该字段参与 Many2one 下拉 / 搜索建议 / 快速搜索
   - 禁止 `search([])` 后在 Python 里过滤参考号

3. **`reference_code_index` 由参考号行自动同步，勿手工编辑**
   - `product.reference.code` 的 `create` / `write` / `unlink` 调 `_sync_template_index`
   - 拼接逻辑在 `product.template._sync_reference_index`（删行后要按剩余行重算）
   - 只在 `reference_code` / `product_tmpl_id` / `active` / `sequence` 变动时同步，避免无谓写入

4. **同产品内参考号不可重复**
   - `@api.constrains('reference_code', 'product_tmpl_id')` 中文提示带出具体值与产品名
   - 数据库 `UNIQUE(product_tmpl_id, reference_code)` 兜底（并发 / 批量导入）

5. **`_search_display_name` 否定操作符取交集**
   - `reference_code_index` 的否定搜索用 `Domain.AND`，否则会查出所有非该参考号的产品
   - 肯定操作符用 `Domain.OR` 并入原生 name 搜索

6. **`web_search_read` 仅在命中参考号时附加提示**
   - 必须先 `_extract_reference_code_search_terms` 判断搜索域是否含 `reference_code_index` 条件
   - 只改返回的 `name` 字段，不破坏其他字段与响应结构
   - 提示格式固定「（命中参考号：xxx）」，已命中则不重复附加

7. **删除产品级联清理参考号**
   - `product_tmpl_id` 的 `ondelete='cascade'`，禁止改成 `set null` 或 `restrict`

8. **内部参考行（Odoo Reference）的特殊规则**
   - 标记 `is_internal=True` 的行是 `product.template.default_code` 在「参考号」页里的镜像
   - 它始终排在参考号列表第一（`_order = "is_internal desc, ..."`），不可删除
   - 修改它（`reference_code`）必须回写 `default_code`；修改 `default_code` 必须同步更新/删除它
   - 禁止手工创建/删除/归档内部参考行；仅通过 `default_code` 间接维护
   - 如果已存在同代码的普通参考号行，同步时直接提升该行，避免唯一约束冲突

9. **Odoo 19 API 事实"
   - `name_get()` / `name_search()` 已从核心移除，只重写 `_compute_display_name` 与 `_search_display_name`
   - `_sql_constraints` 已废弃，用 `models.Constraint("UNIQUE(...)", "提示")`
   - `Domain` 从 `odoo.fields` 导入，`Domain.NEGATIVE_OPERATORS` 判断否定操作符

10. **模块 / 模型 / 字段改名必须有迁移与运维步骤**
   - 结构变更一律写 `migrations/<版本>/pre-migration.py`，且脚本必须幂等（可重复执行）
   - 模块改名（`product_model` → `product_reference`）需先手工执行
     `README.md` →「从 product_model 升级」的 SQL，否则 Odoo 会当成新模块安装
   - 改名后再改命名，必须同步本文件的「命名语义」段与迁移脚本的改名映射表

---

## 国际化约束（i18n）

每处用户可见文本都必须满足：

1. **源语言是英文（`en_US`）**：Python / XML 里一律写英文；中文只能出现在 `i18n/zh_CN.po` 的 `msgstr` 里，禁止写回源码。
2. **可翻译入口正确**：字段 `string` / `help`、selection 标签、约束消息、视图与动作文本走 `.po` 的 `model:` / `model_terms:` 条目；Python 运行期文案（含 `web_search_read` 的命中提示）用 `_()`。
3. **禁止拼接句子**：占位符统一用 `%(name)s` 命名形式，禁止 `"..." % (a, b)` 拼接——翻译无法调整语序。
4. **收尾动作**：改英文源文本 → 同步 `i18n/zh_CN.po` 的 `msgid` / `msgstr` → 提升模块版本 → `-u` 升级 + 刷新页面，在英文与中文两种界面各验一遍。
5. **代码注释保持中文**：注释不参与翻译（符合仓库约定），不要为 i18n 把注释改成英文。
6. **术语一致**：英文 `reference` ↔ 中文「参考号」；`.po` 的 `msgid` 与源码源文本逐字一致，否则译文不生效。

---

## 文件职责

| 文件 | 职责 |
|------|------|
| `__manifest__.py` | 模块元数据、依赖、数据文件声明（security → views） |
| `models/product_reference_code.py` | 参考号明细模型：字段、同产品去重约束、冗余索引同步、级联、内部参考行保护 |
| `models/product_template.py` | 扩展 `product.template`：One2many、冗余字段、`_search_display_name`、`web_search_read`、内部参考行同步 |
| `models/product_product.py` | 扩展 `product.product`：变体 `default_code` 修改时同步到模板侧内部参考行 |
| `views/product_template_views.xml` | 产品表单参考号页、列表参考号列、搜索框并入参考号搜索 |
| `views/product_reference_code_views.xml` | 参考号独立列表/表单/搜索视图与菜单动作 |
| `security/ir.model.access.csv` | 普通用户读写业务数据，销售经理可配置 |
| `migrations/19.0.2.0.0/pre-migration.py` | `product_model` → `product_reference` 的模块 / 模型 / 字段 / 索引 / 元数据改名（幂等） |
| `migrations/19.0.2.1.0/post-migration.py` | 为已有 `default_code` 的产品补建内部参考行 |

---

## 常见扩展场景

### 新增参考号类型

在 `product.reference.code.reference_type` 的 `selection` 追加项即可，无需改搜索逻辑。

### 改变参考号拼接分隔符

只改 `product_template.py` 的 `_sync_reference_index`（当前用 `\n`）。改后对历史数据需触发一次同步，可在 shell 执行：
```python
env['product.template'].search([])._sync_reference_index()
```

### 让参考号出现在其他单据的 Many2one 下拉

无需额外改动——只要该 Many2one 指向 `product.template`，`_search_display_name` 已让参考号参与搜索。若该模型自定义了 `web_search_read`，参照本模块实现附加命中提示。

---

## 调试建议

- 搜索不命中参考号时，检查 `reference_code_index` 是否已同步（在产品表单「参考号」页改一条参考号后看列表列）
- Many2one 下拉不命中时，确认目标字段指向 `product.template` 而非 `product.product`
- 同产品重复参考号报错时，检查是否已有历史数据违反 `UNIQUE`，可在 DB 层先清理
- 列表 `name` 未附加命中提示时，检查搜索域是否含 `reference_code_index` 条件、`specification` 是否请求了 `name`
- 升级后参考号数据「消失」时，先查 `product_reference_code` 表是否有数据、
  `ir_model` 里是否存在 `product.reference.code`，多半是升级前没执行模块改名 SQL

---

## 变更记录规范

每次功能修改后必须更新：
- `__manifest__.py` 的 `version`（遵循 `19.0.x.y.z`）
- `CHANGELOG.md` 的版本说明（变更 / 影响 / 文档）
- 本 `AGENTS.md` 的相关约束（若涉及行为变更）
- `README.md` 的功能说明（若涉及用户可见功能）

版本号建议：
- 破坏性变更或架构调整：升第二位，如 `19.0.2.0.0`
- 功能新增：升第三位，如 `19.0.2.1.0`
- 修复或文档：升第四位，如 `19.0.2.0.1`
