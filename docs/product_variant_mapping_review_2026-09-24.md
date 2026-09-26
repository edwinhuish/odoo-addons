# 多变体映射功能线复盘（`product_variant`，19.0.7.0.0 → 19.0.13.0.1）

> **定位**：本文件是「改属性时怎么安置既有变体」这条功能线的一次**操作复盘 + 决策记录**，
> 按「目标 → 步骤 → 技术要点 → 问题与解法 → 结果」组织，便于后续查阅与复盘。
>
> **权威细节不在这里**：使用者视角看 `product_variant/README.md`，逐版本变更看
> `product_variant/CHANGELOG.md`，约束与踩坑（陷阱 8–23）看 `product_variant/AGENTS.md`。
> 本文件只做汇总、索引与横切归纳，冲突时以模块三件套为准。
>
> **范围**：`19.0.7.0.0`（模块改名 + 映射表初版，已随 `cf0d463` 提交）→ `19.0.13.0.1`。
> 本轮（同日 19:35 / 20:55）交付 `19.0.7.0.1` → `19.0.13.0.1`，共 17 个版本、5 条提交。
>
> **后续迭代（不在本文件范围内）**：`19.0.13.0.2` ~ `19.0.13.0.6` 是这条功能线的**第二轮**
> （保存死锁 → 删唯一属性复用 → 守卫放行 → 面板换行 → 核查修订），操作记录见
> [`product_variant_mapping_change_record_2026-09-24.md`](product_variant_mapping_change_record_2026-09-24.md)
> 的「第二轮」一节；新增的约束与踩坑见 `product_variant/AGENTS.md` 陷阱 **21–23**。本复盘不重复收录。
>
> 规范依据：根 [`AGENTS.md`](../AGENTS.md) 第 7/8 节、[`DOCS_TEMPLATE.md`](../DOCS_TEMPLATE.md)、
> [`docs/README.md`](README.md)。

---

## 0. 一页速览

| 项 | 内容 |
|---|---|
| 功能线 | 产品表单「属性与变体」页：改属性时用一张**映射表**把既有变体安置到新的属性组合上，不许静默丢变体 |
| 涉及模块 | `product_variant`（原 `product_variant_conversion`，`19.0.7.0.0` 改名） |
| 版本变化 | `19.0.7.0.0` → **`19.0.13.0.1`**（17 个迭代版本；+z 修复 12 个、+y 功能 5 个） |
| 本轮提交 | `2e2876d`（实现 + 测试）、`1734e5c`（模块文档）、`8898deb`（根文档）、`7d6e995`（面板定稿）、`9e6f4b4`（面板文档） |
| 关键技术 | OWL 字段 widget 注册契约、`record.getChanges()` 读编辑态、编辑期零 RPC、`FIELD_IS_DIRTY` 脏状态广播、`Record._save()` 早退绕过钩子、视图继承删节点 |
| 修复的真实故障 | 11 处（含 5 处「整页打不开 / 一点就报错」），全部有可复现现象与根因 |
| 自动化测试 | 63 项服务端（含 4 项前端静态检查）+ 15 项纯函数离线自测；`task check` 无失败项 |
| 改名的数据影响 | **零迁移**（模型名 / 字段 / 列名 / xmlid 全未动），已装库只需三条 SQL + `-u`，不需卸载重装 |
| 待目标环境验证 | 映射表交互（面板渲染 / 下拉禁用 / 保存拦截 / 显式保存与丢弃）、中文界面文案（清单见第 5.4 节） |
| 工作树 | 本轮 5 条提交已落库，工作树干净 |

> **一句话概括**：把「改属性会删掉并重建变体」这件事，做成 **一张组合为行、Variant 下拉为列的映射表**——
> 前端把属性组合**穷举展示**给人分配，后端仍按属性规则**按需预建**（「立即」轴全展开、「按需生成」轴只建
> 被既有变体认领的取值），既有变体一律按归属复用、绝不静默丢弃；映射一改就出现
> **Save manually / Discard all changes**，未映射的变体不放过保存，且不会被 Odoo 的自动保存绕过去。

---

## 1. 主要目标

### 1.1 业务背景

Odoo 原生的行为是：改产品属性（删取值、删属性、加属性）时会**删掉并重建变体**，
变体上的库存、单据行、价格、供应商信息随之丢失。`product_variant_conversion` 这个模块的存在，
就是把这件危险操作变成「可确认的转换」：既有变体按归属继续存在（原记录、原 id）。

### 1.2 本轮目标（按提出顺序）

| # | 目标 | 落地版本 |
|---|---|---|
| 1 | 模块改名 `product_variant_conversion` → `product_variant`，并给出**已装库的原地升级路径** | `19.0.7.0.0` |
| 2 | 用「属性 ↔ 变体」映射表取代归属弹窗：属性行下方常驻，能看出哪些变体缺取值（未映射） | `19.0.7.0.0` |
| 3 | 映射表**必须真的能用**（渲染、可编辑、随时刷新、不崩页面） | `19.0.7.0.1` – `19.0.8.0.4` |
| 4 | 一个组合只能被一条变体占用；重复占用要能看出来 | `19.0.9.0.0` |
| 5 | 映射表结构反向：**组合为行、为每个组合选变体**（可清空、可重排） | `19.0.10.0.0` |
| 6 | 前端**穷举展示**全部属性组合，后端**保持按需生成** | `19.0.11.0.0` → `19.0.12.0.0` |
| 7 | 已被别的行选走的变体在下拉里禁用（换位置要显式释放） | `19.0.12.0.1` |
| 8 | 面板定稿：加标题、移除原生那句已不成立的警告、未映射不放行、显示 **Save manually / Discard all changes** | `19.0.13.0.0` / `19.0.13.0.1` |

### 1.3 验收口径（用户视角可观察）

- 打开产品表单 →「属性与变体」页 → **不报错**、面板在属性行下方独占一行、有标题。
- 改属性 → 面板刷新出组合表，**缺取值的变体被点名**，保存被拦。
- 给每个组合挑好变体（或确认新建）→ 保存成功，既有变体保持原 id，台账 / 谱系各记一条。
- 改过映射 → 出现 **Save manually / Discard all changes**；点丢弃后**属性行与映射一起回到改动前**。

---

## 2. 关键步骤（按操作流程）

### 2.1 第一步：模块改名（`19.0.7.0.0`，提交 `cf0d463`）

**做法**：**只改技术名**，**不动**模型名（`product.variant.conversion` / `product.variant.lineage`）、
字段与**列名**、视图 / 动作 / 权限的 xmlid。因此数据**零迁移**，台账、谱系、变体上的来源字段一条不丢。

**已装库的升级路径**（三条 SQL + 升级，顺序不能反）：

```sql
-- 1) 模块身份（Odoo 把目录名当模块名）
UPDATE ir_module_module SET name='product_variant' WHERE name='product_variant_conversion';
-- 2) 关键：不迁的话，升级时 _process_end() 会把旧 xmlid 当成「模块里没有了」而删掉视图 / 动作 / 权限记录
UPDATE ir_model_data  SET module='product_variant' WHERE module='product_variant_conversion';
-- 3) 「应用」列表那条元数据（模块名 / 摘要 / 描述的译文挂靠在 base.module_<技术名> 上）
UPDATE ir_model_data  SET name='module_product_variant'
 WHERE module='base' AND name='module_product_variant_conversion';
```

然后 `odoo -d <db> -u product_variant --stop-after-init` + 重启服务 + 强刷浏览器。

**两个取舍**：

- **不卸载重装**：卸载会 `unlink` 台账 / 谱系 / 变体来源字段（删表删列），只有不要这些历史时才这么做。
- **系统参数前缀随之改变**（`product_variant_conversion.` → `product_variant.`）：代码里新参数没设时
  **回退读旧名**，已有开关不会静默失效。

### 2.2 第二步：把面板做到「能用」（`19.0.7.0.1` – `19.0.7.0.5`）

这一段全是**真实故障修复**，每一条都让产品表单**完全打不开**或**一点就报错**：

1. **`19.0.7.0.1` 字段 widget 注册成裸类** → `Field.template` 崩在 `undefined.name`
   （详见第 4.1 节，含一次误判教训）。
2. **`19.0.7.0.2` 模板变量名写错**：组件上叫 `store`，模板里写成 `state.` → `undefined.blocked`。
3. **`19.0.7.0.3` 面板被排到属性行右侧**：字段外层 `.o_field_widget` 是 `inline-block`，
   需要一层块级 div 包住（并给字段加 `class="d-block w-100"` 双保险）。
4. **`19.0.7.0.4` 点 `Add a line` 立刻报必填缺失**：o2m 新建行发的是
   `[0, 0, {"value_ids": [...]}]`（**没有** `attribute_id`），预览 RPC 拿去试写 → `NotNullViolation`。
   三层修复：前端 `hasIncompleteLine()` 不发请求 / 服务端 `_sanitize_attribute_line_commands()` 清洗 /
   RPC 兜底 `incomplete=True`（**只兜** `NotNullViolation`，原生解释性 `UserError` 原样透出）。
5. **`19.0.7.0.5` 状态字段不再做成 compute**：`variant_mapping_state` 是 compute 时，
   每次 onchange 都会被求值，而那时表单里还有未保存的行（`NewId`）→ `json.dumps` 必炸
   （`TypeError: Object of type NewId is not JSON serializable`）。降级为 `store=False` 的**挂载点**，
   面板挂载时自己取快照。

### 2.3 第三步：映射计算整体搬到前端（`19.0.8.0.0` – `19.0.8.0.4`）

**架构决定**：面板挂载时取**一次**快照（`get_variant_mapping_snapshot()`），此后属性行增删、
勾取值、挑归属**全部在浏览器里用纯函数算**，**编辑期零 RPC**，保存时才把映射随表单提交。

随之而来四个细节坑（都修了）：

| 版本 | 问题 | 解法 |
|---|---|---|
| `19.0.8.0.1` | 加属性「毫无反应」：读 `record.data` 的 x2many 拿到的是命令数组，被读成空 | 用 `record.getChanges()` 合并快照基线 |
| `19.0.8.0.2` | 单变体产品加属性无反应：合并命令时自己造 id | **保留 Odoo 的虚拟 id**，否则后续「选属性 / 勾取值」命令落空 |
| `19.0.8.0.3` | 面板不刷新：`useRecordObserver` 依赖父 record，子行改字段不触发 | patch `X2ManyField` / `ListX2ManyField` 的 `onPatched` 通知面板 |
| `19.0.8.0.4` | 自动补的默认值被当成用户选择，加第二个取值后回不到「未映射」 | 轴状态带 `picked` 标记，默认值不算用户选择 |

### 2.4 第四步：占用唯一（`19.0.9.0.0`）

一个组合只能被一条变体占用：已被占住的候选值在下拉里禁用；真出现重复时那条标成未映射。
与保存时的服务端 `_check_variant_conversion_anchors()` 同口径。

### 2.5 第五步：映射表反向（`19.0.10.0.0`）

**这是本功能线最重要的一次结构转向**：

| | 旧（变体为行） | 新（组合为行） |
|---|---|---|
| 行 | 每条既有变体一行 | 每个**属性组合**一行 |
| 列 | 每个属性轴一列（下拉选值） | 属性列只读 + **Variant 下拉** |
| 操作 | 给每条变体挑它落在哪个组合 | 给每个组合挑由哪条既有变体保留（留空 = 新建） |
| 交换位置 | 两行互相占着对方组合时无解 | 各选自的组合即可（后来进一步改为「先释放再选」） |

**为什么改**：旧结构下「两条变体互换组合」很难受（后改的那一行没有可选值，用户实测反馈「变体下拉需要能够清空」）；
新结构下组合天然不重复（行就是组合），且「哪些组合是新的」一眼可见。

### 2.6 第六步：穷举与按需的口径（`19.0.11.0.0` → `19.0.12.0.0`）

需求原文：「前端属性组合穷举，但后端依然应该保持按需生成。当前端属性选的变体为 `(new variant)` 时，
后端根据属性的规则按需生成（含「按需生成」属性的按需生成）。」

于是**把「展示」与「预建」拆成两件事**：

| | 前端（展示） | 后端（预建） |
|---|---|---|
| 「立即」属性 | 全部取值组合都列出来 | 全部展开、缺失组合补建变体 |
| 「按需生成」属性 | 全部取值组合也列出来 | **只建被既有变体认领的取值**，其余等订单创建 |

- `19.0.11.0.0` 曾经取消 `T-039` 对按需轴的特例（全展开且全预建），
  `19.0.12.0.0` **回滚**为按需口径 —— 前端多出 `row.will_create` / `pending_count`：
  不会现在创建的行**灰显**，表下提示「N 个组合现在不会创建…」。
- 判断规则：该行有既有变体认领 ⇒ 会创建；没有 ⇒ 只有当它所有的「按需」取值都已被别的行认领时才创建。

### 2.7 第七步：交互定稿（`19.0.12.0.1` / `19.0.13.0.x`）

1. **`19.0.12.0.1` 候选禁用**：下拉里**已被别的行选走**的变体灰显、选不了；
   换位置只能先把占着它的那一行改回 `(new variant)` 让出来。
   —— 去掉了早期「选到别处自动从原行让出」的隐式抢占：两条变体互换时，用户改哪一行都像从另一行「抢走」。
2. **`19.0.13.0.0` 面板定稿**：加标题、重排布局；**移除原生那句已不成立的警告**；
   未映射不放行；映射一改出现 **Save manually / Discard all changes**（详见第 3.6 节）。
3. **`19.0.13.0.1`** 标题文案定为 `Variants Mapping` / 「变体映射」。

---

## 3. 技术要点

### 3.1 模块改名的边界：改技术名，不改数据身份

- 目录名 = 模块身份，所以「只改目录不改库」等于「已安装模块凭空消失」。
- 必须迁 `ir_model_data.module`（否则升级时旧 xmlid 被当作「模块里没有了」而**删除视图 / 动作 / 权限记录**）
  与 `base.module_<技术名>`（应用列表元数据）。
- 只要**模型名 / 字段 / 列名 / xmlid 未动**，就没有 schema 迁移、没有迁移脚本。

### 3.2 OWL 字段 widget 的注册契约

值必须是**描述对象**，不是组件类：

```js
export const variantMappingPanelField = {
    component: VariantMappingPanel,
    displayName: _t("Attribute / Variant Mapping"),
    supportedTypes: ["text"],
};
registry.category("fields").add("variant_mapping_panel", variantMappingPanelField);
```

`web.Field` 模板渲染的是 `field.component`；注册裸类时它是 `undefined`，owl 创建子组件时读 `Component.name` 直接抛错。

### 3.3 OWL 模板表达式的作用域

模板里能直接访问的只有**组件实例上的名字**（getter / 方法 / 赋值过的属性）与 OWL 内置的 `props`、
`t-foreach` 的循环变量。`state` **不是**保留字，写错只会得到 `undefined.x`，而且报错栈指向模板、不指向 `setup()`。

### 3.4 表单编辑态的读取方式

- `record.getChanges()` → 本次未保存的命令数组（编辑中 x2many 的真实形态）；
- 与挂载时的快照**按 id 合并**，得到「改动之后」的属性行集合；
- 新建行要**保留 Odoo 的虚拟 id**（`NewId`），自己造 id 会让后续命令落空（那一行永远不成为轴）。

### 3.5 「给前端看的状态」不要做成 compute 字段

compute 字段会在**任何 onchange** 里被求值，此时表单里还可能有未保存的行（`NewId`），
任何 `json.dumps(ids)` 都会炸。正确做法是把它降级为 `store=False` 的**挂载点**，
由前端在需要时自己 RPC 取数据。

### 3.6 脏状态与自动保存（本功能线最微妙的一处）

需求：映射一改就要出现 **Save manually / Discard all changes**，同时**不能让 Odoo 的自动保存
偷偷把映射写进去**。

Odoo 19 的事实（源码级）：

| 事实 | 位置 |
|---|---|
| 那两个按钮是**原生** `FormStatusIndicator`（`data-tooltip="Save manually"` / `"Discard all changes"`） | `web/.../form_status_indicator/form_status_indicator.xml` |
| 显示条件 `model.root.dirty \|\| fieldIsDirty`，其中 `fieldIsDirty` 由 `model.bus` 的 `FIELD_IS_DIRTY` 事件驱动 | 同上 `.js` |
| `Record._save()` 在「没有 changes」时**直接早退**，**不调用** `onWillSaveRecord` | `web/.../relational_model/record.js` |
| `beforeLeave()` / `beforeVisibilityChange()` 的自动保存判据是 `model.root.dirty` | `web/.../views/form/form_controller.js` |

**因此**：

1. 映射改动时 `model.bus.trigger("FIELD_IS_DIRTY", true)`（`setMappingDirty()`）→ 两个按钮出现；
2. **绝不**为了「让表单变脏」把映射塞进 record 的字段 —— 那会让离开页面 / 切标签时自动保存，
   违背「必须由用户显式保存」；
3. `FormController.save()` 里补一次纯映射写入（只改映射时原生 `_save()` 早退，钩子不会被调用）；
4. `FormController.discard()` 里在原生恢复完 record 之后调用 `discardMappingChanges(model)`，
   把 assignment 恢复成基线；
5. 「有没有改动」用 `mappingDiffersFromBaseline()`（**键顺序无关**的签名比较，
   直接 `JSON.stringify` 会因插入顺序不同误判），默认分配属于基线、不算改动。

### 3.7 服务端转换管线

一次保存（属性行 + 映射同一次写库、同一个事务）依次做：

1. **守卫**：会丢变体的改动（删取值 / 删属性）直接拒绝；未映射时兜底报错；
2. **归属锚定**：按映射把每条既有变体绑到它的组合（`variant_conversion_mapping` 是 `force_save` 的临时字段，写完即清）；
3. **补建**：带「按需生成」属性时，「立即」轴展开出的缺失组合用 Odoo 自己的 `_create_product_variant()` 补；
4. **记台账 / 谱系**：`variant_conversion_count` + 谱系明细，变体上写 `variant_conversion_id` / `variant_origin_id`；
5. **价格**：带「按需生成」属性的产品**不做价格分离**（以后订单期还会新建变体，模板级价格要留给它们）。

组合数上限沿用 Odoo 的 `product.dynamic_variant_limit`，且在 `itertools.product` **之前**估算（避免先枚举再拒绝）。

### 3.8 视图继承的两个用法

- **删节点**：`<xpath expr="//p[contains(., 'adding or deleting attributes')]" position="replace"/>`
  （空内容即删除）。删的是 `product.product_template_only_form_view` 里那句 `oe_edit_only` 纯文本警告 ——
  本模块不删变体、一律按归属复用，这句话已不成立。
- **撑满一行**：自定义字段 widget（表格 / 多行块）必须自己包一层块级 div，否则会与 `attribute_line_ids`
  并排、溢出表单可视宽度。

### 3.9 测试的三层结构

| 层 | 覆盖 | 位置 |
|---|---|---|
| 服务端 unittest | 转换管线、归属锚定、台账 / 谱系、按需轴不预建、半成品命令清洗 | `product_variant/tests/test_*.py` |
| 前端静态检查 | assets 登记、字段 widget 是否为描述对象、模板名字能否在组件上解析、`t-name` 与 `static template` 对应 | `product_variant/tests/test_frontend_consistency.py` |
| 纯函数离线自测 | 组合生成、默认分配、占用唯一、基线比较、`will_create` 判定 | `product_variant/tests/js/variant_mapping_pure.mjs`（`node` 直接跑，约 1 秒） |

静态检查做过**负向验证**：把 `store.` 改回 `state.`、把注册改回裸类，检查都会失败。

---

## 4. 遇到的问题与解决方案

### 4.1 一次误判（值得单独记）

| 项 | 内容 |
|---|---|
| 现象 | 打开产品表单报 `UncaughtPromiseError > OwlError`，cause 是 `TypeError: Cannot read properties of undefined (reading 'name')`，栈只落在 `Field.template` |
| 误判 | 先归因为「升级后没重启进程 / 浏览器缓存」，并写进了 `AGENTS.md` 陷阱 8 |
| 真相 | 字段 widget 注册成了**裸组件类**；`web.Field` 拿到的 `field.component` 是 `undefined` |
| 教训 | 报错栈只指向框架（`Field.template`）时，**先怀疑自己传给框架的对象结构**（注册值、模板名字），再怀疑缓存；服务端 `get_views` 正常**不能**证明前端渲染没问题 |

### 4.2 全部故障与修复（按版本）

| # | 版本 | 现象 | 根因 | 解法 |
|---|---|---|---|---|
| 1 | `19.0.7.0.1` | 产品表单 /「属性与变体」页整页崩 | 字段 widget 注册成裸类 | 注册 `{component, displayName, supportedTypes}` |
| 2 | `19.0.7.0.2` | 面板首帧崩在 `undefined.blocked` | 模板写 `state.`，组件上是 `store` | 9 处改为 `store.` |
| 3 | `19.0.7.0.3` | 面板渲染出来但在右侧、看不见 | `.o_field_widget` 是 `inline-block`，与属性行并排并溢出 | 视图里套一层 `d-block w-100` |
| 4 | `19.0.7.0.4` | 点 `Add a line` 就报 `Missing required value for the field 'Attribute'` | 半成品命令（无 `attribute_id`）被拿去试写 | 前端不发 + 服务端清洗 + `NotNullViolation` 兜底 |
| 5 | `19.0.7.0.5` | 选属性后立即 `TypeError: Object of type NewId is not JSON serializable` | 状态字段做成 compute，onchange 期被求值 | 降级为 `store=False` 挂载点 |
| 6 | `19.0.8.0.1` | 加属性「毫无反应」 | 读 `record.data` 的 x2many 拿到命令数组 | 用 `record.getChanges()` 合并快照 |
| 7 | `19.0.8.0.2` | 单变体产品加属性无反应 | 合并命令时自己造了行 id | 保留 Odoo 的虚拟 id |
| 8 | `19.0.8.0.3` | 面板不随子表刷新 | `useRecordObserver` 依赖父 record | patch o2m 组件 `onPatched` |
| 9 | `19.0.8.0.4` | 自动补的默认值被当用户选择，回不到「未映射」 | 轴状态没区分「自动补」与「用户选」 | 轴带 `picked` 标记 |
| 10 | `19.0.12.0.0` | 「按需生成」属性被全量预建（用户不要） | `19.0.11.0.0` 取消了 `T-039` 特例 | 前端穷举展示 + 后端按需预建（`will_create` / `pending_count`） |
| 11 | `19.0.12.0.1` | 两条变体换位置时互相「抢」 | 隐式抢占（选到别处自动让出） | 下拉禁用已占项 + 显式释放 |
| 12 | `19.0.13.0.0` | 只改映射时点保存提交不了 | `Record._save()` 因「没有 changes」早退，钩子不被调用 | `save()` 里补一次纯映射写入 |

### 4.3 需求口径的三次反转（过程记录）

| 版本 | 口径 | 结果 |
|---|---|---|
| `19.0.10.0.0` | 组合为行、按需轴取值是「行上可改的值」（不展开） | 结构对了，但按需轴看不出全貌 |
| `19.0.11.0.0` | 所有属性一律穷举、且全量预建 | 用户指出「按需生成」属性不该被预建 |
| `19.0.12.0.0` | **展示穷举 + 预建按需** | 定稿：前端列全、后端按属性规则 |

**经验**：「前端展示」与「后端预建」是两件事，需求里说「穷举」时先问清是**列出来**还是**建出来**。

---

## 5. 最终结果与产出

### 5.1 版本与提交

| 版本 | 主题 |
|---|---|
| `19.0.7.0.0` | 模块改名 `product_variant` + 映射表初版（提交 `cf0d463`，本轮之前） |
| `19.0.7.0.1` – `19.0.7.0.5` | 面板可运行性五项修复 |
| `19.0.8.0.0` – `19.0.8.0.4` | 映射计算搬到前端 + 四项细节 |
| `19.0.9.0.0` | 一个组合只能被一条变体占用 |
| `19.0.10.0.0` | 映射表反向（组合为行） |
| `19.0.11.0.0` → `19.0.12.0.0` | 穷举展示 + 按需预建（含一次回滚） |
| `19.0.12.0.1` | 下拉禁用已占变体 |
| `19.0.13.0.0` / `19.0.13.0.1` | 面板定稿（标题 / 显式保存与丢弃 / 删原生警告）+ 标题文案 |

本轮提交：`2e2876d`、`1734e5c`、`8898deb`、`7d6e995`、`9e6f4b4`。

### 5.2 代码与文档产出

| 类别 | 产物 |
|---|---|
| 后端 | `models/product_template.py`（转换管线 / 命令清洗 / 组合枚举）、`models/product_variant_mapping.py`（快照 RPC）、`models/product_attribute_guards.py`、`models/product_product.py` |
| 前端 | `static/src/js/variant_mapping_panel.js`（面板 + 纯函数）、`static/src/js/variant_conversion_form_patch.js`（保存钩子 / 脏状态 / 丢弃）、`static/src/xml/variant_mapping_panel.xml` |
| 视图 | `views/product_template_views.xml`（面板挂载、删除原生警告、台账智能按钮、搜索筛选） |
| i18n | `i18n/zh_CN.po`（137 条，含模块元数据与前端 `_t()` 术语） |
| 测试 | 63 项服务端（含 4 项前端静态检查）+ 15 项离线纯函数自测 |
| 文档 | 模块 `README.md` / `AGENTS.md`（陷阱 8–20）/ `CHANGELOG.md`；根 `README.md` / `AGENTS.md` / `TODO.md`（`T-042` 归档）；本复盘 |

### 5.3 验证结果

| 项 | 结果 |
|---|---|
| `task test -- product_variant` | 63 项 0 failed / 0 error |
| `node product_variant/tests/js/variant_mapping_pure.mjs` | 15 项 all good |
| `task update -- product_variant`（dev 库） | 无报错，模块 installed **19.0.13.0.1** |
| 合并后的表单 arch | 原生警告已消失、映射面板字段在位 |
| `task check` | 无失败项 |

### 5.4 待目标环境验证

1. 打开产品 →「属性与变体」页：面板标题 **Variants Mapping / 变体映射**、原生警告已消失、面板在属性行下方独占一行。
2. 改属性 → 面板刷新；缺取值的变体被点名；**保存被拦**。
3. 映射交互：已被别行选走的变体在该行下拉里**灰显**；要换位置先改回 `(new variant)`。
4. 改过映射 → 出现 **Save manually / Discard all changes**；点**丢弃**后属性行与映射一起回到改动前；
   只改映射、**不点保存**就切菜单 / 切浏览器标签 → 不应被自动保存写库。
5. 带「按需生成」属性的产品：未被认领的按需组合**灰显 + 提示**，保存后**不会**凭空多出这些变体。
6. 中文界面各文案（必要时 `task i18n -- zh_CN product_variant` 强制刷新译文）。

### 5.5 生产升级步骤

1. **备份数据库**；
2. 若仍是旧模块名：跑第 2.1 节的三条 SQL（已改名的库跳过）；
3. `odoo -d <db> -u product_variant --stop-after-init` → 重启服务；
4. **强刷浏览器**（Ctrl+F5；前端字段缓存是内存 + 站点存储，普通刷新不一定清掉）。

---

## 6. 可复用的结论

1. **「没报错」≠「生效」**：服务端返回正常、`get_views` 里有字段，都不代表前端渲染得过关。
2. **崩溃栈只指到框架时先查自己的契约**：注册值结构、模板名字、字段是否存在，比缓存更常见。
3. **给前端看的状态别做成 compute**：onchange 期存在未保存行（`NewId`），序列化必炸。
4. **表单之外的编辑状态要自己管**：Odoo 的保存只认 record 的 changes —— 自己决定是否参与保存、
   自己广播脏状态（`FIELD_IS_DIRTY`）、自己实现丢弃；**不要**为了「变脏」把状态塞进 record，
   否则自动保存会带走它。
5. **占位类交互用「显式释放」而不是「隐式抢占」**：一对一占用时，让用户明确让出比自动抢走更好懂。
6. **需求里的「穷举」要问清是展示还是预建**；两者可以不一致，但要在界面上把差异**显示出来**
   （灰显 + 提示），不能让用户以为会创建。
7. **口径反转要留痕**：`19.0.11.0.0` 与 `19.0.12.0.0` 的方向相反，`CHANGELOG` 里写清「回滚了什么、
   为什么」，否则后来者会以为是笔误。
8. **静态检查能拦住「整页崩溃」这类低级但高代价的错误**：把踩过的坑写成文本扫描测试，
   比口头约定可靠（并有负向验证）。

---

## 7. 索引（要找细节看这里）

| 想知道 | 去哪 |
|---|---|
| 怎么用、字段表、验证清单 | `product_variant/README.md` |
| 每个版本改了什么 | `product_variant/CHANGELOG.md`（`19.0.7.0.0` – `19.0.13.0.6`） |
| 约束与踩坑（陷阱 8–23） | `product_variant/AGENTS.md` L2 P4 |
| 第二轮的做了什么 / 注意什么 | [`product_variant_mapping_change_record_2026-09-24.md`](product_variant_mapping_change_record_2026-09-24.md) →「第二轮」 |
| 需求状态与归档 | 根 `TODO.md` → `T-042` |
| 模块一览与交付历史 | 根 `README.md` |
| 本地开发命令 | `DEV_WORKFLOW.md`、`Taskfile.yml` |
| 历史阶段报告 | `docs/archive/STAGE_REPORT_2026-09-2*.md` |
