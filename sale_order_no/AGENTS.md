# AGENTS 工作指引

> 本文档用于指导 AI 助手或新开发者在维护、扩展本 Odoo 模块时的行为规范和关键上下文。

---

## 模块定位

本模块是一个 **Odoo 19 销售扩展模块**，核心目标是为外贸 SOHO 场景生成客户维度的年度订单编号。

- 模块名：`订单编号`
- 技术目录：`sale_order_no`
- 继承模型：`sale.order`、`res.partner`
- 主依赖：`sale`

---

## 不可破坏的核心约束

在修改代码时，必须保证以下行为不变：

1. **不修改系统原生 reference**
   - `sale.order.name`（如 `SOxxxx`）必须继续作为内部主键存在
   - 所有对外展示和打印使用 `order_no`
   - 表单里 `name` 只能 `invisible`、列表里只能 `column_invisible`，**绝不能用 `position="replace"` 删掉该节点**，
     否则其他模块继承 `//field[@name='name']` 时会找不到锚点而安装失败

2. **快照机制**
   - `buyer_ref`、`buyer_order_idx` 与 `order_no` 必须在创建时一次性写入
   - 后续修改客户 `ref` 不得重算历史单据的 `buyer_ref`
   - 修改订单日期 `date_order` 不再自动触发 `order_no` 重算；`order_no` 可手动编辑

3. **流水号稳定性**
   - 作废、取消、复制等操作都不能导致已分配流水号被回收或重排
   - 复制订单时应重新分配新编号，旧编号保留

4. **客户编码格式**
   - `res.partner.ref` 仅允许大写纯英文字母
   - 保存时自动转大写并去除首尾空格

5. **`order_no` 全局唯一**
   - 保存时通过 `@api.constrains('order_no')` 校验并给出中文提示
   - 数据库层另有 `_order_no_unique = models.Constraint("UNIQUE(order_no)")`
   - 分配编号时先自动避让已占用编号，仍冲突才报错

6. **`display_name` 优先使用 `order_no`**
   - Odoo 19 已移除 `name_get()`，禁止再定义或依赖它
   - 只允许重写 `_compute_display_name()`，未分配编号时回退到原生 `name`
   - 需要保留 `sale_show_partner_name` 上下文行为：`订单编号 - 客户名称`

7. **编号可搜索**
   - 重写 `_search_display_name()`，让 `order_no` 参与名称搜索
   - 否定操作符（`not ilike` 等）必须取交集（`Domain.AND`），肯定操作符取并集（`Domain.OR`）

8. **列表 API 返回的 `name` 必须替换为 `order_no`**
   - 重写 `web_search_read()`（定义在 `web` 模块的 `_inherit='base'` 上）
   - 签名必须与 Odoo 19 一致：`(domain, specification, offset, limit, order, count_limit)`
   - 仅当 `specification` 含 `name` 时才做替换查询，避免无谓开销

9. **Odoo 19 报表结构**
   - 只有 `sale.report_saleorder_document` 一个单据模板，报价单与形式发票均由它派生
   - 报表变量是 `doc`（不是 `o`），xpath 必须写 `//span[@t-field='doc.name']`

---

## 文件职责

| 文件 | 职责 |
|------|------|
| `__manifest__.py` | 模块元数据、依赖、数据文件声明 |
| `models/res_partner.py` | 客户编码格式校验与自动转大写 |
| `models/sale_order.py` | 订单编号字段定义、快照分配、避让重号、搜索与列表 API 重写、批量补号 |
| `views/partner_views.xml` | 改写联系人 `ref` 字段标签为“客户编号” |
| `views/sale_order_views.xml` | 表单标题、列表列、搜索视图中的订单编号 |
| `data/sale_order_actions.xml` | 列表“生成订单编号”批量补号服务器动作 |
| `reports/report_saleorder.xml` | 打印报表中用订单编号替换系统编号 |
| `migrations/19.0.1.1.0/` | 历史字段重命名迁移（保留升级路径，勿删） |
| `migrations/19.0.1.3.0/` | 唯一约束上线前的重复编号处理 |

---

## 常见扩展场景

### 改变编号规则

需要真正改变 `order_no` 的生成格式时，只改 `_build_order_no()`；分配与避让逻辑在 `_next_order_idx()`，
不要在视图或报表层拼接编号。改规则必须同时检查 `_restore_index_from_order_no()` 的正则是否仍能还原流水号。

### 增加编号前缀/区分报价单与订单

优先在报表模板或展示层区分，不要改 `buyer_order_idx` 的分配逻辑，否则会破坏流水号连续性。

### 在其他报表中展示

优先使用 `doc.order_no`；若为空应 fallback 到 `doc.name`，避免打印出空白编号。

### 批量导入历史单据

创建时直接写入 `order_no` 即可保留原编号，`_assign_order_fields()` 会跳过重算；
编号符合 `客户编码+两位年份+流水号` 时自动还原 `buyer_order_idx` 以接续后续编号。
导入后仍有缺号单据，用列表“生成订单编号”动作补号。

---

## 调试建议

- 编号未生成时，检查 `partner_id.ref` 是否为空或格式是否符合 `[A-Z]+`（空值会退化为 `UNK`）
- 流水号不连续是预期行为：作废单据同样占用流水号
- 手动导入的编号可能与自动分配冲突，分配时会自动递增避让，不必手工干预
- 出现“订单编号已被占用”提示时，检查是否重复录入或复制后未重新生成
- 若列表页仍显示 `SOxxxx`，检查 `web_search_read` 重写是否生效、模块是否已升级
- 升级到 19.0.1.3.0 报错时，先看日志中 `-DUP` 相关 warning，确认是否有历史重复编号

---

## 变更记录规范

**每次功能修改后必须更新版本号并添加变更日志。**

具体而言，任何改动都应同步更新：

- `__manifest__.py` 中的 `version` 字段（遵循 `19.0.x.y.z` 格式）
- `CHANGELOG.md` 中的版本说明，清晰描述变更、影响与文档同步情况
- 本 `AGENTS.md` 中的相关约束说明（若涉及行为变更）
- `README.md` 中的功能说明（若涉及用户可见功能）

版本号建议：

- 破坏性变更或模块架构调整：升级第二位，例如 `19.0.2.0.0`
- 功能新增：升级第三位，例如 `19.0.1.4.0`
- 缺陷修复或文档更新：升级第四位，例如 `19.0.1.3.1`

新增字段改名、改类型等结构变更，必须配套 `migrations/<新版本>/pre-migration.py`，且迁移脚本要幂等。
