# AGENTS 工作指引

> 本文档用于指导 AI 助手或新开发者在维护、扩展本 Odoo 模块时的行为规范和关键上下文。

---

## 模块定位

- 模块名：`产品多型号`
- 技术目录：`product_model`
- 新建模型：`product.model.code`
- 继承模型：`product.template`
- 主依赖：`product`（最小化，不依赖 `sale`）
- 当前版本：`19.0.1.0.0`

---

## L1：不可破坏的核心约束

每次修改代码必须保证以下行为不变。

1. **型号用独立明细模型，禁止逗号分隔塞进单个 Char**
   - `product.model.code` + `One2many` 挂在 `product.template` 上
   - 禁止为图省事把多个型号拼到一个 `Char` 字段里

2. **搜索在数据库层实现，禁止 Python 侧全表过滤**
   - 冗余可存储字段 `model_code_index`（`Text` + trigram 索引）拼接所有型号
   - `_search_display_name` 扩展让该字段参与 Many2one 下拉 / 搜索建议 / 快速搜索
   - 禁止 `search([])` 后在 Python 里过滤型号

3. **`model_code_index` 由型号行自动同步，勿手工编辑**
   - `product.model.code` 的 `create` / `write` / `unlink` 调 `_sync_template_index`
   - 只在 `model_code` / `product_tmpl_id` / `active` / `sequence` 变动时同步，避免无谓写入

4. **同产品内型号不可重复**
   - `@api.constrains('model_code', 'product_tmpl_id')` 中文提示带出具体值与产品名
   - 数据库 `UNIQUE(product_tmpl_id, model_code)` 兜底（并发 / 批量导入）

5. **`_search_display_name` 否定操作符取交集**
   - `model_code_index` 的否定搜索用 `Domain.AND`，否则会查出所有非该型号的产品
   - 肯定操作符用 `Domain.OR` 并入原生 name 搜索

6. **`web_search_read` 仅在命中型号时附加提示**
   - 必须先 `_extract_model_code_search_terms` 判断搜索域是否含 `model_code_index` 条件
   - 只改返回的 `name` 字段，不破坏其他字段与响应结构
   - 提示格式固定「（命中型号：xxx）」，已命中则不重复附加

7. **删除产品级联清理型号**
   - `product_tmpl_id` 的 `ondelete='cascade'`，禁止改成 `set null` 或 `restrict`

8. **Odoo 19 API 事实**
   - `name_get()` / `name_search()` 已从核心移除，只重写 `_compute_display_name` 与 `_search_display_name`
   - `_sql_constraints` 已废弃，用 `models.Constraint("UNIQUE(...)", "提示")`
   - `Domain` 从 `odoo.fields` 导入，`Domain.NEGATIVE_OPERATORS` 判断否定操作符

---

## 文件职责

| 文件 | 职责 |
|------|------|
| `__manifest__.py` | 模块元数据、依赖、数据文件声明（security → views） |
| `models/product_model_code.py` | 型号明细模型：字段、同产品去重约束、冗余索引同步、级联 |
| `models/product_template.py` | 扩展 `product.template`：One2many、冗余字段、`_search_display_name`、`web_search_read` |
| `views/product_template_views.xml` | 产品表单型号页、列表型号列、搜索框并入型号搜索 |
| `views/product_model_code_views.xml` | 型号独立列表/表单/搜索视图与菜单动作 |
| `security/ir.model.access.csv` | 普通用户读写业务数据，销售经理可配置 |

---

## 常见扩展场景

### 新增型号类型

在 `product.model.code.model_type` 的 `selection` 追加项即可，无需改搜索逻辑。

### 改变型号拼接分隔符

只改 `product_model_code.py` 的 `_sync_template_index`（当前用 `\n`）。改后对历史数据需触发一次同步，可在 shell 执行：
```python
env['product.model.code'].search([])._sync_template_index()
```

### 让型号出现在其他单据的 Many2one 下拉

无需额外改动——只要该 Many2one 指向 `product.template`，`_search_display_name` 已让型号参与搜索。若该模型自定义了 `web_search_read`，参照本模块实现附加命中提示。

---

## 调试建议

- 搜索不命中型号时，检查 `model_code_index` 是否已同步（在产品表单「型号」页改一条型号后看列表列）
- Many2one 下拉不命中时，确认目标字段指向 `product.template` 而非 `product.product`
- 同产品重复型号报错时，检查是否已有历史数据违反 `UNIQUE`，可在 DB 层先清理
- 列表 `name` 未附加命中提示时，检查搜索域是否含 `model_code_index` 条件、`specification` 是否请求了 `name`

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
