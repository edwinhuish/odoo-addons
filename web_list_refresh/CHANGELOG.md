# 变更日志

> 倒序排列，最新版本在最前。每版本固定三段式：变更 / 影响 / 文档。

## [19.0.1.0.0] - 2026-09-25（待验证）

### 变更

- 初始版本：为系统内所有**多记录视图**（列表 / 树形、看板，以及由它们派生的自定义视图如卡片视图）统一增加一个刷新按钮。
- 按钮通过扩展核心 `web.ControlPanel` 模板插入（xpath 锚点 `div.o_cp_pager` 之前），不重写核心模板；表单等未注册处理器的视图自动不显示按钮。
- 刷新语义定为**无参 `model.load()`**：`RelationalModel` 的 `config` 已存着上次加载的 `domain` / `context` / `groupBy` / `orderBy` / `limit` / `offset` / `currentGroups`，无参 load 原样复用，因此搜索词、过滤器、收藏夹、分组（含展开态）、排序与页码全部保留。
  - 明确避开「显式回传搜索参数」的写法：核心 `_getNextConfig()` 里 `params.domain` 非空会把 `offset` 归零，刷新后会跳回第 1 页。
- 控制器扩展方式：`@web/core/utils/patch` 给 `ListController` 与 `KanbanController` 的 `setup` 打补丁，用 `useSubEnv({ viewRefresh: { refresh } })` 注册处理器；`product_card_view` 的 `card` 视图复用 `KanbanController`，因此一并覆盖。
- 编辑态保护：列表 patch 的 `onBeforeReload` 复用控制器已有的 `this.editedRecord`——有编辑行先 `save()`，返回 `false`（校验失败）即中止刷新并保留草稿（与原生分页器同一套处理）。
- 新增 `i18n/zh_CN.po`：按钮术语 `Refresh` → 「刷新」+ 应用列表元数据三条（含 `#. odoo-javascript` 运行期标记）。

### 影响

- **纯前端模块，无模型 / 字段 / 视图 / 权限变更，无数据库结构变更，无需迁移脚本**，卸载无数据残留。
- 只影响数据读取路径：不改变任何原生视图的搜索、排序、分页行为；不重建 `SearchModel`，不动 `WithSearch`。
- 升级 / 安装后必须**强刷浏览器**，否则旧 bundle 里没有这个按钮。
- 唯一的外部依赖点是 Odoo 内部结构：`web.ControlPanel` 模板的 `o_cp_pager` 锚点、`ListController` / `KanbanController` 的 `setup` 与 `this.model`、`RelationalModel.load()` 的 config 复用语义；Odoo 升级后需回归（见模块 `AGENTS.md` → L2 P3）。

### 文档

- 新增模块三件套 `README.md` / `CHANGELOG.md` / `AGENTS.md`、`i18n/zh_CN.po`、`__manifest__.py`（英文 name / summary / description）。
- 根 `README.md`：模块一览表、应用列表（Apps）中文化覆盖表与模块计数同步。
- 根 `AGENTS.md`：第 4.8 节落地情况与第 9 节「已有模块速查」新增本模块。
- 根 `TODO.md`：新增 `T-043` 归档条目（含落地版本与遗留）。
- `.dev/init.yaml`：`addons` 列表登记 `web_list_refresh`（方便本地 `task up` 一次装齐）。
