# 变更日志

> 倒序排列，最新版本在最前。每版本固定三段式：变更 / 影响 / 文档。
> 修复 / 优化类版本在这三段之外补两节，便于追溯「为什么改、改成什么、改前什么样」：
> **优化目标**（置于「变更」之前）与**优化前后对比**（置于「变更」之后，三列「场景 / 优化前 / 优化后」），
> 「影响」一节同时承载预期效果。规范见 [`DOCS_TEMPLATE.md`](../DOCS_TEMPLATE.md) →「CHANGELOG 约定」。
> 版本号规则见根 `AGENTS.md` 第 3 节：架构/破坏性 +x，功能新增 +y，修复 / 文档 +z。

---

## [19.0.2.0.7] - 2026-09-22（修复：切换 filter / group by 后卡片空白、过宽、无间隙）

> 修订日期：2026-09-22 ｜ 类型：修复（+z）｜ 影响文件：`product_card_model.js` /
> `product_card_renderer.js` / `product_card.scss`（无 Python、无数据、无 i18n 改动）

### 优化目标

产品列表的 Card 视图在**搜索框中切换筛选（filter）或分组（group by）之后**，必须与首屏表现一致：

1. 卡片显示产品主图（多图时轮播仍可用）；
2. 卡片显示产品信息（title / reference / on hand / 变体按钮行）；
3. 卡片宽度适当（分组列里不被拉满整列）；
4. 卡片之间保留正常间隙（不粘连）。

四个现象来自**三类互相独立**的问题（取数范围 / 取数时机 / 布局作用域），因此分三条修复；
未分组与分组两种形态都要满足上述四点。

### 变更

1. **取数范围（分组视图）** —— `product_card_model.js`
   - 现状：`fillProductCardPayload` 只吃 `props.list.records`；分组时 `props.list` 是
     `DynamicGroupList`，记录在各 `group.list.records` 里、`list.records` 为空 →
     取数 id 列表为空 → 全局 Map 被清空 → 所有卡片空 payload（无图、无产品信息）。
   - 变更：新增 `collectCardRecords(list)` 统一收集 —— 未分组取 `list.records`、分组取
     `list.groups[].list.records`（多级分组继续下钻）；`collectCardRecordIds()` 在其上取
     `resId` 列表，`cardRecordIdsKey()` 生成批次 key。
2. **取数时机（筛选 / 分组 / 翻页 / reload）** —— `product_card_model.js` +
   `product_card_renderer.js`
   - 现状一：`payloadByResId.clear()` 之后才 `await rpc` —— 请求飞行期间若发生一次渲染，
     卡片读到的是**已清空**的 Map；而 Map 是非 reactive 的，响应回来**不会再触发渲染**，
     空白被固化。
   - 现状二：只依赖 `onWillUpdateProps` 补拉；但筛选 / 分组 / 翻页 / reload 常常只改 `list`
     内部数据，渲染器由 Reactive 直接重渲染、**不走 `updateProps`** → 钩子根本不触发；
     即便触发，Owl 在 await 后还有 `if (fiber !== this.fiber) return`，fiber 被取代时会
     放弃这次渲染。
   - 变更：① `fillProductCardPayload` 改为「请求前不清空、成功后整体替换」，加
     `requestSeq` 丢弃过期响应、加批次 key 避免同一批 id 重复请求、失败时清标记允许重试；
     ② 渲染器新增 `useEffect` 逐次比对本页 id（Owl 19 的 `useEffect` 即
     `onMounted` + `onPatched`，patch 路径全覆盖），数据到位后**显式 `this.render(true)`**
     —— 非 reactive 容器没有别的通知途径（effect 回调不返回 promise，避免被 Owl 当 cleanup 调用）。
3. **布局作用域（分组）与布局时机** —— `product_card.scss` + `product_card_renderer.js`
   - 现状：JS 瀑布流只在 `o_kanban_ungrouped` 下运行；分组时套用官方样式
     `.o_kanban_grouped .o_kanban_record { width: 100% }` + `.o_kanban_record { margin: 0 0 -1px }`
     → 卡片撑满列宽（过宽）、上下零间距（无间隙）。
   - 变更：新增分组样式 `.o_product_card_view.o_kanban_grouped .o_kanban_group
     .o_kanban_record.o_product_card { width: 100%; max-width: 22.5rem; margin: 0 auto 0.75rem }`；
     未分组卡片 `margin: 0`（间距完全由瀑布流 `GAP` 决定），并把 `position: absolute` 从
     SCSS 移到 JS inline（JS 未跑的首帧退回正常流布局作兜底）；布局触发点由
     `onWillUpdateProps` 里的 rAF 改为 `onPatched` + `onMounted`，新增容器 `ResizeObserver`，
     分组时 `_clearCardLayout()` 清掉残留 inline 定位，`innerWidth <= 0` 时跳过计算。

### 优化前后对比

| 维度 | 优化前 | 优化后 |
|------|--------|--------|
| 取数范围（分组） | 只取 `props.list.records` → 分组时为空 → Map 被清空 → 整页无图无信息 | `collectCardRecords()` 覆盖 `list.groups[].list.records`（多级分组递归）→ 有图有信息 |
| 取数时机（筛选 / 分组 / 翻页 / reload） | `clear()` 后再 `await rpc`，飞行期间的渲染读到空 Map 且不再触发渲染 → 空白固定；只靠 `onWillUpdateProps`，而这类刷新不触发它 → 无补拉机会 | 请求前不清空、成功后整体替换 + requestSeq 防乱序；`useEffect` 逐次比对本页 id，数据到位后显式 `render(true)` |
| 卡片宽度（分组） | 官方 `width: 100%` → 撑满列宽 | `width: 100%; max-width: 22.5rem` → 有宽度上限，列内居中 |
| 卡片间隙（分组） | 官方 `margin: 0 0 -1px` → 零间距 | `margin: 0 auto 0.75rem` → 间距 0.75rem |
| 未分组首帧 / 切筛选瞬间 | `position: absolute` 写在 SCSS，JS 未跑时所有卡片叠在一起 | `absolute` 只由 JS 写 inline，未跑时退回正常流布局（官方宽度与边距） |
| 未分组间距 | 官方 `margin` 与瀑布流 `GAP` 叠加，实际间距不可控 | 卡片 `margin: 0`，间距完全由瀑布流 `GAP` 决定 |
| 布局触发 | 仅 `onWillUpdateProps` 里的 rAF（props 更新 ≠ DOM 已更新） | `onPatched`（DOM patch 后）+ `onMounted` + 容器 `ResizeObserver`；分组时清残留 inline 定位 |

### 影响

（预期效果）

- 首屏与切换筛选 / 分组 / 翻页 / reload 后表现一致：卡片有图、有产品信息、宽度适当、间隙正常；
  分组视图同样有图有信息（修复前分组必空）
- 未分组仍为 JS 瀑布流（列高均衡、响应式列数），间距精确可控；分组视图卡片宽度 ≤ 22.5rem、
  间距 0.75rem，不再撑满列宽、不再零间距
- 无数据结构变化、无迁移；接口 `/product_card/payload` 不变（分组时一次性提交所有分组的记录 id）
- 不新增用户可见文案，`i18n/zh_CN.po` 无需改动
- 代价：`useEffect` 会在每次 patch 后比对一次本页 id（字符串 join，约百条量级），
  取到新数据时多一次深渲染 —— 换取「非 reactive 容器下必然刷新」的正确性

### 文档

- 本文件：本版本按「优化目标 / 变更 / 优化前后对比 / 影响 / 文档」记录（修复类版本格式，
  已写进根 [`DOCS_TEMPLATE.md`](../DOCS_TEMPLATE.md) →「CHANGELOG 约定」，供后续模块沿用）
- 模块 `README.md`：功能概述与核心设计补「分组视图」「取数时机」；新增「筛选 / 分组下的取数与布局」小节；
  验证清单补切换 filter / group by 一条；「异常情况与处理」补 3 条排障入口
- 模块 `AGENTS.md`：新增 L2 P6（取数范围 / 取数时机 / 布局作用域 / 布局时机 / effect 返回值五个坑）；
  更新 L1 约束 6、技术设计表「瀑布流 / 分组布局」两行、文件职责表、修订记录
- 根 `README.md` 模块一览表与 `AGENTS.md` 模块速查表：版本 `19.0.2.0.6` → `19.0.2.0.7` + 变更摘要
- 根 `TODO.md`：`T-012` 归档条目补一行本版本追溯
- 根 `STAGE_REPORT_2026-09-22.md`：速览版本行、2.4 节、6.2 界面复验清单、6.3 文件地图、5.3 风险同步
- 根 `DOCS_TEMPLATE.md`：把「修复 / 优化类版本补两节」写进 CHANGELOG 模板与约定（本版本是首个范例）

### 验证记录

| 项 | 结果 |
|----|------|
| JS 语法（`node --check`） | 4 个 js 文件全部通过 ✓ |
| SCSS 编译 | 容器内 libsass 编译 `product_card.scss` 通过，分组规则编译结果已核对 ✓ |
| 模块升级 | 开发库 `task update -- product_card_view` 无报错（assets 顺序、视图与译文正常加载）✓ |
| 仓库门禁 | `task check` 对 `product_card_view` 无告警 ✓ |
| 待目标环境验证 | 非分组 / 分组分别切换 filter 与 group by：卡片有图有信息、宽度与间隙正常（需 `-u` 升级 + 强刷浏览器）|

---

## [19.0.2.0.6] - 2026-09-22（注入改为读取时计算：修掉全新安装漏注入）

### 变更

- **换掉注入机制**：不再往 `sale` / `purchase` / `account` 的 action 里建 `ir.actions.act_window.view`
  记录、也不写它们的 `view_mode`，改为覆盖 `ir.actions.act_window._compute_views()` —— 凡
  `res_model = 'product.template'` 的动作，把 card 放到 `views` 最前（客户端切换器的按钮与默认视图
  都只认服务端算出的 `action.views`，`views[0]` 即默认视图）。
- **根因（用户实测：`task init -- --fresh` 后销售 / 采购没有 Card）**：本模块 `depends` 只有 `stock`，
  全新安装时它在 `sale` / `purchase` **之前**装完，那一刻的 `<function>` 看不到这两个模块的 action，
  之后再没有重跑机会 —— 也就是此前文档里那条「后装需再升级一次」的限制，在真实安装流程里必然发生。
  读取时计算与安装顺序、模块组合都无关。
- 附带简化：删掉 `_sync_product_card_views()`、`CARD_SEQUENCE`、XML 里的 `<function>`，以及跨模块写
  `view_mode` / 建记录 / 登记 xmlid 的全部逻辑（唯一约束、xmlid 撞名、sequence 排序四个坑随之消失）。
  本模块自己的 3 条静态声明（product ×2 + stock）保留作声明式兜底。

### 影响

- 全新库（`task init -- --fresh`）与既有库升级后，库存 / 销售 / 采购 / 发票入口的产品列表**默认都在 Card**，
  切换器保留 Kanban / List / Form / Activity
- 不再修改其它模块的数据；`ir.act_window_view` 里只剩本模块声明的 3 条 card 记录
- 无数据结构变化、无迁移

### 文档

- 模块 `README.md` / `AGENTS.md`：注入机制改写为「读取时计算」，删除已不存在的「后装需再升级」限制；
  L2 P4 保留三种做法的演进结论（为什么最终不选「往别的模块的数据里写记录」）

### 验证记录

| 项 | 结果 |
|----|------|
| `task init -- --fresh`（全新安装） | 7 个 `product.template` 动作 `views[0]` 均为 card；库里 card 记录仅 3 条（静态声明）✓ |
| 销售 / 采购 / 发票 | `views = card → kanban → list → form → activity` ✓ |
| `task check` | 通过 ✓ |

---

## [19.0.2.0.5] - 2026-09-22（T-025：切换器 Card 按钮名国际化）

### 变更

- **Card 按钮名走 `_t()` 并中文化**（`static/src/js/product_card_view.js`）：
  `session.view_info.card.display_name` 从硬编码 `"Card"` 改为 **getter** `() => _t("Card")`。
  - 为什么必须用 getter：`_t()` 返回的 `TranslatedString` 在**构造时**判断译文是否就绪
    （`this.lazy = !translatedTerms[translationLoaded]`），而本文件在模块加载期执行、早于译文就绪；
    直接调用会把 `lazy` 固化下来，之后任何取值都抛
    `Cannot translate string: translations have not been loaded`。getter 让翻译在切换器读取时（译文已就绪）再算。
- **补 po**：新增 `code:addons/product_card_view/static/src/js/product_card_view.js:0` → `Card` / 「卡片」。
- **顺带修掉 5 条一直没生效的 JS 译文**：`product_card_record.js` 的 `Product image` / `Next image` /
  `Previous image` / `Reference` / `On hand` 原本缺 `#. odoo-javascript` 注释 —— 前端译文由
  `web/controllers/utils.py::_local_web_translations()` 在运行时读 po、**按该注释筛选**，缺了就永远不下发
  （这些文案一直显示英文，且不报任何错）。现已补齐。

### 影响

- 中文界面切换器显示「卡片」，英文界面仍为「Card」
- 图片 alt / 上下一张 / 参考号 / 在手数量这些 JS 文案的中文现在真的会生效
- 无数据结构变化、无迁移

### 文档

- 模块 `README.md`：国际化节的「已知缺口」改为已解决并写清 getter 的原因；「遗留问题」移除该条
- 模块 `AGENTS.md`：i18n 约束第 4 条改写为正确做法；新增 L2 P5（`code:` 条目的运行期标记 + `_t` 的时机陷阱）
- 仓库 `.dev/scripts/check_repo.py`：修掉「按 `"\n\n"` 切块遇 CRLF 失效」与「`code:` 引用带行号后缀导致
  扩展名判断永远为假」两个缺陷后，「缺 `odoo-python` / `odoo-javascript` 标记」这条检查才真正生效；
  由于仓库里还有 5 个模块存在同类问题（记入 `TODO.md` → `T-026`），该检查暂按**警告**报出，
  `task check -- --strict` 会算失败

### 验证记录

| 项 | 结果 |
|----|------|
| po 条目 | 新增 `Card -> 卡片`；5 条 JS 条目补上 `#. odoo-javascript` ✓ |
| 前端下发链路 | 调用前端同一个函数 `_local_web_translations(product_card_view/i18n/zh_CN.po)` → 返回 6 条，含 `Card -> 卡片` ✓ |
| `task check` | 通过（本模块不再有相关警告）✓ |
| 待目标环境验证 | 中文界面切换器实际显示「卡片」（需强刷浏览器） |

---

## [19.0.2.0.4] - 2026-09-22（产品列表默认打开 Card 视图）

### 变更

- **把 Card 定为产品列表的默认视图**：插入的 `ir.actions.act_window.view` 记录带
  `sequence = 0`（模块常量 `CARD_SEQUENCE`），排在原生视图之前 —— 客户端
  `_executeActWindowAction` 取 `views[0]` 作默认视图，因此库存 / 销售 / 采购 / 发票入口打开
  产品列表时直接进入卡片视图。
  - 关键点：`ir.actions.act_window.view._order = 'sequence,id'`，而原生视图行的 `sequence` 是
    **NULL**，PostgreSQL 升序把 NULL 排在最后 —— 只要 card 的 `sequence` 是**非 NULL**（0 即可）
    它就排在最前。`19.0.2.0.3` 曾把 `sequence` 置成 NULL 让 card 退到最后（默认视图不变），
    本版按需求改回最前。
  - 归一：`-u` 时会把历史记录里 `sequence` 为空 / 0 的 card 行补成 0（幂等）。
- 静态声明的 3 条记录（`product` ×2 + `stock`）同样显式写 `sequence=0`，与注入的记录保持同一语义。

### 影响

- 7 个 `product.template` 动作的默认视图统一为 card：`views` 形如
  `['card', 'kanban', 'list', 'form', ...]`（销售 / 采购 / 发票还带 activity）
- 切换器里 Kanban / List / Form / Activity 全部保留，可随时切回；`mobile_view_mode` 仍是 kanban
- 无数据结构变化、无迁移；连续两次 `-u` 稳定通过

### 文档

- 模块 `README.md` / `AGENTS.md`：把「默认打开视图不变」改为「默认打开 Card 视图」，
  并把 L2 P4 第 2 条改写成正确结论（`sequence` 必须**非 NULL** 才能排在最前）

### 验证记录

| 入口（`product.template` 动作） | 默认 | views |
|----|------|-------|
| `sale.product_template_action`（销售 / 产品） | card | card → kanban → list → form → activity |
| `purchase.product_normal_action_puchased`（采购 / 产品） | card | 同上 |
| `account.product_product_action_sellable` / `..._purchasable`（发票） | card | 同上 |
| `product.product_template_action` / `_all`、`stock.product_template_action_product`（库存） | card | card → kanban → list → form |

---

## [19.0.2.0.3] - 2026-09-22（Card 入口修复（第二版）：改回「建记录」并修正排序）

### 变更

- **`19.0.2.0.2` 的做法不成立**：那一版只改目标动作的 `view_mode`、不建 `ir.actions.act_window.view`
  记录（理由是「`_compute_views()` 会把缺失模式补成 `(False, mode)`，照样能出按钮」）。实测**销售 /
  采购入口仍然没有 Card**：客户端切换器的条目只来自服务端算出来的 `action.views`
  （`action_service.js::_executeActWindowAction` 里 `for (const [, type] of action.views)`），
  当时 `action.views` 里根本没有 card —— `view_mode` 是普通 Char，会被外部数据重放 / 回滚打回默认值
  （实测见过 `list,card,form` 变回 `list,form`）。
- **本版做法与静态声明的三个动作完全一致**：既补 `view_mode`，又建一条 `ir.actions.act_window.view`
  记录（`view_id` 指向模块的 card 视图），并登记带**模块前缀**的 xmlid
  （`sale_product_template_action_card_view`、`purchase_product_normal_action_puchased_card_view` 等），
  避免与静态记录撞名。
- **新记录的 `sequence` 必须留 NULL**：原生视图行的 `sequence` 是 NULL，而
  `ir.actions.act_window.view._order = 'sequence,id'` 在升序里把**非 NULL 排在 NULL 之前** —— 写数字
  （如 3）会把 Card 顶成 `views[0]`，而客户端用 `views[0]` 作默认视图，于是列表会默认打开卡片视图。
  不写 `sequence` 之后，带原生 `view_ids` 的入口（销售 / 采购 / 发票）顺序变成
  `kanban → list → form → activity → card`，**默认视图不变**；早期版本留下的 `sequence=3` 会在 `-u`
  时自动归一（Integer 用 ORM 写不出 NULL，只能显式 SQL 置空）。
- `flush_all()` + savepoint + 模块前缀 xmlid 三件套，解决了 `19.0.2.0.2` 期间踩到的
  `ir_act_window_view_unique_mode_per_action` 唯一约束冲突（升级期 flush 交错、xmlid 撞名）。

### 影响

- 升级后：库存 / 销售 / 采购 / 发票入口的切换器都会出现 Card；带原生 `view_ids` 的入口默认视图不变
- 硬依赖的三个动作（`product` ×2 + `stock` ×1）没有原生 `view_ids`，Card 作为唯一的显式视图仍排在最前
  （即这三个入口默认打开卡片视图）—— 与本次修复前一致，未改动
- 无数据结构变化、无迁移；连续两次 `-u` 稳定通过

### 文档

- 模块 `README.md` / `AGENTS.md`：把 `19.0.2.0.2` 写的「只改 `view_mode`」结论改正为
  「记录 + `sequence` 留 NULL」，并把客户端判据（`action.views`）与排序坑写进 L2 P4

### 验证记录

| 项 | 结果 |
|----|------|
| 销售 `sale.product_template_action` | `views = kanban, list, form, activity, card`（默认 kanban）✓ |
| 采购 `purchase.product_normal_action_puchased` | 同上 ✓ |
| 发票 `account.product_product_action_sellable` / `..._purchasable` | 同上 ✓ |
| 库存 `stock.product_template_action_product` | Card 记录仍在，顺序与修复前一致 ✓ |
| 连续两次 `-u product_card_view` | 均通过（无唯一约束冲突）✓ |

---

## [19.0.2.0.2] - 2026-09-22（修复：Card 在销售 / 采购 / 发票入口不显示）

### 变更

- **修复 Card 视图入口缺失**：`_sync_product_card_views()` 改为按 `res_model = 'product.template'`
  扫描**所有**窗口动作（不再写死 `sale.product_template_action` / `purchase.product_normal_action_puchased`
  两个 xmlid），给每个动作的 `view_mode` 补上 `card`（插在 `form` 之前，与静态声明的
  `kanban,list,card,form` 同序）。
- **不再动态创建 `ir.actions.act_window.view` 记录**：`_compute_views()` 会把 `view_mode` 里、
  `view_ids` 中缺失的模式补成 `(False, mode)`，客户端据此渲染切换器按钮、服务端再解析该类型在模型上的
  默认视图 —— 本模块 `product.template` 只有一张 card 视图，`(False, 'card')` 必然解析到它。
  静态声明的 3 条记录保持不变（硬依赖模块，显式声明更直观）。
- 根因有两层：
  1. 原实现只补 `act_window.view` 记录、**没写 `view_mode`** —— 而静态声明的那三个动作两者都写，做法不一致；
  2. 目标动作由 `sale` / `purchase`（可选依赖）定义，本模块安装时它们通常还没装，`<function>` 那一次执行
     拿不到，之后再没有重跑机会 → 记录永远不会被创建（库里只有 product / stock 的 3 条）。
- 现在覆盖 7 个动作：库存 `stock.product_template_action_product`、销售 `sale.product_template_action`、
  采购 `purchase.product_normal_action_puchased`、发票 `account.product_product_action_sellable` /
  `..._purchasable`、以及 `product` 自带的两个动作。

### 踩坑（实现过程中实测，已写进 `AGENTS.md` → L2 P4）

- **不要在这条路径上动态建 `ir.actions.act_window.view`**：`(act_window_id, view_mode)` 上有唯一约束
  `ir_act_window_view_unique_mode_per_action`，而 install / `-u` 期间本方法会与 XML 静态记录的写入交错
  （Odoo 在 `search` 之前会先 flush 待写数据），动态 `create` 直接撞
  `duplicate key value violates unique constraint ... (188, card)`。
- **按 action 的 xmlid 末段拼新 xmlid 会撞名**：`product.product_template_action` 与
  `sale.product_template_action` 的末段都是 `product_template_action`，拼出来的
  `product_card_view.product_template_action_card_view` 与静态记录同名 → `_update_xmlids` 会把静态
  xmlid 改指到另一条记录，下一次 `-u` 静态 XML 更新那条记录时同样撞唯一约束。

> 若曾用中间版本（仅存在于 2026-09-22 本地调试期间）升级过，库里的 card 记录与 xmlid 会被改乱，
> 需手工恢复：删掉多出来的动态记录及其 `ir_model_data`，再把
> `product_card_view.product_template_action_card_view` 指回 `act_window_id = 188` 的那条记录。

### 影响

- `task update -- product_card_view` 后，上述入口的视图切换器都会出现 Card 按钮；**默认打开的视图不变**
  （`views` 的计算顺序仍是 `view_ids` 优先，kanban / list 仍是各自入口的默认视图）
- 无数据结构变化、无迁移
- **时机限制仍在**：`sale` / `purchase` 若在本模块之后安装，需要再跑一次 `-u product_card_view`
  （可选依赖的 data 注入无法自动重放）

### 文档

- 模块 `README.md`：「核心设计」「视图」「安装与使用」「验证清单」「后续维护」「遗留问题」同步为新机制
- 模块 `AGENTS.md`：技术设计表与 L2 P4 补「按 `res_model` 扫描 + `view_mode` 与记录都要写」的结论

### 验证记录

- 开发库核对（`ir_act_window` + `ir_act_window_view`）：7 个 `product.template` 动作的 `view_mode` 均含 `card`
  （`kanban,list,card,form` / `list,card,form`），静态声明的 3 条 card 记录 xmlid 归属正确，无重复、无遗漏
- **连续执行两次 `-u product_card_view` 均通过**（升级稳定性，这正是修复前的故障点）
- 待目标环境验证：销售 / 采购 / 发票入口的切换器实际出现 Card 按钮

---

## [19.0.2.0.1] - 2026-09-09（验收通过）

### 变更（i18n / 文档）

- **应用列表（Apps）中文化**：`i18n/zh_CN.po` 补充「应用列表元数据」译文，中文环境下应用卡片与详情页显示中文模块名 / 摘要 / 描述。
  - `model:ir.module.module,shortdesc:base.module_product_card_view` → 「产品卡片视图」
  - `model:ir.module.module,summary:base.module_product_card_view`：摘要整句译文
  - `model:ir.module.module,description:base.module_product_card_view`：`description` 整段译文（`translate=True` 整值翻译，`msgid` 与 `textwrap.dedent(manifest["description"])` 逐字符一致）
  - `model:ir.module.category,name:base.module_category_inventory_product` → 「产品」（`Inventory/Product` 的自定义子分类，官方 `base` 无译文）
- 说明：视图切换器上的 **Card 按钮名称**属于 `session.view_info` 的 `display_name`，与本次应用列表元数据无关，仍是遗留问题（见 `README.md` →「遗留问题」）。

### 影响

- 纯译文改动，无模型 / 字段 / 视图 / 权限变更，**无需迁移脚本**。
- `odoo -d <db> -u product_card_view --stop-after-init` 升级后，中文环境「应用」列表显示中文名称 / 摘要 / 描述与中文分类；英文环境不变。
- 这些记录归属 `base`（xmlid `base.module_*` / `base.module_category_*`、`noupdate=True`）：po 导入只补齐缺失语种，**不覆盖库中已有的 `zh_CN` 值**；后续改译文的强制刷新方式见根 `AGENTS.md` 4.8。

### 文档

- 同步 `__manifest__.py`（版本 19.0.2.0.1）、`README.md`（国际化节）、`AGENTS.md`（当前版本 + i18n 约束）、根 `README.md` / `AGENTS.md` / `TODO.md`。
- 规范沉淀：根 `AGENTS.md` 新增 4.8「应用列表元数据（模块名 / 摘要 / 描述 / 分类）翻译规范」，并更正 4.1 中「写在自研模块 po 里匹配不到、无效果」的错误说法。

### 验收记录（T-013）

- 验收日期：2026-09-09
- 验收环境：目标 Odoo 19 部署环境（已安装「简体中文 (zh_CN)」）
- 验收结果：6 项验收标准全部通过（中英文各验一遍）
  - [x] `odoo -d <db> -u product_card_view --stop-after-init` 升级无报错
  - [x] 中文「应用」列表：卡片标题显示「产品卡片视图」，摘要为中文
  - [x] 中文「应用」详情：描述整段为中文
  - [x] 中文「应用」左侧分类：显示「库存 / 产品」——父级 `Inventory` 沿用官方译文，自定义段 `Product` → 「产品」由本模块提供
  - [x] 切回英文界面：名称 / 摘要 / 描述回到 `__manifest__.py` 的英文原文
  - [x] 仓库内自校验通过：无重复 `msgid`；`shortdesc` / `summary` / `description` 的 `msgid` 与 manifest 逐字符一致；源码无残留中文界面文本（脚本见根 `AGENTS.md` 4.6）

> 本版本只覆盖应用列表元数据；Card 视图本身的功能项（多图 / 变体 / 销售与采购入口 / 双语 / 权限）
> 仍按 `19.0.2.0.0` 的验证清单待目标环境复验。
> 后续若只改译文（`msgstr`），这些记录是 `noupdate=True`，`-u` 不会覆盖库里已有的 `zh_CN`，
> 需按根 `AGENTS.md` 4.8 第 9 条用 `TranslationImporter.save(force_overwrite=True)` 或先清 `zh_CN` key 再升级。

---

## [19.0.2.0.0] - 2026-09-09（Card 入口已确认，其余待复验）

### 交付记录（T-012）

- 验收日期：2026-09-09
- 验收环境：目标 Odoo 19 部署环境（`19.0-20260817`）
- 验收结果：Card 视图入口（库存 → Products 切换器）已由使用方确认可见可用；卡片内容 / 多图轮播 /
  变体联动 / Sales / Purchase 入口 / 中英双语 / 权限列入待复验清单
  （见模块 `README.md` →「验证清单」「测试用例」「遗留问题」）

### 变更

- **架构调整：从「独立动作 + `js_class`」改为注册新 view type `card`**（T-012 需求是官方产品列表
  右上角能切到卡片视图；`js_class` 变体不会在切换器产生新按钮，故必须新增 view type）：
  - Python：`ir.ui.view.type`、`ir.actions.act_window.view.view_mode` 的 Selection 追加 `card`。
  - JS：`registry.category("views").add("card", {...kanbanView, type:"card", ArchParser, Model, Renderer})`；
    **patch `session.view_info.card`**——核心 `view.js` 用 `type in session.view_info` 校验、
    `loadView` 用 `session.view_info[type]` 判存在、`action_service.js` 解构
    `{icon, display_name, multi_record}` 生成按钮；该白名单由服务端核心提供，模块级 Python 无法扩展。
  - 新增 `ProductCardArchParser`（继承 `KanbanArchParser`）：card arch 经 server 校验禁止 OWL 指令，
    不能写 `<templates>`，故在 `parse` 时注入虚拟 `<t t-name="card">` 以满足父类的模板检查。
- **注入官方产品动作**（只加 Card 视图入口，不改官方列表 / 看板 / 表单本身）：
  - 硬依赖：`product.product_template_action`、`product.product_template_action_all`、
    `stock.product_template_action_product`——`view_mode` 加 `card` + 各加一条 `act_window.view` 记录。
    （定位到库存入口实际绑定的是 `stock.product_template_action_product`，
    原先只扩展 product 的两条 action 不生效，这是「升级成功但无 Card 按钮」的根因）
  - 可选：`sale.product_template_action`、`purchase.product_normal_action_puchased` 由
    `<function>` → `_sync_product_card_views()` 条件注入。
- **移除独立的「Product Cards」动作与菜单**：Card 已成为官方 Products 的并列视图，独立入口不再需要
  （`i18n/zh_CN.po` 中对应的 3 条孤儿译文同步删除）。
- 切换器图标改为 `oi oi-view-kanban`（`session.view_info.card.icon`）。

### 影响

- 用户可见：官方 Products（库存 / 销售 / 采购入口）切换器新增 **Card** 按钮
  （顺序 Kanban / List / Card / Form）；默认视图不变，官方 list / kanban / form 的 arch 未改动。
- 依赖收敛：`depends` 仅为 `["stock"]`。
  - `product_image` 改可选：未安装时 `env.get("product.image.gallery")` 返回 `None`，图库留空，
    卡片**只显示主图**，其余功能不受影响。
  - `sale` / `purchase` 改可选：未安装时 `env.ref(..., raise_if_not_found=False)` 判空跳过，不注入也不报错；
    后装这两个模块时需再升级一次本模块才会注入。
- 数据库：无新建模型 / 字段 / 表结构变更，**无需迁移脚本**；仅新增 1 条 `ir.ui.view` 与若干
  `ir.actions.act_window.view` 记录，并扩展已有 action 的 `view_mode` 字段值。
- **卸载注意**：Odoo 不记录字段覆盖前的值，卸载后官方 action 的 `view_mode` 不会自动回滚为不含 `card`，
  需人工确认。
- 风险：`session.view_info` 的 patch 依赖 Odoo 内部实现（校验与解构方式），Odoo 升级需回归
  （见模块 `AGENTS.md` → L2 P2）。

### 文档

- 同步 `__manifest__.py`（版本 + description）、`README.md`（需求 / 接口 / 验收 / 截图 / 遗留问题）、
  `AGENTS.md`（技术设计 / L1 约束 2 改写 / L2 P1~P4 / T-012 复盘）、`i18n/zh_CN.po`
- 同步根 `TODO.md`（T-012 移出，标记已完成）、根 `README.md`（模块一览表 + 路线图）、
  根 `AGENTS.md`（模块速查表）

---

## [19.0.1.0.1] - 2026-09-08（待验证）

### 变更

- 代码结构 / 性能 / 可维护性优化（不改功能，不改 API）：
  - 后端 `models/product_card.py`：变体搜索加 `order="product_tmpl_id, id"`，合并两次属性
    收集循环为一次，删去构造 payload 时每模板的 `sorted`；逻辑等价、顺序一致。
  - 前端 `product_card_record.js`：
    - `selectionText` 直接读 `payload.rows`，避免重复走 `rows` getter；
    - 图片轮播区补 `pointerleave` / `pointercancel` 重置滑动起点，避免鼠标移出后残留误判；
    - 卡片补 `t-on-keydown`：聚焦时左右方向键翻图，提升键盘可访问性。
  - `__init__.py`：调整为 `models` 在前、`controllers` 在后（Odoo 惯例，无依赖影响）。
  - `product_card_model.js`：为 `withCache = false` 补注释说明原因。
  - 控制器 `/product_card/payload` 路由 `type="json"` → `type="jsonrpc"`（Odoo 19 起
    `type="json"` 为废弃别名，安装会出 `DeprecationWarning`）。
  - **修复** `_get_product_card_view_payload`：`product.product` 在 Odoo 19 经
    `product.template.attribute.value`（PTAV）关联属性与值，原代码误用已不存在的
    `attribute_value_ids`（且循环内引用未定义的 `value_id`），导致请求 500
    `AttributeError: 'product.product' object has no attribute 'attribute_value_ids'`。
    改用 `product_template_attribute_value_ids` + `attribute_id` /
    `product_attribute_value_id`。
  - **修复** 卡片模板里 `t-att-title="_t('Reference')"` / `_t('On hand')` 直接调
    `_t`：OWL 模板编译上下文无全局 `_t`，运行时报
    `TypeError: ctx._t is not a function`。改为组件 getter `referenceLabel` /
    `onHandLabel` 返回 `_t(...)`，po 入口（`code:addons/.../product_card_record.js:0`）不变。
  - **修复** 卡片空白 + 加载卡死（核心 bug，三版迭代）：
    ① 第一版在 `_loadData` 里把 payload 挂到 `super._loadData` 返回的 `result.records`
       原始对象上，但 `_createRoot` 随后用它们重建 Record 实例时丢弃自定义属性，
       导致卡片空白（空骨架 + 底部「—」）；
    ② 第二版改把 payload 存到 reactive model 实例 `productCardPayload`，触发了
       reload 循环（keepLast 竞争 + 第二次空响应 + 页面一直加载中）；
    ③ 第三版重写 `load`，按 resId 挂到 reactive `record.productCardData`，给 reactive
       Record 实例加属性触发 Owl DataModel 内部 effect（dirty/onUpdate）→ 前端卡死；
    ④ 第四版改用 module-level WeakMap by model（key=`toRaw(model)` → resId → payload），
       重写 `load` 在 `super.load` 后填充。toRaw 解决了 raw vs proxy 的 identity MISS，
       但又触发 `super.load` 的 `notify` → `onUpdate` → 再调 `load` → 无限循环卡死；
    ⑤ Renderer 方案：完全不重写 model 的 `_loadData` / `load`（前几版都触发 reactive 循环），
       改由 ProductCardRenderer 的 `onWillStart` / `onWillUpdateProps` 生命周期钩子拉取
       payload 填入**非 reactive 的 module-level 全局 Map**（按 resId 索引）。生命周期
       钩子不在 reactive effect 内，不触发 Owl DataModel 的 onUpdate / reload 循环。
       `ProductCardModel` 只保留 `withCache = false`，不重写任何方法。卡片通过
       `getProductCardPayload(resId)` 取；Renderer 钩子等 `await rpc` resolve 才渲染。
    ⑥ _resId 缓存切断 useRecordObserver 循环：KanbanRecord 父类 setup 注册了
       `useRecordObserver`（effect 监听 `props.record` 并写 `dataState.record` 触发
       re-render）；卡片 `payload` getter 若访问 `this.props.record.resId` 或
       `this.dataState.record?.id?.value`（reactive），会与该 effect 冲突 → render
       循环卡死。修复：setup 时把 `resId` 缓存到**非 reactive**实例属性 `_resId`
       （`onWillUpdateProps` 同步更新），payload / templateId getter 用 `_resId` 取，
       不访问任何 reactive state。
    ⑦ VariantRow sub-component 隔离嵌套 t-foreach：删 variants 不卡、加回卡，
       二分定位到 values t-foreach（内层嵌套 t-foreach）触发 Owl 重渲染循环。
       拆出 `ProductCardVariantRow` sub-component，外层只 t-foreach rows，内层
       values 的 t-foreach 在独立组件内，reactive 依赖不再跨层耦合，循环切断。
    - 卡片宽度固定 240px（`column-width: 15rem` + 卡片 `width`/`max-width: 15rem`），
      所有屏幕尺寸一致；变体按钮 active 样式加 `!important` + `box-shadow` 覆盖
      Bootstrap `.btn.active`，active 时显示对勾图标（`fa-check`）。
    同时修正 `templateId` 用 `record.resId`（原用 `record.id` 是 datapoint 内部编号，
    会导致图片 URL 404）。

### 影响

- 无功能 / API / 数据结构变更；无迁移脚本；无新字段或权限。
- T-012 待验证基线随本版本（`19.0.1.0.1`）；原验证清单仍适用，建议按本版本重验。
- 已自校验：JS（`node --check`）/ XML（minidom）/ lint 全部通过；无新增中文界面文本。

### 文档

- 同步 `__manifest__.py` 版本、模块 `CHANGELOG.md`、`AGENTS.md` / `README.md` 版本引用。

---

## [19.0.1.0.0] - 2026-09-08（待验证）

### 变更

- 初始版本，新增 `product_card_view` 模块：产品列表卡片视图（瀑布流），独立动作 + 菜单
  （库存应用 → Products → Product Cards），不修改官方默认产品视图。
- 后端（纯 `product.template` 方法扩展 + JSON 控制器路由 `/product_card/payload`）：
  - 每批产品一次返回卡片数据：模板信息、全部 active 变体（属性组合 / 参考号 / 在手）、
    模板共享图库与各变体专属图库引用；
  - 变体按钮行只保留真实存在于变体组合中的属性与值；
  - 在手读取 `product.product.qty_available`（不可追踪产品返回 `—`）；依赖 `product_image` + `stock`。
- 前端：
  - `views` 注册表新增 `product_cards`（`kanbanView` 派生，替换 Model / Renderer），
    kanban 视图 arch 声明 `js_class="product_cards"` 启用；
  - Model 在每页加载后批量拉取 payload 挂到 record 上；
  - 卡片组件实现顶部多图轮播（左右箭头 / 滑动 / 计数）、title / reference / on hand 信息区、
    按属性分行的变体按钮（选值切换图片 / 参考号 / 在手，禁掉不存在的组合），
    模板层与变体层两套图片不叠加；
  - 渲染器对 `web.KanbanRenderer` primary 继承仅加根类，未分组时以 CSS 多列实现瀑布流并自适应列数。
- 新增 `i18n/zh_CN.po`：动作 / 菜单 / help / JS 术语的中文译文（源语言英文，默认英文）。

### 影响

- 无新建模型、无数据库结构变更、无迁移脚本；无 `security/ir.model.access.csv` 需求。
- 官方默认产品列表 / 看板 / 表单均未修改；仅新增动作、菜单与一个 kanban 视图记录。
- 依赖 `product_image`（多图数据结构）与 `stock`（在手数量 + 库存应用菜单）。
- `19.0.1.0.0` 为初始版本。

### 文档

- 同步创建 `README.md`（功能 / 设计说明 / 安装 / 待验证清单 / 回滚）、`AGENTS.md`、`CHANGELOG.md`
- 同步更新根目录 `TODO.md`（T-012 进行中）、`README.md` 模块一览表与路线图、`AGENTS.md` 模块速查表

---
