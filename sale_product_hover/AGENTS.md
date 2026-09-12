# AGENTS 工作指引

> 本文档用于指导 AI 助手或新开发者在维护、扩展本 Odoo 模块时的行为规范和关键上下文。
> L1 约束段每次加载必读；L2 踩坑档案按主题触发条件加载。

---

## 模块定位

- 模块名：订单行产品悬浮卡（Sale Product Hover）
- 技术目录：`sale_product_hover`
- 新建模型：无；无 `security/ir.model.access.csv`
- 继承模型：`sale.order.line`（新增方法 `_get_product_hover_payload()`，不新增字段）
- 新增 HTTP 控制器：`/sale_product_hover/payload`（`type="jsonrpc"`、`auth="user"`、不 `sudo`）
- 自定义前端：无自定义组件注册；patch `web/views/list/list_renderer` 的 `ListRenderer` + 一个 popover 展示组件 `ProductHoverCard`
- 主依赖：`sale`（订单行）、`stock`（`qty_available` / `is_storable`）
- 当前版本：`19.0.1.0.0`（首版，待目标环境验证）

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
     `mouseover` / `mouseout` 只读事件，不得 `preventDefault` / 停止传播；
     编辑态（`props.list.editedRecord`）不弹浮层
   - 违反后果：点击进入、内联编辑、勾选、删除等原有操作被干扰或出现闪烁

4. **悬停不发请求**
   - 数据在列表挂载 / DOM 更新时按行 id 差集批量预取（`prefetchLineHoverPayload`），
     悬停只读缓存；缓存必须是**模块级非 reactive 容器**
   - 违反后果：每次悬停产生请求；或缓存挂到 reactive 对象上触发 Owl 重渲染 / 重载循环导致页面卡死

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
- 正确做法：`await` 之后必须重新校验 `this._productHoverRowEl === row` 再 `open`

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

## 文件职责

| 文件 | 职责 |
|------|------|
| `__manifest__.py` | 版本 / 依赖（`sale` + `stock`）/ 前端 assets 登记；无 `data` 文件 |
| `models/sale_order_line.py` | `_get_product_hover_payload()`：批量装配浮层展示数据（含价格 / 库存格式化） |
| `controllers/product_hover_controller.py` | `/sale_product_hover/payload` JSON 接口（按行 id 批量返回，当前用户身份） |
| `static/src/js/product_hover_cache.js` | 模块级非 reactive 缓存 + 批量预取（去重 / 增量 / 失败重试） |
| `static/src/js/product_hover_card.js` | 浮层组件：图片降级、库存文案 `_t`、指针离开浮层的关闭判断 |
| `static/src/js/product_hover_list_patch.js` | patch `ListRenderer`：事件委托、延迟开 / 关、目标模型与编辑态判断 |
| `static/src/xml/product_hover_templates.xml` | 浮层 QWeb 模板（字段布局与标签） |
| `static/src/scss/product_hover.scss` | 浮层样式（选择器统一 `.o_sph_` 前缀） |
| `i18n/zh_CN.po` | 简体中文译文；含应用列表元数据条目（`base.module_sale_product_hover`），见根 `AGENTS.md` 4.8 |
| `README.md` / `CHANGELOG.md` / `AGENTS.md` | 三件套文档 |

---

## 常见扩展场景

### 增加浮层字段（例如产品分类、品牌）

1. `models/sale_order_line.py`：把字段加入 `read_fields`，并在 payload 字典里追加；
   需要格式化的（日期 / 货币）在方法内格式化后返回字符串。
2. `static/src/xml/product_hover_templates.xml`：在 `dl.o_sph_fields` 里加 `dt` / `dd`；
   新标签文本会被抽取，需在 `i18n/zh_CN.po` 补条目（`code:addons/sale_product_hover/static/src/xml/product_hover_templates.xml:0`）。
3. 无需改 JS：浮层组件只是把 `props.payload` 透传给模板。

### 支持采购订单行（`purchase.order.line`）

1. 把 `_get_product_hover_payload` 的实现抽到共用抽象（或在 `purchase.order.line` 上实现同名方法，
   把公共逻辑提到 helper / mixin），字段口径保持一致。
2. `product_hover_list_patch.js` 的 `TARGET_MODEL` 改为目标模型集合，
   `_isProductHoverList()` 与预取 / 悬停判断同步调整。
3. 采购行有 `product_qty` / `price_unit` / `date_planned` 等不同字段，
   payload 与模板需按模型分支（建议按模型返回 `kind`，模板用 `t-if` 分支）。

### 调整交互参数

- 弹出 / 关闭延迟：`product_hover_list_patch.js` 顶部 `OPEN_DELAY` / `CLOSE_DELAY`。
- 浮层位置（默认 `right-start`）与 `holdOnHover`：`setup()` 里 `usePopover` 的 options
  （`position` 取值见 `@web/core/position/position_hook`：`top|bottom|left|right` + `start|middle|end|fit`）。
- 视觉：`static/src/scss/product_hover.scss`（选择器统一 `.o_sph_` 前缀，避免影响其他视图）。

---

## 调试建议

- **浮层不出现**：先看控制台是否有 `/sale_product_hover/payload` 报错；
  再确认当前列表 `props.list.resModel` 是否为 `sale.order.line`（Debug 模式看列表 action）；
  最后确认 assets 是否已重建（bundle 里搜 `sale_product_hover`）。
- **浮层反复闪烁**：多为「同一行内移动」判断失效（行元素被重渲染替换），
  确认 `closest("tr.o_data_row")` 每帧拿到的是当前 DOM 元素。
- **浮层位置抖动 / 跑到屏幕外**：`holdOnHover` 是否仍传入；若目标行靠近视口边缘，
  由 `usePosition` 自动翻转，无需额外处理。
- **升级后无变化**：前端资源有缓存，必须强刷浏览器（`Ctrl+Shift+R`）。
- **Odoo 升级后回归**：重点复核 `web/views/list/list_renderer` 的
  `setup()`（`this.rootRef`）、`props.list`（`resModel` / `records` / `editedRecord`）
  与 `@web/core/popover/popover_hook` 的 `usePopover` 签名是否变化。

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
