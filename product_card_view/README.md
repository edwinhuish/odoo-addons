# Product Card View

> 模块技术目录：`product_card_view`（版本 `19.0.2.0.0`，T-012 已交付；**Inventory 入口已确认，卡片内容 / Sales / Purchase 入口待目标环境复验**）。

面向外贸 SOHO 的现代产品列表卡片视图：为 Odoo 官方产品列表（库存 / 销售 / 采购入口）的
**视图切换器新增「Card」按钮**，以瀑布流卡片展示产品——卡片顶部多图轮播、主体
title / reference / on hand、多变体产品在卡片上直接按属性切变体。

官方的列表 / 看板 / 表单视图**本身保持原样**，只是多出一个并列的 Card 视图入口。

> 模块技术名：`product_card_view`（无改名历史）。

---

## 功能概述

- **Card 视图入口**：官方 Products 动作的视图切换器新增 Card 按钮，与 Kanban / List / Form 并列
  （覆盖库存 / 销售 / 采购三个入口，见「依赖」节的可选集成）；默认打开视图不变。
- **图片轮播**：卡片顶部展示产品主图；多图时支持左右箭头、触屏 / 鼠标滑动翻页与右下角计数。
  多图来源遵循 `product_image` 的数据结构：
  - 未选变体：模板主图 + 模板共享图库（`product.image.gallery`）；
  - 选中变体：变体主图（无变体图时由 Odoo 原生回退模板主图）+ 变体专属图库；
  - 模板层与变体层两套图**互不叠加**。
- **信息区**：卡片下方显示 `title`（产品名）、`reference`（`default_code`）与 `on hand`（在手数量）；
  默认口径为模板层（模板参考号 + 全部变体在手总量），点选变体后切为该变体的参考号与该变体在手。
- **变体按钮行**：多变体产品在卡片底部按属性分行（一属性一行）渲染按钮；点击即切到对应变体，
  图片 / 参考号 / 在手同步刷新。再次点击同一值可取消，回到模板层。
  不能与当前已选属性组合出变体的按钮自动禁用，避免点出“不存在的组合”。
- **瀑布流布局**：卡片按内容高度放入最矮列（JS 计算 absolute 定位），按屏幕宽度自适应列数；
  窗口 resize、图片加载完成、变体切换后自动重算。

---

## 核心设计

| 设计点 | 说明 |
|--------|------|
| 新注册 view type `card` | 注册 `views` 注册表项 `card`（`kanbanView` 派生，替换 ArchParser / Model / Renderer），使 Card 能作为独立类型出现在官方视图切换器。不用 `js_class` 是因为同一 type 在切换器只出一个按钮，`js_class` 变体无法新增入口 |
| patch `session.view_info` | Odoo 核心用 `session.view_info` 判定 view type 合法性（`view.js` 校验 + `action_service.js` 取切换器图标 / 名称），该白名单由服务端核心提供、模块级 Python 无法扩展。故在 JS 侧补 `card: {icon, display_name, multi_record}`（见模块 `AGENTS.md` L2 P1） |
| 复用 kanban 的 Controller / 数据链路 | `productCardView = {...kanbanView, type:"card", ArchParser, Model, Renderer}`：分组、搜索、翻页、空态全部沿用 kanban，只换卡片渲染与数据装配，改动面最小 |
| 后端一次性装配 payload | 每页产品只请求一次 `/product_card/payload`，一次返回模板信息 + 全部变体（属性组合 / 参考号 / 在手）+ 两套图库引用，避免每张卡片单独发请求 |
| payload 存非 reactive 全局 Map | 由 Renderer 生命周期钩子填充 `module-level Map`（按 resId 索引）。**不能**存到 reactive 的 model / record 上——会触发 Owl DataModel 的 onUpdate → reload 循环，导致前端卡死（见 `AGENTS.md` L2 P1） |
| 可选依赖用运行时判断 | `product_image` 用 `env.get("product.image.gallery")` 判断；`sale` / `purchase` 用 `env.ref(..., raise_if_not_found=False)` 判断，未安装则跳过注入，模块不报错 |

---

## 视图

- **`product.template.card`**（xmlid `product_card_view.product_template_card_view`，type=`card`）：
  卡片视图本体，arch 根为 `<card>`（server 校验要求 arch 根与 type 一致），
  arch 内**不能**出现 `t-name` 等 OWL 指令（server 会报「Arch 中使用了禁止的 owl 指令」），
  因此不写 `<templates>`，改由 JS `ProductCardArchParser` 在解析时注入虚拟 card 模板。
- **官方动作扩展**（`view_mode` 加 `card` + 各加一条 `ir.actions.act_window.view` 记录）：
  - `product.product_template_action`
  - `product.product_template_action_all`
  - `stock.product_template_action_product`（库存 → Products 入口）
  - `sale.product_template_action`、`purchase.product_normal_action_puchased`（可选，模块安装时才有）

---

## 交互说明

- **图片翻页**：卡片图片区左右箭头点击翻页；触屏 / 鼠标横向拖动超过 35px 也翻页，
  滑动后的 click 会被抑制 350ms，避免误打开产品。
- **键盘**：卡片聚焦时 `←` / `→` 翻图。
- **变体切换**：点击某属性值即选中；再点同一值取消该行选择（回到模板层）；
  切换后卡片高度可能变化，通过 `model.bus` 的 `pcv-resize` 事件通知渲染器下一帧重算瀑布流。
- **打开产品**：点击卡片空白处打开该产品表单；图片箭头、变体按钮区（`.o_product_card__stop`）不触发打开。
- **默认口径**：未选变体时显示模板名 / 模板 `default_code` / 全部变体在手总和；
  非库存追踪产品（服务等）在手显示 `—`。

---

## 接口

### `POST /product_card/payload`

内部 JSON 接口（`auth="user"`，`csrf=False`），供卡片视图按页批量取数；用 `sudo` 读取库存在手等字段，
保证对有产品 / 库存读权限的内部用户也能拿到完整数据。payload 本身不含敏感信息。

**请求**（JSON-RPC，`odoo.define` 之外由前端 `rpc()` 调用）：

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "call",
  "params": {
    "template_ids": [23, 24, 25]
  }
}
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `template_ids` | `int[]` | 本页要渲染的 `product.template` id 列表（由 Renderer 从当前页 records 的 `resId` 收集） |

**响应**（`result` 为 `{模板 id: 卡片数据}` 映射，只包含能取到的模板）：

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "23": {
      "name": "Acoustic Bloc Screens",
      "reference": "",
      "tracked": true,
      "has_stock": true,
      "on_hand_total": 16.0,
      "rows": [
        {
          "attr_id": 3,
          "attr_name": "Color",
          "attr_type": "radio",
          "values": [
            { "id": 50, "name": "White", "html_color": "" },
            { "id": 51, "name": "Black", "html_color": "" }
          ]
        }
      ],
      "variants": [
        { "id": 62, "reference": "", "on_hand": 10.0, "values": { "3": 50 } }
      ],
      "template_images": [11, 12],
      "variant_images": { "62": [13] }
    }
  }
}
```

**响应字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 模板名称（卡片 title） |
| `reference` | `str` | 模板 `default_code`；变体未单独填参考号时回退此值 |
| `tracked` | `bool` | 是否库存追踪（`is_storable`）。`false` 时在手显示 `—` |
| `has_stock` | `bool` | `qty_available` 字段是否可用（依赖 `stock`），不可用时在手显示 `—` |
| `on_hand_total` | `float \| null` | 全部 active 变体在手总量（模板层口径） |
| `rows` | `obj[]` | 变体按钮行；按 `attribute.sequence` 排序，每个属性一行 |
| `rows[].attr_id` | `int` | `product.attribute` id |
| `rows[].attr_name` | `str` | 属性显示名 |
| `rows[].attr_type` | `str` | 属性 `display_type`（`radio` / `select` / `color`…），供按钮渲染取色 |
| `rows[].values` | `obj[]` | 该属性在本模板真实出现过的属性值，按 `value.sequence` 排序 |
| `rows[].values[].id` | `int` | `product.attribute.value` id |
| `rows[].values[].name` | `str` | 属性值显示名 |
| `rows[].values[].html_color` | `str` | 颜色类属性的色值（无则空串） |
| `variants` | `obj[]` | 本模板全部 active 变体 |
| `variants[].id` | `int` | `product.product` id |
| `variants[].reference` | `str` | 变体 `default_code`，为空则回退模板 `reference` |
| `variants[].on_hand` | `float \| null` | 该变体在手数量 |
| `variants[].values` | `obj` | 该变体的属性映射 `{attr_id: value_id}`，用于与按钮选择比对 |
| `template_images` | `int[]` | 模板共享图库的 `product.image.gallery` id 列表（按 sequence 排）。**未装 `product_image` 时为空数组** |
| `variant_images` | `obj` | `{变体 id: 该变体专属图库 id 列表}`。**未装 `product_image` 时为空对象** |

> 图片 URL 由前端 `imageUrl(model, id, "image_512")` 拼装：
> 主图用 `product.template` / `product.product`，图库图用 `product.image.gallery`。

---

## 国际化（i18n）

- **源语言：英文（`en_US`）**；源码（Python / XML / JS / QWeb）一律写英文，中文只出现在 `i18n/zh_CN.po` 的 `msgstr`。
- 覆盖范围：动作 / 菜单名、动作 help、JS `_t()` 术语（图片 alt、上/下一张、参考号、在手数量）。
- **已知缺口**：视图切换器里 Card 按钮的名称来自 JS 侧 patch 的 `session.view_info.card.display_name`
  （硬编码 `"Card"`），未走 `_t()`，切换中文后仍显示英文。官方 type 的名称由服务端提供故可翻译，
  自定义 type 无此通道。如必须中文化，需在 `product_card_view.js` 改为 `_t("Card")` 并补 po 条目
  （注意模块加载期翻译可能未就绪，建议改成 getter 延迟求值）。
- 改动流程：改英文源文本 → 同步 `i18n/zh_CN.po` → `-u` 升级 + 强刷浏览器，中英文各验一遍。

---

## 依赖

- `stock`（在手数量 `qty_available` + 库存应用入口；经 `stock` 传递依赖 `product`）
- **可选集成（不在 `depends` 中，运行时判断）**：
  - `product_image`：提供 `product.image.gallery` 多图图库。**未安装**时 `template_images` /
    `variant_images` 为空，卡片**只显示主图**，其余功能不受影响。
  - `sale` / `purchase`：安装时自动把 Card 注入对应的 Products 动作；**未安装**则跳过，不注入也不报错。
- 不依赖 `website` 等其他重量级模块。

---

## 安装与使用

### 全新安装

1. 将 `product_card_view` 目录放入 Odoo 19 的 `addons_path`
2. 更新应用列表后安装模块：**Product Card View**
3. 进入 **库存 → Products**（或销售 / 采购的 Products），右上角视图切换器点 **Card**

### 升级

```bash
odoo -d <db> -i product_card_view --stop-after-init    # 首次安装
odoo -d <db> -u product_card_view --stop-after-init    # 升级（前端资源改动后必须 -u 并强刷浏览器）
```

### 操作要点

- 切换器按钮顺序为 Kanban / List / **Card** / Form（Card 排在 List 之后、Form 之前）。
- 单变体产品（无组合可选）卡片不显示变体按钮行。
- 先装 `product_card_view` 再装 `sale` / `purchase` 时，需**再升级一次** `product_card_view`
  才会把 Card 注入后者的 Products 入口（注入逻辑在 `<function>` 里，install / upgrade 都会跑，幂等）。

---

## 验证清单（验收标准 + 结果）

> 验收日期：2026-09-09 ｜ 验收环境：目标 Odoo 19 部署环境（`19.0-20260817`）
> 说明：Inventory 入口已由使用方确认；其余项按本次改动在目标环境复验。

| # | 验证项 | 期望 | 结果 |
|---|--------|------|------|
| 1 | 安装 / 升级 | `odoo -d <db> -u product_card_view --stop-after-init` 无报错，启动日志无新 ERROR | 通过 |
| 2 | Card 入口（库存） | 库存 → Products 切换器出现 Card 按钮，点击可打开卡片视图 | **通过**（使用方确认） |
| 3 | 官方视图不受影响 | 官方 Kanban / List / Form 打开正常，样式无变化 | 待验 |
| 4 | 卡片内容渲染 | 卡片显示图片 / title / reference / on hand，无图产品不裂图 | 待验 |
| 5 | 多图轮播 | 多图产品顶部可左右箭头 / 滑动切换，右下角计数正确（需装 `product_image`） | 待验 |
| 6 | 多变体按钮 | 2 颜色 × 3 尺寸产品显示两行按钮；点选后图片 / 参考号 / 在手同步切换；再点取消回模板层 | 待验 |
| 7 | 变体图源不叠加 | 选中变体后只显示该变体图集，不回显模板图库（`product_image` 变体入口） | 待验 |
| 8 | 组合禁用 / 不可追踪 | 不存在组合的按钮禁用（灰）；服务类产品在手显示 `—` | 待验 |
| 9 | 瀑布流与搜索 | 窗口缩放列数自适应；Group By / 搜索过滤可用 | 待验 |
| 10 | Card 入口（销售 / 采购） | 装了 `sale` / `purchase` 时，其 Products 切换器也出现 Card 按钮 | 待验 |
| 11 | 双语 | 英文界面显示英文；切简体中文后菜单 / help / 图片按钮 /「在手 / 参考号」为中文（Card 按钮名见 i18n 已知缺口） | 待验 |
| 12 | 权限 | 普通库存内部用户可正常浏览卡片数据（含在手） | 待验 |

### 测试用例

| 用例 | 步骤 | 期望 | 结果 |
|------|------|------|------|
| TC-01 安装 | `-u product_card_view` 后清缓存刷新 | 无 `Validation error for key "card"`、无 ParseError | 通过 |
| TC-02 入口可见 | 库存 → Products | 切换器含 Kanban / List / Card / Form | 通过 |
| TC-03 无图产品 | 打开无图产品所在的 Card 视图 | 展示占位，不裂图、不报错 | 待验 |
| TC-04 多图切换 | 装 `product_image`，给模板传 3 张图 | 箭头 / 滑动可切，计数 `1/4`（主图 + 3 图库） | 待验 |
| TC-05 变体联动 | 多变体产品点 Blue | 图片 / 参考号 / 在手切到 Blue 变体 | 待验 |
| TC-06 取消选择 | 再点 Blue | 回模板层（主图 + 模板图库 + 总在手） | 待验 |
| TC-07 组合禁用 | 选 Blue 后，某尺寸无 Blue 组合 | 该尺寸按钮禁用不可点 | 待验 |
| TC-08 可选依赖缺失 | 卸载 `product_image` 后打开 Card | 只显示主图，无报错 | 待验 |
| TC-09 可选模块缺失 | 无 `sale` 时升级本模块 | 不报错，Sales 入口无 Card | 通过（设计保证） |
| TC-10 瀑布流 | 缩放窗口 | 列数随宽度变化，卡片无重叠 | 待验 |
| TC-11 接口 | 直接调 `/product_card/payload` | 返回 `{tpl_id: {...}}`，字段见「接口」节 | 通过（响应已核对） |

### 遗留问题

1. **Card 按钮名称未国际化**：`display_name` 硬编码 `"Card"`，中文界面仍显示英文（见「国际化」节）。
2. **`sale` / `purchase` 后装**：需再升级一次本模块才会注入；不会自动感知新装模块。
3. **核心 patch 风险**：`session.view_info` 的 patch 依赖 Odoo 内部实现
   （`view.js` 的 type 校验、`action_service.js` 的 `{icon, display_name, multi_record}` 解构）；
   Odoo 升级若改动这两处需复核 `product_card_view.js`。
4. **卡片内容复验**：历史迭代中卡片曾出现空白 / 卡死，最终方案（Renderer 钩子 + 非 reactive Map）
   已解决，但仍需在目标环境按 TC-03 ~ TC-07 复验确认。

---

## 截图

> 截图需在目标环境截取后放入 `product_card_view/docs/screenshots/`（目录当前未创建，按此路径补充）。

| 截图 | 内容 | 文件 | 状态 |
|------|------|------|------|
| 视图切换器 | 库存 → Products 右上角切换器出现 Card 按钮（Kanban / List / Card / Form） | `docs/screenshots/01-switcher.png` | 待补充 |
| 卡片瀑布流 | 卡片多列瀑布流，含图片轮播箭头与右下角计数 | `docs/screenshots/02-masonry.png` | 待补充 |
| 变体切换 | 多变体产品卡片底部按钮行 + 选中态 + 信息区联动 | `docs/screenshots/03-variant.png` | 待补充 |
| 无图产品 | 无图产品的占位展示（不裂图） | `docs/screenshots/04-no-image.png` | 待补充 |

---

## 异常情况与处理

| 异常 | 处理 |
|------|------|
| 控制台 `Validation error for key "card" in registry "views"` | JS 侧 `session.view_info.card` patch 未生效：确认 assets 已重建（`-u` 升级）+ 浏览器强刷；在 `web.assets_backend` 响应里搜 `session.view_info.card` 确认已进包 |
| 升级报 `card 视图的根节点应该是 <card>` | arch 根必须与 type 一致，卡片视图 arch 根只能写 `<card>` |
| 升级报 `Arch 中使用了禁止的 owl 指令 (t-name)` | card arch 不允许 OWL 指令，不要在 arch 里写 `<templates>` / `t-name`；虚拟模板由 JS ArchParser 注入 |
| 卡片空白 / 页面卡死 | 不要重写 model 的 `load` / `_loadData`，也不要把 payload 挂到 reactive 的 model / record；只能由 Renderer 钩子填充非 reactive 全局 Map（见 `AGENTS.md` L2 P1） |
| 切换器没有 Card 按钮 | 目标动作是否已被注入：检查该 action 的 `view_mode` 含 `card` 且有对应 `ir.actions.act_window.view` 记录；`sale` / `purchase` 后装时需再升级本模块 |
| 图片 404 | 主图用 `record.resId`（不是 datapoint 内部 `record.id`）；图库图用 `product.image.gallery` 的 id |

---

## 后续维护

- **新增图片源 / 改图片字段**：改 `product_card_record.js` 的 `IMAGE_FIELD` 与 `images` getter
  （模板层、变体层分别维护，勿破坏「互不叠加」）。
- **加 Card 到新的产品动作**：硬依赖模块直接在 `views/product_card_views.xml` 加
  `view_mode` 覆盖 + `ir.actions.act_window.view` 记录；可选模块则加进
  `product_card.py` 的 `_sync_product_card_views()` 的 `targets` 元组。
- **变体规则调整**：同步改 `isValueAllowed` / `selectValue` / `currentVariant` 三个方法。
- **样式**：选择器一律以 `.o_product_card_view`（渲染器根类）开头，避免命中官方 kanban 卡片。

---

## 许可证

LGPL-3
