# T-014 订单行产品悬浮卡 · 开发复盘

> **文档定位**：面向本模块维护者与后续「列表内联浮层 / Odoo 19 前端 patch」类需求的过程复盘。
> 与其余文档的关系：**怎么用**看 [`README.md`](README.md)；**改了什么**看 [`CHANGELOG.md`](CHANGELOG.md)；
> **不能破坏什么 + 陷阱档案**看 [`AGENTS.md`](AGENTS.md)；**代码为什么这么写（架构 / 数据流 / 核心要点 / 坑点速查）**
> 看 [`IMPLEMENTATION.md`](IMPLEMENTATION.md)。本文只回答「为什么走了这些弯路、下次怎么少走」——
> 与 `IMPLEMENTATION.md` 有重叠时，以**本文为过程与方法论、实现说明为结论速查**。
>
> **时间与规模**：2026-09-12 ~ 2026-09-16；版本 `19.0.1.0.0` → `19.0.1.6.0`，共 **15 个版本**（其中 9 个是修同一个「悬停无反应」）。
> **状态**：功能自测通过，**目标环境待验证**。

---

## 一页速览

| 维度 | 结论 |
|------|------|
| **做了什么** | 报价单 / 销售订单订单行悬停（触屏长按）弹出**产品详情**浮层：图片 / 名称 / 型号 / 规格 / 描述 / 可用库存（**不含任何价格**）；新增未保存行同样可预览；每页一次批量取数 + 浏览器缓存，悬停不发请求 |
| **技术形态** | 纯 `_inherit` + 前端 patch，**不新增模型 / 字段 / 权限 / 视图**；一个内部 JSON 接口 + 一个 OWL 展示组件 |
| **最贵的三个教训** | ① **没读框架源码就猜根因**，导致 3 个版本（`0.1`/`0.2`/`1.1.0`）在错误方向上打补丁；② **往 assets 加新文件没意识到要 `-u`**，让整个模块加载失败（`1.4.1` 修复）；③ **静默失效类 bug 没有日志就无从下手**，诊断日志是这次唯一真正加速排查的投资 |
| **沉淀下来的资产** | 日志链路（`assets loaded` → `prefetch` → `payload` → `hover row` → `popover opened`）、一行 `self-check`、17 条陷阱档案、一份可复用的模块自校验脚本（见附录 B） |
| **最终认定** | 真正的根因只有一个：**行 `data-id` 是字符串 `"datapoint_N"`，却被 `Number()` 成 `NaN`**，使行归属反查恒失败 |

---

## 一、开发重点

### 1.1 核心目标与范围

| 项 | 内容 |
|----|------|
| 业务目标 | 外贸 SOHO 报价时不必离开单据去翻产品资料：订单行悬停即看产品关键信息 |
| 载体 | 报价单 / 销售订单（共用 `sale.order.line` 与同一视图）的订单行列表 |
| 展示内容（最终口径） | 图片、名称、型号（`default_code`）、规格（变体属性）、销售描述、**可用库存** |
| **明确不做** | **不展示任何价格**：订单行的数量（Quantity）与本单单价（Unit Price）（`19.0.1.5.0` 移除）、产品售价（Sales Price，`19.0.1.6.0` 移除）—— 浮层定位是"产品详情"（看产品长什么样、什么规格），价格在订单行与产品表单上本来就看得见 |
| 跨设备 | 触屏无 hover → 长按 500ms 弹同一浮层；浮层随视口收窄、空间不足自动换侧 |
| 硬约束 | 不改官方视图与核心源码、不新增字段 / 权限、不影响行原有交互、悬停不发请求、源语言英文 |

### 1.2 关键功能模块

| 模块 | 落地位置 | 关键技术 | 设计意图 |
|------|----------|----------|----------|
| **触发链路** | `static/src/js/product_hover_list_patch.js` | patch `web.ListRenderer`；`document` 级**捕获阶段**事件委托；行归属用 `data-id` 反查 `props.list.records` | 不依赖具体视图 arch、不依赖自定义渲染器的根节点结构 |
| **浮层与定位** | 同上 + `product_hover_card.js` + `product_hover_templates.xml` | `usePopover` 服务渲染在 overlay；`_positionProductHover()` 自接管 `left/top` 跟随鼠标；越界翻侧 / 贴边 | 不改变列表 DOM，因此不影响点击、内联编辑、勾选、删除 |
| **数据链路（已保存行）** | `models/sale_order_line.py` + `controllers/product_hover_controller.py` | `_get_product_hover_payload()` 批量装配；`POST /sale_product_hover/payload`（`auth="user"`、不 `sudo`）；数字用 `formatLang` 格式化 | 前端不解析 many2one、不做货币 / 精度格式化，只渲染字符串 |
| **数据链路（未保存新行）** | `static/src/js/product_hover_cache.js` | 前端用**标准 ORM** `searchRead("product.product")` 直读产品（`formatFloat` / `formatMonetary`） | 新行未落库、服务端查不到 → **干脆不查订单**，且不依赖服务端升级 |
| **缓存与性能** | `product_hover_cache.js` | 模块级**非 reactive** `Map`；按行 id 差集预取；新行按 `product_id` 缓存；上限 2000 行 | 悬停零请求；避免 reactive 环路与内存无界增长 |
| **跨设备交互** | `product_hover_list_patch.js` | `touchstart/move/end/cancel` 长按；位移 >10px 取消；长按后吃掉一次 `click`；手势后 800ms 忽略补发的 mouse 事件 | 触屏没有 hover，且长按语义是"看详情"而非"打开记录" |
| **诊断与自证** | 三处 | 统一 `[sale_product_hover]` 前缀 info 日志链路；`__server_version` 回显；后端版本自动读 manifest | 静默失效类 bug（既不报错也不生效）唯一的下手点 |
| **i18n 与文档** | `i18n/zh_CN.po` + 三件套 | 源码只写英文；po 含应用列表元数据三条（`msgid` 与 manifest 逐字符一致） | 中文环境「应用」列表不显示英文 |

### 1.3 主要技术实现要点

1. **事件委托必须用捕获阶段**：列表行模板在 `tr.o_data_row` 上挂着 `t-on-mouseover.capture`，某些状态会 `stopPropagation()`；冒泡阶段的 document 监听会被整段掐断。
2. **行归属不靠 DOM 包含关系**：`this.el.contains(ev.target)` 在自定义渲染器（`sale.ListRenderer.RecordRow` ← `account.SectionAndNoteListRenderer`）下不可靠；改为「行的 `data-id` 能否在 `props.list.records` 里查到」。
3. **`data-id` 与 `record.id` 是字符串**（`"datapoint_42"`），必须按字符串比较；`record.resId` 才是数据库 id（数字）。两者混用**不报错、只静默失效**。
4. **popover 的 `open()` 会先 `close()` 上一个浮层，且同步触发 `onClose`**：父级状态必须在 `open()` 之后补写，否则同一行内移动会反复关闭重开。
5. **跟随鼠标 = 自己接管定位**：Odoo 的 `reposition()` 把浮层设成 `position: fixed` 并写 `left/top`，因此补丁可以直接改写这两个值；每次 `onPositioned` 回调后重新套用一次光标位置。
6. **屏蔽原生 tooltip 的正确层次**：Odoo 的 tooltip 服务挂在 `document.body` 的捕获阶段 `mouseenter`，补丁在更外层的 `document` 捕获阶段**只对"确实有浮层数据的行"**`stopPropagation()`。
7. **新行数据不碰订单**：订单行未保存 → 服务端没有记录；而卡片要展示的全部是产品侧信息 → 直接按 `product_id` 读产品即可，逻辑反而更短。
8. **缓存去重必须先想"响应为空"分支**：任何「先记已请求、后取数」的标记，取数成功但结果为空时都必须回退，否则该 key 永久失效且不报错。
9. **版本自证的两个对照物**：后端版本（`__server_version`）与前端资源邮戳（JS 里的 `MODULE_VERSION`）——**故意不同源**，不一致才说明"浏览器加载的是旧资源"。
10. **只用已登记的文件承载前端代码**：往 `assets` 新增文件需要服务端重读 manifest（`-u` / 重启），改已有文件内容才可只靠强刷。

---

## 二、开发难点

### 难点 1：现象是「什么都不发生」——没有报错、没有请求、没有浮层

- **难在哪**：没有异常栈可比对，唯一线索是"用户说没反应"。第一版把监听挂在渲染器根节点 `t-ref="root"` 上，而订单行用的是自定义渲染器，根节点 ref 不可靠 → 监听整段被跳过。
- **解决思路**：把「不报错」拆成可观测的**阶段**，给每一段加一行 info 日志：资源是否加载（`assets loaded`）→ 列表是否识别（`prefetch`）→ 接口是否有数据（`payload: requested N, received M`）→ 悬停是否命中（`hover row`）→ 浮层是否真的打开（`popover opened`）。
- **结果**：日志一出来就直接定位——`prefetch` / `payload` 都正常但**完全没有 `hover row`**，问题被压缩到"事件收到了但被判定为不属于本列表"这一段。

### 难点 2：需求口径在过程中变了两次，且第二次是"减法"

- **难在哪**：需求从「名称 / 规格 / **数量** / **单价** / 图片等关键信息」→ 中途以"产品详情"为准，去掉数量与单价（`19.0.1.5.0`），随后连产品售价也一并去掉（`19.0.1.6.0`）。若只改模板而不回收取数链路，会留下「接口还在算，界面不展示」的死代码，后续维护必然踩坑。
- **解决思路**：把「展示字段」当成**贯穿层**看待——一次改动同时收窄后端 payload、前端装配、模板、i18n、文档与验收标准；并把签名（缓存键）从「产品\|数量\|单位\|单价\|币种」简化为 `product_id`。
- **结果**：`19.0.1.5.0` 一次性收窄四处，顺带修掉一个隐藏缺陷——原来的「单价 = 售价则不重复展示售价」判据在单价行移除后会让两者相等的产品**一个价格都不显示**；`19.0.1.6.0` 用同一套手法再收一次（后端少读 `list_price`、前端删掉 `formatMonetary` 与公司币种、模板删行 + 明细表加 `t-if`、po 下线 `Sales Price`），至此**价格相关的取数与格式化代码全部清零**。
- **这次新发现的小坑**：删掉常驻的「产品售价」行后，`dl.o_sph_fields` 可能对不跟踪库存的产品（服务类）**整块为空**，而它带 `border-top` + 间距，会留下一条空分隔线 → 明细表加了 `t-if="onHandText"`。**删行时要顺手检查"容器是否可能为空"**。

### 难点 3：框架内部行为不可见（Odoo 前端）

- **难在哪**：本模块踩到的坑有一半在 Odoo 内部：list 行模板的捕获监听、`reposition()` 的坐标基准、`overlay.remove()` 同步调 `onRemove`、tooltip 服务的挂载位置、`Record.isInEdition` 对 `!resId` 恒为真、`Manifest` 的版本规范化。
- **解决思路**：建立「**先读源码再改代码**」的硬规矩——本地克隆 Odoo 19 到 `~/Code/odoo`，遇到行为疑问先 `grep` 实现再动手；把结论写进 `AGENTS.md` 的陷阱档案（含文件路径与行级依据），避免重复考古。
- **结果**：`data-id` 类型、`open()` 先 `close()`、`get_manifest()` 返回空 dict 而非抛错等关键结论都来自源码，而不是试错。

### 难点 4：让浮层"跟着鼠标"而不是"贴着行"

- **难在哪**：`usePopover` 的定位由 Odoo 接管（锚点是行），要跟随鼠标就必须**部分接管**：既不能让 Odoo 的定位把我们覆盖，又不能在 Odoo 每次重定位（滚动 / 缩放 / 挂载）后丢掉光标位置。
- **解决思路**：确认 `reposition()` 写的是 `position: fixed` + `left/top`（视口坐标）→ 用 `mousemove` + `requestAnimationFrame` 合帧直接改写 `left/top`；再用 `onPositioned` 回调在 Odoo 重定位之后重新套用一次。
- **结果**：`19.0.1.2.0` 实现，`holdOnHover` 让指针进入浮层后停止跟随，便于阅读。

### 难点 5：未保存的新行没有数据来源

- **难在哪**：行还没落库，按行 id 反查必然失败；早期甚至尝试把新行"伪装成草稿"发给接口，导致既要改服务端、又要升级后端，恰好撞上"前端已更新、后端没升级"的老问题。
- **解决思路**：回到需求本质——卡片要展示的**全是产品侧信息**，与订单无关 → 直接按 `product_id` 用标准 ORM 读产品，行上的取值一个都不需要。
- **结果**：`19.0.1.4.0` 起新行路径**不依赖服务端升级**，上下文只剩 `{key, product_id}`；`19.0.1.5.0` 移除数量 / 单价后进一步简化，连"表单值变化要重新装配"的逻辑都不需要了。

### 难点 6：多端交互互相打架（触屏）

- **难在哪**：触屏没有 hover，只能长按；但长按结束后浏览器会补发 `click`（会打开记录）、抬手后还会补发一轮 `mouseover`（被当成悬停），表现为"点一下弹两次"或"长按直接打开记录"。
- **解决思路**：长按触发时挂**一次性** `click` 捕获监听吃掉紧随的那一次点击；`touchstart` 起置"触摸中"标记，手势结束后 800ms 内忽略 mouse 事件；`touchmove` 位移 >10px 视为滚动取消长按。
- **结果**：`19.0.1.1.0` 起长按 / 滚动 / 点击三种意图互不干扰。

### 难点 7：「前端新、后端旧」的黑洞

- **难在哪**：`?debug=assets` 模式下 JS / SCSS 按文件 mtime 自动重建（不需要 `-u`），而 Python 必须 `-u` **且重启进程**；于是经常出现"前端看着是新的、接口却是旧的"，症状依然是"没反应"。
- **解决思路**：加**版本自证**：接口回显服务端版本（`__server_version`），前端加载时打印自己的资源邮戳，并在页面打开时输出一行 `self-check: assets X, server Y`；不一致就明确报出该做什么。
- **结果**：`19.0.1.3.3` / `19.0.1.5.1` 之后，这类问题从"猜"变成"看一行日志"；后端版本进一步改为自动读 `__manifest__.py`，版本维护从三处降到两处。

---

## 三、踩坑记录

### 3.1 总览

> 完整技术细节见 [`AGENTS.md`](AGENTS.md) → L2「踩坑档案」（陷阱 1~17）。下表按**排查曲折度**排序，「★★★」= 花了 3 个以上版本的。

| # | 版本 | 现象（一句话） | 根因（一句话） | 规避方法 | 曲折度 |
|---|------|----------------|----------------|----------|--------|
| 1 | `0.0`~`1.1.0` | 悬停完全无反应，无报错，**连 `hover row` 都没有** | 行 `data-id` 是字符串 `"datapoint_42"`，被 `Number()` 成 `NaN` → 行归属反查恒失败 | 按字符串比较（两侧 `String()`）；与 Odoo 官方 `kanban_renderer.js` 写法对齐 | ★★★ |
| 2 | `1.4.0`→`1.4.1` | 控制台 `modules … have not been defined: ['@sale_product_hover/js/product_hover_product']`，模块整个没加载 | 往 `assets` **新增文件**，而运行中的进程内存里是旧 manifest（`?debug=assets` 只重建内容、不重读 manifest） | 代码写进已登记文件；确需新增文件则必须 `-u` / 重启 | ★★★ |
| 3 | `0.1`/`0.2` | 同上（悬停无反应），但接口 200、数据完整 | 监听挂在自定义渲染器不可靠的根节点 ref 上；冒泡阶段委托被行内 `stopPropagation` 掐断 | document 级**捕获阶段**委托；不再用 `this.el.contains()` | ★★★ |
| 4 | `0.2`→`1.1.0` | 行为难以预测：关掉又重开、日志重复 | 「事件双绑定」（document + 根元素两套监听）互相干扰，判重变量还被关闭流程清空 | **只保留一套监听**；出现"不触发"先找根因，不要加第二套兜底 | ★★ |
| 5 | `0.0`~`1.1.1` | 浮层弹出时同时冒出单元格的黑色原生 tooltip | Odoo tooltip 服务挂在 `document.body` 捕获阶段 `mouseenter` | 在更外层的 `document` 捕获阶段，**只对有数据的行** `stopPropagation()` | ★★ |
| 6 | `1.1.1` 前 | 用户反馈"有显示但没跟随鼠标" | popover 定位锚在行上，未接管 `left/top` | `_positionProductHover()` 自接管定位 + `onPositioned` 兜底重套 | ★★ |
| 7 | `1.1.0` 期间 | 同一行内轻移鼠标，浮层反复刷新 | `open()` 内部先 `close()` 旧浮层，而 `overlay.remove()` **同步**触发 `onClose` → 父级状态被清空 | 状态在 `open()` **之后**补写；用 `getPopoverForTarget(row)` 跳过重复打开 | ★★ |
| 8 | `1.3.0` 前 | 新增的产品行永远没有预览；且列表里有一条新行时其它已保存行也被挡 | `Record.isInEdition` 对 `!resId` 恒为真 → 编辑态避让一刀切 | 避让条件收敛为「`editedRecord === record && record.resId`」 | ★★ |
| 9 | `1.3.0`→`1.3.1` | 选了产品后悬停新行无数据、无请求、无报错（永久失效） | 「已请求」标记在发请求前就写入，响应里没有该行数据时未回退 | 空结果必须回退标记；失败给出可操作的 `console.error` | ★★ |
| 10 | `1.3.2` | `Uncaught TypeError: getLineHoverPayload is not a function` | 整份重写缓存模块时**漏了一个导出**（导入侧仍引用） | 改完 JS 必跑「命名导入 vs 导出」自查脚本；跨模块 helper 加载期 `typeof` 自检 | ★★ |
| 11 | `1.1.0` 前后 | SCSS 弹 `SCSS error dialog`，`web.assets_web` / `web.assets_web_print` **整份 CSS 编译失败** | `min(20rem, calc(100vw - 1.5rem))` 被 Sass 当内置函数求值，`calc()` 不是数字 | 拆成 `width` + `max-width: calc(...)`；改 SCSS 必跑 dart-sass 编译 | ★★ |
| 12 | `1.1.0` 设计期 | 触屏长按同时打开了记录 / 点一下闪出浮层 | 长按后浏览器补发 `click`；抬手后补发 `mouseover` 被当成悬停 | 一次性 `click` 捕获吃掉 + 800ms mouse 事件宽限 + 位移取消 | ★ |
| 13 | `0.1` | 某环境下接口整体失败（前端只表现为"没有浮层"） | 直接 `read()` 固定字段列表，字段缺失即 `Invalid field` 整批抛错 | 先按模型实际字段过滤再 `read()`；控制器加 try/except + 服务端日志 | ★ |
| 14 | 设计期（预防） | — | 行加 `mouseenter` / `mouseleave` 委托（不冒泡）；指针移入浮层立即消失；关闭后回到行上不重开；异步返回时行已切换 | 统一用可冒泡的 `mouseover` / `mouseout`；关闭前判断是否移入浮层；关闭时复位"当前行"；异步前先校验行是否仍是当前行 | 预防 |

### 3.2 详录：3 个最贵的坑

#### ① 悬停恒失败：`data-id` 被当成数字（`19.0.1.0.0` ~ `19.0.1.1.0`）

**现象**：控制台只有

```text
[sale_product_hover] prefetch sale.order.line: 1 saved line(s)
[sale_product_hover] payload: requested 1, received 1
```

**完全没有 `hover row`**；鼠标停在订单行上毫无反应，也不报错。

**排查过程**：

1. 先怀疑资源没加载 → 有 `assets loaded (版本)`，排除；
2. 再怀疑事件没到 → 临时在 document 捕获阶段打点，事件到了；
3. 再看"为什么被跳过" → 卡在行归属判定；
4. 读 Odoo 源码 `model/relational_model/utils.js`：
   ```js
   export function getId(prefix = "") { return `${prefix}_${++nextId}`; }  // → "datapoint_42"
   ```
   而我们的代码是 `const id = Number(row.dataset.id)` → `NaN` → `Number.isFinite(NaN)` 为假 → 直接 `return null`。

**根因**：行 `data-id` 是 Owl 的 **datapoint id（字符串）**，`record.resId` 才是数据库 id（数字）。**预取走的是 `resId`**，所以数据链路看起来完全正常，极具迷惑性。

**修法**：按字符串比较，与 Odoo 官方一致（`kanban_renderer.js`：`records.find((e) => e.id === target.dataset.id)`）：

```js
const datapointId = row.dataset.id;
return (this.props.list.records || []).find((record) => String(record.id) === datapointId) || null;
```

**复查点**：任何"用 DOM 找 record"的新逻辑，先在控制台打印 `$0.dataset.id` 与 `record.id` 的**类型**。

#### ② 模块整个加载失败：往 `assets` 新增文件（`19.0.1.4.0` → `1.4.1`）

**现象**：

```text
The following modules are needed by other modules but have not been defined,
they may not be present in the correct asset bundle:
['@sale_product_hover/js/product_hover_product']
The following modules could not be loaded because they have unmet dependencies:
(2) ['@sale_product_hover/js/product_hover_cache', '@sale_product_hover/js/product_hover_list_patch']
```

**排查过程**：`manifest` 里明明登记了 → 但 bundle 里没有 → 意识到「assets 的文件清单来自 manifest，而**运行中的 Odoo 进程内存里是旧 manifest**」；`?debug=assets` 只按文件 mtime 重建 bundle **内容**，不会重新读 manifest。

**根因**：我之前一直强调"改 JS 只需强刷浏览器"——这条**只对"改已有文件的内容"成立**；**新增文件就是动 manifest，必须 `-u`（或重启进程）**。这次为了代码整洁拆了一个新文件，代价是整个模块不可用。

**修法**：把新行取数逻辑**并入已登记的 `product_hover_cache.js`**，删除新文件、从 assets 移除，清单回到原来 5 项（与线上进程内的清单一致）→ 只需强刷。

**规避**：根 `AGENTS.md` 前端规范 + 模块 `AGENTS.md` 陷阱 17 已写成硬约定：**不要往 assets 新增文件**；确需新增必须 `-u` 并在交付说明中写明。

#### ③ 猜根因的代价：两版无效补丁（`19.0.1.0.1` / `0.2`）

**过程**：第一版失效后，我在**没读框架源码**的情况下连续加了两层"保险"：document 级委托 + 根元素兜底（**事件双绑定**）、再加诊断日志。结果：

- `0.2` 的双绑定让同一事件被两套监听处理，行为更难预测（关了又开、日志重复）；
- 真正的原因（`data-id` 类型、捕获阶段、行模板 `stopPropagation`）一个都没碰到。

**教训（写进流程）**：

1. 静默失效必须**先建立可观测性**（分段日志），再动手改逻辑；
2. 涉及框架行为的分歧，**先 `grep` 框架源码**，把"猜测"换成"依据"；
3. 不能用"再加一套兜底"来对付"没触发"——那会把"没触发"变成"触发两次 + 状态错乱"；
4. 一次只改**一个**可疑点，否则修好了也不知道是哪一处起了作用。

### 3.3 沉淀下来的排查方法论（可直接复用）

| 手法 | 用法 |
|------|------|
| **分段日志链路** | `assets loaded` → `prefetch` → `payload: requested/received` → `hover row` → `popover opened`；缺哪一段就锁定在哪一段 |
| **一行自检** | 页面打开时输出 `self-check: assets X, server Y`，判断"前端资源 / 后端代码"哪边旧 |
| **加载期 helper 一致性检查** | 跨模块命名导入的 helper 在加载期做一次 `typeof !== "function"` 自检，`console.error` 点名缺失项（防 `1.3.2` 那类漏导出回归） |
| **DOM → record 映射先验类型** | `$0.dataset` 与 `record.id` / `record.resId` 的类型差异必须显式确认 |
| **`?debug=assets` + 强刷** | 判断"改动是否真的生效"的唯一可靠前提；看不到版本日志就不要再往下猜 |
| **改 SCSS 必须独立编译** | `npx sass --no-source-map <file> /tmp/out.css`（本模块 SCSS 无 `@import`，可独立编译） |
| **整份重写文件前先跑导出对照** | 见附录 B（脚本），漏导出是纯文本层面查不出来的 |

---

## 四、后续优化建议

### 4.1 流程改进（优先级最高，直接决定返工次数）

| 建议 | 具体做法 | 解决的问题 |
|------|----------|------------|
| **① 静默失效先建可观测性** | 需求涉及"交互触发"时，第一步不是写逻辑而是排**日志埋点**：资源是否加载 / 事件是否到达 / 数据是否存在 / 渲染是否执行 | 坑 ①②③ 全是"什么都不发生"，没有日志就只能猜 |
| **② 先读源码再改代码** | 本地保留 Odoo 源码（`~/Code/odoo`，19.0）；任何"框架为什么会这样"的疑问，先 `grep` 实现再动手；结论写进 `AGENTS.md`（含文件路径） | 坑 ①②③⑦⑧⑨⑬ 都可以靠这一步直接跳过 |
| **③ 一次只改一个可疑点** | 禁止"多管齐下"式修复；每个版本只动一处，并在 CHANGELOG 写清"这次验证的是什么假设" | 坑 ③（双绑定）就是多管齐下的反例 |
| **④ 交付必须带"验证清单 + 回滚方式"** | 每个版本末尾给出：需要 `-u` 吗？要不要重启？怎么确认生效（看哪行日志）？怎么回滚 | 坑 ② 的根因之一是我在交付说明里说"不需要 `-u`" |
| **⑤ 需求变化按"贯穿层"改** | 字段增删 = 后端 payload + 前端装配 + 模板 + i18n + 文档 + 验收标准，**一次改全**，并同步简化缓存键 / 清理死字段 | 避免"界面不显示但代码还在算"的死代码（`1.5.0` 的做法） |
| **⑥ 里程碑后写复盘（本文）** | 14 个版本的经验不落纸就会随对话丢失；复盘只写"为什么"和"下次怎么做" | 本次 9 个版本修同一个 bug |

### 4.2 工具与自动化

1. **把自校验脚本固化进仓库**（附录 B 已可直接用）：建议放 `tools/check_module.py`，覆盖
   ①命名导入 vs 导出 ②assets 双向一致（磁盘 ↔ manifest）③版本一致（manifest ↔ JS 邮戳，控制器应无手写版本号）
   ④po 重复 `msgid` + 应用列表元数据与 manifest 逐字符一致 ⑤JS / Python / XML 语法 ⑥源码残留中文（注释外）。
   - 挂到 **pre-commit**（或至少每次交付前手跑一次）；本次每次改动后跑它，实际拦住了 `1.3.2` 之后的同类风险与 `1.5.0` 的字段残留。
2. **SCSS 独立编译校验**：`npx --yes sass@<version> --no-source-map <file> /tmp/out.css`，无输出即通过——`min()/max()` 这类 Sass 内置函数冲突只有编译才暴露。
3. **浏览器端固定检查脚本（DevTools snippet）**：一键打印
   `[sale_product_hover]` 全链路日志筛选结果 + 当前模块版本 + 选中行的 `dataset.id` / `record.id` 类型，替代手工翻控制台。
4. **把"assets 文件清单"纳入交付检查**：改了 `__manifest__.py` 的 `assets` 段 → 自动在交付说明里标记"**必须 `-u` / 重启**"。
5. **建议给 Odoo 前端 patch 类改动准备一份"最小冒烟片段"**：`?debug=assets` 打开订单页 → 看 4 行日志 → 悬停 1 行 → 长按 1 次，总计 30 秒，可做成 checklist。

### 4.3 规范制定（建议上升到仓库级）

| 规范 | 内容 | 状态 |
|------|------|------|
| **禁止往 assets 新增文件** | 前端代码写进已登记文件；确需新增必须 `-u` / 重启并在交付说明写明 | 已写入根 `AGENTS.md` 前端规范 + 模块陷阱 17 |
| **版本号单一来源** | `__manifest__.py` 的 `version` 为唯一来源；后端用 `get_manifest()` 自动读取；前端保留一份**资源邮戳**（故意不同源，用于自证） | 本模块 `19.0.1.5.1` 落地，**建议推广到其他前端模块** |
| **前端模块加载期自检** | 跨模块命名导入的 helper 在加载期做 `typeof` 检查并点名缺失项 | 本模块已有，建议作为前端模块模板项 |
| **"字符串 id" 硬提示** | 凡涉及 Owl datapoint id（`data-id`）的代码，必须字符串比较；`resId` 与 `id` 不得混用 | 建议写入根 `AGENTS.md` 的前端通用坑 |
| **静默失效必修日志** | 任何"看起来该生效但没生效"的功能，交付前必须留下可区分的分段日志 | 建议写入根 `AGENTS.md` 交付标准 |
| **文档三件套同步时机** | 已由根 `AGENTS.md` 第 7 节规定；建议补一条"**新增第四个文档（如本文）时，在 README `后续维护` 与本文件头声明定位**" | 本文已按此执行；`1.6.0` 又补了 [`IMPLEMENTATION.md`](IMPLEMENTATION.md)（实现说明），四份文档的分工表见 `README.md` →「后续维护」 |

### 4.4 风险预防清单（同类需求可直接照做）

1. **DOM ↔ 数据映射**：任何"从 DOM 反查记录"的逻辑，先打印两侧 id 的**值与类型**；禁止 `Number()` 化来路不明的 id。
2. **事件委托**：需要"先于业务监听"时一律用捕获阶段；不要用不冒泡的 `mouseenter` / `mouseleave` 做 document 委托。
3. **overlay / popover 行为耦合**：涉及 `usePopover` / `useOverlay` 时，先确认 `open()` / `remove()` 是否同步触发回调，再决定状态写在 `open()` 之前还是之后。
4. **去重缓存**：必须有"请求成功但结果为空"的回退分支；必须有上限保护（本模块 2000 行）；必须是**非 reactive** 容器。
5. **跨端手势**：任何 `touch*` 交互都要显式处理浏览器补发的 `click` / `mouseover`；位移阈值与时间窗要可调（本模块集中在文件顶部常量）。
6. **Odoo 升级回归点**（升级 Odoo 版本时优先复核）：
   - `web/views/list/list_renderer` 的行模板（`t-att-data-id`、`t-on-mouseover.capture`）与 `props.list`（`records` / `editedRecord`）；
   - `@web/core/popover/popover_hook` 的 `usePopover` 选项与 `open()` 语义；
   - `@web/core/position` 的 `reposition()` 坐标基准；
   - `web.ListRenderer` 及其 sale / account 侧的自定义渲染器继承链；
   - `odoo.modules.module.get_manifest` 的返回形态（本项目用它读版本）。
7. **`?debug=assets` 的"假同步"风险**：它让 JS / SCSS 自动重建，容易掩盖 Python 未升级；因此**前端与后端都必须有版本自证**，不能只靠"看起来是新的"。

### 4.5 若继续演进（功能侧，按性价比排序）

| 想法 | 说明 | 成本 |
|------|------|------|
| 复用采购订单行（`purchase.order.line`） | 把 payload 装配抽象到共用 mixin；`TARGET_MODEL` 改为模型集合；模板按 `kind` 分支 | 中 |
| 卡片字段可配置 | 例如用 `ir.config_parameter` 决定是否显示某项（避免像 `1.5.0` 那样"改需求要改代码"） | 中 |
| 图片放大 / 多图预览 | 浮层内点击图片打开大图（复用 Odoo 的 `file_viewer`） | 低 |
| 大列表性能 | 虚拟滚动下按需预取（当前是"整页差集预取"，几十行内足够） | 高 |
| 移动端改为底部抽屉 | 窄屏下长按弹出 bottom sheet 而非浮层，阅读体验更好（Odoo 自带 `bottom_sheet` 组件） | 中 |

---

## 附录 A：版本一览（14 个版本）

| 版本 | 日期 | 一句话 |
|------|------|--------|
| `19.0.1.0.0` | 09-12 | 首版：接口批量装配 + 前端 patch + 缓存（含本单单价 / 数量） |
| `19.0.1.0.1` | 09-13 | 触发链路加固：document 级委托、不抢焦点、字段过滤、异常兜底 |
| `19.0.1.0.2` | 09-13 | 事件双绑定 + info 级诊断日志 + 版本自证（**后证明方向错误**） |
| `19.0.1.1.0` | 09-14 | 重做触发链路（捕获阶段 + `data-id` 归属、去双绑定）；补规格 / 数量 / 单价；触屏长按 + 响应式 |
| `19.0.1.1.1` | 09-14 | **修掉真正根因**：`data-id` 是字符串却被 `Number()` 化 |
| `19.0.1.2.0` | 09-14 | 浮层跟随鼠标（自接管定位）+ 屏蔽行内原生 tooltip |
| `19.0.1.3.0` | 09-15 | 新增（未保存）行也能预览（先走"草稿"方案） |
| `19.0.1.3.1` | 09-15 | 修复"接口无数据即永久失效"+ 加前后端版本自证 |
| `19.0.1.3.2` | 09-15 | 修复缓存模块漏导出 `getLineHoverPayload` 的回归 |
| `19.0.1.3.3` | 09-15 | 空 `line_ids` 探测 + 启动自检，区分"服务端没升级"与数据 / 权限问题 |
| `19.0.1.4.0` | 09-15 | 新行改为**前端直接查产品**（不再依赖服务端升级） |
| `19.0.1.4.1` | 09-15 | 修复"新增 assets 文件导致模块加载失败"（并入已有文件） |
| `19.0.1.5.0` | 09-15 | 按需求**移除浮层里的数量与单价**（两条取数路径同步收窄） |
| `19.0.1.5.1` | 09-15 | 后端版本改为自动读 `__manifest__.py`（版本只剩 manifest + JS 两处） |
| `19.0.1.6.0` | 09-16 | 按需求**移除浮层里的产品售价**（两条取数路径同步收窄，前端不再需要 `formatMonetary` / 公司币种） |

## 附录 B：模块自校验脚本（可直接复用）

```bash
cd <odoo-addons 根目录> && python3 - <<'PY'
import re, pathlib, ast, collections, textwrap

MODULE = "sale_product_hover"

# ① 命名导入 vs 导出（整份重写 JS 时的回归防线）
EXPORT_RE = re.compile(r'^export\s+(?:async\s+)?(?:function|const|let|var|class)\s+(\w+)', re.M)
EXPORT_LIST_RE = re.compile(r'^export\s*\{([^}]*)\}', re.M)
IMPORT_RE = re.compile(r'import\s*\{([^}]*)\}\s*from\s*"(\.[^"]+)"', re.S)
bad = []
for js in sorted(pathlib.Path(".").glob(f"{MODULE}/static/src/**/*.js")):
    for names, target in IMPORT_RE.findall(js.read_text(encoding="utf-8")):
        tp = (js.parent / target).with_suffix(".js")
        if not tp.exists():
            bad.append(f"{js}: 目标不存在 {target}"); continue
        t = tp.read_text(encoding="utf-8")
        have = set(EXPORT_RE.findall(t))
        for grp in EXPORT_LIST_RE.findall(t):
            have |= {n.strip().split(" as ")[-1].strip() for n in grp.split(",") if n.strip()}
        want = {n.strip().split(" as ")[0].strip() for n in names.split(",") if n.strip()}
        if want - have:
            bad.append(f"{js} ← {target}: 未导出 {sorted(want - have)}")
print("① 导入导出问题:", bad or "无")

m = ast.literal_eval(pathlib.Path(f"{MODULE}/__manifest__.py").read_text(encoding="utf-8"))

# ② assets 双向一致（防"新增文件忘了 -u"与"文件删了还登记"）
listed = {p for paths in m["assets"].values() for p in paths}
on_disk = {str(p) for p in pathlib.Path(f"{MODULE}/static").rglob("*") if p.is_file()}
static = {p for p in on_disk if p.endswith((".js", ".xml", ".scss"))}
print("② assets 未登记:", sorted(static - listed) or "无", "| 登记但缺失:", sorted(listed - on_disk) or "无")

# ③ 版本一致：manifest 为唯一来源；控制器不得有手写版本号
js = pathlib.Path(f"{MODULE}/static/src/js/product_hover_list_patch.js").read_text(encoding="utf-8")
ctrl = pathlib.Path(f"{MODULE}/controllers/product_hover_controller.py").read_text(encoding="utf-8")
js_v = re.search(r'MODULE_VERSION = "([^"]+)"', js).group(1)
print("③ manifest:", m["version"], "| JS 邮戳:", js_v, "=>", "一致" if m["version"] == js_v else "不一致!")
assert 'get_manifest("sale_product_hover")' in ctrl and not re.search(r'MODULE_VERSION\s*=\s*"19\.', ctrl), "控制器版本写法不合规"

# ④ po：重复 msgid + 应用列表元数据与 manifest 逐字符一致
s = open(f"{MODULE}/i18n/zh_CN.po", encoding="utf-8").read()
ids = ["".join(re.findall(r'"((?:[^"\\]|\\.)*)"', e)) for e in re.findall(r'^msgid ((?:"(?:[^"\\]|\\.)*"\s*)+)', s, re.M)]
print("④ po 条目:", len(ids), "| 重复:", [k for k, v in collections.Counter(ids).items() if v > 1] or "无")
KEYS = {"shortdesc": "name", "summary": "summary", "description": "description"}
found = set()
for b in s.split("\n\n"):
    mm = re.search(r"^#: model:ir\.module\.module,(\w+):base\.module_(\w+)$", b, re.M)
    if not mm: continue
    key = mm.group(1); found.add(key)
    raw = re.search(r'^msgid ((?:"(?:[^"\\]|\\.)*"\s*)+)', b, re.M).group(1)
    got = re.sub(r"\\(.)", lambda x: {"n": "\n", "t": "\t"}.get(x.group(1), x.group(1)),
                 "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', raw)))
    want = textwrap.dedent(m[KEYS[key]]) if key == "description" else m[KEYS[key]]
    assert got == want, f"{key} msgid 与 manifest 不一致"
assert set(KEYS) == found
print("④ apps metadata ok")
PY
# ⑤ 语法：JS / Python / XML（SCSS 另跑 sass）
cd sale_product_hover && for f in static/src/js/*.js; do cp "$f" /tmp/chk.mjs && node --check /tmp/chk.mjs || echo "JS FAIL $f"; done \
  && python3 -m py_compile models/*.py controllers/*.py && echo "PY OK" \
  && python3 -c "
import glob, xml.dom.minidom
for f in glob.glob('static/**/*.xml', recursive=True): xml.dom.minidom.parse(f)
print('XML OK')"
```

## 附录 C：冒烟验证清单（30 秒版）

```bash
odoo -d <db> -u sale_product_hover --stop-after-init    # 改了 Python / manifest 时必须；只改 JS/XML/SCSS 时可省
```

1. **强刷浏览器**（`Ctrl+Shift+R`），用 `?debug=1` 或 `?debug=assets` 打开订单页；
2. 控制台第 1 行应为 `[sale_product_hover] assets loaded (19.0.1.6.0)`；
3. 紧接着 `self-check: assets 19.0.1.6.0, server 19.0.1.6.0 (ok)`；
4. 列表加载时 `prefetch sale.order.line: N saved / M new line(s)` + `payload: requested … received …`；
5. 悬停订单行：`hover row …` → `popover opened …`，浮层只剩**可用库存**一项数值
   （**无数量、无单价、无产品售价**）；服务类产品的明细表整块不出现；
6. 触屏（DevTools 设备模拟）长按：弹浮层、不打开记录、滚动不弹出；
7. 回归：点击进入 / 内联编辑 / 勾选 / 删除照旧；采购行、发票行无浮层；
8. 切成 `zh_CN` 复核标签为「可用库存」。

---

## 许可证

LGPL-3
