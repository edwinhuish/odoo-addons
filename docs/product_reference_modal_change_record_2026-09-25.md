# `product_reference` 额外参考号弹窗 · 操作记录与变更追溯（2026-09-25）

> **文档定位**：本文件记录「额外参考号弹窗（多型号 modal）交互调整」这条改动的**实际操作过程与产生的变更** ——
> 操作目的、时间、环境、执行内容（命令级）、变更清单、注意事项、后续建议。
> 面向「查阅与追溯」：想知道「谁在什么时候做了什么、动到了哪些东西、升级要注意什么」，看这份。
>
> **权威来源分工**（本文件不复制结论，只做归纳与链接）：
>
> | 想知道 | 看哪里 |
> |---|---|
> | 做了什么、产生什么变更、升级注意什么、怎么追溯 | **本文件** |
> | 逐版本变更说明 | `product_reference/CHANGELOG.md` → `19.0.3.1.1` |
> | 约束与「勿改回」清单 | `product_reference/AGENTS.md` → L1 第 9 条 |
> | 模块怎么用 / 验证清单 | `product_reference/README.md` →「用「+」弹窗管理额外参考号」 |
> | 模块当前版本与状态 | 根 `README.md` → 模块一览表 |
>
> **操作人**：AI 助手（CodeBuddy）在本轮协作中执行；目标环境界面验收**待团队成员**。
> 文中的命令均为**实际执行过**的（除明确标注「供目标环境执行」的升级 / 验证步骤）。

---

## 1. 操作目的与背景

用户在 `product_reference` 模块（产品多参考号）上提出两条界面要求：

1. **`Done` 按钮应该在右下方** —— 额外参考号管理弹窗底部的完成按钮目前靠左；
2. **点击 modal 外部不应该隐藏 modal** —— 点在弹窗外（遮罩区域）会把弹窗直接关掉，
   正在录入、还没保存到产品表单的参考号会一起丢。

背景：该弹窗不是 Odoo 的 `dialog` 服务弹窗，而是挂在顶层 `main_components` 的自研 overlay
（与 `product_image` 图库弹窗同一模式），结构与类名刻意与 `web.Dialog` 对齐 ——
所以这两条要求都和「原生长什么样」有关系，动手前必须先核对 Odoo 19 原生实现。

验收口径（用户视角）：`Done` 出现在弹窗右下角、与表格右边缘对齐；点弹窗外弹窗保持打开；
Esc / 右上角 × / `Done` 三个入口仍能正常关闭。

---

## 2. 操作时间与环境

### 2.1 时间线

| 时间（主机本地） | 事件 |
|---|---|
| 2026-09-25 | 读取模块前端模板 / JS / SCSS，确认弹窗结构与本轮改动点 |
| 2026-09-25 | 用 `odoo:19.0` 镜像核对原生 `web.Dialog` 的 footer 类名、close 行为、注释节点支持 |
| 2026-09-25 | 改模板（footer 右对齐 + 不再 click-outside 关闭）+ 同步 JS / SCSS 注释 |
| 2026-09-25 | 版本 `19.0.3.1.1` + 模块 / 根文档同步 + 本地静态自校验 |
| 2026-09-25 | 代码与模块文档提交为 `3946ddb` |
| 2026-09-25 | 文档整理：本操作记录 + `docs/README.md` 地图登记（未提交） |

### 2.2 环境

| 项 | 值（本轮实际） |
|---|---|
| 仓库 | `/home/edwin/Code/odoo-addons`（git 仓库，分支 `main`） |
| Odoo | Odoo **19**，源码 `/usr/lib/python3/dist-packages/odoo` |
| 源码查询方式 | 常驻容器 `odoo19` **当时未运行**（`docker ps -a` 无此容器）→ 改用**本地已有镜像** `odoo:19.0` 起一次性容器只读查询：`docker run --rm odoo:19.0 sh -c "..."`（不启动整套环境、不联网、不另克隆源码） |
| 容器状态实测 | `docker ps -a` → 仅 `naughty_hofstadter`（`hello-world`，已退出）；`docker images` → 存在 `odoo:19.0` |
| 数据库 | **本轮未连库**（纯前端交互 + 文档改动，无需升级 / 查库） |
| 命令入口 | `Taskfile.yml`（`task --list`）；日常手册见 `DEV_WORKFLOW.md` |
| 本地校验 | `python3`（minidom / ast）、`node --check`、AGENTS 4.6 的 po 自校验片段 |

---

## 3. 涉及的系统与模块

| 系统 / 模块 | 涉及内容 |
|---|---|
| 模块 `product_reference` | 前端弹窗模板 `static/src/xml/product_reference_manage.xml`、组件 `static/src/js/product_reference_manage.js`、样式 `static/src/scss/product_reference.scss`、`__manifest__.py` 版本、`CHANGELOG.md` / `AGENTS.md` / `README.md` |
| Odoo Web（`web`） | `web.Dialog` 模板与样式（`static/src/core/dialog/dialog.xml` / `dialog.scss` / `dialog.js`）、`web/static/src/scss/utilities_custom.scss`、OWL 模板编译器（`web/static/lib/owl/owl.js`） |
| Bootstrap 5 工具类 | `justify-content-*`（footer 对齐）、`d-empty-none`（`utilities_custom.scss:201` 定义 `.d-empty-none:empty`） |
| 文档体系 | 模块三件套、根 `README.md`、`docs/`（本记录 + 文档地图） |

---

## 4. 具体执行内容

### 4.1 前置调研：核对 Odoo 19 原生实现（只读）

```bash
docker ps -a --format '{{.Names}}\t{{.Status}}'
docker images --format '{{.Repository}}:{{.Tag}}' | head -20
docker inspect naughty_hofstadter --format '{{.Config.Image}}'
docker run --rm odoo:19.0 sh -c "cat .../web/static/src/core/dialog/dialog.xml; cat .../dialog.scss; grep -n 'enable-important' .../bootstrap_overridden.scss"
docker run --rm odoo:19.0 sh -c "cat .../web/static/src/core/dialog/dialog.js"
docker run --rm odoo:19.0 grep -rn "d-empty-none" .../odoo/addons/web/static/src
docker run --rm odoo:19.0 sh -c "sed -n '880,900p;5055,5075p' .../web/static/lib/owl/owl.js"
```

关键输出（决定改动方案的四条事实）：

| # | 事实 | 出处 |
|---|---|---|
| 1 | 原生 footer 类名是 `modal-footer d-empty-none justify-content-around justify-content-md-start flex-wrap gap-1 w-100`（md 以上**左对齐**） | `web/static/src/core/dialog/dialog.xml` |
| 2 | 原生 `web.Dialog` **没有 click-outside 关闭**：`.modal` 元素上没有任何点击处理（`dialog.js` 里只有 `escape` 热键与 `dismiss()`） | `dialog.xml` / `dialog.js` |
| 3 | `d-empty-none` 是 `.d-empty-none:empty` 的视觉 helper（空容器不占位），保留无副作用 | `web/static/src/scss/utilities_custom.scss:201` |
| 4 | OWL 模板编译器**支持注释节点**（`parseTextCommentNode` → `{type: Comment}`），模板体内写注释安全 | `web/static/lib/owl/owl.js` |

> 结论：要求 ② 其实与原生行为一致（原生也不关）；要求 ① 属于**有意偏离原生**（原生是左对齐），
> 因此在代码与文档里必须写明「有意偏离、勿改回」，不能写成「沿用原生」。

### 4.2 代码修改（3 个前端文件）

| 文件 | 改动 |
|---|---|
| `static/src/xml/product_reference_manage.xml` | ① 去掉 `.modal` 上的 `t-on-click.self="close"`；② footer 的 `justify-content-around justify-content-md-start` → **`justify-content-end`**；③ 头注释增补「两处有意偏离原生」+ 关闭入口；④ footer 前加一行说明注释 |
| `static/src/js/product_reference_manage.js` | 「关闭」段落注释：删除「遮罩」这一入口并说明为何不加 click-outside（不改逻辑，`close()` 仍被 × 与 `Done` 使用） |
| `static/src/scss/product_reference.scss` | 弹窗段注释：注明遮罩**点击不关闭**、footer 对齐由模板工具类负责、此处不再覆盖样式 |

改动后的关键代码：

```xml
<div role="dialog"
     class="o_product_reference_manage modal d-block o_technical_modal"
     tabindex="-1"
     t-ref="autofocus"
     t-on-keydown.stop="onKeydown">
```

```xml
<footer class="modal-footer d-empty-none justify-content-end flex-wrap gap-1 w-100">
    <button type="button" class="btn btn-primary" t-on-click="close">Done</button>
</footer>
```

### 4.3 版本与文档同步

| 载体 | 内容 |
|---|---|
| `product_reference/__manifest__.py` | 版本 `19.0.3.1.0` → **`19.0.3.1.1`**（修复 / 文档位 +z） |
| `product_reference/CHANGELOG.md` | 新增 `[19.0.3.1.1] - 2026-09-25`（变更 / 影响 / 验证记录） |
| `product_reference/AGENTS.md` | 「当前版本」行更新 + L1 第 9 条新增「**两处有意偏离原生，勿改回**」清单 |
| `product_reference/README.md` | 「用「+」弹窗管理额外参考号」小节增补两条行为 + 关闭入口；验证清单新增 2 行（`19.0.3.1.1`） |
| 根 `README.md` | 模块一览表 `product_reference` 版本与状态；模块版本对照表版本 |

### 4.4 本地自校验（无 Odoo 环境也能跑）

```bash
python3 -c "import xml.dom.minidom; xml.dom.minidom.parse('product_reference/static/src/xml/product_reference_manage.xml')"
for f in product_reference/static/src/js/*.js; do cp "$f" /tmp/chk.mjs && node --check /tmp/chk.mjs; done
python3 -c "import ast; ast.literal_eval(open('product_reference/__manifest__.py',encoding='utf-8').read())"
grep -rn "t-on-click.self" product_reference/static/src/xml/
# AGENTS 4.6 的 po 自校验：重复 msgid + 应用列表元数据一致性
git --no-pager diff --stat
```

| 检查项 | 结果 |
|---|---|
| XML 解析（minidom） | `XML OK` |
| JS 语法（`node --check`） | `product_reference_editor.js` / `product_reference_manage.js` 均 OK |
| `__manifest__.py` 可解析 | `manifest OK` |
| 残留 `t-on-click.self` | 仅**注释**里命中一处（模板指令已移除） |
| po 重复 `msgid` | `dup msgid: []` |
| 应用列表元数据一致性 | `apps metadata ok`（`shortdesc` / `summary` / `description` 的 `msgid` 与 manifest 逐字符一致） |
| 编辑器诊断（`read_lints`） | 0 条 |
| 改动规模 | `git diff --stat` → **8 files changed, 76 insertions(+), 17 deletions(-)** |

---

## 5. 产生的变更

### 5.1 数据库变更

| 类别 | 变更 | 是否需要迁移脚本 |
|---|---|---|
| 表结构 / 字段 | **无** | **不需要** |
| 视图 / 数据文件 | **无**（未改 `views/`、`security/`、`data`） | **不需要** |
| 模块元数据 | `ir_module_module.latest_version` 随 `-u` 变为 `19.0.3.1.1` | 不需要 |
| i18n | **无新增术语**（`Done` 的 `msgid` / `msgstr` 未变），无需重新导入译文 | 不需要 |

> 本轮**不需要**任何人工数据库操作，纯前端改动 + 文档。

### 5.2 文件变更

| 类别 | 文件 |
|---|---|
| 前端 | `product_reference/static/src/xml/product_reference_manage.xml`、`.../js/product_reference_manage.js`、`.../scss/product_reference.scss` |
| 清单 | `product_reference/__manifest__.py`（版本） |
| 模块文档 | `product_reference/CHANGELOG.md`、`AGENTS.md`、`README.md` |
| 根文档 | `README.md` |
| `docs/` | `docs/product_reference_modal_change_record_2026-09-25.md`（本文件）、`docs/README.md`（地图登记） |

> **提交状态**：上一轮的 8 个文件已提交为 `3946ddb`
> `fix(product_reference): 额外参考号弹窗 Done 右对齐且点外部不关闭`（8 files, +76 −17）；
> `docs/` 下的本记录与 `docs/README.md` 地图登记**尚未提交**（`git status --short` → `M docs/README.md`、`?? docs/product_reference_modal_change_record_2026-09-25.md`）。

### 5.3 行为变更（用户可见）

| 场景 | 变更前 | 变更后 |
|---|---|---|
| 弹窗底部 `Done` 位置 | 靠左（`justify-content-md-start`，与原生 19.0 一致） | **靠右下角**（`justify-content-end`） |
| 点击弹窗外灰色遮罩 | 弹窗被关闭（未保存的录入一起丢） | **弹窗保持打开**（与原生 `web.Dialog` 一致） |
| 关闭入口 | × / 遮罩 / Esc / `Done` | **× / Esc / `Done`** 三个 |

---

## 6. 遇到的问题与解决办法

| # | 问题 | 原因 | 解决办法 |
|---|---|---|---|
| 1 | 想核对原生实现时，AGENTS 里写的常驻容器 `odoo19` 不存在 | `docker ps -a` 只有 `naughty_hofstadter`（`hello-world`，已退出），本地 Odoo 开发环境当时未启动 | **不启整套环境**，用本地已有镜像 `odoo:19.0` 起一次性容器只读查询（`docker run --rm odoo:19.0 sh -c "cat/grep ..."`）—— 符合 AGENTS「查源码一律在 Odoo 容器里、不要另克隆」的约束，且离线、无副作用 |
| 2 | 原模板注释声称「footer 沿用原生（**左对齐**）」，与「Done 应靠右」的需求冲突 | 两条要求指向相反方向，若含糊处理会让后续维护者以「统一原生」为由改回左对齐 | 与源码逐字核对后确认原生确实是 `justify-content-md-start`，于是把「Done 右对齐」明确标为**有意偏离原生**：模板头注释 + `AGENTS.md` L1 第 9 条「勿改回」清单 + `README.md` 三条同时写明，防止被无意改回 |
| 3 | 「点弹窗外不关闭」看似是偏离原生，担心与仓库「弹窗沿用原生」的约束冲突 | 直觉认为原生弹窗点遮罩会关 | 查 `dialog.xml` / `dialog.js` 证实**原生也没有 click-outside 关闭**（只有 Esc 与 `dismiss()`），因此本改动反而更贴近原生；该事实写进注释作为依据 |
| 4 | 想在模板 `<main>` 与 `<footer>` 之间加说明注释，但不确定 OWL 是否支持模板体内注释 | OWL 用自己的模板编译器，注释若不被识别会编译报错 | 查 `owl.js` 的 `parseTextCommentNode`：`Node.COMMENT_NODE` 被编译为 Comment 节点（`sed` 实测源码），确认安全后再写 |
| 5 | 改 footer 对齐时不确定能否靠「多写一个工具类」覆盖 | 原生类里有 `justify-content-md-start`（md 媒体查询内），另加 `justify-content-end` 会形成两条 `justify-content` 的次序竞争，结果依赖样式表顺序 | 改为**替换**而非叠加：直接把对齐类换成 `justify-content-end`，单一 `justify-content` 声明，不依赖顺序、不用 `!important`，也不新增自定义 footer 样式 |

---

## 7. 执行结果

### 7.1 已完成

| 项 | 结果 |
|---|---|
| `Done` 按钮右下角 | 已改（模板 footer 换 `justify-content-end`，其余类名与原生一致） |
| 点弹窗外不关闭 | 已改（移除 `t-on-click.self="close"`，与原生 `web.Dialog` 一致） |
| 关闭入口保持可用 | × / Esc / `Done` 三处逻辑未动（`close()` 仍被两处按钮引用） |
| 版本 / 文档同步 | `19.0.3.1.1`；模块三件套 + 根 `README.md` + 本记录 + `docs/README.md` 地图 |
| 本地静态校验 | XML / JS / manifest / po 一致性 / lint **全部通过**（见 4.4） |
| 迁移 | **不需要**（无字段、无数据、无术语变更） |

### 7.2 待验证（需在目标环境浏览器确认）

> 供目标环境执行：

```bash
odoo -d <db> -u product_reference --stop-after-init
```

1. **强刷浏览器**（前端模板与样式吃缓存，普通刷新不一定生效），英文 / 中文各验一遍；
2. 打开产品表单 → `Ref.` 输入框内「+」：`Done` 在弹窗**右下角**、与表格右边缘对齐；
3. 点弹窗外灰色遮罩：弹窗**保持打开**；Esc / × / `Done` 三个入口仍能关闭；
4. 回归：弹窗内新增 / 改值 / 改类型 / 停用 / 删除 / 上移下移均正常，关闭后点产品「保存」才入库。

**回滚方式**：把 footer 的对齐类改回 `justify-content-around justify-content-md-start`、
给 `.modal` 加回 `t-on-click.self="close"`（或整体回退到 `19.0.3.1.0`），
并按需把根 `README.md` 一览表版本一并回退。

---

## 8. 后续建议

1. 目标环境按 7.2 验证后，把结果回填到 `product_reference/README.md` 的验证清单（两行 `19.0.3.1.1`）；
2. 若后续又收到「与原生保持一致」的意见，注意本条是**用户明确要求的有意偏离**，
   先读 `product_reference/AGENTS.md` L1 第 9 条的「勿改回」清单再决定；
3. 若希望彻底避免 `Done` 位置争议，可评估改用 Odoo `dialog` 服务（原生 footer 左对齐、
   由服务统一管遮罩与栈），但会牵动「弹窗挂 `main_components` 以避免表单重渲染闪烁」的既有设计，
   属于架构级改动，需单独评估；
4. 本记录结论完全沉淀进模块三件套、且不再有人查阅后，按 `docs/README.md` 第三节归档到 `docs/archive/`。

---

## 9. 追溯入口

| 想查什么 | 命令 / 位置 |
|---|---|
| 本轮提交与改动清单 | `git show --stat 3946ddb`（代码 + 模块 / 根文档，8 files）；本记录与 `docs/README.md` 登记未提交 |
| 本轮改动明细 | `git --no-pager show 3946ddb -- product_reference/static/src` |
| 本版本完整说明 | `product_reference/CHANGELOG.md` → `[19.0.3.1.1]` |
| 「勿改回」约束 | `product_reference/AGENTS.md` → L1 第 9 条「两处有意偏离原生」 |
| 用户可见行为与验证清单 | `product_reference/README.md` →「用「+」弹窗管理参考号」/ 验证清单 |
| 模块当前版本 | `product_reference/__manifest__.py` 或 `psql -U odoo -d dev -c "SELECT name, state, latest_version FROM ir_module_module WHERE name='product_reference';"` |
| 原生 footer 类名依据 | `docker run --rm odoo:19.0 cat /usr/lib/python3/dist-packages/odoo/addons/web/static/src/core/dialog/dialog.xml` |
| 原生 close 行为依据 | 同上的 `.../core/dialog/dialog.js`（只有 `escape` 热键，无 click-outside） |
