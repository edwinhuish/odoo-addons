# 变更日志

> 倒序排列，最新版本在最前。每版本固定三段式：变更 / 影响 / 文档。
> 版本号规则见根 `AGENTS.md` 第 3 节：架构/破坏性 +x，功能 +y，修复/文档 +z。

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
