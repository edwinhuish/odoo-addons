# 列表视图刷新

Odoo 19 后台可用性增强模块：给系统内所有列表 / 看板 / 卡片视图统一加一个刷新按钮，点一下按当前条件重新查库，搜索词、过滤器、分组、排序、页码与展开状态全部不变——不用切筛选、不用按 F5 把整页状态冲掉。

> 模块技术名：`web_list_refresh`。纯前端模块，`depends: ["web"]`。

---

## 功能概述

- 所有**多记录视图**（列表 / 树形、看板，以及由它们派生的自定义视图如卡片视图）的控制面板上出现统一的刷新按钮，位于分页器左侧
- 刷新只重新查询数据，**不重建视图、不重建搜索模型**：搜索词、过滤器、自定义过滤器、收藏夹、分组（含展开 / 折叠）、排序、当前页码与每页条数全部原样保留
- **编辑态保护**：列表内有行正在编辑时，先保存该行；保存校验失败则中止刷新并保留草稿
- **只影响数据读取**：不新增模型 / 字段 / 视图 / 权限，无数据库结构变更、无迁移脚本
- **自动降级**：未注册刷新处理器的视图（表单等）根本不渲染按钮，不报错
- 只用标准扩展方式：`t-inherit` 继承一个核心 OWL 模板 + `@web/core/utils/patch` 给两个控制器打补丁；**不修改任何 Odoo 核心文件**

---

## 核心设计

| 设计点 | 说明 |
|--------|------|
| 单一按钮插入点 | 只扩展一次 `web.ControlPanel` 模板（插在 `div.o_cp_pager` 之前），所有带控制面板的多记录视图自动获得，不必逐视图改模板 |
| 刷新 = 重新查询，不是重建 | 调用 `model.load()`（**无参**）——`RelationalModel` 的 `config` 里存着上次加载用的 `domain` / `context` / `groupBy` / `orderBy` / `limit` / `offset` / `currentGroups`，无参 load 直接复用这份 config |
| 不手工捕获 / 回填搜索状态 | 搜索状态由 `WithSearch` 持有的 `SearchModel`（`env.searchModel`）管理，刷新全程不重建它，天然保留 |
| **禁止**显式传 `domain` | 核心 `_getNextConfig()` 里 `if (!config.isMonoRecord && params.domain) resetOffset(config)`：一旦显式回传 domain，`offset` 会被归零，刷新后跳回第 1 页 |
| env 契约 + 软探测 | 控制器用 `useSubEnv({ viewRefresh: { refresh } })` 注册处理器；按钮 `t-if="env.viewRefresh"`——缺处理器就不渲染（表单视图天然无按钮） |
| 复用控制器继承 | 只 patch `ListController` 与 `KanbanController` 两个基类；任何 `...listView` / `...kanbanView` 派生的自定义视图（含本仓库 `product_card_view` 的 `card`）自动继承 |
| 编辑态先保存 | 列表 patch 的 `onBeforeReload` 用控制器已有的 `this.editedRecord`：有编辑行就 `save()`，返回 `false`（校验失败）即中止刷新（与原生分页器同一套处理） |
| 并发安全 | `RelationalModel` 内部 `keepLast` 会丢弃过期响应，连续点击不会出现旧数据覆盖新数据 |

---

## 模块资源

| 文件 | 职责 |
|------|------|
| `static/src/js/view_refresh.js` | 适配层：`useViewRefresh(getModel, { onBeforeReload })`，把刷新处理器写进 sub-env；刷新语义（无参 `model.load()`）与降级都在这一处 |
| `static/src/js/list_refresh_patch.js` | patch `ListController`（含编辑态先保存）与 `KanbanController`，调用 `useViewRefresh` |
| `static/src/xml/list_refresh_templates.xml` | `t-inherit` 扩展 `web.ControlPanel`，在分页器左侧插入刷新按钮 |
| `i18n/zh_CN.po` | 简体中文译文（按钮 `title` / `aria-label` 术语 + 应用列表元数据三条） |

> 本模块为**纯前端模块**：无 Python 模型、无数据文件、无 `security/` 目录、`__init__.py` 为空。

---

## 视图

- **`web.ControlPanel`（扩展，非重写）**：`t-name="web_list_refresh.ControlPanel"` + `t-inherit="web.ControlPanel"` + `t-inherit-mode="extension"`，xpath 锚点 `//div[hasclass('o_cp_pager')]`，`position="before"` 插入按钮
- 不修改 `web.ListView` / `web.KanbanView` 模板，也不替换任何原生节点

---

## 交互说明

- **点刷新**：按当前搜索条件、分组、排序与页码重新查库；界面出现极短的数据替换，无整页刷新与闪烁
- **编辑中**：有行处于编辑态时先保存该行；校验失败会给出原生报错并**不刷新**，草稿保留
- **按钮不出现**：当前视图没有注册刷新处理器（例如表单视图），或资源未升级 / 未强刷浏览器

---

## 国际化（i18n）

- **源语言：英文（`en_US`）**，用户可见文本（按钮 `title` / `aria-label`）在 OWL 模板里写英文；中文只出现在 `i18n/zh_CN.po` 的 `msgstr`。
- **中文译文：`i18n/zh_CN.po`**；覆盖范围：OWL 模板术语 `Refresh` → `code:addons/web_list_refresh/static/src/xml/list_refresh_templates.xml:0`（带 `#. odoo-javascript` 标记）。
- **应用列表（Apps）元数据**：模块名 / 摘要 / 描述的中文由 `model:ir.module.module,shortdesc|summary|description:base.module_web_list_refresh` 三条提供；分类用官方已有 `Productivity`（`base` 自带中文译文，无需自译）。改 `__manifest__.py` 的 `name` / `summary` / `description` 英文文案时必须同步这三条 `msgid`，规范见根 [`AGENTS.md`](../AGENTS.md) 4.8。
- 改动流程：改英文源文本 → 同步 `i18n/zh_CN.po` → `-u` 升级 + **强刷浏览器**（前端术语有缓存），英文与中文各验一遍。

---

## 依赖

- `web`（最小化依赖：只用到 Owl 的 `useSubEnv`、`@web/core/utils/patch` 与两个视图控制器的基类）
- 不依赖任何业务模块；与 `product_card_view` 等自研模块**无 `depends` 关系**——card 视图因其控制器继承自 `KanbanController` 而自动获得按钮

---

## 安装与使用

### 全新安装

1. 将 `web_list_refresh` 目录放入 Odoo 19 的 `addons_path`
2. 更新应用列表后安装模块：`List View Refresh`（中文环境显示「列表视图刷新」）
3. **强制刷新浏览器**（前端资源有缓存），进入任意列表 / 看板视图即可在分页器左侧看到刷新按钮

### 操作

- 先加好过滤器 / 分组 / 排序、翻到某一页，再点刷新：条件、展开态、排序与页码应完全不变
- 列表内联编辑时点刷新：会先保存当前行；若必填缺失等校验失败，刷新被中止、草稿保留

---

## 验证清单

> 验收日期：待目标环境验证（本地完成仓库自检与源码核对）。版本 `19.0.1.0.0`，2026-09-25。

| 验证项 | 期望 | 结果 |
|--------|------|------|
| 安装 / 升级 | `odoo -d <db> -i web_list_refresh --stop-after-init` 无报错，资源打包无 `SyntaxError` | 待验 |
| 按钮出现（列表） | 任意列表 / 树形视图分页器左侧出现刷新按钮 | 待验 |
| 搜索状态保留 | 加过滤器 / 搜索词 / 自定义过滤器后刷新，条件与结果集不变 | 待验 |
| 分组与展开态保留 | Group By 后展开若干分组再刷新，分组与展开 / 折叠状态不变 | 待验 |
| 排序保留 | 点列头排序（含多列排序）后刷新，排序不变 | 待验 |
| 分页位置保留 | 翻到第 3 页（含调整每页条数）后刷新，仍停在同一页 | 待验 |
| 看板视图 | 看板视图按钮可用，筛选 / 分组后刷新状态不变 | 待验 |
| Card 视图 | `product_card_view` 的 Card 视图按钮可用且刷新正常 | 待验 |
| 编辑态保护 | 列表行内编辑改一半点刷新 → 自动保存；造必填缺失 → 刷新中止且草稿保留 | 待验 |
| 表单视图无按钮 | 表单视图控制面板上**不出现**刷新按钮 | 待验 |
| 双语 | 英文界面 `title` 为 `Refresh`；中文界面为「刷新」 | 待验 |
| 应用列表中文化 | 中文「应用」搜 `web_list_refresh`，卡片标题「列表视图刷新」、摘要与详情描述为中文、分类「生产力」；切英文回到 manifest 原文 | 待验 |

### 异常情况与处理

- 按钮不出现：先确认已 `-u web_list_refresh` 并**强刷浏览器**；再确认当前是列表 / 看板 / 卡片视图（表单视图按设计不显示按钮）
- 按钮出现但点击无反应：打开控制台看是否有异常；重点检查 `ListController` / `KanbanController` 的 `setup` 是否被别的模块替换成了非 `super()` 写法
- 刷新后跳回第 1 页：说明有代码把搜索参数显式回传给了 `model.load({ domain, ... })` —— 刷新必须走**无参** `model.load()`（见 `AGENTS.md` L1）
- 卸载：模块无数据，UI 卸载或 `odoo -d <db> --uninstall` 即可

### 后续维护

- 想给别的视图类型加按钮：在对应控制器里调一次 `useViewRefresh(() => this.model, { onBeforeReload })`，无需改模板（按钮是全局的、按 `env.viewRefresh` 显示）
- 想改按钮位置 / 样式：改 `static/src/xml/list_refresh_templates.xml` 的 xpath 锚点与 class
- Odoo 升级后回归：`web.ControlPanel` 模板的 `o_cp_pager` 锚点、`ListController` / `KanbanController` 的 `setup` 与 `this.model`、`RelationalModel.load()` 无参复用 config 的语义

---

## 许可证

LGPL-3
