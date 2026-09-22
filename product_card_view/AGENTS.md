# AGENTS 工作指引

> 本文档用于指导 AI 助手或新开发者在维护、扩展本 Odoo 模块时的行为规范和关键上下文。
> L1 约束段每次加载必读；L2 踩坑档案按主题触发条件加载。
> 最近修订：2026-09-22（`19.0.2.0.7` 修复切换 filter / group by 的取数与布局，新增 L2 P6）——
> 历史修订见文末「修订记录」。

---

## 模块定位

- 模块名：产品卡片视图（Product Card View）
- 技术目录：`product_card_view`
- 新建模型：无；无 `security/ir.model.access.csv`
- 继承 / 扩展模型：
  - `product.template`：新增方法 `_get_product_card_view_payload()`（不新增字段）
  - `ir.ui.view`：`type` Selection 追加 `card`
  - `ir.actions.act_window.view`：`view_mode` Selection 追加 `card` + `_sync_product_card_views()`（可选模块注入）
- 新增 HTTP 控制器：`/product_card/payload`（`auth="user"`，内部 JSON 接口，`sudo` 读数据）
- 自定义前端：`views` 注册表 **`card`**（新 view type，`kanbanView` 派生）
- 主依赖：`stock`（`product` 经其传递依赖）
- 可选集成（**不在 `depends`**）：`product_image`（多图图库）、`product_reference`（卡片编号取产品母型号）、`sale` / `purchase`（注入 Card 入口）
- 当前版本：`19.0.2.1.2`（19.0.2.1.2 可选依赖探测收敛进 `_get_optional_base_reference()` 并补 payload 降级用例 `tests/test_product_card_payload.py`；19.0.2.1.1：母型号只对**多变体**产品生效 —— 单变体产品的编号真身在变体上，残留母型号不得盖掉它；19.0.2.1.0 卡片编号优先读产品母型号 `base_reference` —— `product_reference` 可选，按字段存在性软适配；19.0.2.0.7 修复切换 filter / group by 后卡片空白、过宽、无间隙 —— 分组取数 + payload 填充时机 + 分组布局，见 L2 P6；19.0.2.0.6 注入改为读取时计算 —— 覆盖 `_compute_views()`，解决「全新安装时 sale / purchase 未装导致漏注入」；19.0.2.0.5 完成 T-025 Card 按钮名国际化、19.0.2.0.4 产品列表默认 Card）

---

## L1：不可破坏的核心约束

每次修改代码必须保证以下行为不变。每条只列约束与违反后果，实现细节见 L2 踩坑档案。

1. **不新增模型 / 字段 / 权限**
   - 所有卡片数据通过 `product.template` 方法 + 控制器路由装配，沿用产品与库存既有权限
   - 违反后果：破坏「开箱即用、无需额外权限」的设计，引入迁移与安全配置负担

2. **只新增 Card 视图入口，不改官方列表 / 看板 / 表单视图本身**
   - 允许：扩展官方 `ir.actions.act_window` 的 `view_mode`（加 `card`）并新增
     `ir.actions.act_window.view` 记录，让切换器多一个 Card 按钮
   - 禁止：改动官方 list / kanban / form 视图的 arch、字段、按钮
   - 违反后果：影响其他模块与官方视图的继承锚点、改动面扩散

3. **模板层与变体层两套图片互不叠加**
   - 模板层 = 模板主图 + 模板共享图库；变体层 = 变体主图（无则回退模板主图）+ 变体专属图库
   - 违反后果：卡片图库语义与 `product_image` 不一致，变体图片混入共享图

4. **变体按钮行必须真实反映可组合变体**
   - 行值来源于 active 变体的 `product_template_attribute_value_ids`（PTAV）并集
     （属性经 `PTAV.attribute_id`、值经 `PTAV.product_attribute_value_id`，不是
     `product.attribute.value` 直接关联）；已选其他属性下不存在组合的值必须禁用
   - 违反后果：点选后无对应变体，信息无法切换

5. **默认口径：模板层；点选切变体**
   - 默认显示模板名 / 模板编号 / 全部变体在手总量；选择变体后切为对应变体信息
   - 编号的取值链固定为「**变体 `default_code` → 产品母型号 `base_reference` → 模板 `default_code`**」，
     产品台账在 `_get_product_card_view_payload()` 里解析好再下发；前端只做 `variant?.reference || data.reference`
   - **母型号只在模板有多个 active 变体时才参与**：单变体产品的编号真身在那条变体上
     （`product_reference` 不在产品侧写镜像），产品上的残留值（旧镜像 / 退回单变体的遗留 / 外部写入）
     **禁止**盖掉变体编号
   - `base_reference` 来自可选模块 `product_reference`，**必须按字段存在性判断**（`"base_reference" in
     env["product.template"]._fields`，与 `product_image` 的 `env.get` 同一套路），禁止写进 `depends`
   - **可选模块的接入点必须收在一处**：`base_reference` 只准出现在 `_get_optional_base_reference()`
     里（可选集成适配层），别处不许直接读写该字段 —— 对方改名 / 改字段时只改那一处；
     `product_image` 同理收在 `env.get("product.image.gallery")` 那一段
   - 降级行为由 `tests/test_product_card_payload.py` 在「装 / 不装 `product_reference`」两种配置下
     分别断言（编号取值链、残留母型号被忽略），改编号逻辑必须同步改这些用例
   - 违反后果：多变体产品（模板 `default_code` 恒为空）在卡片上编号一栏空白；或本模块被迫硬依赖 `product_reference`

6. **每页只发一次数据请求，payload 必须存在非 reactive 容器**
   - 由 `ProductCardRenderer` 的 `onWillStart` / `onWillUpdateProps`（渲染前）+ `useEffect`
     监听本页 id（渲染后兜底）拉 `/product_card/payload`，填入 **module-level 非 reactive
     全局 Map**（key=resId → payload）；卡片用 `getProductCardPayload(resId)` 取。
     `ProductCardModel` 只保留 `withCache = false`
   - 取数范围必须覆盖**分组**：未分组 `list.records`、分组 `list.groups[].list.records`
     （见 `collectCardRecords`）；非 reactive 容器意味着**数据到位后必须显式 `render(true)`**
   - 违反后果：① 只取 `list.records` → 分组视图整页空白；② 存到 reactive 的 model / record、
     或重写 model 的 `load` / `_loadData` → 触发 Owl DataModel 的 onUpdate / reload 循环 →
     前端卡死。**改 `product_card_model.js` / `product_card_renderer.js` 时必读 P1 与 P6**

7. **卡片 getter 必须用非 reactive 的 `_resId`，变体按钮行必须拆 sub-component**
   - 违反后果：与 `KanbanRecord` 的 `useRecordObserver` effect 冲突 / 嵌套 `t-foreach`
     → render 循环卡死。**改 `product_card_record.js` 时必读 P1**

8. **可选依赖必须运行时判断，不得写死 `depends`**
   - `product_image` 用 `env.get("product.image.gallery")`；`sale` / `purchase` 用
     `env.ref(..., raise_if_not_found=False)`
   - 违反后果：在未装这些模块的环境安装 / 升级本模块直接报错
     （XML 里直接 `ref` 不存在的 xmlid 会 ParseError）。**改 `views/*.xml` / 依赖时必读 P3**

9. **所有用户可见文本源语言为英文（`en_US`）**
   - Python / XML / JS / QWeb 不写中文界面文案；中文只在 `i18n/zh_CN.po` 的 `msgstr`
   - 违反后果：默认英文界面出现中文，或译文失效 / 重复 `msgid` 导致 po 解析失败

---

## 国际化约束（i18n）

1. 源语言英文；翻译键名按根 `AGENTS.md` 4.2 对照表：
   - 动作 / 菜单名 → `model:ir.actions.act_window,name:` / `model:ir.ui.menu,name:`
   - 动作 help → `model_terms:ir.actions.act_window,help:`
   - JS `_t()` 术语 → `code:addons/product_card_view/static/src/js/product_card_record.js:0`
2. JS `_t()` 字符串与 QWeb 里的文本、tooltip 文案保持一致，改了源文本必须同步 po。
3. 占位符 / 拼接：前端已全部用单词翻译或模板变量，禁止把翻译拆碎。
4. **Card 按钮名走 `_t()`（T-025 已解决）**：官方 view type 的名称由服务端提供，自定义 type 只能在前端给
   `session.view_info.card.display_name` —— 它必须写成 **getter** `() => _t("Card")`：本文件在模块加载期
   执行，而 `_t()` 返回的 `TranslatedString` 会把「构造时译文未就绪」固化成 lazy，之后取值直接抛
   `Cannot translate string: translations have not been loaded`。po 条目见
   `code:addons/product_card_view/static/src/js/product_card_view.js:0`，且**必须带 `#. odoo-javascript`**
   （前端译文靠它放行，见 L2 P5）。
5. 收尾动作：改英文源文本 → 同步 `i18n/zh_CN.po` → 提升版本 → `-u` + 强刷浏览器，中英文各验一遍。
6. **应用列表（Apps）元数据必须有中文**：改 `__manifest__.py` 的 `name` / `summary` / `description` 后，必须同步 `i18n/zh_CN.po` 的 `model:ir.module.module,shortdesc|summary|description:base.module_product_card_view` 三条（`description` 条的 `msgid` 必须等于 `textwrap.dedent(manifest["description"])`，逐字符一致），改 `category` 则同步 `model:ir.module.category,name:base.module_category_inventory_product`。这些记录归属 `base` 且 `noupdate=True`，导入只补缺失语种、不覆盖库里已有值；改译文后的强制刷新方式见根 [`AGENTS.md`](../AGENTS.md) 4.8。违反后果：中文环境「应用」列表显示英文，或译文与英文源文本长期不同步。

---

## 技术设计

### 实现方案总览

需求要的是「官方产品列表右上角能切到卡片视图」。Odoo 的视图切换器按 **view type** 出按钮，
同一 type 的 `js_class` 变体不会产生新按钮，因此必须注册一个**新的 view type `card`**。

```text
1. Python：ir.ui.view.type / ir.actions.act_window.view.view_mode 的 Selection 追加 card
2. XML   ：product.template.card 视图（type=card）+ 扩展官方产品动作（view_mode 加 card
           + 各加一条 ir.actions.act_window.view 记录）
3. JS    ：patch session.view_info 补 card → 注册 views.card（kanbanView 派生）
4. 数据  ：Renderer 生命周期钩子拉 /product_card/payload → 非 reactive 全局 Map → 卡片按 resId 查
```

### 关键逻辑

| 环节 | 关键逻辑 | 为什么这样做 |
|------|----------|--------------|
| 注册新 view type | `registry.category("views").add("card", {...kanbanView, type:"card", ArchParser, Model, Renderer})` | 切换器按 type 出按钮；复用 kanban 的 Controller / 分组 / 搜索 / 翻页，改动面最小 |
| `session.view_info` patch | 模块加载时 `session.view_info.card = {icon, display_name, multi_record}` | 核心 `view.js` 用 `type in session.view_info` 校验（仅 debug 模式触发）、`loadView` 用 `session.view_info[type]` 判存在、`action_service.js` 解构 `{icon, display_name, multi_record}` 生成按钮。该白名单由服务端核心提供，模块级 Python 无法扩展，只能 JS 侧补 |
| ArchParser | `ProductCardArchParser extends KanbanArchParser`，parse 时若无 `<templates>` 则注入虚拟 `<t t-name="card">` | server 校验 card arch 禁止 OWL 指令（`t-name`），arch 不能写模板；但 `KanbanArchParser` 缺 card 模板会抛 `Missing 'card' template`。实际卡片由 Renderer 自绘，不读该模板 |
| arch 根 | 必须是 `<card>`（不能写 `<kanban>`） | server 校验 arch 根必须与 type 一致 |
| 动作注入（硬依赖） | `product.product_template_action` / `product_template_action_all` / `stock.product_template_action_product`：覆盖 `view_mode="kanban,list,card,form"` + 各加一条 `act_window.view` 记录 | `_compute_views` 由 `view_ids` + `view_mode` 派生 `action.views`，缺任一段都可能不出按钮；`_unique_mode_per_action` 要求每个 action 各一条记录 |
| 动作注入（可选） | 覆盖 `ir.actions.act_window._compute_views()`：凡 `res_model = 'product.template'` 的动作，把 card 放到 `views` 最前 | 客户端切换器的条目与默认视图都只认服务端算出的 `action.views`（`views[0]` 即默认视图）。**读取时计算**与安装顺序无关、不写别的模块的数据，也不必猜 xmlid（`purchase.product_normal_action_puchased` 这种拼写很容易漏）；演进过程与三个反例见 L2 P4 |
| 可选图库 | `Gallery = env.get("product.image.gallery")`，为 `None` 则跳过查询 | 未装 `product_image` 时模型不存在，直接 `env["..."]` 会 KeyError |
| 瀑布流（未分组） | JS 计算列数，卡片 `position:absolute`（**只写 inline**）放最矮列；`onPatched` / resize / 容器 `ResizeObserver` / img load / `pcv-resize` 重算 | CSS 多列无法保证「按内容高度填空隙」，JS 才能均衡列高；不写进 SCSS 是为了让 JS 未跑的首帧有正常流布局兜底 |
| 分组（Group By）布局 | 不跑瀑布流，卡片按列内正常流布局：宽度上限 22.5rem + 间距 0.75rem（SCSS） | 官方分组列是 `width:100%` + `margin:0 0 -1px`（过宽、零间距）；分组列宽度下瀑布流恒为单列，CSS 即可 |

### 数据结构变更

- **无新建模型、无新建字段、无数据库结构变更、无需迁移脚本。**
- Selection 扩展（Python 层字段定义，非表结构）：
  - `ir.ui.view.type` += `card`
  - `ir.actions.act_window.view.view_mode` += `card`
- 新增数据记录：
  - `ir.ui.view`：`product_card_view.product_template_card_view`（type=`card`）
  - `ir.actions.act_window.view`：3 条静态声明（product ×2 + stock，声明式兜底）。sale / purchase / account 的动作**不写任何记录** —— card 由 `_compute_views()` 的覆盖在读取时注入
  - 扩展已有 `ir.actions.act_window` 的 `view_mode` 字段值（3 ~ 5 条）
- 卸载模块：上述记录随 `ir.model.data` 级联移除；官方动作的 `view_mode` 字段会被写回为不含 `card`
  的值吗——**不会自动回滚**（Odoo 不记录字段覆盖前的值），卸载后需重新确认官方动作 `view_mode`。

---

## L2：踩坑档案

### P1：卡片空白 / 前端卡死（reactive 循环）

**触发条件**：改 `product_card_model.js` / `product_card_renderer.js` / `product_card_record.js` 时必读

**陷阱 1：payload 挂到 reactive 对象上**
- 现象：页面一直加载中 / 卡死 / 卡片空白
- 根因：给 reactive 的 model 或 Record 实例加自定义属性，会触发 Owl DataModel 内部 effect
  （dirty / onUpdate 检测）→ reload → 循环。重写 `load` / `_loadData` 同理（`notify` → `onUpdate` → 再 `load`）
- 正确做法：**只**在 Renderer 的 `onWillStart` / `onWillUpdateProps` 里 `await rpc`，
  结果填入 module-level 非 reactive `Map`（按 resId）；`ProductCardModel` 不重写任何方法

**陷阱 2：卡片 getter 访问 reactive state**
- 现象：render 循环卡死
- 根因：`KanbanRecord` 父类 setup 注册了 `useRecordObserver`（effect 监听 `props.record` 并写
  `dataState.record` 触发 re-render）；getter 若访问 `props.record.resId` 或
  `dataState.record?.id?.value` 会与该 effect 冲突
- 正确做法：setup 时把 `resId` 缓存到**非 reactive** 实例属性 `_resId`（`onWillUpdateProps` 同步更新），
  payload / templateId getter 只用 `_resId`

**陷阱 3：主模板嵌套 `t-foreach`**
- 现象：删掉变体不卡、加回就卡
- 根因：Owl 19 在主模板里嵌套 `t-foreach`（rows × values）触发重渲染循环
- 正确做法：拆出 `ProductCardVariantRow` sub-component，外层只 `t-foreach` rows，内层 values 在独立组件内

**陷阱 4：`record.id` vs `record.resId`**
- 现象：图片 404
- 根因：`record.id` 是 datapoint 内部编号，不是数据库 id
- 正确做法：主图 URL 用 `record.resId`

**最终实现**（`product_card_model.js`）：

```javascript
const payloadByResId = new Map();   // 非 reactive
export async function fillProductCardPayload(records) {
    const templateIds = records.map((r) => r.resId ?? r.id).filter((id) => id != null);
    payloadByResId.clear();
    if (!templateIds.length) return;
    const payload = await rpc("/product_card/payload", { template_ids: templateIds });
    for (const resId of templateIds) {
        if (payload && payload[resId]) payloadByResId.set(resId, payload[resId]);
    }
}
```

---

### P2：注册新 view type 的限制

**触发条件**：改 `product_card_view.js` / 升级 Odoo 版本时必读

**陷阱 1：`views` 注册表校验报 `Validation error for key "card"`**
- 现象：`'type' is not valid`，模块加载失败、整页报错
- 根因：`viewRegistry.addValidation({ type: { validate: (t) => t in session.view_info } })`
  （`web/static/src/views/view.js`），`session.view_info` 是服务端核心白名单
- 正确做法：JS 侧 patch `session.view_info.card`。注意该校验**只在 `odoo.debug` 为真时执行**
  （`registry.js` 的 `validateSchema` 首行 `if (!odoo.debug) return;`），但 `loadView` 的
  `session.view_info[type]` 检查与 `action_service` 的解构在非 debug 下同样需要，故 patch 不能省

**陷阱 2：切换器没出按钮**
- 现象：patch 生效（bundle 里能搜到 `session.view_info.card`）但仍无 Card 按钮
- 根因：`action.views` 由 `_compute_views` 从 `view_ids` + `view_mode` 派生；
  当前页面绑定的 action 可能不是你扩展的那个（例如库存入口实际是
  **`stock.product_template_action_product`**，不是 `product.product_template_action`）
- 正确做法：先确认当前 action 的 External ID（Debug → Edit Action），再针对性扩展；
  `sale` / `purchase` 的 action 用 `view_ids`（`Command.create`）而非 `view_mode` 字符串，
  `_compute_views` 优先 `view_ids`，只需加一条 `act_window.view` 记录

---

### P3：arch 与 OWL 指令限制（card 类型）

**触发条件**：改 `views/product_card_views.xml` 时必读

**陷阱 1：`card 视图的根节点应该是 <card>，而不是 <kanban>`**
- 根因：server 校验 arch 根必须与 view type 一致
- 正确做法：arch 根写 `<card>`（`KanbanArchParser` 不检查根标签名，仍可正常解析）

**陷阱 2：`Arch 中使用了禁止的 owl 指令 (t-name)`**
- 根因：card 类型不走 kanban 的 OWL 模板白名单，arch 内不允许 `t-name` 等指令
- 正确做法：arch 不写 `<templates>`；由 `ProductCardArchParser.parse` 在 JS 侧注入虚拟
  `<t t-name="card">`，满足 `KanbanArchParser` 的 `Missing 'card' template` 检查

---

### P4：可选依赖的运行时判断

**触发条件**：改 `depends` / 新增对其它模块 action 的注入时必读

- **陷阱**：在 XML 里直接写 `<record id="sale.product_template_action">` 或
  `ref="sale.product_template_action"`，若 `sale` 未安装会 ParseError（或错误地新建一条 action）
- **正确做法**：可选依赖一律不进 `depends`；需要建记录时改由 `<function>` 调 Python 方法，
  方法内用 `env.ref(..., raise_if_not_found=False)` 判断，命中才创建并登记 `ir.model.data`
  （`noupdate=True`）。方法要幂等（先 `search_count`），因为 `<function>` 在每次 install / upgrade 都会跑
- **局限**：若 `sale` 在本模块之后才安装，需再升级一次本模块才会注入（`<function>` 只在 install / upgrade 执行，无法自动感知新装模块）
- **2026-09-22 实测演进（保留结论，避免重蹈）**：这块前后试过三种做法，最后落到「读取时计算」：
  1. **只改 `view_mode`** ✗：客户端切换器的条目只来自服务端算出的 `action.views`
     （`action_service.js::_executeActWindowAction` 遍历 `action.views` 再查 `session.view_info`），
     而 `view_mode` 是普通 Char、会被外部数据重放打回默认值 → 销售 / 采购入口什么都不显示。
  2. **建 `ir.actions.act_window.view` 记录** △：`action.views` 先读 `view_ids`，记录确实能稳定提供
     `(view_id, 'card')`，但有四个坑 —— `(act_window_id, view_mode)` 唯一约束与升级期 flush 交错会撞
     `duplicate key`；按 action 的 xmlid 末段拼新 xmlid 会与静态记录撞名
     （`product.product_template_action` 与 `sale.product_template_action` 末段相同）导致静态 xmlid 被改指；
     排序受 `_order = 'sequence,id'` 中「NULL 排最后」影响（要让 card 当默认视图反而必须写非 NULL 值）；
     **最致命的是安装顺序** —— `sale` / `purchase` 通常在本模块之后安装，`<function>` 那一次执行看不到
     它们的 action、之后没有重跑机会，`task init -- --fresh` 就是这样漏掉的。
  3. **覆盖 `ir.actions.act_window._compute_views()`** ✓（现行方案）：对
     `res_model = 'product.template'` 的动作直接把 card 放到 `views` 最前。与安装顺序、模块组合都无关，
     不往别的模块的数据里写任何东西；客户端只读 `action.views`，切换器按钮与默认视图一次到位。
- **结论**：遇到「给别的模块的 action 注入入口」这类需求，优先**读取时计算**（override 计算字段 / 视图），
  而不是往对方的数据里写记录 —— 后者要额外处理安装顺序、唯一约束、xmlid 撞名与排序四件事。

### P5：`code:` 译文的两个「静默失效」与 `_t` 的时机陷阱（T-025 实测）

- **前端 / Python 译文靠注释标记放行**：`web/controllers/utils.py::_local_web_translations()` 在运行时读模块的
  po，只收带 `JAVASCRIPT_TRANSLATION_COMMENT`（`#. odoo-javascript`）的条目；Python 的 `_()` 则由
  `CodeTranslations._load_python_translations()` 按 `#. odoo-python` 过滤。缺标记 = 永远不下发，且**不报任何错**
  （界面一直英文）。本模块曾有 5 条 `product_card_record.js` 的条目就是这样失效的。
- **`_t()` 不能在模块加载期调用**：`TranslatedString` 构造时执行
  `this.lazy = !translatedTerms[translationLoaded]`，一旦在译文就绪前构造，`valueOf()` 会**永久**抛
  `Cannot translate string: translations have not been loaded`。需要「早注册、晚取值」的场景一律用 getter
  （`translationIsReady.then(...)` 也能等，但往非响应式对象上写值不会触发重渲染，按钮名不会更新）。
- **自检要能真的验到**：`task check` 里这条检查一开始是坏的 —— 按 `"\n\n"` 切条目遇 CRLF 行尾切不开
  （整份文件被当成一个条目），`code:` 引用又带 `:0` 行号后缀导致 `endswith('.py')` 恒为假。修好后立刻暴露出
  仓库里另有 5 个模块存在同类问题（见 `TODO.md` → `T-026`）。教训：写「静默失效」类检查时，先用一条
  **已知坏数据**验证它确实会报错，否则等于没写。

---

### P6：切换筛选 / 分组后卡片空白、过宽、无间隙（19.0.2.0.7 实测）

**触发条件**：改 `product_card_model.js` / `product_card_renderer.js` / `product_card.scss`
的取数、payload 时机或布局时必读

**陷阱 1：分组时 `list.records` 是空的**
- 现象：Group By 之后所有卡片无图、无产品信息（只剩占位）
- 根因：`props.list` 未分组是 `DynamicRecordList`（记录在 `list.records`），分组是
  `DynamicGroupList`（记录在 `list.groups[].list.records`，`list.records` 为空）。
  只按 `list.records` 收集 → 取数 id 为空 → 全局 Map 被清空 → 全页空 payload
- 正确做法：统一走 `collectCardRecords(list)`（未分组取 `records`，分组递归
  `groups[].list`，支持多级分组）

**陷阱 2：先 `clear()` 再 `await rpc`（非 reactive 容器的致命时序）**
- 现象：切换筛选后卡片空白，且**一直不恢复**
- 根因：请求飞行期间 Map 已被清空，此时若发生一次渲染，卡片读到空 Map；
  而 Map 非 reactive，响应回来后**不会触发任何渲染**，空白被固化
- 正确做法：请求前**不清空**，响应回来后整体替换；用 requestSeq 丢弃过期响应；
  并用批次 key 避免同一批 id 重复请求

**陷阱 3：`onWillUpdateProps` 不是「数据变了」的可靠信号**
- 现象：换 filter / group by / 翻页后没有补拉 payload
- 根因：这类操作常常只改 `list` 内部数据，渲染器由 **Reactive 直接重渲染**，
  不经过 `updateProps` → `onWillUpdateProps` 根本不触发；即便触发，Owl 在
  `await` 后还有 `if (fiber !== this.fiber) return` —— fiber 被别的渲染取代时会
  **放弃这次渲染**，取到的数据也就没机会显示
- 正确做法：渲染后补一条 `useEffect`，依赖用「本页 id 列表」的 key。注意 Owl 19 的
  `useEffect` 就是 `onMounted` + `onPatched` 逐次比对依赖（**不是** reactive 订阅），
  所以 patch 路径全覆盖；取到数据后**显式 `this.render(true)`** ——
  非 reactive 容器没有别的通知途径。另：effect 回调**不要返回 promise**
  （Owl 会把返回值当 cleanup 调用，Promise 会抛 `cleanup is not a function`）

**陷阱 4：瀑布流只在未分组生效，分组要靠 CSS**
- 现象：Group By 后卡片撑满列宽（过宽）、上下零间距（无间隙）
- 根因：官方 `.o_kanban_grouped .o_kanban_record { width: 100% }` +
  `.o_kanban_record { margin: 0 0 -1px }`；JS 瀑布流只在 `o_kanban_ungrouped` 下跑
- 正确做法：分组样式单独给（卡片 `width:100%; max-width:22.5rem; margin:0 auto 0.75rem`）；
  `position:absolute` **只由 JS 写 inline**（写进 SCSS 会让 JS 未跑的首帧所有卡片叠在一起）；
  未分组卡片 `margin: 0`，避免官方 margin 叠加到瀑布流算的 GAP 上；
  从分组切回 / 空页时用 `_clearCardLayout()` 清掉残留 inline 定位

**陷阱 5：布局时机**
- 现象：卡片错位、高度不对
- 正确做法：布局放在 `onPatched`（DOM patch 后 offsetHeight 才准）+ `onMounted`，
  而不是 `onWillUpdateProps` 里的 rAF（props 更新不代表 DOM 已更新）；容器
  `ResizeObserver` 覆盖侧栏收放等只改宽度的情况；`innerWidth <= 0` 时直接跳过
  （容器还没布局完，算出来的列数没有意义）

---

## 文件职责

| 文件 | 职责 |
|------|------|
| `__manifest__.py` | 版本 / 依赖（`stock`）/ assets 登记；`depends` 只放硬依赖 |
| `models/product_card.py` | `_get_product_card_view_payload()` 装配卡片数据；`ir.ui.view` / `ir.actions.act_window.view` 的 Selection 扩展；`_sync_product_card_views()` 可选模块注入 |
| `controllers/product_card_controller.py` | `/product_card/payload` JSON 接口（`auth="user"` / `sudo`） |
| `views/product_card_views.xml` | `product.template.card` 视图（type=card）+ 硬依赖 action 的 `view_mode` 覆盖与 `act_window.view` 记录 + 调用同步方法的 `<function>` |
| `static/src/js/product_card_view.js` | patch `session.view_info.card`；`ProductCardArchParser`（注入虚拟 card 模板）；注册 `views.card` |
| `static/src/js/product_card_model.js` | `ProductCardModel`（只 `withCache=false`）+ 非 reactive 全局 Map + `collectCardRecords` / `collectCardRecordIds`（覆盖分组）/ `fillProductCardPayload`（成功后整体替换 + 请求序号防乱序）/ `getProductCardPayload` |
| `static/src/js/product_card_renderer.js` | `KanbanRenderer` 子类：替换卡片组件、加根类、`onWillStart` / `onWillUpdateProps` 渲染前拉 payload、`useEffect` 渲染后兜底并 `render(true)`、`onPatched` / `ResizeObserver` 重算瀑布流（分组时清 inline 定位） |
| `static/src/js/product_card_record.js` | 卡片组件：轮播 / 变体选择 / 信息同步 / 打开产品；`_resId` 缓存；内含 `ProductCardVariantRow` sub-component |
| `static/src/xml/product_card_templates.xml` | 渲染器 primary 继承模板 + 卡片 QWeb + VariantRow 模板 |
| `static/src/scss/product_card.scss` | 瀑布流与卡片 / 轮播 / 变体按钮样式（选择器以 `.o_product_card_view` 开头） |
| `i18n/zh_CN.po` | 简体中文译文 |
| `README.md` / `CHANGELOG.md` / `AGENTS.md` | 三件套文档（需求 + 接口 + 验收在 README，技术设计在本文档） |

---

## 维护要点与调试建议

- **新增图片源字段**：改 `product_card_record.js` 的 `IMAGE_FIELD` 与 `images` getter
  （模板层与变体层分别维护入口，勿破坏「互不叠加」约束）。
- **变体规则调整**：改 `isValueAllowed` / `selectValue` / `currentVariant` 三个方法，保持三者一致。
- **切换器无 Card 按钮**：先 Debug → Edit Action 确认当前 action 的 External ID；
  再查该 action 的 `view_mode` 含 `card` 且有对应 `act_window.view` 记录；
  最后确认 bundle 里能搜到 `session.view_info.card`（assets 未重建则 `-u` + 强刷）。
- **payload 缺数据**：先看 `models/product_card.py` 的字段是否被阅读权限挡住
  （控制器已 `sudo`）；卡片对空 payload 有兜底，不应白屏。
- **样式只在卡片视图生效**：所有选择器以 `.o_product_card_view` 开头；官方 kanban 卡片不在该根类下。
- **Odoo 升级后回归**：重点复核 `session.view_info` patch 是否仍被
  `view.js` / `action_service.js` 按同样方式消费（见 P2）。

---

## T-012 开发复盘与关键经验

### 目标与决策

- 需求 T-012 要求「官方产品列表能切到卡片视图」。最初实现为「独立动作 + 菜单 + `js_class`」，
  但 `js_class` 变体**不会**在切换器产生新按钮，与需求不符 → 改为注册新 view type `card`。
- 随之暴露 Odoo 核心限制：`session.view_info` 白名单无法从模块扩展 → 采用 JS 侧 patch（方案 B）。

### 踩过的坑（按发生顺序）

1. `views.card` 注册报 `Validation error ... 'type' is not valid` → `session.view_info` 校验，JS 侧 patch 解决。
2. arch 根写 `<kanban>` 报「根节点应该是 `<card>`」→ 改 `<card>`。
3. arch 写 `<templates><t t-name="card">` 报「禁止的 owl 指令」→ arch 不写模板，JS ArchParser 注入。
4. 升级成功但切换器无 Card → 当前页面绑定的是 `stock.product_template_action_product`，
   不是 `product.product_template_action`；补齐三个硬依赖 action + 两个可选 action 后正常。
5. 卡片空白 / 卡死（多版迭代）→ 见 P1，最终为「Renderer 钩子 + 非 reactive 全局 Map + `_resId` 缓存
   + VariantRow sub-component」四件套。

### 可复用经验

- **给 Odoo 加新 view type** 的三处一致性：Python Selection（`ir.ui.view.type`、
  `ir.actions.act_window.view.view_mode`）+ JS `views` 注册表 + `session.view_info`（核心不给，需 patch）。
- **调试前端资源是否生效**：在 `web.assets_backend` 的 Network 响应里搜新代码，比看版本号可靠。
- **定位是哪条 action**：Debug → Edit Action 看 External ID，比按菜单名猜快。

---

## 变更记录规范

每次功能修改后必须更新：
- `__manifest__.py` 的 `version`（遵循 `19.0.x.y.z`）
- `CHANGELOG.md` 版本说明（三段式「变更 / 影响 / 文档」；**修复 / 优化类版本**另在「变更」前补
  「优化目标」、在「变更」后补「优化前后对比」表）
- 本 `AGENTS.md` 相关约束（若涉及行为变更）+ 下方「修订记录」表
- `README.md` 用户可见功能（若涉及；含顶部「修订日期」与「验证清单」条目）
- 跨模块同步：根 `README.md` 模块一览表与 `AGENTS.md` 模块速查表的版本 / 状态摘要；
  需求类改动同步根 `TODO.md`（归档条目补追溯行）；当日阶段报告（如 `STAGE_REPORT_*.md`）若有涉及则一并同步

版本号建议：
- 破坏性变更或架构调整：升第二位，如 `19.0.2.0.0`
- 功能新增：升第三位，如 `19.0.1.1.0`
- 修复或文档：升第四位，如 `19.0.1.0.1`

---

## 修订记录

> 只记录**行为 / 约束层面**的修订（改了 L1 / L2 / 技术设计 / 文件职责）；
> 逐版本的完整变更见 `CHANGELOG.md`，用户可见功能见 `README.md`。

| 修订日期 | 版本 | 修订内容 | 涉及章节 |
|----------|------|----------|----------|
| 2026-09-22 | `19.0.2.0.7` | 修复「切换 filter / group by 后卡片空白、过宽、无间隙」：取数范围覆盖分组、payload 改为成功后整体替换 + `useEffect` 兜底重渲染、分组布局改由 SCSS 给（含未分组 `absolute` 改由 JS 写 inline、布局触发点改 `onPatched`） | L1 约束 6；技术设计「瀑布流 / 分组布局」；文件职责；新增 L2 P6 |
| 2026-09-22 | `19.0.2.0.6` | 注入机制改为覆盖 `_compute_views()` 的读取时计算（不再往其它模块写数据） | 技术设计表；L2 P4 |
| 2026-09-22 | `19.0.2.0.5` | Card 按钮名改 `_t()` getter；补 5 条失效 JS 译文 | i18n 约束 4；新增 L2 P5 |
| 2026-09-09 | `19.0.2.0.1` | 应用列表元数据中文化 | i18n 约束 6 |
| 2026-09-09 | `19.0.2.0.0` | 注册新 view type `card`（取代独立动作 + `js_class`） | 技术设计总览；L1 约束 2；L2 P1~P4；T-012 复盘 |
