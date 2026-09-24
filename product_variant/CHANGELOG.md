# 变更日志

> 倒序排列，最新版本在最前。每版本固定三段式：变更 / 影响 / 文档。
> 版本号规则见根 `AGENTS.md` 第 3 节：架构/破坏性 +x，功能新增 +y，修复/文档 +z。

## [19.0.13.0.1] - 2026-09-24（文案：面板标题改为 `Variants Mapping` / 「变体映射」）

> 修订日期：2026-09-24 ｜ 类型：修复/文案（+z） ｜ 影响文件：
> `static/src/js/variant_mapping_panel.js`、`i18n/zh_CN.po`、`__manifest__.py`、`AGENTS.md` / `README.md`

### 变更

1. 面板标题由 `Attributes and variants mapping` 改为 **`Variants Mapping`**（中文 `变体映射`），
   po 里同一条目直接改写 `msgid` / `msgstr`。
2. 标题文案与字段 widget 的 `displayName`（`Attribute / Variant Mapping`，只出现在字段设置里）刻意不同：
   前者是用户看到的页内标题，后者是开发者视角的字段说明。

### 影响

- 纯文案；需 `-u` + 强刷浏览器。`msgid` 变了，中文界面会按新条目显示（旧条目留在库里成为孤儿，无副作用）。

## [19.0.13.0.0] - 2026-09-24（映射表面板：标题、显式保存/丢弃、未映射不放行）

> 修订日期：2026-09-24 ｜ 类型：功能（+y） ｜ 影响文件：
> `views/product_template_views.xml`、`static/src/js/variant_mapping_panel.js`、
> `static/src/js/variant_conversion_form_patch.js`、`static/src/xml/variant_mapping_panel.xml`、
> `tests/js/variant_mapping_pure.mjs`、`i18n/zh_CN.po`、`__manifest__.py`、`AGENTS.md` / `README.md`

### 变更

1. **面板布局 + 标题**：新增标题 `Attributes and variants mapping`（带下划线分隔），说明、警示、
   映射表、新变体 / 等待创建提示、勾选框、未保存操作区分层排列。
2. **移除原生警告**：`product.product_template_only_form_view` 里那句
   `<p class="opacity-50 oe_edit_only">``Warning``: adding or deleting attributes will delete and
   recreate existing variants...</p>` 已不成立（本模块不删变体、一律按归属复用），用 xpath 整段删除。
3. **未映射不放行**：所有既有变体必须各占一行；存在未映射变体时保存被拦（前端提示 + 服务端兜底），
   且**不会**被 Odoo 的自动保存绕过去（见下）。
4. **显式保存 / 丢弃**：映射一发生改动，面板下方出现 **Save manually** / **Discard all changes**
   两个按钮（文案与 Odoo 原生状态指示器一致），同时通过 `FIELD_IS_DIRTY` 让原生状态指示器也出现；
   点 **Discard all changes** 会把属性行与映射一起回滚到最后一次保存的状态。
5. **规避自动保存**：映射改动只存在于本模块的 store（不是 record 的字段改动），
   因此 `beforeLeave()` / `beforeVisibilityChange()` 这些自动保存路径不会带上它 ——
   映射只由用户显式保存（或属性行改动触发的正常保存）落库。又因为 `Record._save()` 在
   「没有 changes」时会直接早退（不调用 `onWillSaveRecord`），`FormController.save()` 里补了
   一次纯映射写入，保证只改映射时点 **Save manually** 也能落库。
6. 测试：离线自测 15 项（新增「映射改过才显示保存/丢弃」）。

### 影响

- 前端 + 视图 arch（删除原生警告节点）；字段 / RPC / 数据结构未动。需 `-u` + 强刷浏览器。

### 文档

- 模块 `AGENTS.md` → L2 P4 陷阱 20（纯前端的「脏」要自己广播给状态指示器，别把状态塞进 record）；
  `README.md` 补面板行为说明。

## [19.0.12.0.1] - 2026-09-24（修复：Variant 下拉里已被别的行占用的变体要禁用）

> 修订日期：2026-09-24 ｜ 类型：修复/体验（+z） ｜ 影响文件：
> `static/src/js/variant_mapping_panel.js`、`static/src/xml/variant_mapping_panel.xml`、
> `tests/js/variant_mapping_pure.mjs`、`i18n/zh_CN.po`、`__manifest__.py`、`AGENTS.md` / `README.md`

### 变更

1. **需求**：Variant 下拉里**已经被别的行选走的变体**要灰显、选不了；要换位置只能先把占着它的那一行
   改回 ``(new variant)`` 把它让出来，再给另一行选。
2. **做法**：新增纯函数 ``buildVariantOptions(variants, rows)`` —— 每个选项带上 ``taken_by``
   （占着它的组合 key）；模板里 ``t-att-disabled="isOptionTaken(option, row)"``
   （``taken_by`` 存在且不是自己这一行 → 禁用 + ``title`` 说明怎么办）；
   ``onSelectVariant()`` 里再防御一次（被别行占着就直接返回），免得程序化赋值绕过 UI。
3. **为什么不做「自动让出」**（早期做法）：两个下拉互相抢时，用户改哪一行都像从另一行「抢走」，
   看不出谁让给谁。
4. 自测新增 1 项（``已被别的行选走的变体在那一行禁用：只能先让出来再换``，共 14 项）。

### 影响

- 纯前端交互 + 文案，字段、视图 arch、RPC、数据结构与**后端行为一律没动**；需 `-u` + 强刷。

### 文档

- 模块 `AGENTS.md` → L2 P4 陷阱 19（占位类交互：**禁止**优于**隐式抢占**）、当前版本；
  `README.md` 里「选到别的行会自动让出、互换只需两下」的表述改为「已被占的禁用，先让出再选」。

## [19.0.12.0.0] - 2026-09-24（前端穷举展示，后端保留「按需生成」）

> 修订日期：2026-09-24 ｜ 类型：功能/行为（+y） ｜ 影响文件：
> `models/product_template.py`、`static/src/js/variant_mapping_panel.js`、
> `static/src/xml/variant_mapping_panel.xml`、`tests/test_product_variant_conversion.py`、
> `tests/js/variant_mapping_pure.mjs`、`i18n/zh_CN.po`、`__manifest__.py`、`AGENTS.md` / `README.md`

### 变更目标（用户要求）

> 前端属性组合穷举，但后端依然应该保持按需生成。当前端属性选的变体为 ``(new variant)`` 时，
> 后端根据属性的规则按需生成（含「按需生成」属性的按需生成）。

### 变更

1. **后端恢复按需语义**（回滚 `19.0.11.0.0` 的全展开）：
   - `_split_variant_conversion_lines()` / `_get_variant_conversion_fixed_values()` 恢复；
   - `_get_variant_conversion_combinations()`：按需轴**不展开**，只钉住每条既有变体占有的取值；
   - `_create_variant_conversion_missing_variants()`：只在带按需属性时补建「立即」轴的组合；
   - `_check_variant_conversion_combination_cap()`：组合数估算同步回「变体数 × 立即轴乘积」。
2. **前端保持穷举展示**（按需轴的全部取值都列出来），并新增「会不会**现在**创建」的标记：
   - `row.will_create`：该行有既有变体认领 ⇒ 会创建；没认领 ⇒ 要求它所有的「按需」取值
     都已被别的行认领（也就是：那个取值有变体在保留），否则**不会现在创建**；
   - 不会创建的行显示为灰色，表下方提示「N 个组合现在不会创建…」；
   - `new_count` 只统计「会创建的新组合」（`newVariantsLabel` 因此更准确）。
3. 测试：3 个 `T-039` 用例回到「按需轴不预建」的期望；离线自测新增
   `will_create` / `pending_count` 断言（13 项）。

### 影响

- 后端预建口径回到 `19.0.10.0.0`；前端多了「哪些组合现在不会被创建」的可见提示。
  `-u` + 强刷浏览器。

### 文档

- `AGENTS.md`（当前版本 / 陷阱 18）与 `README.md`（场景表 S11、核心设计、使用前提）同步为
  「**前端穷举展示、后端按需预建**」。

## [19.0.11.0.0] - 2026-09-24（取消 T-039 特例：**所有属性一律穷举，属性列只读**）

> 修订日期：2026-09-24 ｜ 类型：功能/行为变更（+y） ｜ 影响文件：
> `models/product_template.py`、`static/src/js/variant_mapping_panel.js`、
> `static/src/xml/variant_mapping_panel.xml`、`tests/test_product_variant_conversion.py`、
> `tests/js/variant_mapping_pure.mjs`、`__manifest__.py`、`AGENTS.md` / `README.md`

### 变更目标（用户实测反馈）

> 所有属性都不能为可选，如 Length，应该充分列举所有可能的组合。

映射表里的属性列必须**只读**、组合必须**穷举**；之前为「按需生成」属性留的
「那一列是可以改的下拉」不满足这个要求。

### 变更

1. **取消 `T-039` 的特例**（`dynamic` 属性不再特殊对待）：
   - `_get_variant_conversion_combinations()`：所有属性一律参与笛卡尔积（原来对 `dynamic` 轴只钉住
     既有变体的取值）；
   - `_create_variant_conversion_missing_variants()`：不再只在「有按需属性」时补建 —— 统一补
     「计划里还没有变体」的组合（不带按需属性时通常没有缺失，作为兜底）；
   - `_check_variant_conversion_combination_cap()`：组合数估算改为「各属性有效取值数的乘积」；
   - 删除 `_split_variant_conversion_lines()` 与 `_get_variant_conversion_fixed_values()`。
2. **前端**：属性列全部只读、组合穷举（`buildCombinationRows()` 对所有轴做笛卡尔积）；
   删除「按需列可改」的 `dynamicPicks` / `onSelectDynamicValue` 与相关提示、文案。
3. **保留**：带按需属性时**不做价格分离**（Odoo 仍会在订单里为未预建的取值创建变体，
   模板级价格要留给它们）；建产品时直接带按需属性仍被拦住（原生会建出 0 变体的产品）。
4. 测试：三个 `T-039` 用例按新行为改写（穷举后组合数、变体数、来源字段的判定都跟着变；
   「本次才启用的取值」派生出来的变体没有来源，这是谱系判定「按转换前已存在的取值认来源」的口径）；
   离线自测改为「12 个组合一个不少」。

### 影响

- **行为变更**：带「按需生成」属性的产品，改属性时会把该属性的**全部取值组合**都建成变体
  （不再等订单），这正是「穷举」的语义；不需要预建时请不要给属性设 `Variant Creation = On Demand`。
- 迁移：无需迁移脚本；升级后强刷浏览器。需 `-u`。

### 文档

- 模块 `AGENTS.md`（当前版本 / L2 P4 陷阱 13、18）与 `README.md`（场景表 S11、核心设计、
  使用前提与限制、导入、遗留清单）里「按需轴不展开」的表述全部改为「所有属性一律穷举」。

## [19.0.10.0.0] - 2026-09-24（映射表反向：**组合为行、为每个组合选变体**）

> 修订日期：2026-09-24 ｜ 类型：功能/交互（+y） ｜ 影响文件：
> `static/src/js/variant_mapping_panel.js`、`static/src/xml/variant_mapping_panel.xml`、
> `static/src/js/variant_conversion_form_patch.js`、`i18n/zh_CN.po`、
> `tests/js/variant_mapping_pure.mjs`、`__manifest__.py`、`AGENTS.md` / `README.md`

### 变更目标

按用户要求把映射关系**反向**：**属性组合是固定的行，用户为每个组合选择「由哪条既有变体保留」**
（而不是给每条变体逐轴挑值）。组合天然不会重复，且 Variant 下拉可以留空 / 清空 —— 交换位置
只需点两下。

### 变更

1. **行的身份 = 属性组合**：
   - 「立即」属性（``always``）：按取值做笛卡尔积，每行一个组合；
   - 「按需生成」属性（``dynamic``）：**不展开**取值空间（``T-039`` 保留）——它的列是**行上的可改
     下拉**（默认取本行原本那条变体带着的取值，没有就取第一个），改它只影响这一行的组合；
   - 全是按需属性时，行按既有变体现带的取值组合给出（不展开取值空间）。
2. **Variant 列**（每行一个下拉）：留空 = 该组合**新建变体**；选一条既有变体 = 由它继续保留。
   **同一条变体只能占一行**：选到别的行时自动从原行让出（交换只需两下）；清空后不再被默认分配填回
   （``store.cleared``）。
3. **默认分配**：打开面板时把「本来就属于这一行」的既有变体放回它的行（只比「立即」轴 ——
   新加的按需轴既有变体肯定没有取值，不该因此判它不匹配）。
4. **拦截条件**：没被任何组合认领的既有变体会在上方**点名**并阻止保存（原「未映射」改为「未分配」）。
5. **保存载荷不变**：仍是 ``{mapping: [{values, origin_variant_id}], share_vendor_prices}``
   —— 与服务端契约天然一致，**服务端零改动**（``_check_variant_conversion_anchors()`` 仍是权威）。
6. i18n：说明文案随交互重写（po 同步：替换 5 条、删除 3 条、新增 1 条）。
7. 离线自测按新模型重写（13 项）：组合行 / 默认分配 / 一行一变体 / 交换 / 清空 / 按需列可改 /
   mapping 结构 / 全按需产品 / 命令合并 / 删空行。

### 影响

- 前端交互模型变化；视图 arch、RPC、数据结构**一律没动**。需 `-u` + 强刷浏览器。

### 文档

- 模块 `AGENTS.md` → L2 P4 陷阱 13（落地说明）与陷阱 18（改为「以组合为行」）已同步；
  `README.md` 的映射表说明与验证清单同步。

## [19.0.9.0.0] - 2026-09-24（映射表：一个属性组合只能被一条变体占用）

> 修订日期：2026-09-24 ｜ 类型：功能（+y） ｜ 影响文件：
> `static/src/js/variant_mapping_panel.js`、`static/src/xml/variant_mapping_panel.xml`、
> `i18n/zh_CN.po`、`tests/js/variant_mapping_pure.mjs`、`__manifest__.py`、`AGENTS.md` / `README.md`

### 变更目标

用户实测：映射表允许两条变体选到同一个属性组合，直到保存才被服务端拒绝（
`_check_variant_conversion_anchors()`：「确认归属组合互不重复」），用户白填一遍。
本次把「组合唯一」变成**界面上就看得见**的约束。

### 变更

1. **前端唯一性约束**（``applyCombinationUniqueness()``，纯函数、可用离线自测覆盖）：
   - 已被别的变体占住的组合，在下拉里**禁用** —— 用户看得到、点不了，不会选重；
   - 万一还是重了（历史状态、被别处改动），把重复的那条标成**未映射**并给出提示，照样拦住保存；
   - 候选值**逐行克隆**：`options` 数组原本是所有行共享同一个引用，一行禁用会影响所有行。
2. **提示文案**：新增「%(count)s variants are mapped to the same combination…」，`i18n/zh_CN.po` 已同步。
3. **与服务端同口径**：服务端 `_check_variant_conversion_anchors()` 仍是权威（API 调用也拦得住），
   前端只是把结论提前。
4. 离线自测新增 2 项：冲突候选被禁用（且不影响本行自己的候选）/ 真重复时算未映射且先不列新组合。

### 设计取舍：「固定变体选属性」还是「固定组合选变体」

保持**以变体为中心**（现状）。这条流程的本质约束是「**每条既有变体都必须落到一个组合**」
（要保住它的库存、单据、价格），以变体为中心才能把「漏选」明确暴露成**未映射**并拦住保存；
若改成「列出所有组合、为每个组合挑一条既有变体」，组合数往往远多于既有变体数
（示例产品 2×3×3 = 18 个组合 vs 6 条既有变体），绝大多数组合要用户点「新建」，
还得另设一列反向核对「哪条既有变体还没被分配」——更容易漏、更费点击。
组合重复的问题用上面的唯一性约束解决，效果与「固定组合」等价。

### 影响

- 前端交互 + 一条新文案；视图 arch、RPC、数据结构**一律没动**。需 `-u` + 强刷浏览器。

### 文档

- 模块 `AGENTS.md` → L2 P4 陷阱 18：组合归属的唯一性要在界面上可见。

## [19.0.8.0.4] - 2026-09-24（修复：自动补的默认值被当成用户选择，加第二个取值后回不到未映射）

> 修订日期：2026-09-24 ｜ 类型：修复（+z） ｜ 影响文件：
> `static/src/js/variant_mapping_panel.js`、`tests/js/variant_mapping_pure.mjs`、
> `__manifest__.py`、`AGENTS.md`

### 变更

1. **现象**（实测）：某属性起初只有 1 个取值（Length: 140）→ 面板替 Odoo 把 140 显示到所有变体上、
   算「已映射」；用户随后又勾了 120 → 面板**仍然**显示 140、仍算已映射 —— 长度 120 的变体本该是
   未映射，却一个都没进未映射列表。
2. **根因**：`buildSelectionPayload()` 把「面板当前显示的取值」一律当成「用户的选择」写回 selection，
   包括**单取值轴自动补的那个默认值**；下一轮重算它又被当成用户选择 ⇒ 自我固化，永远回不到未映射。
3. **修复**：轴状态带 `picked` 标记 —— 只有用户在下拉里选过（含选回「Choose a value」）才是 true；
   `buildSelectionPayload()` 只输出 `picked` 的项。于是：
   - 自动补的值不写回 selection；
   - 该轴出现第二个取值时，若谁都没选过 → 变体回到**未映射**（期望行为）；
   - 变体**原本就带着**的取值仍显示且算已映射（不需要用户重选）。
4. 离线自测新增两项：自动补的不算用户选择（该轴多出取值后回到未映射）、用户选过的在重算里保留。

### 影响

- 纯前端判定；**编辑期仍然零 RPC**。需 `-u` + 强刷浏览器。

### 文档

- 模块 `AGENTS.md` → L2 P4 陷阱 17：默认值 / 派生值 / 用户确认值必须在状态里分开记。

## [19.0.8.0.3] - 2026-09-24（修复：面板不刷新 —— 属性行的变化没被通知到）

> 修订日期：2026-09-24 ｜ 类型：修复（+z） ｜ 影响文件：
> `static/src/js/variant_mapping_panel.js`、`__manifest__.py`、`AGENTS.md`

### 变更

1. **根因**：`useRecordObserver` 的实现是 ``effect(cb, [props.record])``
   （`web/core/utils/reactive.js`）—— 依赖**只有 record 对象本身**，而编辑表单时这个引用不变；
   「选属性 / 勾取值」改的是**子 record** 的字段，不保证让父 record 的 effect 重跑。
   `19.0.8.0.0` 起我又把回调简化成不读任何数据，等于把仅有的触发点也去掉了 →
   面板停在挂载时那一次的状态（加属性、勾取值都没反应）。
2. **修复**（三路信号，任一命中即重算，签名去重保证不重复渲染）：
   - patch 外层 `X2ManyField` 与真正渲染行的 `ListX2ManyField`，在它们每次 `onPatched` 后通知面板
     —— 子表被编辑时它们是必然重渲染的；包装原 `setup` 时用 `originalSetup?.call(this)`，
     不假设每个类都有 `setup`（`ListX2ManyField` 直接继承 `Component`）；
   - 保留 `useRecordObserver`（覆盖 record 级变化、保存后重载）；
   - 面板挂载期间每秒本地自检一次（`recompute()` 纯本地计算 + 签名没变就直接返回，稳定时零开销），
     作为「Odoo 内部机制再变也照常工作」的兜底。
3. 离线纯函数自测不变（纯函数逻辑本来就对，这次修的是**触发链路**）。

### 影响

- 只动前端触发链路；**编辑期仍然零 RPC**（`getChanges()` 是本地操作）。需 `-u` + 强刷浏览器。

### 文档

- 模块 `AGENTS.md` → L2 P4 陷阱 16：`useRecordObserver` 不会因为「子表里改字段」而触发。

## [19.0.8.0.2] - 2026-09-24（修复：新加的属性行不成为轴 —— 虚拟行 id 被自己造掉了）

> 修订日期：2026-09-24 ｜ 类型：修复（+z） ｜ 影响文件：
> `static/src/js/variant_mapping_panel.js`、`__manifest__.py`、`AGENTS.md`

### 变更

1. **根因**：把 ``getChanges()`` 的命令合并到基线时，新建行自己造了 id（``new-0``）。但用户点
   **Add a line** 之后，「选属性」「勾取值」在 Odoo 眼里是对**同一个虚拟行**的后续更新
   （``[1, 0, {...}]``，用的是它自己的虚拟 id ``0``）—— 找不到 ``new-0`` 那一行，这些更新全被丢掉，
   那一行永远只有 ``attribute_id: false`` → 不成为轴 → **面板毫无反应**
   （单变体产品里加一个多取值属性就是这条路径）。
2. **修复**：``mergeAttributeLines()`` 原样保留 Odoo 给的虚拟 id；``[1, id, vals]`` 在基线里找不到
   对应行时，把它当作「本次新建的虚拟行」接住（而不是跳过）。
3. **自测**（Node 抽纯函数跑真实命令序列）：单变体产品加 ``Color: Black/Red`` → 轴出现且该变体
   **未映射**（正是应当拦住保存的情形）；逐条勾取值（增量 ``[4, id]``）→ 两个取值都在；
   改已保存行的取值 / 删整行 → 正常。

### 影响

- 纯前端合并逻辑，**编辑期仍然零 RPC**。需 `-u` + 强刷浏览器。

### 文档

- 模块 `AGENTS.md` → L2 P4 陷阱 15：合并 ``getChanges()`` 命令时，虚拟行的 id 必须原样保留。

## [19.0.8.0.1] - 2026-09-24（修复：面板读不到表单里正在编辑的属性行，加属性毫无反应）

> 修订日期：2026-09-24 ｜ 类型：修复（+z） ｜ 影响文件：
> `static/src/js/variant_mapping_panel.js`、`models/product_variant_mapping.py`、
> `static/src/js/variant_conversion_form_patch.js`、`tests/test_product_variant_mapping.py`、
> `__manifest__.py`、`AGENTS.md` / `README.md`

### 变更

1. **根因**：面板原来用 ``record.data.attribute_line_ids.records[].data.value_ids.records`` 读「表单当前
   编辑态」的取值。编辑中的 o2m 子行 / m2m 取值在 ``record.data`` 里可能是**命令数组**
   （``[[0, 0, vals]]`` / ``[[1, id, vals]]``）而不是 record 列表，于是取值被读成空 → 用户新加的那一行
   **不成为轴** → 面板「没有任何反应」。
2. **修复**：不再猜内部结构，改用 Odoo 公开的 ``record.getChanges()``（**本地，不发请求**）拿属性行命令，
   与快照里的**已保存基线** ``lines`` 合并出编辑态：
   - ``mergeAttributeLines()``：``[0]`` 新建 / ``[1]`` 改 / ``[2]``\ ``[3]`` 删 / ``[5]`` 清空 / ``[6]`` set；
   - ``applyValueCommands()``：m2m 的 set（``[6,0,ids]``）与增量（``[4,id]`` 关联 / ``[3,id]`` 取消 / ``[5]`` 清空）
     分开处理 —— **增量命令不能当替换**，否则勾一个取值会丢掉原来勾的。
3. **快照**相应带上 ``lines``（已保存的属性行基线）、``attributes``（id → 名称 + ``create_variant``）、
   ``values``（id → 名称 + 归属属性）：前端手里只有 id，名称一律从快照查。
4. **测试**：快照用例跟上新结构；另把面板纯函数抽出来在 Node 里跑真实数据自测 —— 加属性 → 轴出现且
   两条变体未映射、Length 的三个取值都在下拉里、挑好后「按需生成」轴只列用到的取值、
   勾取值走增量不丢原值、把某一行取值删空/删整行都不报错。

### 影响

- 纯前端 + 快照结构（本模块内部 RPC）；**编辑期仍然零 RPC**。需 `-u` + 强刷浏览器。

### 文档

- 模块 `AGENTS.md` → L2 P4 陷阱 14：读「表单当前编辑态」要用 ``getChanges()`` 合并基线，
  不要读 record 内部结构。

## [19.0.8.0.0] - 2026-09-24（映射表改为**纯前端计算**：编辑期零 RPC，保存才回服务端）

> 修订日期：2026-09-24 ｜ 类型：功能/架构（+y） ｜ 影响文件：
> `models/product_variant_mapping.py`、`static/src/js/variant_mapping_panel.js`、
> `static/src/js/variant_conversion_form_patch.js`、`tests/test_product_variant_mapping.py`、
> `__manifest__.py`、`AGENTS.md` / `README.md` / `CHANGELOG.md`

### 变更目标

把「增删属性 / 勾取值时的映射计算」整个搬到前端：**编辑期间不再因为表单还没写完就把数据发给后端**，
服务端只在保存时参与（安全转换 + 权威判定）。

### 变更

1. **新增一次性快照 RPC** ``get_variant_mapping_snapshot()``：面板挂载时取一次，返回既有变体
   （id / 名称 / 在手数量 / 它带的 ``{属性: 取值}``）与各属性的 ``create_variant``。它只描述
   **已经保存的事实**，所以表单里那些没保存的行（Add a line 的空行、被删空的取值行）不会让它报错。
2. **新增前端纯函数** ``computeVariantMapping()``（含 ``readAttributeLines()`` /
   ``newCombinationLabels()``）：按表单**当前**的属性行 × 快照 × 用户已选，在浏览器里算
   每条变体的组合、未映射数、本次会新建的组合；属性行一改只做**本地重算**（防抖 150ms）。
3. **编辑期不再调 RPC**：原 ``get_variant_mapping_preview()`` 保留为服务端侧判定入口
   （调试 / 兜底），前端不再使用。
4. **保存钩子改为纯本地判定**：读前端算好的状态 —— 有未映射就提示并拦住保存，否则把映射随
   ``changes`` 一起提交；「会丢变体」仍由服务端 ``write()`` 拒绝并给出解释文案。
5. **按需轴不再自动填第一个取值**（``_get_variant_mapping_rows()``）：多取值轴一律要求显式映射，
   **「按需生成」轴不例外**。原行为会让「加了 Length（120/140/160）」只显示 120 并算成已映射，
   用户没法指定每条变体保留哪个取值（实测反馈）；按需轴仍然**不预建**它的其它取值（``T-039`` 不变）。
6. 测试：按需轴用例改为「要求显式映射」、新增快照用例（63 项）。

### 影响

- 前端行为重构 + 新增一个 RPC；字段、视图 arch、数据结构**一律没动**，无迁移。需 `-u` + 强刷。
- 编辑期间**零 RPC** ⇒ 表单未写完的状态（空行、空取值）不会再触发服务端校验弹窗。

### 文档

- 模块 `AGENTS.md` → L2 P4 陷阱 13：编辑期的计算放前端（一次性快照 + 纯函数），
  服务端只在保存时参与。

## [19.0.7.0.5] - 2026-09-24（修复：映射状态 compute 在 onchange 里崩 —— 改为前端按需取）

> 修订日期：2026-09-24 ｜ 类型：修复（+z） ｜ 影响文件：
> `models/product_variant_mapping.py`、`static/src/js/variant_mapping_panel.js`、
> `tests/test_product_variant_mapping.py`、`i18n/zh_CN.po`、`__manifest__.py`、`AGENTS.md`

### 变更

1. **根因**：``variant_mapping_state`` 原本是 compute 字段（``@api.depends("attribute_line_ids", ...)``）。
   Odoo 的 ``onchange`` 会把**每个变更字段**挨个求值，于是产品表单**每次 onchange**
   （点 Add a line 后随便选一个属性就够）都会在「表单里还有没保存的行」的上下文里跑这个 compute：
   那些行的 id 是 ``NewId``，``json.dumps()`` 直接抛
   ``TypeError: Object of type NewId is not JSON serializable``，整个 RPC 500。
2. **修复**：把该字段降级为**纯挂载点**（``fields.Text(store=False)``、**不写 compute / 不写 depends**）——
   面板挂载时自己调 ``get_variant_mapping_preview()`` 取初始状态（切回页签重新挂载走同一条路）。
   服务端从此不再在 onchange 里为「前端展示用状态」做序列化。
3. **前端**：``setup()`` 不再解析字段值（删掉 ``parseValue()``），改为挂载即 ``scheduleRefresh()``。
4. **测试**：``test_panel_initial_state_comes_from_the_preview`` 校验「挂载点字段不做 compute、不落库」
   + 初始状态来自 RPC。
5. i18n：字段 help 文案随之改写，po 里对应 ``msgid`` / ``msgstr`` 已同步（仍然是英文源文本）。

### 影响

- 少一个 compute、多一次（原本靠字段省掉的）RPC；字段 ``store=False`` → **无数据库列、无迁移**。
- 需 `-u` + 强刷浏览器。

### 文档

- 模块 `AGENTS.md` → L2 P4 陷阱 12：**给前端看的状态不要做成 compute 字段** —— compute 会在
  onchange（带着未保存的虚拟记录）里被求值，序列化 ``NewId`` 必炸。

## [19.0.7.0.4] - 2026-09-24（修复：在属性页点「Add a line」就报必填缺失）

> 修订日期：2026-09-24 ｜ 类型：修复（+z） ｜ 影响文件：
> `models/product_template.py`、`models/product_variant_mapping.py`、
> `static/src/js/variant_mapping_panel.js`、`static/src/js/variant_conversion_form_patch.js`、
> `tests/test_product_variant_mapping.py`、`__manifest__.py`、`AGENTS.md`

### 变更

1. **根因**：点 **Add a line** 时前端生成的是一条「新建但还没选属性」的命令
   （``[0, 0, {"value_ids": ...}]``，没有 ``attribute_id``）；映射表的防抖刷新把它原样发给
   ``get_variant_mapping_preview()``，服务端拿去试写 → ``attribute_id`` 必填缺失 →
   用户**一点按钮**就收到 ``Missing required value for the field 'Attribute' (attribute_id)``。
2. **三层修复**：
   - 前端（第一层）：新增 ``hasIncompleteLine()``，识别这类半成品命令 —— 这种状态下**不调 RPC**，
     保持上一次的映射状态，等用户选好属性再算；
   - 服务端（第二层）：新增 ``_sanitize_attribute_line_commands()``，分析与试写前丢掉半成品行
     （同一次提交里正常的那几条照常参与分析）；
   - 服务端（第三层）：``get_variant_mapping_preview()`` 兜住 ``NotNullViolation``，回
     ``incomplete=True``（映射表不改状态、保存钩子交回原生校验）；Odoo **原生**的解释性 ``UserError``
     （例如「清空某行的属性」）照旧透出，不被吞掉。
3. 新增 3 项测试：半成品行不炸且不影响同批的正常命令、清空属性时原生文案不被吞。

### 影响

- 改动集中在前端刷新时机与 RPC 入参清洗，字段、视图 arch、数据结构**一律没动**；需 `-u` + 强刷。

### 文档

- 模块 `AGENTS.md` → L2 P4 陷阱 11：产品表单的命令流里有「新建但还没填必填」的半成品，
  预览类 RPC 必须清洗或兜底，不能让用户一点按钮就看到必填报错。

## [19.0.7.0.3] - 2026-09-24（修复：映射表面板被排到属性行右侧、看不见）

> 修订日期：2026-09-24 ｜ 类型：修复（+z） ｜ 影响文件：
> `views/product_template_views.xml`、`static/src/xml/variant_mapping_panel.xml`、`__manifest__.py`、`AGENTS.md`

### 变更

1. **根因**：字段外层的 `.o_field_widget`（`web.Field` 模板套的那层 div）是 `display: inline-block`；
   「属性与变体」页里的 `attribute_line_ids` 同样是 inline-block 且宽度不是 100%，于是面板被排到
   它**右边**（同一行）并溢出表单可视宽度 —— 表现就是「渲染出来了，但跑到右边、看不见」。
2. **修复**：视图里用一层 `<div class="d-block w-100">` 包住字段，字段本身也加
   `class="d-block w-100"`，让面板独占一行、占满表单宽度；组件模板根节点补 `w-100`。

### 影响

- 只改视图 arch 与模板的 class：需 `-u` + 强刷浏览器；字段、RPC、数据结构**一律没动**。

### 文档

- 模块 `AGENTS.md` → L2 P4 陷阱 10：自定义字段 widget（表格 / 多行）必须在视图里自己撑满一行。

## [19.0.7.0.2] - 2026-09-24（修复：映射表模板变量名写错，首次渲染即崩）

> 修订日期：2026-09-24 ｜ 类型：修复（+z） ｜ 影响文件：
> `static/src/xml/variant_mapping_panel.xml`、`__manifest__.py`、`AGENTS.md`

### 变更

1. **根因**：模板里写的是 `state.blocked` / `state.rows` / `state.newCombinations` …，而组件上这份状态叫
   **`this.store`**（`setup()` 里 `this.store = useState(getMappingStore(...))`）。OWL 模板表达式里
   `state` 不是保留字，只是一个不存在的名字 → `undefined.blocked`。
2. **现象**：`UncaughtPromiseError > OwlError`，cause 为
   `TypeError: Cannot read properties of undefined (reading 'blocked')`，栈落在
   `VariantMappingPanel.template`（`19.0.7.0.1` 修好字段注册方式后暴露出来的第二个前端错误）。
3. **修复**：模板里 9 处 `state.` 全部改成 `store.`；顺带核对了模板引用的其余名字
   （`introLabel` / `unmappedCount` / `axisLabels` / `variantDisplay` / `axisDisplay` / `chooseLabel` /
   `mappedLabel` / `unmappedAxisLabel` / `newVariantsLabel` / `onDemandHint` / `shareVendorPricesLabel` /
   `onSelectValue` / `onToggleShareVendorPrices`）都是组件上真实的 getter / 方法。
4. **新增静态检查**（`tests/test_frontend_consistency.py`，4 项，纯文本扫描、不需要浏览器）：
   ① 前端文件都登记进 `assets`；② 字段 widget 注册值必须是 `{component: ...}` 描述对象（陷阱 8）；
   ③ 模板表达式里的名字都能在组件上找到（陷阱 9）；④ `t-name` 与 `static template` 一一对应。
   已做负向验证：把 `store.` 写回 `state.`、把注册改回裸类，检查都会失败。

### 影响

- 纯前端模板改动，字段、视图 arch、RPC、数据结构**一律没动**，无迁移。
- 升级（`-u product_variant`）+ 强刷浏览器后，「属性与变体」页的映射表正常渲染。

### 文档

- 模块 `AGENTS.md` → L2 P4 陷阱 9：模板表达式只能引用**组件实例上真实存在的名字**
  （`state` 不是 OWL 保留字，写错只会得到 `undefined.x`，而且报错栈指到模板、不指向 `setup()`）。

## [19.0.7.0.1] - 2026-09-24（修复：映射表组件注册方式导致产品表单打不开）

> 修订日期：2026-09-24 ｜ 类型：修复（+z） ｜ 影响文件：
> `static/src/js/variant_mapping_panel.js`、`i18n/zh_CN.po`、`__manifest__.py`、`AGENTS.md`

### 变更

1. **根因**：`registry.category("fields").add("variant_mapping_panel", VariantMappingPanel)` 把**组件类**
   直接注册进字段注册表。Odoo 的字段注册值是**描述对象**（`web/static/src/views/fields/char/char_field.js`
   末尾：`registry.category("fields").add("char", charField)`），`web.Field` 模板渲染的是
   `field.component` —— 裸类下它是 `undefined`，owl 创建子组件时读 `Component.name` 直接抛错。
2. **现象**：打开产品表单（或点开「属性与变体」页签）报
   `UncaughtPromiseError > OwlError`，cause 为
   `TypeError: Cannot read properties of undefined (reading 'name')`，栈只落在 `Field.template`，
   不指向本模块的组件，极易误判为「升级后没重启 / 浏览器缓存」（服务端 `get_views` 里字段与视图
   其实都正常）。
3. **修复**：改为注册描述对象
   `{ component: VariantMappingPanel, displayName: _t("Attribute / Variant Mapping"), supportedTypes: ["text"] }`，
   并导出为 `variantMappingPanelField`。
4. i18n：`displayName` 的文案与字段 `string` 同字面，po 里合并成**一条** `msgid`（补
   `code:addons/product_variant/static/src/js/variant_mapping_panel.js:0` 引用与 `#. odoo-javascript` 标记）。

### 影响

- 前端只改了字段注册方式，映射表的数据流、RPC、保存拦截与列 / 表结构**一律没动**，无迁移。
- 升级（`-u product_variant`）+ 强刷浏览器后，产品表单与「属性与变体」页签恢复正常。

### 文档

- 模块 `AGENTS.md` → L2 P4 陷阱 8 改写为这条真实根因（原先把现象归因为「升级后未重启进程」，
  属于误判），含自查命令 `grep -rn 'category("fields").add(' <module>/static/src/js/`。

## [19.0.7.0.0] - 2026-09-24（模块改名 `product_variant` + 「属性 ↔ 变体」映射表）

> 修订日期：2026-09-24 ｜ 类型：架构/破坏性（+x，已装库需原地改名）+ 交互重构 ｜ 影响文件：
> 模块目录改名、`models/product_variant_mapping.py`（新增）、
> `static/src/js/variant_mapping_panel.js` / `static/src/xml/variant_mapping_panel.xml`（新增）、
> `static/src/js/variant_conversion_form_patch.js`、`views/product_template_views.xml`、
> `models/product_template.py`（保存拦截文案）、`i18n/zh_CN.po`、`__manifest__.py`、
> `README.md` / `AGENTS.md` / 本文件
> 删除：`static/src/js/variant_conversion_dialog.js`、`static/src/xml/variant_conversion_dialog.xml`

### 变更目标

1. 模块技术名 `product_variant_conversion` → `product_variant`（业务域名，为后续变体相关功能留位）。
2. 归属确认从「保存时弹一次模态框」改成「属性与变体页下方的常驻映射表」：改了属性立刻显示每条变体带哪个
   组合，缺取值的变体标记**未映射**，还有未映射的变体就**不放行保存**。

### 变更

1. **模块改名**（只改技术名）：目录、`__manifest__.py`（显示名「产品变体」/ 版本 / 资源路径）、
   OWL 模板注册名、系统参数前缀（新参数没设时回退读旧名，已设过的开关不失效）、全部文档与 po 引用。
   **模型名 `product.variant.conversion` / `product.variant.lineage`、所有字段与列名、视图 / 动作 /
   权限的 xmlid 一律不动** → 已装库原地改名即可，数据不丢（升级步骤见 `README.md`）。
2. **映射表**（`models/product_variant_mapping.py`）：
   - 新增 `get_variant_mapping_preview(attribute_line_ids, selection)`：复用现有「只写配置、不碰变体」的
     试写，返回每条既有变体在**这次改动之后**带哪个组合（`rows`）、未映射条数（`unmapped_count`）、
     本次会新建的组合，以及「会丢变体」的 blocked 提示（判定与文案沿用现有预览，不分叉）；
   - 新增非存储计算字段 `variant_mapping_state`：表单打开时就把当前（已保存的）映射交给前端，省一次 RPC。
3. **未映射判据**：某属性轴有多个取值、而这条变体在该轴上没有取值（既不是自己带着的、也不是用户刚选的）
   → 未映射。单取值轴与「按需生成」轴由 Odoo 自己补取值，不算未映射（行里标 `fixed`）。
4. **前端**：新增 field widget `variant_mapping_panel`（挂在属性行下方，`readonly="0"` 保证下拉可编辑）；
   属性行一改就防抖 300ms 问一次服务端；映射状态存在 `model.variantMapping` 上（切页签不丢选择）；
   保存钩子据此决定放行还是拦住，放行时把归属写进 `changes.variant_conversion_mapping`。
5. **弹窗删除**：`variant_conversion_dialog.js` / `.xml` 不再需要，「供应商价格共享」勾选框移到映射表下方。
6. **保存拦截文案**：改为「还有变体没有组合：请在属性行下方的映射表里给每条变体指定它保留的组合，然后再保存」。

### 影响

- 交互：从「点保存 → 弹窗确认 → 保存」变成「改属性 → 映射表里挑 → 保存」；未映射时保存被拦住
  （服务端同判据兜底，前端资源没生效时直接报错）
- 载荷格式（`variant_conversion_mapping`）与服务端转换逻辑不变；无数据结构变化、无迁移脚本
- 已装库必须走「原地改名」三条 SQL（见 `README.md`）；**卸载重装会清空台账 / 谱系 / 变体来源字段**

### 文档

- 模块 `README.md`（全文按新交互更新 + 新增「从 `product_variant_conversion` 改名升级」章节）、
  `AGENTS.md`（文件职责、约束、验证清单）、本条目
- 根 `README.md` / `AGENTS.md` / `TODO.md` 模块名与版本（`TODO.md` 归档为 `T-042`）

### 验证记录

| 跑法 | 结果 |
|------|------|
| `task test -- product_variant --test-tags=/product_variant` | 55 项全部通过（0 failed / 0 error） |
| 新增映射测试 8 项（当前配置 / 加属性后未映射 / 选值后恢复 / 未映射阻止保存 / 单取值自动补 / 按需自动补 / blocked / 初始状态字段） | 全部通过 |
| dev 库原地改名三条 SQL + `-u product_variant` | 升级无报错，模块 `installed` 19.0.7.0.0 |
| `task check`（仓库自检） | 无失败项（重复 msgid 已修；仅余测试断言里的既有中文告警） |
| 前端映射表（面板渲染 / 下拉 / 保存拦截） | **待目标环境验证**（无浏览器自动化） |

## [19.0.6.1.0] - 2026-09-24（归属弹窗：所有选项可选，重复选择自动互换）

> 修订日期：2026-09-24 ｜ 类型：交互优化（+y）｜ 影响文件：
> `static/src/js/variant_conversion_dialog.js` / `static/src/xml/variant_conversion_dialog.xml` /
> `i18n/zh_CN.po` / `__manifest__.py` / `AGENTS.md` / `README.md`（服务端零改动、无数据结构变化）

### 优化目标

归属弹窗原来把「已被别的组合选走」的既有变体在下拉里**置灰**（`t-att-disabled`）：想换个组合承载就必须
先把某个组合改回「新变体」腾出位置，来回两步才能完成一次互换，且用户看不出为什么某个选项点不了。

### 变更

1. **所有下拉选项都可选**（`variant_conversion_dialog.xml` 去掉 `t-att-disabled`）。
2. **选中已被占用的选项即互换**：新增纯函数 `applyOwnershipSelection(selection, index, variantId)`
   —— 若该既有变体已被另一行占用，就把「占用者」改成当前行原先的选项，再给当前行赋新值。
   于是任意时刻每条既有变体仍然**只被一行占用**，也不会出现「重复占用」或「两边都空着」。
   例（用户给的场景）：单变体产品转成 Black / White 两个组合，默认原变体落在 Black；
   在 White 那行也选「原变体」→ Black 拿到「新变体」、White 拿到原变体，两个下拉的显示同步更新。
3. `onSelect()` 改为生成新的 selection 对象再赋回 `state.selection`（OWL `useState` 响应式刷新两行显示）；
   删除已无用的 `isVariantUsed()`。
4. 弹窗顶部说明补一句「每个选项都可以选：选中已被别的组合占用的变体会与那个组合互换」，同步 `zh_CN.po`。

### 影响

- 交换归属从「两步（先腾位置再选）」变成「一步（直接选，自动互换）」；`Confirm` 的可用条件
  （每条既有变体都已被分配）不变，因此不会出现「都指同一条变体」的非法载荷
- 服务端、载荷格式、默认归属全都不变；无数据结构变化、无迁移

### 文档

- 模块 `README.md`（「怎么用、归属怎么指定」、核心设计、验证清单）、`AGENTS.md`（文件职责、L2 P4）、本条目
- 根 `README.md` 模块一览表版本、`TODO.md`（`T-040` 归档）

### 验证记录

| 跑法 | 结果 |
|------|------|
| 纯函数一次性验证（node，6 组用例 + 「无重复占用」不变量） | Black/White 示例互换、两行互换、选「新变体」不影响别人、三行抢占、重复选自身、单行均可通过 ✓ |
| `node --check` | 语法通过 ✓ |
| `task test -- product_variant` 等四组配置 | 47 项 0 failed / 0 error ✓（服务端未动，用回归确认） |
| `task update -- product_variant` | 升级无报错，前端资源已登记在 `assets` ✓ |
| 目标环境 | 弹窗交互（选项全可选 / 互换后两行显示同步 / 中英文提示）**待验证**（前端改动，需 `-u` + 强刷浏览器） |

---

## [19.0.6.0.0] - 2026-09-24（T-039：支持「按需生成变体」的属性 —— 只展开「立即」轴）

> 修订日期：2026-09-24 ｜ 类型：功能新增（+y）｜ 影响文件：`models/product_template.py` /
> `static/src/js/variant_conversion_dialog.js` / `static/src/xml/variant_conversion_dialog.xml` /
> `tests/test_product_variant_conversion.py` / `i18n/zh_CN.po` / `__manifest__.py` /
> `AGENTS.md` / `README.md`（无数据结构变化、无迁移）

### 优化目标

`19.0.5.3.1` 起，只要产品带「按需生成变体」（`create_variant == 'dynamic'`）的属性，
本模块就**整块拒绝**改属性。但这条边界很痛：**Odoo 的产品导入会把新建属性自动设成「按需生成」**，
导入来的产品因此在表单里改不了任何属性，而 Odoo 又不允许修改「已被产品使用」的属性的变体生成方式 ——
用户只能走「归档 / 删除变体 → 摘掉属性行 → 改属性设置 → 再加回来」这条难路。

`T-039` 把这条边界打开：**只展开「立即」（`always`）的属性轴，按需轴不展开**。

### 变更

1. **组合枚举按「轴」分类**：`_split_variant_conversion_lines()` 把属性行分成
   「本模块负责展开的（`always`）」与「固定取值、不展开的（`dynamic`）」；
   `_get_variant_conversion_combinations()` 改成「每条既有变体 × 各『立即』属性的取值组合」
   （按需轴取该变体现带的取值，没有则取第一个取值 —— 见 `_get_variant_conversion_fixed_values()`），
   最后仍过一遍 Odoo 的排除规则并去重。**只有「立即」属性时结果与老版本逐条一致**。
2. **新增变体自己建**：`_create_variant_ids()` 遇到按需生成的属性会整段跳过新建，所以
   `_create_variant_conversion_missing_variants()` 用 Odoo 自己的 `_create_product_variant()`
   （销售配置器同款入口）补上「计划里还没有变体」的组合；按需轴的其它取值**不建**，
   仍然由 Odoo 在订单里创建。`_create_variant_conversion_combination()` 负责给
   「不生成变体」的属性行补占位取值，好通过 `_is_combination_possible()` 的校验。
3. **原生会丢变体时必须自己锚定**：分析新增 `needs_anchoring` —— 某条既有变体没带上某个
   **多取值**属性行的取值时，原生 `_create_variant_ids()` 会把它的组合判成「不完整」而删掉它；
   这种情况（例如给产品加一个多取值的按需属性）不再走「原生保存」，改为走转换、用默认归属锚定
   （没有新变体，所以不弹窗）。
4. **带按需属性的产品不做价格分离**：分离会把模板级的供应商价格 / 价格表规则拆到既有变体上并删掉
   原记录，而这类产品以后还会由 Odoo 在订单里新建变体 —— 那些新变体就再也取不到价格。
   所以这类产品保持模板级共享（台账 `separate_variant_prices` 记为否），弹窗里也不再显示勾选框。
5. **组合数上限按新口径**：带按需属性时 = `既有变体数 × 各「立即」属性有效取值数乘积`（按需轴不乘）。
6. **保留的拦截**：建产品时带按需生成的属性仍然拒绝（原生会建出「有属性、没变体」的产品），
   文案改为**可执行**的出路：先不带该属性把产品建好、保存，再把属性加到产品上（本模块会保住既有变体）。
7. **弹窗提示**：预览接口新增 `dynamic`，弹窗据此显示「按需轴的其它取值不会现在建变体」的提示，
   并隐藏供应商价格勾选框。
8. 删除已无用的两条拒绝文案（属性行级别的「按需生成」拒绝、入口校验里的同款），同步 `zh_CN.po`；顺手补上
   `code:.../variant_conversion_dialog.js:0` 那条 `%(label)s — %(count)s on hand` 缺失的
   `#. odoo-javascript` 标记（缺标记的前端译文**永远不下发且不报错**，弹窗「在手 N」的中文一直没生效 ——
   即 `T-026` 在本模块的那 1 条）。
9. 测试 46 → **47 项**：`test_dynamic_attribute_is_refused` 换成两条正向用例
   （按需产品只展开「立即」轴 / 加按需属性不能丢变体），并更新「订单期变体不被接管」那条边界用例。

### 影响

- **导入来的产品现在可以正常改属性**：加「立即」属性会弹窗确认归属，既有变体一条不少，
  只多出「展开轴」带来的变体；按需轴的其它取值仍然按订单创建
- 给既有产品加**多取值**的按需属性：既有变体不再被原生删掉（改由本模块锚定到第一个取值）
- 带按需属性的产品：价格记录保持模板级（不做按需分离）——这是刻意的，见上文第 4 条
- 只有「立即」属性的产品（绝大多数）：行为**一字不变**（46 项老用例全部保持通过）
- 无数据结构变化、无迁移

### 文档

- 模块 `README.md`（场景矩阵 S11、使用前提、被拒绝的改动、价格分离、已知边界、后续迭代、验证清单）、
  `AGENTS.md`（L1 约束 18 改写、L2 P5 覆盖矩阵与缺口 10 结案）、本条目
- 根 `README.md` 模块一览表版本、`TODO.md`（`T-039` 移入「已归档」）

### 验证记录

| 跑法 | 结果 |
|------|------|
| `task test -- product_variant` | 47 项 0 failed / 0 error ✓ |
| `task test -- product_variant,stock,sale_management` | 47 项 0 failed / 0 error ✓ |
| `task test -- product_variant,product_dimension` | 47 项 0 failed / 0 error ✓ |
| `task test -- product_variant,product_reference,product_card_view,sale_management` | 57 项 0 failed / 0 error ✓ |
| shell 实测（按需产品加「立即」属性） | 计划组合 4 条（未展开未被使用的按需取值）、既有变体原记录保留、新增 2 条带来源字段、台账 1 / 谱系 4、`separate_variant_prices=False` ✓ |
| shell 实测（加多取值按需属性） | 预览 `required=False`、原变体记录存活并锚定到第一个取值（原生原本会删掉它）✓ |
| 目标环境 | 导入产品加属性、弹窗提示与中文文案**待验证** |

---

## [19.0.5.3.2] - 2026-09-24（修：一次加两个属性时 chatter 记录抛 Expected singleton，整单回滚）

> 修订日期：2026-09-24 ｜ 类型：修复（+z）｜ 影响文件：`models/product_template.py` /
> `tests/test_product_variant_conversion.py` / `__manifest__.py` / `AGENTS.md` / `README.md`（无 i18n、无数据、无迁移）

### 问题（目标环境上报）

一次保存里**同时加两个属性**（例如 `Color` + `Size`）时，转换的最后一步
`_log_variant_conversion()` 抛 `ValueError: Expected singleton: product.attribute(2, 1)`
（`models/product_template.py` 里 `added_attributes.display_name` —— 对**多记录集**取单值），
报错发生在转换内部，**整单回滚**：用户看到「Odoo Server Error」，属性与变体都没落库。

一次只加一个属性时 `added_attributes` 是单条记录，不会触发 —— 这正是原来 44 项测试没覆盖到的原因。

### 变更

1. `_log_variant_conversion()` 改为 `", ".join(added_attributes.mapped("display_name")) or "-"`
   （空记录集仍显示 `-`，即「只追加取值、没加新属性」的场景），并就地写下这条坑的说明。
2. 新增回归用例 `test_adding_two_attributes_at_once_is_logged_with_both_names`：一次加两个属性 →
   4 条变体、chatter 里两个属性名都在。**已实测该用例在旧代码上会复现同一条 `Expected singleton`**。
3. 新增边界用例 `test_variants_created_on_demand_are_neither_blocked_nor_adopted`：按需生成的产品在
   **订单期**由 Odoo 自建变体（配置器 → `_create_product_variant()` → `product.product.create()`）时，
   本模块**既不拦也不接管**（无来源字段 / 无台账 / 无谱系），且产品属性依旧改不了。
4. 测试 44 → **46 项**。

### 影响

- 一次加多个属性的保存（此前**必然失败**）：现在能正常完成
- 一次加一个属性、只追加取值、建产品：行为不变（`-` 与单属性名照旧）
- 无数据结构变化、无迁移；无需改 po（`msgid` 未变）

### 已知边界的补充核实（同批交付的文档）

为回答「按需生成的产品，订单期生成变体时本模块能不能正确处理」，把两件事核实清楚并写进文档：

| 事实 | 结论 |
|------|------|
| 订单期创建变体的路径 | 配置器 → `sale.order.line` → `product.template._create_product_variant()` → `product.product.create()`，**不经过 `product.template.write()`** |
| 本模块的介入 | **不拦、也不接管**：不写 `Variant Conversion` / `Derived From`、不写台账 / 谱系、不做按谱系继承（继承只在本模块自己的转换里）；这类产品的属性改动本来就被拒（L1 约束 18），所以它的变体永远由 Odoo 自己建 —— 要带来源 / 继承得等 `T-039` |
| 新发现的风险 | 非沙盒上下文的 `product.template.attribute.line.create()` 会自己调 `_create_variant_ids()`：对按需生成的产品，新加一行会让既有变体组合「不完整」，原生把它们**直接删掉**（实测 2 条在用变体消失）。属性行守卫只覆盖「移走取值 / 删行」，**未覆盖「新增行」**（`T-017` 遗留） |

### 文档

- 模块 `AGENTS.md`（L2 P3 新增陷阱 5：多记录集不能取 `.display_name` / `.id` 这类单值属性；
  L2 P5 新增「订单期变体完全在本模块之外」、缺口 1 补齐 `line.create()` 实测）、
  `README.md`（测试数、验证清单、已知边界新增两行：订单期不接管 + 直接写属性行会绕过）、本条目
- 根 `README.md` 模块一览表版本、`TODO.md`（`T-039` 补上这次核实的两条事实）

### 验证记录

| 跑法 | 结果 |
|------|------|
| `task test -- product_variant` | 46 项 0 failed / 0 error ✓ |
| `task test -- product_variant,stock,sale_management` | 46 项 0 failed / 0 error ✓ |
| `task test -- product_variant,product_dimension` | 46 项 0 failed / 0 error ✓ |
| `task test -- product_variant,product_reference,product_card_view,sale_management` | 56 项 0 failed / 0 error ✓ |
| 新用例在**旧代码**上的表现 | 复现 `ValueError: Expected singleton: product.attribute(1, 2)` ✓（证明用例有效） |
| 订单期创建变体（shell 实测） | 变体正常创建；`variant_conversion_id` / `variant_origin_id` 为空、谱系 0 行、台账 0 条、成本 / 体积 / 重量保持 0 ✓（与文档一致） |
| 目标环境 | 加两个属性的保存复验**待验证**（`-u` 后重做一次即可，之前失败的那次没有写入任何数据） |

---

## [19.0.5.3.1] - 2026-09-23（按需生成属性：报错点名 + 建产品时就拦住，不留「有属性、没变体」的产品）

> 修订日期：2026-09-23 ｜ 类型：修复（+z）｜ 影响文件：`models/product_template.py` /
> `tests/test_product_variant_conversion.py` / `i18n/zh_CN.po` / `__manifest__.py` /
> `AGENTS.md` / `README.md`（无数据结构变化、无迁移）

### 问题（用户上报）

产品带「按需生成变体」（`create_variant == 'dynamic'`）的属性时：

1. **建产品直接把这类属性加进「属性与变体」页**：保存**不报错**，但产品**一条变体都没有**
   —— 原生 `create()` 末尾的 `_create_variant_ids()` 一遇到按需生成的属性就整段跳过
   （`if not tmpl_id.has_dynamic_attributes()`），于是留下一个「有属性、没变体」的产品：
   卖不了，也进不了本模块的转换流程（转换前提是「至少有一条既有变体可以保留」）。
2. **之后任何改属性的保存**都被本模块拒绝，但报错文案是**通稿**（不说是哪个属性），
   且给的出路**走不通**：Odoo 不允许修改「已被产品使用」的属性的变体生成方式
   （`product.attribute.write()` 的 `number_related_products` 检查），而「先把属性从产品上摘掉」
   这一步又因为变体带着它的取值被本模块的属性行守卫拦住 —— 用户卡死。
   （实践中很容易踩到：**Odoo 的产品导入会把新建属性自动设成「按需生成」**，
   见 `product.product._load_records_create()`。）

### 变更

1. 新增 `_get_variant_conversion_dynamic_attributes()`：返回产品上按需生成的属性**记录集**
   （与 Odoo 自己的 `has_dynamic_attributes()` 同源，区别是能点名）。
2. 新增 `_get_variant_conversion_dynamic_message()`：**前端预览与服务端拒绝共用同一份文案**，
   点名属性并给出**能走通**的出路 —— 先把该属性从产品上移除、再把它的「变体生成方式」改成
   「立即」、最后加回产品。原来那条通稿（`The product %(product)s creates variants on demand ...`）
   删除，`write()` / `get_variant_conversion_preview()` / `_check_variant_conversion_allowed()`
   三处统一改用它。
3. 新增 `create()` 拦截：建产品时若带上按需生成的属性，直接拒绝（此时属性**还没被任何产品使用**，
   Odoo 允许改它的变体生成方式，报错里的出路是当场可执行的）。
   `create_product_product=False`（产品导入等「调用方自己管变体」的沙盒模式）一律放行。
4. 测试 42 → **44 项**：`test_dynamic_attribute_is_refused` 补「点名属性 + 出路文案」断言；
   新增 `test_product_created_with_a_dynamic_attribute_is_refused`（拒绝且不留半成品）、
   `test_product_creation_in_the_variant_sandbox_is_left_alone`（沙盒模式放行）。

### 影响

- 带按需生成属性的产品：改属性依旧**被拒绝**（设计不变，变体由 Odoo 按订单创建），
  但报错现在点名属性且出路可执行；**建产品**这一步从「静默留一个没变体的产品」变成「当场拒绝」
- 产品导入（`base_import`）**不受影响**：它走 `create_product_product=False` 的沙盒路径自己建变体
- 无条件属性（`always`）的产品：行为一字不变（原有 42 项用例全过）
- 无数据结构变化、无迁移；只有在产品带按需生成属性时才会命中新逻辑

### 文档

- 模块 `README.md`（「使用前提与限制」、被拒绝改动表、已知边界新增「产品导入建出的按需生成属性」、
  后续迭代新增第 7 条、验证清单与异常处理）、`AGENTS.md`（L1 新增约束 18、P5 矩阵与缺口）、
  本条目
- 根 `README.md` 模块一览表版本、`TODO.md`（新增 `T-039`）

### 验证记录

| 跑法 | 结果 |
|------|------|
| `task test -- product_variant` | 44 项 0 failed / 0 error ✓ |
| `task test -- product_variant,stock,sale_management` | 44 项 0 failed / 0 error ✓（含依赖模块回归） |
| `task test -- product_variant,product_dimension` | 44 项 0 failed / 0 error ✓ |
| `task test -- product_variant,product_reference,product_card_view,sale_management` | 54 项 0 failed / 0 error ✓（另两个模块用 `create` 带属性行建产品，验证没有误伤） |
| 目标环境 | 中英文报错文案与「建产品被拦」的界面表现**待验证** |

---

## [19.0.5.3.0] - 2026-09-23（彻底与 product_reference 解耦：转换不再改变体编号、不再交接参考号）

> 修订日期：2026-09-23 ｜ 类型：行为调整（+y）｜ 影响文件：`models/product_template.py` /
> `models/product_variant.py` / `tests/test_product_variant_conversion.py` /
> `i18n/zh_CN.po` / `__manifest__.py` / `AGENTS.md` / `README.md`

### 优化目标

按要求让本模块**彻底与 `product_reference` 解耦**：不再读写对方的任何字段
（`base_reference` / `reference_code_line_ids` / `variant_reference_code_line_ids`）、
不再判断对方是否安装。转换只做它自己的事 —— **按用户确认的归属复用既有变体**，
`product.product` 上的值（含 `default_code`）**原样保留**。

移除的两处历史耦合：

| 历史行为 | 引入版本 | 为什么要移除 |
|----------|----------|--------------|
| 把单变体时期的编号「上移」成产品编号、清空原变体编号 | `19.0.5.1.0`～`19.0.5.2.1` | 需要知道对方的字段与「单变体镜像」约定；对方已改为「单变体两处同值、产品编号由自己叠加进 `default_code` 的 compute」，本模块不该参与编号归属 |
| 把产品级共享参考号「交接」给被保留的变体 | `19.0.4.1.1`～`19.0.5.2.1` | 前提是「对方在多变体时隐藏产品级参考号」，该前提已被对方 `19.0.3.0.0` 取消（两层各自独立、都可见），交接反而把行搬离了它的归属层 |

### 变更

1. 删除步骤 ⑤.5 `_move_single_variant_reference_to_base_reference()` 与 ⑦.5
   `_transfer_shared_references_to_original()` 及其调用、以及 `19.0.5.2.1` 引入的
   「可选集成适配层」三个方法（`_has_base_reference_field()` / `_has_shared_reference_lines()` /
   `_get_reference_code_model()`）。
2. `_convert_to_multi_variant()` 的步骤编号顺延（⑤ 之后直接 ⑥ 谱系、⑦ 继承、⑧ 价格）；
   转换结果里**没有任何一处**会读写 `default_code` 或参考号行。
3. 谱系字段 `result_default_code` 的 help 文案回到原义（「参考号属于变体，转换不会改动它」），
   manifest 描述里那条「编号会被上移」的说明改为「变体级数据原样保留」，两者同步 `zh_CN.po`。
4. 测试：删除两条母型号用例与降级用例；两条参考号交接用例合并为
   `test_references_are_left_untouched_by_the_conversion()`（转换一行参考号都不搬）；
   `test_variant_level_values_stay_on_the_kept_variant()` 恢复「编号 / 条码 / 成本 / 体积 / 重量
   一个都没变」的断言，`test_product_data_stays_on_the_variant_that_keeps_the_product()` 恢复无条件断言。

### 影响

- 单变体 → 多变体后：被保留的那条变体**仍带着原来的编号**（如 `KEEP-001`），新变体没有编号 ——
  用户按变体自己填；产品级编号由 `product_reference` 负责（单变体产品两处同值，转换后产品编号不变、
  变体编号也还在，两层互不影响）
- 产品级参考号行**留在产品上**（不再被搬到某条变体），产品表单与变体表单各自维护自己那一层
- 未装 `product_reference` 时行为完全不变（本来就不参与）
- 无数据结构变化、无迁移；测试 46 → **42 项**（删除 4 条、合并 2 条为 1 条）

### 文档

- 模块 `AGENTS.md`（L2：删除编号上移 / 参考号交接两段，改为「与 product_reference 零耦合」+
  「变体上的值一律原样保留」）、`README.md`（属性归属审计表、可选集成表、「新变体不会自动获得的东西」）、
  本条目
- 根 `README.md` 解耦矩阵与版本行、`TODO.md`（`T-035`）同步

### 验证记录

| 跑法 | 结果 |
|------|------|
| `task test -- product_variant`（未装 `product_reference`） | 42 项 0 failed / 0 error ✓ |
| `task test -- product_variant,product_reference` | 48 项 0 failed / 0 error（含参考号「原样不动」用例）✓ |
| 三模块同装 + `stock` | 见该组合的回归记录 ✓ |
| 目标环境 | 弹窗交互与界面复验**待验证** |

---

## [19.0.5.2.1] - 2026-09-22（对可选模块的了解收敛进适配层 + 降级用例）

> 修订日期：2026-09-22 ｜ 类型：优化（+z）｜ 影响文件：`models/product_template.py` /
> `tests/test_product_variant_conversion.py` / `AGENTS.md` / `README.md` / `__manifest__.py`（无数据、无 i18n 改动）

### 优化目标

本模块 `depends` 只有 `product`，`product_reference` 是**可选**集成 —— 任何模块组合下转换都必须成功。
但审计发现两处「间接假设」，一旦对方改名 / 被打补丁就会让**每一次转换**崩掉：

1. `_transfer_shared_references_to_original()` 里 `self.env["product.reference.code"]`（模型不在注册表
   就是 `KeyError`），只靠同一函数上一行的字段判断间接保证；
2. 交接后调 `self._sync_reference_index()` 是对方定义在 `product.template` 上的方法，只靠「字段在 ⟺
   方法在」这个隐含前提取用。

同时把「对 `product_reference` 的全部了解」从散落各处收敛到**一个适配层**，让边界可读、可测、可一处修改。

### 变更

1. 新增「可选集成适配层」（`models/product_template.py` 内同名注释段）三个方法：
   `_has_base_reference_field()` / `_has_shared_reference_lines()` / `_get_reference_code_model()`；
   两个消费点改成用它们判断，字段名与模型名从此只出现在适配层里。
2. `_get_reference_code_model()` 用 `env.get("product.reference.code")`（未注册返回 `None`），
   不再出现任何 `env[对方模型名]`。
3. `_sync_reference_index()` 改为 `getattr` 探测方法存在后再调用，去掉「字段在 ⟺ 方法在」的隐含前提。
4. 新增降级用例 `test_reference_handling_degrades_gracefully_without_product_reference()`：
   在**两种配置**下都跑，分别断言「装了 → 编号上移成母型号」「没装 → 编号原样留在变体上、转换照常成功」。
5. 文档补齐可选集成矩阵（README →「可选集成与解耦边界」）与硬约束（AGENTS → L2）。

### 优化前后对比

| 场景 | 优化前 | 优化后 |
|------|--------|--------|
| 未装 `product_reference` | 靠字段判断跳过；分支内藏 `env[对方模型]`，模型缺失即 `KeyError`（每次转换都失败） | 适配层统一判断，取模型走 `env.get()`，缺席时两步都空转、转换照常完成 |
| 对方被第三方改名 / 改字段 | 字段名散落 5 处、方法名 1 处，漏改一处即崩 | 只改适配层那 3 个方法 |
| 降级行为是否有测试 | 无常驻用例（只有「装了」路径的用例） | 新增用例在两种配置下分别断言，`skip` 只覆盖「装了才有意义」的部分 |

### 影响

- 行为不变（装了 / 没装 `product_reference` 的转换结果与 `19.0.5.2.0` 完全一致）
- 无数据结构变化、无迁移；测试 **45 → 46 项**（`odoo.tests.result` 口径，新增 1 条降级用例）

### 文档

- 模块 `README.md` →「依赖」下新增「可选集成与解耦边界」表（含 `product_dimension` / `stock` 等）
  与「本模块会拦截改属性的 `write()`，程序化建变体请走 `create()`」提示
- 模块 `AGENTS.md` → L2 新增适配层约束与 `create()` 提示；根 `README.md` 新增「扩展解耦矩阵」；
  `TODO.md`（`T-034`）

### 验证记录

| 跑法 | 结果 |
|------|------|
| `task test -- product_variant`（未装 `product_reference`） | 46 项 0 failed / 0 error（新用例走「没装」分支）✓ |
| `task test -- product_variant,product_reference,product_card_view`（三模块同装） | 54 项 0 failed / 0 error（含另两个模块的用例）✓ |

---

## [19.0.5.2.0] - 2026-09-22（编号上移改为唯一来源，母型号以变体编号为准）

> 修订日期：2026-09-22 ｜ 类型：行为调整（+y）｜ 影响文件：`models/product_template.py` /
> `__manifest__.py` / `i18n/zh_CN.po` / `tests/test_product_variant_conversion.py`

### 优化目标

`19.0.5.1.0` 上移编号时要求「产品母型号已经和变体编号同值」才清空变体编号 —— 那是建立在
`product_reference` 「单变体写两处」的镜像写法上的。该镜像已被 `product_reference` `19.0.2.7.0`
删除（同一份数据写两处必然出现不一致），因此这一步改为**转换本身就是母型号的数据来源**：
单变体产品的变体编号就是产品型号，上移时**覆盖式写入**，不再与产品侧已有值比对。

### 变更

1. **`_move_single_variant_reference_to_base_reference()` 简化**：转换前唯一那条变体有编号时，
   无条件把它写进 `product.template.base_reference`（覆盖产品侧可能残留的值）并清空变体编号；
   覆盖了不同的旧值时记一条日志便于追溯。
2. **去掉「编号与母型号不同就保留」的分支**：单变体产品侧不再有任何合法来源，留着只会让
   「多变体退回单变体」的残留值拦住上移。
3. **变体没有编号时仍然什么都不做**：此时产品侧若有母型号（残留），保留比误删安全 —— 已加测试钉住。
4. manifest 描述措辞同步（`stays on` → `is moved to`），`i18n/zh_CN.po` 的 `description:` 条目同步。

### 影响

- 单变体转多变体：产品母型号 = 原变体编号（覆盖式），两条变体的编号都为空（待用户按变体填）；
  值一处不丢
- 「多变体退回单变体」后再转多变体：残留母型号不会被清成空；若那条变体有编号，则以编号为准
- 未装 `product_reference` 时行为完全不变（整个方法直接返回）
- 无数据结构变化、无迁移；测试 45 项（改写两条母型号用例）

### 文档

- 模块 `AGENTS.md`（L2「唯一的例外」重写、版本行）、`README.md`（属性归属审计表一行 + 说明块）、
  本条目
- `19.0.5.1.0` 条目已加注：其第 2 点中的「母型号为空时才上移」被本版替换
- 根 `README.md` / `AGENTS.md` 版本行、仓库 `TODO.md`（`T-033`）同步

### 验证记录

| 跑法 | 结果 |
|------|------|
| `task test -- product_variant,product_reference` | 45 项 0 failed / 0 error（含 `test_single_variant_reference_moves_to_the_product_base_reference` 与 `test_variant_reference_wins_over_a_leftover_base_reference`）✓ |
| `task test -- product_variant`（未装 `product_reference`） | 45 项 0 failed / 0 error，两条用例按预期 skip ✓ |
| `… -- product_variant,product_dimension`、`… ,stock,sale_management` | 目标环境待验证（本地未跑该组合） |

---

## [19.0.5.1.0] - 2026-09-22（单变体的内部参考号升级为产品母型号）

> 修订日期：2026-09-22 ｜ 类型：功能新增（+y）｜ 影响文件：`models/product_template.py` /
> `models/product_variant.py` / `tests/test_product_variant_conversion.py` /
> `i18n/zh_CN.po` / `__manifest__.py`
>
> ⚠ **本条的第 2 点已被 `19.0.5.2.0` 替换**：上移不再要求「母型号已同值」，
> 改为**覆盖式写入**（转换本身就是母型号的数据来源），理由见该条目的「优化目标」。

### 变更

1. **新增 ⑤.5 步 `_move_single_variant_reference_to_base_reference(originals)`**：转换前唯一那条变体
   若顶着产品型号，把型号留在产品上（`product.template.base_reference`，`product_reference` 模块提供）、
   清空它的 `default_code`。放在 ④ `_create_variant_ids()` **之后**：此时产品已是多变体，
   `product_reference` 的单变体镜像（只在单变体时把两处写同值）不会再介入。
2. **三条边界**（都写在方法 docstring 里）：
   - 只在**转换前恰好一条变体**时处理 —— 本来就是多变体的产品，各变体编号本来就独立，转换一个都不动；
   - 母型号为空时**先把编号记到产品上再清变体**（升级前建的存量产品、直接写变体导入的编号不丢数据）；
   - 编号与母型号不同（用户刻意区分）时**保留**，只记日志。
   - 未安装 `product_reference`（没有 `base_reference` 字段）时整个方法直接返回，不做任何事。
3. **谱系字段 help 文案同步**：`product.variant.lineage.result_default_code` 原先写着
   「转换不会改动它」，现在不再成立，改为「单变体产品转换时该编号留在产品上作母型号、并从变体上清空」，
   `i18n/zh_CN.po` 对应条目同步（msgid + msgstr）。
4. **manifest 描述新增一条**说明参考号不丢（留在产品母型号上），`i18n/zh_CN.po` 的 `description:` 同步。

### 影响

- 单变体产品（`G001`）转成多变体后：产品上母型号 = `G001`，两条变体的 `default_code` 都是空 ——
  用户按变体各填 `G001-WT` / `G001-BK`，不再出现「被保留的那条看起来像整机、其它变体没编号」
- 本来就是多变体的产品：转换**完全不动**变体编号（新增断言钉住）
- 未装 `product_reference` 的环境：行为与 `19.0.5.0.0` 完全一致（两条新用例自动跳过）
- 无数据结构变化、无迁移；测试 **43 → 45 项**（`odoo.tests.result` 口径，新增两条用例）

### 文档

- 模块 `README.md`（「新变体不会自动获得的东西」补说明、属性归属审计表两行更新）、`AGENTS.md`
  （版本行 + L2 字段归属节新增「唯一的例外」）、本条目
- 根 `README.md` / `AGENTS.md` 模块版本行同步；仓库 `TODO.md`：`T-033` 落地 → 归档

### 验证记录

| 跑法 | 结果 |
|------|------|
| `task test -- product_variant,product_reference` | 45 项 0 failed / **0 error**（含两条新用例：母型号迁移、母型号为空时先存后清）✓ |
| `task test -- product_variant`（未装 `product_reference`） | 45 项 0 failed / 0 error，两条新用例按预期 skip ✓ |
| `task test -- product_variant,product_reference,stock,sale_management` | 目标环境待验证（本地未跑全套可选模块组合） |

---

## [19.0.5.0.0] - 2026-09-22（谱系来源判定更准 + 修复「没装 product_reference 时转换必崩」）

### 变更

- **谱系来源判定换算法**（新增 `_find_variant_conversion_origin()` / `_get_variant_conversion_origin_key()`）：
  改为按「**转换前就存在的取值**」匹配 —— 只看新变体保留着老取值的那些属性轴，候选原变体在这些轴上的
  取值必须完全一致，一致的有多个时取最具体的那个，仍并列才判为不唯一。

  旧算法比对的是「转换前存在的**属性轴**上的取值组合」，而本次新加的取值同样落在这些轴上，于是
  **给已有属性加取值**（最常见的一种转换）时新变体永远匹配不上任何原变体：只有一条原变体时才靠兜底
  规则指对，多条原变体时新变体一律「无来源」，`product_dimension` 的尺寸 / 原生 Volume / 成本
  **就此丢失**。现在 `Red/M`、`Blue/M` 这类原变体能被准确认出来，新变体的数据落到**对应**的
  `product.product` 上（新增两条测试钉住映射与尺寸继承）。
- **修复：未装 `product_reference` 时每一次转换都失败**。`_transfer_shared_references_to_original()`
  在跳过分支里 `browse` 了 `product.reference.code` —— 模块没装时该模型不在注册表，`env[模型名]`
  直接抛 `KeyError`，转换整单回滚。纯 `product` 环境下（本模块只依赖 `product`）这是必现故障：
  HEAD 上实测 33/43 条用例 error，修复后 0 error。改为返回硬依赖 `product.product` 的空记录集。
- **修复：`_log_variant_conversion()` 在程序化调用时拿 `None` 报错**。它用的是入参 `added_attributes`
  （程序化调用不传时为 `None`），改为用推断后的 `new_attributes`。
- **移除不再需要的 `previous_attribute_lines` 参数**（`_convert_to_multi_variant()` 及其内部快照）：
  来源判定按各变体携带的取值认，不再依赖「改动前的属性行快照」，`write()` 相应少传一个参数。

### 影响

- 行为变化：给已有属性加取值时，新变体不再「无来源」，而是准确挂到对应原变体上并继承其变体级数据
  （成本 / 体积 / 重量 / 装了 `product_dimension` 时的尺寸）；判定确实不唯一时仍然留空，不乱指
- 修复类变化：没有 `product_reference` 的环境（含只装 `product` 的干净库）转换恢复可用
- 无数据结构变化、无迁移；测试 39 → **43 项**

### 文档

- 模块 `README.md`：「新变体继承策略」补来源判定规则与「加取值」举例，测试数与验证清单同步
- 模块 `AGENTS.md` → L2 P5 更新来源判定与跨模块协同说明；文件职责表补两个新方法
- 模块 `CHANGELOG.md` 本条目；根 `README.md` / `AGENTS.md` 版本行同步

### 验证记录

| 跑法 | 结果 |
|------|------|
| `task test -- product_variant`（只装 `product`） | 43 项 0 failed / **0 error**（修复前 33 error）✓ |
| `… -- product_variant,product_dimension` | 43 项 0 failed（含尺寸落到对应变体的新用例）✓ |
| `… -- product_variant,product_reference` | 43 项 0 failed（走参考号交接分支）✓ |
| `… -- product_variant,stock,sale_management` | 43 项 0 failed ✓ |

---

## [19.0.4.1.1] - 2026-09-22（修复：转换后产品级共享参考号无处可去）

### 变更

- **转换时把「产品级共享参考号」交接给被保留的变体**（装了 `product_reference` 时生效）：
  新增步骤 ⑦.5 `_transfer_shared_references_to_original(originals)`，把
  `reference_code_line_ids`（`product_tmpl_id` 那一层）改挂到被保留的那条变体上
  （`write({"product_id": kept.id, "product_tmpl_id": False})`），并显式重算源产品的
  `reference_code_index`（参考号行的 `write` 只同步「新主人」一侧的索引）。
- **根因**：`product_reference` 的参考号有两种归属（二选一）—— 产品级共享（产品表单维护）与
  变体级（变体表单维护），且「多变体产品不共用」：产品表单在 `product_variant_count > 1` 时**整块隐藏**
  参考号区域。单变体产品上用户录入的正是产品级那一层；转换后它既不在产品表单（已隐藏）、
  也不在变体表单（那里只认变体级）→ 数据其实还在，但没有任何入口能碰到，
  表现为「转换把参考号弄丢了」。
- **保守分支**：
  - 原来就有多条变体时无法判断该交给谁 → 保持原样并记日志（不猜）；
  - 变体上已有同码的行（`UNIQUE(product_id, reference_code)`）→ 产品级那条留在原地，
    不删用户数据、也不撞约束；
  - 未安装 `product_reference` 时按字段判断跳过（不硬依赖）。

### 影响

- 单变体 → 多变体的转换不再让产品级参考号失联：被保留变体的参考号 = 原有产品级行 + 它自己的变体级行
- 新变体仍不继承任何参考号（沿用 `product_reference` 的 L1「多变体不共用」）
- 无数据结构变化、无迁移

### 文档

- 模块 `README.md`：「属性归属审计」新增参考号行、「已知边界」补 N>1 时不交接、验证清单加一条
- 模块 `AGENTS.md`：L2 P5「同步规则」补交接规则；缺口清单补 N>1 这条

### 验证记录

| 项 | 结果 |
|----|------|
| 开发库实测（单变体、产品级 `CUST-SHARED` + 变体级 `VAR-OWN` → 转换） | 原变体 = `['CUST-SHARED', 'VAR-OWN']`；新变体为空；产品级为空；源产品索引 `False` ✓ |
| 自动化测试 | `task test -- product_variant,product_reference,sale_management --test-tags=/product_variant_conversion` → **41 项 0 failed**（含新增 2 项：正常交接、同码时保守保留）✓ |

---

## [19.0.4.1.0] - 2026-09-22（产品尺寸随谱系继承；与 product_dimension 打通）

### 变更

- **按谱系继承清单新增产品尺寸**：装了 [`product_dimension`](../product_dimension/README.md)（前身 `product_packing`，
  `19.0.2.0.0` 改名重写）时，`_get_variant_conversion_inherited_fields()` 会把 `dimension_unit` /
  `dimension_length` / `dimension_width` / `dimension_height` 一并算进继承清单 —— 尺寸是体积的来源，
  只继承体积会让新变体出现「有体积、没尺寸」的错位。按字段是否存在判断，**不硬依赖**那个模块（未安装时行为完全不变）。
- **只在来源尺寸齐全时复制尺寸**：长宽高有 0 时不复制这几个尺寸字段，否则会触发 `product_dimension`
  「尺寸不齐 → Volume 归 0」的规则，把刚继承来的体积冲掉（`_get_variant_conversion_inheritance_values()`）。
- 新增集成测试 `test_new_variants_inherit_variant_dimensions_when_installed()`（未装该模块时自动跳过）。

### 影响

- 行为变化仅在装了 `product_dimension` 时发生（新变体多继承四个尺寸字段）；不装则完全不变
- 无数据结构变化、无迁移；测试 38 → 39 项

### 文档

- 模块 `README.md`：「属性归属审计」表的产品尺寸行改为**变体级**、「新变体继承策略」表新增尺寸行、测试数同步
- 模块 `AGENTS.md` → L2 P5「同步规则」把原 `product_packing` 的跨模块注意改写为「与 `product_dimension` 协同」（`T-021` 已解决）
- 仓库 `TODO.md`：`T-021` 交付归档

---

## [19.0.4.0.0] - 2026-09-22（T-017 / T-018 / T-019 / T-020 一次交付）

### 变更

- **T-017 属性主数据路径的拦截**（新增 `models/product_attribute_guards.py`，三个模型四道闸）：
  - `product.template.attribute.value.unlink()`：仍有在用变体携带该取值时拒绝（原生会把它们连坐删 / 归档）；
  - `product.attribute.value.unlink()`：正被产品使用的取值不允许删（会破坏变体组合）；
  - `product.template.attribute.line.unlink()` / `.write()`：直接删属性行、写 `value_ids` 移走在用变体携带的取值时拒绝；
  - `create_product_product=False` 的沙盒写入放行（与 L1 约束 10 同源）；报错都给出「先处理变体」的出路。
- **T-018 健壮性**：
  - 组合数**前置上限**：`_check_variant_conversion_combination_cap()` 用「各属性有效取值数乘积」在
    `itertools.product` 枚举**之前**对照 `product.dynamic_variant_limit` 拒绝（分析与转换两条路都拦）；
  - `write()` 在分析**之前**对模板行 `FOR UPDATE`（并发下分析结论不再可能过期）；
  - 取值被归档导致的「会丢变体」报错单独措辞，指向「先恢复取值」而不是「先删变体」。
- **T-019 在手数量与测试**：
  - 预览的 `on_hand` 改为「未装 stock / 无权限时为 null」，弹窗据此在每条既有变体选项后附「在手 N」；
  - 归属载荷构造与未分配计数抽成纯函数（`buildOwnershipPayload()` / `countUnassigned()`，供单测复用）；
  - 补测未覆盖分支：多记录写入、归档变体、dynamic 属性（combo 因构造组合产品需要先配 choice 而未测）。
- **T-020 扩展点与可维护性**：
  - 新增 `_post_variant_conversion_hook(originals, new_variants, anchors)`（保存点内的扩展点，其它模块在此给新变体补数据）；
  - 转换完成后在产品 chatter 留一条转换记录（`_log_variant_conversion()`）；
  - 价格归属逻辑拆到 `models/product_template_prices.py`；
  - **批量转换入口不做**：多产品批量无法逐条确认归属，与「绝不静默改归属」冲突（已写入 AGENTS）。

### 影响

- **行为变化**：属性主数据里删除被变体使用的取值 / 属性行会被拒绝（此前是静默删 / 归档变体）——
  这是本模块承诺的补全；报错里给出处置办法
- 新增 2 个模型文件（守卫 / 价格拆分）；无数据结构变化、无迁移
- i18n +12 条；测试 28 → 38 项

### 文档

- 模块 `README.md`：功能概述 / 已知边界（归档取值不拦、combo 未测）/ 验证清单同步
- 模块 `AGENTS.md`：新增 L1 约束 17（属性主数据拦截）；文件职责与缺口清单同步；「常见扩展场景」注明批量转换不做的原因
- 仓库 `TODO.md`：T-017 / T-018 / T-019 / T-020 交付归档

---

## [19.0.3.5.0] - 2026-09-22（产品详情页移除「Variant Lineage」页签）

### 变更

- **产品表单不再显示「Variant Lineage」页**（用户反馈：产品详情页多出一个多数时候用不上的页签）。
  谱系明细与归属信息没有丢，都还在：
  - **Conversions** 智能按钮 → 转换台账**详情页**（每条结果变体一行：来源变体 → 结果变体、
    `is_kept`、转换前后的组合文本、新增取值，以及上一版加的参考号 / 条码 / 成本三列）；
  - **变体表单 / 变体列表 / 变体搜索**上的「来源变体 / 所属转换」（`variant_origin_id` / `variant_conversion_id`）不变；
  - 产品搜索「With Converted Variants」筛选不变。

### 影响

- 只删视图页签，模型 / 数据 / 其它视图不变；`-u` 升级 + 强刷浏览器即可
- 模块 `README.md` 的「变体来源与归属怎么追溯」「视图」「操作」「验证清单」同步改为指向台账详情页

### 文档

- 模块 `AGENTS.md` → 文件职责注明「刻意不加谱系页」
- 仓库 `TODO.md`：登记并归档 `T-024`（当日提出、当日完成）

---

## [19.0.3.4.0] - 2026-09-22（价格数据按变体分离：改一个变体的价格不再牵动别的变体）

### 变更

- **默认把价格数据按变体分离**（新增系统参数 `product_variant.separate_variant_prices`，默认开启）：
  - 本产品**模板级**的供应商价格（`supplierinfo.product_id` 为空）与价格表规则（`applied_on = '1_product'`）
    **按变体各复制一份（数值不变）后删除原记录** → 从此每条变体一份、各自可改；
  - **新变体**从谱系来源（`Derived From`）继承一份；来源没有就留空；
  - `3_global`（所有产品）与 `2_product_category`（按分类）的价格表规则**绝不触碰**；
  - 弹窗「把这些变体的供应商价格应用到全部变体」勾选框（默认不勾选）保留原语义：勾上则退回模板级共享；
    价格表规则始终按变体分离（与勾选框无关）。
- **两道安全线**（避免拆分过程中静默改价）：
  1. 变体在同一「价格表 + 数量门槛」上已有自己的规则时，模板级规则**不再拆过去**（否则会多出一条同档规则、
     把原来生效的那条挤掉）；
  2. 新增 `_check_variant_price_separation()` 后置断言：分离前后「供应商价格只多不少、**原有变体的实际售价一分未变**、
     新变体售价与其来源一致」（用 `pricelist._get_product_price()` 逐价格表 / 逐门槛比对），不符即整单回滚。
- 转换台账新增 `separate_variant_prices` 字段（列表可选列 + 详情页）。
- `_share_vendor_prices_with_variants()` 保持「只改按变体记录」的守卫，并返回被改写的记录集。

### 影响

- **行为变化（重要）**：转换后模板级的价格记录会被拆分并删除 —— 值完整保留在各变体上（有断言保证售价不变），
  但**记录条数会变多**（每条变体一份）。不想要这个行为就把系统参数 `separate_variant_prices` 设为 `0`。
- 新增 1 个存储布尔字段（`product.variant.conversion.separate_variant_prices`）→ 有列新增，`-u` 自动完成，无迁移脚本
- 测试 25 → 28 项

### 文档

- 模块 `README.md`：新增「价格数据按变体分离（默认）」小节（含两条安全线与关闭方式）；「价格与库存的同步规则」
  「新变体继承策略」「已有业务数据怎么处理」「模型字段」「已知边界」「后续迭代」「验证清单」同步
- 模块 `AGENTS.md`：新增 L1 约束 16（价格按变体分离）；L2 P5 同步规则更新、缺口 3 标记为已解决
- 仓库 `TODO.md`：`T-022` 落地 → 归档

---

## [19.0.3.3.0] - 2026-09-22（原产品资料保留核查 + 供应商价格勾选框默认不勾选）

### 变更

- **供应商价格勾选框默认值改为「不勾选」**：`VariantConversionDialog` 的 `shareVendorPrices` 初值由 `true` 改为 `false`。
  勾选后仍是原行为：`product_id` 指向既有变体的价格记录改为模板级「适用于全部变体」，**所有变体取到同一批数值**；
  不勾选（默认）则价格只对原来那条变体生效。
- **`_share_vendor_prices_with_variants()` 显式化守卫并返回被改写的记录集**：只改 `product_id` 指向既有变体的记录；
  本来就是模板级（对所有变体生效）的记录不动 —— 「已属于全部变体就不需要转移」，便于调用方 / 测试核对。
- **「把原产品资料保留给指定变体」= 保留原记录本身，确认无需转移**（本轮用测试钉住，**没有**新增搬数据的代码）：
  内部参考号 / 条码 / 按变体的供应商价格（`supplierinfo.product_id`）/ 按变体的价格表规则
  （`pricelist.item.applied_on = 0_product_variant`）/ 补货规则（`orderpoint.product_id`）本来就在被指定的那条
  变体（原 `product.product` 记录，id 不变）上；模板级记录保持模板级。

### 影响

- 行为变化：**弹窗里供应商价格默认不再共享** —— 要共享得主动勾选（避免无意中抹平同一供应商对不同变体的价差）
- 无数据结构变化、无迁移脚本；JS 改动需 `-u` + 强刷浏览器
- 测试 21 → 25 项（新增：原产品资料保留、补货规则保留、共享只改按变体记录、共享后所有变体同价）

### 文档

- 模块 `README.md`：「已有业务数据怎么处理」新增「为什么不需要转移」说明段，并逐类更新数据状态；
  功能概述 / 操作步骤 / 价格与库存同步规则 / 新变体继承策略 / 已知边界 / 验证清单同步勾选框默认值
- 模块 `AGENTS.md` → L2 P5「同步规则」补「原产品资料不需要转移」与共享守卫两条；文件职责与缺口清单同步
- 仓库 `TODO.md`：登记并归档 `T-023`（本条目当日提出、当日完成）

---

## [19.0.3.2.0] - 2026-09-22（T-016 完成：新变体按谱系继承，可开关）

### 变更

- **新变体按谱系继承变体级数据**：`_apply_variant_data_inheritance()` 把新变体的
  **成本 `standard_price` / 体积 `volume` / 重量 `weight`** 从它的谱系来源（`Derived From`，即 `variant_origin_id`）复制过来，
  在转换第 ⑦ 步（写完谱系之后）执行；来源为空时跳过该变体，保持空值、不做猜测。
- **可配置**：系统参数 `product_variant.inherit_variant_data`，默认开启；
  设为 `0` / `false` / `no` / `off` 则新变体保持 Odoo 默认的空 / 0。
- **刻意不继承**（各有硬约束，详见 README →「新变体继承策略」）：
  - 内部参考号 `default_code`：本仓库 `product_reference` 的 L1 约束「多变体产品不共用参考号」；
  - 条码 `barcode`：`product.product._check_barcode_uniqueness()` 有唯一性约束，复制必然报错；
  - 价格表规则 / 补货规则：规则各自带适用条件，盲目复制会产生重复规则（`T-022` / 另议）；
  - 供应商价格：仍由弹窗勾选框决定（拟升级为按谱系逐变体继承，`T-022`）。
- 转换台账新增 `inherit_variant_data` 字段（列表可选列 + 详情页），记录本次是否启用了继承。

### 影响

- **行为变化**：默认开启继承 → 转换后新变体的成本 / 体积 / 重量不再为空 / 0，而是等于来源变体的值；
  需要旧行为就把系统参数设为 `0`
- 新增 1 个存储布尔字段（`product.variant.conversion.inherit_variant_data`）→ 有列新增，`-u` 自动完成，无迁移脚本
- 测试 19 → 21 项

### 文档

- 模块 `README.md` 新增「新变体继承策略」表（继承什么 / 不继承什么 / 为什么 + 关闭方式）；
  「属性归属审计」「已知边界」「后续迭代」「模型字段」「验证清单」同步更新
- 模块 `AGENTS.md` 新增 L1 约束 15（继承范围与来源）；L2 P5 同步规则与缺口清单同步（缺口 2 标记为已解决）
- 仓库 `TODO.md`：`T-016` 四项验收标准全部完成 → 归档；新增 `T-022`（供应商价格按谱系逐变体继承）

---

## [19.0.3.1.0] - 2026-09-22（T-016 核实：属性归属审计 + 变体级属性关联展示）

### 变更

- **核实结论：转换不需要任何数据迁移**（源码 + 自动化测试双重证据）
  - **真身在变体上**：`barcode` / `standard_price` / `volume` / `weight` / `default_code` 都是 `product.product` **自己声明的存储字段**，
    在变体上**覆盖**了 `_inherits` 委托来的模板字段；
  - 模板侧那几个退化为**单变体桥接**（`_compute_template_field_from_variant_field()` / `_set_product_variant_field()`）：
    单变体时读 / 写都落到那条变体；多变体时读出空 / 0、写入**不落任何变体**（Odoo 原生语义）；
  - 本模块保留原 `product.product` 记录（id 不变）→ 默认变体（= 原记录）天然带着全部原值，**一个字节都不用搬**；
  - 模板级字段（销售价、税、计量单位、`product_packing` 的纸箱与产品尺寸）全变体共享，转换根本不碰；
  - 唯一变化是**查看位置**：多变体后产品表单上那几个字段显示空 / 0，真值在对应变体上。
- **前端：把结果变体上的变体级属性关联展示出来**（非存储 `related`，不新增数据库列、不需要迁移）
  - `product.variant.lineage` 新增 `result_default_code` / `result_barcode` / `result_standard_price`；
  - 产品表单 **Variant Lineage** 页与转换台账详情页的谱系表新增这三列，并在产品表单补一句字段归属说明。
- 自动化测试 17 → 19 项：新增 `test_field_storage_layers_match_the_audit()`（字段层级审计，Odoo 改存储层时先失败）
  与 `test_variant_level_values_stay_on_the_kept_variant()`（原值保留 / 新变体为空 / 多变体下模板桥接字段语义 / 谱系关联展示）。

### 影响

- **无数据结构变化**（新字段全部是非存储 `related`）、无迁移脚本；`-u` 升级即可
- 界面新增三列与一句提示文案（中英双语已补）；既有的转换与归属逻辑未改动
- 若你在产品表单上看不到条码 / 成本 / 体积 / 重量：那是 Odoo 多变体产品的原生表现，值在变体表单 / 变体列表里（见 README →「属性归属审计」）

### 文档

- 模块 `README.md` 新增「属性归属审计」表（逐字段：真身 / 单变体时 / 转换后 / 默认变体上的值 / 是否需要迁移）与 `_inherits` + 单变体桥接机制说明
- 模块 `AGENTS.md` → L2 P5「同步规则」补字段归属审计结论、桥接规则，以及 `product_packing` 尺寸 → Volume 在多变体下失效的跨模块注意
- 仓库 `TODO.md`：`T-016` 移入「进行中」（补验收标准）；新增 `T-021`（`product_packing` 的产品尺寸同步在多变体产品上不再落到变体）

---

## [19.0.3.0.2] - 2026-09-21（文档：业务场景覆盖、数据流与一致性边界评估）

### 变更

- **无代码行为变更**，只补文档（`19.0.3.0.1` 的前端修复已实测通过）
- 模块 `README.md` 新增四节：
  - **场景覆盖矩阵**：12 类属性改动的结局（弹窗 / 拒绝 / 放行）与测试覆盖一览
  - **数据流**：从点保存到落库的完整时序（预览 RPC 的试写 + 回滚、三结局分支、转换五步、失败整单回滚）
  - **价格与库存的同步规则**：逐字段说明归属（模板级 / ptav 级 / 变体级），并写明两处代价——「新变体成本为 0」「共享供应商价格会抹平同一供应商对不同变体的价差」
  - **已知边界与后续迭代**：8 条边界 + 5 条迭代方向（带 `TODO.md` 条目号）
- 模块 `AGENTS.md` 新增 L2 **P5：业务场景、数据流与一致性边界**：覆盖矩阵、判据、同步规则、9 条已识别缺口、扩展点表、升级回归的内部 API 清单

### 影响

- 无代码、无视图、无 i18n 变化；照常 `-u` 更新版本号即可，不需要数据迁移

### 文档

- 本轮核实的三条新源码事实已写进文档：
  1. 成本 `standard_price` 是**变体级**字段（模板侧只是单变体时的 compute/inverse 通道）→ 新变体成本为 0；
  2. **删 / 归档属性取值会直接删 / 归档既有变体**（`product.template.attribute.value.unlink()` → `_unlink_or_archive()`），
     直接写 `product.template.attribute.line` 也会自己调 `_create_variant_ids()` —— 两条路都**绕过**本模块的保存拦截；
  3. 采购取价按 `price_discounted → sequence → id`（`product.product._select_seller`）→ 共享供应商价格后会静默只取一条。
- 迭代需求登记进仓库 `TODO.md` 待办池：`T-016` 变体级数据按谱系继承、`T-017` 属性主数据路径拦截、
  `T-018` 组合枚举前置上限与并发锁顺序、`T-019` 弹窗展示在手数量与测试补齐、`T-020` 扩展点与可维护性。

---

## [19.0.3.0.1] - 2026-09-21（修复弹窗确认后的保存错误；本地开发库已验证，待目标环境验证）

### 变更

- **修复：弹窗里点确认后保存报 `Uncaught Promise > this.model.save is not a function`**
  - 根因：`RelationalModel` 上**没有** `save` 方法——保存入口在 `Record` 上（`this.model.root.save()`），
    控制器层另有 `FormController.save()`（它负责挂 `onSaveError`、尊重 `props.saveRecord`、触发 `props.onSave`）
  - 修法：改调 `await this.save()`，并在代码注释里写明正确入口
- **加固：技术字段 `variant_conversion_mapping` 在视图里加 `force_save="1"`**
  - 原因：`Record._getChanges()` 会把「在 activeFields 里、但只读且未标 `forceSave`」的字段从 `changes` 里剔除。
    这个字段承载弹窗确认后的归属映射，一旦有人给它加 `readonly="1"`，映射会静默不随保存提交，
    表现为「确认后保存又被拦一次、弹窗反复出现」，且没有任何报错线索
- 架构与判定逻辑未变（仍是保存拦截 + 归属确认弹窗 + 只增不删）

### 影响

- 只改前端保存调用与一个视图属性，无数据结构变化、无迁移
- 升级后必须强刷浏览器（Ctrl+F5）：前端资源有缓存，不刷新仍会跑到旧代码

### 文档

- 模块 `AGENTS.md` → L2 P4 补两条陷阱：保存入口只能是 `FormController.save()` / `Record.save()`；
  承载前端回传数据的技术字段必须 `force_save="1"`

---

## [19.0.3.0.0] - 2026-09-21（本地开发库已验证，待目标环境验证）

### 验收记录

- 验收日期：2026-09-21
- 验收环境：本地开发库（`dev`）；自动化测试分别在「只装 `product`」与「加装 `stock` + `sale_management`」两种库上跑
- 验收结果：两轮各 17 项测试全部通过（0 failed / 0 error）
  - [x] `-i` / `-u` 无报错（含删除旧的向导模型与视图、加载 3 个前端资源）
  - [x] 加属性但未确认归属 → 写入被拒绝，产品与变体均不变
  - [x] 预览接口给出「是否需要确认 / 改动后的组合 / 既有变体的默认归属」，且自己不改库
  - [x] 确认归属后：2 变体 + 新属性 → 4 变体，两条原记录各自保留自己的组合，另两个组合是新记录
  - [x] 归属可逐条交叉指定；归属漏项 / 重复指向都被拒绝且不改库
  - [x] 给已有属性追加取值同样需要确认；只加单取值属性 / 「不生成变体」属性 / 重提同样配置都不需要确认
  - [x] 删取值 / 删属性行被拒绝（预览给出 blocked 提示）
  - [x] 转换台账、变体谱系、变体来源字段内容正确
  - [x] 两个变体各有库存：预览能看到各自在手数量，转换后库存仍分别挂在原来那条记录上
  - [x] 销售订单行仍指向原来那条变体
  - [ ] 目标环境：保存时弹窗、取消不保存、按钮消失、中英文界面（待验证）

### 变更

- **入口改为「保存时自动检测 + 归属确认弹窗」**，移除产品表单上的「Add Attributes To Variants」按钮与整个向导：
  - 用户照常在原生「属性与变体」页改属性、点保存；
  - 前端 patch `FormController.onWillSaveRecord(record, changes)`（官方保存前钩子，返回 false 即阻止保存），
    保存前调 `product.template.get_variant_conversion_preview()` 问这次改动的影响；
  - 需要确认时弹出新的归属弹窗：按「改动后的组合」逐行选择**由哪条既有变体继续承载**
    （默认值 = 什么都不指定时的结果），每条既有变体必须恰好被指定一次；
  - **用户确认之前保存不继续**（取消 / 关掉弹窗 = 本次不保存，表单保持未保存状态）；
  - 确认后把归属映射放进本次保存的 `changes`（技术字段 `variant_conversion_mapping`）重走一次保存，
    属性变更与归属在同一次写库、同一个事务里落地。
- **`write()` 保存拦截的三种结局**：不影响变体 → 原生保存；会新增变体 → 没有归属映射就拦住（由弹窗接管）/
  有映射就先安全转换再落库；会丢变体（删取值 / 删属性 / 组合数变少）→ 直接拒绝，绝不静默删除
- **新增试写分析 `_analyze_variant_conversion_write()`**：带 `create_product_product=False` 只写配置（属性行 + ptav）
  并在保存点里回滚，既有变体毫发无损。**刻意不用原生写法当判据**——原生写法在「加属性」时本来就会删掉既有变体
- 新增预览 RPC `get_variant_conversion_preview()`，返回 `blocked` / `required` / `variants`（含在手数量）/ `combinations`（含默认归属）
- 新增归属载荷与校验 `_parse_variant_conversion_mapping()`：格式 `{"mapping": [{values, origin_variant_id}], "share_vendor_prices": bool}`，
  校验「每条既有变体恰好一次、取值必须存在、不能两条既有变体占同一组合」；技术字段 `variant_conversion_mapping` 写完即清空
- **新增前端资源**：`static/src/js/variant_conversion_form_patch.js`（保存拦截）、
  `static/src/js/variant_conversion_dialog.js` + `static/src/xml/variant_conversion_dialog.xml`（归属确认弹窗，
  含「把这些变体的供应商价格应用到全部变体」勾选框）
- **删除向导模型**：`product.variant.conversion.wizard` / `.line` / `.variant.line` 与向导视图、对应安全规则
- 供应商价格共享从「向导选项」改成「弹窗勾选框」（默认勾选），语义不变
- 多记录写入保护：一次改多个产品的属性无法逐条记录归属 → 拒绝并提示逐个产品保存
- 新增拦截：产品上有「按需生成变体」的属性时明确提示（那种情况下变体由 Odoo 自己创建，没有归属可确认）
- `_convert_to_multi_variant()` 新增 `previous_attribute_lines` / `added_attributes` 两个可选参数：
  属性行已被 `write()` 写成目标配置后调用时，谱系与台账要用「改动前快照」才不会把来源判空、把新增属性记空

### 影响

- **不需要迁移脚本**：删除的是瞬态向导模型（无历史数据）；`product.template` 只新增一个技术字段 `variant_conversion_mapping`（Text，通常为空）
- **升级后必须强刷浏览器**（Ctrl+F5）：保存拦截与弹窗是前端资源，缓存里没有它们时保存会被服务端拒绝并给出提示
- 产品表单上原来的「Add Attributes To Variants」按钮消失，改为「改属性 → 保存 → 需要时确认归属」
- 已按旧版本转换过的产品不受影响：台账、谱系、变体来源字段与转换逻辑都没变
- 依赖仍只有 `product`；新增的 `stock` 调用（预览里的在手数量）已做存在性与权限降级

### 文档

- 同步更新 `__manifest__.py`（版本 `19.0.3.0.0`、`summary` / `description`、assets 登记）、
  `README.md`（按新流程重写：功能概述 / 核心设计 / 怎么用与归属怎么指定 / 会被拒绝的改动 / 没有弹窗时 / 模块资源 / 验证清单）、
  `AGENTS.md`（L1 扩到 14 条，L2 新增 P4「保存拦截与弹窗」并重写 P1 的判定与来源说明）
- `i18n/zh_CN.po` 用官方导出骨架重建（101 条：删除向导词条，新增弹窗模板与 JS `_t()` 词条、保存拦截的报错文案）
- 根 `README.md` 模块一览表 / 路线图、根 `AGENTS.md` 模块速查表、根 `TODO.md`（T-015）同步

---

## [19.0.2.0.0] - 2026-09-21（本地开发库已验证，待目标环境验证）

### 验收记录

- 验收日期：2026-09-21
- 验收环境：本地开发库（`dev`，Odoo 19 官方镜像；另一轮测试库额外装了 `stock` / `sale_management`）
- 验收结果：两轮自动化测试均 14 项全部通过（0 failed / 0 error）；`i18n/zh_CN.po` 148 条 `msgid` 直接来自官方术语导出，与源码逐字符一致
  - [x] `-i` / `-u` 安装与升级无报错（含 5 个模型、安全规则、6 个视图文件）
  - [x] 只有 `product` 与加上 `stock` / `sale_management` 两种环境下测试都全绿
  - [x] 2 个变体 + 新属性 → 4 个变体：两条原记录各自保留自己的组合，另两条为新记录
  - [x] 归属可逐条交叉指定（把 Blue 那条记录改指 Blue + L）
  - [x] 两条原变体被指到同一组合时拒绝，且不改库
  - [x] 只加单取值属性：变体数不变，每条既有变体都带上该取值
  - [x] 删除已有取值被拒绝；带归档变体的产品被拒绝
  - [x] 转换台账、变体谱系、`product.product` 上的来源字段内容正确
  - [x] 两个变体各有库存时，转换后库存仍分别挂在原来那条记录上
  - [x] 销售订单行仍指向原来那条变体
  - [x] 供应商价格共享选项两种情况均符合预期
  - [ ] 目标环境界面显隐（按钮 / 智能按钮 / 谱系页 / 变体列表可选列 / 搜索筛选）待验证
  - [ ] 目标环境界面中英文各验一遍待验证

### 执行流程

1. 升级：`odoo -d <db> -u product_variant --stop-after-init`
2. 打开有变体的产品 → 「属性与变体」页 → **Add Attributes To Variants**
3. 加属性 / 加取值 → 在 **Variant Ownership** 表里核对或修改每条既有变体转换后占有的取值 → **Convert**
4. 核对：产品表单 `Conversions` 智能按钮看台账，`Variant Lineage` 页看归属；变体列表按 `Derived From` 排序或搜索
5. 本地可复跑：`task test -- product_variant,stock,sale_management --test-tags=/product_variant_conversion`

### 变更

- **模块技术名由 `product_variant_convert` 改为 `product_variant`**（交付前定名调整，目录 / xmlid 前缀 / 五个模型名 / 关系表名 / po 引用 / 文档全部同步）：
  - 原名词性与家族不一致（仓库模块都是名词短语：`product_reference` / `product_packing` / `product_card_view`…），且 `convert` 没说「转成什么」——Odoo 19 里还有 `product.combo`，容易被读成「把变体转成组合产品」（本模块恰恰明确拒绝 combo 产品）
  - 新名与显示名（`Product Variant Conversion`）、与模块内部命名天然对齐（模型 `product.variant.conversion`、字段 `variant_conversion_id`、界面 `Variant Conversion` / `Variant Conversions`、动作 `product_variant_conversion_action`）
  - 向导模型一并统一为 `product.variant.conversion.wizard` / `.line` / `.variant.line`（原 `product.variant.convert.*`）
  - 改名时机：目标环境尚未交付过本模块（只有本地 dev 库），先 `odoo module uninstall` 干净卸载旧模块再安装新名，**无需生产库卸载重装**；仓库文档也写明交付后改名的代价极高
- **支持多变体产品的转换**（原 `19.0.1.0.0` 只支持「仅含单一变体」的产品）：现在只要产品有变体就能追加属性 / 取值，例如「2 个颜色」再加「2 个尺码」变成 4 个变体
- **新增「变体归属表」**（`product.variant.conversion.variant.line`）：每条既有变体一行，显式指定它转换后占有的取值（每属性一个），表格自动预填（已有属性保持原取值、新加属性取本次第一个取值）并可逐行修改；同一属性写多行时按并集合并
  - 归属表由 `_sync_variant_lines()` 统一补齐，`line_ids` 的 onchange 与 `action_convert()` 都会调用，保证界面与执行用的是同一份配置
  - 归属表每行显示该变体的在手数量，库存归属一目了然
- **移除** `product.variant.conversion.line.default_value_id`（原「逐属性指定原变体取值」）：归属改由归属表逐条变体表达，避免「同一件事两个地方表达」
- 核心算法从「单个默认组合」推广为「逐条变体锚定」：`variant_mapping` 是唯一入口，未提供时由 `_get_variant_conversion_default_mapping()` 补齐；预检新增「归属组合互不重复」与「预期变体数不得少于既有变体数」；后置断言改为逐条变体检查
- **新增归属追溯**：
  - `product.variant.conversion` 转换台账：产品、转换前后的变体数、新增变体数、本次真正新增的属性、是否共享供应商价格、时间与操作人
  - `product.variant.lineage` 变体谱系：来源变体 → 结果变体、`is_kept`（结果是否就是原记录）、转换前后组合快照、本次为该变体新增的取值；新变体的来源按「转换前就存在的属性轴」判定，判定不唯一时留空
  - `product.product` 新增可搜索字段 `variant_conversion_id` / `variant_origin_id`
- **新增界面**：产品表单 `Conversions` 智能按钮与 `Variant Lineage` 页、产品搜索「含转换产生的变体」筛选、变体表单来源分组、变体列表两个可选列、变体搜索按来源变体 / 所属转换检索与筛选、转换台账列表 / 详情视图
- **新增拒绝规则**：产品存在归档变体时直接拒绝转换（避免 `_create_variant_ids` 悄悄把老变体重新激活）
- 审计面板改为按**全部既有变体**聚合；`product.variant.conversion` 的 `_description` 取 `Variant Conversion Log`（与模块名区分，避免 `msgid` 撞车）
- 测试从 12 项扩到 14 项并改成覆盖多变体场景（归属映射 / 交叉指定 / 归属互斥 / 谱系 / 库存与订单行不变），且在只有 `product` 的环境下也能跑（`is_storable` 由 `stock` 提供，先判断字段是否存在）
- i18n：`i18n/zh_CN.po` 改为用官方 `odoo i18n export` 导出的术语骨架重建（148 条，含应用列表元数据 3 条），杜绝手写 `msgid` 与源码不一致

### 影响

- **不涉及任何数据库结构变更迁移**：新增的 2 个模型由 Odoo 正常建表；向导字段与向导模型名的变化都发生在瞬态模型上（无历史数据），**无需迁移脚本**
- **改名影响**：本模块从未在目标环境交付过，改名只需在开发库 `odoo module uninstall product_variant_convert` 后安装 `product_variant`（本地已实测：旧模块的表与数据随卸载一并清理，无残留表）。若某个库已经装过旧名模块，必须按「先卸载旧名、再安装新名」处理——Odoo 视改名为不同模块
- 不改动任何官方模型字段与视图节点，只新增按钮 / 智能按钮 / 页签 / 可选列 / 搜索项、2 个新模型与 2 个变体字段
- 已按 `19.0.1.0.0` / 旧名版本转换过的产品不受影响：转换结果与新版本读的是同一批数据（变体的实际取值组合、台账与谱系行），不依赖向导字段名
- 依赖仍只有 `product`；新增的 UI 元素在 `stock` / `sale` / `purchase` / `account` 未安装时同样可用

### 文档

- 同步更新 `__manifest__.py`（版本、`summary` / `description`）、`README.md`（新增「如何指定每条既有变体的归属」「变体来源与归属怎么追溯」两节，字段表与验证清单扩写）、`AGENTS.md`（L1 扩到 11 条，L2 新增 P1 归属算法、P2 i18n 与 po 维护、P3 Odoo 19 字段与命名坑）
- 根 `README.md` 模块一览表 / 路线图 / 应用列表元数据总览、根 `AGENTS.md` 模块速查表、根 `TODO.md`（T-015 归档内容更新）

---

## [19.0.1.0.0] - 2026-09-21（开发期中间版本，已被 19.0.2.0.0 取代；当时技术名为 `product_variant_convert`）

### 验收记录

- 验收日期：2026-09-21
- 验收环境：本地开发库（`dev`，Odoo 19 官方镜像；自动化测试库额外装了 `stock` / `sale_management`）
- 验收结果：本地 12 项自动化测试全部通过（0 failed / 0 error），i18n 85 条 `msgid` 与 Odoo 术语抽取结果逐条对齐

  - [x] `-i product_variant` 安装无报错
  - [x] `-u product_variant` 升级无报错，安全规则与两个视图加载成功
  - [x] 单变体产品转换后原变体记录 id 不变，并成为指定的默认变体
  - [x] 两个属性时生成全部组合，原变体占用户指定的那一组
  - [x] 已有单取值属性行可追加取值，只新增变体
  - [x] 删除已有取值被拒绝，且不改库
  - [x] 库存量记录与销售订单行仍指向原变体
  - [x] 供应商价格共享选项两种情况均符合预期
  - [x] 已是多变体的产品拒绝进入向导
  - [ ] 目标环境中文「应用」列表显示中文元数据（待验证）
  - [ ] 目标环境界面中英文各验一遍（待验证）

### 执行流程

1. 安装：`odoo -d <db> -i product_variant --stop-after-init`
2. 打开只有 1 个变体的产品 → 「属性与变体」页 → **Convert to Multi-Variant**
3. 填属性与取值，逐属性指定「Original Variant Value」（原变体取值）→ **Convert**
4. 核对：变体列表中新旧变体齐备；默认变体上仍能看到原有的在手数量与订单行
5. 本地可复跑：`task test -- product_variant,stock,sale_management --test-tags=/product_variant_conversion`

### 变更

- 初始版本，新建模块 `product_variant`（产品变体转换）
- 在 `product.template` 上新增转换入口与核心实现 `_convert_to_multi_variant()`：
  - 带 `create_product_product=False` 上下文写 `attribute_line_ids`，只生成 `product.template.attribute.value`，不触发 `_create_variant_ids()`（不新建、不删除任何变体）
  - 把用户指定的「默认组合」锚定到原变体的 `product_template_attribute_value_ids` 上，再调用 `_create_variant_ids()`：原变体因组合匹配而被复用，缺失组合才新建
  - 全过程包在 `savepoint` 内，配前置校验（只允许追加取值、默认取值必须落在选值内、属性不能是按需生成等）与后置断言（原变体仍在且等于默认组合、变体数等于用 Odoo 规则算出的预期数），任何不符即整单回滚
  - 同一产品的转换用 `SELECT ... FOR UPDATE` 串行化，避免并发改同一产品的属性行
  - 可选把仅挂在原变体上的 `product.supplierinfo` 改为适用于全部变体（`product_id = False`）
- 新建瞬态模型 `product.variant.conversion.wizard` 与 `product.variant.conversion.line`：
  - 逐属性指定「原变体取值」；同属性写多行时自动合并取值（默认取值必须一致）
  - 打开时自动预填产品已有的属性行（取值与原变体取值取当前配置）
  - 转换前审计面板：在手数量、库存量记录、库存移动明细、未完成库存移动、批次、销售 / 采购订单行（总数与未完结数）、发票行、供应商价格、补货规则、价格表规则
  - 审计通过 `model_name in self.env` + `check_access_rights` 降级，模块不依赖 `stock` / `sale` / `purchase` / `account`
- 产品表单「属性与变体」页新增按钮与说明（仅单变体产品显示）
- 新增 `tests/test_product_variant_conversion.py`：12 项测试覆盖保留原变体、多属性组合、追加取值、拒绝删取值、拒绝无新变体、供应商价格共享，以及（装了 `stock` / `sale` 时）库存量记录与销售订单行仍指向原变体
- i18n：源语言英文 + `i18n/zh_CN.po`（85 条 `msgid`，含应用列表元数据 3 条与分类 `Product`）

### 影响

- 不涉及任何数据库结构变更（未新增字段、未改字段类型），**无需迁移脚本**
- 不改动任何官方模型字段与视图节点，只新增按钮、两个瞬态模型与安全规则；卸载模块后转换能力消失，但已转换的产品不受影响
- 转换会写 `product.template.attribute.line` / `product.template.attribute.value` / `product.product.product_template_attribute_value_ids`，并可选择性质地写 `product.supplierinfo.product_id`（仅在勾选时）
- 依赖最小：只依赖 `product`；审计面板对未安装模型自动降级为 0

### 文档

- 同步更新 `__manifest__.py`、`README.md`、`AGENTS.md`、`CHANGELOG.md`（本文件）
- 根 `TODO.md`（T-015 归档）、根 `README.md`（模块一览表 / 路线图 / 应用列表元数据总览）、根 `AGENTS.md`（第 9 节模块速查表）
- `.dev/init.yaml` 与 `DEV_WORKFLOW.md` 的开发库模块清单加入本模块，`DEV_ENV_SETUP.md`（现已归档到 `docs/archive/`）的验收描述同步模块数量
