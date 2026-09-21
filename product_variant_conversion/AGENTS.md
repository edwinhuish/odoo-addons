# AGENTS 工作指引

> 本文档用于指导 AI 助手或新开发者在维护、扩展本 Odoo 模块时的行为规范和关键上下文。
> L1 约束段每次加载必读；L2 踩坑档案按主题触发条件加载。

---

## 模块定位

- 模块名：产品变体转换
- 技术目录：`product_variant_conversion`
- 新建模型：`product.variant.conversion`（转换台账）、`product.variant.lineage`（变体谱系）；**没有向导模型**（入口是保存拦截，不是按钮）
- 继承模型：`product.template`（保存拦截 + 转换核心）、`product.product`（来源字段）
- 自定义组件（前端模块）：`VariantConversionDialog`（归属确认弹窗）+ `FormController.onWillSaveRecord` 补丁
- 主依赖：`product`（**不依赖** `stock` / `sale` / `purchase` / `account`；这些模型只用来给弹窗补在手数量，运行时判断是否存在）
- 当前版本：`19.0.3.0.2`
- 命名说明：技术名用**名词短语** `product_variant_conversion`，与显示名（`Product Variant Conversion`）、
  模型 `product.variant.conversion`、字段 `variant_conversion_id` 一致；原用名 `product_variant_convert`
  （裸动词，且容易被读成「把变体转成组合产品」，而 Odoo 19 里 `product.combo` 是另一个概念）已在交付前改掉
- ⚠ **不要再改技术名**：Odoo 视改名为不同模块，装过的库必须「先卸载旧名、再安装新名」；
  交付前改名是唯一一次机会（见根 `AGENTS.md` 命名约定）

---

## L1：不可破坏的核心约束

每次修改代码必须保证以下行为不变。每条只列约束与违反后果，实现细节见 L2 踩坑档案。

1. **绝不删除、重建或归档既有变体**
   - 转换只能新增 `product.product`；改动前存在的每一条变体记录都必须原地保留（id 不变），并各自成为用户确认的那个组合
   - 违反后果：`stock.move.line` 因 `ondelete='cascade'` 被连带删除（库存历史直接丢失）；`sale.order.line` / `purchase.order.line` / `account.move.line` / `stock.quant` 因 `ondelete='restrict'` 导致删除失败后退化为归档旧变体 + 新建同组合变体，单据与库存从此对不上

2. **入口只能是「保存时检测」，不能加按钮 / 向导**
   - 属性变更的归属确认必须发生在保存流程里（前端 `onWillSaveRecord` + 服务端 `write` 双层），
     不允许再加产品表单按钮、也不允许用「先打开向导再改属性」的入口
   - 违反后果：用户在原生界面改属性仍会绕过确认，数据照样被删；或入口分裂成两套、行为不一致

3. **`write()` 的三种结局必须区分清楚**
   - ① 既有变体一条不少、也不新增变体 → 原样 `super().write(vals)`；
   - ② 会新增变体（组合数 > 既有变体数）→ 没有归属映射就**拦住保存**（抛错，由前端弹窗接管），有映射就先安全转换再落库；
   - ③ 会丢变体（`lost_variant_ids` 非空，或组合数 < 既有变体数）→ **直接拒绝**，绝不静默删除
   - 违反后果：把 ② 判成 ③ 会让主场景（加属性）永远弹不出确认框；把 ③ 判成 ①/② 会真删变体

4. **检测不能拿「原生写法」当判据**
   - 必须用 `_analyze_variant_conversion_write()`：带 `create_product_product=False` 只写配置（属性行 + ptav）、
     在保存点里跑一遍再回滚。原生写法在「加属性」时本来就会删掉既有变体，那是要防的结果
   - 违反后果：主场景被误判成「会丢变体」而拒绝；或为了测量而真的执行一次破坏性写入（虽然能回滚，但会引入 `stock.move.line` 级联删除、附件泄漏等副作用）

5. **每个既有变体都必须先锚定到它自己的归属组合，再调用 `_create_variant_ids()`**
   - 顺序固定：写配置（不碰变体）→ 预检（组合数、归属互不重复、默认组合不被排除）→ 逐个写
     `variant.product_template_attribute_value_ids` → `_create_variant_ids()`
   - 归属来自唯一的入口 `variant_mapping`（`{既有变体: 取值集合}`）；程序化调用留空时由
     `_get_variant_conversion_default_mapping()` 按「已有属性保持原取值、新加属性取第一个取值」补齐
   - 违反后果：某条既有变体的组合不匹配任何新组合，它就会被删 / 被归档，违反约束 1

6. **归属必须完整且不重复**
   - `_parse_variant_conversion_mapping()` 必须要求：每条既有变体恰好出现一次、取值必须存在；
     `_check_variant_conversion_anchors()` 必须拒绝「两条既有变体占同一个组合」
   - 违反后果：漏掉一条既有变体就会让它被删；重复会让 Odoo 的组合匹配字典碰撞，其中一条被删且谱系记错来源

7. **整个转换必须在 `savepoint` 内，且带前置校验 + 后置断言**
   - 后置断言必须包含：每条既有变体仍存在且启用、它携带的组合等于自己的归属组合、变体数等于用 Odoo 规则算出的预期数
   - 违反后果：出现一致性异常时数据库停留在半转换状态，比转换失败更难收拾

8. **只允许追加取值，不允许删除**
   - 删取值 / 删属性行一律在 `write()` 里被拒绝（`lost_variant_ids` / 组合数变少）
   - 违反后果：删取值会让 Odoo 归档 / 删除对应 ptav 并牵动变体，把删除风险重新引入

9. **归属与属性变更必须同一次写库**
   - 弹窗确认的归属通过技术字段 `variant_conversion_mapping` 与用户那组属性命令一起提交；
     `write()` 先写配置、再做安全转换、最后写其余字段，失败整单回滚；技术字段写完即清空
   - 违反后果：出现「属性改了但归属没落库」或反之的半成品状态；技术字段残留还会污染下一次保存

10. **`create_product_product=False` 的写入必须直接放行**
    - `write()` 的第一道判断必须包含 `not self.env.context.get("create_product_product", True)` → `super().write(vals)`；
      这是模块自己的「只写配置、不碰变体」模式（分析用的一次试写、转换内部写属性行都走它）
    - 违反后果：无限递归（试写会再次进入拦截逻辑），直接 `RecursionError`

11. **归档变体必须先拒绝转换**
    - `_check_variant_conversion_allowed()` 必须拒绝带归档变体的产品（提示先恢复或删除）
    - 违反后果：`_create_variant_ids` 会自动激活组合仍然可能的老变体，转换悄悄把归档变体复活

12. **依赖最小化：只能依赖 `product`**
    - 需要 `stock` / `sale` / `purchase` / `account` 的信息时，一律用 `model_name in self.env` +
      `check_access_rights("read", raise_exception=False)` 降级；测试里 `is_storable`（stock 提供）也要先判断字段是否存在
    - 违反后果：只装库存的库装不上本模块，或弹窗/台账因权限不足直接报错

13. **转换逻辑只能有一处实现**
    - 核心逻辑留在 `product.template._convert_to_multi_variant()`，`write()` 只做判定与编排；
      禁止在前端或另一个方法里另写一份写库逻辑
    - 违反后果：两处实现分叉，绕过校验的路径重新出现

14. **所有用户可见文本源语言为英文（`en_US`）**
    - Python / XML / JS 中不写中文界面文案；中文只放在 `i18n/zh_CN.po` 的 `msgstr`
    - 违反后果：默认英文界面出现中文；或重复 `msgid` 导致整份 po 解析失败

---

## 国际化约束（i18n）

每处用户可见文本都必须满足（通用规则见根 `AGENTS.md` 第 4 节）：

1. **源语言是英文（`en_US`）**：Python / XML / JS 里一律写英文；中文只能出现在 `i18n/zh_CN.po` 的 `msgstr` 里。
2. **可翻译入口正确**：见根 `AGENTS.md` 4.2「可翻译入口对照表」（`model:` / `model_terms:` / `code:` 三类键名）；前端术语走 `code:addons/<module>/static/src/js/<file>.js:0` 与 `code:addons/<module>/static/src/xml/<file>.xml:0`。
3. **禁止拼接句子**：占位符统一 `%(name)s`。弹窗里夹在元素中的句子（如「还差 N 条」）**必须在 JS 侧用 `_t()` 拼好再 `t-esc`**，否则模板会把句子切成碎片；
   唯一允许的拼接是「属性: 取值」这类数据标签。
4. **`<span>` / `<option>` 等内联元素整块成术语**：见 L2 P2 陷阱 1；选项文案与提示句一律用 JS getter + `_t()`，不要写成模板里的文本节点。
5. **收尾动作**：改英文源文本 → 同步 `i18n/zh_CN.po` → 提升版本 → `-u` 升级 + 强刷浏览器，中英文各验一遍。
6. **代码注释保持中文**，不为 i18n 改英文。
7. **应用列表（Apps）元数据必须有中文**：改 `__manifest__.py` 的 `name` / `summary` / `description` 后，必须同步
   `model:ir.module.module,shortdesc|summary|description:base.module_product_variant_conversion` 三条
   （`description` 条的 `msgid` 必须等于 `textwrap.dedent(manifest["description"])`）；分类沿用官方的 `Inventory/Product`，
   自定义段 `base.module_category_inventory_product` 的「产品」译文与其它产品类模块**合并成同一条 `msgid`**。
   见根 `AGENTS.md` 4.8。
8. **每次改完视图 / 文案后，用官方导出重建 po 而不是手改**（见 L2 P2 的自查方式）。

---

## 文件职责

| 文件 | 职责 |
|------|------|
| `__manifest__.py` | 模块元数据、版本、依赖（仅 `product`）、数据文件与前端资源登记（assets 里三个文件） |
| `models/product_template.py` | 保存拦截 `write()`、预览 RPC `get_variant_conversion_preview()`、试写分析 `_analyze_variant_conversion_write()`、归属解析、核心转换 `_convert_to_multi_variant()`、校验与断言、谱系写入、台账入口 `action_open_variant_conversions()` |
| `models/product_product.py` | 变体上的可搜索来源字段 `variant_conversion_id` / `variant_origin_id` |
| `models/product_variant_conversion.py` | 转换台账与变体谱系两个模型 |
| `static/src/js/variant_conversion_form_patch.js` | patch `FormController.onWillSaveRecord`：保存前检测、拦保存、弹窗、把归属放进本次 `changes` |
| `static/src/js/variant_conversion_dialog.js` | 归属确认弹窗组件（逐组合选「由谁继续承载」+ 供应商价格勾选框 + 文案 getter） |
| `static/src/xml/variant_conversion_dialog.xml` | 弹窗模板 `product_variant_conversion.VariantConversionDialog` |
| `views/product_template_views.xml` | 产品表单的技术字段（不可见）、`Conversions` 智能按钮、**Variant Lineage** 页；产品搜索筛选 |
| `views/product_product_views.xml` | 变体表单的来源分组、变体列表可选列、变体搜索（按来源变体 / 所属转换） |
| `views/product_variant_conversion_views.xml` | 转换台账的列表 / 详情视图与动作 |
| `security/ir.model.access.csv` | 两个模型的访问规则（`base.group_user` 与 `product.group_product_variant`） |
| `tests/test_product_variant_conversion.py` | 17 项自动化测试（拦截、预览、归属确认、拒绝删减、台账与谱系、库存与订单行不变） |
| `i18n/zh_CN.po` | 简体中文译文（源语言 `en_US` 写在代码里，无需 `en_US.po`；`i18n/` 不进 `data`）；含应用列表元数据条目 |
| `README.md` | 用户可见功能、字段表、归属怎么指定、被拒绝的情况、已有业务数据处理、验证清单 |
| `CHANGELOG.md` | 逐版本「变更 / 影响 / 文档」记录 |
| `AGENTS.md` | 本文件：核心约束、i18n 规则、文件职责、踩坑档案、变更规范 |

---

## L2：踩坑档案

> 按主题归档的实现陷阱。L1 约束标注的触发条件下必读，其他时候按需查阅。

### P1：变体生成、归属与保留原记录（改 `models/product_template.py` 前必读）

**触发条件**：任何触碰 `attribute_line_ids` / `_create_variant_ids` / `product.product.write` / 归属判定的改动。

**四条已核实的 Odoo 19 事实**（对照镜像内 `odoo/addons/product/models/`）：

1. `product.template.write()` 里触发变体生成的判断是
   `if self.env.context.get("create_product_product", True) and 'attribute_line_ids' in vals: self._create_variant_ids()`
   → 带 `create_product_product=False` 写 `attribute_line_ids` 不会生成变体。
   同一开关在 `product.template.attribute.line._update_product_template_attribute_values()` 末尾也有一份，
   所以 ptav 的增删同样不会顺带生成变体。
2. `_create_variant_ids()` 先算 `existing_variants = {variant.product_template_attribute_value_ids: variant}`，
   再用 `_filter_combinations_impossible_by_config()` 遍历所有可能组合：命中字典的进 `variants_to_activate`（复用），
   没命中的进 `variants_to_create`；最后 `variants_to_unlink += all_variants - current_variants_to_activate`。
   → 「把每条既有变体锚定到它自己的组合」= 让它们全部落进 `variants_to_activate`，它们就不会被删。
   字典键与查找值都是 **recordset**（`concat` 后的 `product.template.attribute.value`），
   靠 `BaseModel.__hash__ = hash((self._name, frozenset(self._ids)))` 匹配，顺序无关。
   **注意**：匹配用的组合元组每个属性只有一个取值，所以锚定值必须是「每属性恰好一个」。
3. `product.product.unlink()`：`if self.env.context.get('create_product_product') is False: return super().unlink()`
   —— 即绕过「删掉最后一个变体时连带删模板」的逻辑。**不要**在转换流程里带这个上下文去删变体。
4. `_create_variant_ids()` 里的 `single_value_lines` 分支：只有 1 个取值的属性行会被自动写到所有变体上
   （Odoo 保证「加单取值属性不重建变体」的机制）。因此「只加一个取值的属性」是一次合法转换：
   变体数不变、没有新变体，但每条既有变体都会带上这个取值 —— 也正是判断「需不需要弹窗」的依据
   （组合数变多才需要确认归属）。

**为什么不能拿「原生写法」当判据**：原生写法在「加属性 / 加取值」时本来就会把既有变体删掉重建
（它们不再匹配任何新组合）。所以分析用的是 `create_product_product=False` 的试写：
只写配置、ptav，既有变体完全不受影响，也没有「先删再回滚」带来的级联删除 / 附件残留风险。

**归属与新变体来源的判定**：

- 归属组合 = 「该变体在改动前就存在的属性行上的取值」∪「归属表里为本次处理的属性指定的取值」；
  改动前不存在的属性行（本次新加）必须由归属表指定（`_get_variant_conversion_anchor_values`）。
- 新变体的来源（谱系 `origin_variant_id`）= 它在**改动前就存在的属性轴**上的取值，与哪条既有变体一致；
  判定不唯一时宁可留空（`_create_variant_conversion_lineage`）。
- 「能不能再锚定」（会不会丢变体）= 变体现有取值里，凡属性还在新配置中的，其取值必须仍然保留；
  属性行被删掉本身不影响（那只是少一个属性轴），但组合数变少（< 既有变体数）同样会丢变体 → 一并拒绝。

**最终实现**（`models/product_template.py` 的 `write()`）：

```python
if "attribute_line_ids" not in vals or not self.env.context.get("create_product_product", True):
    return super().write(vals)          # 模块自己的「只写配置」模式，必须放行（否则递归）
...
affected = self._analyze_variant_conversion_write(vals["attribute_line_ids"])
if 会丢变体:  raise UserError(...)
if 不新增变体:  return super().write(vals)
if 没有归属映射:  raise UserError(...)     # 前端弹窗接管
self.with_context(create_product_product=False).write({"attribute_line_ids": ...})  # ① 先写配置
self._convert_to_multi_variant(..., previous_attribute_lines=..., added_attributes=...)  # ② 再安全转换
return super().write(其余字段)              # ③ 其余字段照常落库
```

**维护提醒**：

- `_filter_combinations_impossible_by_config()` 与 `attribute_line._without_no_variant_attributes()` 是 Odoo 内部方法，
  Odoo 升级需回归（后置断言用「计算出的预期变体数 == 实际变体数」把这类 API 变化暴露成明确报错）。
- ③ 那一步会把属性行排除在外（`attribute_line_ids` 已在 ①②写过了）：再写一次会让 Odoo 为同一个属性
  建出**重复的属性行**。
- ①②之后调用的转换必须带 `previous_attribute_lines` / `added_attributes`（改动前快照），
  否则谱系会拿「改动后的属性轴」去判断来源，`variant_origin_id` 会全部留空。

### P2：i18n 术语抽取与 po 维护（改视图 / 文案 / po 时必读）

**触发条件**：新增 / 修改视图节点、模板文本、字段文案、Python `_()`、JS `_t()`、`i18n/zh_CN.po` 时。

**陷阱 1：内联元素整块成术语**
- 现象：`<span class="text-muted">Adds variants…</span>` 抽取出的术语是**含标签的整段 XML**，按纯文本写的 `msgid` 对不上，界面永远显示英文。
- 根因：`span` / `b` / `i` / `kbd` / `code` / `option` / `select` 等在 `odoo/tools/translate.py` 的 `TRANSLATED_ELEMENTS` 里，
  该元素及其内容会被当成**一个**术语；`div` / `p` / `th` / `td` 不在其中，文本节点才是独立术语（带 `t-*` 属性的元素也会退化成独立文本节点）。
- 正确做法：说明性文字放在 `div` / `p` 里；弹窗里的选项文案、提示句一律用 JS getter + `_t()`（再 `t-esc`），不要写成模板文本节点。

**陷阱 2：句子被元素切碎**
- 现象：「还差 N 条」写成 `还有 <t t-esc="n"/> 条没指定` 会变成三个术语碎片。
- 正确做法：JS 侧 `_t("%(count)s existing variants still have no combination", {count})` + `t-esc`。

**陷阱 3：字段级 `domain` 会被 Odoo 19 应用到服务端查询**
- 现象：`domain=[("id", "in", "allowed_value_ids")]`（list 形式）读该字段时报
  `invalid input syntax for type integer: "allowed_value_ids"`。
- 根因：`fields_relational.py::_get_query_for_condition_value()` 会把字段 `domain` 注入 comodel 查询，
  而 `get_comodel_domain()` 只对**字符串** domain 返回 `Domain.TRUE`（字符串型 domain 是「只给客户端求值」的约定）。
- 正确做法：带字段引用的 domain 一律写成**字符串**；服务端安全靠自己的校验兜住。

**陷阱 4：`product.attribute.value.display_name` 已经是「属性: 取值」**
- 正确做法：拼「属性: 取值」时取值用 `.name`，属性用 `.display_name`。

**陷阱 5：模型 `_description` 与模块名同字面会撞 `msgid`**
- 现象：`check_repo.py` 报重复 `msgid`（模块名要进「应用」列表，模型描述也要翻译，同一个 `msgid` 却想要两种译文）。
- 正确做法：让模型 `_description` 与 manifest `name` 措辞不同（本模块用 `Variant Conversion Log`）；
  实在要同字面时把两条 `#:` 引用**合并**成一条。

**自查方式**（比 `task check` 更彻底）：

```bash
# 1) 用官方 CLI 导出术语骨架（含 #: 引用，msgid 与源码逐字符一致；JS _t 与模板文本都会带上）
docker compose -f .dev/compose.yml run --rm -T odoo \
    odoo i18n export -d dev -l pot -o /mnt/extra-addons/product_variant_conversion/_export.po product_variant_conversion
# 2) 核对 _export.po：新增 / 改过措辞的条目补译文，然后按 msgid 合并回 i18n/zh_CN.po
#    （元数据三条要单独手写，导出向导不会带出来，见根 AGENTS.md 4.8）
```

预期结果：只有 `Created by` / `Created on` / `Display Name` / `ID` / `Last Updated by` / `Last Updated on`
（标准审计字段标签，界面上不显示）不需要译文。

**每次改完必须跑**：`task check` → `task update` → `task i18n -- zh_CN product_variant_conversion`（确认 po 能正常导入）→ 强刷浏览器。

### P3：Odoo 19 的字段与命名坑（新增字段 / 模型时必读）

**触发条件**：给模型加字段、加 m2m、给 `product.product` / `product.template` 加字段时。

**陷阱 1：m2m 自动关系表名过长**
- 现象：`ValidationError: Table name '…' is too long`，模块直接装不上。
- 根因：自动表名是 `%s_%s_rel`（模型 `_table` + comodel 表名），PostgreSQL 标识符上限 63 字节。
- 正确做法：模型名 + comodel 名较长时显式指定 `relation=`。

**陷阱 2：o2m 子行 create 不会自动补父级必填字段**
- 现象：`null value in column "product_tmpl_id" ... violates not-null constraint`。
- 正确做法：`product.variant.conversion.lineage_ids` 的行里显式带 `product_tmpl_id`。

**陷阱 3：`is_storable` 属于 `stock` 模块**
- 正确做法：写入前先判断 `"is_storable" in model._fields`（测试里的 `_create_product` 已这么做）。

**陷阱 4：`product.product` 通过 `_inherits` 继承 `product.template` 的字段**
- 现象：给 `product.template` 加的字段会同时出现在 `field_product_product__…` 上（导出 po 时能看到两条引用）。
- 正确做法：正常现象，别去「修」；给模板加字段时注意不要与变体上已有字段语义冲突。

### P4：保存拦截与弹窗（改 `static/src/**` 或 `write()` 时必读）

**触发条件**：改保存拦截、弹窗、归属载荷格式时。

**机制（已核实 Odoo 19 源码）**：

- `web/static/src/model/relational_model/record.js::_save()` 里有
  `const canProceed = await this.model.hooks.onWillSaveRecord(this, changes); if (canProceed === false) return false;`
  → `onWillSaveRecord(record, changes)` 是官方保存前钩子：**返回 false 即阻止保存**，`record` 保持 dirty（用户的编辑不会丢）。
- 同一个 `_save()` 紧接着 `await this.model.orm.webSave(this.resModel, [this.resId], changes, kwargs)`
  → **`changes` 就是发给 `web_save` 的 `vals`**，所以在钩子里往 `changes` 里塞字段是官方支持的「随本次保存提交额外数据」写法。
- `FormController` 在 `getModelParams` 里把 `this.onWillSaveRecord.bind(this)` 注册成该钩子
  → patch `FormController.prototype.onWillSaveRecord` 即是官方扩展点（不要 patch `Record._save`）。

**本模块的用法**：

- 只在 `record.resModel === "product.template"`、有 `resId`、且本次 `changes` 里含 `attribute_line_ids`、
  且尚未带 `variant_conversion_mapping` 时介入；
- 调 `orm.call("product.template", "get_variant_conversion_preview", [[resId], changes.attribute_line_ids])`
  （把服务端原本要写的那组命令原样过去，服务端在保存点里试写 + 回滚后给出结论）；
- `preview.blocked` → 提示并 `return false`；`preview.required` → 弹窗并 `return false`；
- 弹窗确认后：`await record.update({variant_conversion_mapping: JSON.stringify(payload)})` 再 `this.model.save()`
  → 第二次保存因为 `changes.variant_conversion_mapping` 已存在而直接放行，服务端走安全转换。

**陷阱 1：递归**
- 服务端的 `_analyze_variant_conversion_write()` 与 `_convert_to_multi_variant()` 都会用
  `with_context(create_product_product=False)` 写 `attribute_line_ids`，而 `write()` 的第一道判断必须把这种写入放行，
  否则会无限递归（实测 `RecursionError`，且栈里全是 `sql_db.py` 的 savepoint，很难看出根因）。

**陷阱 2：弹窗取消必须真的不保存**
- 「先弹窗、保存照做」是错的：钩子必须返回 `false`（本次保存不执行），把「保存」这个动作交给用户确认后的第二次保存；
  弹窗的 `onConfirm` 才去 `record.update(...) + this.model.save()`。取消 / 直接关掉弹窗时什么都不做即可（表单保持 dirty）。

**陷阱 3：字段必须在视图里存在**
- `record.update({variant_conversion_mapping: ...})` 要求该字段在表单视图的 activeFields 里
  → `views/product_template_views.xml` 里以 `invisible="1"` 登记；否则 OWL 侧会当作未知字段。

**陷阱 4：`assets` 新增文件必须 `-u`**
- 本模块的三个前端文件登记在 `__manifest__.py` 的 `assets.web.assets_backend`；新增 / 改文件名后必须
  `-u`（或重启进程）+ 强刷浏览器，否则前端钩子不会生效（表现就是「点了保存但没弹窗，只报错误提示」）。

**陷阱 5：保存入口不是 `this.model.save()`（实测踩过）**
- 现象：弹窗点确认后控制台报 `Uncaught Promise > this.model.save is not a function`。
- 根因：`RelationalModel` 上**没有** `save`。保存入口在 **Record** 上（`this.model.root.save(options)`），
  控制器层还有 `FormController.save(params)`（内部 `record.save({ onError: this.onSaveError, ...params })`，
  并尊重 `props.saveRecord` / `props.onSave`）。
- 正确做法：在 `onWillSaveRecord` 的弹窗回调里用 `await this.save()`（`this` 是 FormController）；
  **不要**用 `this.model.save()`，也不要直接 `this.model.root.save()`（会绕过控制器的错误处理）。
- 参考：`web/static/src/views/form/form_controller.js` 里 `save()` / `create()` / `saveButtonClicked()`
  统一走 `this.model.root.save({ onError })`。

**陷阱 6：承载前端回传数据的技术字段必须 `force_save="1"`**
- 现象：弹窗确认后保存又被拦一次、弹窗反复出现，且没有任何报错。
- 根因：`Record._getChanges()` 对「在 activeFields 里、但 `_isReadonly(fieldName)` 为真且没标 `forceSave`」
  的字段直接 `continue`，该字段不会进 `changes`，也就不会随 `webSave` 提交。
- 正确做法：`variant_conversion_mapping` 在视图里写 `invisible="1" force_save="1"`（模型字段本身保持可写）。
  改这个字段的属性（尤其加 `readonly`）前，先确认 `changes` 里还能看到它。

### P5：业务场景、数据流与一致性边界（评估完整性 / 排障时读）

**触发条件**：判断「某个改动会不会被本模块拦住」、评估业务场景完整性、回答「库存 / 价格为什么没跟着走」时。
数据流时序图见模块 `README.md` →「数据流」；这里只放维护者视角的判据、同步规则与缺口清单。

**覆盖矩阵**（✅ = 有自动化测试锁住）：

| 场景 | 结局 | 处理 | 测试 |
|------|------|------|------|
| 单变体加多取值属性（1→N） | required | 弹窗确认归属 | ✅ |
| 多变体加新属性（N→N×M，主场景） | required | 弹窗确认归属 | ✅ |
| 给已有属性追加取值 | required | 弹窗确认归属 | ✅ |
| 加单取值属性 / 加 no_variant 属性 / 重提同配置 | 不涉及变体 | 原样 `super().write()` | ✅ |
| 删取值 / 删属性行 | blocked | 拒绝保存 | ✅ |
| 组合数变少（改动后被排除规则过滤） | blocked | 拒绝保存 | — |
| 多记录批量写入 | 视情况 | 会动到变体 → 拒绝（表达不了逐条归属）；不动到变体 → 放行 | — |
| 按需生成变体（dynamic）的属性 | blocked | 拒绝，要求改为「立即」 | — |
| 带归档变体的产品 | blocked | 拒绝，要求先恢复 / 删除 | — |
| combo 产品 | blocked | 拒绝 | — |

**判据只有一条**：组合数 > 既有变体数 ⇒ 一定出现新记录 ⇒ 才需要归属确认。组合数不变（单取值属性、no_variant 属性、重提同配置）就没有可确认的东西。

**同步规则（写文档 / 排障时别搞错）**

- 库存：**完全不动**（`stock.quant` / `move.line` / `move` / `lot` / `orderpoint` 都留在各自那条原记录上）。
- 模板级字段（`list_price`、`taxes_id`、`uom_id`）天然覆盖全部变体；ptav 级（`price_extra`）随取值走。
- **变体级字段不会自动继承**：`standard_price`（成本）→ 新变体为 0（模板侧那个只是单变体时的 compute/inverse 通道）；
  `product.pricelist.item`（`applied_on=0_product_variant`）→ 不覆盖新变体；`supplierinfo` → 只有勾选共享才生效。
- ⚠ **共享供应商价格会抹平变体级价差**：同一供应商对不同变体给不同价时，共享后全是模板级同级记录，
  采购取价按 `price_discounted → sequence → id`（`product.product._select_seller`）只取一条，另一条静默失效。
- `default_code` / `barcode` → 新变体为空。

**已识别的缺口**（明确记录在案的边界，不是「未知 bug」；对应需求见仓库 `TODO.md` → 待办池 T-016 ~ T-020）

1. **绕过路径（最重要）**：归属确认挂在 `product.template.write()` 上，但
   `product.template.attribute.value.unlink()` 会 `self.ptav_product_variant_ids._unlink_or_archive()` —— **直接删 / 归档变体**；
   `product.template.attribute.line.write()` 又会自己调 `product_tmpl_id._create_variant_ids()`。
   于是「在属性主数据里删取值」「直接写属性行」这两条路**不经过本模块**，照样丢变体。
2. **成本价不继承**（`standard_price` 是变体级字段）。
3. **供应商价格共享抹平价差**（见上）。
4. **谱系行随变体级联删除**：`product.variant.lineage` 的两个变体字段都是 `ondelete='cascade'`，删变体即丢审计行（台账本身不受影响）。
5. **组合枚举无前置上限**：`_get_variant_conversion_combinations()` 在 `product.dynamic_variant_limit` 检查之前就枚举全部组合，超大配置会先枚举再拒绝。
6. **试写在加锁之前**：`_analyze_variant_conversion_write()` 不带 `FOR UPDATE`，并发下分析结果可能过期 ——
   由 `_check_variant_conversion_anchors()` 与后置断言兜住（拒绝并整单回滚），不会写坏数据，但报错会指向「组合被排除 / 变体数不符」。
7. **弹窗未展示在手数量**：预览已返回 `variants[].on_hand`，模板只渲染了 `label`。
8. **前端无自动化测试**：17 项都是服务端测试，弹窗与钩子靠手工验证（见 `README.md` →「验证清单」）。
9. **有代码无测试的服务端分支**：多记录写入、combo、归档变体、dynamic 属性、组合被排除、无 `stock` / 无读权限时的降级。

**扩展点**

| 想扩展什么 | 在哪扩 |
|-----------|--------|
| 默认归属规则 | override `_get_variant_conversion_default_mapping()` |
| 弹窗里的新选项 | `variant_conversion_dialog.js` 加选项 → `_parse_variant_conversion_mapping()` 解析 → `write()` 落地（现有 `share_vendor_prices` 就是范例） |
| 转换后的数据补全（成本 / 参考号 / 图片 / 价格表规则） | 目前**没有正式钩子**，只能插在 `_create_variant_conversion_lineage()` 之后；`T-020` 要补 |
| 批量转换 | 新增独立入口（列表按钮 / 服务器动作），逐产品调用 `_convert_to_multi_variant()`，**各自包一个保存点** |
| 拦截「属性主数据」路径 | 在 `product.template.attribute.value` 上加同样的判定（`T-017`） |

**维护提醒**

- **任何新增的「改属性」入口都必须经过 `product.template.write()`**，否则等于绕过 L1 约束 1。
- 升级 Odoo 必须回归的内部 API：`_filter_combinations_impossible_by_config()`、`_without_no_variant_attributes()`、
  `_create_variant_ids()`、`FormController.onWillSaveRecord`、`Record._getChanges()` 的 `forceSave` 语义、
  `product.template.attribute.value.unlink()` 里的 `_unlink_or_archive()` 行为。

---

## 常见扩展场景

### 想支持「给产品删属性 / 删取值」

不要在现有流程上开口子（会破坏 L1 约束 8 的推理链）。删取值会让 Odoo 归档 / 删除 ptav 并牵动变体，
属于另一个风险等级的功能，要做就得先回答：被删取值的库存与单据往哪条变体上挪？想不清楚就不要做。
当前设计给用户的路是「先归档 / 删除不想要的变体，再改属性配置」。

### 想在弹窗里加选项（例如同时调整价格表规则）

- 前端：在 `variant_conversion_dialog.js` 加字段 + 在载荷里带出去（参考 `share_vendor_prices`）；
- 服务端：在 `_parse_variant_conversion_mapping()` 里解析并返回，`write()` 负责落地。
- 注意载荷格式变化后要同步改 `_parse_variant_conversion_mapping()` 的校验分支。

### 想批量转换多个产品（列表 / 服务器动作）

当前 `write()` 对多记录写入仅做安全判定（会动到变体就拒绝）。要支持批量，应新增一个独立入口
（服务器动作 / 列表按钮），逐条产品调用 `_convert_to_multi_variant()` 并各自包一个保存点：
不要在一个保存点里转换多个产品（一个失败会连累全部，且报错无法定位到具体产品）。

---

## 调试建议

- **点保存没弹窗、只报错**：前端资源没生效（没 `-u` 或没强刷浏览器），按报错提示强刷一次；报错文案就是这条线索。
- **弹出了归属框但默认归属很奇怪**：默认归属来自 `_get_variant_conversion_default_mapping()`（已有属性保持原取值、新加属性取第一个取值）；确认预览里的 `combinations` 是否与 `_get_variant_conversion_combinations()` 的输出一致。
- **报「属性重复 / 取值不能删除 / 会删变体」**：都是 `write()` 的前置校验，报错不改库；按提示先处理变体再改属性。
- **报「变体数不符 / 原变体不见了 / 没带上该组合」**：后置断言触发，整单已回滚。重点看产品的属性排除配置
  （产品表单属性行的「Configure」弹窗里可以配置取值互斥）与归属表是否有重复。
- **`RecursionError`**：`write()` 的第一道判断丢了 `create_product_product` 放行分支，见 P4 陷阱 1。
- **谱系里 `variant_origin_id` 全是空**：`_convert_to_multi_variant()` 没拿到 `previous_attribute_lines`
  （改动前快照），来源判定用了改动后的属性轴，见 P1「维护提醒」。
- **中文界面还是英文**：先 `task i18n -- zh_CN product_variant_conversion` 强制刷新译文（元数据条目 `noupdate=True`），
  再强刷浏览器；后端字段标签刷新页面即可。
- **预览里的在手数量是 0**：没装 `stock`，或当前用户没有 `stock.quant` 的读权限（设计如此）。

---

## 变更记录规范

每次功能修改后必须更新：
- `__manifest__.py` 的 `version`（遵循 `19.0.x.y.z`）
- `CHANGELOG.md` 的版本说明（变更 / 影响 / 文档）
- 本 `AGENTS.md` 的相关约束（若涉及行为变更）
- `README.md` 的功能说明（若涉及用户可见功能）

版本号建议：
- 破坏性变更或架构调整：升第二位，如 `19.0.3.0.0`
- 功能新增：升第三位，如 `19.0.1.1.0`
- 修复或文档：升第四位，如 `19.0.1.0.1`
