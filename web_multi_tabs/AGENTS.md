# AGENTS 工作指引

> 本文档用于指导 AI 助手或新开发者在维护、扩展本 Odoo 模块时的行为规范和关键上下文。
> L1 约束段每次加载必读；L2 踩坑档案按主题触发条件加载。

---

## 模块定位

- 模块名：`后台多标签页`（英文源文本 `Web Multi Tabs`）
- 技术目录：`web_multi_tabs`
- 新建模型：**无**（纯前端模块 + 一个控制器，不落地业务数据）
- 继承模型：无；继承控制器 `WebManifest`（`web`）
- 自定义组件（前端模块）：无 OWL 组件，标签栏是注入 `header.o_navbar` 的纯 DOM 节点
- 主依赖：`web`（不依赖 `product` / `sale` / `website`）
- 当前版本：`19.0.2.0.0`
- 版本沿革：模块技术名始终为 `web_multi_tabs`；`19.0.1.0.0` 为初始实现，`19.0.2.0.0`（2026-09-09）是在其基础上的升级优化（资源目录重构、控制器改继承、i18n 中英双语、修运行期缺陷），功能与交互不变

---

## L1：不可破坏的核心约束

每次修改代码必须保证以下行为不变。每条只列约束与违反后果，实现细节见 L2 踩坑档案。

1. **JS 首行必须是 `/** @odoo-module **/`**
   - 文件在 `static/src/` 下虽会被强制转译，但标记同时是「本文件是独立模块」的声明；删掉它就退回「原样拼进 bundle」的老行为
   - 违反后果：顶层 `var`（`tabs` / `log` / `init` / `CONFIG`…）与 `web.assets_backend` 内其他文件共享作用域，互相覆盖且无报错

2. **静态资源路径固定 `static/src/js/` + `static/src/scss/`，走 `assets` 而非 `data`**
   - `__manifest__.py` 用 `assets` 字段注册到 `web.assets_backend`
   - 违反后果：资源不打包或被当数据文件加载，标签栏不出现

3. **不修改 Odoo 核心源码 / 核心对象**
   - 控制器行为扩展一律用**控制器继承**（`class WebManifestMultiTabs(WebManifest)` + `super()`），禁止给核心类打 monkey-patch、禁止替换类属性
   - 违反后果：与其他同样扩展该类的 addon 互相覆盖；Odoo 升级后静默失效（详见 L2 P1）

4. **标签栏 DOM 挂在 `header.o_navbar` 内部，不重写核心模板**
   - 用 `insertBefore(barElement, header.firstChild)`；WCO 模式的视觉位置由 CSS 控制，DOM 不脱离 header
   - 违反后果：导航栏 flex 布局错位；Odoo 改版时比 patch 模板更难回归

5. **URL 必须先过 `normalizeUrl()` 再比较 / 存进 `tabs`**
   - 去 hash、去末尾斜杠、`/` `/web` `/odoo` `/odoo/` 统一为 `/odoo`
   - 违反后果：同一页面出现多个重复标签（本模块最典型的退步）

6. **最后一个标签不可关闭**
   - `closeTab()` 的 `if (tabs.length <= 1) return` 与 `buildTabsInnerHtml()` 的 `showClose = tabs.length > 1` 必须同时保留
   - 违反后果：关掉最后一个标签后自动新建「首页」并触发默认 action，瞬间冒出两个标签

7. **`_t()` 只在函数里调用，不写在模块顶层**
   - 译文在应用启动时才加载，顶层 `_t()` 永远拿到英文
   - 违反后果：中文用户看到英文标签名（且不报错）

8. **调试日志默认关闭**
   - 只有 URL 带 `?debug_tabs=1` / `?debug_wco=1` 或 `localStorage.debug_tabs` / `debug_wco` 为 `"1"` 时才输出
   - 违反后果：生产库控制台被 300ms 一次的轮询日志刷屏

---

## 国际化约束（i18n）

每处用户可见文本都必须满足（通用规则见根 `AGENTS.md` 第 4 节）：

1. **源语言是英文（`en_US`）**：JS 里一律写英文并包 `_t()`；中文只能出现在 `i18n/zh_CN.po` 的 `msgstr` 里，禁止写回源码。代码注释保持中文。
2. **可翻译入口正确**：本模块只有 `code:` 类型条目——`code:addons/web_multi_tabs/static/src/js/multi_tabs.js:0`（无模型 / 无视图，不会出现 `model:` / `model_terms:` 条目）。
3. **禁止拼接句子**：占位符统一 `%(name)s`；本模块暂无带参文案，新增时同样禁止字符串 `+` 拼接句子。
4. **收尾动作**：改英文源文本 → 同步 `i18n/zh_CN.po` → 提升版本 → `-u` 升级 + 强刷浏览器，中英文各验一遍。
5. **应用列表（Apps）元数据必须有中文**：改 `__manifest__.py` 的 `name` / `summary` / `description` 后必须同步 `i18n/zh_CN.po` 的 `model:ir.module.module,shortdesc|summary|description:base.module_web_multi_tabs`（`description` 的 `msgid` 必须等于 `textwrap.dedent(manifest["description"])`）。分类用官方 `Productivity`，其译文由 `base` 提供，**不要**自己再译一条 `base.module_category_productivity`。违反后果见根 `AGENTS.md` 4.8。

---

## 开发复盘与关键经验（升级优化，19.0.2.0.0）

> 通用规则见根 `AGENTS.md`，本节只记本模块特有的坑。

### 本模块特有改动点

- **只有 `code:` 条目 + 元数据条目**：纯前端模块，`.po` 里不会出现字段 / 视图类条目，写 po 时别照抄别的模块加 `model:` 键。
- **路径名映射必须延迟构造**：`getPathNameMap()` 里每个值都是 `_t()`；写成顶层常量对象会让中文用户拿到英文应用名。
- **调试开关有两个来源**：URL 参数与 `localStorage`，`__MultiTabsDebug.enable()` 写 `localStorage` 且**同时**改 `DEBUG` / `DEBUG_WCO` 变量，缺一就不生效（升级前就是缺后者）。
- **WCO 重建链路**：`destroyBar()` → `createBar()` 这条路径要重绑 ResizeObserver、清 `lastOverflowState`、关下拉菜单；新增任何「随 bar 生命周期」的监听都要在这两个函数里成对处理。

### 维护提醒

- 前端术语有缓存，任何文案改动都要 `-u` 升级 **+ 强刷浏览器**。
- Odoo 升级后优先回归三个外部依赖点：`header.o_navbar` 选择器、`.o_control_panel` 面包屑选择器、`WebManifest._get_webmanifest()` 签名。

---

## L2：踩坑档案

### P1：控制器扩展方式（改 `controllers/webmanifest.py` 时必读）

**触发条件**：需要改 PWA manifest 的任何字段，或怀疑「重写没生效」时。

**陷阱 1：以为必须 monkey-patch**
- 现象：旧实现直接 `WebManifest._get_webmanifest = _patched`，注释称「Odoo 19 的路由系统不会调用子类覆盖」。
- 根因：误判。`odoo/http.py::_generate_routing_rules()` 会 `get_leaf_classes()` 取继承树的叶子类，拼出 `type("WebManifest (extended by WebManifestMultiTabs)", (WebManifestMultiTabs,), {})`，MRO 里子类在前，`webmanifest()` 端点里的 `self._get_webmanifest()` 自然调到子类实现。
- 正确做法：`class WebManifestMultiTabs(WebManifest)` + `super()._get_webmanifest()`，不用碰核心类。

**陷阱 2：顺手把 `scope` 放宽到 `/`**
- 现象：main manifest 的 `scope` 被改成 `/`，与核心 `/scoped_app` 的独立 PWA 作用域重叠。
- 根因：核心已经写了 `scope="/odoo"` 与 `start_url="/odoo"`，这里的覆盖既没必要又有副作用。
- 正确做法：只加 `display_override`；启动入口的 `/odoo/` 与 `/odoo` 差异交给前端 `normalizeUrl()`。

### P2：bundle 作用域与模块标记（改 `static/src/js/multi_tabs.js` 时必读）

**触发条件**：文件搬家、改首行注释、或出现「变量莫名其妙被改掉」时。

**陷阱：`static/` 下非 `static/src/` 的 JS 不是 Odoo 模块**
- 现象：文件会被原样拼进 bundle，顶层 `var` 与其他文件共享作用域。
- 根因：`js_transpiler.is_odoo_module()` 里 `url.startswith(f'/{addon}/static/src')` 才强制转译；否则只看有没有 `@odoo-module` 标记。
- 正确做法：文件放 `static/src/js/`，首行 `/** @odoo-module **/`；需要外部符号时用 `import`（本模块只 import `_t`）。

### P3：标签去重与首页合并（改 `onRouteChange()` / `normalizeUrl()` 时必读）

**触发条件**：出现重复标签、首页标签被拆成两个、「关不干净」等投诉时。

**陷阱 1：比较 URL 前没归一化**
- 现象：`/odoo` 与 `/odoo/`、带不带 query 被当成两个标签。
- 正确做法：所有比较 / 入库都用 `normalizeUrl()`。

**陷阱 2：启动时 Odoo 自动跳转被当成新页面**
- 现象：打开首页后冒出两个标签（「首页」+「消息」）。
- 正确做法：`onRouteChange()` 里的「启动窗口合并」分支（唯一标签是首页 + 在 `HOME_REDIRECT_WINDOW` 内 + 尚未合并过）更新现有标签的 URL，不新建。

**陷阱 3：允许关闭最后一个标签**
- 现象：关掉后自动重建首页并触发默认 action，标签越关越多。
- 正确做法：`closeTab()` 早退 + `showClose` 条件两处都要留。

**最终实现**（`static/src/js/multi_tabs.js`）：

```js
// 最后一个标签禁止关闭：避免关闭后自动新建"首页"并触发"消息"标签
if (tabs.length <= 1) return;
```

---

## 文件职责

| 文件 | 职责 |
|------|------|
| `__manifest__.py` | 模块元数据、依赖（`web`）、`assets` 资源声明；`name` / `summary` / `description` 为英文源文本 |
| `__init__.py` | `from . import controllers` |
| `controllers/__init__.py` | `from . import webmanifest` |
| `controllers/webmanifest.py` | `WebManifestMultiTabs` 控制器，给 PWA manifest 注入 `display_override`（控制器继承，非 patch） |
| `static/src/js/multi_tabs.js` | 标签栏全部逻辑：配置区 / 调试区 / PWA-WCO 检测 / DOM 管理 / 宽度计算 / 溢出与滚动 / 标签增删改 / 事件监听 / 初始化 |
| `static/src/scss/multi_tabs.scss` | 标签栏与标签样式、溢出下拉菜单、WCO 模式样式、PWA 下 `html` / `body` 滚动约束 |
| `i18n/zh_CN.po` | 简体中文译文（前端 `_t()` 术语 + 应用列表元数据 `base.module_web_multi_tabs` 三条）；`i18n/` 不进 `data` |
| `README.md` / `CHANGELOG.md` / `AGENTS.md` | 使用说明 / 变更记录 / 维护约束 |

---

## 常见扩展场景

### 调整标签上限 / 轮询间隔 / WCO 回退宽度

改 `static/src/js/multi_tabs.js` 顶部的 `CONFIG`（`MAX_TABS` / `POLL_INTERVAL` / `WCO_CONTROL_WIDTH_FALLBACK` / `HOME_REDIRECT_WINDOW` …），不要散落硬编码常量。

### 新增一个应用路径的显示名

在 `getPathNameMap()` 里加一行（英文 + `_t()`），并在 `i18n/zh_CN.po` 补对应 `msgid` / `msgstr`；注意不要与已有 `msgid` 重复（重复会让整份 po 解析失败）。

### 给 manifest 加别的字段

在 `WebManifestMultiTabs._get_webmanifest()` 里对 `super()` 结果做增量修改；**不要**改 `scope` / `start_url`（见 L2 P1 陷阱 2）。

### 想改成 OWL 组件实现

当前是纯 DOM 实现（不重写核心模板，Odoo 升级只回归选择器）。若改为 OWL 组件，需重做：navbar 模板扩展点、状态与路由同步、`assets` 与模板注册；改动面大，非必要不动。

---

## 调试建议

- 标签栏不出现：先 `-u web_multi_tabs` 升级并强刷浏览器；再查 `header.o_navbar` 是否仍在当前 Odoo 版本
- 重复标签：URL 加 `?debug_tabs=1` 看路由日志，确认 `normalizeUrl()` 是否覆盖到该 URL 形态
- WCO 宽度不对：`window.__MultiTabsDebug.env()` 看 `env(titlebar-area-*)` 实测值，`.adjust()` 手动重算，`.snapshot()` 看整份状态
- 溢出按钮闪烁 / 不显隐：查 `overflowBtnLocked` 是否被解开（切换后两个 rAF 内解锁）与 `lastOverflowState` 是否被 `destroyBar()` 重置
- 日志太多：`window.__MultiTabsDebug.disable()`（会清掉 `localStorage` 里的开关）

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
