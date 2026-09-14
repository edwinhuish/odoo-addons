# AGENTS 工作指引

> 本文档用于指导 AI 助手或新开发者在维护、扩展本 Odoo 模块时的行为规范和关键上下文。
> L1 约束段每次加载必读；L2 踩坑档案按主题触发条件加载。

---

## 模块定位

- 模块名：订单行产品悬浮卡（Sale Product Hover）
- 技术目录：`sale_product_hover`
- 新建模型：无；无 `security/ir.model.access.csv`
- 继承模型：`sale.order.line`（新增方法 `_get_product_hover_payload()` / `_get_hover_specifications()`，不新增字段）
- 新增 HTTP 控制器：`/sale_product_hover/payload`（`type="jsonrpc"`、`auth="user"`、不 `sudo`）
- 自定义前端：无自定义组件注册；patch `web/views/list/list_renderer` 的 `ListRenderer` + 一个 popover 展示组件 `ProductHoverCard`；悬停用 document 级**捕获阶段**事件委托，触屏用长按
- 主依赖：`sale`（订单行）、`stock`（`qty_available` / `is_storable`）
- 当前版本：`19.0.1.1.1`（首版 `19.0.1.0.0`；`19.0.1.0.1` / `19.0.1.0.2` 尝试修复悬停不触发；`19.0.1.1.0` 重做触发链路、补齐规格 / 数量 / 单价展示、新增触屏长按与响应式；`19.0.1.1.1` 修复 `data-id` 类型判错——**这才是悬停一直没反应的真正根因**，见 P1 陷阱 11；均待目标环境验证）

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
     编辑态（`props.list.editedRecord`）不弹浮层；popover 必须传 `setActiveElement: false`
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
   - 违反后果：越权暴露其他用户订单行的产品与单价信息

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
  - 后果：越权返回其他用户订单行的单价
  - 正确做法：以当前用户身份 browse；只返回产品展示字段与本行单价
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
| `__manifest__.py` | 版本 / 依赖（`sale` + `stock`）/ 前端 assets 登记；无 `data` 文件 |
| `models/sale_order_line.py` | `_get_product_hover_payload()`：批量装配浮层展示数据（含价格 / 数量 / 库存格式化）；`_get_hover_specifications()`：批量拼变体规格 |
| `controllers/product_hover_controller.py` | `/sale_product_hover/payload` JSON 接口（按行 id 批量返回，当前用户身份） |
| `static/src/js/product_hover_cache.js` | 模块级非 reactive 缓存 + 批量预取（去重 / 增量 / 失败重试 / 上限保护） |
| `static/src/js/product_hover_card.js` | 浮层组件：图片降级、数量与库存文案 `_t`、指针离开浮层的关闭判断 |
| `static/src/js/product_hover_list_patch.js` | patch `ListRenderer`：document 捕获级事件委托 + 触屏长按、`data-id` 反查行归属、延迟开 / 关、目标模型与编辑态判断；**顶部 `MODULE_VERSION` 必须与 `__manifest__.py` 的 `version` 同步**（用于控制台版本自证）；含 info 级诊断日志 |
| `static/src/xml/product_hover_templates.xml` | 浮层 QWeb 模板（字段布局与标签） |
| `static/src/scss/product_hover.scss` | 浮层样式（选择器统一 `.o_sph_` 前缀，含窄屏媒体查询） |
| `i18n/zh_CN.po` | 简体中文译文；含应用列表元数据条目（`base.module_sale_product_hover`），见根 `AGENTS.md` 4.8 |
| `README.md` / `CHANGELOG.md` / `AGENTS.md` | 三件套文档 |

---

## 常见扩展场景

### 增加浮层字段（例如产品分类、品牌）

1. `models/sale_order_line.py`：把字段加入 `read_fields`，并在 payload 字典里追加；
   需要格式化的（日期 / 货币 / 数量）在方法内格式化后返回字符串（**不要在 JS 里格式化**，
   也不要在 Python 里拼可翻译句子——用 `%(name)s` 占位符交给 JS `_t`）。
2. `static/src/xml/product_hover_templates.xml`：在 `dl.o_sph_fields` 里加 `dt` / `dd`；
   新标签文本会被抽取，需在 `i18n/zh_CN.po` 补条目（`code:addons/sale_product_hover/static/src/xml/product_hover_templates.xml:0`），
   标签必须写成**单行文本节点**（夹了子元素就会被切碎）。
3. 需要「数量 + 单位」这类拼接时：在 `product_hover_card.js` 加 getter，用
   `_t("%(qty)s %(uom)s", { qty, uom })`；能复用已有 `_quantityText()` 就复用。
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
  `assets loaded (版本号)` → `prefetch … N saved line(s)` → `payload: requested N, received M`
  → `hover row` → `popover opened`（中间若有 `skip: …` 会说明跳过原因）。
  没有 `assets loaded` = 资源未加载（缓存 / 未升级）；没有 `prefetch` = 列表判断未命中；
  `received 0` = 接口无数据；没有 `hover row` = 悬停事件未命中（行不在本渲染器的
  `props.list.records` 里，或鼠标事件被别的浮层遮挡）；有 `popover opened` 却看不到浮层 =
  样式 / DOM 问题。控制台无任何 `[sale_product_hover]` 输出时，先确认 `MODULE_VERSION` 与
  `__manifest__.py` 的 `version` 是否一致（资源确实重新打包了）。
- **有请求但从不弹浮层**：优先怀疑监听注册阶段——监听必须是 `document` + `{capture: true}`
  （见 P1 陷阱 6），且归属判定只能走 `_getProductHoverRecord(row)`（陷阱 7）。
  不要再加第二套监听「兜底」（陷阱 8）。
- **触屏问题**：长按不弹 = 检查 `touchstart` 监听是否还在（capture）；点一下弹出 =
  `TOUCH_MOUSE_GRACE` 时间窗是否被改小；滚动中弹出 = `TOUCH_MOVE_TOLERANCE` 是否过大。
- **浮层反复闪烁**：多为「同一行内移动」判断失效（行元素被重渲染替换），
  确认 `closest("tr.o_data_row")` 每帧拿到的是当前 DOM 元素；`onPatched` 里会把已脱离
  文档的 `_productHoverRowEl` 复位，若仍闪烁先确认这段逻辑没被删掉。
- **浮层位置抖动 / 跑到屏幕外**：`holdOnHover` 与 `extendedFlipping` 是否仍传入；
  宽度由 `.o_sph_card` 的 `width: 20rem; max-width: calc(100vw - 1.5rem)` 控制，若被改宽，
  窄屏会溢出（`.o_sph_popover` 上的 `max-width` 会被 Popover 自带的 `mw-100 !important`
  压过，别指望在那上面限制宽度，见 P4）。
- **升级后无变化**：前端资源有缓存，必须强刷浏览器（`Ctrl+Shift+R`）。
- **Odoo 升级后回归**：重点复核 `web/views/list/list_renderer` 的
  `props.list`（`resModel` / `records` / `editedRecord`）、行模板上的
  `t-att-data-id="record.id"` 与 `t-on-mouseover.capture`、
  以及 `@web/core/popover/popover_hook` 的 `usePopover` 签名是否变化。

---

## 变更记录规范

每次功能修改后必须更新：
- `__manifest__.py` 的 `version`（遵循 `19.0.x.y.z`）
- `CHANGELOG.md` 的版本说明（变更 / 影响 / 文档）
- 本 `AGENTS.md` 的相关约束（若涉及行为变更）
- `README.md` 的功能说明（若涉及用户可见功能）

版本号建议：
- 破坏性变更或架构调整：升第二位，如 `19.0.2.0.0`
- 功能新增：升第三位，如 `19.0.1.1.0`
- 修复或文档：升第四位，如 `19.0.1.0.1`
