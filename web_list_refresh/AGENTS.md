# AGENTS 工作指引

> 本文档用于指导 AI 助手或新开发者在维护、扩展本 Odoo 模块时的行为规范和关键上下文。
> L1 约束段每次加载必读；L2 踩坑档案按主题触发条件加载。

---

## 模块定位

- 模块名：列表视图刷新（英文源文本 `List View Refresh`）
- 技术目录：`web_list_refresh`
- 新建模型：**无**（纯前端模块，无 Python 代码）
- 继承模型：**无**（不落地任何业务数据）
- 自定义组件（前端模块）：无独立 OWL 组件；按钮是扩展 `web.ControlPanel` 模板插入的普通 `<button>`，处理器由控制器通过 `useSubEnv` 注册
- 主依赖：`web`（不依赖 `product` / `sale` / `website`）
- 当前版本：`19.0.1.0.0`

---

## L1：不可破坏的核心约束

每次修改代码必须保证以下行为不变。每条只列约束与违反后果，实现细节见 L2 踩坑档案。

1. **刷新必须走无参 `model.load()`**
   - 刷新处理器里只能调 `getModel().load()`（不带任何参数）
   - 违反后果：一旦显式回传搜索状态（`model.load({ domain, groupBy, orderBy, ... })`），核心 `_getNextConfig()` 里 `if (!config.isMonoRecord && params.domain) resetOffset(config)` 会把 `offset` 归零，刷新后**跳回第 1 页**，本模块的核心卖点当场失效（**改 `static/src/js/view_refresh.js` 时必读 L2 P1**）

2. **只重新查询，不重建视图 / 不重建搜索模型**
   - 不得重建 `WithSearch` / `SearchModel`，不得 `location.reload()`，不得重新触发 action
   - 违反后果：搜索词 facet、自定义过滤器、收藏夹、搜索面板折叠值、分组展开态与滚动位置全部丢失，与「刷新不丢状态」的需求相反
   - **改 `static/src/js/view_refresh.js` 时必读 L2 P1**

3. **环境契约必须可缺省（软探测 + 降级）**
   - 按钮模板必须保留 `t-if="env.viewRefresh"`；控制器只通过 `useViewRefresh()` 注册处理器，不直接读 `env.model` / `env.config.viewType` 之类别的内部结构
   - 违反后果：表单等未注册的视图也会出现按钮；或换成 `env.model` 判据后表单视图（它同样设置 `env.model`）也被加上按钮（**改 `static/src/xml/list_refresh_templates.xml` 时必读 L2 P2**）

4. **扩展方式仅限 patch + t-inherit，禁止改核心**
   - 用 `@web/core/utils/patch` 补 `setup`（先 `super.setup(...arguments)`）、用 `t-inherit` + `t-inherit-mode="extension"` 扩展核心模板
   - 违反后果：与其他同样扩展这些类的 addon 互相覆盖；Odoo 升级后静默失效
   - 违反根 `AGENTS.md` 第 3 / 5 节约束

5. **列表编辑态先保存、失败即中止刷新**
   - `ListController` patch 的 `onBeforeReload` 必须在 `this.editedRecord` 存在时 `return this.editedRecord.save()`，返回 `false` 时刷新中止
   - 违反后果：用户改了一半的行被无提示丢弃，属于数据丢失级缺陷（**改 `static/src/js/list_refresh_patch.js` 时必读 L2 P4**）

6. **模板锚点只用稳定的控制面板结构**
   - xpath 只依赖 `div.o_control_panel_navigation` 内的 `div.o_cp_pager`，不改核心模板的其它节点
   - 违反后果：Odoo 调整控制面板 DOM 时按钮丢失或位置错乱

---

## 国际化约束（i18n）

每处用户可见文本都必须满足（通用规则见根 `AGENTS.md` 第 4 节）：

1. **源语言是英文（`en_US`）**：OWL 模板里的 `title` / `aria-label` 写英文；中文只能出现在 `i18n/zh_CN.po` 的 `msgstr` 里，禁止写回源码。代码注释保持中文。
2. **可翻译入口正确**：本模块只有 `code:` 类型条目——`code:addons/web_list_refresh/static/src/xml/list_refresh_templates.xml:0`（无模型 / 无视图数据文件，不会出现 `model:` / `model_terms:` 条目）。
3. **必须带运行期标记**：`code:` 引用指向 `.xml` / `.js`，条目必须带 `#. odoo-javascript`，否则前端译文**静默不生效**（界面一直英文，且不报错）。
4. **禁止拼接句子**：占位符统一 `%(name)s`；本模块暂无带参文案，新增时同样禁止字符串 `+` 拼接。
5. **应用列表（Apps）元数据必须有中文**：改 `__manifest__.py` 的 `name` / `summary` / `description` 后必须同步 `model:ir.module.module,shortdesc|summary|description:base.module_web_list_refresh`（`description` 的 `msgid` 必须等于 `textwrap.dedent(manifest["description"])`）。分类用官方 `Productivity`，其译文由 `base` 提供，**不要**自己再译 `base.module_category_productivity`。违反后果见根 `AGENTS.md` 4.8。
6. **收尾动作**：改英文源文本 → 同步 `i18n/zh_CN.po` → 提升版本 → `-u` 升级 + **强刷浏览器**，中英文各验一遍。

---

## L2：踩坑档案

### P1：刷新语义——无参 load 才能保住分页与分组展开态

**触发条件**：改 `static/src/js/view_refresh.js` 的刷新实现，或怀疑「刷新后条件 / 页码变了」时必读。

**陷阱 1：把搜索状态显式传回 `model.load()`**
- 现象：刷新后跳回第 1 页（搜索条件与排序倒是对的）。
- 根因：`RelationalModel._getNextConfig()` 末尾有
  `if (!config.isMonoRecord && params.domain) { resetOffset(config); }` —— 只要 `params.domain` 非空就重置 `offset`。
- 正确做法：`await model.load()`（无参）。`config` 会从当前 config 整体复制：`domain` / `context` / `groupBy` / `orderBy` / `limit` / `offset` 全部保留；`groupBy` 未变时也不会 `delete config.groups`，展开态随之保留。

**陷阱 2：以为要自己快照 / 回填搜索条件**
- 现象：为「刷新后条件不变」写了一堆 `env.searchModel.domain` 的存取代码。
- 根因：搜索状态（facet、过滤器、收藏夹、搜索面板）由 `WithSearch` 持有的 `SearchModel` 管理，只要不重建 `WithSearch`，它本来就不动。
- 正确做法：刷新只碰数据模型；**不要**动 `SearchModel` / `WithSearch`。

**陷阱 3：想用整页刷新省事**
- 现象：`location.reload()` 后 action 重跑，搜索面板折叠值、滚动位置、展开的分组全没了。
- 正确做法：坚持 `model.load()`。

### P2：环境契约与降级（改模板 / 注册方式时必读）

**触发条件**：改 `static/src/xml/list_refresh_templates.xml` 或 `useViewRefresh()`。

**陷阱：用 `env.model` 当判据**
- 现象：表单视图也冒出了刷新按钮。
- 根因：`FormController` 同样执行 `useSubEnv({ model: this.model })`（`web/static/src/views/form/form_controller.js`），`env.model` 不是列表视图专有。
- 正确做法：用本模块自己的键 `env.viewRefresh`，只有列表 / 看板（及其派生视图）才注册；缺了就不渲染。

**边界**：`useSubEnv` 在 `patch(...).setup()` 里是可以调用的（Owl 的 hook 在组件 setup 执行期内有效）；核心 `WithSearch` 就在一个 setup 里连调三次 `useSubEnv`（`__getContext__` / `__getOrderBy__` / `searchModel`），多次调用会依次合并。控制器原本的 `useSubEnv({ model })` 与我们的 `useSubEnv({ viewRefresh })` 互不影响。

**为什么按钮能读到 env**：控制器模板里渲染 `Layout`、`Layout` 再渲染 `ControlPanel`，是同一棵组件树，sub-env 随组件树向下传递（`ControlPanel` 里的 `env.searchModel` 就来自更上层的 `WithSearch`）。

### P3：Odoo 升级回归清单

**触发条件**：升级 Odoo 版本、或怀疑按钮消失 / 刷新失效时必读。

回归三处内部依赖：

1. `web.ControlPanel` 模板里是否仍有 `div.o_cp_pager`（当前在 `search/control_panel/control_panel.xml` 的 `o_control_panel_navigation` 内）——变了要改 xpath。
2. `ListController` / `KanbanController` 是否仍导出、`setup()` 内是否仍 `this.model = useState(useModelWithSampleData(...))`（我们依赖 `this.model`）。
3. `RelationalModel.load()` 无参时是否仍复用当前 `config`、`params.domain` 非空时是否仍重置 `offset`（P1 的根因）。

排查顺序：先确认 `-u web_list_refresh` + 强刷浏览器，再在控制台看 `document.querySelector('.o_web_list_refresh_button')` 是否存在；不存在则说明 `env.viewRefresh` 没注册（检查控制器 setup 是否被别的 addon 的 patch 影响）。

### P4：列表编辑态

**触发条件**：改 `list_refresh_patch.js` 的 `onBeforeReload`。

- `ListController` 维护的 `this.editedRecord` 来自 `this.model.root.editedRecord`（`onWillRender` 里同步）。
- `onBeforeReload` 返回 `false` 表示「别刷新」——`Record.save()` 校验失败时返回 `false`，于是草稿与报错都保留，与原生分页器 `usePager.onUpdate` 的处理一致。
- 分组列表下 `editedRecord` 可能取不到组内编辑行（`DynamicGroupList` 的 `records` 为空）：此时刷新会重建 root、丢弃草稿。若日后要覆盖该场景，需遍历 `root.groups[].list.editedRecord` 逐个保存（当前未实现，验收时留意）。

---

## 文件职责

| 文件 | 职责 |
|------|------|
| `__manifest__.py` | 模块元数据、依赖（`web`）、`assets` 资源声明；`name` / `summary` / `description` 为英文源文本 |
| `__init__.py` | 空（纯前端模块，无 Python 子包） |
| `static/src/js/view_refresh.js` | 适配层：`useViewRefresh(getModel, { onBeforeReload })`；唯一注册点，刷新语义（无参 `model.load()`）与降级都在这里 |
| `static/src/js/list_refresh_patch.js` | patch `ListController`（编辑态先保存）与 `KanbanController`，各调一次 `useViewRefresh` |
| `static/src/xml/list_refresh_templates.xml` | `t-inherit` 扩展 `web.ControlPanel`，在分页器左侧插入按钮，`t-if="env.viewRefresh"` |
| `i18n/zh_CN.po` | 简体中文译文（模板术语 `Refresh` + 应用列表元数据三条）；`i18n/` 不进 `data` |
| `README.md` / `CHANGELOG.md` / `AGENTS.md` | 使用说明 / 变更记录 / 维护约束 |

---

## 常见扩展场景

### 给别的视图类型加按钮

在对应控制器里调一次 `useViewRefresh(() => this.model, { onBeforeReload })`，**不用改模板**——按钮是全局的、按 `env.viewRefresh` 显示。可选集成（第三方模块）不写进 `depends`。

### 调整按钮位置 / 外观

改 `list_refresh_templates.xml` 的 xpath 锚点与 `class`；若要换图标，用核心在用的 `fa fa-refresh`（`views/fields/domain/domain_field.xml` 同款）。

### 想加快捷键

在按钮上加 `data-hotkey`（Odoo 的热键机制按 `data-hotkey` 属性扫描），例如 `data-hotkey="r"`；注意可能与原生热键冲突，需先核对。

---

## 调试建议

- 按钮不出现：`-u` + 强刷；再看当前视图是否是表单（按设计不显示）；最后在控制台确认控制器 setup 是否注册了 `env.viewRefresh`。
- 点刷新没反应：看控制台异常；确认刷新走的是无参 `model.load()`。
- 刷新后跳回第 1 页：见 P1 陷阱 1——有代码把搜索参数显式传给了 `load()`。
- 条件 / 分组丢：确认没有重建 `SearchModel` / `WithSearch`（P1 陷阱 2）。

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
