# `product_variant` 映射表改造 · 操作记录与变更追溯（2026-09-24 ~ 09-25）

> **文档定位**：本文件记录「多变体映射」这条改造的**实际操作过程与产生的变更** ——
> 操作目的、时间、环境、执行内容（命令级）、变更清单、注意事项、后续建议。
> 面向「查阅与追溯」：想知道「谁在什么时候做了什么、动到了哪些东西、升级要注意什么」，看这份。
>
> **与复盘文档的分工**（避免重复，两边互相链接）：
>
> | 想知道 | 看哪份 |
> |---|---|
> | 做了什么、产生什么变更、升级注意什么、怎么追溯 | **本文件** |
> | 为什么这样设计、踩了哪些坑、可复用结论 | [`product_variant_mapping_review_2026-09-24.md`](product_variant_mapping_review_2026-09-24.md) |
> | 模块怎么用 / 逐版本变更 / 约束与踩坑 | `product_variant/README.md` / `CHANGELOG.md` / `AGENTS.md` |
>
> **操作人**：AI 助手（CodeBuddy）在本轮协作中执行；复核与目标环境验收**待团队成员**。
> 文中的命令均为**实际执行过**的（除了明确标注「升级步骤（供生产执行）」的那些）。

---

## 1. 操作目的

把「改产品属性会删掉并重建变体」这件危险操作，改造成**可控的映射转换**：

1. 模块改名为 `product_variant`，并给出**已装库的原地升级路径**（不卸载重装、不丢台账 / 谱系）；
2. 用「属性 ↔ 变体」映射表取代归属弹窗：属性行下方常驻，能看出哪些变体缺取值、哪些组合是新的；
3. 保证映射表**真的可用**（渲染、可编辑、实时刷新、不崩页面）；
4. 口径定稿：**前端穷举展示全部组合，后端按属性规则按需预建**；
5. 交互定稿：一个组合只能被一条变体占用（下拉禁用已占项）；未映射不放行；
   映射一改出现 **Save manually / Discard all changes**，丢弃能回到改动前。

验收口径（用户视角）：打开产品表单不报错 → 面板有标题、在属性行下方独占一行 → 改属性后面板刷新并点名未映射的变体 →
补好映射能保存、既有变体保持原 id → 改过映射能显式保存或整体丢弃。

---

## 2. 操作时间与环境

### 2.1 时间线

| 时间（主机本地） | 事件 |
|---|---|
| 2026-09-24 下午 | 模块改名 + 映射表初版（`19.0.7.0.0`），提交 `cf0d463`（本轮之前） |
| 2026-09-24 19:35 | 本轮主提交：映射表定稿实现 + 测试（`2e2876d`），模块文档（`1734e5c`），根文档（`8898deb`） |
| 2026-09-24 20:55 | 面板定稿（`7d6e995`）+ 面板文档（`9e6f4b4`） |
| 2026-09-25 | 文档整理：功能线复盘、本操作记录、`docs/README.md` 地图登记 |

> 时区说明：以上为主机本地时间；Odoo 容器日志输出为 UTC，与提交时间可能相差数小时。

### 2.2 环境

| 项 | 值 |
|---|---|
| 仓库 | `/home/edwin/Code/odoo-addons`（git 仓库，分支 `main`） |
| Odoo | Odoo 19，容器 `odoo19`（compose 文件 `.dev/compose.yml`），源码 `/usr/lib/python3/dist-packages/odoo` |
| 附加模块路径 | `/mnt/extra-addons`（即本仓库） |
| 数据库 | 开发库 `dev`（PostgreSQL 服务 `db`）；测试跑在 `test` 库（`task test` 自动建 / 复用） |
| 命令入口 | `Taskfile.yml`（`task --list`）；日常手册见 `DEV_WORKFLOW.md` |
| 代码检查 | 仓库自带 `.dev/scripts/check_repo.py`（`task check`） |

---

## 3. 涉及的系统与模块

| 系统 / 模块 | 涉及内容 |
|---|---|
| 模块 `product_variant` | 后端模型 `product.template` / `product.variant.*` 扩展、前端映射面板、视图继承、i18n |
| 模块 `product`（Odoo 原生） | 继承其产品表单视图 `product.product_template_only_form_view`（挂载面板、删除原生警告段落）；沿用其 `product.dynamic_variant_limit` 组合数上限 |
| Odoo Web（`web`） | 字段 widget 注册表 `registry.category("fields")`、表单控制器 `FormController`、状态指示器 `FormStatusIndicator`、`Record._save()` / `discard()` |
| 开发库 `dev` | 模块升级（`-u`）、诊断查询（视图 arch / 模块状态） |
| 测试库 `test` | 服务端单元测试与前端静态检查 |
| 文档体系 | 模块三件套、根 `README.md` / `AGENTS.md` / `TODO.md`、`docs/`（复盘 + 本记录 + 文档地图） |

---

## 4. 具体执行内容

### 4.1 代码与文档修改

按主题分四批改动（细节见 `product_variant/CHANGELOG.md` 各版本条目）：

| 批次 | 版本 | 主要文件 |
|---|---|---|
| 面板可运行性修复 | `19.0.7.0.1` – `19.0.7.0.5` | `static/src/js/variant_mapping_panel.js`、`static/src/xml/variant_mapping_panel.xml`、`views/product_template_views.xml`、`models/product_template.py`、`models/product_variant_mapping.py` |
| 计算搬到前端 + 细节 | `19.0.8.0.0` – `19.0.8.0.4`、`19.0.9.0.0` | 同上 + `static/src/js/variant_conversion_form_patch.js` |
| 结构与口径 | `19.0.10.0.0` – `19.0.12.0.1` | `models/product_template.py`（组合枚举 / 补建 / 上限估算）、前端面板与模板 |
| 面板定稿 | `19.0.13.0.0` / `19.0.13.0.1` | `views/product_template_views.xml`（删原生警告）、前端面板与 patch、`i18n/zh_CN.po`、`__manifest__.py` |

### 4.2 数据库升级（开发库）

```bash
task update -- product_variant          # 等价：odoo -d dev -u product_variant --stop-after-init（+ 重启常驻服务）
```

执行了多次（每批改动后一次），结果：**无报错**，模块 `installed`，最终版本 **`19.0.13.0.1`**。
**本轮未执行任何 SQL 写入**（模块改名所需的三条 SQL 在更早的准备阶段完成，见第 6.1 节）。

### 4.3 测试与自检

```bash
task test -- product_variant --test-tags=/product_variant          # 服务端单元测试 + 前端静态检查
node product_variant/tests/js/variant_mapping_pure.mjs             # 纯函数离线自测（约 1 秒）
python3 .dev/scripts/check_repo.py                                 # 仓库自检（等价 task check）
```

| 命令 | 结果 |
|---|---|
| `task test` | **63 项** 0 failed / 0 error（含 4 项前端静态检查 `test_frontend_consistency.py`） |
| 离线自测 | **15 项** all good |
| `task check` | 无失败项（每次改动后都跑） |

### 4.4 诊断与验证操作

| 操作 | 命令 / 方式 | 用途 |
|---|---|---|
| 读 Odoo 源码 | `docker exec odoo19 grep -rn ... /usr/lib/python3/dist-packages/odoo/addons/...` | 确认字段 widget 注册契约、`FormController` 保存 / 丢弃 / 离开钩子、`Record._save()` 早退、状态指示器显示条件、原生警告出处 |
| 读合并后的视图 | `odoo shell -d dev --no-http` 里 `env["product.template"].get_views([(False, "form")])` | 确认面板字段在 arch 里、原生警告已消失 |
| 查模块状态 | `psql -U odoo -d dev -c "SELECT name, state, latest_version FROM ir_module_module WHERE name='product_variant';"` | 确认升级后的版本与状态 |
| 查视图来源 | `psql ... SELECT substring(arch_db::text from position('Warning' in arch_db::text)-500 for 900) ...` | 取出原生警告所在的 arch 片段，确定 xpath 写法 |
| HTTP 会话 | `curl` 登录 `dev` 后调 `get_views` | 早期用于排除「进程未重启 / 浏览器缓存」的误判方向 |
| 语法与静态检查 | `node --check`、`python3 -m py_compile` | 每次改完前端 / 后端文件后先本地检查 |

### 4.5 版本与文档同步

`__manifest__.py` 版本从 `19.0.7.0.0` 递增到 **`19.0.13.0.1`**，同步更新（缺一不可）：

- 模块：`CHANGELOG.md`（逐版本「变更 / 影响 / 文档」）、`AGENTS.md`（当前版本 + L2 P4 陷阱 8–20）、`README.md`（面板行为、场景表、升级步骤）；
- 根：`README.md`（模块一览表版本与状态）、`AGENTS.md`（速查）、`TODO.md`（`T-042` 归档条目 + 验收记录）；
- `docs/`：功能线复盘、本操作记录、文档地图登记。

### 4.6 提交记录

| 提交 | 类型 | 内容 | 规模 |
|---|---|---|---|
| `cf0d463` | `refactor` | 模块改名 `product_variant` + 映射表初版（`19.0.7.0.0`，本轮之前） | 32 files |
| `2e2876d` | `feat` | 映射表定稿：穷举展示 / 按需预建 / 候选禁用 + 5 处崩溃修复 + 测试（`19.0.7.0.1` – `19.0.12.0.1`） | 13 files, +1312 −330 |
| `1734e5c` | `docs` | 模块 `README` / `AGENTS`（陷阱 8–19）/ `CHANGELOG` | 3 files, +708 −19 |
| `8898deb` | `docs` | 根 `README` / `AGENTS` / `TODO`（版本与 `T-042` 归档） | 3 files, +7 −7 |
| `7d6e995` | `feat` | 面板定稿：标题 / 显式保存与丢弃 / 未映射不放行 / 移除原生警告（`19.0.13.0.1`） | 7 files, +307 −43 |
| `9e6f4b4` | `docs` | 面板行为、陷阱 20、`19.0.13.0.0` / `19.0.13.0.1` 变更日志 | 6 files, +89 −9 |

提交策略：按「实现（含测试）／模块文档／仓库文档」拆，**文件不重叠**，且实现提交上测试全绿。
未 `push`（截至本记录）。

---

## 5. 产生的变更

### 5.1 数据库变更

| 类别 | 变更 | 是否需要迁移脚本 |
|---|---|---|
| 表结构（字段 / 列） | **无** | **不需要**（本次全功能线未新增 / 改名任何字段或列） |
| 视图 `ir_ui_view` | 继承视图的 arch 随 `-u` 更新：面板挂载节点、**删除原生警告 `<p>` 的 xpath**、台账智能按钮、搜索筛选 | 不需要 |
| 模块元数据 | `ir_module_module.latest_version` → `19.0.13.0.1`，`state = installed` | 不需要 |
| 权限 / 动作 | 无新增、无删除 | 不需要 |
| i18n | 前端 `_t()` 术语与字段文案的中文译文随 `-u` 导入（`i18n/zh_CN.po` 137 条） | 不需要 |
| 系统参数 | 前缀随模块改名从 `product_variant_conversion.` 变 `product_variant.`；代码在新参数未设时**回退读旧名** | 不需要 |

> 唯一需要人工执行的数据库操作是**模块改名**（仅限未改名的库），见第 6.1 节。

### 5.2 文件变更（本轮提交涉及）

| 类别 | 文件 |
|---|---|
| 后端 | `models/product_template.py`、`models/product_variant_mapping.py` |
| 前端 | `static/src/js/variant_mapping_panel.js`、`static/src/js/variant_conversion_form_patch.js`、`static/src/xml/variant_mapping_panel.xml` |
| 视图 | `views/product_template_views.xml` |
| i18n | `i18n/zh_CN.po` |
| 清单 | `__manifest__.py`（版本） |
| 测试 | `tests/js/variant_mapping_pure.mjs`、`tests/test_frontend_consistency.py`、`tests/test_product_variant_conversion.py`、`tests/test_product_variant_mapping.py`、`tests/__init__.py` |
| 文档 | 模块 `README.md` / `AGENTS.md` / `CHANGELOG.md`；根 `README.md` / `AGENTS.md` / `TODO.md`；`docs/product_variant_mapping_review_2026-09-24.md`、`docs/product_variant_mapping_change_record_2026-09-24.md`、`docs/README.md` |

### 5.3 行为变更（用户可见）

| 场景 | 变更前 | 变更后 |
|---|---|---|
| 「属性与变体」页 | 有一句「改属性会删掉并重建变体、自定义会丢失」的警告 | 警告**已移除**（本模块不删变体），改为面板标题 `Variants Mapping` / 「变体映射」 |
| 改属性后的安置方式 | 弹窗逐条确认归属 | 属性行下方**常驻映射表**：组合为行、Variant 为列 |
| 「按需生成」属性的取值 | 不展开（看不出全貌） | **列出来**供分配，但未被既有变体认领的组合**灰显 + 提示**、不预建 |
| 同一变体被两行选 | 自动从原行让出（隐式抢占） | 在下拉里**禁用**；要换位置先把自己那行改回 `(new variant)` |
| 存在未映射变体时保存 | 拦不住 | 保存被拦（前端点名 + 服务端兜底），且**不会被自动保存绕过** |
| 只改了映射 | 无保存入口（表单不脏） | 出现 **Save manually / Discard all changes**（面板内 + 右上角状态指示器） |

---

## 6. 注意事项

### 6.1 生产升级（顺序不可反，先备份）

1. **备份数据库**；
2. 若目标库仍是旧模块名，先执行三条 SQL（**未改名过就跳过**）：
   `ir_module_module.name` → `product_variant`；
   `ir_model_data.module` → `product_variant`（**不做这步会让升级删掉视图 / 动作 / 权限记录**）；
   `base.module_<技术名>` 那条元数据同步改名；
3. `odoo -d <db> -u product_variant --stop-after-init` → **重启 Odoo 服务**（刷新内存注册表）；
4. **强刷浏览器**（Ctrl+F5）。
5. **不要**用「卸载 + 重装」代替：卸载会清空台账 / 谱系 / 变体来源字段。

### 6.2 前端缓存

Odoo 前端的字段与资源缓存是「内存 + 站点存储」，**普通刷新不一定清掉**；改完前端资源（JS / XML / 视图 arch）
必须 `-u`（或重启进程）+ 强刷，必要时用隐私窗口验证。

### 6.3 i18n

- 库里**已存在**的译文不会被 `-u` 覆盖 → 中文界面若仍显示英文，执行 `task i18n -- zh_CN product_variant` 强制刷新；
- 本轮标题文案改了 `msgid`（`Attributes and variants mapping` → `Variants Mapping`），旧条目在库中成为孤儿，无副作用；
- 改英文源文本后必须同步 `i18n/zh_CN.po`，否则中文环境会出现英文。

### 6.4 保存被拦时怎么向用户解释

出现「N 个变体还没有被分配到任何组合」不是故障，而是保护：那条变体一旦不参与本次转换就会被 Odoo 归档 / 删除，
库存与单据会跟着走。**在映射表的 Variant 列给每条变体各选一行即可**（或把它对应的那一行保留）。

### 6.5 仓库文档规范

- **不要**在仓库根新增 `STAGE_REPORT_*.md`（`docs/README.md` 第五节）；
  功能线复盘 / 操作记录写在 `docs/` 下，并在 `docs/README.md` 第二节**登记**；
- 模块目录只放三件套（`README` / `CHANGELOG` / `AGENTS`）；
- 每个事实只有一处权威来源：模块版本 → 根 `README.md` 一览表；逐版本变更 → 模块 `CHANGELOG.md`；
  约束与踩坑 → 模块 `AGENTS.md`；命令语法 → `Taskfile.yml` 的 `desc`。

### 6.6 已知限制

- 前端没有任何自动化测试（浏览器侧行为靠人工验证）；
- 前端交互的静态检查只能拦住「模板名字解析不到」「注册值不是描述对象」这类结构性错误，拦不住逻辑错误。

---

## 7. 执行结果

### 7.1 已验证（自动化 + 服务端查询）

| 验证项 | 结果 |
|---|---|
| 服务端测试 | 63 项 0 failed / 0 error |
| 前端静态检查（4 项） | 通过（含负向验证：回退旧写法会失败） |
| 纯函数离线自测 | 15 项 all good |
| 仓库自检 `task check` | 无失败项 |
| dev 库升级 | 无报错，模块 installed `19.0.13.0.1` |
| 合并后的表单 arch | 面板字段在位、原生警告已消失 |
| 代码检查 | `node --check` / `py_compile` 全部通过 |

### 7.2 未验证（需人工在浏览器确认）

1. 面板渲染与布局：标题、位置（属性行下方独占一行）、宽满；
2. 下拉禁用：已被别行选走的变体灰显、选不了；改回 `(new variant)` 后能选到；
3. 保存拦截：存在未映射时点保存被拦、提示点名；
4. **Save manually / Discard all changes**：出现时机；丢弃后属性行与映射一起回到改动前；
   只改映射不点保存就切菜单 / 切标签时**不应**被自动保存；
5. 「按需生成」属性：未认领组合灰显 + 提示；保存后不凭空多出变体；
6. 中文界面：`变体映射` / `映射有未保存的改动` / `手动保存` / `放弃所有更改`。

---

## 8. 后续建议

1. **目标环境按第 6.1 节升级后，先跑第 7.2 节的 6 项人工验证**，结果回填到模块 `README.md` 的验证清单与 `TODO.md` 的 `T-042` 条目；
2. **补前端自动化**（可选）：仓库目前无浏览器自动化；映射面板的交互（下拉禁用、保存拦截、丢弃回滚）
   适合用 Playwright / Odoo tours 覆盖，可显著降低后续改动风险；
3. **推送提交**：本条功能线的 5 条提交尚未 `push`，确认后再推；
4. **观察「按需生成」属性的实际使用**：若用户希望未认领的按需组合也预建，改动点在
   `_split_variant_conversion_lines()` / `_get_variant_conversion_combinations()`，**不要**只改前端文案；
5. **命名一致性（可选）**：字段 widget 的 `displayName` 仍是 `Attribute / Variant Mapping`（仅出现在字段设置里），
   如需与面板标题统一，改 `variant_mapping_panel.js` 的 `variantMappingPanelField.displayName` 并同步 po；
6. 长期不再查阅本记录时，按 `docs/README.md` 第三节归档（结论已沉淀进模块三件套）。

---

## 9. 追溯入口

| 想查什么 | 命令 / 位置 |
|---|---|
| 本轮改动的文件清单 | `git show --stat 2e2876d 1734e5c 8898deb 7d6e995 9e6f4b4` |
| 某版本的完整说明 | `product_variant/CHANGELOG.md`（`19.0.7.0.0` – `19.0.13.0.1`） |
| 模块当前版本 | `psql -U odoo -d dev -c "SELECT name, state, latest_version FROM ir_module_module WHERE name='product_variant';"` 或 `product_variant/__manifest__.py` |
| 合并后的表单视图 | `odoo shell -d dev --no-http` → `env["product.template"].get_views([(False, "form")])` |
| 测试报告 | `task test -- product_variant --test-tags=/product_variant`；离线自测 `node product_variant/tests/js/variant_mapping_pure.mjs` |
| 仓库自检 | `task check`（等价 `python3 .dev/scripts/check_repo.py`） |
| 设计取舍与踩坑 | [`product_variant_mapping_review_2026-09-24.md`](product_variant_mapping_review_2026-09-24.md)、`product_variant/AGENTS.md` L2 P4 |
| 需求状态 | 根 `TODO.md` → `T-042` |
