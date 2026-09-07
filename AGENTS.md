# AGENTS

本仓库是 **Odoo 19 外贸 SOHO 进销存**的自研 addons 集合。给 AI 助手与新开发者看的行为规范与关键上下文。

## 1. 业务背景

- 使用者：外贸 SOHO（一人 / 小团队），要求操作简单、少点几下就能录完单据。
- 核心链路：产品（参考号 / 图片）→ 报价单 → 销售订单 → 采购 → 出入库 → 收付款 / 发票。
- 语言：文档与代码注释统一**简体中文**；**模块源语言为英文（`en_US`），默认展示英文**，简体中文译文放 `i18n/zh_CN.po`，语言切换后界面随之更新（详见第 4 节「国际化（i18n）规范」）。金额默认涉及多币种（报价常用 USD）。
- 对外单据编号是业务刚需：客户编码 + 年份 + 流水号（如 `DZ2602`），内部 `SOxxxx` 不对外。

## 2. 仓库约定

- 仓库根目录（`<addons-path>`）**即 `addons_path`**：一个模块一个一级目录，根目录只放文档。
  文档中出现的 `<addons-path>`、`<db>`、`<module>`、`<version>` 均为占位符，按实际部署值替换，不要写死本机路径。
- **本仓库不含 Odoo 源码与数据库**，模块无法在仓库内独立运行；改动需挂到目标 Odoo 环境安装/升级后验证，
  交付时给出「待验证清单」。
- **查阅 Odoo 源码**：应前往 `/tmp/odoo` 目录进行查阅；若该目录不存在，则需重新执行
  `cd /tmp && git clone --depth 1 -b 19.0 git@github.com:odoo/odoo.git` 命令进行克隆，
  不要每次都 curl GitHub 以免触发限流。
- 模块目录骨架：

```text
<module>/
|-- __init__.py            # from . import models
|-- __manifest__.py
|-- models/
|-- views/
|-- security/              # 有独立模型时必须有 ir.model.access.csv
|-- static/src/{js,xml,scss}/
|-- i18n/                  # 译文：zh_CN.po（源语言 en_US 写在代码里，无需 en_US.po）
|-- migrations/<version>/  # 仅在字段/数据需要迁移时
|-- README.md  CHANGELOG.md  AGENTS.md
```

## 3. 模块规范

- `version` 一律 `19.0.x.y.z`：架构/破坏性变更 +x，功能新增 +y，修复与文档 +z。
- `__manifest__.py` 必填：`name`（中文）、`summary`、`description`、`category`、`author`、`depends`、`installable: True`、`license`。静态资源走 `assets`（`web.assets_backend`），不走 `data`。
- `depends` 最小化：能用 `product` 就不要依赖 `sale`；不要为了方便依赖 `website`。
- 新增模型必须配 `security/ir.model.access.csv`，权限最小化（普通用户可读写业务数据，管理员可配置）。
- 数据文件（视图/报表/权限）必须登记进 `data`，顺序：security → views → reports → data。
- 模块命名：`<业务域>_<功能点>`（如 `sale_order_no`、`product_reference`）；纯前端通用增强用 `web_` 技术层前缀（如 `web_image_paste`，符合 Odoo `web_*` 惯例）；**禁止**用 Odoo 官方模块名。**不加项目统一前缀**（`soho_` 等）——会偏离 Odoo 生态惯例，且改名需卸载重装生产库；自研模块归属用 `author: "edwinhuish"` 字段标识。命名约定完整版见 `DOCS_TEMPLATE.md`。

## 4. 国际化（i18n）规范

### 4.1 基本约定

- **源语言固定英文（`en_US`）**：Python / XML / JS / QWeb 模板里所有用户可见文本一律写英文，中文不写回源码；**不提供 `en_US.po`**（源语言即英文，Odoo 直接用源码文本）。
- **译文目录**：简体中文 `i18n/zh_CN.po`；新增语言按 `<lang>.po` 追加（如 `zh_TW.po`）。`i18n/` **无需登记进 `data`**，Odoo 安装 / 升级模块时自动扫描导入。
- **默认英文**：未安装中文语言的库一律显示英文；安装「简体中文 (zh_CN)」并切换后显示中文。
- **代码注释保持中文**：注释不参与翻译（XML 注释属于 `SKIPPED_ELEMENT_TYPES`），不要为 i18n 把注释改英文。
- **manifest 例外**：`name` / `summary` / `description` 写英文即可——模块描述的译文由 Odoo 官方在 `base` 的 po（`model:ir.module.module,description:base.module_<module>`）里集中维护，自研模块的 `i18n/zh_CN.po` 里写它匹配不到、无效果，不要浪费条目。

### 4.2 可翻译入口对照表（写错入口 = 翻译不生效）

| 位置 | 源码写法 | `.po` 里的 `#:` 类型 |
|------|----------|----------------------|
| 模型名 | `_description` | `model:ir.model,name:<module>.model_<model>` |
| 字段标签 | `string=` | `model:ir.model.fields,field_description:<module>.field_<model>__<field>` |
| 字段 help | `help=` | `model:ir.model.fields,help:<module>.field_<model>__<field>` |
| selection 标签 | `selection=[("k", "Label")]` | `model:ir.model.fields.selection,name:<module>.selection__<model>__<field>__<k>` |
| 约束消息 | `models.Constraint(def, "msg")` | `model:ir.model.constraint,message:<module>.constraint_<属性名去掉前导下划线>` |
| 视图 arch | `string` / `help` / `placeholder` / 文本节点 | `model_terms:ir.ui.view,arch_db:<module>.<view_xmlid>` |
| 动作名称 | `<field name="name">` | `model:ir.actions.act_window,name:<module>.<id>`（服务端动作用 `ir.actions.server`） |
| 动作空视图帮助 | `<field name="help" type="html">` | `model_terms:ir.actions.act_window,help:<module>.<id>` |
| Python 运行期文案 | `_("...")` | `code:addons/<module>/models/<file>.py:0` |
| JS 文案 | `_t("...")` | `code:addons/<module>/static/src/js/<file>.js:0` |
| QWeb 模板文本 / `title` / `aria-label` | 直接写英文 | `code:addons/<module>/static/src/xml/<file>.xml:0` |

> `<model>` 里的点换成下划线（如 `product.reference.code` → `product_reference_code`）；`<field>` 前是双下划线。

### 4.3 已核实的 Odoo 19 抽取事实（对照 `odoo/tools/translate.py`）

- 术语一律 **`_push()` 后 `.strip()`**，但**内部的换行与缩进会保留** → 可译文本必须写成**单行**，否则 po 里的 `msgid` 会带上换行缩进，极易写错。
- 视图 `arch_db` 是 `translate=xml_translate`，`ir.actions.act_window.help` 也是 HTML 术语翻译 → 都是**按术语**存，不是整段 arch；`translate_xml_node` 用 `content.strip()` 取术语，属性用 `val.strip()`。
- 视图 arch 里能被抽取的属性见 `TRANSLATED_ATTRS`（`string` / `help` / `placeholder` / `title` / `alt` / `label` / `confirm` …）；OWL 模板里能被抽取的见 `OWL_TRANSLATED_ATTRS`（`alt` / `aria-label` / `label` / `placeholder` / `title` / `data-tooltip` …）。**`t-att-*`（动态属性）不会被翻译**。
- QWeb 模板中**每个文本节点、每个属性各自独立成术语** → 一句话里夹了子元素（`<kbd>Ctrl</kbd>+<kbd>V</kbd>`、`<t t-esc>`）就会被切碎，无法整体翻译。
- JS `_t` 由转译器自动注入模块名作上下文，不同模块的同名词条互不干扰；`.po` 里加 `#. odoo-javascript` / `#. odoo-python` 注释是与官方导出格式对齐，不影响导入。
- 不要在 `.po` 里写**重复的 `msgid`**：同一 `msgid` 只能有一条，多个来源合并到一条的多个 `#:` 引用上，否则 po 解析报错。

### 4.4 禁止的写法（本次改造的真实坑）

| 反面写法 | 后果 | 正确做法 |
|----------|------|----------|
| `hint = "（命中参考号：%s）" % codes` | Python 侧硬编码中文，永远不变语言 | `_(" (Matching reference: %(codes)s)", codes=codes)` |
| `_("...%s...%s") % (a, b)` | 译者无法调整语序 | `_("...%(name)s...%(other)s", name=a, other=b)` |
| `t-att-aria-label="'删除' + it.name"` | 动态属性不翻译 | JS 侧 `_t("Delete %(name)s", { name })`，模板调方法 |
| `<span>已选 <t t-esc="n"/> 张</span>` | 三个术语碎片，无法翻译 | getter 里 `_t("%(count)s selected", {count})` + `t-esc` |
| `或按 <kbd>Ctrl</kbd>+<kbd>V</kbd> 粘贴…` | 被 `<kbd>` 切碎 | 拆成前缀/后缀两个完整可译片段，各自 `_t()` |
| 多行文本节点 | `msgid` 带换行缩进，写不对 | 压成单行 |
| `.po` 中同一 `msgid` 写两条 | po 解析失败，整份译文不导入 | 合并为一条多 `#:` 引用 |

### 4.5 执行 SOP（下次做 i18n 直接照此顺序）

1. **盘点**：`grep -rnP '[\x{4e00}-\x{9fff}]' --include=*.py --include=*.xml --include=*.js <module>`，剔除注释后即为待改清单；同时搜 `_t(`、`_(` 看已有入口。
2. **改源文本**：按 4.2 表逐处改英文；占位符统一 `%(name)s`。
3. **修模板**：把拼接句、夹子元素的句子改成单行或拆到 JS getter。
4. **写 `.po`**：按 4.2 表的键名写 `msgid`（英文源文本，一字不差）/ `msgstr`（中文），每条带 `#. module: <module>` + `#:` 引用。
5. **自校验**（无 Odoo 环境也能跑，见 4.6）。
6. **提版本 + 同步文档**：manifest（版本 + 英文 name/summary/description）、模块 `CHANGELOG.md` / `README.md` / `AGENTS.md`、根 `README.md` / `AGENTS.md` / `TODO.md`。
7. **交付**：给出「待验证清单」——升级命令、英文与中文各验一遍、强刷浏览器、回滚方式。

### 4.6 自校验脚本（改造后必跑）

```python
# 1) 重复 msgid 检查（重复会导致整份 po 解析失败）
import glob, re, collections
for f in sorted(glob.glob("*/i18n/*.po")):
    s = open(f, encoding="utf-8").read()
    ids = ["".join(re.findall(r'"((?:[^"\\]|\\.)*)"', e))
           for e in re.findall(r'^msgid ((?:"(?:[^"\\]|\\.)*"\s*)+)', s, re.M)]
    dup = [k for k, v in collections.Counter(ids).items() if v > 1]
    print(f, len(ids), "dups:", dup)

# 2) 残留中文界面文本检查（命中应只剩下注释）
# grep -rnP '[\x{4e00}-\x{9fff}]' --include="*.py" --include="*.xml" --include="*.js" --include="*.csv" .

# 3) XML / JS 语法
# python3 -c "import glob,xml.dom.minidom;[xml.dom.minidom.parse(f) for f in glob.glob('*/**/*.xml',recursive=True)]"
# for f in <module>/static/src/js/*.js; do cp $f /tmp/chk.mjs && node --check /tmp/chk.mjs; done
```

### 4.7 验证与运维注意

- 前端术语（JS `_t` / QWeb 模板）由前端缓存，**`-u` 升级后必须强刷浏览器**才看得到新译文；后端字段标签 / help / 报错刷新页面即可。
- 源文本改英文后，旧的中文源文本对应的 `ir.translation` 行会成为孤儿项（msgid 已变、不再被查），不影响显示，可在「设置 → 翻译」清理。
- 只做 i18n 的改动**不需要迁移脚本**（不涉及字段与数据结构）；但仍要 `-u` 升级，否则新译文与新的字段标签不会写入库。

## 5. Python 规范

- **禁止修改 Odoo 核心源码**；一律 `_inherit` 扩展，必须改行为时用 patch / 继承并注明原因。
- 创建/写入入口统一用 `@api.model_create_multi` 的 `create` 与 `write`，不要在旧式单个 create 上做逻辑。
- Odoo 19 显示名统一用 `_compute_display_name()`；`name_get()` / `name_search()` 已从核心移除，禁止再定义或依赖（详见下一节）。
- 字段定义要有中文 `string` 与 `help`；业务字段加 `index=True`（凡是要搜索的字段）；`copy=False` 需显式声明。
- 校验用 `@api.constrains` + `ValidationError`，错误信息必须是可直接给用户看的中文，带上出错的具体值。
- 搜索能力必须在数据库层实现：可 `store=True` 的计算字段配索引，或字段级 `search=` 方法，或 `('x2many', 'any', [...])` 域；禁止先 `search([])` 再在 Python 里过滤。
- 结构变更必须写 `migrations/<version>/pre-migration.py`（改名、改类型、数据回填），并在 CHANGELOG 说明影响。
- 编号 / 流水类字段：创建时一次性快照写入，后续不因主数据变化而重算；作废、取消、删除不回收已用号。

### 已核实的 Odoo 19 API 事实（对照 `odoo/odoo@19.0` 源码）

- `name_get()` / `name_search()` 已从核心移除，只剩 `_compute_display_name()` 与 `_search_display_name(operator, value)`（后者返回 `Domain` 对象）。
- 名称搜索走 `_search_display_name()`，可在其中 OR/AND 进自定义字段；否定操作符（`not ilike` 等）必须取交集。
- `Domain` 从 `odoo.fields` 导入：`from odoo.fields import Command, Domain`；`Domain.OR/AND` 接受任意 domain 表达式。
- `_sql_constraints` 已废弃，改用模型属性：`_xxx_unique = models.Constraint("UNIQUE(field)", "提示")`、`models.Index(...)`、`models.UniqueIndex(...)`。
- `web_search_read(domain, specification, offset, limit, order, count_limit)` 定义在 `web` 模块的 `_inherit='base'` 上，所有模型可用。
- 视图继承：扩展祖先视图（extension）对其所有 primary 子视图生效，改列表要继承基础列表而非某个 primary 子视图。
- 改动前先核对目标结构：查阅 Odoo 源码时，应前往 `/tmp/odoo` 目录进行查阅；若该目录不存在，则需重新执行 `cd /tmp && git clone --depth 1 -b 19.0 git@github.com:odoo/odoo.git` 命令进行克隆，避免每次直连 GitHub 触发限流。

## 6. 前端规范

- JS 文件首行必须是 `/** @odoo-module **/`；用 `@web/core/utils/patch` 打补丁，不覆写整个组件。
- QWeb 用 `t-inherit` + `t-inherit-mode="extension"` 扩展原模板，不复制核心模板全文。
- 静态资源放 `static/src/{js,xml,scss}/`（如 `web_image_paste` 为此结构，迁移时保持一致）。
- 事件处理要判 `props.readonly`，只读态不得触发写操作。
- 复用原生上传 / 校验链路（如 `onFileUploaded`、`checkFileSize`），不重复实现。

## 7. 文档与变更规范

每次功能改动必须同步更新，缺一不可：

1. `__manifest__.py` 的 `version`（按第 3 节规则递增）与 `description`（涉及用户可见行为时）
2. 模块 `CHANGELOG.md`：变更 / 影响 / 文档同步三段式，注明日期
3. 模块 `README.md`：用户可见功能、字段表、安装与使用步骤
4. 模块 `AGENTS.md`：**不可破坏的核心约束**清单（约束变化时更新）
5. 根目录 `TODO.md`：任务状态流转（见第 8 节）

> 三类模块文档（`README.md` / `CHANGELOG.md` / `AGENTS.md`）的统一骨架与约定见根目录 [`DOCS_TEMPLATE.md`](DOCS_TEMPLATE.md)，新模块按此创建，既有模块迭代时按此对齐。

## 8. TODO.md 使用规则

- `TODO.md` 是**待处理需求**的唯一入口，仅记录待办 / 进行中 / 搁置项，不要在对话里另立清单。
- 新需求追加到「待办池」末尾并取下一个 ID；开工移入「进行中」并补齐验收标准；验收通过后整条移出本文件，完成信息（日期 / 落地版本 / 验收记录 / 异常与维护）沉淀到对应模块的 `CHANGELOG.md` 与 `README.md` / `AGENTS.md`，根 `README.md` 模块一览表更新状态；不做则移入「搁置」并写原因。
- 动工前先读该条目的「设计约束」，有疑问在条目下以备注形式记录，不要自行放宽约束。

## 9. 已有模块速查

> 自研模块通过 `__manifest__.py` 的 `author: "edwinhuish"` 字段统一标识归属，应用列表可按 author 筛选；模块命名遵循 `<业务域>_<功能点>` 约定（见 `DOCS_TEMPLATE.md`），不加项目前缀。

| 模块 | 版本 | 作用 | 状态 |
|------|------|------|------|
| `sale_order_no` | 19.0.1.8.0 | 销售订单 / 报价单自定义编号（`order_no`，客户编码 + 两位年份 + 年度流水），含客户编码格式校验、报表替换、PDF 文件名定制、门户预览定制、批量补号 | 已交付，目标环境已验证（T-001） |
| `web_image_paste` | 19.0.2.1.0 | 后台图片字段粘贴 / 拖拽上传（patch `ImageField` + `FileUploader`，复用原生上传链路，即时预览 + 进度条；原名 `image_uploader`） | 已交付，目标环境已验证（T-003） |
| `product_reference` | 19.0.2.2.0 | 产品多参考号 + 可搜索（One2many 明细 / 冗余 trigram 索引 / 命中提示）；`19.0.2.0.0` 由 `product_model` 改名（模型 `product.model.code` → `product.reference.code`，含幂等迁移脚本与升级前置 SQL）；`19.0.2.2.0` 参考号页顶部直接展示 Odoo 原生 `default_code`（Reference）供统一编辑，不再在参考号表中存储镜像行 | 已交付，目标环境已验证（T-002）；`19.0.2.0.0` 改名与 `19.0.2.2.0` 前端展示均待目标环境验证 |
| `product_image` | 19.0.2.5.0 | 产品多图（原生主图独立 + 图库补充图 / 主图无删除入口/ 首张上传即主图 / 主图 2 倍 / 悬浮局部放大（540窗口+1080图片平移·左侧不足转下方/缩小·选框按比例·留白区白色）/ 点击预览（多图切换+右侧缩略图·关闭按钮暗色半透明·底部条默认透明悬浮淡入·图片初始避开上下条放大可覆盖全屏·任意大小可拖拽grab/grabbing·GPU 1:1顺滑·切图保留状态·无滚动条·缩略图未选中无边框）/ 右侧竖排缩略图（蓝色选中边框·编辑态无删除按钮·滚动不越界且与主图区顶底贴边·仅切换不写库）/ 图片管理弹窗（「+」打开·顶层overlay：上半大图（仅预览、无删除按钮）+平铺缩略图（每张含主图右上角×：删图库删记录·删主图自动提升图库首张·点缩略图只切弹窗大图·缩略图可拖排序(含主图·首位即主图·避让动画)·删除均先确认(含缩略图·主图提示提升)·批量删除(勾选模式+含缩略图清单确认)·大图固定尺寸缩略图占满余量超高滚动·选中主图名称行留空）·下半dropzone 点击/拖放/Ctrl+V（上传中缩略图+动画·粘贴后不自动关闭·上传不改页面大图）·header 最右侧正方形×关闭按钮 hover 变红）/ 继承 image.mixin 复用多尺寸；原名 `product_multi_image`） | 已交付，目标环境已验证（T-005，19.0.2.4.2，含 19.0.2.2.10~4.2：拖动排序（含主图·首位即主图）/ 删除确认 / 批量删除 / 选中主图名称行留空 / 确认框按钮顺序 / 关闭按钮贴边）；坑点与风险提示见模块 `AGENTS.md` →「会话修改总结与风险提示」/「开发复盘与关键经验（T-005）」 |
| `product_packing` | 19.0.1.0.0 | 为产品 Inventory 标签页增加外贸纸箱字段：装箱数、长宽高（厘米 / 米可配置）、毛重、净重、自动计算 CBM；产品列表增加纸箱规格与 CBM 可选列 | 进行中（T-009），待目标环境验证 |

## 10. 验证流程

模块必须挂到目标 Odoo 环境才能运行，仓库内无法直接执行。在已部署 Odoo 服务与数据库的环境上执行：

```bash
# 更新应用列表后安装
odoo -d <db> -i <module> --stop-after-init
# 代码改动后升级（含前端资源）
odoo -d <db> -u <module> --stop-after-init
# 开发期热更新视图
odoo -d <db> --dev=xml
```

- 前端资源改动后必须 `-u` 升级并强刷浏览器（Odoo 资源有缓存）。
- 涉及字段改名的改动，先在测试库跑迁移脚本，确认无数据丢失再上生产库。
- 交付时附「待验证清单」：改了什么、在哪验证、怎么验、回滚方式。
