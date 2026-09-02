# 变更日志

## [19.0.1.6.1] - 2026-09-02

### 变更

- PDF 文件名覆盖修复（dict 写入陷阱）：
  - 1.6.0 用 `write({'print_report_name': {lang: value for lang in langs}})` 传 dict，但 Odoo 19 的 `_String.write` 经 `convert_to_cache` 调 `str(value)` 把 dict 整体转为字符串值写入，导致英文界面下文件名变成 `{"zh_CN": "...", "en_US": "..."}` 的字符串表示
  - 改为在 `_force_order_no_print_name` 内逐语言切换上下文后 write，每次只写一个 lang 的 JSONB key：
    - 先 `with_context(lang='en_US').write(...)` 写 base 值
    - 再循环 `res.lang`，对每个非 en_US 语言 `with_context(lang=code).write(...)` 写对应 lang 的 key

### 影响

- 升级后所有语言的 `print_report_name` 都被覆盖为含 `order_no` 的字符串值
- 不再有 dict 被转为字符串的污染问题

### 文档

- 同步更新 `__manifest__.py`

---

## [19.0.1.6.0] - 2026-09-02

### 变更

- PDF 文件名覆盖——按语言强制写入：
  - 发现 1.5.4 用 `<function>` + `write` 只覆盖了 `en_US` 翻译，`zh_CN` 仍是原生 `object.name` 表达式，导致中文界面下 PDF 文件名仍是 `S00026`
  - 根因：`print_report_name` 是 `translate=True` 字段（JSONB 按语言存储），XML 加载默认上下文是 `en_US`，普通 `write({'print_report_name': '...'})` 只写当前 lang 对应的 key
  - 新增 `models/ir_actions_report.py`，扩展 `ir.actions.report`，提供 `_force_order_no_print_name(expression)` 方法
  - 该方法在所有 `res.lang` 上写入相同表达式（用 `with_context(lang=None).write({'print_report_name': {lang: value for lang in langs}})`）
  - `reports/report_saleorder.xml` 中两条 `<function>` 改为调用 `_force_order_no_print_name`

### 影响

- 升级后任意语言下打印，PDF 文件名都会显示 `order_no`（如 `Quotation - OW2602.pdf`）
- 数据库中 `print_report_name` 的 JSONB 所有语言 key 都会被统一覆盖
- 不涉及 sale_order 表结构变更

### 文档

- 同步更新 `__manifest__.py`

---

## [19.0.1.5.4] - 2026-09-02

### 变更

- PDF 文件名覆盖改为 `<function>` + `write` 强制执行：
  - 1.5.3 用 `<record id="sale.action_report_saleorder" model="ir.actions.report">` 跨模块引用 sale 的报表动作，但截图证明 PDF 文件名仍未变（仍是 `S00026`），说明该写法在升级时未真正覆盖 `print_report_name`
  - 改为在 `reports/report_saleorder.xml` 末尾追加两条 `<function model="ir.actions.report" name="write">`，显式查找 `sale.action_report_saleorder` 与 `sale.action_report_pro_forma_invoice` 的 `res_id` 并写入新的 `print_report_name`
  - `<function>` 在 init/update/demo 模式下都会执行，确保数据库里该字段必定为最新版本
  - 1.5.3 之前的 `<record>` 写法保留以兼容两种模式，但 `<function>` 会强制覆盖

### 影响

- 升级后 `print_report_name` 必定被强制写入含 `order_no` 的表达式，不再依赖 XML 跨模块 record id 引用的兼容性
- 不涉及数据库结构变更

### 文档

- 同步更新 `__manifest__.py`

---

## [19.0.1.5.3] - 2026-09-02

### 变更

- PDF 文件名覆盖修复：
  - 1.4.0 用 `<data noupdate="1">` 包裹两条 `ir.actions.report` 覆盖，导致首次安装后再次升级时 Odoo 跳过写入，旧 `object.name` 表达式残留，PDF 文件名仍为 `Quotation - S00026.pdf`
  - 移除 `<data noupdate="1">` 包裹，改为默认 `noupdate=0`，每次升级都强制覆盖 `print_report_name`，避免用户手动改动或历史失败升级造成的旧值残留

### 影响

- 升级后 `sale.action_report_saleorder` 与 `sale.action_report_pro_forma_invoice` 的 `print_report_name` 会被强制刷新为含 `order_no` 的表达式
- 不涉及数据库结构变更

### 文档

- 同步更新 `__manifest__.py`

---

## [19.0.1.5.2] - 2026-09-02

### 变更

- 客户门户预览页面（xpath 兼容性修复）：
  - 1.5.1 用的 xpath `//li[hasclass('breadcrumb-item') and hasclass('active')]/t[2]` 在 Odoo 19 视图继承链中报"上级视图内找不到元素"
  - 改为 `//li[hasclass('breadcrumb-item')][hasclass('active')]/t`（两个谓词连写代替 `and`，去掉位置索引 `[2]`，直接选 active `<li>` 内唯一的 `<t>`）
  - H2 标题的 xpath 保持 `//div[@id='introduction']//h2/em`

### 影响

- 与 1.5.0/1.5.1 行为一致；不涉及数据库结构变更

### 文档

- 同步更新 `__manifest__.py`

---

## [19.0.1.5.1] - 2026-09-02

### 变更

- 客户门户预览页面（xpath 加固）：
  - 1.5.0 实现的 xpath 使用 `[@t-out='sale_order.name']` 属性匹配，在某些环境下匹配失败导致预览页面仍显示 `S00026`
  - 改为基于 DOM 结构的稳健 xpath：面包屑用 `t[2]` 位置定位，H2 用 `//div[@id='introduction']//h2/em` 路径定位
  - 行为与 1.5.0 完全一致，仅调整 xpath 表达式

### 影响

- 与 1.5.0 一致；不涉及数据库结构变更，无需迁移脚本

### 文档

- 同步更新 `README.md`、`__manifest__.py`

---

## [19.0.1.5.0] - 2026-09-02

### 变更

- 客户门户预览页面：
  - 新增 `views/portal_templates_inherit.xml`，扩展 `sale.portal_my_home_menu_sale` 与 `sale.sale_order_portal_content`
  - 面包屑尾（`销售订单 / 报价单 XXXXX`）从 `sale_order.name` 改为 `sale_order.order_no or sale_order.name`
  - 详情页 H2 标题（`报价单 - XXXXX`）从 `sale_order.name` 改为 `sale_order.order_no or sale_order.name`
  - 后台用户预览客户门户时（包括 `portal_back_in_edit_mode` 包装层）也能看到自定义订单编号

### 影响

- 这两处原本直接 `t-out sale_order.name`，绕过了 `_compute_display_name()` 的优先显示 `order_no` 逻辑，必须显式覆盖
- 不涉及数据库结构变更，无需迁移脚本
- 未分配 `order_no` 的单据（理论上新建未保存状态下才出现）回退到 `sale_order.name`，保证不显示空白

### 文档

- 同步更新 `README.md`、`__manifest__.py`

---

## [19.0.1.4.0] - 2026-09-02

### 变更

- PDF 文件名定制：
  - 覆盖 `sale` 模块原生 `ir.actions.report` 记录 `action_report_saleorder` 与 `action_report_pro_forma_invoice` 的 `print_report_name`
  - 使用完整外部 ID（`sale.action_report_saleorder`）引用现有记录，避免被 Odoo 19 数据加载器当作新建（首次实现误用本模块命名空间 id 导致 `name` 字段 NotNullViolation）
  - 用 `<data noupdate="1">` 包裹，防止后续升级反复覆盖用户手动调整
  - 未分配 `order_no` 时回退到 `object.name`，保证新建未保存单据不报错
  - 报价单（draft/sent 态）文件名由 `Quotation - <order_no or name>` 生成，订单态为 `Order - <order_no or name>`
  - 形式发票文件名由 `PRO-FORMA - <order_no or name>` 生成
  - 未分配 `order_no` 时回退到 `object.name`，保证新建未保存单据不报错

### 影响

- 用户打印询价单、报价单、销售订单、形式发票时，下载的 PDF 文件名会显示自定义订单编号（如 `Quotation - DZ2602.pdf`），不再暴露原生 `SOxxxx`
- 打印报表正文显示订单编号的能力在 `19.0.1.3.0` 已具备（继承 `sale.report_saleorder_document`），本次无重复改动
- 不涉及数据库结构变更，无需迁移脚本

### 文档

- 同步更新 `README.md`、`__manifest__.py`

---

## [19.0.1.3.0] - 2026-09-01

### 变更

- Odoo 19 兼容化改造：
  - 移除 `name_get()`（Odoo 19 已从核心删除），显示名称统一由 `_compute_display_name()` 提供
  - 新增 `_search_display_name()`，使 Many2one 下拉、搜索建议、快速搜索可命中 `order_no`
  - `web_search_read()` 按 Odoo 19 的 `(domain, specification, offset, limit, order, count_limit)` 签名重写
  - 报表继承由 `sale.report_saleorder_quotation`（Odoo 19 已不存在）改为只继承 `sale.report_saleorder_document`，
    变量由 `o.name` 修正为 `doc.name`
  - 列表视图继承基础视图 `sale.sale_order_tree`，报价单与销售订单列表同时生效；
    编号列置顶显示，原生 `name` 列用 `column_invisible` 隐藏而非删除，避免破坏其他模块的继承锚点
- 编号分配增强：
  - 新增数据库层 `UNIQUE(order_no)` 约束，作为并发创建与批量导入时的兜底
  - 生成编号时自动避让已占用的编号（历史导入、手动改号、复制单据），不再直接报错阻断
  - 年度区间上界改用当天 23:59:59，修复年末最后一天单据被漏算的问题
  - `date_order` 为空时回退到当前时间，保证导入单据也能正常编号
- 批量处理能力：
  - 导入时显式指定 `order_no` 不再被覆盖，并尝试从编号中还原年度流水号以接续编号
  - 新增 `action_generate_order_no()` 与列表“动作 → 生成订单编号”，为缺号单据批量补号
- 搜索体验：
  - 销售订单搜索框默认过滤域加入 `order_no`，输入编号即可命中
  - 表单标题区的原生 `name` 改为隐藏而非删除，避免其他模块继承该字段时找不到锚点
- 联系人视图：
  - 不再重复插入 `ref` 字段（Odoo 19 原生表单已有），改为改写标签与占位提示

### 影响

- 升级到本版本会执行 `migrations/19.0.1.3.0/pre-migration.py`：
  - 空字符串编号归一化为 `NULL`
  - 重复编号改写为 `<原编号>-DUP<n>`（保留 id 最小的一条），日志会记录明细，需人工核对
- 历史单据的 `buyer_ref`、`buyer_order_idx`、`order_no` 均不受影响
- 打印报表仍优先显示 `order_no`，未分配时回退到原生 `name`

### 文档

- 同步更新 `README.md`、`AGENTS.md`、`__manifest__.py`

---

## [19.0.1.2.2] - 2026-08-14

### 变更

- 将 `order_no` 的中文名称从“对外单据编号”统一改为“订单编号”。
- 同步更新字段 `string`、视图标签、校验提示、报表注释及说明文档（README、AGENTES.md、CHANGELOG）。
- 将模块显示名称由“客户年度单据编号”改为“订单编号”。

### 影响

- 表单、列表、搜索视图、打印报表及错误提示中统一展示为“订单编号”。
- 模块在应用列表中的显示名称变为“订单编号”，功能与数据库结构保持不变。

### 文档

- 同步更新 `README.md`、`AGENTES.md`、`CHANGELOG.md`、`__manifest__.py` 中的名称与描述。

---

## [19.0.1.2.1] - 2026-08-14

### 变更

- 修复 `models/sale_order.py` 中 `ValidationError` 未导入导致的模块加载/保存异常。
- 显式重写 `_compute_display_name()`，确保 `display_name` 字段优先使用 `order_no`，为空时回退到原生 `name`。
- 重写 `web_search_read()`，在 `/web/dataset/call_kw/sale.order/web_search_read` 返回的列表记录中，将 `name` 字段值替换为对应 `order_no`，保持其他字段与响应结构不变。

### 影响

- 面包屑、页面标题、通知、邮件模板等使用 `display_name` 的场景统一展示 `order_no`。
- 销售订单列表页 API 返回的 `name` 字段对外显示为 `order_no`（如 `DZ2602`），不再暴露原生 `SOxxxx` 编号。
- 原生 `sale.order.name` 仍作为内部主键保留，不影响数据库与其他依赖内部编号的逻辑。

### 文档

- 同步更新 `README.md`、`AGENTES.md`、`__manifest__.py` 中的字段说明、API 行为描述与版本号。

---

## [19.0.1.2.0] - 2026-08-13

### 变更

- `order_no` 由计算字段改为普通存储字段，创建时自动生成，支持手动编辑。
- 新增 `@api.constrains('order_no')` 全局唯一性校验，保存时若重复则阻止并给出中文提示。
- 重写 `name_get()`，`display_name` 优先显示 `order_no`，为空时回退到原生 `name`。
- 销售订单详情页标题由 `name` 替换为可编辑的 `order_no`。
- 销售订单列表页 `name` 列替换为 `order_no` 列。

### 影响

- 修改订单日期 `date_order` 不再自动触发 `order_no` 重算；用户可手动编辑调整。
- 报价单、销售订单在 Many2one、下拉选择、搜索建议中的显示名称统一使用 `order_no`。
- 复制订单时 `order_no` 也会被清空并重新生成，避免编号冲突。

### 文档

- 同步更新 `README.md`、`AGENTES.md`、`__manifest__.py` 中的字段说明与行为描述。

---

## [19.0.1.1.0] - 2026-08-13

### 变更

- 字段重命名：
  - `sale.order.customer_code` -> `sale.order.buyer_ref`
  - `sale.order.customer_seq_num` -> `sale.order.buyer_order_idx`
  - `sale.order.customer_doc_no` -> `sale.order.order_no`
- 字段移除：
  - `sale.order.customer_doc_year`：不再单独快照年份，改为从 `date_order` 实时读取两位年份。
- 计算方法：
  - `order_no` 的计算依赖更新为 `buyer_ref`、`date_order`、`buyer_order_idx`。

### 影响

- 已有数据通过迁移脚本 `migrations/19.0.1.1.0/pre-migration.py` 自动迁移，历史单据的 `buyer_ref`、`buyer_order_idx`、`order_no` 值保持不变。
- 修改订单日期 `date_order` 会触发 `order_no` 重新计算（年份部分随之变化）。
- 客户编号 `buyer_ref` 和流水号 `buyer_order_idx` 仍保持创建时快照，不会因客户信息变更而变动。

### 文档

- 同步更新 `README.md`、`AGENTES.md`、`__manifest__.py` 中的字段名称与说明。

---

## [19.0.1.0.0] - 初始版本

- 实现按客户编码 + 两位年份 + 年度流水号生成订单编号。
- 提供销售订单/报价单统一编号、客户编码校验、快照机制及报表替换功能。
