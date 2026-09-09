# 后台多标签页

Odoo 19 后台导航增强模块：把每次打开的视图变成内部标签页，少开几个浏览器标签，特别适合 PWA / 独立应用模式（浏览器标签栏隐藏时尤其有用）。

> 模块技术名：`web_multi_tabs`。`19.0.2.0.0`（2026-09-09）是在原实现基础上的一次**升级优化**：重构静态资源目录、控制器改为标准继承、源语言改为英文并补齐中文译文，同时修掉若干运行期缺陷；功能与交互保持不变，详见 `CHANGELOG.md`。

---

## 功能概述

- 在顶部导航栏（`header.o_navbar`）内渲染**标签栏**，每次打开新视图自动创建标签
- 点击标签切换视图；每个标签带关闭按钮，**最后一个标签不显示关闭按钮**（避免关完自动新建出一堆标签）
- 放不下的标签折叠为「更多标签」下拉菜单（`▾`），切换后自动把当前标签滚动到可见区域
- 标签标题**跟随当前视图**（面包屑 / 表单标题，如报价单编号、客户名称），`PWA` 模式下同步作为浏览器文档标题
- 首页等价 URL（`/`、`/web`、`/odoo`、`/odoo/`）统一为一个「首页」标签；Odoo 启动时自动跳转到默认 action（如 Discuss）的那次重定向也**合并进首页标签**，不会产生两个指向同一页面的标签
- 标签数超过 `MAX_TABS`（默认 15）时淘汰最旧的非活跃标签
- **PWA / Window Controls Overlay（WCO）适配**：标签栏宽度按 CSS `env(titlebar-area-*)` 计算，铺满标题栏区域，左上角 LOGO 区可拖动窗口
- 通过**标准控制器继承**给 PWA `manifest` 追加 `display_override: ["window-controls-overlay"]`，不 monkey-patch 核心类
- 不重写任何核心模板：标签栏只是插入 `header.o_navbar` 的普通 DOM 节点

---

## 核心设计

| 设计点 | 说明 |
|--------|------|
| 纯 DOM 注入，不改核心模板 | 标签栏是 `div#o_multi_tabs_bar`，插到 `header.o_navbar` 首位；不 patch OWL 组件，Odoo 升级时只需回归选择器 `header.o_navbar` |
| `history.pushState` / `replaceState` hook | Odoo 切视图大量用 pushState，必须 hook 才能捕获；另有 300ms 轮询兜底（覆盖不走 history API 的跳转） |
| URL 归一化（`normalizeUrl`） | 去 hash、去末尾斜杠、`/`  `/web`  `/odoo`  `/odoo/` 统一为 `/odoo`，从源头避免重复标签 |
| 首页重定向合并 | 启动 3 秒窗口内，若唯一标签是首页且发生跳转，则更新该标签 URL 而不是新建 |
| WCO 宽度三级回退 | CSS `env(titlebar-area-width)` → `navigator.windowControlsOverlay.getBoundingClientRect()` → 固定回退值（152px）；`geometrychange` / `resize` / 轮询签名变化都会重算 |
| 溢出检测 | `scrollWidth > clientWidth` 判溢出，只切换 `o_overflow_visible` 类（用 visibility + opacity + width 而非 display，避免重排闪烁）；切换过程中加锁 `overflowBtnLocked` 防抖 |
| 控制器继承替 monkey-patch | `WebManifestMultiTabs(WebManifest)` 重写 `_get_webmanifest()`；Odoo 的 `_generate_routing_rules()` 会取控制器继承树的叶子实现，效果与 patch 一致但不污染核心类 |

---

## 模块资源

| 文件 | 职责 |
|------|------|
| `static/src/js/multi_tabs.js` | 标签栏全部逻辑：配置区 / 调试区 / PWA-WCO 检测 / DOM 管理 / 宽度计算 / 溢出与滚动 / 标签增删改 / 事件监听 / 初始化 |
| `static/src/scss/multi_tabs.scss` | 标签栏、标签、关闭按钮、溢出按钮与下拉菜单样式；WCO 模式样式；PWA 模式下把 `html` / `body` 锁为视口高度、让 `.o_action_manager` 接管滚动 |
| `controllers/webmanifest.py` | `WebManifestMultiTabs` 控制器，给 PWA manifest 注入 `display_override` |
| `i18n/zh_CN.po` | 简体中文译文（前端 `_t()` 文案 + 应用列表元数据） |

> 本模块**无 Python 模型、无数据文件、无 `security/` 目录**（控制器不落地业务数据）。

---

## 国际化（i18n）

- **源语言：英文（`en_US`）**，JS 里所有用户可见文本（标签名、关闭 / 更多标签按钮 `title`、路径段显示名）一律写英文并包 `_t()`；中文只出现在 `i18n/zh_CN.po` 的 `msgstr`。
- **中文译文：`i18n/zh_CN.po`**（`zh_CN`）；模块默认展示英文，安装中文语言后界面切为中文。
- 覆盖范围：JS `_t()` 文案（`code:addons/web_multi_tabs/static/src/js/multi_tabs.js:0`）——`Home` / `Action` / `Page` / `Close` / `More tabs`，以及 29 个 Odoo 应用路径段名。
- **应用列表（Apps）元数据**：模块名 / 摘要 / 描述的中文由 `i18n/zh_CN.po` 的 `model:ir.module.module,shortdesc|summary|description:base.module_web_multi_tabs` 三条提供；分类用官方已有 `Productivity`（`base` 自带译文，无需自译）。改 `__manifest__.py` 的 `name` / `summary` / `description` 英文文案时必须同步这三条的 `msgid`，规范见根 [`AGENTS.md`](../AGENTS.md) 4.8。
- **不要**把 `_t()` 写在模块顶层：译文在应用启动时才加载，顶层调用只能拿到英文——路径名映射表因此写成 `getPathNameMap()`，在实际使用时才调用。
- 改动流程：改英文源文本 → 同步 `i18n/zh_CN.po` → `-u` 升级 + **强刷浏览器**（前端术语有缓存），英文与中文各验一遍。

---

## 交互说明

- **切标签**：单击标签；超出的标签从右侧 `▾` 下拉菜单里选
- **关标签**：点标签上的 `×`；只剩一个标签时 `×` 不显示（禁止关闭）
- **PWA / WCO**：标签栏占据窗口标题栏区域，左上角 LOGO 区可拖动窗口；标签栏宽度随窗口与标题栏几何变化自动重算
- **调试**：URL 加 `?debug_tabs=1` / `?debug_wco=1` 打开日志；DevTools Console 可用
  `window.__MultiTabsDebug.enable()` / `.disable()` / `.snapshot()` / `.adjust()` / `.env()`
  （开关写入 `localStorage` 的 `debug_tabs` / `debug_wco`，刷新后仍生效）

---

## 依赖

- `web`（最小化依赖：只复用其前端环境、controller 基类与译文工具 `@web/core/l10n/translation`）

---

## 安装与使用

### 全新安装

1. 将 `web_multi_tabs` 目录放入 Odoo 19 的 `addons_path`
2. 更新应用列表后安装模块：`Web Multi Tabs`（中文环境显示「后台多标签页」）
3. 刷新浏览器（前端资源有缓存），顶部导航栏下方即出现标签栏

### 从旧版本升级

模块技术名始终是 `web_multi_tabs`，升级前后是同一个模块：

1. `odoo -d <db> -u web_multi_tabs --stop-after-init`
2. 浏览器**强制刷新**（静态资源路径与文案都变了，旧 bundle 会继续跑旧代码）

本次升级**无模型 / 字段 / 视图 / 权限变更，无数据，无需迁移脚本**；`addons_path` 中只需保留一份 `web_multi_tabs`。

### 操作要点

- 打开菜单进入任意视图即新建标签，点标签在已打开的视图间来回切换，无需重新加载
- 标签过多时用右侧 `▾` 找被折叠的标签
- PWA 场景：把 Odoo 安装为应用（浏览器菜单「安装此站点」）后以独立窗口打开，标签栏会接管标题栏区域

---

## 验证清单

> 本次升级尚未在目标环境验证，以下为待验项（版本 `19.0.2.0.0`，2026-09-09）。

| 验证项 | 期望 | 结果 |
|--------|------|------|
| 安装升级 | `odoo -d <db> -i web_multi_tabs --stop-after-init` 无报错，资源打包无 `SyntaxError` | 待验 |
| 标签栏出现 | 顶部导航栏内出现标签栏，导航栏布局不错位 | 待验 |
| 自动建标签 | 打开新视图自动新建标签 | 待验 |
| 切换 / 关闭 | 点标签切换视图；`×` 关闭标签；仅剩一个标签时无 `×` | 待验 |
| 首页合并 | `/` `/web` `/odoo` `/odoo/` 只产生一个「首页」标签；启动跳转 Discuss 不新建第二个标签 | 待验 |
| 溢出折叠 | 标签超出宽度出现 `▾`，菜单列出被折叠标签，切换后滚动到可见 | 待验 |
| 标签标题 | 标签名跟随面包屑 / 表单标题（如报价单编号） | 待验 |
| PWA / WCO | 以 PWA 打开时标签栏铺满标题栏区域，可拖动窗口；窗口缩放后宽度重算 | 待验 |
| manifest | `/web/manifest.webmanifest` 返回体含 `display_override: ["window-controls-overlay"]` | 待验 |
| 应用列表中文化 | 中文环境「应用」搜 `web_multi_tabs`，卡片标题「后台多标签页」、摘要与详情描述为中文、分类「生产力」；切英文回到 manifest 原文 | 待验 |
| 双语 | 英文界面下标签名 / 按钮 `title` 为英文；切中文后为中文 | 待验 |

### 异常情况与处理

- 标签栏不出现：前端资源缓存，`-u web_multi_tabs` 升级后强刷浏览器；再检查 `header.o_navbar` 选择器是否仍存在于当前 Odoo 版本
- 出现两个首页标签：已由 `normalizeUrl` + 启动合并窗口覆盖；仍复现就用 `?debug_tabs=1` 看路由日志
- WCO 下标签栏宽度不对：用 `window.__MultiTabsDebug.env()` 看 `env(titlebar-area-*)` 实测值，`.adjust()` 手动重算
- 卸载：`web_multi_tabs` 无数据，UI 卸载或 `odoo -d <db> --uninstall` 即可

### 后续维护

- 调标签数上限 / 轮询间隔 / WCO 回退宽度：改 `static/src/js/multi_tabs.js` 的 `CONFIG`
- 新增应用路径显示名：加进 `getPathNameMap()`（英文 + `_t()`），并在 `i18n/zh_CN.po` 补译文
- Odoo 升级后重点回归：`header.o_navbar`、`.o_control_panel` 面包屑选择器、`WebManifest._get_webmanifest()` 签名

---

## 许可证

LGPL-3
