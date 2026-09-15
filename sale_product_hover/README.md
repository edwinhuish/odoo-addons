# 订单行产品悬浮卡

在报价单 / 销售订单的订单行列表上，鼠标悬停某一行（触屏设备为长按）时弹出浮层，展示该行产品的图片、名称、型号、规格、描述、数量、单价与可用库存；面向外贸 SOHO 场景，报价时不必离开单据去翻产品资料。

> 模块技术名：`sale_product_hover`（无前身模块，直接全新安装）

---

## 功能概述

- 悬停订单行 → 延迟 300ms 弹出产品详情浮层，鼠标快速划过不触发
- 浮层内容：产品图片、名称、型号（`default_code`）、规格（变体属性，如 `颜色: 红, 尺寸: L`）、销售描述、订单数量（含单位）、单价（订单币种）、产品售价（与单价不同时才显示）、可用库存
- **跟随鼠标**：浮层贴在光标右下随鼠标移动；指针移入浮层后停止跟随（方便阅读），移开后延迟 200ms 关闭
- **新增产品行也能预览**：刚加进订单、尚未保存的行同样能悬停看详情（不必先保存）；数量 / 单位 / 单价改动后浮层内容随之更新。**这条路径直接从产品取数**（订单行还没落库，服务端查不到），因此与服务端版本无关
- **自适应**：右侧放不下自动翻到光标左侧，下方放不下自动上移贴边，窄屏下浮层随视口收窄、图片与字号收紧
- **不抢原生 tooltip**：悬停订单行时行内单元格的黑色原生提示会被屏蔽，只显示本模块的浮层
- **触屏设备**没有 hover，改为**长按订单行 500ms** 弹出同一浮层（不阻止滚动，也不影响原本的点击打开）
- 报价单与销售订单一并覆盖（两者共用 `sale.order.line` 模型与视图）
- 每个列表页只发一次批量请求，悬停不再发请求（浏览器内缓存）
- 只作用于销售订单行；采购订单行、发票行等其他列表不受影响
- 不改官方视图、不新增字段与权限，原有行的点击 / 编辑 / 勾选 / 删除照旧

---

## 核心设计

| 设计点 | 说明 |
|--------|------|
| patch `ListRenderer` 而非继承模板 | 报价单 / 销售订单表单内的订单行使用 sale 自定义行模板 `sale.ListRenderer.RecordRow`（← `account.SectionAndNoteListRenderer.RecordRow` ← `web.ListRenderer.RecordRow`），继承 `web.ListRenderer.RecordRow` 在该处不会生效；补丁作用于渲染器实例，对其所有子类（含自定义渲染器）一致生效，且不必改动任何视图 arch |
| document 级**捕获阶段**事件委托 | `mouseenter` / `mouseleave` 不冒泡，无法委托；改用可冒泡的 `mouseover` / `mouseout`，并在**捕获阶段**注册：先于行内业务监听触发，不会被 `stopPropagation` 吃掉，也与渲染器根节点 ref / 挂载时机无关（自定义渲染器的 `t-ref="root"` 不可靠，这是 `19.0.1.0.1` 之前「悬停完全没反应」的根因） |
| 行归属用 `data-id` 反查，不用 `this.el.contains()` | 行的 `data-id`（Owl datapoint id）能在 `props.list.records` 里查到就说明是本渲染器的行：既不依赖根元素结构，也天然排除其他模型列表的行。**注意 `data-id` 与 `record.id` 是字符串**（`"datapoint_42"`），必须按字符串比较，不能 `Number()` 化（`Number("datapoint_42")` 是 `NaN`，会静默失效——这是 `19.0.1.1.0` 及之前悬停完全没反应的真正原因）；`record.resId` 才是数据库 id（数字） |
| 触屏长按 | `touchstart` 计时 500ms，`touchmove` 位移超 10px 视为滚动并取消；长按触发后吃掉紧随的这次 `click`（长按是"看详情"，不是"打开记录"）；手势结束后 800ms 内忽略浏览器补发的 mouse 事件，避免"点一下弹两次" |
| 用 popover 服务渲染浮层 | 浮层挂在 overlay 容器，不改变列表 DOM，因此不干扰原有行交互；`holdOnHover` 让指针进入浮层后位置锁定；`setActiveElement: false` 保证悬停不抢占页面焦点 |
| 浮层位置自己算（跟随鼠标） | popover 的目标仍是**行**（`getPopoverForTarget(row)` 才能查到浮层、移入浮层不关闭），但落点由 `_positionProductHover()` 计算：贴在光标右下，右/下放不下就翻到光标左侧 / 上移贴边，视口装不下再收紧 `maxHeight`。可行性来自 Odoo 的 `reposition()`——它把浮层设成 `position: fixed` 并直接写 `left/top`（视口坐标），所以补丁可以直接改写 `left/top` 跟随 `mousemove`（`requestAnimationFrame` 合帧）；每次 Odoo 重定位后回调 `onPositioned`，在那里再套用一次光标位置即可 |
| 屏蔽行内原生 tooltip | Odoo 的 tooltip 服务挂在 `document.body` 的**捕获阶段** `mouseenter` 上；补丁在更外层的 `document` 捕获阶段拦截该事件，**只在该行确实有本模块浮层数据时** `stopPropagation()`，原生黑色提示不再弹出，其余行与元素不受影响 |
| 已保存行的数据由后端一次装配 | 前端不解析 many2one 数据格式、不做货币 / 数量格式化：`_get_product_hover_payload()` 用 `formatLang` 按用户语言与货币（单位）精度直接返回可展示字符串；规格由 `product.template.attribute.value.display_name` 拼成（属性名与取值都是产品数据，随产品记录语言展示，不进 po） |
| **新行直接从产品取数** | 未保存的订单行在服务端**根本不存在**，按行 id 反查必然失败；它要展示的东西来源其实很干净：**产品侧**（名称 / 型号 / 规格 / 描述 / 图片 / 产品售价 / 可用库存）按 `product_id` 读 `product.product`，**行侧**（数量 / 单位 / 单价 / 币种）就是表单里正在编辑的值。因此由 `product_hover_product.js` 用**标准 ORM**（`searchRead`，任何后端版本可用、应用记录规则）读产品并装配，`formatFloat` / `formatMonetary` 与后端 `formatLang` 等价 —— 不依赖自研接口，也**不需要服务端升级** |
| 每页一次批量请求 + 非 reactive 缓存 | 列表挂载与每次 DOM 更新后按行 id 差集预取（新行按 `product_id` 批量读产品、同一产品多行共用缓存）；缓存放**模块级 `Map`**（挂到 reactive 对象会触发 Owl 重渲染循环，见 `product_card_view` 的 P1 踩坑），并设上限避免长时间使用后无界增长 |
| 只读、不提权 | 控制器以当前用户身份读取（不 `sudo`）；新行走标准 ORM（`searchRead` 应用记录规则、自动剔除读不到的产品），均沿用产品与订单行的既有权限 |
| 编辑态避让只针对已保存行 | 正在内联编辑的**已保存**行不弹（避免遮挡正在改的字段）；**未保存的新行不受限**——Odoo 里 `Record.isInEdition` 对 `!resId` 恒为真（`config.mode === "edit" \|\| !resId`），新行一加进列表就是 `editedRecord`，若照旧一刀切则新增产品永远没有预览，而且只要列表里有一条新行，其它已保存行也会被一起挡掉 |
| 新行的实时性靠取值签名 | 新行按 `产品\|数量\|单位\|单价\|币种` 生成签名；产品数据已缓存且取值没变时命中上一次结果（**悬停不发请求**），变了才重新装配——`onPatched` 随表单输入刷新，悬停时再兜一次，保证浮层跟着输入走 |
| 只依赖 `sale` + `stock` | `sale` 提供订单行模型；`stock` 提供 `qty_available`。不依赖 `web`（内建），不为展示图片依赖 `product_image`（用原生主图） |

---

## 模块资源

> 本模块以前端为主：**无新建模型、无新建字段、无权限文件**，因此没有 `security/`、`data/`、`views/`；已保存行的展示数据由既有模型的扩展方法 + 一个内部 JSON 接口提供，未保存的新行由前端直接查产品。

| 文件 | 职责 |
|------|------|
| `models/sale_order_line.py` | **只服务已保存行**：`_get_product_hover_payload()` → `_build_hover_payload()` 统一装配；`_get_hover_specifications()` 拼变体规格 |
| `controllers/product_hover_controller.py` | `POST /sale_product_hover/payload`（`type="jsonrpc"`、`auth="user"`）：按行 id 返回展示数据，并回显 `__server_version` 供前端做版本自证 |
| `static/src/js/product_hover_product.js` | **未保存新行的取数与装配**：按 `product_id` 用标准 ORM 读产品（含变体规格、可用库存），行的数量 / 单价由表单当前值提供，用 `formatFloat` / `formatMonetary` 装配 |
| `static/src/js/product_hover_cache.js` | 数据层：已保存行走接口（按行 id 去重）、新行走产品缓存 + 取值签名；模块级非 reactive 缓存、失败可重试 / 上限保护、服务端版本探测 |
| `static/src/js/product_hover_card.js` | 浮层组件（图片失败降级占位、数量文案、指针离开处理） |
| `static/src/js/product_hover_list_patch.js` | patch `ListRenderer`：捕获阶段事件委托、触屏长按、新行的取数上下文（`_getProductHoverContext`）、编辑态避让、延迟开 / 关、仅 `sale.order.line` 生效 |
| `static/src/xml/product_hover_templates.xml` | 浮层 QWeb 模板 |
| `static/src/scss/product_hover.scss` | 浮层样式（选择器统一 `.o_sph_` 前缀，含窄屏媒体查询） |
| `i18n/zh_CN.po` | 简体中文译文（含应用列表元数据） |

### 卡片 payload 字段

**两条取数路径产出同一种 payload**（卡片模板与组件不关心数据来源）：

- **已保存行** → 接口 `POST /sale_product_hover/payload`（入参 `line_ids`，返回 `{行id: payload}`
  外加保留键 `__server_version`；空 `line_ids` 只回版本，供前端探测服务端是否已升级）；
- **未保存的新行** → 前端 `product_hover_product.js` 按 `product_id` 用标准 ORM 读产品后装配
  （不经过本模块的接口，**不需要服务端升级**）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `line_id` | `int` \| `char` | 该条数据的键（已保存行 → 行 id；新行 → Owl datapoint id 字符串） |
| `product_id` | `int` | 产品 id |
| `name` | `char` | 产品显示名（按 `display_default_code=False` 口径去掉 `[参考号] ` 前缀） |
| `reference` | `char` | 型号 / 内部参考号（`default_code`） |
| `specification` | `char` | 规格：变体属性值的 `display_name` 用 `", "` 连接（如 `颜色: 红, 尺寸: L`）；无变体属性为空串 |
| `image_url` | `char` | `/web/image/product.product/<id>/image_256` |
| `description` | `text` | 销售描述（`description_sale`），无则为空串 |
| `qty_ordered_text` | `char` | 订单数量，按 `Product Unit` 精度与用户语言格式化（**不含单位**，单位由 `uom_name` 提供） |
| `uom_name` | `char` | 订单行的计量单位名（`product_uom_id.name`） |
| `unit_price_text` | `char` | 本单单价，按订单币种格式化 |
| `list_price_text` | `char` | 产品售价，按公司币种格式化 |
| `show_list_price` | `bool` | 产品售价与本单单价不同（币种或数值）时为真，前端才展示该行 |
| `qty_available_text` | `char` | 可用库存数量（`Product Unit` 精度）；不跟踪库存的产品为空串 |
| `available_uom_name` | `char` | 可用库存的计量单位名（`qty_available` 是产品默认单位口径） |

> 数量 / 价格 / 库存都是**已格式化的字符串**：已保存行由后端 `formatLang` 生成，新行由前端
> `formatFloat` / `formatMonetary` 生成（同一套用户语言与货币精度，输出一致）。
> 前端只做「数量 + 单位」的可翻译拼接（`_t("%(qty)s %(uom)s")`）。

---

## 视图

无新增视图，也不修改任何官方视图：

- 只作用于 `sale.order.line` 的列表（含报价单 / 销售订单表单内的订单行、销售订单行列表视图），由渲染器补丁识别模型决定。
- 其他模型的列表渲染器不做任何处理（补丁在非目标模型上直接返回）。

---

## 交互说明

| 行为 | 表现 |
|------|------|
| 悬停订单行 | 300ms 后弹出浮层（延迟用于过滤鼠标快速划过） |
| 行内移动鼠标 | 浮层跟随光标移动，不重开、不闪烁 |
| 行内元素的原生 tooltip | 被屏蔽，只显示本模块浮层（不影响其他行与其他元素） |
| 指针移出行 | 200ms 后关闭；若这期间指针移入浮层则取消关闭 |
| 指针移入浮层 | 停止跟随并锁定位置，可从容阅读；移出浮层（且未回到该行）立即关闭 |
| 指针从浮层移回该行 | 浮层关闭后重新计时打开，不会卡死 |
| 触屏长按订单行 | 500ms 后弹出浮层，停在手指位置；长按不会同时打开记录 |
| 触屏滚动列表 | 长按被取消（位移超 10px） |
| 触屏点按别处 | 浮层关闭（popover 的点击外部关闭） |
| 已保存行处于内联编辑 | 不弹浮层（正在改字段时不遮挡） |
| 新增产品行（未保存） | 正常弹浮层（悬停 / 触屏长按均可）；改数量 / 单位 / 单价后再悬停，浮层内容同步更新 |
| 新增行还没选产品 | 不弹浮层（没有可展示的产品），选了产品后可预览 |
| 新增行保存后 | 自动切到「已保存行」的取数路径，表现不变 |
| 产品无图片 / 图片 404 | 显示占位图标，不出现破图 |
| 服务类产品（不跟踪库存） | 不展示「可用库存」一行 |
| 本单单价 = 产品售价 | 不重复展示「产品售价」一行 |
| 浮层贴近视口边缘 | 右侧放不下翻到光标左侧，下方放不下上移贴边，视口装不下则内部滚动 |

---

## 国际化（i18n）

- **源语言：英文（`en_US`）**，源码（Python / JS / XML）里一律写英文；中文只出现在 `i18n/zh_CN.po` 的 `msgstr`。
- 覆盖范围：
  - 浮层 QWeb 模板文本（`Quantity` / `Unit Price` / `Sales Price` / `On Hand`）→ `code:addons/sale_product_hover/static/src/xml/product_hover_templates.xml:0`
  - JS 数量文案 `%(qty)s %(uom)s` → `code:addons/sale_product_hover/static/src/js/product_hover_card.js:0`
  - 产品名 / 型号 / 规格 / 描述 / 单位名是**数据**，随产品记录语言展示，不进 po（规格的属性名与取值同样是数据）
- 价格、数量、库存数字由后端 `formatLang` 按用户语言格式化，无需前端 `locale` 处理。
- 占位符统一 `%(name)s` 命名形式，禁止按位置拼接。
- **应用列表（Apps）元数据**：模块名 / 摘要 / 描述的中文由 `i18n/zh_CN.po` 的 `model:ir.module.module,shortdesc|summary|description:base.module_sale_product_hover` 三条提供；分类 `Sales/Sales` 是官方分类，沿用 `base` 自带译文，不重复翻译。改 `__manifest__.py` 的 `name` / `summary` / `description` 时必须同步这三条的 `msgid`，规范见根 [`AGENTS.md`](../AGENTS.md) 4.8。
- 改动流程：改英文源文本 → 同步 `i18n/zh_CN.po` → `-u` 升级 + **强刷浏览器**（前端术语有缓存），英文与中文各验一遍。

---

## 依赖

- `sale`：提供 `sale.order.line`（报价单与销售订单共用）与订单币种、单价、数量。
- `stock`：提供 `qty_available`（可用库存）与 `is_storable`（是否跟踪库存）。
- 内建 `web`：popover 服务、列表渲染器、`rpc`，无需额外声明。
- **不依赖** `product_image`（浮层用产品原生主图 `image_256`）、`product_reference`（型号取原生 `default_code`）。

---

## 安装与使用

### 全新安装

1. 将 `sale_product_hover` 目录放入 Odoo 19 的 `addons_path`
2. 更新应用列表后安装模块：**订单行产品悬浮卡**
3. 打开任意报价单 / 销售订单：把鼠标停在订单行上，浮层自动弹出

```bash
odoo -d <db> -i sale_product_hover --stop-after-init   # 首次安装
odoo -d <db> -u sale_product_hover --stop-after-init   # 代码改动后升级
```

### 操作

- 悬停即用，无需开关；浮层是只读的，不会修改任何数据。
- 想要更长的阅读时间：把指针移入浮层内即可（浮层不会自动消失）。
- 触屏设备（平板 / 手机）：长按订单行弹出浮层，点别处关闭。
- 编辑订单行时会暂停浮层显示，保存 / 退出编辑后恢复。

---

## 验证清单

> 验收日期：待定，目标环境**待验证**。

| 验证项 | 期望 | 结果 |
|--------|------|------|
| `-u sale_product_hover` 升级 | 无报错，`/sale_product_hover/payload` 可访问 | 待验 |
| 报价单订单行悬停 | 浮层显示图片 / 名称 / 型号 / 规格 / 描述 / 数量 / 单价 / 售价 / 可用库存 | 待验 |
| 销售订单订单行悬停 | 同报价单表现一致 | 待验 |
| 含变体产品 | 规格行显示 `颜色: 红, 尺寸: L` 之类；无变体产品的规格行不显示 | 待验 |
| 数量与单位 | 数量按订单行单位显示（含单位名） | 待验 |
| 移开与移入 | 移开延迟关闭；移入浮层不关闭；从浮层移回行可重开 | 待验 |
| 触屏长按 | 平板 / 手机长按订单行弹出浮层；滚动列表不弹出；长按不会打开记录 | 待验 |
| 窄屏 | 浮层宽度不超出屏幕，空间不足时自动换侧 | 待验 |
| 原有操作不受影响 | 点击进入、内联编辑、勾选、删除照旧；编辑态不弹浮层 | 待验 |
| 非目标列表 | 采购订单行、发票行不出现浮层 | 待验 |
| 边界情况 | 无图显示占位；服务类产品无库存行；新行未选产品不弹 | 待验 |
| 新增产品行悬停 | 未保存的新行也能弹浮层，内容与保存后一致；改数量 / 单价后浮层同步更新 | 待验 |
| 双语 | 默认英文；装 `zh_CN` 并切换后标签为「数量 / 单价 / 产品售价 / 可用库存」 | 待验 |
| 控制台 | 无 JS 报错、无重复请求 | 待验 |

### 异常情况与处理

- 浮层不出现：确认浏览器控制台是否有 `/sale_product_hover/payload` 报错；若 403，检查当前用户对产品 / 该订单行的读权限。
- **`Uncaught TypeError: getLineHoverPayload is not a function`**（`19.0.1.3.1` 的回归，已在
  `19.0.1.3.2` 修复）：页面加载时会有配套的
  `assets are inconsistent: … missing from product_hover_cache.js exports`。
  升级到 `19.0.1.3.2` + 强刷即可；若在自研改动后又出现，说明 JS 的命名导入与导出不一致
  （自查脚本见根 `AGENTS.md` 第 6 节）。
- **排障第一步：看那一行 `self-check`**（打开订单页时输出，每会话一次）：
  - `[sale_product_hover] self-check: assets 19.0.1.4.0, server 19.0.1.4.0 (ok)` → 两端一致；
  - `… server NOT UPGRADED → …` → **服务端 Python 没升级**（只影响**已保存行**的取数），
    执行 `odoo -d <db> -u sale_product_hover --stop-after-init` 并**重启服务进程**，再强刷浏览器。
    > 为什么常见「前端新、后端旧」：`?debug=assets` 模式下 JS / SCSS 会用文件 mtime 参与
    > assets 校验和，改完**自动重建、不需要 `-u`**；而 Python 必须 `-u`，且运行中的进程
    > 内存里还是旧代码，**必须重启进程**才生效。
- **已保存行不弹浮层 / 字段缺失**：看 `self-check` 是否 `NOT UPGRADED`（见上）；
  服务端日志里会有 `sale_product_hover: product … not found or not readable`（产品读不到）
  或 `unable to build hover payload`（装配异常）。
- **新增的行不弹浮层**：这条路径**不经过服务端接口**（按 `product_id` 在前端直接查产品），
  所以与服务端版本无关。控制台里 `skip:` 会说明原因：
  - `新行还没选产品（或为分节 / 备注行）` → 该行确实没有产品可展示；
  - `skip: product <id> not found or not readable` → 产品不存在或当前用户读不到；
  - `unable to build preview data from the product` + 错误 → ORM 读取失败（看错误详情）。
  > `19.0.1.3.1`~`19.0.1.3.3` 曾用「把新行当订单行发到后端」的方案，那段历史问题
  > （缺数据行永久失效、依赖服务端升级）随 `19.0.1.4.0` 改为前端直接查产品而消失。
- 预取正常（有 `prefetch` / `payload` 日志）但悬停毫无反应、连 `hover row` 都没有：
  说明行归属判定没命中。先在控制台选中订单行元素，看 `$0.dataset.id`（形如 `datapoint_42`）
  与 `record.id` —— 两者都是**字符串**，绝不能用 `Number()` 转换（详见 `AGENTS.md` → P1 陷阱 11）。
- 浮层一直不消失：多为指针停在浮层内（按设计保留），把指针移出浮层即可。
- 升级后界面无变化：前端资源有缓存，必须强刷浏览器（`Ctrl+Shift+R`）。

### 后续维护

- 增减浮层字段：改 `models/sale_order_line.py` 的 payload 与 `static/src/xml/product_hover_templates.xml`（必要时同步 po）。
- 调整延迟 / 位置 / 样式：`static/src/js/product_hover_list_patch.js` 顶部常量与 `static/src/scss/product_hover.scss`。
- 关闭触屏长按：删掉 `product_hover_list_patch.js` 里 `touchstart` / `touchmove` / `touchend` / `touchcancel` 四个监听与对应方法即可（互不影响）。
- 扩大适用范围（如采购订单行）：需把 `sale.order.line` 的 payload 方法抽象到共用模型，并在补丁里扩展目标模型清单。
- 悬停无浮层时的排查顺序（用 `?debug=1` 或 `?debug=assets` 打开页面；日志为 `info` 级别，控制台默认可见）：
  1. 页面加载时应有 `[sale_product_hover] assets loaded (19.0.1.3.3)` —— **看不到这行**说明浏览器
     仍在用旧缓存 / assets 未重建：`-u sale_product_hover` 后**强刷浏览器**（`Ctrl+Shift+R`）。
     括号内版本应与 `__manifest__.py` 的 `version` 一致；紧接着还会有一行
     `self-check: assets X, server Y`，**先看这行**判断前后端是否同步；
  2. 列表加载 / 翻页 / 表单改动时应有
     `[sale_product_hover] prefetch sale.order.line: N saved / M draft line(s)` 与
     `[sale_product_hover] payload: requested N saved line(s), received M`
     （新行则打印 `requested N draft line(s), received M`）：**没有 prefetch** 说明当前不是
     `sale.order.line` 列表或补丁未生效；**`received 0`** 说明接口没返回数据，查服务端日志
     `sale_product_hover: unable to build hover payload`；
  3. 悬停订单行时应依次出现 `hover row <id>` → `popover opened for line <id>`：
     - 完全没有 `hover row` → 悬停事件未命中（行不在本渲染器的记录里）；
     - 有 `hover row` 但没有 `popover opened` → 会同时输出 `skip: …` 说明跳过原因
       （未保存的新行 / 该行没有可展示数据 / 指针已移开）；
     - 有 `popover opened` 仍看不到浮层 → 查 Elements 里是否存在 `.o_popover .o_sph_card`，
       以及是否紧接着出现 `popover closed`（被误关闭）。

---

## 许可证

LGPL-3
