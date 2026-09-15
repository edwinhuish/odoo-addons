# 变更日志

> 倒序排列，最新版本在最前。每版本固定三段式：变更 / 影响 / 文档。
> 版本号规则见根 `AGENTS.md` 第 3 节：架构/破坏性 +x，功能 +y，修复/文档 +z。

## [19.0.1.4.0] - 2026-09-15（待验证）

### 变更

- **未保存的新行改为「直接从产品取数」**（反馈：*订单未保存，新添加的产品在服务端订单列表里当然
  没有；此时应该直接从产品里查数据，而不是从报价单 / 订单里查*）：
  - 删掉后端 `drafts` 方案（`sale.order.line._get_product_hover_draft_payload()`、接口的
    `drafts` 参数）：它本质仍是「把新行当成订单行来查」，而且要求服务端先升级才能用——
    这正是它一直不生效的原因。
  - 新增前端模块 **`static/src/js/product_hover_product.js`**：按 `product_id` 用**标准 ORM**
    （`searchRead("product.product", [["id","in",ids]], …)`）读产品数据，行的数量 / 单位 /
    单价 / 币种直接用表单里**正在编辑**的值，用 Odoo 前端格式化工具
    （`formatFloat` / `formatMonetary`）装配出与已保存行**完全同形**的 payload。
  - 产品数据按 `product_id` 缓存（同一产品多行共用；读不到的产品记 `null`，不反复请求），
    行的取值变化时才重新装配——所以改完数量 / 单价，下一次悬停立刻显示新值。
  - **收益**：新行预览不再依赖自研接口，也**不再需要服务端升级 / `-u`**（`?debug=assets`
    下 JS 会自动重建），彻底摆脱「前端新、后端旧」的部署问题。
- **接口收窄**：`/sale_product_hover/payload` 只服务**已保存**行（`line_ids`），
  并在注释里写明**不要再给它加参数去处理新行**：旧后端收到不认识的参数（如曾经的 `drafts`）
  会整批报错，连已保存行的预览也会一起失效。`version` 参数一并去掉（空 `line_ids` 的
  版本回显已可满足探测需求）。
- 服务端版本探测保留：打开订单页仍输出一行
  `self-check: assets X, server Y`——它现在只对**已保存行**有意义（新行是前端直接查产品）。

### 影响

- 不涉及数据库结构变更，**无需迁移脚本**；接口向后兼容（少了一个从未生效的可选参数）。
- 对用户：新增产品行**无需保存即可预览**，且**无需升级服务端**；已保存行行为不变。
- 若服务端 Python 未升级：已保存行的卡片仍可能缺字段（旧 payload 字段名），
  届时 `self-check` 会明确提示 `server NOT UPGRADED`。

### 文档

- 同步 `__manifest__.py`（`19.0.1.4.0`，assets 登记新前端文件）、`README.md`
  （功能概述 / 核心设计 / 模块资源 / 接口 / 排障 / 验证清单）、`AGENTS.md`
  （L1 约束、P1 陷阱 16、文件职责、调试建议）、根 `README.md` / `AGENTS.md` / `TODO.md`。

---

## [19.0.1.3.3] - 2026-09-15（待验证）

### 变更

- **新增「服务端版本探测 + 启动自检」**，一次定性「服务端 Python 没升级」还是「业务上确实没数据」：
  - 探测请求用**空 `line_ids`** 打同一个接口：**旧后端也一定会成功返回** `{}`（不会报错），
    新后端则多一个保留键 `__server_version`——因此它能在**不依赖 `drafts` 新参数**的前提下
    判断服务端代码版本（用 `drafts` 是探测不出来的：旧后端遇到新参数直接 500）。
  - 打开订单页（订单行列表首次预取）时输出**一行**结论，排查先看它：
    - `[sale_product_hover] self-check: assets 19.0.1.3.3, server 19.0.1.3.3 (ok)`
    - `… server NOT UPGRADED → the server does NOT report __server_version, i.e. its Python code is
      not upgraded. Run -u sale_product_hover and RESTART the server process …`
  - 取数失败（无论是「请求本身失败」还是「请求成功但没返回这一行」）时，
    `console.error` 除了现象还会**带上探测结论**：已升级 → 属数据 / 权限问题（看服务端日志）；
    未升级 → 直接给升级 + 重启命令。
  - 探测请求每个会话只发一次、且只在订单行列表出现时触发，正常流程零额外请求。
- 补充说明一个**长期误判的根源**：`?debug=assets` 模式下 Odoo 会用文件的 mtime 参与 assets
  校验和，因此 **JS / SCSS 改了会立刻重建、不需要 `-u`；而 Python 必须 `-u` 且要重启进程**
  （运行中的进程 `sys.modules` 里还是旧代码）。这正是「前端已经是新版、后端还是旧版」的成因。

### 影响

- 不涉及数据库结构变更，**无需迁移脚本**；接口与 payload 未变（仍只有那一个保留键）。
- 正常使用时只多一次极小的探测请求（每会话一次）；版本一致时只输出一条 info。

### 文档

- 同步 `__manifest__.py`（`19.0.1.3.3`）、`README.md`（排障按 `self-check` 行分流）、
  `AGENTS.md`（调试建议）、根 `README.md` / `AGENTS.md` 的版本引用。

---

## [19.0.1.3.2] - 2026-09-15（待验证）

### 变更

- **修复 `19.0.1.3.1` 引入的回归：`Uncaught TypeError: getLineHoverPayload is not a function`**
  （悬停任意订单行时抛出，浮层完全不可用）：
  - 根因：`19.0.1.3.1` 为了加版本自证**整份重写了 `product_hover_cache.js`**，重写时漏掉了
    `export function getLineHoverPayload()`。同一次 import 里的 `setClientVersion` 还在，
    所以模块能正常加载、`prefetch` 也照常发请求，**只有真正读缓存那一步炸**——
    表现为悬停时的 `Uncaught Promise > TypeError`，而不是加载期报错。
  - 修复：补回 `getLineHoverPayload` 的导出。
  - **防回归**：`product_hover_list_patch.js` 增加**加载期自检**，逐个检查从缓存模块命名导入的
    4 个 helper 是否真的是函数，缺失就 `console.error` 明确报出「assets 不一致 + 该怎么做」，
    不再等到悬停才抛难懂的 TypeError。
- 附带把「命名导入 vs 导出」的静态自查加进规范（见 `AGENTS.md`），本次已对**全部模块**跑过，
  当前无其它同类问题。

### 影响

- 不涉及数据库结构变更，**无需迁移脚本**；接口与 payload 无变化。
- 版本三处同步升为 `19.0.1.3.2`（`__manifest__.py` / JS / 控制器）。

### 文档

- 同步 `__manifest__.py`、`README.md`（排障）、`AGENTS.md`（新增 JS 导出自查、调试建议）、
  根 `AGENTS.md`（前端规范增加该自查）、根 `README.md` 的版本引用。

---

## [19.0.1.3.1] - 2026-09-15（待验证）

### 变更

- **修复「接口成功但没返回这一行的数据」会让该行永久失效**（真实反馈：选了产品后悬停依旧
  无浮层，控制台只有 `skip: … 该行没有可展示数据 … datapoint_165`）：
  - 根因：`prefetchDraftHoverPayload()` 在**发请求之前**就把该行的「取值签名」记为已请求。
    若这次响应里**没有**这一行的数据（服务端异常被吞、或服务端 Python 未升级导致草稿被跳过），
    签名会一直留着 → 之后每次悬停都被判为「已请求过」→ **不再发请求、永远拿不到数据**，
    且没有任何报错，只有一条语义含糊的 skip 日志。已保存行的「已请求」标记同理。
  - 现在：响应里没有数据的行会**回退标记**，下次悬停重试；同时对「整批一条都没回来」
    与「新行没拿到数据」各给一条**可操作的 `console.warn`**（只告警一次，不刷屏）。
- **新增前后端版本自证**（本项目已多次踩「静态资源更新了、Python 没升级」的坑）：
  - 接口新增入参 `version`，并在响应里回显保留键 `__server_version`
    （`controllers/product_hover_controller.py` 的 `MODULE_VERSION`）；
  - 前端把资源版本带上去，发现服务端版本**缺失或不一致**时直接给出可执行提示：
    `server module version is X while the loaded assets are Y. Run -u sale_product_hover, restart…`；
  - `MODULE_VERSION` 因此要求**三处同步**：`__manifest__.py` / JS / 控制器。
- 服务端可观测性：草稿行的 `product_id` 非法、或产品不存在 / 当前用户读不到时，
  在服务端日志里明确记一条（原来这些情况都是静默 `continue`，前端只表现为「不弹」）；
  `product_id` 若被序列化成数字字符串也会自动兜住。

### 影响

- 不涉及数据库结构变更，**无需迁移脚本**；接口向后兼容（新增可选入参 + 一个保留键，
  已保存行的键仍是行 id）。
- 对用户：不再是「静默失效」——取不到数据时会重试并在控制台给出原因与修复动作。

### 文档

- 同步 `__manifest__.py`（`19.0.1.3.1`）、`README.md`（接口入参 / 排障步骤）、
  `AGENTS.md`（版本三处同步要求、P1 陷阱 15、调试建议）、
  根 `README.md` / `AGENTS.md` 的版本引用。

---

## [19.0.1.3.0] - 2026-09-15（待验证）

### 变更

- **新增（尚未保存）的产品行现在也能预览**（此前文档明确写「未保存的新行跳过」，用户实测
  「老产品能看详情，刚新增的产品行没有」）：
  - **根因 1 · 编辑态守卫一刀切**：Odoo 的 `Record.isInEdition` 是
    `this.config.mode === "edit" || !this.resId`（`model/relational_model/record.js`），
    也就是**对没有 `resId` 的新行恒为真**——新行一加进列表就已经是 `editedRecord`，
    于是 `if (this.props.list.editedRecord) return;` 把新行全部挡掉；更糟的是只要列表里
    存在一条新行，**其它已保存行也会被一起挡住**。
    现在避让条件收敛为 `_isProductHoverBlockedByEdit()`：仅「正在被内联编辑的**已保存**行」不弹。
  - **根因 2 · 取数只认数据库 id**：预取跳过 `!record.resId`，打开浮层也要求 `record.resId`。
    现在缓存键改为 `_getProductHoverKey()`（已保存行 → 数据库 id；新行 → Owl datapoint id），
    新行由 `_getProductHoverDraft()` 把表单里正在编辑的值（产品 / 数量 / 单位 / 单价 / 币种）
    作为「草稿规格」传给后端。
  - **后端两条路径合一**：新增 `_get_product_hover_draft_payload()`，
    与已保存行的 `_get_product_hover_payload()` 共用 `_build_hover_payload()`，
    保证两种行的浮层内容与格式化口径完全一致；产品改用
    `with_context(active_test=False).search([("id", "in", ids)])` 读取（应用记录规则并剔除
    读不到的产品），避免前端传来的产品 id 让 `read()` 整批抛 `AccessError`。
    接口 `/sale_product_hover/payload` 新增可选入参 `drafts`。
  - **实时性**：草稿按 `产品|数量|单位|单价|币种` 生成签名，签名未变即命中上一次结果
    （**悬停依然不发请求**），变了才重新取数；`onPatched` 随表单输入刷新，悬停时再兜一次，
    因此改完数量 / 单价立刻能在浮层里看到新值。
  - 受接口影响：`drafts` 中的数量与单价**只用于展示、不写库**；产品字段仍按当前用户权限读取。

### 影响

- 不涉及数据库结构变更，**无需迁移脚本**：无新建模型 / 字段 / 权限 / 视图。
- 接口新增可选入参 `drafts`，返回值的键对已保存行仍是行 id（向后兼容）。
- 对用户：新增产品行（含触屏长按）可立即看到浮层，不必先保存；改动数量 / 单价后浮层随之更新；
  已保存行的内联编辑避让行为不变（且不再被列表里的新行连带影响）。
- 性能：已保存行仍是每页一次批量请求 + 悬停零请求；新行仅在取值变化后各多一次（通常 1~2 行）。

### 文档

- 同步 `__manifest__.py`（`19.0.1.3.0`，`description` 补新行预览说明）、`README.md`
  （功能概述 / 核心设计 / 交互说明 / 接口入参与字段 / 验证清单 / 排障版本号）、
  `AGENTS.md`（L1 约束、P1 新增陷阱 14）、`i18n/zh_CN.po`（应用列表描述条目同步）、
  根 `README.md` / `AGENTS.md` / `TODO.md` 的版本引用与验收项。

---

## [19.0.1.2.0] - 2026-09-14（待验证）

### 变更

- **浮层改为跟随鼠标**（原来固定挂在整行的右侧，离光标很远）：
  - popover 的目标仍是**行**（这样 `getPopoverForTarget(row)` 才能查到浮层、浮层内移入不关闭），
    但落点由补丁自己算：`_positionProductHover()` 把浮层摆在**光标右下**
    （`POINTER_OFFSET_X/Y = 16/12`），右侧放不下就翻到光标左侧，下方放不下就上移贴边，
    连视口都装不下时自己收紧 `maxHeight` 并允许内部滚动，任何情况下都不会被屏幕裁切。
  - `mousemove`（document 捕获 + `passive`）用 `requestAnimationFrame` 合帧更新位置；
    指针**进入浮层后停止跟随**（`el.contains(ev.target)`），方便阅读。
  - 这样做的可行性来自 Odoo 的 `reposition()`：它会把浮层设成 `position: fixed` 并直接写
    `left/top`（视口坐标），所以补丁可以直接改写 `left/top` 跟随光标；每次 Odoo 重定位
    （挂载 / 滚动 / 缩放）后都会回调 `onPositioned`，在那里再套用一次光标位置即可。
  - 随之 `animation: false`（关掉开合动画的位移与锁位，跟随场景只会造成抖动），
    并去掉不再需要的 `extendedFlipping`（翻转已由补丁自己处理）。
  - `open()` 之后补回 `_productHoverRowEl` 与 `_productHoverPointer`：`open()` 内部会先关闭
    旧浮层并**同步**触发 `onClose`，不补回会导致浮层先闪在行旁边才跳到光标处（见 `AGENTS.md` P1 陷阱 10）。
- **屏蔽行内元素的原生 tooltip**（截图里那层黑色小提示，原来会和浮层同时出现）：
  - Odoo 的 tooltip 服务挂在 `document.body` 的**捕获阶段** `mouseenter` 上，元素上的
    `data-tooltip`（单元格常见，延迟 1000ms）会独立弹出。
  - 补丁在更外层的 `document` 捕获阶段监听 `mouseenter`，**只在该行确实有我们自己的浮层数据时**
    `stopPropagation()`（`_isProductHoverCardReady()`：有 record / 有 `resId` / 缓存里有 payload / 非编辑态），
    tooltip 服务收不到事件就不会再弹；其余行与元素完全不受影响。

### 影响

- 仅前端行为，**不涉及数据库结构变更，无需迁移脚本**；接口 payload 无变化。
- `MODULE_VERSION` 与 `__manifest__.py` 同步升为 `19.0.1.2.0`（控制台
  `assets loaded (19.0.1.2.0)` 可确认浏览器已加载新资源）。

### 文档

- 模块 `AGENTS.md` 新增 P1 陷阱 12（原生 tooltip 在 `document.body` 捕获阶段）与
  陷阱 13（自己接管 popover 定位的可行性与边界）；同步 `README.md`、
  `__manifest__.py`（`19.0.1.2.0`）、根 `README.md` / `AGENTS.md` 版本引用。

---

## [19.0.1.1.1] - 2026-09-14（待验证）

### 变更

- **修复「预取正常但悬停始终不弹浮层」的真正根因**（`19.0.1.0.0` 起一直存在）：
  - 现象：控制台只有 `prefetch … N saved line(s)` 与 `payload: requested N, received M`，
    **完全没有 `hover row`**；鼠标停在订单行上毫无反应，也不报错。
  - 根因：行 DOM 上的 `data-id` 是 Owl 的 **datapoint id，字符串**
    （`odoo/addons/web/static/src/model/relational_model/utils.js` 的 `getId()` 返回
    `` `${prefix}_${++nextId}` ``，即 `"datapoint_42"`），而 `_getProductHoverRecord()`
    写成 `Number(row.dataset.id)` → `Number("datapoint_42")` = `NaN` →
    `Number.isFinite(NaN)` 为假 → **反查行归属永远失败**，每个 `mouseover` 都在第一步
    `return`；因为 prefetch 走的是 `record.resId`（数据库 id），所以数据链路看起来完全正常。
  - 修复：`_getProductHoverRecord()` 改为**按字符串比较**（两侧都做一次 `String()` 化），
    与 Odoo 官方写法一致（`kanban_renderer.js`：`records.find((e) => e.id === target.dataset.id)`）。
  - `MODULE_VERSION` 同步升为 `19.0.1.1.1`，便于用控制台
    `assets loaded (19.0.1.1.1)` 确认浏览器确实加载了新资源（`19.0.1.1.0` 已被缓存过）。

### 影响

- 仅前端一行判定逻辑，**不涉及数据库结构变更，无需迁移脚本**。
- `19.0.1.1.0` 的其余改动（捕获阶段委托、去双绑定、规格 / 数量 / 单价、触屏长按、
  响应式、SCSS `min()` 修坑）保持不变。

### 文档

- 模块 `AGENTS.md` 新增 P1 陷阱 11（datapoint id 是字符串）与调试建议更新；
  同步 `__manifest__.py`（`19.0.1.1.1`）、`README.md`、根 `README.md` / `AGENTS.md` 版本引用。

---

## [19.0.1.1.0] - 2026-09-14（待验证）

### 变更

- **修复订单页悬停不弹浮层**（重做触发链路，去掉此前两版的猜测性加固）：
  - 事件监听改成 **document 级「捕获阶段」委托**。捕获阶段先于行内业务监听触发，
    不会被 `stopPropagation` 吃掉（Odoo 列表在触屏选择模式下会拦截 `mouseover`），
    也与渲染器 DOM 结构、挂载时机、根节点 ref 无关。
  - **删除「事件双绑定」**（document 冒泡 + 渲染器根元素 `this.el`）：那是对
    `19.0.1.0.1` 失效原因的猜测，两套监听互相干扰；现在只有一套。
  - 行归属判定不再用 `this.el.contains(ev.target)`，改为**用行的 `data-id` 反查
    `props.list.records`**：查得到即属于本渲染器。既不依赖根元素结构，也不会误判
    其他模型列表的行。
  - 所有 `debugInfo` 里的中文字符串保留（仅 `?debug` 下输出的排障日志，非界面文案）。
- **浮层内容补齐为「产品详情」**（原来只有名称 / 型号 / 描述 / 价格 / 库存）：
  - 新增**规格**：变体属性值 `product.template.attribute.value.display_name` 拼成
    `颜色: 红, 尺寸: L`（属性名与取值都是产品数据，随产品记录语言展示，不进 po）。
  - 新增**订单数量**（`product_uom_qty`，行上的计量单位）：`Quantity` 行显示
    `10 Units`；与「可用库存」各自用自己的单位名（订单行单位 / 产品默认单位）。
  - 「本单单价」标签改为 **`Unit Price`**，「产品售价」标签改为 `Sales Price`
    （原 `Order Price` 文案随之下线，po 同步）。
  - 卡片改为「图片 + 标识区 → 描述 → 明细表」布局，明细行 `dt` 左、`dd` 右且等宽数字对齐。
- **跨设备可用**：
  - **触屏长按**：触屏没有 hover，改为长按订单行 500ms 弹出同一浮层；`touchmove`
    位移超 10px 视为滚动并取消；长按触发后吃掉紧随的那次 `click`（长按是"看详情"，
    不是"打开记录"）；手势结束后 800ms 内忽略浏览器补发的 mouse 事件，避免"点一下弹两次"。
  - **响应式**：`extendedFlipping: true` 让空间不足时自动换方位；卡片宽度改为
    `width: 20rem; max-width: calc(100vw - 1.5rem)`（窄屏自动收窄）；
    新增窄屏（≤ 575.98px）媒体查询收紧图片与字号。
  - `arrow: false`：浮层锚在整行（行较高）上，去掉箭头更干净。
  - **SCSS 修坑**：卡片宽度原写成 `width: min(20rem, calc(100vw - 1.5rem))`，Sass 会把
    `min()` 当内置函数求值并因 `calc()` 不是数字而报错（`"calc(...)" is not a number for 'min'`），
    导致 `web.assets_web` / `web.assets_web_print` **整份 CSS 编译失败**；改为
    `width: 20rem; max-width: calc(100vw - 1.5rem);`（`calc()` 始终原样透传）。
    踩坑记录见 `AGENTS.md` → P4。
- 缓存增加**上限保护**（`MAX_CACHED_LINES = 2000`）：一次会话翻过大量订单行时整体清空重建，
  避免长时间使用后内存无界增长。

### 影响

- 不涉及数据库结构变更，**无需迁移脚本**：无新建模型、无新建字段、无权限文件，
  也不新增 / 修改任何视图与动作。
- 接口 `/sale_product_hover/payload` 的返回字段有**增删改名**（内部接口，仅本模块前端消费）：
  新增 `specification` / `qty_ordered_text` / `available_uom_name`，
  `order_price_text` → `unit_price_text`、`sales_price_text` → `list_price_text`、
  `show_order_price` → `show_list_price`，字段口径见 `README.md`。
- 对用户：订单行悬停新增只读浮层；行的点击、内联编辑、勾选、删除等行为不变；
  触屏设备新增「长按看详情」手势。
- 卸载模块后：无残留数据（无 `ir.model.data` 记录、无字段、无视图），仅前端资源随
  bundle 重建消失。
- 性能：每个列表页一次批量请求（payload 只含展示字段，不含图片二进制）；
  规格多一次 `product.template.attribute.value` 批量读（仅涉及本页产品用到的属性值）；
  悬停为纯前端缓存读取。

### 文档

- 同步更新 `__manifest__.py`（`19.0.1.1.0`，`description` 补新功能说明）、`README.md`、
  `AGENTS.md`、`i18n/zh_CN.po`（新增 `Quantity` / `Unit Price` 两条，删除 `Order Price`，
  应用列表描述条目同步）、根 `README.md` / `AGENTS.md` / `TODO.md` 的版本引用。

---

## [19.0.1.0.2] - 2026-09-13（待验证）

### 变更

- **排障增强 + 事件绑定双保险**（`19.0.1.0.1` 后端接口已确认正常：`POST /sale_product_hover/payload`
  返回 200 且数据完整，问题只出现在「悬停 → 弹浮层」这一段）：
  - 事件**双重绑定**：document 级委托（setup 阶段注册）之外，`onMounted` 时再在渲染器根元素
    `this.el` 上绑定一次，兜底不同版本渲染器结构 / 事件系统差异；同一行重复命中由
    `_productHoverRowEl` 判重挡住，不会重复打开浮层。
  - 诊断日志由 `console.debug` 改为 **`console.info`**（控制台默认可见；仅在
    `?debug=1` / `?debug=assets` 下输出，日常不刷屏）：`prefetch` / `hover row` /
    `skip: …`（含跳过原因）/ `popover opened` / `popover closed`，可完整定位「事件未触发 →
    未打开 → 已打开但被关闭」中的哪一环。
  - 增加**版本自证**：资源加载时始终输出
    `[sale_product_hover] assets loaded (19.0.1.0.2)`，括号内为运行版本——看不到这行即说明浏览器
    仍在用旧缓存 / assets 未重建。JS 内的 `MODULE_VERSION` 需与 `__manifest__.py` 的 `version` 同步。
  - 排查说明同步进 `README.md`「后续维护」与 `AGENTS.md`「调试建议」。

### 影响

- 行为逻辑不变；仅新增兜底监听与诊断输出，不涉及数据库结构变更，无需迁移脚本。
- 前端资源改动，升级后需**强刷浏览器**。

### 文档

- 同步更新 `__manifest__.py`（`19.0.1.0.2`）、`README.md`、`AGENTS.md`、根 `README.md` / `AGENTS.md`
  的版本引用。

---

## [19.0.1.0.1] - 2026-09-13（待验证）

### 变更

- **修复**：安装后悬停订单行不出现浮层。逐项加固触发链路与数据链路：
  - 事件监听改为 **document 级 `mouseover` / `mouseout` 委托**，并用 `this.el.contains()` 限定
    只处理本渲染器渲染的行。此前监听挂在渲染器根节点 `this.rootRef.el`（`t-ref="root"`）上，
    而销售订单行使用的是 `sale.ListRenderer.RecordRow` ← `account.SectionAndNoteListRenderer`
    （primary 继承的自定义模板），根节点 ref 不可靠，可能出现「监听从未绑定 → 完全无反应」。
  - `usePopover` 增加 `setActiveElement: false`：popover 服务默认会 `?? true` 抢占焦点，
    悬停浮层不应打断正在进行的输入与快捷键。
  - `_isProductHoverList()` 增加 x2many 兜底：`props.list.resModel` 取不到时回退首条记录的
    `resModel`。
  - 后端 `_get_product_hover_payload()` 改为**按 `product.product` 实际字段过滤**后再 `read()`，
    取值统一用 `dict.get()`：避免个别环境字段缺失触发 `Invalid field` 使接口整体失败
    （前端只表现为「没有浮层」，无弹窗报错）。
  - 控制器增加异常兜底 + `_logger.exception` 服务端日志，失败返回 `{}`，不再静默。
  - 增加排障日志（默认级别下不可见，控制台勾 Verbose 或用 `?debug=1`）：
    资源加载时输出 `[sale_product_hover] assets loaded`；预取时输出
    `[sale_product_hover] prefetch sale.order.line: N saved line(s)` 与
    `[sale_product_hover] payload: requested N, received M`，用于区分
    「资源未加载」「前端未发请求」「请求返回无数据」三种情况。

### 影响

- 功能行为不变，仅修复触发链路并提升健壮性；**不涉及数据库结构变更，无需迁移脚本**。
- 前端资源改动，升级后需**强刷浏览器**。
- 排障入口见模块 `AGENTS.md` →「调试建议」。

### 文档

- 同步更新 `__manifest__.py`（`19.0.1.0.1`）、`AGENTS.md`（L1 / L2 增补）、`README.md`、
  根 `README.md` / `AGENTS.md` 的版本引用。

---

## [19.0.1.0.0] - 2026-09-12（待验证）

### 变更

- 初始版本，实现「报价单 / 销售订单订单行悬停展示产品详情浮层」（T-014）：
  - 后端：`sale.order.line._get_product_hover_payload()` 一次批量装配展示数据
    （名称 / 型号 / 描述 / 图片地址 / 产品售价 / 本单单价 / 可用库存 + 单位），
    价格与库存数字用 `formatLang` 按用户语言与货币（单位）精度格式化。
  - 接口：`POST /sale_product_hover/payload`（`type="jsonrpc"`、`auth="user"`、不 `sudo`），
    按订单行 id 批量返回展示数据。
  - 前端：patch `web/views/list/list_renderer` 的 `ListRenderer`，用原生
    `mouseover` / `mouseout` 事件委托实现「延迟 350ms 弹出、移开延迟 200ms 关闭、
    可移入浮层、行内移动不重开」；浮层由 popover 服务渲染在 overlay 容器，
    不改变列表 DOM。
  - 数据：列表挂载与每次 DOM 更新后按行 id 差集预取，缓存在模块级非 reactive `Map`，
    悬停不再发请求；未保存的新行跳过。
  - 范围控制：仅对 `sale.order.line` 列表生效（报价单与销售订单共用模型与视图），
    编辑态不弹浮层，其他模型列表不受影响。
  - i18n：源语言英文 + `i18n/zh_CN.po`（含应用列表元数据三条）。

### 影响

- **不涉及数据库结构变更，无需迁移脚本**：无新建模型、无新建字段、无权限文件，
  也不新增 / 修改任何视图与动作。
- 对用户：订单行悬停新增只读浮层；行的点击、内联编辑、勾选、删除等行为不变。
- 对外部：新增一个内部 JSON 路由 `/sale_product_hover/payload`（`auth="user"`），
  以当前用户身份读取，沿用产品与订单行的既有权限与记录规则。
- 卸载模块后：无残留数据（无 `ir.model.data` 记录、无字段、无视图），仅前端资源随
  bundle 重建消失。
- 性能：每个列表页一次批量请求（payload 只含展示字段，不含图片二进制）；
  悬停为纯前端缓存读取。

### 文档

- 新增 `__manifest__.py`（`19.0.1.0.0`）、`README.md`、`AGENTS.md`、本文件。
- 同步更新根 `TODO.md`（T-014 → 进行中）、`README.md` 模块一览表与路线图、
  `AGENTS.md` 第 9 节「已有模块速查」。
