# AGENTS 工作指引

> 本文档用于指导 AI 助手或新开发者在维护、扩展本 Odoo 模块时的行为规范和关键上下文。
> L1 约束段每次加载必读；L2 踩坑档案按主题触发条件加载。

---

## 模块定位

- 模块名：订单行产品悬浮卡（Sale Product Hover）
- 技术目录：`sale_product_hover`
- 新建模型：无；无 `security/ir.model.access.csv`
- 继承模型：`sale.order.line`（新增方法 `_get_product_hover_payload()` / `_build_hover_payload()` / `_get_hover_specifications()`，不新增字段；**只服务已保存行**）
- 新增 HTTP 控制器：`/sale_product_hover/payload`（`type="jsonrpc"`、`auth="user"`、不 `sudo`；**只接受 `line_ids`**，另回显 `__server_version`）
- 浮层内容：**只有产品侧信息**（图片 / 名称 / 型号 / 规格 / 描述 / 产品售价 / 可用库存），**不含订单行的数量与本单单价**（`19.0.1.5.0` 起按需求移除）
- 未保存的新行：**不走后端**，前端 `product_hover_cache.js` 按 `product_id` 用标准 ORM 读产品后装配（上下文只需 `{key, product_id}`，见陷阱 16）
- 自定义前端：无自定义组件注册；patch `web/views/list/list_renderer` 的 `ListRenderer` + 一个 popover 展示组件 `ProductHoverCard`；悬停用 document 级**捕获阶段**事件委托，触屏用长按；浮层位置由补丁自己接管（跟随鼠标）
- 主依赖：`sale`（订单行）、`stock`（`qty_available` / `is_storable`）
- 当前版本：`19.0.1.5.0`（首版 `19.0.1.0.0`；`19.0.1.0.1` / `19.0.1.0.2` 尝试修复悬停不触发；`19.0.1.1.0` 重做触发链路、补齐规格 / 数量 / 单价展示、新增触屏长按与响应式；`19.0.1.1.1` 修复 `data-id` 类型判错——**这才是悬停一直没反应的真正根因**，见 P1 陷阱 11；`19.0.1.2.0` 浮层跟随鼠标并屏蔽行内原生 tooltip，见陷阱 12 / 13；`19.0.1.3.x` 新增（未保存）行的预览并多次修坑，见陷阱 14 / 15；`19.0.1.4.0` 新行改为**前端直接查产品**（陷阱 16），`19.0.1.4.1` 把该逻辑并入已有文件、避免新增 assets 文件（陷阱 17）；`19.0.1.5.0` 按需求**移除浮层里的数量与单价**，两条取数路径同步收窄（陷阱 16 的上下文简化为 `{key, product_id}`）；均待目标环境验证）

---

## L1：不可破坏的核心约束

每次修改代码必须保证以下行为不变。每条只列约束与违反后果，实现细节见 L2 踩坑档案。

1. **不新增模型 / 字段 / 权限 / 视图**
   - 展示数据由 `sale.order.line` 扩展方法 + 内部 JSON 接口提供，沿用产品与订单行既有权限
   - 违反后果：破坏「开箱即用、不改官方视图」的设计，引入迁移、权限与视图继承锚点风险

2. **只对 `sale.order.line` 列表生效**
   - 目标模型常量在 `product_hover_list_patch.js`（`TARGET_MODEL`）；非目标列表必须完全不介入
   - 违反后果：采购订单行、发票行等列表出现无关浮层，且牵连其他模块的渲染器行为

3. **不影响原有行交互**
   - 浮层必须由 popover 服务渲染在 overlay 容器，不改变列表 DOM；
     `mouseover` / `mouseout` / `touch*` 监听一律只读，不得 `preventDefault` / 停止传播；
     编辑态避让**只针对正在被内联编辑的「已保存行」**（`_isProductHoverBlockedByEdit()`）；
     popover 必须传 `setActiveElement: false`
   - **不得**改回「`props.list.editedRecord` 非空就不弹」：Odoo 里 `Record.isInEdition` 对
     `!resId` 恒为真，未保存的新行一加进列表就是 `editedRecord`，那样写会让新增产品永远没有
     预览，还会连带挡掉同列表里的已保存行（见 P1 陷阱 14）
   - **唯一例外**：触屏长按弹出浮层后，用一次性 `click` 捕获监听吃掉紧随的那一次点击
     （长按语义是"看详情"而非"打开记录"），该监听不命中任何其它事件，用完即摘；
     不得把它扩大成常驻监听
   - 违反后果：点击进入、内联编辑、勾选、删除等原有操作被干扰，或悬停抢走输入焦点
     （popover 服务默认 `setActiveElement ?? true`）；常驻 `click` 拦截会让整张列表点不动

4. **悬停不发请求**
   - 数据在列表挂载 / DOM 更新时按行 id 差集批量预取（`prefetchLineHoverPayload`），
     悬停只读缓存；缓存必须是**模块级非 reactive 容器**，并保留上限保护
     （`MAX_CACHED_LINES`，触发时整体清空重建）
   - 违反后果：每次悬停产生请求；缓存挂到 reactive 对象上触发 Owl 重渲染 / 重载循环导致页面卡死；
     无上限则长时间翻页后内存持续增长

5. **控制器不提权**
   - 不 `sudo`；以当前用户身份读取（前端只传当前列表页可见的行，记录规则照常生效）
   - 产品集合一律用 `search` 而不是 `browse().read()`：
     `with_context(active_test=False).search([("id", "in", ids)])`——`search` 会应用记录规则并
     剔除读不到的产品，否则一个越权 / 失效的 id 会让 `read()` 整批抛 `AccessError`，把所有行的
     浮层一起打没。前端读产品（未保存的新行）同理：用 `orm.searchRead` 而不是 `orm.read`
   - 违反后果：越权暴露其他用户订单行的产品与库存信息；或一个异常的产品 id 让整批取数失效

6. **所有用户可见文本源语言为英文（`en_US`）**
   - Python / JS / QWeb 模板不写中文界面文案；中文只在 `i18n/zh_CN.po` 的 `msgstr`
   - 违反后果：默认英文界面出现中文，或译文失效 / 重复 `msgid` 导致 po 解析失败

---

## 国际化约束（i18n）

每处用户可见文本都必须满足（通用规则见根 `AGENTS.md` 第 4 节）：

1. **源语言是英文（`en_US`）**：Python / JS / QWeb 模板里一律写英文；中文只能出现在 `i18n/zh_CN.po` 的 `msgstr` 里，禁止写回源码。
2. **可翻译入口正确**：见根 `AGENTS.md` 4.2「可翻译入口对照表」。本模块只有两类：
   - QWeb 模板文本 → `code:addons/sale_product_hover/static/src/xml/product_hover_templates.xml:0`
   - JS `_t()` → `code:addons/sale_product_hover/static/src/js/product_hover_card.js:0`
3. **禁止拼接句子**：占位符统一 `%(name)s`（如库存文案 `_t("%(qty)s %(uom)s", …)`），禁止按位置 `%s` 或 JS `+` 拼接可翻译句子。
4. **数字 / 货币不进 po**：价格与库存数字由后端 `formatLang` 按用户语言与货币（单位）精度格式化后直接展示；产品名 / 型号 / 描述 / 单位名是数据，随产品记录语言展示。
5. **收尾动作**：改英文源文本 → 同步 `i18n/zh_CN.po` → 提升版本 → `-u` 升级 + **强刷浏览器**，中英文各验一遍。
6. **代码注释保持中文**，不为 i18n 改英文。
7. **应用列表（Apps）元数据必须有中文**：改 `__manifest__.py` 的 `name` / `summary` / `description` 后，必须同步 `i18n/zh_CN.po` 的 `model:ir.module.module,shortdesc|summary|description:base.module_sale_product_hover` 三条（`description` 条的 `msgid` 必须等于 `textwrap.dedent(manifest["description"])`，逐字符一致）。分类 `Sales/Sales` 是官方分类，沿用 `base` 译文，**不要**重复翻译。这些记录归属 `base` 且 `noupdate=True`，导入只补缺失语种、不覆盖库里已有值；改译文后的强制刷新方式见根 [`AGENTS.md`](../AGENTS.md) 4.8。违反后果：中文环境「应用」列表显示英文，或译文与英文源文本长期不同步。

---

## L2：踩坑档案

### P1：悬停事件与浮层抖动

**触发条件**：改 `product_hover_list_patch.js` / `product_hover_card.js` 时必读

**陷阱 1：给行加 `mouseenter` / `mouseleave` 委托**
- 现象：事件不触发，浮层永远不弹
- 根因：`mouseenter` / `mouseleave` 不冒泡，无法在渲染器根节点做事件委托
- 正确做法：用可冒泡的 `mouseover` / `mouseout` + `ev.target.closest("tr.o_data_row")` 定位行，
  并用 `this._productHoverRowEl` 记录当前行，避免行内子元素间移动时反复重开

**陷阱 2：指针从行移入浮层时浮层立即消失**
- 现象：鼠标刚碰到浮层就关闭，无法在浮层内阅读
- 根因：浮层渲染在 overlay 容器，不是行的子节点，行的 `mouseout` 认为指针已离开
- 正确做法：`mouseout` 时用 `getPopoverForTarget(row)?.contains(ev.relatedTarget)` 判断指针
  是否已进入浮层，是则取消关闭；同时浮层组件根节点用 `t-on-pointerleave` 处理「移出浮层」
  （此时行已收不到 mouseout，必须显式关闭）

**陷阱 3：浮层关闭后指针回到行上不再重开**
- 现象：从浮层把指针移回触发行，浮层消失且不再出现
- 根因：行内 `mouseover` 因 `this._productHoverRowEl === row` 被判为「行内移动」而跳过
- 正确做法：popover 的 `onClose` 回调里清空 `this._productHoverRowEl`（`_resetProductHover`），
  使指针回到行上时能重新走一次打开计时

**陷阱 4：异步取数返回后行已切换**
- 现象：浮层显示在错误的行上，或组件已卸载仍尝试打开
- 根因：`await prefetchLineHoverPayload(...)` 之后指针可能已移到别处
- 正确做法：`await` 之后必须重新校验 `this._productHoverRowEl === row` 且 `row.isConnected` 再 `open`

**陷阱 5：把监听挂在渲染器根节点 ref 上（本模块真实踩过）**
- 现象：悬停完全没反应，控制台无报错，Network 里也没有 `/sale_product_hover/payload` 请求
- 根因：`web.ListRenderer` 模板根节点有 `t-ref="root"`，但销售订单行用的是
  `sale.ListRenderer.RecordRow` ← `account.SectionAndNoteListRenderer`
  （primary 继承的自定义模板，`static template = "account.SectionAndNoteListRenderer"`）；
  自定义渲染器的根节点 ref 不一定存在，`onMounted` 里的 `addEventListener` 整段被跳过
- 正确做法：用 `useExternalListener(document, ...)` 在 **setup 阶段**注册
  （与 DOM 结构、挂载时机均无关）

**陷阱 6：只用冒泡阶段委托（`19.0.1.0.1` / `19.0.1.0.2` 的真实失效原因之一）**
- 现象：预取正常（Network 里有 `/sale_product_hover/payload`），但悬停始终不弹浮层
- 根因：Odoo 列表的行模板在 `tr.o_data_row` 上带 `t-on-mouseover.capture` /
  `t-on-mouseout.capture`（`ignoreEventInSelectionMode`），某些状态下会
  `ev.stopPropagation()`；冒泡阶段的 document 监听排在其后，被整段掐断
- 正确做法：document 级监听一律传 `{ capture: true }`（`CAPTURE` 常量），
  捕获阶段先于行内监听触发，且不受其 `stopPropagation` 影响

**陷阱 7：用 `this.el.contains(ev.target)` 判断行归属（`19.0.1.1.0` 起已移除）**
- 现象：鼠标确实停在行上，但 `_isProductHoverList()` 为真、事件却始终被 `return` 掉
- 根因：`this.el` 是渲染器的根元素，自定义渲染器（`SectionAndNoteListRenderer` 家族）
  的根元素结构与标准模板不一致；一旦 `this.el` 取到的是别的节点，`contains` 恒为假
- 正确做法：**用行的 `data-id`（Owl datapoint id）反查 `props.list.records`**
  （`_getProductHoverRecord`）：查得到即属于本渲染器。既不依赖根元素，也不会误判
  其他模型列表的行；`_isProductHoverList()` 另有 `list.resModel` 取不到时的记录级兜底

**陷阱 8：「事件双绑定」互相干扰（`19.0.1.0.2` 引入、`19.0.1.1.0` 删除）**
- 现象：同一枚事件被两个监听处理，行为难以预测（关掉又立刻重开、日志重复）
- 根因：document 冒泡委托 + 渲染器根元素各绑一套，靠 `_productHoverRowEl` 判重"打补丁"，
  而这枚状态变量又被关闭流程清空，判重并不成立
- 正确做法：**只保留一套监听**（document 捕获阶段）。出现"不触发"时先定位根因，
  不要靠加第二套监听兜底——那会把"没触发"变成"触发两次 + 状态错乱"
- 附注：`setup()` 里注册的 `useExternalListener` 由 Owl 在 `onMounted` / `onWillUnmount`
  自动挂载与摘除，无需自己 `addEventListener` / `removeEventListener`

**陷阱 9：触屏上"长按"与"点击打开"互相打架**
- 现象：触屏长按弹出浮层的同时又打开了记录弹窗；或点一下就闪出浮层
- 根因：长按结束后浏览器会补发 `click`；抬手后还会补发一轮
  `mouseover` / `mousedown` / `mouseup`，把"触屏"又当成"悬停"
- 正确做法：长按触发时用**一次性** `click` 捕获监听吃掉紧随的那一次点击
  （`_suppressNextProductHoverClick`，另设定时器兜底摘除）；`touchstart` 起置
  `_productHoverTouchActive`，手势结束后 800ms 内忽略 mouse 事件
  （`TOUCH_MOUSE_GRACE`）；`touchmove` 位移超 10px（`TOUCH_MOVE_TOLERANCE`）即视为滚动取消长按

**陷阱 10：`usePopover().open()` 会先关掉上一个浮层，并**同步**触发 `onClose`**
- 现象：浮层能弹出来，但鼠标在同一行内轻微移动时浮层反复刷新（关闭 → 重新计时 → 再弹）
- 根因：`makePopover.open(target, props)` 的第一行是 `close()`；`close()` →
  `overlay.remove()` → `await onRemove()`，而 `onRemove` 是**同步调用**的
  （`overlay_service.js` 的 `remove(id, onRemove)` 里 `await onRemove(...)`，
  调用表达式的函数体在同步阶段就跑完了）→ 我们的 `onClose` 回调把
  `this._productHoverRowEl` 清成了 `null`；父级行状态与浮层状态就此不一致
- 正确做法：**在 `open()` 之后**再把 `this._productHoverRowEl = row` 补回
  （见 `_openProductHover`），不要写在 `open()` 之前，也别自己再调一次 `close()`
- 顺带：`getPopoverForTarget(row)` 是公开辅助，可用来判断"这一行是否已挂着浮层"，
  在 `mouseover` 里据此跳过重复打开（`POPOVERS` 由 Popover 在 `onMounted` 写入）

**陷阱 11：把 `data-id` 当数字用（`19.0.1.0.0`~`19.0.1.1.0` 悬停没反应的真正根因）**
- 现象：预取链路完全正常（`prefetch … N saved line(s)`、`payload: requested N, received M`），
  但鼠标停在订单行上**毫无反应**，也**没有任何 `hover row` 日志**，控制台无报错
- 根因：行上的 `data-id` 是 Owl 的 **datapoint id，类型是字符串**
  （`model/relational_model/utils.js`：`getId(prefix = "")` 返回 `` `${prefix}_${++nextId}` ``，
  即 `"datapoint_42"`）；而 `_getProductHoverRecord()` 写成
  `const id = Number(row.dataset.id)` → `Number("datapoint_42")` = `NaN` →
  `Number.isFinite(NaN)` 为假 → 直接 `return null`，于是「行是否属于本渲染器」永远为假，
  每个 `mouseover` 都在第一步被丢掉。**预取走的是 `record.resId`（数据库 id，数字），
  所以数据链路看起来一切正常，极具迷惑性**
- 正确做法：**按字符串比较**，两侧都做一次 `String()` 化以兼容类型变化：
  ```js
  const datapointId = row.dataset.id;
  return (this.props.list.records || []).find(
      (record) => String(record.id) === datapointId
  ) || null;
  ```
  与 Odoo 官方写法一致：`kanban_renderer.js` 里
  `this.props.list.records.find((e) => e.id === target.dataset.id)`
- 排查手法：`record.resId`（DB id，数字）与 `record.id`（datapoint id，字符串 `"datapoint_N"`）
  是两个完全不同的东西，混用时**不会报错**，只会静默失效；新增任何"用 DOM 找 record"的
  逻辑前，先在控制台 `$0.dataset` 与 `record.id` 打印一下类型

**陷阱 12：行内元素的原生 tooltip 会和我们自己的浮层同时弹（`19.0.1.1.1` 及之前）**
- 现象：浮层正常弹出，但同时在产品 / 描述单元格上又浮出一层黑色小提示（内容是单元格被截断的全文）
- 根因：Odoo 的 tooltip 服务挂在 **`document.body` 的捕获阶段** `mouseenter` 上
  （`tooltip_service.js`：`document.body.addEventListener("mouseenter", onMouseenter, { capture: true })`），
  元素上的 `data-tooltip`（列表单元格自带，`data-tooltip-delay="1000"`）会独立弹出，
  与我们的浮层**互不影响、同时存在**；它比浮层晚弹（1000ms vs 300ms），所以看起来像"浮层没把它顶掉"
- 正确做法：补丁在更外层的 **`document` 捕获阶段**监听 `mouseenter`
  （`_onProductHoverMouseEnter`），只要该行确实有我们自己的浮层数据
  （`_isProductHoverCardReady()`：有 record、有 `resId`、缓存里有 payload、非编辑态），
  就 `ev.stopPropagation()`——事件在 `document` 就被截住，`document.body` 的捕获监听
  自然收不到，tooltip 不会再弹
- 边界：**只在"我们自己会弹浮层"的行上拦截**，其余行 / 元素零影响；
  副作用是行内元素的 `t-on-mouseenter` 也不会触发（Odoo 行模板上只有
  `ignoreEventInSelectionMode`，仅在触屏选择模式下起作用，可接受）。
  不要改成"删 `data-tooltip` 属性"：那是改 Owl 管理的 DOM，重渲染时会被还原并可能造成抖动，
  而且 tooltip 的定时器在 `mouseenter` 时就已捕获参数，删属性拦不住已经排队的弹出

**陷阱 13：浮层跟随鼠标 = 自己接管 popover 定位（`19.0.1.2.0`）**
- 目标：浮层要贴在光标旁边（原来固定挂在整行右侧，离光标很远），且要连续跟随
- 关键事实：Odoo 的 `reposition()`（`core/position/utils.js`）会把浮层设成
  **`position: fixed`** 并直接写 `left/top`（**视口坐标**）
  ```js
  popper.style.position = "fixed";
  popper.style.top = "0px"; popper.style.left = "0px";
  // …计算后
  popper.style.top = `${top}px`; popper.style.left = `${left}px`;
  ```
  ⇒ 补丁可以放心直接改写 `left/top`（用 `clientX/clientY` 即可对齐），不会与 Odoo 打架
- 触发时机：`usePosition` 的 `useEffect`（无依赖）会在浮层**每次渲染后**重新定位，
  另外滚动 / 缩放也会；每次定位完都会回调 `onPositioned` —— 用
  `usePopover(..., { onPositioned: (el) => this._positionProductHover(pointer, el) })`
  就能在 Odoo 每次摆位后把浮层拉回光标处（**不要**想靠"改目标元素位置"来跟随：
  popover 的 props 被 `markRaw`，目标移动不会触发重新定位）
- 实现要点：
  - `mousemove`（document 捕获 + `passive: true`）+ `browser.requestAnimationFrame` 合帧更新
    （定位里要读 `getBoundingClientRect`，直接绑 mousemove 会引发布局抖动）
  - 指针**进入浮层后停止跟随**（`el.contains(ev.target)`），否则浮层会跟着光标在自身内部乱跑
  - `animation: false`：开合动画会 `position.lock()` 并在结束后 `unlock()` 重新定位，跟随场景只会抖
  - 越界兜底自己做（翻到光标左侧 / 上移贴边 / 装不下时收紧 `maxHeight`）；
    `reposition()` 写的 `maxHeight` 是 `min()` 叠加的，接管定位后要先清掉再判断
  - 务必保留 `open()` 之后把 `_productHoverRowEl` **和** `_productHoverPointer` 一起补回
    （见陷阱 10）：光标丢了，浮层挂载时的 `onPositioned` 就无从定位，会先闪在行旁边

**陷阱 14：新增（未保存）的产品行没有预览（`19.0.1.3.0` 修复）**
- 现象：已保存的订单行悬停能看详情；**刚新增、还没保存的产品行怎么悬停都没反应**
- 根因有两条，缺一不可：
  1. **编辑态守卫一刀切**：Odoo 的
     ```js
     // model/relational_model/record.js
     get isInEdition() {
         if (this.config.mode === "readonly") return false;
         return this.config.mode === "edit" || !this.resId;
     }
     ```
     对**没有 `resId` 的记录恒为真** → 新行一加进列表就已经是 `list.editedRecord`
     （`editedRecord` = `records.find((r) => r.isInEdition)`），于是
     `if (this.props.list.editedRecord) return;` 把新行全部挡掉；更糟的是
     `editedRecord` 只有一条，列表里只要**存在**一条新行，**其它已保存行也会被一起挡住**
  2. **取数只认数据库 id**：预取 `if (record.resId)` 直接跳过新行，打开浮层也要求 `record.resId`
- 正确做法：
  - 避让条件收敛成 `_isProductHoverBlockedByEdit(record)`：
    `editedRecord === record && record.resId`——只有「正在被内联编辑的**已保存**行」才不弹；
  - 缓存键换成 `_getProductHoverKey(record)`：`record.resId || record.id`（数字 / `"datapoint_N"` 不冲突）；
  - 新行的展示数据由 `_getProductHoverContext(record)` 给出 `{key, product_id}`，
    再**按 `product_id` 读产品**装配（实现见陷阱 16）；
  - 缓存：新行展示内容只由产品决定，签名就是 `product_id`（`19.0.1.5.0` 起；此前是
    `产品|数量|单位|单价|币种`），产品已缓存即命中缓存（**悬停不发请求**）
- **顺带的坑（读 `record.data` 时必看）**：Odoo 19 里 many2one 的取值是
  **`{id, display_name}` 对象**，不是 `[id, name]` 数组——`record.data.product_id.id`；
  写 `[0]` / `[1]` 会静默拿到 `undefined`。另：`record.data` 只含列表视图的
  `activeFields`（含 `column_invisible` 的），取字段前先确认它在视图 arch 里声明过。
  > 历史包袱：`19.0.1.5.0` 之前新行还要带走表单里的数量 / 单价 / 单位 / 币种，其中
  > `currency_id` 可能还没从 onchange 回来，需要退回 `record.evalContext?.parent?.currency_id`
  > （订单币种），且要兼容「`{id, display_name}` 对象 vs 已被 `_computeDataContext()`
  > 压成 id 数字」两种形态。现在卡片只展示产品侧信息，**这段逻辑已整体删除**；
  > 若将来又要读行上的取值，记得把这套形态兼容一并考虑进去。

**陷阱 15：「已请求过」标记在响应缺数据时不回退 → 该行永久失效（`19.0.1.3.1` 修复）**
- 现象：选了产品后悬停新行，控制台只有
  `skip: 接口没有返回这一行的数据（无产品 / 分节行 / 无权限 / 服务端未升级） datapoint_165`，
  **没有报错、没有网络请求**，之后每次悬停都一样
- 根因（当时新行走服务端 `drafts`）：`prefetchDraftHoverPayload()` 在**发请求之前**就把
  「取值签名」记进 `requestedDraftSignatures`。一旦这次响应里**没有**该行的数据
  （服务端异常被 controller 的 try/except 吞掉、或服务端 Python 未升级导致草稿被跳过），
  标记会一直留着 → 之后每次悬停都被 `if (signature 未变) continue` 挡掉 →
  **不再发请求、也永远拿不到数据**，而且完全不报错
- 正确做法：没拿到数据的 key **必须回退标记**，下次重试；并对失败给出可操作的
  `console.error`（只告警一次）。**`19.0.1.4.0` 改成前端直接查产品后**，产品数据缓存在
  `productById`（读不到记 `null`，不再重复请求），未装配成功的行会清掉签名、下次重算，
  因此不存在「永久卡死」这一态
- 教训：任何「先记已请求、后取数」的去重缓存，都要考虑**取数成功但结果为空**的分支；
  否则一次异常就会变成永久性静默失效（比报错更难查）

**陷阱 16：未保存的新行绝不能再去查订单（`19.0.1.4.0` 起）**
- 现象：新行悬停无浮层，服务端日志 / 控制台只能看到「没有数据」，怎么改取数参数都没用
- 根因：订单还没保存，**服务端根本没有这条 `sale.order.line`**——任何「按行 id 反查」
  的方案（包括曾经把新行伪装成 `drafts` 发给接口的做法）都无从下手；而且那种方案还要求
  服务端先 `-u` 升级，恰好撞上本项目「前端已更新、后端没升级」的老问题
- 正确做法：**新行直接从产品取数**——`_getProductHoverContext()` 只提供
  `{key, product_id}`（`19.0.1.5.0` 起；此前还带表单里的数量 / 单位 / 单价 / 币种，后因
  卡片不再展示这些本单数据而整体删除），由 `product_hover_cache.js` 用**标准 ORM**
  （`orm.searchRead("product.product", ...)`）读产品，`formatFloat` / `formatMonetary`
  与后端 `formatLang` 等价
- 好处：不依赖自研接口 / 服务端升级，`?debug=assets` 下改完 JS 立刻生效；
  卡片字段全在产品侧，**新行与已保存行天然同源**
- 边界：产品数据按 `product_id` 缓存（同一产品多行共用）；`searchRead` 天然剔除读不到的产品，
  不会因个别 id 让整批失败；新增字段时**两条路径都要改**（后端 `_build_hover_payload()` 与
  前端 `buildProductHoverPayload()`），否则新行与已保存行的卡片会不一致

**陷阱 17：往 assets 里新增文件 → bundle 缺模块、整条链路加载失败（`19.0.1.4.1` 修复）**
- 现象（浏览器控制台，模块完全没加载，连 `assets loaded (版本)` 都没有）：
  ```
  The following modules are needed by other modules but have not been defined,
  they may not be present in the correct asset bundle:
  ['@sale_product_hover/js/product_hover_product']
  The following modules could not be loaded because they have unmet dependencies:
  (2) ['@sale_product_hover/js/product_hover_cache', '@sale_product_hover/js/product_hover_list_patch']
  ```
- 根因：`19.0.1.4.0` 把新行取数逻辑写成新文件并加进 `__manifest__.py` 的 `assets`。
  **assets 清单来自 manifest，而运行中的进程内存里还是旧 manifest**；
  `?debug=assets` 下 Odoo 只按文件 mtime 重建 bundle 内容、**不会重读 manifest** →
  bundle 里没有新文件 → `import` 失败 → 依赖它的模块一起挂
- 正确做法：**代码写进已登记的文件**（本模块就是 4 个 js 文件，见「文件职责」）。
  只改已有文件的内容时，强刷浏览器即可生效（`?debug=assets` 会按 mtime 重建）；
  **新增文件则必须 `-u sale_product_hover` / 重启进程**，并在交付说明里写明这一步
- 教训：本模块一直强调「JS 改动不需要服务端动作」，这个优势只对**改内容**成立；
  动 manifest 就是动服务端，能不拆文件就不拆（本模块宁可把数据层都放在
  `product_hover_cache.js` 里，也不新增文件）

### P2：reactive 缓存导致的渲染循环

**触发条件**：改 `product_hover_cache.js` 时必读

- **陷阱**：把 payload 存到 reactive 对象（`useState` / `reactive`）或 model / record 上
- **现象**：页面持续重渲染乃至卡死
- **根因**：Owl 对 reactive 容器内的写入会触发依赖它的渲染 effect
- **正确做法**：用模块级 `Map` / `Set`（非 reactive），组件通过 getter 读取普通对象；
  组件内只把「图片是否加载失败」这类纯 UI 状态放 `useState`

### P3：payload 与权限

**触发条件**：改 `models/sale_order_line.py` / `controllers/product_hover_controller.py` 时必读

- **陷阱 1**：在控制器里 `sudo()` 图省事
  - 后果：越权返回其他用户本无权查看的产品信息（名称 / 价格 / 库存）
  - 正确做法：以当前用户身份 browse；只返回产品的展示字段（`19.0.1.5.0` 起已不含行上的数量 / 单价）
- **陷阱 2**：逐行访问 `line.product_id.xxx` 构造 payload
  - 后果：每行触发一次 read，行多时明显变慢
  - 正确做法：`products.read(fields)` 一次批量读，按 id 建映射后再逐行组装
- **陷阱 3**：把图片二进制放进 payload
  - 后果：一页 200 行时 payload 达到 MB 级
  - 正确做法：只返回 `/web/image/product.product/<id>/image_256` 地址，由浏览器按需加载；
    图片 404 / 无图时前端 `t-on-error` 降级为占位图标

---

## P4：SCSS 与 Sass 内置函数

**触发条件**：改 `static/src/scss/product_hover.scss` 时必读

- **陷阱**：写 `width: min(20rem, calc(100vw - 1.5rem))`
- **现象**：浏览器弹 `SCSS error dialog`，报
  `"calc(100vw - 1.5rem)" is not a number for 'min'`，
  `web.assets_web` 与 `web.assets_web_print` **整份 CSS 编译失败**（不只是浮层没样式，
  全后台样式都可能受影响）
- **根因**：`min()` / `max()` 是 **Sass 内置函数**，Sass 会先尝试求值；参数里出现
  `calc()` 这种"计算表达式"时无法求值，直接抛错。`clamp()` / `minmax()` 不是 Sass 内置，
  会原样透传，所以 `grid-template-columns: auto minmax(0, 1fr)` 是安全的
  （Odoo 核心也这么写）
- **正确做法**：宽度约束拆成 `width` + `max-width` 两条，用 `calc()` 兜底
  （`calc()` 始终原样透传）：
  ```scss
  width: 20rem;                             // 目标宽度
  max-width: calc(100vw - 1.5rem);          // 视口兜底，窄屏自动收窄
  ```
  确实需要 `min()` 时改为**上游计算一个变量**再用，不要在 `min()` 里混 `calc()`。
- **自检**：改完 SCSS 至少跑一次
  `npx --yes sass@1.77.8 --no-source-map static/src/scss/product_hover.scss /tmp/sph.css`，
  无输出即通过（本模块 SCSS 无 `@import`，可独立编译）。

---

## 文件职责

| 文件 | 职责 |
|------|------|
| `__manifest__.py` | 版本 / 依赖（`sale` + `stock`）/ 前端 assets 登记（**固定 5 项，不要新增文件**，见陷阱 17）；无 `data` 文件 |
| `models/sale_order_line.py` | **只服务已保存行**：`_get_product_hover_payload()` → `_build_hover_payload()` 批量装配（入参 `{key: product_id}`，含价格 / 库存格式化）；`_get_hover_specifications()` 批量拼变体规格 |
| `controllers/product_hover_controller.py` | `/sale_product_hover/payload` JSON 接口（只接受 `line_ids`，按行 id 批量返回；当前用户身份）；**顶部 `MODULE_VERSION` 必须与 `__manifest__.py` 的 `version` 同步**，它回显在保留键 `__server_version` 上供前端做版本自证 |
| `static/src/js/product_hover_cache.js` | 数据层（两条取数路径都在本文件，**刻意不拆文件**，见陷阱 17）：已保存行走接口（按行 id 去重）；**未保存新行按 `product_id` 用标准 ORM（`searchRead`）读产品**（含变体规格 / 可用库存），上下文只有 `{key, product_id}`，`formatFloat` / `formatMonetary` 装配（见陷阱 16）；模块级非 reactive 缓存、失败重试 / 上限保护、服务端版本探测与自证告警 |
| `static/src/js/product_hover_card.js` | 浮层组件：图片降级、库存文案 `_t`、指针离开浮层的关闭判断 |
| `static/src/js/product_hover_list_patch.js` | patch `ListRenderer`：document 捕获级事件委托 + 触屏长按、`data-id` 反查行归属（**按字符串比较**）、浮层跟随鼠标的定位（`_positionProductHover`）、行内原生 tooltip 拦截、新行取数上下文（`_getProductHoverContext` / `_getProductHoverKey`）与编辑态避让（`_isProductHoverBlockedByEdit`）、延迟开 / 关、目标模型判断；**顶部 `MODULE_VERSION` 必须与 `__manifest__.py` 的 `version` 同步**（用于控制台版本自证）；含 info 级诊断日志 |
| `static/src/xml/product_hover_templates.xml` | 浮层 QWeb 模板（字段布局与标签） |
| `static/src/scss/product_hover.scss` | 浮层样式（选择器统一 `.o_sph_` 前缀，含窄屏媒体查询） |
| `i18n/zh_CN.po` | 简体中文译文；含应用列表元数据条目（`base.module_sale_product_hover`），见根 `AGENTS.md` 4.8 |
| `README.md` / `CHANGELOG.md` / `AGENTS.md` | 三件套文档 |

---

## 常见扩展场景

### 增加浮层字段（例如产品分类、品牌）

1. **两条取数路径都要改**（否则「新增行」与「已保存行」的卡片会不一致）：
   - 已保存行：`models/sale_order_line.py` 的 `_build_hover_payload()`（字段加入 `read_fields`，
     在 payload 字典里追加；格式化在方法内做，用 `formatLang`）；
   - 新行：`static/src/js/product_hover_cache.js` 的 `buildProductHoverPayload()`
     （字段加入 `PRODUCT_FIELDS`，用 `formatFloat` / `formatMonetary` 格式化）。
   - 都**不要拼可翻译句子**——用 `%(name)s` 占位符交给 JS `_t`。
2. `static/src/xml/product_hover_templates.xml`：在 `dl.o_sph_fields` 里加 `dt` / `dd`；
   新标签文本会被抽取，需在 `i18n/zh_CN.po` 补条目（`code:addons/sale_product_hover/static/src/xml/product_hover_templates.xml:0`），
   标签必须写成**单行文本节点**（夹了子元素就会被切碎）。
3. 需要「数量 + 单位」这类拼接时（已有的「可用库存」就是这么做的）：在
   `product_hover_card.js` 加 getter，用 `_t("%(qty)s %(uom)s", { qty, uom })`；
   能复用已有 `_quantityText()` 就复用。
4. 纯透传的字段无需改 JS：组件把 `props.payload` 直接给模板。

### 支持采购订单行（`purchase.order.line`）

1. 把 `_get_product_hover_payload` 的实现抽到共用抽象（或在 `purchase.order.line` 上实现同名方法，
   把公共逻辑提到 helper / mixin），字段口径保持一致。
2. `product_hover_list_patch.js` 的 `TARGET_MODEL` 改为目标模型集合，
   `_isProductHoverList()` 与预取 / 长按判断同步调整。
3. 采购行有 `product_qty` / `price_unit` / `date_planned` 等不同字段，
   payload 与模板需按模型分支（建议按模型返回 `kind`，模板用 `t-if` 分支）。

### 调整交互参数

- 悬停 / 长按 / 关闭延迟：`product_hover_list_patch.js` 顶部
  `OPEN_DELAY` / `CLOSE_DELAY` / `TOUCH_OPEN_DELAY` / `TOUCH_MOUSE_GRACE` / `TOUCH_MOVE_TOLERANCE`。
- 浮层位置（默认 `right-start`）与 `holdOnHover` / `extendedFlipping`：`setup()` 里
  `usePopover` 的 options（`position` 取值见 `@web/core/position/position_hook`：
  `top|bottom|left|right` + `start|middle|end|fit`；`extendedFlipping: true` 让空间不足时换方位）。
- 视觉：`static/src/scss/product_hover.scss`（选择器统一 `.o_sph_` 前缀，避免影响其他视图）。

---

## 调试建议

- **浮层不出现**：用 `?debug=1` / `?debug=assets` 打开，按 info 日志链路定位：
  `assets loaded (版本号)` → `prefetch … N saved / M new line(s)`
  → `payload: requested N saved line(s), received M`（新行是
  `requested N new line(s), assembled M`）→ `hover row` → `popover opened`
  （中间若有 `skip: …` 会说明跳过原因）。
  没有 `assets loaded` = 资源未加载（缓存 / 未升级）；没有 `prefetch` = 列表判断未命中；
  `received 0` = 接口无数据；没有 `hover row` = 悬停事件未命中（行不在本渲染器的
  `props.list.records` 里，或鼠标事件被别的浮层遮挡）；有 `popover opened` 却看不到浮层 =
  样式 / DOM 问题。控制台无任何 `[sale_product_hover]` 输出时，先确认 `MODULE_VERSION` 与
  `__manifest__.py` 的 `version` 是否一致（资源确实重新打包了）。
- **`received 0` / 「接口没有返回这一行的数据」**（只可能是**已保存行**，新行不走接口）：
  **先看 `self-check` 那一行**（打开订单页时输出一次）：
  - `self-check: assets X, server X (ok)` → 两端一致，是数据 / 权限问题，查服务端日志的
    `sale_product_hover: product … not found or not readable`（产品读不到）或
    `unable to build hover payload`（装配异常）；
  - `server NOT UPGRADED` → **服务端 Python 没升级**，`-u sale_product_hover` **并重启进程**
    （运行中的进程 `sys.modules` 里还是旧代码）+ 强刷。
  - 该结论来自「空 `line_ids` 探测」：旧后端也**会成功返回** `{}`，新后端多一个
    `__server_version`，所以**不带任何新参数**就能判断版本（带新参数会让旧后端整个请求失败，
    连已保存行的预览一起打没）。
  - **为什么总出现「前端新、后端旧」**：`?debug=assets` 下 JS/SCSS 会按文件 mtime 参与
    assets 校验和、改完自动重建，**不需要 `-u`**；Python 必须 `-u` **且必须重启进程**。
  - **注意 `19.0.1.3.1` 之前这种情况会静默永久失效**，见 P1 陷阱 15。
- **新行不弹浮层**：该路径不经过接口（陷阱 16），看 `skip:` 的具体原因：
  `新行还没选产品（或为分节 / 备注行）` / `product <id> not found or not readable`；
  ORM 读取失败会打印 `unable to build preview data from the product`。
- **有请求但从不弹浮层**：优先怀疑监听注册阶段——监听必须是 `document` + `{capture: true}`
  （见 P1 陷阱 6），且归属判定只能走 `_getProductHoverRecord(row)`（陷阱 7）。
  不要再加第二套监听「兜底」（陷阱 8）。
- **触屏问题**：长按不弹 = 检查 `touchstart` 监听是否还在（capture）；点一下弹出 =
  `TOUCH_MOUSE_GRACE` 时间窗是否被改小；滚动中弹出 = `TOUCH_MOVE_TOLERANCE` 是否过大。
- **浮层反复闪烁**：多为「同一行内移动」判断失效（行元素被重渲染替换），
  确认 `closest("tr.o_data_row")` 每帧拿到的是当前 DOM 元素；`onPatched` 里会把已脱离
  文档的 `_productHoverRowEl` 复位，若仍闪烁先确认这段逻辑没被删掉。
- **浮层位置抖动 / 跑到屏幕外**：位置由 `_positionProductHover()` 接管（见 P1 陷阱 13），
  先确认 `onPositioned` 回调还在、`_productHoverPointer` 在 `open()` 之后被补回；
  宽度由 `.o_sph_card` 的 `width: 20rem; max-width: calc(100vw - 1.5rem)` 控制，若被改宽，
  窄屏会溢出（`.o_sph_popover` 上的 `max-width` 会被 Popover 自带的 `mw-100 !important`
  压过，别指望在那上面限制宽度，见 P4）。
- **浮层不跟随鼠标**：`mousemove` 监听是否还在（capture + passive）；指针已进入浮层时按设计
  停止跟随（`el.contains(ev.target)`），这是预期行为，不要当成 bug 改掉。
- **黑色原生 tooltip 又冒出来**：`mouseenter` 拦截是否还在（见 P1 陷阱 12）；
  注意它依赖「预取已完成」——列表刚打开、`payload` 还没到时不拦截（避免无谓地屏蔽 tooltip）。
- **`Uncaught TypeError: xxx is not a function`**（例如 `getLineHoverPayload is not a function`）：
  先看页面加载时有没有 `assets are inconsistent: … missing from product_hover_cache.js exports`
  ——有就是**源码里少了一个导出**（`19.0.1.3.1` 真踩过：整份重写缓存模块时漏掉
  `getLineHoverPayload`），按根 `AGENTS.md` 第 6 节的脚本跑一遍「命名导入 vs 导出」自查即可定位；
  没有这行再怀疑资源与代码不同步（强刷 / `-u`）。
- **升级后无变化**：前端资源有缓存，必须强刷浏览器（`Ctrl+Shift+R`）。
- **Odoo 升级后回归**：重点复核 `web/views/list/list_renderer` 的
  `props.list`（`resModel` / `records` / `editedRecord`）、行模板上的
  `t-att-data-id="record.id"` 与 `t-on-mouseover.capture`、
  以及 `@web/core/popover/popover_hook` 的 `usePopover` 签名是否变化。

---

## 变更记录规范

每次功能修改后必须更新：
- `__manifest__.py` 的 `version`（遵循 `19.0.x.y.z`）
- **`MODULE_VERSION` 三处同步**：`__manifest__.py` 的 `version`、
  `static/src/js/product_hover_list_patch.js` 的 `MODULE_VERSION`、
  `controllers/product_hover_controller.py` 的 `MODULE_VERSION`——漏改任何一处，
  前端版本自证都会误报（或该报不报），而版本自证正是本项目排查「资源/后端不同步」的主要手段。
  改完可用 `grep -rn "19\.0\." __manifest__.py static/src/js/product_hover_list_patch.js controllers/product_hover_controller.py` 自查。
- **改完 JS 必跑「命名导入 vs 导出」自查**（脚本见根 `AGENTS.md` 第 6 节）：
  本模块 `product_hover_list_patch.js` 从 `product_hover_cache.js` 命名导入 4 个 helper，
  整份重写缓存模块时漏掉一个导出就会在悬停时抛 `xxx is not a function`
  （`19.0.1.3.1` 的回归），而 `node --check` 查不出来。
- `CHANGELOG.md` 的版本说明（变更 / 影响 / 文档）
- 本 `AGENTS.md` 的相关约束（若涉及行为变更）
- `README.md` 的功能说明（若涉及用户可见功能）

版本号建议：
- 破坏性变更或架构调整：升第二位，如 `19.0.2.0.0`
- 功能新增：升第三位，如 `19.0.1.1.0`
- 修复或文档：升第四位，如 `19.0.1.0.1`
