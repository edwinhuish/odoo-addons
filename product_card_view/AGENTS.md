# AGENTS 工作指引

> 本文档用于指导 AI 助手或新开发者在维护、扩展本 Odoo 模块时的行为规范和关键上下文。
> L1 约束段每次加载必读；L2 踩坑档案按主题触发条件加载。

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
- 可选集成（**不在 `depends`**）：`product_image`（多图图库）、`sale` / `purchase`（注入 Card 入口）
- 当前版本：`19.0.2.0.1`（19.0.2.0.1 补应用列表（Apps）中文元数据：`shortdesc` / `summary` / `description` + 分类 `Product` 译文）

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
   - 默认显示模板名 / 模板 `default_code` / 全部变体在手总量；选择变体后切为对应变体信息；
     变体 `default_code` 为空时回退模板参考号
   - 违反后果：卡片信息口径混乱

6. **每页只发一次数据请求，payload 必须存在非 reactive 容器**
   - 由 `ProductCardRenderer` 的 `onWillStart` / `onWillUpdateProps` 拉 `/product_card/payload`，
     填入 **module-level 非 reactive 全局 Map**（key=resId → payload）；卡片用
     `getProductCardPayload(resId)` 取。`ProductCardModel` 只保留 `withCache = false`
   - 违反后果：存到 reactive 的 model / record、或重写 model 的 `load` / `_loadData`
     → 触发 Owl DataModel 的 onUpdate / reload 循环 → 前端卡死。**改 `product_card_model.js`
     / `product_card_renderer.js` 时必读 P1**

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
4. **已知缺口**：切换器的 Card 按钮名来自 JS patch 的 `session.view_info.card.display_name`（硬编码
   `"Card"`，未走 `_t()`），中文界面仍显示英文。官方 type 的名称由服务端提供故可翻译，自定义 type
   无此通道；如需中文化，改为 `_t("Card")` + 补 po，并注意模块加载期翻译可能未就绪（建议 getter 延迟求值）。
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
| 动作注入（可选） | `<function>` 调 `_sync_product_card_views()`，用 `env.ref(..., raise_if_not_found=False)` 判断后创建 + 登记 `ir.model.data` | `sale` / `purchase` 不在 `depends`，XML 里直接 `ref` 会 ParseError；`<function>` 在 install / upgrade 都执行且幂等 |
| 可选图库 | `Gallery = env.get("product.image.gallery")`，为 `None` 则跳过查询 | 未装 `product_image` 时模型不存在，直接 `env["..."]` 会 KeyError |
| 瀑布流 | JS 计算列数，卡片 `position:absolute` 放最矮列；resize / img load / `pcv-resize` 重算 | CSS 多列无法保证「按内容高度填空隙」，JS 才能均衡列高 |

### 数据结构变更

- **无新建模型、无新建字段、无数据库结构变更、无需迁移脚本。**
- Selection 扩展（Python 层字段定义，非表结构）：
  - `ir.ui.view.type` += `card`
  - `ir.actions.act_window.view.view_mode` += `card`
- 新增数据记录：
  - `ir.ui.view`：`product_card_view.product_template_card_view`（type=`card`）
  - `ir.actions.act_window.view`：3 条硬依赖 + 最多 2 条可选（sale / purchase）
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
- **局限**：若 `sale` 在本模块之后才安装，需再升级一次本模块才会注入

---

## 文件职责

| 文件 | 职责 |
|------|------|
| `__manifest__.py` | 版本 / 依赖（`stock`）/ assets 登记；`depends` 只放硬依赖 |
| `models/product_card.py` | `_get_product_card_view_payload()` 装配卡片数据；`ir.ui.view` / `ir.actions.act_window.view` 的 Selection 扩展；`_sync_product_card_views()` 可选模块注入 |
| `controllers/product_card_controller.py` | `/product_card/payload` JSON 接口（`auth="user"` / `sudo`） |
| `views/product_card_views.xml` | `product.template.card` 视图（type=card）+ 硬依赖 action 的 `view_mode` 覆盖与 `act_window.view` 记录 + 调用同步方法的 `<function>` |
| `static/src/js/product_card_view.js` | patch `session.view_info.card`；`ProductCardArchParser`（注入虚拟 card 模板）；注册 `views.card` |
| `static/src/js/product_card_model.js` | `ProductCardModel`（只 `withCache=false`）+ 非 reactive 全局 Map + `fillProductCardPayload` / `getProductCardPayload` |
| `static/src/js/product_card_renderer.js` | `KanbanRenderer` 子类：替换卡片组件、加根类、生命周期钩子拉 payload、JS 瀑布流布局与重算 |
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
- `CHANGELOG.md` 版本说明（变更 / 影响 / 文档）
- 本 `AGENTS.md` 相关约束（若涉及行为变更）
- `README.md` 用户可见功能（若涉及）

版本号建议：
- 破坏性变更或架构调整：升第二位，如 `19.0.2.0.0`
- 功能新增：升第三位，如 `19.0.1.1.0`
- 修复或文档：升第四位，如 `19.0.1.0.1`
