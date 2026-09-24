# AGENTS

本仓库是 **Odoo 19 外贸 SOHO 进销存**的自研 addons 集合。给 AI 助手与新开发者看的行为规范与关键上下文。

## 1. 业务背景

- 使用者：外贸 SOHO（一人 / 小团队），要求操作简单、少点几下就能录完单据。
- 核心链路：产品（参考号 / 图片）→ 报价单 → 销售订单 → 采购 → 出入库 → 收付款 / 发票。
- 语言：文档与代码注释统一**简体中文**；**模块源语言为英文（`en_US`），默认展示英文**，简体中文译文放 `i18n/zh_CN.po`，语言切换后界面随之更新（详见第 4 节「国际化（i18n）规范」）。金额默认涉及多币种（报价常用 USD）。
- 对外单据编号是业务刚需：客户编码 + 年份 + 流水号（如 `DZ2602`），内部 `SOxxxx` 不对外。

## 2. 仓库约定

- 仓库根目录（`<addons-path>`）**即 `addons_path`**：一个模块一个一级目录，根目录只放**长青文档**
  （`README.md` / `AGENTS.md` / `TODO.md` / `DOCS_TEMPLATE.md` / `DEV_WORKFLOW.md`）与统一开发入口
  （`Taskfile.yml`）；
  本地开发环境（compose + 辅助脚本）在 `.dev/`，日常用法见 [`DEV_WORKFLOW.md`](DEV_WORKFLOW.md)，
  环境搭建过程 / 方案选型 / 当时的踩坑记录已归档到
  [`docs/archive/DEV_ENV_SETUP.md`](docs/archive/DEV_ENV_SETUP.md)
  （其中仍有效的约束已并入 `DEV_WORKFLOW.md` 第 1 / 8 节）。
- **阶段性产物不留在根目录**：阶段报告等时效性文档进 `docs/archive/`，策略与决策记录见
  [`docs/README.md`](docs/README.md) →「三、归档策略」。文档总地图以 `docs/README.md` 为准。
  文档中出现的 `<addons-path>`、`<db>`、`<module>`、`<version>` 均为占位符，按实际部署值替换，不要写死本机路径。
- **本仓库不含 Odoo 源码与数据库**，模块无法在仓库内独立运行；改动需挂到目标 Odoo 环境安装/升级后验证，
  交付时给出「待验证清单」。
- **查阅 Odoo 源码：一律在 Odoo 容器里查，不要另外下载或克隆一份**。本地跑的 Odoo 就是官方镜像
  （`odoo:19.0`），源码就在镜像里，也正是**运行时真正加载的那份**（`odoo.conf` 的 `addons_path` 指向它），
  版本必然与本地运行/服务器一致：
  1. 核心框架：`/usr/lib/python3/dist-packages/odoo/`（`orm/`、`fields/`、`http.py`、`cli/`、`tools/`，
     标准模块在 `odoo/addons/`）。
  2. 另一份 addons 包：`/usr/lib/python3/dist-packages/addons/`（`account`、`sale` 等）。
  3. 仓库自己的模块：`/mnt/extra-addons/`（= 本仓库，宿主机上直接看）。

  查法（不必进交互式 shell，一条命令即可）：

  ```bash
  docker exec odoo19 grep -rn "def _compute_display_name" /usr/lib/python3/dist-packages/odoo/orm/
  docker exec odoo19 sed -n '1,60p' /usr/lib/python3/dist-packages/odoo/orm/models.py
  docker exec odoo19 grep -rn "t-inherit" /usr/lib/python3/dist-packages/odoo/addons/sale/views/ | head
  task bash                      # 要连着看多处 / 用 less 时，进容器里查
  ```

  想在编辑器里读、跳转、打断点（Pylance / debugpy）：跑一次 `task odoo-src`，它把镜像里的核心 `.py`
  导到 `.dev/.cache/odoo-src`（约 160MB，从镜像里取、不联网、已 gitignore；`task odoo-src-clean` 删掉），
  `.vscode/settings.json` 与 `launch.json` 已指向那里；或用
  `Remote-Containers: Attach to Running Container` 直接浏览容器内目录。

  > 每个会话第一次查源码前，先 `docker exec odoo19 ls /usr/lib/python3/dist-packages/odoo` 确认容器在跑
  > （没在跑就 `task up`）；**不要**克隆 `../odoo` / `/tmp/odoo`，也不要每次直连 GitHub（限流）。
  > 要换 Odoo 版本就改 `.dev/compose.yml` 里的镜像 tag，源码随之固定，再 `task rebuild`。
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
- `__manifest__.py` 必填：`name`、`summary`、`description`（三者写**英文源文本**，中文译文按 4.8 写进 `i18n/zh_CN.po`，否则中文环境「应用」列表显示英文）、`category`、`author`、`depends`、`installable: True`、`license`。静态资源走 `assets`（`web.assets_backend`），不走 `data`。
- `depends` 最小化：能用 `product` 就不要依赖 `sale`；不要为了方便依赖 `website`。
- **模块间可选集成必须解耦**：自研模块之间默认**不互相写进 `depends`**（确实需要对方的数据结构才算硬依赖）；
  跨模块取数据一律**运行期软探测** —— 读字段前判 `_fields`，取模型用 `env.get()`（未注册返回 `None`），
  调对方的方法用 `getattr` 探测；探测点必须收在**一处适配层**（方法 / 常量），缺对方时**降级**（少一层数据、
  主流程照常），禁止让整个操作报错。**降级分支要有用例**（用 `_fields` 判断 + `skipTest` 覆盖「装了」与
  「没装」两种配置）。示例与矩阵见根 `README.md` →「扩展解耦矩阵」。
- 新增模型必须配 `security/ir.model.access.csv`，权限最小化（普通用户可读写业务数据，管理员可配置）。
- 数据文件（视图/报表/权限）必须登记进 `data`，顺序：security → views → reports → data。
- 模块命名：`<业务域>_<功能点>`（如 `sale_order_no`、`product_reference`）；纯前端通用增强用 `web_` 技术层前缀（如 `web_image_paste`，符合 Odoo `web_*` 惯例）；**禁止**用 Odoo 官方模块名。**不加项目统一前缀**（`soho_` 等）——会偏离 Odoo 生态惯例，且改名需卸载重装生产库；自研模块归属用 `author: "edwinhuish"` 字段标识。命名约定完整版见 `DOCS_TEMPLATE.md`。

## 4. 国际化（i18n）规范

### 4.1 基本约定

- **源语言固定英文（`en_US`）**：Python / XML / JS / QWeb 模板里所有用户可见文本一律写英文，中文不写回源码；**不提供 `en_US.po`**（源语言即英文，Odoo 直接用源码文本）。
- **译文目录**：简体中文 `i18n/zh_CN.po`；新增语言按 `<lang>.po` 追加（如 `zh_TW.po`）。`i18n/` **无需登记进 `data`**，Odoo 安装 / 升级模块时自动扫描导入。
- **默认英文**：未安装中文语言的库一律显示英文；安装「简体中文 (zh_CN)」并切换后显示中文。
- **代码注释保持中文**：注释不参与翻译（XML 注释属于 `SKIPPED_ELEMENT_TYPES`），不要为 i18n 把注释改英文。
- **manifest 也要译**：`name` / `summary` / `description` **源文本写英文**，中文译文写在本模块的 `i18n/zh_CN.po` 里（键指向 `base.module_<module>`），否则中文环境「应用（Apps）」列表里模块名与描述永远是英文。详见 **4.8 应用列表元数据翻译规范**。
  > 历史更正：本节曾写「自研模块 po 里写 `model:ir.module.module,*:base.module_<module>` 匹配不到、无效果」，**该说法有误**。已对照 `odoo/tools/translate.py` 核实：po 导入按 `#:` 引用里的 xmlid 定位记录，与 po 文件属于哪个模块无关（`TranslationImporter._load` 的 `xmlids` 过滤在 `_load_module_terms` 里未启用）；官方的导出向导不会把这些条目导到自研模块的 po 里，但**手写的条目导入生效**。

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
| 应用列表模块名 | manifest `name` | `model:ir.module.module,shortdesc:base.module_<module>` |
| 应用列表摘要 | manifest `summary` | `model:ir.module.module,summary:base.module_<module>` |
| 应用详情描述 | manifest `description` | `model:ir.module.module,description:base.module_<module>` |
| 应用列表分类 | manifest `category` | `model:ir.module.category,name:base.module_category_<路径小写下划线>` |

> `<model>` 里的点换成下划线（如 `product.reference.code` → `product_reference_code`）；`<field>` 前是双下划线。
> 最后 4 行的 xmlid 前缀是 **`base.`**（记录归属 `base` 模块），但条目照样写在自研模块的 `i18n/zh_CN.po` 里，规范与坑点见 4.8。

### 4.3 已核实的 Odoo 19 抽取事实（对照 `odoo/tools/translate.py`）

- 术语一律 **`_push()` 后 `.strip()`**，但**内部的换行与缩进会保留** → 可译文本必须写成**单行**，否则 po 里的 `msgid` 会带上换行缩进，极易写错。
- 视图 `arch_db` 是 `translate=xml_translate`，`ir.actions.act_window.help` 也是 HTML 术语翻译 → 都是**按术语**存，不是整段 arch；`translate_xml_node` 用 `content.strip()` 取术语，属性用 `val.strip()`。
- 视图 arch 里能被抽取的属性见 `TRANSLATED_ATTRS`（`string` / `help` / `placeholder` / `title` / `alt` / `label` / `confirm` …）；OWL 模板里能被抽取的见 `OWL_TRANSLATED_ATTRS`（`alt` / `aria-label` / `label` / `placeholder` / `title` / `data-tooltip` …）。**`t-att-*`（动态属性）不会被翻译**。
- QWeb 模板中**每个文本节点、每个属性各自独立成术语** → 一句话里夹了子元素（`<kbd>Ctrl</kbd>+<kbd>V</kbd>`、`<t t-esc>`）就会被切碎，无法整体翻译。
- JS `_t` 由转译器自动注入模块名作上下文，不同模块的同名词条互不干扰；`.po` 里加 `#. odoo-javascript` / `#. odoo-python` 注释是与官方导出格式对齐，不影响导入。
- 不要在 `.po` 里写**重复的 `msgid`**：同一 `msgid` 只能有一条，多个来源合并到一条的多个 `#:` 引用上，否则 po 解析报错。
- **`code:` 译文在运行时按注释标记放行**：Web 端 JS / OWL 模板的译文由 `web/controllers/utils.py::_local_web_translations()` 读模块 po 时按 `#. odoo-javascript` 过滤，Python `_()` 由 `CodeTranslations._load_python_translations()` 按 `#. odoo-python` 过滤；缺标记的条目**永远不下发且不报错**（界面一直英文）。`task check` 对缺失给警告、`--strict` 算失败；另注意 `_t()` 不能在模块加载期调用（`TranslatedString` 会把「译文未就绪」固化成 lazy 后永久抛错）。
- **`translate=True`（非 callable）是「整值翻译」**（po 里的 `model:` 类型）：整个字段值就是一个翻译单元，`msgid` **允许多行**（如 `ir.module.module.description`），这是「可译文本必须单行」的唯一例外——因为它不是术语抽取。
- **整值翻译的目标记录只由 `#:` 引用里的 xmlid 决定**：`PoFileReader` 解析 `#: (model|model_terms):<model>,<field>:<module>.<xmlid>` 时用引用里的 `<module>` 定位，与条目的 `#. module:` 注释、与 po 文件属于哪个模块**都无关**；`_load_module_terms` 调用时不传 `xmlids`，所以没有「只能翻译本模块记录」的限制。
- **整值翻译导入时不比对 `msgid`**：`_load` 只要求 `msgid` 非空，随后按 xmlid 整体覆盖 `msgstr` → `msgid` 写错**不会报错**，但会与源文本长期失同步，只能靠自校验（4.6）保证一致。
- **每个条目必须有 `#. module: xxx` 作为第一行 `#.` 注释**：`PoFileReader.__iter__` 用 `re.match(r"(module[s]?): (\w+)", entry.comment)` 后直接 `.groups()`，缺这行会 `AttributeError`，**整份 po 导入失败**；其他说明要写在这行之后，或写成 `#` 译者注释。

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
| 改了 manifest 的 `name` / `summary` / `description`，没同步 po | 中文「应用」列表显示英文，或译文与源文本失同步（不报错，很难发现） | 同步 4.8 的三条键，并跑 4.6 的一致性校验 |
| 应用列表元数据的引用写成 `<module>.module_<module>` | xmlid 找不到记录，**静默不生效** | 前缀必须是 `base.`（记录归属 `base`） |
| 条目缺少 `#. module: xxx` 首行注释 | `PoFileReader` 抛 `AttributeError`，整份 po 不导入 | 每条都补 `#. module: <module>`（元数据条目写 `base`） |

### 4.5 执行 SOP（下次做 i18n 直接照此顺序）

1. **盘点**：`grep -rnP '[\x{4e00}-\x{9fff}]' --include=*.py --include=*.xml --include=*.js <module>`，剔除注释后即为待改清单；同时搜 `_t(`、`_(` 看已有入口。
2. **改源文本**：按 4.2 表逐处改英文；占位符统一 `%(name)s`。
3. **修模板**：把拼接句、夹子元素的句子改成单行或拆到 JS getter。
4. **写 `.po`**：按 4.2 表的键名写 `msgid`（英文源文本，一字不差）/ `msgstr`（中文），每条带 `#. module: <module>` + `#:` 引用。
5. **补应用列表元数据**：按 4.8 写 `shortdesc` / `summary` / `description`（+ 自定义分类）四类条目——**新模块必做，改 manifest 文案时必同步**。
6. **自校验**（无 Odoo 环境也能跑，见 4.6）。
7. **提版本 + 同步文档**：manifest（版本 + 英文 name/summary/description）、模块 `CHANGELOG.md` / `README.md` / `AGENTS.md`、根 `README.md` / `AGENTS.md` / `TODO.md`。
8. **交付**：给出「待验证清单」——升级命令、英文与中文各验一遍、强刷浏览器、回滚方式。

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

# 2) 应用列表元数据一致性检查（msgid 必须与 manifest 源文本逐字符一致；缺条目要补）
import ast, textwrap
KEYS = {"shortdesc": "name", "summary": "summary", "description": "description"}
for f in sorted(glob.glob("*/i18n/zh_CN.po")):
    module = f.split("/")[0]
    manifest = ast.literal_eval(open(f"{module}/__manifest__.py", encoding="utf-8").read())
    blocks = open(f, encoding="utf-8").read().split("\n\n")
    found = set()
    for b in blocks:
        m = re.search(r"^#: model:ir\.module\.module,(\w+):base\.module_(\w+)$", b, re.M)
        if not m:
            continue
        key, target = m.groups()
        assert target == module, f"{f}: 引用指向了别的模块 {target}"
        found.add(key)
        raw = re.search(r'^msgid ((?:"(?:[^"\\]|\\.)*"\s*)+)', b, re.M).group(1)
        got = re.sub(r"\\(.)", lambda x: {"n": "\n", "t": "\t"}.get(x.group(1), x.group(1)),
                     "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', raw)))
        want = manifest[KEYS[key]]
        want = textwrap.dedent(want) if key == "description" else want
        assert got == want, f"{f}: {key} 的 msgid 与 manifest 不一致"
    assert not (set(KEYS) - found), f"{f}: 缺少应用列表元数据条目 {sorted(set(KEYS) - found)}"
    print(f, "apps metadata ok")

# 3) 残留中文界面文本检查（命中应只剩下注释）
# grep -rnP '[\x{4e00}-\x{9fff}]' --include="*.py" --include="*.xml" --include="*.js" --include="*.csv" .

# 4) XML / JS 语法
# python3 -c "import glob,xml.dom.minidom;[xml.dom.minidom.parse(f) for f in glob.glob('*/**/*.xml',recursive=True)]"
# for f in <module>/static/src/js/*.js; do cp $f /tmp/chk.mjs && node --check /tmp/chk.mjs; done
```

### 4.7 验证与运维注意

- 前端术语（JS `_t` / QWeb 模板）由前端缓存，**`-u` 升级后必须强刷浏览器**才看得到新译文；后端字段标签 / help / 报错刷新页面即可。
- **Odoo 19 没有「应用术语 / Translated Terms」菜单**（`ir.translation` 表与「应用术语」UI 自 17 起废弃，改为 jsonb 字段内嵌翻译 `{en_US: ..., zh_CN: ...}`）。改单个翻译条目没有现成 UI，只能在「设置 → 翻译 → 导入翻译」用 po 文件、或 odoo shell / SQL。
- 源文本改英文后，旧 `msgid` 对应的 jsonb 里的 `zh_CN` key 不会被自动清理（成为孤儿项，不影响显示，但占空间），需要时可按字段用 SQL 删 key。
- 只做 i18n 的改动**不需要迁移脚本**（不涉及字段与数据结构）；但仍要 `-u` 升级，否则新译文与新的字段标签不会写入库。
- **改「已有译文」的 `msgstr` 时，`-u` 不可信**（通用规则，不只是应用列表元数据）：po 导入只**补齐缺失语种**，
  不覆盖库里已有的 `zh_CN` —— 应用列表元数据（`ir_module_module.*`，`noupdate=True`）如此，
  **视图术语 `model_terms:ir.ui.view,arch_db` 同样如此**（`product_image` `19.0.2.6.5` 实测：改了列标题译文，
  `-u` 后界面仍是旧词，且不报错）。处置二选一：① 跑 `task i18n -- zh_CN <模块>`
  （等价 `TranslationImporter(...).save(force_overwrite=True)`）；② 写一条迁移，定向用
  `view.update_field_translations("arch_db", {"zh_CN": {...}})` 刷新（幂等、未装 zh_CN 跳过）。
  换言之「`-u` 就能生效」这个直觉**只在新增译文时成立**。

### 4.8 应用列表元数据（模块名 / 摘要 / 描述 / 分类）翻译规范

**目标**：中文环境「应用（Apps）」列表里，自研模块的卡片标题、摘要、详情描述、左侧分类都显示中文。

**落地情况**：仓库**全部 9 个模块**均已按本节写入这 4 类条目（`task check` 的「应用列表元数据一致性」检查覆盖全仓库，缺任一
条会告警）。按验收状态分：

| 分组 | 模块 | 说明 |
|------|------|------|
| T-013 已验收（2026-09-09，目标环境） | `sale_order_no` `19.0.1.8.1`、`web_image_paste` `19.0.2.1.1`、`product_reference` `19.0.2.5.1`、`product_image` `19.0.2.6.3`、`product_packing`（现 `product_dimension`）`19.0.1.1.3`、`product_card_view` `19.0.2.0.1` | 6 项验收标准全部通过，中英文各验一遍 |
| 随 T-014 一并验收 | `sale_product_hover` `19.0.1.6.0` | 2026-09-17 归档时验收 |
| 条目已写入，**整包待目标环境验证** | `web_multi_tabs` `19.0.2.0.0`、`product_variant` `19.0.12.0.1` | 升级后需在中文「应用」列表里核对标题 / 摘要 / 描述 / 分类 ；`19.0.7.0.1` 修字段 widget 注册（此前产品表单打不开）；`19.0.7.0.2` 修模板变量名；`19.0.7.0.3` 修映射表排版；`19.0.7.0.4` 修「Add a line 即报必填缺失」；`19.0.7.0.5` 修 onchange 崩溃（映射状态改前端按需取）；`19.0.8.0.0` 映射计算搬到前端（编辑期零 RPC）；`19.0.8.0.1` 修「加属性面板无反应」；`19.0.8.0.2` 修「加属性无反应」；`19.0.8.0.3` 修「面板不刷新」；`19.0.8.0.4` 修「默认值当成用户选择」；`19.0.9.0.0` 组合唯一约束；`19.0.10.0.0` 映射表反向（组合为行、选变体）；`19.0.11.0.0` 所有属性一律穷举；`19.0.12.0.0` 前端穷举、后端按需；`19.0.12.0.1` 下拉禁用已占变体|
| 后续版本改过 `description` 需重验 | `product_dimension` `19.0.4.1.1`、`product_reference` `19.0.3.0.0`、`product_image` `19.0.2.6.5` | 改过 manifest 文案的版本已同步 `msgid`（`task check` 会卡住不一致），但库里旧的 `zh_CN` 不会自动更新，重验前先按第 9 条强制刷新一次 |

总览、示例与验收结果见根 [`README.md`](README.md) →「应用列表（Apps）中文化」。新模块首版必带，清单见
[`DOCS_TEMPLATE.md`](DOCS_TEMPLATE.md) →「新模块 i18n 必备清单」。

**每个模块必须有的 4 类条目**（写在**本模块** `i18n/zh_CN.po`，`msgid` 为 manifest 里的英文源文本）：

| 显示位置 | 键（`#:` 引用） | `msgid` 取值 |
|----------|-----------------|--------------|
| 应用卡片标题 / 模块名 | `model:ir.module.module,shortdesc:base.module_<module>` | manifest `name` |
| 应用卡片摘要 | `model:ir.module.module,summary:base.module_<module>` | manifest `summary` |
| 应用详情描述 | `model:ir.module.module,description:base.module_<module>` | `textwrap.dedent(manifest["description"])` |
| 左侧分类树 | `model:ir.module.category,name:base.module_category_<路径小写下划线>` | 分类段英文名 |

```po
#. module: base
#: model:ir.module.module,shortdesc:base.module_product_packing
msgid "Product Packing"
msgstr "产品装箱"

#. module: base
#: model:ir.module.module,description:base.module_product_packing
msgid ""
"\n"
"Product carton packing module for foreign trade SOHO scenarios.\n"
...
msgstr ""
"\n"
"外贸 SOHO 场景下的产品纸箱装箱模块。\n"
...
```

**必须遵守（每条都有对应的坑）**：

1. **xmlid 前缀是 `base.`**，不是模块名：模块记录由 `ir.module.module.create()` 写入 `ir.model.data`（`module='base'`、`name='module_<module>'`、`noupdate=True`），分类由 `odoo/modules/db.py:create_categories()` 写入（`base.module_category_<...>`）。写成 `<module>.module_<module>` 会静默失效。
2. **分类 xmlid 的算法**：`'module_category_' + '_'.join(段.lower())`，`&`→`and`、空格→`_`，且**逐级都建一条**。例如 `Inventory/Product` → `base.module_category_inventory`（官方已有译文，不要重复翻译）+ `base.module_category_inventory_product`（自定义段，**必须自己译**）。官方已有分类（`Sales`、`Productivity` 等）不重复翻译，避免与 `base` 的译文打架。
3. **`description` 的 `msgid` 必须等于 `textwrap.dedent(manifest["description"])`**（Odoo 存的就是这个值，见 `ir_module.get_values_from_terp`）：多行、缩进、结尾换行都要一致；这是「术语必须单行」规则的例外（整值翻译）。
4. **`msgstr` 是整段全量译文**，不能只译一部分——整值翻译会用 `msgstr` 覆盖整个字段值。
5. **每条都要 `#. module: base` 首行注释**（记录归属 `base`）：缺 `#. module:` 会让整份 po 导入崩溃（4.3）。
6. **不要产生重复 `msgid`**：模块名常与已有条目（动作名 / 字段标签）同字面，例如 `Product References`、`Product Images`、`Order Number`、`Product` → 把新引用**合并到已有条目**的 `#:` 列表里，不要新开一条。
7. **改 manifest 英文文案 = 必须同步这些 `msgid`**：导入不比对 `msgid`（4.3），写错不报错，只会长期失同步 → 靠 4.6 的一致性校验兜住。
8. **导出向导不会生成这些条目**：`TranslationModuleReader._export_translatable_records()` 按 `ir_model_data.module` 过滤，这些记录属于 `base`，所以「设置 → 翻译 → 导出」导本模块 po 时**不含**它们。**手写维护**，并且**不要用导出结果整体覆盖** `i18n/zh_CN.po`，否则这几条会被抹掉。
9. **改译文要强制刷新**：记录是 `noupdate=True`，`TranslationImporter.save()` 只在 `force_overwrite` 时才覆盖它们；`-u` 甚至 `-u --i18n-overwrite` 都只**补齐缺失语种**，不会更新库里已有的 `zh_CN` 值。首次升级正常生效；**后续修改译文**要二选一：
   - odoo shell：
     ```python
     from odoo.tools.translate import TranslationImporter
     imp = TranslationImporter(env.cr)
     imp.load_file('<addons-path>/<module>/i18n/zh_CN.po', 'zh_CN')
     imp.save(force_overwrite=True)
     env.cr.commit()
     ```
   - 或先清掉旧值再 `-u`：`UPDATE ir_module_module SET shortdesc = shortdesc - 'zh_CN', summary = summary - 'zh_CN', description = description - 'zh_CN' WHERE name = '<module>';`
10. **验证方式**：中文环境「应用」里搜模块技术名，看卡片标题 / 摘要 / 详情描述 / 左侧分类是否中文；切回英文应显示 manifest 原文。

## 5. Python 规范

- **禁止修改 Odoo 核心源码**；一律 `_inherit` 扩展，必须改行为时用 patch / 继承并注明原因。
- 创建/写入入口统一用 `@api.model_create_multi` 的 `create` 与 `write`，不要在旧式单个 create 上做逻辑。
- Odoo 19 显示名统一用 `_compute_display_name()`；`name_get()` / `name_search()` 已从核心移除，禁止再定义或依赖（详见下一节）。
- 字段定义要有 `string` 与 `help`（**英文源文本**，中文走 `i18n/zh_CN.po`，见第 4 节）；业务字段加 `index=True`（凡是要搜索的字段）；`copy=False` 需显式声明。
- 校验用 `@api.constrains` + `ValidationError`，错误信息必须是可直接给用户看的完整句子（英文源文本 + 中文译文），并带上出错的具体值。
- 搜索能力必须在数据库层实现：可 `store=True` 的计算字段配索引，或字段级 `search=` 方法，或 `('x2many', 'any', [...])` 域；禁止先 `search([])` 再在 Python 里过滤。
- 结构变更必须写 `migrations/<version>/pre-migration.py`（改名、改类型、数据回填），并在 CHANGELOG 说明影响。
- 编号 / 流水类字段：创建时一次性快照写入，后续不因主数据变化而重算；作废、取消、删除不回收已用号。

### 已核实的 Odoo 19 API 事实（对照镜像内 `/usr/lib/python3/dist-packages/odoo`，即 `odoo/odoo@19.0`）

- `name_get()` / `name_search()` 已从核心移除，只剩 `_compute_display_name()` 与 `_search_display_name(operator, value)`（后者返回 `Domain` 对象）。
- 名称搜索走 `_search_display_name()`，可在其中 OR/AND 进自定义字段；否定操作符（`not ilike` 等）必须取交集。
- `Domain` 从 `odoo.fields` 导入：`from odoo.fields import Command, Domain`；`Domain.OR/AND` 接受任意 domain 表达式。
- `_sql_constraints` 已废弃，改用模型属性：`_xxx_unique = models.Constraint("UNIQUE(field)", "提示")`、`models.Index(...)`、`models.UniqueIndex(...)`。
- `web_search_read(domain, specification, offset, limit, order, count_limit)` 定义在 `web` 模块的 `_inherit='base'` 上，所有模型可用。
- 视图继承：扩展祖先视图（extension）对其所有 primary 子视图生效，改列表要继承基础列表而非某个 primary 子视图。
- 改动前先核对目标结构：查 Odoo 源码一律在容器里（`docker exec odoo19 grep -rn … /usr/lib/python3/dist-packages/odoo/…`，或 `task bash` 进去看），**不要**克隆 `../odoo` / `/tmp/odoo`、也不要直连 GitHub。详见第 2 节「查阅 Odoo 源码」。

## 6. 前端规范

- JS 文件首行必须是 `/** @odoo-module **/`；用 `@web/core/utils/patch` 打补丁，不覆写整个组件。
- QWeb 用 `t-inherit` + `t-inherit-mode="extension"` 扩展原模板，不复制核心模板全文。
- 静态资源放 `static/src/{js,xml,scss}/`（如 `web_image_paste` 为此结构，迁移时保持一致）。
- 事件处理要判 `props.readonly`，只读态不得触发写操作。
- 复用原生上传 / 校验链路（如 `onFileUploaded`、`checkFileSize`），不重复实现。
- **改完 JS 必须跑一次「命名导入 vs 导出」自查**：整份重写一个模块时很容易漏掉某个
  `export`，而 `node --check` 只验语法、查不出「少了一个导出」，浏览器里表现为
  运行到那行才抛 `xxx is not a function`，排查代价很高（`sale_product_hover`
  `19.0.1.3.1` 就因此回归过）：

  ```python
  # 在仓库根目录执行：报出所有「import 了但目标文件没导出」的名字
  import re, pathlib
  EXPORT_RE = re.compile(r'^export\s+(?:async\s+)?(?:function|const|let|var|class)\s+(\w+)', re.M)
  EXPORT_LIST_RE = re.compile(r'^export\s*\{([^}]*)\}', re.M)
  IMPORT_RE = re.compile(r'import\s*\{([^}]*)\}\s*from\s*"(\.[^"]+)"', re.S)
  for js in sorted(pathlib.Path(".").glob("*/static/src/**/*.js")):
      for names, target in IMPORT_RE.findall(js.read_text(encoding="utf-8")):
          tpath = (js.parent / target).with_suffix(".js")
          if not tpath.exists():
              print(f"{js}: 目标文件不存在 {target}"); continue
          ttext = tpath.read_text(encoding="utf-8")
          have = set(EXPORT_RE.findall(ttext))
          for grp in EXPORT_LIST_RE.findall(ttext):
              have |= {n.strip().split(" as ")[-1].strip() for n in grp.split(",") if n.strip()}
          want = {n.strip().split(" as ")[0].strip() for n in names.split(",") if n.strip()}
          if want - have:
              print(f"{js} ← {target}: 未导出 {sorted(want - have)}")
  ```

  跨模块复用的 helper 还应在**加载期**做一次 `typeof !== "function"` 兜底自检
  （见 `sale_product_hover/static/src/js/product_hover_list_patch.js` 的 `hoverHelpers`），
  让不一致在页面加载时就以明确的 `console.error` 暴露。
- **不要往 `__manifest__.py` 的 `assets` 里新增文件**（除非确实需要并准备升级服务端）：
  assets 的文件清单来自 manifest，而**运行中的 Odoo 进程内存里是旧 manifest**——
  `?debug=assets` 下 Odoo 只按文件 mtime 重建 bundle 内容，**不会重新读取 manifest**。
  新增文件后浏览器会直接报
  `The following modules are needed by other modules but have not been defined, they may not be
  present in the correct asset bundle: ['@<module>/js/xxx']`，并且依赖它的模块一起加载失败。
  想加代码就写进**已登记的文件**里（只改内容时强刷浏览器即可）；确实要新增文件，
  必须 `-u <module>`（或重启进程）让 manifest 重新生效，并在交付说明里写明这一步。

## 7. 文档与变更规范

每次功能改动必须同步更新，缺一不可：

1. `__manifest__.py` 的 `version`（按第 3 节规则递增）与 `description`（涉及用户可见行为时）
2. `i18n/zh_CN.po`：新增 / 改动的用户可见文本译文；改了 manifest 的 `name` / `summary` / `description` 时同步 4.8 的应用列表元数据条目
3. 模块 `CHANGELOG.md`：变更 / 影响 / 文档同步三段式，注明日期；**修复 / 优化类版本**另加「优化目标」（变更之前）与「优化前后对比」（变更之后）两节，说明「为什么改、改前什么样」
4. 模块 `README.md`：用户可见功能、字段表、安装与使用步骤；顶部写「修订日期」，涉及验证的改动同步「验证清单」条目
5. 模块 `AGENTS.md`：**不可破坏的核心约束**清单（约束变化时更新）+ 文末「修订记录」表
6. 根目录 `TODO.md`：任务状态流转（见第 8 节）；已归档需求若有后续修订，在归档条目下补追溯行
7. 根目录 `README.md` 模块一览表（**版本与状态的总表，权威口径**）：模块版本与状态摘要保持一致
8. 根目录 `AGENTS.md` 第 9 节的模块速查表：只维护「版本 + 一句话技术要点 + 状态」，详细版本史的去处在根 `README.md`
9. （**可选 / 已不推荐**）阶段性总结：历史上曾用根目录 `STAGE_REPORT_*.md` 承载交接。
   现在改为写进当次需求的 `TODO.md` 归档条目、或各模块 `CHANGELOG.md` / `AGENTS.md`，
   **不要在仓库根新建阶段报告文件**；理由与替代方案见 [`docs/README.md`](docs/README.md) →「四、本次归档的决策记录」

> 三类模块文档（`README.md` / `CHANGELOG.md` / `AGENTS.md`）的统一骨架与约定见根目录 [`DOCS_TEMPLATE.md`](DOCS_TEMPLATE.md)，新模块按此创建，既有模块迭代时按此对齐。
> **文档全面貌见 [`docs/README.md`](docs/README.md)**（含 `docs/archive/` 归档区）。

## 8. TODO.md 使用规则

- `TODO.md` 是**待处理需求**的唯一入口，仅记录待办 / 进行中 / 搁置项，不要在对话里另立清单。
- 新需求追加到「待办池」末尾并取下一个 ID；开工移入「进行中」并补齐验收标准；验收通过后整条移出本文件，完成信息（日期 / 落地版本 / 验收记录 / 异常与维护）沉淀到对应模块的 `CHANGELOG.md` 与 `README.md` / `AGENTS.md`，根 `README.md` 模块一览表更新状态；不做则移入「搁置」并写原因。
- 动工前先读该条目的「设计约束」，有疑问在条目下以备注形式记录，不要自行放宽约束。
- **结构化校验**：`task check` 会一并检查 TODO.md —— 条目格式（`- [ ] T-0xx ｜ 模块 ｜ Pn ｜ 描述`）、ID 全局唯一（含已归档）、
  待办池 ID 递增、模块列对应仓库里真实存在的模块目录、条目里的文档链接存在、`检测：` 条件语法合法；
  「进行中」条目缺「验收标准」只是警告。
- **状态看板**：`task todo` 跑每条需求自带的 `检测：` 条件（追加规则 8），输出「可能已实现 / 未实现」。
  它是**特征探测**（必要条件），不是验收结论；条目归档时 `检测：` 行跟着条目一起移走，脚本里不维护清单。

## 9. 已有模块速查

> 自研模块通过 `__manifest__.py` 的 `author: "edwinhuish"` 字段统一标识归属，应用列表可按 author 筛选；模块命名遵循 `<业务域>_<功能点>` 约定（见 `DOCS_TEMPLATE.md`），不加项目前缀。
>
> **本表只做技术速查**：`作用` 列写「技术定位与关键约束」，`状态` 列写「当前是否待目标环境验证」。
> 版本 / 完整功能描述 / 交付历史以根 [`README.md`](README.md) 的模块一览表为准（**那里是唯一权威口径**），
> 本表不重复版本演进细节，避免两处漂移 —— 2026-09-24 复盘时发现本节有 4 处版本号与实际 manifest 不符，根因就是重复维护。

| 模块 | 版本 | 作用 | 状态 |
|------|------|------|------|
| `sale_order_no` | 19.0.1.8.1 | 销售订单 / 报价单自定义编号（`order_no`，客户编码 + 两位年份 + 年度流水），含客户编码格式校验、报表替换、PDF 文件名定制、门户预览定制、批量补号 | 已交付，目标环境已验证（T-001；T-006 i18n 随 19.0.1.8.0 验收通过，2026-09-07）；`19.0.1.8.1`（2026-09-09，T-013）补应用列表（Apps）中文元数据（模块名 / 摘要 / 描述），目标环境已验收通过 |
| `web_image_paste` | 19.0.2.1.1 | 后台图片字段粘贴 / 拖拽上传（patch `ImageField` + `FileUploader`，复用原生上传链路，即时预览 + 进度条；原名 `image_uploader`） | 已交付，目标环境已验证（T-003；T-006 i18n 随 19.0.2.1.0 验收通过，2026-09-07）；`19.0.2.1.1`（2026-09-09，T-013）补应用列表（Apps）中文元数据（模块名 / 摘要 / 描述 / 分类「图片」），目标环境已验收通过 |
| `product_reference` | 19.0.3.0.0 | 产品多参考号 + 可搜索（One2many 明细 / 冗余 trigram 索引 / 命中提示）+ **产品级编号 `base_reference`**（`19.0.2.6.0` 新增字段、`19.0.3.0.0` 定最终形态：**叠加进原生 `default_code` 的 compute**（`base_reference` 优先）—— 产品表单 / 列表 / `display_name` / 搜索 / 其它模块读原生字段都能拿到产品编号；inverse 按变体数分流（单变体两处同值、多变体只写 `base_reference`）；产品级与变体级参考号**都可见**，不再按变体数隐藏；存量由 `migrations/19.0.3.0.0/` 回填）；`19.0.2.0.0` 由 `product_model` 改名（模型 `product.model.code` → `product.reference.code`，含幂等迁移脚本与升级前置 SQL）；`19.0.2.2.0` 参考号页顶部直接展示 Odoo 原生 `default_code`（Reference）供统一编辑，不再在参考号表中存储镜像行；`19.0.3.0.0`（T-035）产品级编号叠加进原生 `default_code` + 契约测试 6 项（`tests/test_base_reference.py`） | 已交付，目标环境已验证（T-002 / T-007 / T-008，19.0.2.2.0，2026-09-07：`19.0.2.0.0` 改名迁移与 `19.0.2.2.0` 前端展示均已验收通过）；`19.0.2.5.0`（T-011，2026-09-08）参考号界面改造 + 多变体不共用已验收通过；`19.0.2.5.1`（2026-09-09，T-013）补应用列表（Apps）中文元数据（模块名 / 摘要 / 描述 / 分类「产品」），目标环境已验收通过；`19.0.2.5.3`（T-027）删掉权限文件里硬编码的可选模块用户组；`19.0.3.0.0`（T-035 / T-037 定稿）是产品级编号的最终形态，**待目标环境验证** |
| `product_image` | 19.0.2.6.5 | 产品多图（产品 / 产品变体双入口独立图集（19.0.2.6.0 起）+ 原生主图独立 + 图库补充图 / 主图无删除入口/ 首张上传即主图 / 主图 2 倍 / 悬浮局部放大（540窗口+1080图片平移·左侧不足转下方/缩小·选框按比例·留白区白色）/ 点击预览（多图切换+右侧缩略图·关闭按钮暗色半透明·底部条默认透明悬浮淡入·图片初始避开上下条放大可覆盖全屏·任意大小可拖拽grab/grabbing·GPU 1:1顺滑·切图保留状态·无滚动条·缩略图未选中无边框）/ 右侧竖排缩略图（蓝色选中边框·编辑态无删除按钮·滚动不越界且与主图区顶底贴边·仅切换不写库）/ 图片管理弹窗（「+」打开·顶层overlay：上半大图（仅预览、无删除按钮）+平铺缩略图（每张含主图右上角×：删图库删记录·删主图自动提升图库首张·点缩略图只切弹窗大图·缩略图可拖排序(含主图·首位即主图·避让动画)·删除均先确认(含缩略图·主图提示提升)·批量删除(勾选模式+含缩略图清单确认)·大图固定尺寸缩略图占满余量超高滚动·选中主图名称行留空）·下半dropzone 点击/拖放/Ctrl+V（上传中缩略图+动画·粘贴后不自动关闭·上传不改页面大图）·header 最右侧正方形×关闭按钮 hover 变红）/ 继承 image.mixin 复用多尺寸；原名 `product_multi_image`） | 已交付，目标环境已验证（T-005，19.0.2.4.2，含 19.0.2.2.10~4.2：拖动排序（含主图·首位即主图）/ 删除确认 / 批量删除 / 选中主图名称行留空 / 确认框按钮顺序 / 关闭按钮贴边）；坑点与风险提示见模块 `AGENTS.md` →「会话修改总结与风险提示」/「开发复盘与关键经验（T-005）」；T-010 变体多图（19.0.2.6.1）已完成，目标环境验收通过（2026-09-08，含图库图片占位回归修复与复验；验收记录见模块 `CHANGELOG.md` →「交付记录（T-010）」）；19.0.2.6.2（2026-09-08）修复变体上传报「双归属」Validation Error（变体 action context `default_product_tmpl_id` 污染图库子行创建，见模块 `CHANGELOG.md` → `[19.0.2.6.2]`），待目标环境复验；`19.0.2.6.3`（2026-09-09，T-013）补应用列表（Apps）中文元数据（模块名 / 摘要 / 描述 / 分类「产品」），目标环境已验收通过；`19.0.2.6.4`（T-027）删掉权限文件里硬编码的可选模块用户组；`19.0.2.6.5`（T-038，2026-09-23）产品列表「Images」列由绑图库计数改绑原生 `image_128`（主图缩略）+ `image` widget，含定向刷新视图术语的迁移，**待目标环境界面复验** |
| `product_dimension` | 19.0.4.1.1 | 为产品 Logistics 组增加物流尺寸（尺寸单位 cm / m + 长宽高，`Dimension Unit` 默认厘米）；尺寸存放在**变体**上（模板侧是单变体桥接，与原生 `volume` / `weight` 同构），每条变体各持一份尺寸与 Volume；`19.0.2.0.1`（T-021）由 `product_packing` 改名而来，移除纸箱与包装字段，并带安装前钩子把旧模板尺寸数据搬到变体 | `product_packing` 时期（T-009，2026-09-08 与 T-013，2026-09-09）目标环境已验证；`19.0.2.0.1`（T-021，2026-09-22）改名 + 尺寸下沉 + 移除纸箱：本地已验证（**17 项**测试含三表单挂载、可见性门控、前后端职责划分与前端规则 node 实测、旧数据搬运实测、干净库合成 arch 实测、前端资源进包实测），**待目标环境验证**；`19.0.4.1.1`（2026-09-23）修新建产品时产品表单的 `Dimension Unit` 是空的（镜像字段补自带 `default`，见模块 `AGENTS.md` → L2 P9），本地已验证、界面待目标环境复验；坑点见模块 `AGENTS.md` → L1 / L2 |
| `product_card_view` | 19.0.2.1.4 | 产品列表卡片视图（瀑布流）：注册新 view type `card`，为官方 Products 视图切换器新增 Card 按钮（库存 / 销售 / 采购入口）；卡片多图轮播（模板 / 变体两层图源不叠加）+ title / reference / on hand + 多变体按钮切换；**编号随选择切换**（`19.0.2.1.4` 起：未选变体=产品编号，选中变体=该变体编号，变体无编号回退产品编号；已选组合行只显示属性组合）；编号只读原生 `product.template.default_code`（与 `product_reference` **零耦合**，代码里不出现任何自研模块字段）；后端每页一次批量 `/product_card/payload`；`product_image` / `sale` / `purchase` 为可选依赖（运行时判断，4 项 payload 用例钉住） | 已交付（T-012，2026-09-09）：Card 入口已确认，其余项待复验；依赖 Odoo 内部 `session.view_info` 的 JS patch，Odoo 升级需回归（见模块 `AGENTS.md` → L2 P2）；`19.0.2.0.7`（2026-09-22）修复切换 filter / group by 后卡片空白、过宽、无间隙（取数覆盖分组 + payload 填充时机 + 分组布局，见模块 `AGENTS.md` → L2 P6）；`19.0.2.0.1`（2026-09-09，T-013）补应用列表（Apps）中文元数据（模块名 / 摘要 / 描述 / 分类「产品」），目标环境已验收通过；`19.0.2.0.6` 起 Card 注入改为读取时计算（修全新安装漏注入），`19.0.2.0.7` 修分组 / 筛选切换后空白（Card 其余项仍待复验）；`19.0.2.1.0`（2026-09-22，T-033）卡片编号优先读产品母型号 `base_reference`（`product_reference` 可选、按字段存在性软适配），并修掉应用详情描述的 RST 列表渲染；`19.0.2.1.1` 收紧为仅**多变体**产品读母型号（单变体产品的编号真身在变体上）：本地已验证（升级无告警 / 描述渲染 8 个列表项 / 元数据一致性校验通过），卡片显示待目标环境验证 |
| `product_variant` | 19.0.12.0.1 | 给产品追加属性 / 取值而不丢变体，**入口是保存拦截而不是按钮**：前端 patch `FormController.onWillSaveRecord`、保存前调预览 RPC，服务端 `write()` 用「只写配置、不碰变体」的试写分析判定三种结局（不影响变体→原生保存；会新增变体→还有未映射的变体就拦住、都映射好了先安全转换再落库；会丢变体→拒绝）；归属在「属性与变体」页下方的**映射表**里逐条指定（每行一条既有变体，缺取值的轴给下拉），状态存在 `model.variantMapping` 上（切页签不丢）；既有 `product.product` 记录 id 不变，库存与单据引用不受影响；转换落成台账 + 变体谱系 + 变体上可搜索的「所属转换 / 来源变体」。仅依赖 `product`；**与 `product_reference` 零耦合**（`19.0.5.3.0` 起：不读不写对方任何字段，转换只做「按归属复用既有变体」，变体上的值与参考号行原样保留）；**支持「按需生成变体」（`dynamic`）的属性**（`19.0.6.0.0` / T-039：改属性只展开「立即」轴、按需轴按既有变体现带取值钉住、缺失组合自己用 `_create_product_variant()` 补、带按需属性的产品不做价格分离；**建产品**时带按需属性仍拦住，因为原生会建出「有属性、没变体」的产品） | 已交付（T-015，2026-09-21；`19.0.3.0.0` 起改为保存拦截并移除按钮 / 向导；`19.0.7.0.0` 起技术名由 `product_variant_conversion` 改为 `product_variant`，**已装库必须走「原地改名」三条 SQL**，卸载重装会清空台账 / 谱系）：本地开发库 `-i` / `-u` 无报错；`19.0.5.1.0` ~ `19.0.5.2.1` 曾把单变体编号「上移」为产品母型号、把共享参考号「交接」给被保留的变体，已按「模块间彻底解耦」的要求在 `19.0.5.3.0` **全部移除**（变体上的值与参考号一律原样保留）；`19.0.5.3.1`（按需属性的建产品拦截 + 点名文案）、`19.0.5.3.2`（修「一次加两个属性」时 chatter 抛 `Expected singleton`）、`19.0.6.0.0`（T-039 支持按需生成属性）、`19.0.6.1.0`（T-040 弹窗互换）为当日交付，本地四组配置各 **55 项**用例 0 failed / 0 error（目标环境待验证）；`i18n/zh_CN.po` 与源码逐字符一致；**待目标环境验证**（映射表交互与保存拦截、按需属性产品的转换、改名升级、中英文界面，清单见模块 `README.md` →「验证清单」）；Odoo 变体生成机制、保存前钩子与递归陷阱、i18n 与字段命名坑见模块 `AGENTS.md` → L2（P1~P5；P5 是场景覆盖矩阵、价格 / 库存同步规则与缺口清单） ；`19.0.7.0.1`（2026-09-24）修字段 widget 注册方式（裸类 → 描述对象）：此前打开产品表单 /「属性与变体」页会崩在 `Field.template` 的 `undefined.name`；`19.0.7.0.2`（2026-09-24）修映射表模板变量名（`state.` → `store.`），映射表首帧渲染不再崩；`19.0.7.0.3`（2026-09-24）修映射表排版（字段外层 `.o_field_widget` 是 inline-block，加了一层块级 div 包住），不再跑到属性行右侧被裁；`19.0.7.0.4`（2026-09-24）修「点 Add a line 就报必填缺失」（预览 RPC 清洗半成品属性行 + 兜底）；`19.0.7.0.5`（2026-09-24）把映射状态从 compute 字段改成前端按需 RPC（compute 会在 onchange 里序列化未保存行的 `NewId` 而崩）；`19.0.8.0.0`（2026-09-24）**映射计算搬到前端**（挂载取一次快照，编辑期零 RPC，保存才回服务端）；`19.0.8.0.1`（2026-09-24）修「加属性面板无反应」（改用 `record.getChanges()` 合并快照基线读编辑态）；`19.0.8.0.2`（2026-09-24）修「单变体产品加属性无反应」（新建行要保留 Odoo 的虚拟 id，否则后续「选属性 / 勾取值」命令落空）；`19.0.8.0.3`（2026-09-24）修「面板不刷新」（子表编辑改为订阅 o2m 组件 `onPatched`）；`19.0.8.0.4`（2026-09-24）修「自动补的默认值被当成用户选择、加第二个取值后回不到未映射」；`19.0.9.0.0`（2026-09-24）**一个组合只能被一条变体占用**（已被占住的候选值在下拉里禁用，真重复时标未映射）；`19.0.10.0.0`（2026-09-24）**映射表反向：组合为行、为每个组合选变体**（Variant 下拉可留空/清空，交换位置只需两下；未认领的既有变体拦住保存）；`19.0.11.0.0`（2026-09-24）**取消 T-039 特例：所有属性一律穷举、属性列只读**（带「按需生成」属性的产品改属性时会把它的全部取值组合都建出来）；`19.0.12.0.0`（2026-09-24）**前端穷举展示、后端按需预建**（按需属性没被既有变体认领的取值不预建，前端灰显 + 提示）；`19.0.12.0.1`（2026-09-24）Variant 下拉禁掉已被别行占用的变体（换位置要先让出来）|
| `web_multi_tabs` | 19.0.2.0.0 | 后台内部多标签页：每次打开视图生成一个可切换 / 可关闭的标签，溢出折叠为下拉菜单，URL 归一化 + 首页重定向合并避免重复标签；PWA / Window Controls Overlay 适配（标签栏按 CSS `env(titlebar-area-*)` 铺满标题栏）；`WebManifestMultiTabs` 控制器继承注入 `display_override` | 2026-09-09 在 `19.0.1.0.0` 基础上升级优化：补 `/** @odoo-module **/` 与 `static/src/{js,scss}` 路径、控制器继承替 monkey-patch、源语言改英文 + `i18n/zh_CN.po` 中英双语、修调试开关与 ResizeObserver 重绑；功能与交互不变，待目标环境验证；本模块文档见 `web_multi_tabs/AGENTS.md` |
| `sale_product_hover` | 19.0.1.6.0 | 报价单 / 销售订单订单行悬停（触屏长按）展示**产品详情**浮层（图片 / 名称 / 型号 / 规格 / 描述 / 可用库存，**不含任何价格**：无订单行的数量与单价，也无产品售价）：patch `ListRenderer` + popover 服务，document 捕获阶段事件委托、以行 `data-id` 反查归属（**按字符串比较**）、浮层跟随鼠标并屏蔽行内原生 tooltip；已保存行走自研接口（`formatLang` 装配），**新增（未保存）的行按 `product_id` 用标准 ORM 直接查产品**（不依赖服务端升级）；每页一次批量 payload 与浏览器缓存，仅 `sale.order.line` 生效，不新增模型 / 字段 / 权限 / 视图 | **已完成（T-014，2026-09-17 归档）**；`19.0.1.0.1` / `19.0.1.0.2` 曾尝试修复悬停不触发，`19.0.1.1.0` 重做触发链路、补齐规格与价格、新增触屏长按与响应式，`19.0.1.1.1` 修掉真正根因（`data-id` 是字符串却被 `Number()` 化），`19.0.1.2.0` 浮层跟随鼠标 + 屏蔽行内原生 tooltip，`19.0.1.3.0` 支持新增行预览（`Record.isInEdition` 对 `!resId` 恒为真导致新行被编辑态守卫挡掉），`19.0.1.3.1` 修复缺数据行永久失效 + 版本自证，`19.0.1.3.2` 修复缓存模块漏导出 `getLineHoverPayload` 的回归，`19.0.1.3.3` 加服务端版本探测与启动自检，`19.0.1.4.0` 新行改为前端直接查产品，`19.0.1.4.1` 把该逻辑并入已有文件（**新增 assets 文件必须 `-u`**，否则报 modules 未定义），`19.0.1.5.0` 移除浮层里的订单数量与本单单价（两条取数路径同步收窄），`19.0.1.5.1` 后端版本改为自动读 `__manifest__.py`（版本只剩 manifest + JS 两处：后端 `get_manifest()` 取，JS 保留一枚资源邮戳），`19.0.1.6.0` 再移除产品售价（浮层不含任何价格，前端不再需要 `formatMonetary` 与公司币种，明细表在库存为空时整块不渲染）；排障链路见模块 `README.md`，技术约束与踩坑见模块 `AGENTS.md` |

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
