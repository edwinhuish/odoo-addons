# 变更日志

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
