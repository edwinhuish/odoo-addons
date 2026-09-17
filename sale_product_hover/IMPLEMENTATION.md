# 订单行产品悬浮卡 · 实现说明

> **文档定位**：本模块的**实现说明书**（architecture / data flow / 核心要点 / 难点 / 坑点速查）。
> 面向需要**读懂并改动代码**的维护者；只关心用法的看 [`README.md`](README.md)。
>
> 与其余文档的分工（四件套，避免互相重复）：
>
> | 文档 | 回答什么 | 什么时候看 |
> |------|----------|-----------|
> | [`README.md`](README.md) | 怎么用：功能、字段、安装、验证清单 | 使用 / 验收 |
> | [`CHANGELOG.md`](CHANGELOG.md) | 改了什么：逐版本「变更 / 影响 / 文档」 | 升级前 |
> | [`AGENTS.md`](AGENTS.md) | 不能破坏什么：L1 约束 + L2 陷阱档案 + 文件职责 | 动手改之前 |
> | **本文** | 为什么这么写：架构、数据流、核心要点、难点、坑点（现象 / 原因 / 规避） | 读懂实现、排查问题 |
> | [`RETROSPECTIVE.md`](RETROSPECTIVE.md) | 走弯路的过程复盘与方法论沉淀 | 复盘 / 方法论 |
>
> **当前版本**：`19.0.1.6.0`（与 `__manifest__.py` 一致）　**状态**：**已完成（T-014，2026-09-17 归档）**；
> 验收记录见 [`CHANGELOG.md`](CHANGELOG.md) →「验收记录（T-014）」，验证 / 回归清单见 [`README.md`](README.md)。

---

## 一、架构总览

### 1.1 分层与文件职责

```text
┌──────────────────────── 浏览器 ────────────────────────┐
│  product_hover_list_patch.js   ← 触发层（patch ListRenderer） │
│    · document 捕获阶段事件委托（mouse / touch）                │
│    · 行归属判定（data-id 反查）· 延迟开 / 关 · 编辑态避让        │
│    · 自接管浮层定位（跟随鼠标 / 越界翻侧）                      │
│            │ 预取               │ 打开浮层                    │
│            ▼                    ▼                            │
│  product_hover_cache.js      product_hover_card.js            │
│    · 两条取数路径 + 模块级缓存     · 纯展示组件（OWL）           │
│    · 版本自证 / 失败诊断           · 图片降级、库存文案拼接       │
│            │                           │                     │
│            │ rpc（仅已保存行）           ▼                     │
│            │                     product_hover_templates.xml   │
│            │                     product_hover.scss            │
└────────────┼─────────────────────────────────────────────────┘
             ▼  POST /sale_product_hover/payload
┌──────────────────────── 服务端 ────────────────────────┐
│  controllers/product_hover_controller.py                       │
│    · auth="user"、不 sudo · 回显 __server_version · 异常兜底     │
│            ▼                                                   │
│  models/sale_order_line.py                                     │
│    · _get_product_hover_payload() → _build_hover_payload()      │
│    · _get_hover_specifications()（批量拼变体规格）               │
└────────────────────────────────────────────────────────────────┘
```

| 文件 | 职责 | 关键入口 |
|------|------|----------|
| `static/src/js/product_hover_list_patch.js` | 触发与交互层 | `patch(ListRenderer.prototype, {...})`、`_getProductHoverRecord()`、`_openProductHover()`、`_positionProductHover()` |
| `static/src/js/product_hover_cache.js` | 数据层（两条路径 + 缓存 + 诊断） | `prefetchLineHoverPayload()`、`prefetchDraftHoverPayload()`、`getLineHoverPayload()`、`ensureServerDiagnostics()` |
| `static/src/js/product_hover_card.js` | 展示组件 | `ProductHoverCard`、`onHandText`、`onPointerLeave` |
| `static/src/xml/product_hover_templates.xml` | 浮层 QWeb 模板 | `sale_product_hover.ProductHoverCard` |
| `static/src/scss/product_hover.scss` | 样式（统一 `.o_sph_` 前缀 + 窄屏媒体查询） | — |
| `models/sale_order_line.py` | 已保存行的 payload 装配 | `_get_product_hover_payload()` / `_build_hover_payload()` / `_get_hover_specifications()` |
| `controllers/product_hover_controller.py` | 内部 JSON 接口 | `sale_product_hover_payload()` |
| `i18n/zh_CN.po` | 中文译文（含应用列表元数据） | — |

> **assets 只有 5 个静态文件**，前端代码请写进已登记的文件：新增文件需要服务端重读 manifest
> （`-u` / 重启）才会进 bundle，否则浏览器报 `modules … have not been defined`，整个模块加载失败（见坑 #2）。

### 1.2 两条取数路径（本模块最关键的设计）

| | **已保存行** | **未保存的新行** |
|---|---|---|
| 触发时机 | 行已在库里 | 刚新增、还没保存（`record.resId` 为空） |
| 缓存键 | 数据库 id（数字，来自 `record.resId`） | Owl datapoint id（字符串 `"datapoint_42"`，来自 `record.id`） |
| 取数方式 | 接口 `POST /sale_product_hover/payload`（`line_ids` 批量） | 前端直接 `orm.searchRead("product.product")`（**标准 ORM**，任何后端版本可用） |
| 装配位置 | 服务端 `_build_hover_payload()`，库存用 `formatLang` | 前端 `buildProductHoverPayload()`，库存用 `formatFloat` |
| 是否依赖服务端升级 | **是**（要装新的 Python） | **否** |
| 为什么这样 | 行在库里，按 id 查最省 | 行**根本不在库里**，按行 id 反查必然查不到 |

两条路径产出**同一种 payload**，卡片组件与模板不关心数据从哪来。

### 1.3 payload 字段（`19.0.1.6.0` 最终口径）

| 字段 | 说明 |
|------|------|
| `line_id` | 该条数据的键（已保存行 → 行 id；新行 → datapoint id） |
| `product_id` | 产品 id |
| `name` | 产品显示名（去掉 `[参考号] ` 前缀） |
| `reference` | 型号（`default_code`） |
| `specification` | 规格：变体属性值 `display_name` 用 `", "` 连接 |
| `image_url` | `/web/image/product.product/<id>/image_256` |
| `description` | 销售描述（`description_sale`） |
| `qty_available_text` | 可用库存（已格式化字符串，`Product Unit` 精度） |
| `available_uom_name` | 库存计量单位名 |

> **没有任何价格字段**（`19.0.1.5.0` 下线数量 / 单价，`19.0.1.6.0` 下线产品售价）。
> 可用库存为空时模板**整块不渲染** `dl.o_sph_fields`（见坑 #15）。

### 1.4 运行时序

```text
[资源加载] product_hover_list_patch.js
           ├─ setClientVersion(MODULE_VERSION)           ← 前端资源邮戳
           └─ console.info("assets loaded (x.y.z)")
[列表挂载/更新] onMounted / onPatched
           └─ _prefetchProductHover()
                ├─ ensureServerDiagnostics()  → "self-check: assets X, server Y"
                ├─ 已保存行 → prefetchLineHoverPayload([resId…])  → rpc 接口 → payloadByKey
                └─ 新行     → prefetchDraftHoverPayload(orm, [{key, product_id}…])
                                                          → searchRead 产品 → payloadByKey
[悬停]     mouseover（document 捕获）→ 行归属 → 300ms → _openProductHover(row)
           ├─ 缓存命中则**不发请求**
           └─ popover.open(row, {payload}) → onPositioned → _positionProductHover(光标)
[跟随]     mousemove → rAF 合帧 → 改写 left/top（指针进入浮层后停止跟随）
[关闭]     mouseout 200ms 延迟 → popover.close() → onClose → _resetProductHover()
[触屏]     touchstart → 500ms → 吃掉紧随的 click → 打开；touchmove >10px 取消；touchend 后 800ms 忽略补发 mouse 事件
```

---

## 二、核心要点（为什么这么写）

| # | 要点 | 做法 | 为什么（源码依据） |
|---|------|------|--------------------|
| 1 | **patch `ListRenderer.prototype`，不继承行模板** | `patch(ListRenderer.prototype, {...})` | 报价单 / 销售订单表单里的订单行走的是 sale 自定义行模板（`sale.ListRenderer.RecordRow` ← `account.SectionAndNoteListRenderer.RecordRow` ← `web.ListRenderer.RecordRow`），继承 `web.ListRenderer.RecordRow` 在该处**不会生效**；补丁作用于渲染器实例，对其所有子类一致生效，且不必改任何视图 arch |
| 2 | **document 级捕获阶段事件委托** | `useExternalListener(document, "mouseover", h, {capture:true})` | `mouseenter` / `mouseleave` **不冒泡**，无法委托，故用 `mouseover` / `mouseout`；行模板上挂着 `t-on-mouseover.capture` 且某些状态会 `stopPropagation`，捕获阶段先于它们触发 |
| 3 | **行归属用 `data-id` 反查记录** | `props.list.records.find(r => String(r.id) === row.dataset.id)` | 比 `this.el.contains()` 稳：不依赖渲染器根节点（自定义渲染器的 `t-ref="root"` 不可靠），且天然排除其他模型列表的行。**`data-id` 是字符串** `"datapoint_N"`（`model/relational_model/utils.js` 的 `getId()`），`Number()` 化会得到 `NaN` → 静默失效（坑 #1） |
| 4 | **键的双轨制** | `record.resId \|\| record.id` | 已保存行用数据库 id（数字），新行用 datapoint id（字符串），两者不冲突，新行不必等落库就能预览 |
| 5 | **新行不碰订单** | 上下文只有 `{key, product_id}`，前端按 `product_id` 读产品 | 行未落库 → 服务端按行 id 反查必然查不到；而卡片展示的**全是产品侧信息**（且不含价格），与订单无关。逻辑更短，还不依赖服务端升级 |
| 6 | **卡片只展示产品侧信息** | 字段见 1.3；两条路径同步收窄 | "产品详情"定位：看产品长什么样、什么规格；价格（行数量 / 单价 / 售价）在订单行与产品表单上本来就看得见 |
| 7 | **非 reactive 模块级缓存** | 模块级 `Map` / `Set`，不挂 reactive 对象 | 挂到 reactive 对象会触发 Owl 重渲染 / 重载循环（同 `product_card_view` 的 P1 踩坑）；另设上限 `MAX_CACHED_LINES = 2000` 防内存无界增长 |
| 8 | **"已请求"标记必须有回退分支** | 响应为空 / 抛错时把 id 从 `requestedLineIds` 删掉 | 否则"接口成功但没数据"的行会**永久失效且不报错**（坑 #9） |
| 9 | **浮层位置自己接管** | `_positionProductHover()` 直接写 `left/top` | Odoo 的 `reposition()` 把浮层设成 `position: fixed` 并写 `left/top`（视口坐标），所以可以直接改写；每次 Odoo 重定位都会回调 `onPositioned`，在那里再套用一次光标位置 |
| 10 | **状态在 `open()` 之后补写** | `popover.open(...)` 之后重新赋值 `_productHoverRowEl` / `_productHoverPointer` | `open()` 内部先 `close()` 旧浮层，而 `overlay.remove()` **同步**触发 `onClose` → 父级状态被清空（坑 #7） |
| 11 | **编辑态避让只针对已保存行** | `editedRecord === record && record.resId` | `Record.isInEdition` 对 `!resId` 恒为真（`this.config.mode === "edit" \|\| !this.resId`），新行一加进列表就是 `editedRecord` → 一刀切会让新增行永远没预览，还会连带挡掉其它已保存行（坑 #8） |
| 12 | **触屏：显式处理补发事件** | 一次性 `click` 捕获吃掉；`touchend` 后 800ms 忽略 mouse 事件；`touchmove` >10px 取消 | 长按后浏览器会补发 `click`（会打开记录），抬手还会补发一轮 `mouseover`（被当成悬停 → "点一下弹两次"） |
| 13 | **屏蔽行内原生 tooltip** | 在更外层的 `document` 捕获阶段 `mouseenter` 上 `stopPropagation()`，**只对确实有浮层数据的行** | Odoo 的 tooltip 服务挂在 `document.body` 的捕获阶段 `mouseenter`；在更外层拦截才有效，且只拦自己的行，不影响其他元素 |
| 14 | **版本单一来源 + 双端自证** | `__manifest__.py` 的 `version` 为唯一来源；控制器 `get_manifest()` 自动读；JS 保留一枚资源邮戳 | 两者**故意不同源**：不一致就说明"浏览器加载的是旧资源 / 服务端 Python 没升级"。`?debug=assets` 下 JS / SCSS 按 mtime 自动重建、Python 必须 `-u` 且**重启进程**，极易出现"前端新、后端旧"（坑 #16） |
| 15 | **接口参数只增不改、且旧后端必须能容忍** | 只发 `line_ids`；服务端版本用**空 `line_ids` 探测** | 旧后端遇到不认识的参数会整批 TypeError；版本探测若带新参数则连"旧后端"这个结论都拿不到（坑 #13） |
| 16 | **i18n 与展示字段同步增减** | 改展示字段 = 改后端 payload + 前端装配 + 模板 + `i18n/zh_CN.po` + 文档 + 验收标准 | 否则 po 里会留下永远匹配不到的孤儿条目（坑 #17） |

---

## 三、实现与联调难点

### 难点 1：现象是「什么都不发生」——没有报错、没有请求、没有浮层

- **难在哪**：没有异常栈可比对，唯一线索是"用户说没反应"。第一版把监听挂在渲染器根节点 `t-ref="root"` 上，而订单行用的是自定义渲染器，根节点 ref 不可靠 → 监听整段被跳过。
- **解法**：把「不报错」拆成**可观测的阶段**，每段一行 info 日志：
  `assets loaded`（资源）→ `prefetch`（列表识别）→ `payload: requested N, received M`（接口数据）→ `hover row`（悬停命中）→ `popover opened`（渲染）。
- **结果**：日志一出来就定位——`prefetch` / `payload` 都正常但**完全没有 `hover row`**，问题被压缩到"事件收到但被判定为不属于本列表"这一段，最终查明是 `data-id` 类型。
- **沉淀**：**静默失效必须先建可观测性**，再动手改逻辑。

### 难点 2：需求口径在过程中变了两次，且都是「减法」

- **难在哪**：需求从「名称 / 规格 / **数量** / **单价** / 图片」→ 中途以"产品详情"为准去掉数量与单价（`19.0.1.5.0`），随后连产品售价也去掉（`19.0.1.6.0`）。只改模板不改取数链路，会留下"接口还在算、界面不展示"的死代码。
- **解法**：把「展示字段」当**贯穿层**——一次改动同时收窄后端 payload、前端装配、模板、i18n、文档与验收标准；缓存签名从「产品\|数量\|单位\|单价\|币种」简化为 `product_id`（`19.0.1.5.0`）→ 再去掉价格相关取数与格式化（`19.0.1.6.0`）。
- **结果**：`1.5.0` 顺带修掉一个隐藏缺陷——原「单价 = 售价则不重复展示售价」判据在单价行移除后，会让两者相等的产品**一个价格都不显示**；`1.6.0` 之后价格相关的取数 / 格式化代码**全部清零**。

### 难点 3：框架内部行为不可见（Odoo 前端）

- **难在哪**：一半的坑在 Odoo 内部：list 行模板的捕获监听、`reposition()` 的坐标基准、`overlay.remove()` 同步调 `onRemove`、tooltip 服务挂载位置、`Record.isInEdition` 对 `!resId` 恒为真、`get_manifest()` 的返回形态。
- **解法**：立规矩——**先读源码再改代码**（`docker exec odoo19 grep …` 或 `task odoo-src`，见根 `AGENTS.md` 第 2 节），结论写进 `AGENTS.md` 陷阱档案（含文件路径）。
- **结果**：`data-id` 类型、`open()` 先 `close()`、`get_manifest()` 返回空 dict 等关键结论都来自源码，而不是试错。

### 难点 4：让浮层「跟着鼠标」而不是「贴着行」

- **难在哪**：`usePopover` 的锚点是行，定位由 Odoo 接管；既要跟随鼠标，又不能在 Odoo 每次重定位（挂载 / 滚动 / 缩放）后丢掉光标位置。
- **解法**：确认 `reposition()` 写的是 `position: fixed` + `left/top` → 用 `mousemove` + `requestAnimationFrame` 合帧改写；再用 `onPositioned` 回调在 Odoo 重定位之后重新套用；并先清掉 Odoo 可能写下的 `maxHeight` / `overflowY`。
- **结果**：`19.0.1.2.0` 实现；`holdOnHover: true` 让指针进入浮层后停止跟随，便于阅读。

### 难点 5：未保存的新行没有数据来源（早期走了弯路）

- **难在哪**：行还没落库，按行 id 反查必然失败；`1.3.0`~`1.3.3` 曾把新行"伪装成草稿"发给接口，导致既要改服务端、又要升级后端，恰好撞上"前端已更新、后端没升级"。
- **解法**：回到需求本质——卡片要展示的全是产品侧信息 → 直接按 `product_id` 用标准 ORM 读产品，行上的取值一个都不需要。
- **结果**：`19.0.1.4.0` 起新行路径**不依赖服务端升级**；`19.0.1.5.0` 移除数量 / 单价后进一步简化，上下文只剩 `{key, product_id}`。

### 难点 6：多端交互互相打架（触屏）

- **难在哪**：触屏没有 hover，只能长按；长按后浏览器补发 `click`（打开记录）、抬手补发 `mouseover`（再次触发悬停）。
- **解法**：一次性 `click` 捕获吃掉紧随的点击；`touchstart` 置"触摸中"标记，手势结束后 800ms 内忽略 mouse 事件；`touchmove` 位移 >10px 视为滚动取消。
- **结果**：`19.0.1.1.0` 起长按 / 滚动 / 点击三种意图互不干扰。

### 难点 7：联调部署的「前端新、后端旧」黑洞

- **难在哪**：`?debug=assets` 下 JS / SCSS 按文件 mtime 自动重建（不需要 `-u`），而 Python 必须 `-u` **且重启进程**；症状依然是"没反应"，极易误判为代码 bug。
- **解法**：**版本自证**——接口回显 `__server_version`，前端加载时打印资源邮戳，页面打开时输出一行 `self-check: assets X, server Y`；不一致就明确给出该做什么（`-u` + 重启 + 强刷）。
- **结果**：`19.0.1.5.1` 起后端版本自动读 manifest，版本维护从三处降到两处；这类问题从"猜"变成"看一行日志"。

### 难点 8：接口必须向后兼容旧后端

- **难在哪**：升级窗口内，浏览器里的 JS 是新版本、服务端 Python 可能还是旧版本。任何"顺手加个参数"都会让旧后端整批报错。
- **解法**：接口只认 `line_ids`；版本探测用**空 `line_ids`**（新旧后端都能成功返回，只在新后端多一个 `__server_version`）；新行需求改走前端直读产品，不再给接口加参数。
- **结果**：`19.0.1.3.3` 起可干净区分「服务端没升级」与「业务上确实没有数据 / 没权限」。

---

## 四、坑点档案（现象 → 原因 → 规避）

> 排查曲折度：★★★ = 花了 3 个以上版本。完整技术细节另见 [`AGENTS.md`](AGENTS.md) → 踩坑档案。

| # | 版本 | 现象（一句话） | 原因分析 | 规避方案 | 曲折度 |
|---|------|----------------|----------|----------|--------|
| 1 | `1.0.0`~`1.1.0` | 悬停完全无反应，**连 `hover row` 都没有** | 行 `data-id` 是字符串 `"datapoint_42"`，被 `Number()` 成 `NaN` → 行归属恒失败；预取走的是 `resId`，所以数据链路看起来完全正常 | 两侧 `String()` 后比较（对齐官方 `kanban_renderer.js`）；任何"DOM ↔ record"映射先打印两侧**值与类型** | ★★★ |
| 2 | `1.4.0`→`1.4.1` | `modules … have not been defined: ['@sale_product_hover/js/product_hover_product']`，模块整个没加载 | 往 `assets` **新增文件**，而运行中的进程内存里是旧 manifest（`?debug=assets` 只按 mtime 重建内容、不重读 manifest） | 代码写进**已登记**的 5 个文件；确需新增文件必须 `-u` / 重启，并在交付说明写明 | ★★★ |
| 3 | `0.1` / `0.2` | 悬停无反应，但接口 200、数据完整 | 监听挂在自定义渲染器不可靠的根节点 ref；冒泡阶段委托被行内 `stopPropagation` 掐断 | document 级**捕获阶段**委托；不用 `this.el.contains()` 判归属 | ★★★ |
| 4 | `0.2`→`1.1.0` | 关掉又重开、日志重复、行为不可预测 | **事件双绑定**（document + 根元素两套监听）互相干扰 | 只保留**一套**监听；"没触发"要找根因，不要加第二套兜底 | ★★ |
| 5 | `1.1.1` 前 | 浮层弹出时同时冒出行内黑色原生 tooltip | Odoo tooltip 服务挂在 `document.body` 捕获阶段 `mouseenter` | 在更外层 `document` 捕获阶段，**只对有浮层数据的行** `stopPropagation()` | ★★ |
| 6 | `1.1.1` 前 | "有显示但没跟随鼠标" | popover 定位锚在行上，未接管 `left/top` | `_positionProductHover()` + `onPositioned` 兜底重套 | ★★ |
| 7 | `1.1.0` 期间 | 同一行内轻移鼠标，浮层反复关闭重开 | `open()` 内部先 `close()` 旧浮层，`overlay.remove()` **同步**触发 `onClose` → 父级状态被清空 | 行 / 光标状态在 `open()` **之后**补写；用 `getPopoverForTarget(row)` 跳过重复打开 | ★★ |
| 8 | `1.3.0` 前 | 新增行永远没有预览；且有一条新行时其它已保存行也被挡 | `Record.isInEdition` 对 `!resId` 恒为真，编辑态避让一刀切 | 避让条件收敛为 `editedRecord === record && record.resId` | ★★ |
| 9 | `1.3.0`→`1.3.1` | 选了产品后悬停新行无数据、无请求、无报错（**永久失效**） | "已请求"标记在发请求前写入，响应里没有该行数据时**未回退** | 空结果必须回退标记；失败给可操作的 `console.error` | ★★ |
| 10 | `1.3.2` | `Uncaught TypeError: getLineHoverPayload is not a function` | 整份重写缓存模块时**漏了一个导出**（导入侧仍在引用） | 加载期 `typeof` 自检 + 交付前跑「命名导入 vs 导出」脚本（附录 B / 根 `AGENTS.md` 第 6 节） | ★★ |
| 11 | `1.1.0` 前后 | SCSS 报 `SCSS error dialog`，`web.assets_web` **整份 CSS 编译失败** | `min(20rem, calc(100vw - 1.5rem))` 被 Sass 当内置函数求值，`calc()` 不是数字 | 拆成 `width` + `max-width: calc(...)`；改 SCSS 必跑 `npx sass` 独立编译 | ★★ |
| 12 | `1.1.0` 设计期 | 触屏长按同时打开了记录；或点一下闪出浮层 | 长按后浏览器补发 `click`；抬手后补发 `mouseover` 被当成悬停 | 一次性 `click` 捕获吃掉 + 800ms mouse 宽限 + 位移 >10px 取消 | ★ |
| 13 | `0.1` | 某环境下接口整体失败（前端只表现为"没有浮层"） | 直接 `read()` 固定字段列表，字段缺失即 `Invalid field` 整批抛错；且给旧后端传了它不认识的参数 | 先按模型实际字段过滤再 `read()`；控制器 try/except + 服务端日志；**不新增旧后端不认识的参数** | ★ |
| 14 | 设计期（预防） | 指针移入浮层立即消失；关闭后回到行上不重开；异步返回时行已切换 | `mouseenter` / `mouseleave` 不冒泡无法委托；关闭未判断"是否移入浮层"；异步回调未复核当前行 | 统一用 `mouseover` / `mouseout`；关闭前判断 relatedTarget；异步返回后复核 `row === _productHoverRowEl && row.isConnected` | 预防 |
| **15** | `1.6.0` | 删掉常驻的「产品售价」行后，**服务类产品的浮层里出现一条空的分隔线**（明细表有 `border-top` + 上间距，却没有任何内容） | `dl.o_sph_fields` 原本靠"产品售价常驻"保证非空；售价移除后，不跟踪库存的产品没有 `dt/dd`，容器整块为空但样式照常渲染 | `<dl class="o_sph_fields" t-if="onHandText">`：**删行时顺手检查容器是否可能为空** | ★ |
| **16** | 联调期 | `?debug=assets` 下前端看着是新的，浮层却没有数据 | JS / SCSS 按 mtime 自动重建（不需要 `-u`），Python 必须 `-u` **且重启进程** | 看那行 `self-check: assets X, server Y`；后端版本自动读 manifest，版本维护只有两处 | ★ |
| **17** | `1.5.0` / `1.6.0` | po 里留下永远匹配不到的孤儿术语（`Quantity` / `Unit Price` / `Sales Price`） | 需求"做减法"时只改了模板，没同步下线 i18n 术语 | 展示字段增减 = 后端 payload + 前端装配 + 模板 + `i18n/zh_CN.po` + 文档 + 验收标准，**一次改全** | ★ |

### 4.1 详录：三个最贵的坑

#### ① 悬停恒失败：`data-id` 被当成数字（`19.0.1.0.0` ~ `19.0.1.1.0`）

**现象**：

```text
[sale_product_hover] prefetch sale.order.line: 1 saved line(s)
[sale_product_hover] payload: requested 1, received 1
```

**完全没有 `hover row`**；鼠标停在订单行上毫无反应，也不报错。

**排查**：① 资源已加载（有 `assets loaded`）→ 排除；② document 捕获阶段打点，事件到了 → 排除；③ 卡在"行归属判定"；④ 读源码 `model/relational_model/utils.js`：

```js
export function getId(prefix = "") { return `${prefix}_${++nextId}`; }   // → "datapoint_42"
```

而我们的代码是 `Number(row.dataset.id)` → `NaN` → 判定失败直接 `return null`。

**根因**：行 `data-id` 是 **Owl datapoint id（字符串）**，`record.resId` 才是数据库 id（数字）。**预取走 `resId`，所以数据链路完全正常**，极具迷惑性。

**修法**：按字符串比较（对齐 Odoo 官方 `kanban_renderer.js`）：

```js
return (this.props.list.records || []).find((r) => String(r.id) === row.dataset.id) || null;
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

**根因**：assets 的文件清单来自 manifest，而**运行中的 Odoo 进程内存里是旧 manifest**；`?debug=assets` 只按文件 mtime 重建 bundle **内容**，不会重读 manifest。
"改 JS 只需强刷浏览器"这条**只对"改已有文件的内容"成立**。

**修法**：把新行取数逻辑**并入已登记的 `product_hover_cache.js`**，删掉新文件、从 assets 移除，清单回到原来 5 项 → 只需强刷。

**规避**：已写成硬约定（根 `AGENTS.md` 前端规范 + 本模块 `AGENTS.md` 陷阱 17）：**不要往 assets 新增文件**。

#### ③ 猜根因的代价：两版无效补丁（`19.0.1.0.1` / `0.2`）

**过程**：第一版失效后，在**没读框架源码**的情况下连续加了两层"保险"：document 级委托 + 根元素兜底（**事件双绑定**）→ 同一事件被两套监听处理，行为更难预测；真正的原因一个都没碰到。

**教训（写进流程）**：

1. 静默失效必须**先建立可观测性**（分段日志），再改逻辑；
2. 涉及框架行为的分歧，**先 `grep` 框架源码**，把"猜测"换成"依据"；
3. 不能用"再加一套兜底"对付"没触发"——会把"没触发"变成"触发两次 + 状态错乱"；
4. 一次只改**一个**可疑点，否则修好了也不知道是哪处起作用。

---

## 五、维护与扩展指引

### 5.1 改动的"贯穿层"清单（照此逐项走，避免死代码与孤儿术语）

| 改动类型 | 必改位置 |
|----------|----------|
| **增减浮层字段** | ① `models/sale_order_line.py` 的 `read_fields` + payload ② `product_hover_cache.js` 的 `PRODUCT_FIELDS` + `buildProductHoverPayload()` ③ `product_hover_templates.xml` ④ `i18n/zh_CN.po`（新增 / 下线术语）⑤ `README.md` 字段表 ⑥ 验证清单与 `TODO.md` 验收标准 |
| **调交互参数**（延迟 / 距离 / 偏移） | `product_hover_list_patch.js` 顶部常量（`OPEN_DELAY` / `CLOSE_DELAY` / `TOUCH_OPEN_DELAY` / `TOUCH_MOVE_TOLERANCE` / `POINTER_OFFSET_*` / `VIEWPORT_MARGIN`） |
| **改样式** | `product_hover.scss`（选择器统一 `.o_sph_` 前缀），改完跑 `npx sass` 独立编译 |
| **扩大适用模型**（如采购行） | 把 payload 装配抽到共用 mixin；`TARGET_MODEL` 改模型集合；确认该模型列表同样渲染 `tr.o_data_row[data-id]` |
| **提版本** | 只改 `__manifest__.py` 的 `version` 与 `product_hover_list_patch.js` 的 `MODULE_VERSION`（控制器自动读 manifest）；同步 `CHANGELOG.md` / `README.md` / `AGENTS.md` / 根三件套 |
| **只改 JS / XML / SCSS** | 不需要 `-u`，但**必须强刷浏览器**；改了 Python / manifest 才需要 `-u` **并重启进程** |

### 5.2 交付前自校验（可直接复用，脚本见 `RETROSPECTIVE.md` 附录 B）

- ① 命名导入 vs 导出（防 `1.3.2` 那类漏导出回归）
- ② assets 双向一致（磁盘 ↔ manifest）
- ③ 版本一致（manifest ↔ JS 邮戳；控制器不得有手写版本号）
- ④ po 无重复 `msgid` + 应用列表元数据 `msgid` 与 manifest 逐字符一致
- ⑤ JS / Python / XML 语法（SCSS 另跑 `npx sass`）
- ⑥ 源码无残留中文（注释除外）

### 5.3 30 秒冒烟（详见 `RETROSPECTIVE.md` 附录 C）

1. 强刷浏览器，`?debug=1` 打开订单页；
2. 控制台应先出现 `assets loaded (19.0.1.6.0)` 与 `self-check: assets 19.0.1.6.0, server 19.0.1.6.0 (ok)`；
3. 列表加载出现 `prefetch …` / `payload: requested …, received …`；
4. 悬停 → `hover row` → `popover opened`；浮层只剩**可用库存**一项数值（无数量 / 单价 / 售价）；
5. 服务类产品：明细表整块不出现；
6. 触屏长按、原有点击 / 编辑 / 勾选 / 删除、非销售列表各回归一次；
7. 切 `zh_CN` 复核标签为「可用库存」。

### 5.4 回滚

- 无数据库结构变更（无新模型 / 字段 / 权限 / 视图），**回滚不需要迁移脚本**。
- 代码回滚：把版本改回上一版并 `-u` + 重启进程 + 强刷浏览器即可；缓存只在浏览器内存里，刷新即重建。

---

## 六、相关文档

- 使用与验收：[`README.md`](README.md)
- 逐版本变更：[`CHANGELOG.md`](CHANGELOG.md)
- 约束与陷阱：[`AGENTS.md`](AGENTS.md)
- 过程复盘与方法论：[`RETROSPECTIVE.md`](RETROSPECTIVE.md)
- 仓库级规范：[根 `AGENTS.md`](../AGENTS.md)（第 2 节查源码、第 4 节 i18n、第 7 节文档规范）

---

## 许可证

LGPL-3
