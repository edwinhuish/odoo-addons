# AGENTS 工作指引

> 本文档用于指导 AI 助手或新开发者在维护、扩展本 Odoo 模块时的行为规范和关键上下文。
> 约束段（L1）每次加载必读；踩坑档案段（L2）按主题触发条件加载。

---

## 模块定位

- 模块名：`订单编号`
- 技术目录：`sale_order_no`
- 继承模型：`sale.order`、`res.partner`、`ir.actions.report`
- 主依赖：`sale`、`sale_pdf_quote_builder`
- 当前版本：`19.0.1.7.0`（仅支持全新安装，已删除 migrations）

---

## L1：不可破坏的核心约束

每次修改代码必须保证以下行为不变。每条只列约束与违反后果，实现细节见 L2 踩坑档案。

1. **不修改系统原生 `sale.order.name`**
   - `SOxxxx` 继续作为内部主键；对外展示与打印用 `order_no`
   - 表单里 `name` 只能 `invisible`、列表里只能 `column_invisible`，**绝不能用 `position="replace"` 删节点**——其他模块继承 `//field[@name='name']` 会找不到锚点而安装失败

2. **快照机制**：`buyer_ref`、`buyer_order_idx`、`order_no` 创建时一次性写入，后续修改客户 `ref` 或 `date_order` 不重算

3. **流水号稳定性**：作废、取消、复制都不回收已分配流水号；复制时重新分配新编号

4. **客户编码格式**：`res.partner.ref` 仅允许大写纯英文字母，保存时自动转大写去空格

5. **`order_no` 全局唯一**：`@api.constrains` 中文提示 + 数据库 `UNIQUE(order_no)` 约束双重保证，分配时先避让重号

6. **`display_name` 优先 `order_no`**：Odoo 19 已移除 `name_get()`，只重写 `_compute_display_name()`，未分配回退到 `name`；保留 `sale_show_partner_name` 上下文行为

7. **编号可搜索**：重写 `_search_display_name()` 让 `order_no` 参与搜索；否定操作符取交集（`Domain.AND`），肯定操作符取并集（`Domain.OR`）

8. **列表 API 返回 `name` 替换为 `order_no`**：重写 `web_search_read()`，签名 `(domain, specification, offset, limit, order, count_limit)`，仅 `specification` 含 `name` 时做替换

9. **Odoo 19 报表结构**：只有 `sale.report_saleorder_document` 一个单据模板，变量是 `doc`（不是 `o`），xpath 写 `//span[@t-field='doc.name']`

10. **PDF 文件名覆盖**：必须用 `<function>` 调 `_force_order_no_print_name`，覆盖三个报表动作（`sale.action_report_saleorder` / `sale.action_report_pro_forma_invoice` / `sale_pdf_quote_builder.action_report_saleorder_raw`）。**改 `reports/report_saleorder.xml` 或 `models/ir_actions_report.py` 时必读 P1**

11. **客户门户预览页面**：`sale.portal_my_home_menu_sale` 与 `sale.sale_order_portal_content` 直接 `t-out sale_order.name`，绕过 `_compute_display_name`，必须视图层显式覆盖。**改 `views/portal_templates_inherit.xml` 时必读 P2**

---

## L2：踩坑档案

按主题归档的实现陷阱。L1 约束标注的触发条件下必读，其他时候按需查阅。

### P1：PDF 文件名覆盖的三个陷阱

**触发条件**：改 `reports/report_saleorder.xml`、`models/ir_actions_report.py`，或新增报表动作覆盖时。

**陷阱 1：`<record id="sale.xxx" model="ir.actions.report">` 跨模块引用不生效**
- 升级模式下 Odoo 19 数据加载器对带模块前缀 id 的处理不统一，可能不真正写入字段值
- 表现：升级日志无报错，但 `print_report_name` 仍是旧值
- 正确做法：用 `<function>` + 自定义方法

**陷阱 2：`write({'print_report_name': {lang: value}})` 传 dict 会被 `str()` 转字符串**
- `_String.write` 经 `convert_to_cache` 调 `str(value)`，dict 整体变成 `"{'zh_CN': '...', 'en_US': '...'}"` 字符串
- 表现：英文界面下文件名变成字典的字符串表示
- 正确做法：传字符串值，不传 dict

**陷阱 3：XML 数据加载默认上下文是 `en_US`，普通 write 只写当前 lang 的 JSONB key**
- `zh_CN` 翻译保留旧值，中文界面下 PDF 文件名仍是 `S00026`
- 表现：英文界面正常，中文界面不生效
- 正确做法：在 `_force_order_no_print_name` 内逐语言 `with_context(lang=code).write(...)`，每次只写一个 lang

**最终实现**（`models/ir_actions_report.py`）：

```python
def _force_order_no_print_name(self, expression):
    self.ensure_one()
    self.with_context(lang='en_US').write({'print_report_name': expression})
    for lang_code in self.env['res.lang'].search([]).mapped('code'):
        if lang_code == 'en_US':
            continue
        self.with_context(lang=lang_code).write({'print_report_name': expression})
    return True
```

**覆盖范围**（三个报表动作，缺一会出现某个菜单 PDF 文件名不变）：

| 报表动作 xmlid | report_name | 菜单项 |
|--------|--------|--------|
| `sale.action_report_saleorder` | `sale.report_saleorder` | 打印 → PDF 询价 |
| `sale.action_report_pro_forma_invoice` | `sale.report_saleorder_pro_forma` | 打印 → 形式发票 |
| `sale_pdf_quote_builder.action_report_saleorder_raw` | `sale.report_saleorder_raw` | 打印 → 报价单/订单 |

第三个由 `sale_pdf_quote_builder` 模块新建，与 `sale.action_report_saleorder` 是**两个不同的 record**（sale_pdf_quote_builder 还把后者的 name 改为 "PDF Quote"）。

**调试 SQL**：
```sql
SELECT imd.module, imd.name, r.print_report_name
FROM ir_act_report_xml r
JOIN ir_model_data imd ON imd.model='ir.actions.report' AND imd.res_id=r.id
WHERE r.model='sale.order' ORDER BY imd.module, imd.name;
```
期望：每条 JSONB 各语言值都含 `object.order_no or object.name`，不再有纯 `object.name` 或 dict 字符串。

### P2：客户门户预览 xpath 陷阱

**触发条件**：改 `views/portal_templates_inherit.xml` 时。

**陷阱 1：`hasclass('a') and hasclass('b')` 在 Odoo 19 xpath 中不工作**
- 报错："上级视图内找不到元素"
- 正确做法：两个谓词连写 `[hasclass('a')][hasclass('b')]`

**陷阱 2：位置索引 `t[2]` 在 extension 链中找不到**
- `sale.portal_my_home_menu_sale` 是 extension 模式，parent 是 `portal.portal_breadcrumbs`，应用 sale 那个 extension 之后的全树结构与原 XML 不完全对应
- 正确做法：用结构路径定位，如 `//li[hasclass('breadcrumb-item')][hasclass('active')]/t`（active li 内只有一个 `<t>`，无歧义）

**陷阱 3：`_compute_display_name` 优先 `order_no` 对门户模板无效**
- `sale.portal_my_home_menu_sale`（面包屑）与 `sale.sale_order_portal_content`（H2 标题）直接 `t-out sale_order.name`，绕过 display_name 计算
- 必须视图层显式覆盖，不能依赖模型层的 `_compute_display_name`

**最终 xpath**：
- 面包屑：`//li[hasclass('breadcrumb-item')][hasclass('active')]/t` → `t-out="sale_order.order_no or sale_order.name"`
- H2 标题：`//div[@id='introduction']//h2/em` → `t-out="sale_order.order_no or sale_order.name"`

### P3：升级失败后状态残留

**触发条件**：升级报错后再次升级时。

- Odoo 19 升级失败会回滚事务，但 `ir_module_module.state` 可能停在 `to upgrade`；重置：`UPDATE ir_module_module SET state='installed' WHERE name='sale_order_no';`
- 若之前用过 `<data noupdate="1">` 包裹 record 且首次写入失败，`ir_model_data` 可能残留 `noupdate=True` 标记但字段值未写入；清理：`DELETE FROM ir_model_data WHERE module='sale_order_no' AND model='ir.actions.report';` 后重新升级
- `migrations/` 目录已删除（仅支持全新安装），不要恢复

---

## 文件职责

| 文件 | 职责 |
|------|------|
| `__manifest__.py` | 模块元数据、依赖、数据文件声明 |
| `models/res_partner.py` | 客户编码格式校验与自动转大写 |
| `models/sale_order.py` | 订单编号字段定义、快照分配、避让重号、搜索与列表 API 重写、批量补号 |
| `models/ir_actions_report.py` | 扩展 `ir.actions.report`，提供 `_force_order_no_print_name` 按所有语言写入 `print_report_name` |
| `views/partner_views.xml` | 改写联系人 `ref` 字段标签为"客户编号" |
| `views/sale_order_views.xml` | 表单标题、列表列、搜索视图中的订单编号 |
| `views/portal_templates_inherit.xml` | 客户门户预览页面的面包屑与 H2 标题替换为 `order_no` |
| `data/sale_order_actions.xml` | 列表"生成订单编号"批量补号服务器动作 |
| `reports/report_saleorder.xml` | 打印报表正文用订单编号替换系统编号 + PDF 文件名 `<function>` 覆盖 |

---

## 常见扩展场景

### 改变编号规则

只改 `_build_order_no()`；分配与避让逻辑在 `_next_order_idx()`，不要在视图或报表层拼接编号。改规则必须同时检查 `_restore_index_from_order_no()` 的正则是否仍能还原流水号。

### 增加编号前缀/区分报价单与订单

优先在报表模板或展示层区分，不要改 `buyer_order_idx` 的分配逻辑，否则会破坏流水号连续性。

### 在其他报表中展示

优先用 `doc.order_no`；若为空应 fallback 到 `doc.name`，避免打印出空白编号。

### 批量导入历史单据

创建时直接写入 `order_no` 即可保留原编号，`_assign_order_fields()` 会跳过重算；编号符合 `客户编码+两位年份+流水号` 时自动还原 `buyer_order_idx` 以接续后续编号。导入后仍有缺号单据，用列表"生成订单编号"动作补号。

---

## 调试建议

- 编号未生成时，检查 `partner_id.ref` 是否为空或格式是否符合 `[A-Z]+`（空值会退化为 `UNK`）
- 流水号不连续是预期行为：作废单据同样占用流水号
- 手动导入的编号可能与自动分配冲突，分配时会自动递增避让，不必手工干预
- 出现"订单编号已被占用"提示时，检查是否重复录入或复制后未重新生成
- 若列表页仍显示 `SOxxxx`，检查 `web_search_read` 重写是否生效、模块是否已升级
- PDF 文件名问题与门户预览问题的调试方法见 L2 踩坑档案 P1/P2

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

新增字段改名、改类型等结构变更，必须配套 `migrations/<新版本>/pre-migration.py`，且迁移脚本要幂等。本模块当前已删除 migrations，仅支持全新安装；若未来恢复结构变更，需重新创建该目录。
