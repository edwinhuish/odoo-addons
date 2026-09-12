# 订单行产品悬浮卡

在报价单 / 销售订单的订单行列表上，鼠标悬停某一行时弹出浮层，展示该行产品的图片、名称、型号、描述、价格与可用库存；面向外贸 SOHO 场景，报价时不必离开单据去翻产品资料。

> 模块技术名：`sale_product_hover`（无前身模块，直接全新安装）

---

## 功能概述

- 悬停订单行 → 延迟 350ms 弹出产品详情浮层，鼠标快速划过不触发
- 浮层内容：产品图片、名称、型号（`default_code`）、销售描述、产品售价、本单单价、可用库存
- 指针移开后延迟 200ms 关闭；也可直接把指针移入浮层继续阅读（移入不关闭）
- 报价单与销售订单一并覆盖（两者共用 `sale.order.line` 模型与视图）
- 每个列表页只发一次批量请求，悬停不再发请求（浏览器内缓存）
- 只作用于销售订单行；采购订单行、发票行等其他列表不受影响
- 不改官方视图、不新增字段与权限，原有行的点击 / 编辑 / 勾选 / 删除照旧

---

## 核心设计

| 设计点 | 说明 |
|--------|------|
| patch `ListRenderer` 而非继承模板 | 报价单 / 销售订单表单内的订单行使用 sale 自定义行模板 `sale.ListRenderer.RecordRow`，继承 `web.ListRenderer.RecordRow` 在该处不会生效；补丁作用于渲染器实例，对其所有子类（含自定义渲染器）一致生效，且不必改动任何视图 arch |
| document 级 `mouseover` / `mouseout` 事件委托 | `mouseenter` / `mouseleave` 不冒泡，无法做事件委托；改用可冒泡事件 + `closest("tr.o_data_row")` 定位行，再用 `this.el.contains()` 限定只处理本渲染器渲染的行。**不依赖渲染器根节点 ref**：销售订单行是 primary 继承的自定义模板（`account.SectionAndNoteListRenderer`），`t-ref="root"` 不一定存在 |
| 用 popover 服务渲染浮层 | 浮层挂在 overlay 容器，不改变列表 DOM，因此不干扰原有行交互；`holdOnHover` 让指针进入浮层后位置锁定，避免跟随抖动；`setActiveElement: false` 保证悬停不抢占页面焦点 |
| 后端一次装配展示数据 | 前端不解析 many2one 数据格式、不做货币格式化：`_get_product_hover_payload()` 用 `formatLang` 按用户语言与货币精度直接返回可展示字符串，前端零格式化逻辑 |
| 每页一次批量请求 + 非 reactive 缓存 | 列表挂载与每次 DOM 更新后按行 id 差集预取；缓存放**模块级 `Map`**（挂到 reactive 对象会触发 Owl 重渲染循环，见 `product_card_view` 的 P1 踩坑） |
| 只读、不提权 | 控制器以当前用户身份读取（不 `sudo`），沿用产品与订单行的既有记录规则与权限 |
| 编辑态不弹浮层 | `props.list.editedRecord` 存在时不弹，避免遮挡正在输入的单元格 |
| 未保存的新行跳过 | 新行尚无数据库 id，无展示数据；保存后列表刷新即自动纳入预取（不报错、不弹空浮层） |
| 只依赖 `sale` + `stock` | `sale` 提供订单行模型；`stock` 提供 `qty_available`。不依赖 `web`（内建），不为展示图片依赖 `product_image`（用原生主图） |

---

## 模块资源

> 本模块以前端为主：**无新建模型、无新建字段、无权限文件**，因此没有 `security/`、`data/`、`views/`；展示数据由既有模型的扩展方法 + 一个内部 JSON 接口提供。

| 文件 | 职责 |
|------|------|
| `models/sale_order_line.py` | `sale.order.line._get_product_hover_payload()`：一次批量装配全部展示数据 |
| `controllers/product_hover_controller.py` | `POST /sale_product_hover/payload`（`type="jsonrpc"`、`auth="user"`）：按行 id 返回展示数据 |
| `static/src/js/product_hover_cache.js` | 模块级非 reactive 缓存 + 批量预取（去重 / 增量 / 失败可重试） |
| `static/src/js/product_hover_card.js` | 浮层组件（图片失败降级占位、库存文案、指针离开处理） |
| `static/src/js/product_hover_list_patch.js` | patch `ListRenderer`：事件委托、延迟开 / 关、仅 `sale.order.line` 生效 |
| `static/src/xml/product_hover_templates.xml` | 浮层 QWeb 模板 |
| `static/src/scss/product_hover.scss` | 浮层样式（选择器统一 `.o_sph_` 前缀） |
| `i18n/zh_CN.po` | 简体中文译文（含应用列表元数据） |

### 接口 payload 字段（`/sale_product_hover/payload`）

入参：`line_ids`（当前列表页可见的 `sale.order.line` id 数组）。
返回：`{order_line_id: {…}}`，每个值为：

| 字段 | 类型 | 说明 |
|------|------|------|
| `line_id` | `int` | 订单行 id |
| `product_id` | `int` | 产品 id |
| `name` | `char` | 产品显示名（`display_default_code=False`，不带 `[参考号]` 前缀） |
| `reference` | `char` | 型号 / 内部参考号（`default_code`） |
| `image_url` | `char` | `/web/image/product.product/<id>/image_256` |
| `description` | `text` | 销售描述（`description_sale`），无则为空串 |
| `sales_price_text` | `char` | 产品售价，按公司币种与用户语言格式化 |
| `order_price_text` | `char` | 本单单价，按订单币种格式化 |
| `show_order_price` | `bool` | 本单单价与产品售价不同（币种或数值）时为真 |
| `qty_available_text` | `char` | 可用库存数量（`Product Unit` 精度）；不跟踪库存的产品为空串 |
| `uom_name` | `char` | 计量单位名 |

---

## 视图

无新增视图，也不修改任何官方视图：

- 只作用于 `sale.order.line` 的列表（含报价单 / 销售订单表单内的订单行、销售订单行列表视图），由渲染器补丁识别模型决定。
- 其他模型的列表渲染器不做任何处理（补丁在非目标模型上直接返回）。

---

## 交互说明

| 行为 | 表现 |
|------|------|
| 悬停订单行 | 350ms 后弹出浮层（延迟用于过滤鼠标快速划过） |
| 行内移动鼠标 | 不重开、不闪烁（按行元素判断） |
| 指针移出行 | 200ms 后关闭；若这期间指针移入浮层则取消关闭 |
| 指针移入浮层 | 浮层保留；移出浮层（且未回到该行）立即关闭 |
| 指针从浮层移回该行 | 浮层关闭后重新计时打开，不会卡死 |
| 指针停在浮层内 | 位置锁定（`holdOnHover`），不随页面滚动 / 重排抖动 |
| 行处于编辑态 | 不弹浮层（正在输入时不遮挡） |
| 未保存的新行 | 悬停不弹浮层（无数据库 id），保存后恢复 |
| 产品无图片 / 图片 404 | 显示占位图标，不出现破图 |
| 服务类产品（不跟踪库存） | 不展示「可用库存」一行 |
| 本单单价 = 产品售价 | 不重复展示「本单单价」一行 |

---

## 国际化（i18n）

- **源语言：英文（`en_US`）**，源码（Python / JS / XML）里一律写英文；中文只出现在 `i18n/zh_CN.po` 的 `msgstr`。
- 覆盖范围：
  - 浮层 QWeb 模板文本（`Sales Price` / `Order Price` / `On Hand`）→ `code:addons/sale_product_hover/static/src/xml/product_hover_templates.xml:0`
  - JS 库存文案 `%(qty)s %(uom)s` → `code:addons/sale_product_hover/static/src/js/product_hover_card.js:0`
  - 产品名 / 型号 / 描述 / 单位名是**数据**，随产品记录语言展示，不进 po。
- 价格与库存数字由后端 `formatLang` 按用户语言格式化，无需前端 `locale` 处理。
- 占位符统一 `%(name)s` 命名形式，禁止按位置拼接。
- **应用列表（Apps）元数据**：模块名 / 摘要 / 描述的中文由 `i18n/zh_CN.po` 的 `model:ir.module.module,shortdesc|summary|description:base.module_sale_product_hover` 三条提供；分类 `Sales/Sales` 是官方分类，沿用 `base` 自带译文，不重复翻译。改 `__manifest__.py` 的 `name` / `summary` / `description` 时必须同步这三条的 `msgid`，规范见根 [`AGENTS.md`](../AGENTS.md) 4.8。
- 改动流程：改英文源文本 → 同步 `i18n/zh_CN.po` → `-u` 升级 + **强刷浏览器**（前端术语有缓存），英文与中文各验一遍。

---

## 依赖

- `sale`：提供 `sale.order.line`（报价单与销售订单共用）与订单币种、单价。
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
- 编辑订单行时会暂停浮层显示，保存 / 退出编辑后恢复。

---

## 验证清单

> 验收日期：待定，目标环境**待验证**。

| 验证项 | 期望 | 结果 |
|--------|------|------|
| `-u sale_product_hover` 升级 | 无报错，`/sale_product_hover/payload` 可访问 | 待验 |
| 报价单订单行悬停 | 浮层显示图片 / 名称 / 型号 / 描述 / 售价 / 本单单价 / 可用库存 | 待验 |
| 销售订单订单行悬停 | 同报价单表现一致 | 待验 |
| 移开与移入 | 移开延迟关闭；移入浮层不关闭；从浮层移回行可重开 | 待验 |
| 原有操作不受影响 | 点击进入、内联编辑、勾选、删除照旧；编辑态不弹浮层 | 待验 |
| 非目标列表 | 采购订单行、发票行不出现浮层 | 待验 |
| 边界情况 | 新行不弹；无图显示占位；服务类产品无库存行 | 待验 |
| 双语 | 默认英文；装 `zh_CN` 并切换后文案为中文 | 待验 |
| 控制台 | 无 JS 报错、无重复请求 | 待验 |

### 异常情况与处理

- 浮层不出现：确认浏览器控制台是否有 `/sale_product_hover/payload` 报错；若 403，检查当前用户对产品 / 该订单行的读权限。
- 浮层一直不消失：多为指针停在浮层内（按设计保留），把指针移出浮层即可。
- 升级后界面无变化：前端资源有缓存，必须强刷浏览器（`Ctrl+Shift+R`）。

### 后续维护

- 增减浮层字段：改 `models/sale_order_line.py` 的 payload 与 `static/src/xml/product_hover_templates.xml`（必要时同步 po）。
- 调整延迟 / 位置 / 样式：`static/src/js/product_hover_list_patch.js` 顶部常量与 `static/src/scss/product_hover.scss`。
- 扩大适用范围（如采购订单行）：需把 `sale.order.line` 的 payload 方法抽象到共用模型，并在补丁里扩展目标模型清单。
- 悬停无浮层时的排查顺序（用 `?debug=1` 或 `?debug=assets` 打开页面；日志为 `info` 级别，控制台默认可见）：
  1. 页面加载时应有 `[sale_product_hover] assets loaded (19.0.1.0.2)` —— **看不到这行**说明浏览器
     仍在用旧缓存 / assets 未重建：`-u sale_product_hover` 后**强刷浏览器**（`Ctrl+Shift+R`）。
     括号内版本应与 `__manifest__.py` 的 `version` 一致；
  2. 列表加载 / 翻页时应有 `[sale_product_hover] prefetch sale.order.line: N saved line(s)` 与
     `[sale_product_hover] payload: requested N, received M`：**没有 prefetch** 说明当前不是
     `sale.order.line` 列表或补丁未生效；**`received 0`** 说明接口没返回数据，查服务端日志
     `sale_product_hover: unable to build hover payload`；
  3. 悬停订单行时应依次出现 `hover row <id>` → `popover opened for line <id>`：
     - 完全没有 `hover row` → 悬停事件未命中（行不在本渲染器内或被其它逻辑拦截）；
     - 有 `hover row` 但没有 `popover opened` → 会同时输出 `skip: …` 说明跳过原因
       （未保存的新行 / 取不到数据 / 指针已移开）；
     - 有 `popover opened` 仍看不到浮层 → 查 Elements 里是否存在 `.o_popover .o_sph_card`，
       以及是否紧接着出现 `popover closed`（被误关闭）。

---

## 许可证

LGPL-3
