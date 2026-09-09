# 变更日志

> 倒序排列，最新版本在最前。每版本固定三段式：变更 / 影响 / 文档。

## [19.0.2.0.0] - 2026-09-09（待验证）

### 变更

在原实现（`19.0.1.0.0`）基础上的一次升级优化，功能与交互不变，重点是把代码对齐到本仓库规范并修掉运行期缺陷：

**目录与资源**
- 静态资源从 `static/js/` + `static/css/` 迁到仓库约定的 `static/src/js/multi_tabs.js` + `static/src/scss/multi_tabs.scss`，`assets` 路径同步。
- 补模块三件套文档 `README.md` / `CHANGELOG.md` / `AGENTS.md`。

**前端（修复 / 健壮性）**
- **补 `/** @odoo-module **/` 首行标记**：原文件放在 `static/js/`（不在 `static/src/` 下）且无标记，`is_odoo_module()` 判定为「非 Odoo 模块」，代码被**原样拼进 `web.assets_backend` bundle**，顶层 `var`（`tabs` / `log` / `init` / `CONFIG` 等）与同 bundle 内其他文件共享作用域，存在互相覆盖风险。
- **修调试开关失效**：`__MultiTabsDebug.enable()` / `disable()` 原来只写 `window.__DEBUG_WCO` 与 `localStorage.debug_wco`，而 `DEBUG` / `DEBUG_WCO` 是由 URL 参数算出的常量、**没有任何地方读取**这两个值，开关完全无效。改为 `let` + 初始化时读 `localStorage`，`enable()` / `disable()` 真正生效。
- **修 ResizeObserver 丢失**：WCO 状态切换走 `destroyBar()` → `createBar()`，原实现 disconnect 后从不重新 `observe()`，此后容器尺寸变化不再触发溢出检测。现在 `createBar()` 会重新绑定。
- **`destroyBar()` 补齐状态清理**：关闭下拉菜单、移除 `document` 上的 outside-click 监听、重置 `lastOverflowState`（原值会让重建后的溢出日志与判断失真）。
- **删死代码**：`closeTab()` 里 `if (tabs.length <= 1) return` 之后「关掉最后一个标签」的分支永远不可达，已删除。
- `escapeHtml()` 复用同一个游离 `div`，不再每次创建 DOM 节点；`escapeAttr()` 对入参做 `String()`，避免 `_t()` 返回 `TranslatedString` 时出错。
- 折叠按钮 `title` 在循环外只算一次；SCSS 去掉 `.o_multi_tabs_overflow_btn` 里被后面覆盖的重复 `width: 32px;`。
- 启动合并窗口时长（原硬编码 3000）与调试 `localStorage` 键名收进 `CONFIG`。

**Python（去 monkey-patch）**
- `controllers/webmanifest.py` 由「直接改写 `WebManifest._get_webmanifest` 的类属性」改为**标准控制器继承** `class WebManifestMultiTabs(WebManifest)` + `super()`。已对照 `odoo/http.py::_generate_routing_rules()` 核实：Odoo 19 会按控制器继承树取叶子实现（生成类 `WebManifest (extended by WebManifestMultiTabs)`），重写生效，**不需要** monkey-patch 核心类，符合根 `AGENTS.md` 第 5 节「禁止修改 Odoo 核心源码」。
- **不再覆盖 `scope` / `start_url`**：核心 `WebManifest._get_webmanifest()` 已经写入 `scope="/odoo"` 与 `start_url="/odoo"`，原代码把 `scope` 放宽到 `/` 会与核心 `/scoped_app` 的独立 PWA 作用域冲突；启动入口差异（`/odoo/` vs `/odoo`）由前端 `normalizeUrl()` 统一。

**国际化（i18n）**
- 源语言改为**英文**：JS 里的中文界面文本（首页 / 操作 # / 页面 / 关闭 / 更多标签 / 29 个应用路径名）改为英文 + `_t()`，调试日志文案改英文。
- 路径名映射从常量对象改为 `getPathNameMap()`：**模块加载时译文尚未就绪**，顶层 `_t()` 只能拿到英文，必须延迟到实际使用时调用。
- 新增 `i18n/zh_CN.po`：38 条译文（前端术语 + 应用列表元数据 `shortdesc` / `summary` / `description`）。
- `__manifest__.py` 的 `name` / `summary` / `description` 改写英文，`author` 统一 `edwinhuish`，`category` 由 `Website` 改为官方已有分类 `Productivity`（`base` 自带中文译文，无需自译）。

### 影响

- **纯前端 + 一个控制器，无模型 / 字段 / 视图 / 权限变更，无迁移脚本**，无数据损失。
- 控制器由 monkey-patch 改为继承：行为等价（manifest 仍带 `display_override`），但**不再在导入期改写核心类属性**，避免与其他同样扩展该方法的 addon 互相覆盖。
- `scope` 不再放宽到 `/`：主 PWA 作用域回到核心默认的 `/odoo`，`/scoped_app` 的独立 PWA 不受影响；对多标签功能本身无影响（启动入口由前端归一化）。
- 静态资源路径变更：升级后必须**强刷浏览器**，否则旧 bundle 仍在跑旧路径的旧代码。
- 升级方式：`odoo -d <db> -u web_multi_tabs --stop-after-init`（模块技术名未变，不需要卸载重装）。

### 文档

- 同步 `__manifest__.py`（版本 19.0.2.0.0、英文 name / summary / description、`author` / `category` / `assets` 路径）、`README.md`、`CHANGELOG.md`（本文件）、`AGENTS.md`（模块约束与踩坑档案）、`i18n/zh_CN.po`。
- 根 `README.md`：模块一览表更新 `web_multi_tabs` 的状态与版本。
- 根 `AGENTS.md`：第 9 节「已有模块速查」更新本模块行。
- 按需求要求**不写入 TODO**：本次升级直接按完成状态归档，验收记录待目标环境验证后补进本文件。

---

## [19.0.1.0.0] - 升级前基线（历史版本）

### 变更

- 初始实现：在 `header.o_navbar` 内注入标签栏，打开视图自动建标签，支持切换 / 关闭 / 溢出折叠 / 首页重定向合并；PWA 与 Window Controls Overlay 适配；通过改写 `WebManifest._get_webmanifest` 给 manifest 注入 `display_override` 与固定的 `start_url` / `scope`。
- 界面文案直接写在 JS 里（中文），静态资源放在 `static/js/` 与 `static/css/`。

### 影响

- 纯前端 + 一个控制器，无数据、无迁移脚本。

### 文档

- 该版本当时只有 `__manifest__.py` 与源码，无模块文档；文档自 `19.0.2.0.0` 起补齐。
