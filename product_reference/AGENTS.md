# AGENTS 工作指引

> 本文档用于指导 AI 助手或新开发者在维护、扩展本 Odoo 模块时的行为规范和关键上下文。

---

## 模块定位

- 模块名：`产品多参考号`
- 技术目录：`product_reference`（原名 `product_model`，`19.0.2.0.0` 起改名，含数据迁移脚本）
- 新建模型：`product.reference.code`（原名 `product.model.code`）
- 继承模型：`product.template`、`product.product`（变体专属参考号）
- 自定义组件（前端）：字段 widget `product_reference_editor`、额外参考号管理弹窗
  （顶层 `main_components` overlay）、徽标 tooltip 模板
- 主依赖：`product`（最小化，不依赖 `sale`）
- 当前版本：`19.0.3.0.0`（19.0.3.0.0 架构调整：产品级编号 `base_reference` **叠加**进模板级 `default_code` 的 compute（`base_reference` 优先）、单变体产品两处同值、多变体产品只写 `base_reference`、产品级参考号两层都可见（不再按变体数隐藏）+ 存量回填迁移；19.0.2.7.1 补契约测试；19.0.2.5.2 修主变体表单的参考号归属）

> 命名语义：与 Odoo 原生一致，`default_code` 是「内部参考（Internal Reference）」，
> 本模块挂的是**额外的**参考号（客户 / 工厂 / 别名）。源码与用户可见文案一律用
> `reference`，**禁止再出现 `model` 指代参考号**（`model` 在 Odoo 里另有「模型」语义，易混淆）。
> 产品母型号固定叫 `base_reference`（界面标签 `Base Ref.`）：`base` 表达「母 / 基础」层级，
> 与 `default_code`（变体参考号）一眼可分；`ref` / `reference` 已被原生与外部编号语义占用，
> 不得复用（见 L1.3）。

---

## L1：不可破坏的核心约束

每次修改代码必须保证以下行为不变。

1. **参考号用独立明细模型，禁止逗号分隔塞进单个 Char**
   - `product.reference.code` + `One2many`：产品级共享行挂在 `product.template`
     （`reference_code_line_ids`），变体专属行挂在 `product.product`
     （`variant_reference_code_line_ids`）
   - 禁止为图省事把多个参考号拼到一个 `Char` 字段里

1.1. **参考号归属二选一，产品级与变体级两层各自独立**（`19.0.2.4.0` 起，
   `19.0.3.0.0` 起**不再按变体数隐藏产品级那一层**）
   - 每一行要么属于产品（`product_tmpl_id`），要么属于变体（`product_id`），
     `_check_single_owner` 兜底；禁止放宽成「两者都为空 / 两者都有」
   - **两层都可见、都可在各自的表单上维护**：产品表单始终显示产品编号 + 产品级参考号
     （含「+」弹窗），变体表单维护该变体自己那一组。`19.0.2.4.0`～`19.0.2.7.1` 曾按
     `product_variant_count > 1` 隐藏产品级那一层，`19.0.3.0.0` 按要求放开：**禁止**再加
     `invisible="product_variant_count > 1"` 之类的整块 / 元素级隐藏
   - **变体侧任何表单都必须显式指定 `lines_field=\"variant_reference_code_line_ids\"`**：
     widget 默认落在同视图里那个隐藏的 o2m 上，漏写就会去改产品级共享行（`19.0.2.5.2` 修的就是主变体表单）
   - 变体参考号子行创建时必须剥离 context 的 `default_product_tmpl_id`
     （`product.product.create/write` 里强制 `product_tmpl_id=False`），否则双归属报错
   - 去重约束按主人分别成立：`UNIQUE(product_tmpl_id, reference_code)` 与
     `UNIQUE(product_id, reference_code)`
   - 违反后果：变体之间共用参考号（客户 / 工厂编码串味），且报错信息指不出真正归属；
     或产品级参考号在多变体产品上「没有入口」（`19.0.3.0.0` 之前的表现）

1.2. **禁止硬编码可选模块的用户组**（`19.0.2.5.3`）
   - `depends` 只有 `product`：数据文件（`security/*.csv`、视图 XML）里只允许引用 `base.group_*`
     或本模块已依赖模块提供的组，**禁止**出现 `sales_team.` / `sale.` / `purchase.` / `stock.` /
     `account.` 等可选模块的组
   - 违反后果：在没有该模块的库上安装**直接失败**
     （`No matching record found for external id 'sales_team.group_sale_manager' in field 'Group'`），
     而装了 `sale` 的开发库完全看不出来 —— 这类问题只在干净库 / CI 上暴露
   - 历史：`19.0.2.5.3` 删掉了 `sales_team.group_sale_manager` 那行（权限与 `base.group_user` 行等价，
     纯冗余）；同一次排查在 `product_image` 也修了同类问题
   - 校验：`task check` 的「权限 / 视图里引用的用户组」检查会卡住

1.3. **产品级编号存 `base_reference`，并「叠加」在原生 `default_code` 上**（`19.0.2.6.0` 引入字段，
   `19.0.3.0.0` 定为「compute 叠加 + 单变体两处同值」）
   - 字段：`product.template.base_reference`（存储 + trigram 索引 + `copy=True`）＝**产品这一层的编号**
     （`G001`），与变体编号（`G001-WT`）分属两层
   - **模板级 `default_code` 的 compute 被本模块叠加**：`base_reference` 优先，其次才是原生单变体桥接
     （`ProductTemplate._compute_default_code()` 先 `super()` 再按需覆盖）。于是产品表单的 `Ref.` 框、
     产品列表 / Many2one 的 `[编号] 名称`、列表搜索、以及**其它模块**（卡片视图等）只要读原生
     `default_code` 就能拿到产品编号 —— 消费方不需要知道本模块存在。**禁止**把这段 compute 删掉或改回去
   - **inverse 规则（`ProductTemplate._set_default_code()`）**：单变体产品同时写两处
     （`base_reference` + 那条变体的 `default_code`，后者由原生 inverse 完成）；多变体产品只写
     `base_reference`（变体编号各归各的变体）
   - **⚠ 写入路径必须收敛**：`_set_default_code()` 里**禁止**顺手再写 `default_code`
     （会再次触发 inverse → 无限递归，`19.0.3.0.0` 实现时实测 `RecursionError`）；
     要把产品编号同步给变体，走 `_sync_single_variant_default_code()`；
     从变体侧改编号则由 `product.product._sync_single_variant_base_reference()` 反向同步
     （**仅单变体产品**，否则模板级 compute 会读到旧值）
   - 视图形状：产品表单**两种形态都显示** `Ref.`（值就是 `default_code`，多变体产品即产品编号）
     与额外参考号入口；`Base Ref.` 不再单独占一个输入框（它就是 `Ref.` 里那个值）
   - 搜索：模板层靠原生 `default_code` 即可命中产品编号；**变体层**（订单行选产品等）由
     `product.product._search_display_name()` 并入 `Domain("base_reference", …)` 命中
     （经 `_inherits` 委托；变体编号里没有 `G001`，不并入就搜不到）
   - **禁止**改用「产品编号直接存原生 `default_code` 那一列」（`19.0.4.0.0` 曾实现又回退）：
     要在 compute 里从库里读回已存值才不被原生赋空，写法脆弱；卸载还得靠钩子清值，
     否则会留下「原生认为不该有」的编号（评估记录见 `CHANGELOG.md` → `19.0.4.0.0`）
   - 存量数据（`migrations/19.0.3.0.0/post-migration.py`）：单变体产品按变体 `default_code` 回填
     `base_reference`（两处同值的既成结果）；有多变体产品则把存储列 `default_code` 对齐 `base_reference`
     —— 升级前那列是原生桥接算出来的（多变体时为空），列表搜索走存储列，不对齐就会搜不到
   - **只做提供方、不感知消费方**：本模块**禁止**调用 / 判断 `product_variant_conversion`、
     `product_card_view`（它们不在 `depends` 里）。本模块用 `tests/test_base_reference.py` 钉住字段契约
     （单变体两处同值 / 多变体只写产品编号 / 产品编号可被搜到）
   - 违反后果：产品编号在多变体产品上消失（表单、列表、卡片、搜索一起丢）、
     单变体产品两处编号不同步、或写入路径无限递归
   - **改 `models/product_template.py` / `models/product_product.py` 时必读 P1、P4；写迁移 / 卸载逻辑时必读 P5；再遇到「不要自有字段、用原生 `default_code` 承载产品编号」的要求，先读 P2、P3 再答复**

2. **搜索在数据库层实现，禁止 Python 侧全表过滤**
   - 冗余可存储字段（均 `Text` + trigram 索引）：产品级 `reference_code_index`、
     变体级 `product.product.variant_reference_code_index`
   - `_search_display_name` 扩展让这些字段参与 Many2one 下拉 / 搜索建议 / 快速搜索：
     - `product.template`：共享参考号 **+** 各变体参考号
       （`('product_variant_ids', 'any', [('variant_reference_code_index', ...)])`）
     - `product.product`：本变体参考号 **+** 所属产品的共享参考号
   - 搜索视图的 `filter_domain` 必须同步并入变体参考号，否则「变体里加的参考号在
     Products 搜不到」（`19.0.2.5.0` 修的就是这个）；产品编号不必再并入
     （`19.0.3.0.0` 起它已进模板级 `default_code` 的 compute，原生那一支就能命中，见 L1.3）
   - 禁止 `search([])` 后在 Python 里过滤参考号

3. **冗余搜索索引由参考号行自动同步，勿手工编辑**
   - `product.reference.code` 的 `create` / `write` / `unlink` 调 `_sync_owners_index`
   - 拼接逻辑分主人：产品侧 `product.template._sync_reference_index`、
     变体侧 `product.product._sync_variant_reference_index`（删行后都要按剩余行重算）
   - 只在 `reference_code` / `product_tmpl_id` / `product_id` / `active` / `sequence`
     变动时同步，避免无谓写入

4. **同一主人内参考号不可重复**
   - `@api.constrains('reference_code', 'product_tmpl_id', 'product_id')`
     （`_check_reference_code_unique_per_owner`）提示带出具体值与归属
   - 数据库 `UNIQUE(product_tmpl_id, reference_code)` 与
     `UNIQUE(product_id, reference_code)` 兜底（并发 / 批量导入）

5. **`_search_display_name` 否定操作符取交集**
   - `reference_code_index` 的否定搜索用 `Domain.AND`，否则会查出所有非该参考号的产品
   - 肯定操作符用 `Domain.OR` 并入原生 name 搜索

6. **`web_search_read` 仅在命中参考号时附加提示**
   - 必须先 `_extract_reference_code_search_terms` 判断搜索域是否含 `reference_code_index` 条件
   - 只改返回的 `name` 字段，不破坏其他字段与响应结构
   - 提示格式固定「（命中参考号：xxx）」，已命中则不重复附加

7. **删除产品级联清理参考号**
   - `product_tmpl_id` 的 `ondelete='cascade'`，禁止改成 `set null` 或 `restrict`

8. **Odoo 19 API 事实"
   - `name_get()` / `name_search()` 已从核心移除，只重写 `_compute_display_name` 与 `_search_display_name`
   - `_sql_constraints` 已废弃，用 `models.Constraint("UNIQUE(...)", "提示")`
   - `Domain` 从 `odoo.fields` 导入，`Domain.NEGATIVE_OPERATORS` 判断否定操作符

9. **额外参考号的管理入口与保存语义（`19.0.2.3.0` 起）**
   - 产品表单**没有「参考号」页**：入口是产品名下方 Reference 输入框右侧的「+」弹窗；
     禁止再回到页签里塞 One2many 列表
   - 弹窗内增删改只作用在产品表单 record 上（`record.update` / 子记录 `update` / x2many 命令），
     **不即时写库**；点产品「保存」才提交（未保存的新产品也能先录入）
   - 徽标 / tooltip 只统计**启用中**的参考号；停用的行只在弹窗内可见可恢复
   - Reference 输入框复用 Odoo 原生 `CharField` 渲染 `default_code`，禁止自己实现一套输入 / 提交逻辑
   - 输入框前标签固定 `Ref.`（**中英界面一致**，`i18n/zh_CN.po` 该条 `msgstr` 同样为 `Ref.`），
     禁止改回 `Reference` 或给它加中文译文
   - 「+」按钮**内置在输入框右端**（外层容器带 `o_input`，嵌套 input 由原生 `.o_input .o_input`
     规则自动去边框 / 去内边距），不要移到输入框外面，也不要改成文字按钮
   - 变体表单（`product.product`）维护**变体专属行** `variant_reference_code_line_ids`，
     与产品级共享行完全独立；widget 通过 `options.lines_field` / `resModel` 分流，
     不要把变体表单接到 `reference_code_line_ids` 上（那会变成变体之间共用）
   - 原生 Reference 在常规信息页 / Codes 组被隐藏，避免与标题区重复；新增表单入口时必须同步处理
   - 违反后果：出现「页签 + 标题区」两套参考号 UI，或变体表单改的是共享行（变体之间串数据）

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
7. **应用列表（Apps）元数据必须有中文**：改 `__manifest__.py` 的 `name` / `summary` / `description` 后，必须同步 `i18n/zh_CN.po` 的 `model:ir.module.module,shortdesc|summary|description:base.module_product_reference` 三条（`description` 条的 `msgid` 必须等于 `textwrap.dedent(manifest["description"])`，逐字符一致），改 `category` 则同步 `model:ir.module.category,name:base.module_category_inventory_product`。这些记录归属 `base` 且 `noupdate=True`，导入只补缺失语种、不覆盖库里已有值；改译文后的强制刷新方式见根 [`AGENTS.md`](../AGENTS.md) 4.8。违反后果：中文环境「应用」列表显示英文，或译文与英文源文本长期不同步。

---

## 开发复盘与关键经验（T-011）

> T-011（2026-09-08，落地 `19.0.2.5.0`，含 `19.0.2.3.0` 界面改造、`19.0.2.4.0` 多变体归属、
> `19.0.2.5.0` 变体参考号纳入产品搜索）：移除「参考号」页、Reference 上移到产品名下方、
> 输入框内「+」管理弹窗、徽标 tooltip、多变体参考号不共用。

### 本模块特有改动点

- **widget 复用原生 `CharField`**：标题区输入框直接渲染 Odoo 原生 `CharField`（改值走
  `record.update`），不自己实现输入 / dirty / 提交逻辑；「+」靠外层容器带 `o_input`
  （原生 `.o_input .o_input` 规则让嵌套 input 自动去边框 / 去内边距）做到「内置在输入框」。
- **隐藏的 One2many 必须双声明**：arch 里 `invisible="1"` 的参考号 One2many 不会进入主记录
  加载 spec，必须同时在 widget 的 `fieldDependencies` 声明，否则徽标数量恒为 0
  （与 `product_image` 图库同一坑）。
- **弹窗挂 `main_components`**：管理弹窗注册到顶层 overlay，避免 `record.update` 重渲染表单时
  弹窗被重建 / 闪烁；弹窗改动只落在 record 上，随产品「保存」提交。
- **变体子行的 `default_product_tmpl_id`**：变体 action context 会污染子行，必须在
  `product.product.create/write` 里对 `(0, 0, …)` 命令强制 `product_tmpl_id=False`，
  否则触发「不能同时归属产品与变体」。
- **同名术语合并**：JS `_t("Customer Reference")` 等与 selection 标签同 `msgid`，
  `.po` 里合并为一条多 `#:` 引用；`Product Reference` 与模型名 / 表单标题同理。
  同一 `msgid` 只能一条，否则整份 po 解析失败。
- **搜索覆盖要双向**：`product.template` 需并入变体参考号（`any` 子域），
  `product.product` 需并入产品共享参考号；搜索视图 `filter_domain` 必须同步，
  否则「变体里加的参考号在 Products 搜不到」。

### 维护提醒

- 前端资源 / 译文改动后 `-u` 升级**并强刷浏览器**（徽标、tooltip、弹窗文案都吃缓存）。
- 改搜索相关代码后回归三件事：产品能搜到变体参考号、变体能搜到产品共享参考号、命中提示正常。
- 索引与行不一致时，shell 重建：
  `env['product.template'].search([])._sync_reference_index()` 与
  `env['product.product'].search([])._sync_variant_reference_index()`

---

## 开发复盘与关键经验（T-035 / T-037）

> **T-035**（2026-09-23，落地 `19.0.3.0.0`）：产品编号**叠加进原生 `default_code` 的 compute**，
> 消费方（`product_card_view` / `product_variant_conversion`）回到只读原生字段。
> **T-037**（同日）：评估「干脆不要自有字段、产品编号直接存原生 `default_code` 那一列」并
> **按要求回退**；`product_card_view` 的编号口径定稿为「随选择切换」。
> 三次方案取舍的证据与源码依据见 L2 → P1 / P2 / P3，结论：**保留 `base_reference` 自有字段 + compute 叠加**。

### 关键决策链（按时间顺序，便于追溯「为什么最后是这样」）

1. 多变体产品（`G001-WT` / `G001-BK`）的产品编号 `G001` 无处可存 → 新增
   `product.template.base_reference`（存储字段 + trigram 索引），单变体产品与变体编号两处同值；
2. 消费方不必知道本模块存在 → 把 `base_reference` **叠加**进模板级 `default_code` 的 compute
   （`base_reference` 优先，`super()` 保底单变体桥接）→ 产品列表 / `[编号] 名称` / 搜索 / 单据
   全部原生口径自动带编号；
3. 「不要自有字段，直接用原生 `default_code` 那一列」→ 实现后**回退**（理由见 P3：原生 compute
   会在多变体时把该列赋空，保住值必须「先 flush 再从库读回」+ 卸载要钩子清值；少一个字段的收益
   远小于脆弱性与残留风险）；
4. `product_card_view` 编号口径定稿：**随选择切换**（未选=产品编号，选中=变体编号），
   已选组合行只显示属性组合（过程见该模块 `AGENTS.md` → P7）。

### 本模块特有改动点（`19.0.3.0.0`，易漏项）

- 模板级 `default_code` 的 compute **必须 `super()` 之后再覆盖**（先保住原生单变体桥接）；
- inverse（`_set_default_code`）里**只能写 `base_reference`**，禁止再写 `default_code`（实测 `RecursionError`）；
- 变体侧反向同步（`_sync_single_variant_base_reference`）**只在「所属产品恰好一条变体」时做**：
  多变体产品的变体编号与产品编号无关，放开判断会被「转换时清空原变体编号」连带清掉产品编号；
- 视图按变体数分流，且必须用**元素级** `invisible`（禁止再整块隐藏 `div[name='product_reference']`，
  那会把多变体产品的编号输入框一起藏掉）；
- 搜索要**三处**都并入 `base_reference`：模板 `_search_display_name`、变体 `_search_display_name`
  （经 `_inherits` 委托）、搜索视图 `filter_domain`（顶部搜索框 + 独立「Reference」搜索项）。

### 维护提醒

- 改 `_compute_default_code` / `_set_default_code` / `_sync_single_variant_default_code` 前后各跑
  `task test -- product_reference`（6 项契约用例：单变体两处同值双向 / 多变体只写产品编号 /
  变体编号不动产品编号 / 模板编号优先且清空后回落 / 两层可搜索）；
- **卸载即丢产品编号**（`base_reference` 是自有字段，随模块一起消失）→ 需要留档先导出；
- 存量**多变体**产品的产品编号仍需人工补录一次（无可自动推断的来源）。

---

## L2：踩坑档案

> 本节记录「产品编号该存哪、怎么写、怎么迁移、怎么卸载」这条链路上的实测结论与源码依据。
> L1 第 1.3 条标注的触发条件下必读。

### P1：模板级 `default_code` 是「桥接字段」，不能承载产品编号

**触发条件**：想让产品级编号走原生 `default_code` 时必读（改 `models/product_template.py` 的
compute / inverse 之前）。

- **源码事实**（Odoo 19）：`product.template.default_code = fields.Char(compute='_compute_default_code',
  inverse='_set_default_code', store=True)`；compute 走 `_compute_template_field_from_variant_field()`：
  **单变体**镜像那条变体的值、**多变体**赋空、**零变体**写归档变体；`create()` 里另有一段
  `_get_related_fields_variant_template()`（`['barcode', 'default_code', 'standard_price', 'volume', 'weight']`）
  的补写。
- **实测**（开发库）：多变体产品写模板级 `default_code` **确实写进数据库**；但只要 compute 真跑一次，
  这一列就被赋空 —— 「值在库里」和「值不会被清」是两件事。
- **陷阱**：覆盖这段 compute 会连带影响导入 / 创建路径的补写行为（上一条）。
- **正确做法**：产品编号用**自有存储字段** `base_reference`，只把它的值「读时叠加」进 `default_code`；
  桥接原样保留。

### P2：把 `default_code` 改成纯 stored 字段（去掉 compute）—— 能做，但不能做

**触发条件**：收到「不要计算字段、改成实际存储数据」这类要求时**必读本节**（先读完再动手）。

- **可行性（源码依据）**：Odoo 19 的字段继承是「参数合并」——
  `Field._get_attrs()` 先 `attrs.update(基础定义._args__)` 再 `attrs.update(本模块._args__)`，
  所以**显式传 `compute=None` / `inverse=None` 能让合并结果里的 compute 消失**，
  字段就变成普通存储字段（`store` 继承基础定义的 `True`）。
- **为什么不能做**：
  1. **拆掉原生单变体桥接**：单变体产品的模板编号不再跟随变体 → `display_name` 的 `[编号] 名称`、
     `create()` 的 related 传播、单据 / 报表口径全部漂移（直接违反「不影响 Odoo 原有逻辑」）；
  2. 表单 `Ref.` 写的是**模板列**、那条变体的 `default_code` 永远为空 → 报价 / 采购 / PDF 里没编号；
  3. **卸载不干净**：字段声明虽会自动复原，但写进这一列的值仍在（原生语义下多变体产品该列为空）
     → 必须再加 `uninstall_hook` 主动清值，而清值就等于「卸载即丢编号」；
  4. 属于**非文档化扩展面**：Odoo 从未承诺「后装的模块可以摘掉前一个模块的 compute」，
     跨版本回归风险由维护者自担。
- **若确实要做**（最小清单）：`compute=None, inverse=None, readonly=False, copy=False` 重声明 +
  自己实现「单变体写入时同时写变体」+ 补 `display_name` / 搜索 / 导入口径 + `uninstall_hook` 清值 +
  全量回归（含 `product_variant_conversion` 里被测试钉住的桥接契约）。

### P3：「产品编号直接存原生列」为什么被回退（评估记录，`19.0.4.0.0` 未发布）

**触发条件**：再次收到同类需求时必读（可省一次完整试错）。

- **当时的实现要点**：`_compute_default_code()` 先 `self.env.flush_all()` → 用 `cr.execute`
  从库里读回模板级已存值 → `super()`（原生镜像 / 赋空）→ 把值放回（单变体记录跳过）；
  `product.product._search_display_name()` 并入 `product_tmpl_id.default_code`；
  存量值由 `migrations/19.0.4.0.0/pre-migration.py` 从 `base_reference` 搬过来；
  `uninstall_hook` 负责把写进原生列的值清掉。
- **为什么脆弱**：
  - **必须先落库再读**：同一事务里刚写入的新值还在缓存，直接读库会读到旧值再写回 ——
    等于吞掉用户本次修改；
  - 在 compute 里调用 `flush_all()` 属于「计算过程中触发 flush」，是 ORM 内部机制的灰区；
  - 「值会不会被清」取决于 compute 何时被触发（实测用户操作路径不触发、`add_to_compute` 也不触发），
    但这是**观察到的行为，不是契约** —— 一个版本升级或一次批量写入就可能变；
  - 用户第 3 条要求「卸载后不遗留任何数据或行为变更」在这条路上要额外靠钩子兜住，
    而钩子一旦失败 / 被跳过，就留下「原生认为不该存在」的编号。
- **结论**：收益（少一个字段）远小于代价（脆弱 + 残留 + 跨版本风险）→ **保留 `base_reference` 自有字段**。

### P4：产品编号的写入路径必须单向收敛（`RecursionError` 实测）

**触发条件**：改 `_set_default_code` / `_sync_single_variant_default_code` /
`product.product._sync_single_variant_base_reference` 时必读。

- **现象**：在 inverse 里再写 `default_code` → 再次触发 inverse → `RecursionError`
  （`19.0.3.0.0` 实现时实测）。
- **正确做法**：
  - `_set_default_code()` **只写 `base_reference`**；要把值同步给变体，走 `_sync_single_variant_default_code()`；
  - 从变体侧改编号，由 `product.product._sync_single_variant_base_reference()` 反向写 `base_reference`，
    且**仅当所属产品恰好一条变体**；
  - 「直接写 `base_reference`」（API / 脚本 / 导入）这条路的收口也在 `_sync_single_variant_default_code()`。
  三条路径互相不回头，因此必然收敛；任何「顺手再写另一个字段」的改动都要先想清楚会不会成环。

### P5：迁移与钩子的时序（pre vs post / 卸载钩子）

**触发条件**：加字段、删字段、写 `migrations/` 或 `uninstall_hook` 时必读。

- **新增列的回填 → post-migration**：新列要到模型加载（`_auto_init`）之后才存在
  （`19.0.3.0.0` 的回填就是 post）；
- **要读「即将被删掉的列」→ pre-migration**：模型里一删字段，加载时列即被 drop，post 阶段读不到
  （`19.0.4.0.0` 评估版据此选的 pre）；
- **卸载钩子时机**：`uninstall_hook` 在 `module_uninstall()` **之前**执行、且模块代码仍然加载
  （`odoo/modules/loading.py` STEP 5）→ 可以放心用 ORM；之后注册表整体重载，本模块的字段与 compute
  覆盖面随之下线；
- **模块升级不会自动重算存量计算字段**（`loading.py` 里没有相关逻辑）→ 别指望「升级会把编号算回来」，
  升级后要抽查一遍真实数据。。

---

## 文件职责

| 文件 | 职责 |
|------|------|
| `__manifest__.py` | 模块元数据、依赖、数据文件声明（security → views） |
| `models/product_reference_code.py` | 参考号明细模型：字段、归属二选一约束、按主人去重、冗余索引同步、级联 |
| `models/product_template.py` | 扩展 `product.template`：共享参考号 One2many、冗余字段 `reference_code_index`、`_search_display_name`、`web_search_read`、搜索词提取（供变体侧复用） |
| `models/product_product.py` | 扩展 `product.product`：变体专属 One2many `variant_reference_code_line_ids`、冗余字段 `variant_reference_code_index`、变体搜索与命中提示、子行剥离模板默认 |
| `views/product_template_views.xml` | 产品模板表单标题区 Reference 编辑器（继承 `product.product_template_form_view`）、隐藏常规信息页原生 Reference、列表参考号列、搜索框并入参考号搜索 |
| `views/product_product_views.xml` | 变体主表单（`product.product.form`）与变体独立编辑表单（`product_variant_easy_edit_view`）的标题区 Reference 编辑器，并隐藏两处重复的原生 Reference |
| `views/product_reference_code_views.xml` | 参考号独立列表/表单/搜索视图与菜单动作 |
| `static/src/js/product_reference_editor.js` | 字段 widget `product_reference_editor`：复用原生 `CharField` 渲染 `default_code`，右侧「+」与「+N」徽标（tooltip） |
| `static/src/js/product_reference_manage.js` | 额外参考号管理弹窗组件 + 顶层 overlay 注册（`main_components`）；行增删改排序都落到产品表单 record |
| `static/src/xml/*.xml` | 编辑器 / 徽标 tooltip / 管理弹窗的 QWeb 模板 |
| `static/src/scss/product_reference.scss` | 编辑器行、徽标、tooltip、管理弹窗样式 |
| `security/ir.model.access.csv` | 普通用户读写业务数据，销售经理可配置 |
| `migrations/19.0.2.0.0/pre-migration.py` | `product_model` → `product_reference` 的模块 / 模型 / 字段 / 索引 / 元数据改名（幂等） |
| `migrations/19.0.2.2.0/pre-migration.py` | 清理 `19.0.2.1.0` 遗留的内部参考行（如未部署则无影响） |

---

## 常见扩展场景

### 新增参考号类型

在 `product.reference.code.reference_type` 的 `selection` 追加项即可，无需改搜索逻辑。

### 改变参考号拼接分隔符

只改 `product_template.py` 的 `_sync_reference_index` 与 `product_product.py` 的
`_sync_variant_reference_index`（当前都用 `\n`）。改后对历史数据需触发一次同步，可在 shell 执行：
```python
env['product.template'].search([])._sync_reference_index()
env['product.product'].search([])._sync_variant_reference_index()
```

### 变体参考号索引与行不一致

在 shell 执行：
```python
env['product.product'].search([])._sync_variant_reference_index()
```

### 让参考号出现在其他单据的 Many2one 下拉

无需额外改动——只要该 Many2one 指向 `product.template`，`_search_display_name` 已让参考号参与搜索。若该模型自定义了 `web_search_read`，参照本模块实现附加命中提示。

---

## 调试建议

- 搜索不命中参考号时，检查 `reference_code_index` 是否已同步（用产品名下方「+」弹窗改一条参考号并保存产品后看列表列）
- 标题区编辑器 / 徽标不出现：检查模块前端资源是否已升级并强刷浏览器；`product_reference_editor` widget 是否挂到了 `default_code` 节点
- 徽标数量一直为 0：多半是 One2many 没随主记录加载（`fieldDependencies` 或 arch 里不可见的 `reference_code_line_ids` 声明缺失）
- 在变体里加的参考号在 Products 搜不到：检查该变体的 `variant_reference_code_index` 是否已同步
  （shell 执行 `env['product.product'].search([])._sync_variant_reference_index()`），
  以及产品搜索视图的 `filter_domain` 是否含 `product_variant_ids.variant_reference_code_index`
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
