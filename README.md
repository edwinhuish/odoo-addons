# Odoo 19 外贸 SOHO 进销存自研模块

以 Odoo 19 社区版为基础，面向外贸 SOHO（一人 / 小团队）场景的进销存扩展模块集合。

核心链路：**产品（参考号 / 图片）→ 报价单 → 销售订单 → 采购 → 出入库 → 收付款 / 发票**

设计取向：单据录入步骤尽量少、对外单据编号符合外贸习惯、界面支持中英双语（**源语言英文，默认英文，中文由 `i18n/zh_CN.po` 提供**）。

---

## 目录结构

仓库根目录**即 Odoo 的 `addons_path`**，一个模块一个一级目录，根目录只放文档。

```text
odoo-addons/           # 本目录即 addons_path
|-- README.md          # 本文件：项目说明与上手指南
|-- AGENTS.md          # AI 助手 / 开发者的行为规范与关键约束
|-- TODO.md            # 需求唯一入口，任务在这里流转
|-- sale_order_no/     # 订单编号（已迁入）
`-- .../               # 后续模块按同一结构新增
```

单个模块的结构：

```text
<module>/
|-- __init__.py            # from . import models
|-- __manifest__.py
|-- models/
|-- views/
|-- security/              # 有独立模型时必须有 ir.model.access.csv
|-- static/src/{js,xml,scss}/
|-- migrations/<version>/  # 仅在字段/数据需要迁移时
|-- README.md  CHANGELOG.md  AGENTS.md
```

---

## 模块一览

> 自研模块通过 `__manifest__.py` 的 `author: "edwinhuish"` 字段统一标识归属；命名遵循 `<业务域>_<功能点>`（见 [`DOCS_TEMPLATE.md`](DOCS_TEMPLATE.md)），不加项目前缀。

| 模块 | 版本 | 作用 | 状态 |
|------|------|------|------|
| [`sale_order_no`](sale_order_no/README.md) | 19.0.1.8.1 | 销售订单 / 报价单自定义编号：客户编码 + 两位年份 + 年度流水（如 `DZ2602`）；含客户编码格式校验、报表替换、PDF 文件名定制、门户预览定制、批量补号 | 已交付，目标环境已验证（T-006，19.0.1.8.0，i18n：源语言英文 + `i18n/zh_CN.po` 中英双语）；`19.0.1.8.1`（T-013，2026-09-09）补应用列表（Apps）中文名 / 摘要 / 描述译文，目标环境已验收通过 |
| [`web_image_paste`](web_image_paste/README.md) | 19.0.2.1.1 | 后台图片字段支持剪贴板 `Ctrl+V` / `Cmd+V` 粘贴与拖拽上传，即时预览 + 进度条，一次多图，超大图报错（原名 `image_uploader`） | 已交付，目标环境已验证（T-006，19.0.2.1.0，i18n：源语言英文 + `i18n/zh_CN.po` 中英双语）；`19.0.2.1.1`（T-013，2026-09-09）补应用列表（Apps）中文名 / 摘要 / 描述 + 分类「图片」译文，目标环境已验收通过 |
| [`web_multi_tabs`](web_multi_tabs/README.md) | 19.0.2.0.0 | 后台内部多标签页：每次打开视图生成一个可切换 / 可关闭的标签，标签过多折叠为下拉菜单，标签名跟随当前视图；适配 PWA / Window Controls Overlay（标签栏接管标题栏区域） | 已交付（2026-09-09，在 `19.0.1.0.0` 基础上升级优化：静态资源目录重构、控制器改标准继承、源语言改英文 + `i18n/zh_CN.po` 中英双语、修调试开关与 ResizeObserver 重绑），待目标环境验证 |
| [`product_reference`](product_reference/README.md) | 19.0.2.5.1 | 产品多参考号 + 可在列表 / 选产品时按参考号搜索；`19.0.2.3.0` 起移除「参考号」页，原生 `default_code`（Reference）输入框移到产品名下方（模板 + 变体表单，标签 `Ref.`），输入框内右端「+」以弹窗管理额外参考号，存在额外参考号时悬停徽标显示清单 tooltip；`19.0.2.4.0` 起多变体产品参考号不共用（各变体维护自己的一份，产品表单整块隐藏） | `19.0.2.2.0` 已交付并验证（T-007 / T-008；T-006 i18n 随 `19.0.2.0.0` 改名同步完成）；T-011（2026-09-08，落地 `19.0.2.5.0`）已完成并**目标环境验收通过**：移除「参考号」页 / Reference 输入框移到产品名下方（标签 `Ref.`）/ 输入框内「+」弹窗管理额外参考号 / 徽标悬停显示清单 tooltip / 多变体参考号不共用（各变体一份）/ 变体参考号可在产品列表搜索；验收记录见模块 `CHANGELOG.md` →「验收记录（T-011）」；`19.0.2.5.1`（T-013，2026-09-09）补应用列表（Apps）中文名 / 摘要 / 描述 + 分类「产品」译文，目标环境已验收通过；T-011 与 T-013 均已验收 |
| `product_image` | 19.0.2.6.3 | 产品多图：产品 / 产品变体双入口（19.0.2.6.0 起，每个变体各自维护一组独立补充图）+ 原生主图独立 + 图库补充图 / 主图无删除入口/ 首张上传即主图 / 主图 2 倍 / 悬浮局部放大（540窗口+1080图片平移·左侧不足转下方/缩小·选框按比例·留白区白色）/ 点击预览（多图切换+右侧缩略图·关闭按钮暗色半透明·底部条默认透明悬浮淡入·图片初始避开上下条放大可覆盖全屏·任意大小可拖拽grab/grabbing·GPU 1:1顺滑·切图保留状态·无滚动条·缩略图未选中无边框）/ 右侧竖排缩略图（蓝色选中边框·编辑态无删除按钮·滚动不越界且与主图区顶底贴边·仅切换不写库）/ 图片管理弹窗（「+」打开·顶层overlay：上半大图（仅预览、无删除按钮）+平铺缩略图（每张含主图右上角×：删图库删记录·删主图自动提升图库首张·点缩略图只切弹窗大图·缩略图可拖排序(含主图·首位即主图·避让动画)·删除均先确认(含缩略图·主图提示提升)·批量删除(勾选模式+含缩略图清单确认)·大图固定尺寸缩略图占满余量超高滚动·选中主图名称行留空）·下半dropzone 点击/拖放/Ctrl+V（上传中缩略图+动画·粘贴后不自动关闭·上传不改页面大图）·header 最右侧正方形×关闭按钮 hover 变红） | 已交付，目标环境已验证（T-005，19.0.2.4.2，含 19.0.2.2.10~4.2：拖动排序（含主图·首位即主图）/ 删除确认 / 批量删除 / 选中主图名称行留空 / 确认框按钮顺序 / 关闭按钮贴边；T-006 i18n 在 19.0.2.5.0 完成）；坑点与风险提示见模块 `AGENTS.md` →「会话修改总结与风险提示」/「开发复盘与关键经验（T-005）」（原名 `product_multi_image`）；T-010 变体多图（19.0.2.6.1）已完成，目标环境验收通过（2026-09-08，含图库图片占位回归修复与复验；验收记录见模块 `CHANGELOG.md` →「交付记录（T-010）」）；19.0.2.6.2（2026-09-08）修复变体上传报「双归属」Validation Error（变体 action context `default_product_tmpl_id` 污染图库子行创建，见模块 `CHANGELOG.md` → `[19.0.2.6.2]`），待目标环境复验；`19.0.2.6.3`（T-013，2026-09-09）补应用列表（Apps）中文名 / 摘要 / 描述 + 分类「产品」译文，目标环境已验收通过 |
| [`product_packing`](product_packing/README.md) | 19.0.1.1.3 | 为产品 Inventory 标签页增加产品自身尺寸（尺寸变化时自动同步原生 Volume）与外贸纸箱字段：装箱数、长宽高、毛重、净重、自动计算 CBM；产品列表增加纸箱规格与 CBM 可选列 | 已交付（T-009，2026-09-08），目标环境已验证；`19.0.1.1.3`（T-013，2026-09-09）补应用列表（Apps）中文名 / 摘要 / 描述 + 分类「产品」译文并修掉重复 `msgid`，目标环境已验收通过 |
| [`product_card_view`](product_card_view/README.md) | 19.0.2.0.1 | 产品列表卡片视图（瀑布流）：为官方 Products 视图切换器新增 **Card** 按钮（库存 / 销售 / 采购入口），卡片顶部多图轮播（模板 / 变体两层图源不叠加）+ title / reference / on hand + 多变体按钮切换（一属性一行，禁用不存在组合），后端每页一次批量 `/product_card/payload`；官方 list / kanban / form 本身不改；`product_image` / `sale` / `purchase` 为可选依赖 | 已交付（T-012，2026-09-09）：Card 入口已确认；卡片内容 / 多图 / 变体 / Sales / Purchase 入口 / 双语 / 权限待复验（清单见模块 `README.md`，技术设计与踩坑见模块 `AGENTS.md`）；`19.0.2.0.1`（T-013，2026-09-09）补应用列表（Apps）中文名 / 摘要 / 描述 + 分类「产品」译文，目标环境已验收通过（Card 其余项仍待复验） |

历史模块（`sale_order_no`、`web_image_paste`（原 `image_uploader`）、`web_multi_tabs`）早期在仓库之外维护，
现已全部纳入本仓库统一迭代：`sale_order_no`、`web_image_paste` 较早纳入；`web_multi_tabs` 于 2026-09-09 在
`19.0.1.0.0` 基础上升级优化至 `19.0.2.0.0`（此前曾评估为「搁置」，本次按需求重启并完成规范对齐，详见模块
`CHANGELOG.md` → `[19.0.2.0.0]`）。
> 此处原标注的 `T-005` 与 `TODO.md` 中 product_image 需求编号重复，已去掉编号避免混淆。

---

## 快速开始

### 1. 挂到 Odoo

把本目录加入 Odoo 启动参数或配置文件的 `addons_path`（路径按实际部署位置填写）：

```bash
odoo --addons-path=/path/to/odoo/addons,/path/to/odoo-addons -d <db>
```

```ini
# odoo.conf
addons_path = /path/to/odoo/addons,/path/to/odoo-addons
```

### 2. 安装 / 升级模块

```bash
odoo -d <db> -i sale_order_no --stop-after-init     # 首次安装
odoo -d <db> -u sale_order_no --stop-after-init     # 代码改动后升级
```

也可在后台「应用 → 更新应用列表」后手动安装。

> 前端资源（JS / SCSS / QWeb）改动后必须 `-u` 升级，并在浏览器强制刷新，Odoo 会缓存资源。

---

## 应用列表（Apps）中文化（T-013）

> 2026-09-09 完成，目标环境**验收通过**（6 项验收标准全部通过，中英文各验一遍）。

### 是什么

模块源语言是英文，不装中文语言时「应用」列表全是英文；装了「简体中文 (zh_CN)」并切换后，**模块卡片标题、摘要、详情描述、左侧分类**要显示中文。这些文本不是来自 `__manifest__.py`（那里必须保持英文源文本），而是由各自模块 `i18n/zh_CN.po` 的「应用列表元数据」条目提供。

### 覆盖范围

| 模块 | 版本 | 中文名 | 中文分类 | 状态 |
|------|------|--------|----------|------|
| `sale_order_no` | 19.0.1.8.1 | 订单编号 | 销售（官方） | 已验收 |
| `web_image_paste` | 19.0.2.1.1 | 图片粘贴上传 | 生产力 / **图片** | 已验收 |
| `product_reference` | 19.0.2.5.1 | 产品参考号 | 库存 / **产品** | 已验收 |
| `product_image` | 19.0.2.6.3 | 产品图片 | 库存 / **产品** | 已验收 |
| `product_packing` | 19.0.1.1.3 | 产品装箱 | 库存 / **产品** | 已验收 |
| `product_card_view` | 19.0.2.0.1 | 产品卡片视图 | 库存 / **产品** | 已验收 |
| `web_multi_tabs` | 19.0.2.0.0 | 后台多标签页 | 生产力（官方） | 元数据已写入，**整包待验证** |

> 加粗的分类段是自定义段（官方 `base` 无译文），必须自己译；「销售 / 库存 / 生产力」是官方分类，沿用 `base` 自带译文，**不要**重复翻译。

### 使用方式

1. 目标环境升级（可一次带全部模块）：

   ```bash
   odoo -d <db> -u sale_order_no,web_image_paste,product_reference,product_image,product_packing,product_card_view --stop-after-init
   ```

2. 确认已安装中文：设置 → 语言 → 安装「简体中文 (zh_CN)」，然后切换到中文。
3. 打开「应用」，搜模块技术名（如 `product_packing`）：卡片标题 / 摘要 / 详情描述 / 左侧分类应为中文。
4. 切回英文：应回到 `__manifest__.py` 里的英文原文。

> 应用列表元数据是**后端字段**，`-u` 后刷新页面即可，**不需要**强刷浏览器；只有前端 JS / QWeb 术语才需要强刷。

### 示例（`product_packing/i18n/zh_CN.po` 节选）

```po
#. module: base
#: model:ir.module.module,shortdesc:base.module_product_packing
msgid "Product Packing"
msgstr "产品装箱"

#. module: base
#: model:ir.module.module,summary:base.module_product_packing
msgid ""
"Add packing/carton fields (units per carton, dimensions, gross/net weight, "
"auto CBM) to the product Inventory tab"
msgstr "在产品「库存」标签页增加装箱 / 纸箱字段：装箱数、长宽高、毛重 / 净重、自动计算 CBM"

#. module: base
#: model:ir.module.module,description:base.module_product_packing
msgid ""
"\n"
"Product carton packing module for foreign trade SOHO scenarios.\n"
"\n"
"Source language of this module is English (en_US); a Simplified Chinese\n"
"translation ships in i18n/zh_CN.po.\n"
"..."
msgstr ""
"\n"
"外贸 SOHO 场景下的产品纸箱装箱模块。\n"
"\n"
"本模块源语言为英文（en_US），简体中文译文见 i18n/zh_CN.po。\n"
"..."

#. module: base
#: model:ir.module.category,name:base.module_category_inventory_product
msgid "Product"
msgstr "产品"
```

四个易错点：

1. xmlid 前缀必须是 **`base.`**（模块记录由 `base` 写入），写成 `<module>.module_<module>` 会**静默失效**。
2. 每条都得以 `#. module: base` 开头，缺 `#. module:` 会让**整份 po 导入失败**。
3. `description` 的 `msgid` 必须等于 `textwrap.dedent(manifest["description"])`，多行 / 缩进 / 结尾换行都要一致（这是「可译文本必须单行」的唯一例外，因为它是整值翻译而非术语抽取）。
4. 同一 `msgid` 只能有一条：模块名常与已有条目同字面（如 `Product Images`、`Order Number`、`Product`），把新引用**合并进已有条目**的 `#:` 列表，不要新开一条。

### 改文案时必做

- 改了 `__manifest__.py` 的 `name` / `summary` / `description` → 必须同步上面三条的 `msgid`。导入时**不比对 `msgid`**，写错不报错，只会长期失同步。
- 改了**译文**（`msgstr`）→ 这些记录是 `noupdate=True`，`-u` 只补缺失语种、**不会覆盖**库里已有的 `zh_CN`。要生效二选一：

  ```python
  # odoo shell
  from odoo.tools.translate import TranslationImporter
  imp = TranslationImporter(env.cr)
  imp.load_file('<addons-path>/<module>/i18n/zh_CN.po', 'zh_CN')
  imp.save(force_overwrite=True)
  env.cr.commit()
  ```

  ```sql
  -- 或先清掉旧值再 -u
  UPDATE ir_module_module
     SET shortdesc = shortdesc - 'zh_CN',
         summary = summary - 'zh_CN',
         description = description - 'zh_CN'
   WHERE name = '<module>';
  ```

- **不要用「设置 → 翻译 → 导出」的结果整体覆盖** `i18n/zh_CN.po`：导出向导按 `ir_model_data.module` 过滤，这些记录属于 `base`，导出结果里**不含**它们，覆盖会把手写条目抹掉。
- 新增模块：按 [`DOCS_TEMPLATE.md`](DOCS_TEMPLATE.md) →「新模块 i18n 必备清单」执行，首版即带中文名称与描述。

### 验收结果（T-013，2026-09-09，目标 Odoo 19 部署环境）

| # | 验收标准 | 结果 |
|---|----------|------|
| 1 | 6 个模块 `-u` 升级无报错 | 通过 |
| 2 | 中文「应用」列表：6 个模块卡片标题为中文，摘要为中文 | 通过 |
| 3 | 中文「应用」详情：描述整段为中文 | 通过 |
| 4 | 中文「应用」左侧分类树：自定义段显示「产品」/「图片」 | 通过 |
| 5 | 切回英文：名称 / 摘要 / 描述回到 manifest 英文原文 | 通过 |
| 6 | 新模块按 `DOCS_TEMPLATE.md`「新模块 i18n 必备清单」执行 | 通过（清单已落地） |

**仓库内自动化自校验**（2026-09-09 实测，脚本见 [`AGENTS.md`](AGENTS.md) 4.6）：

| 检查项 | 结果 |
|--------|------|
| 重复 `msgid`（会导致整份 po 解析失败） | 7 份 `i18n/zh_CN.po` 均无重复 |
| 应用列表元数据 `msgid` 与 manifest 逐字符一致 | 7 个模块的 `shortdesc` / `summary` / `description` 全部一致 |
| 残留中文界面文本（`.py` / `.xml` / `.js` / `.csv`） | 仅剩中文注释，符合规范 |
| XML 语法 | 20 个文件解析通过 |
| JS 语法（`node --check`） | 11 个文件通过 |

---

## 开发约定（摘要）

完整规范见 [`AGENTS.md`](AGENTS.md)，以下为最容易踩坑的部分：

- **禁止修改 Odoo 核心源码**，一律 `_inherit` 扩展或 patch。
- 版本格式固定 `19.0.x.y.z`：破坏性变更 +x，功能新增 +y，修复 / 文档 +z。
- 界面、提示、注释、文档统一**简体中文**；错误信息要能直接给用户看，并带上出错的具体值。
- **国际化（i18n）**：模块源语言为**英文（`en_US`）**，所有用户可见文本（字段标签 / help / 报错 / 通知 / 视图与动作文案 / 前端 `_t()` 与 OWL 模板文本）在源码里写英文；简体中文译文放 `i18n/zh_CN.po`，默认展示英文，安装中文语言后切换生效。占位符统一 `%(name)s` 命名形式，禁止按位置拼接。
- **应用列表（Apps）也要中文**：`__manifest__.py` 的 `name` / `summary` / `description` 写英文，中文由 `i18n/zh_CN.po` 的 `model:ir.module.module,shortdesc|summary|description:base.module_<module>` 三条提供（自定义分类段再加 `model:ir.module.category,name:base.module_category_<...>`）。新模块首版必带，改 manifest 文案必须同步 `msgid`；细则与坑点见 [`AGENTS.md`](AGENTS.md) 4.8，新模块清单见 [`DOCS_TEMPLATE.md`](DOCS_TEMPLATE.md) →「新模块 i18n 必备清单」。
- 搜索能力必须在数据库层实现（可存储的计算字段 + 索引、`search=` 方法或 `any` 域），禁止 Python 侧全表过滤。
- 新增模型必须配 `security/ir.model.access.csv`。
- 字段改名 / 改类型必须配套 `migrations/<版本>/pre-migration.py`，且脚本要幂等。
- 每次改动需同步更新：manifest 版本号、模块 `CHANGELOG.md`、`README.md`、`AGENTS.md` 与根目录 `TODO.md`。

### Odoo 19 与旧版的差异（已核实源码）

- `name_get()` / `name_search()` 已**移除**，只剩 `_compute_display_name()` 与 `_search_display_name()`。
- `_sql_constraints` 已废弃，改用 `models.Constraint("UNIQUE(field)", "提示")`。
- 视图继承时，扩展祖先视图对其所有 primary 子视图生效；列表要继承基础列表而非某个 primary 子视图。
- 不要 `position="replace"` 删除原生字段节点（如 `sale_order` 的 `name`），改用 `invisible` / `column_invisible`，否则其他模块会找不到继承锚点。

---

## 文档地图

| 文件 | 面向 | 内容 |
|------|------|------|
| [`README.md`](README.md) |所有人 | 项目说明、目录结构、安装与使用、开发约定摘要 |
| [`AGENTS.md`](AGENTS.md) | AI 助手 / 开发者 | 业务背景、模块与代码规范、Odoo 19 API 事实、验证流程 |
| [`TODO.md`](TODO.md) | 需求管理 | 待办池 / 进行中 / 搁置（已完成需求不在此留存，完成信息与验收记录见模块一览表与各模块 `CHANGELOG.md`） |
| [`DOCS_TEMPLATE.md`](DOCS_TEMPLATE.md) | 维护者 | 模块 `README.md` / `CHANGELOG.md` / `AGENTS.md` 三类文档统一骨架与命名约定 |
| `<module>/README.md` | 使用者 | 单个模块的功能、字段、安装与操作步骤 |
| `<module>/AGENTS.md` | 维护者 | 该模块不可破坏的核心约束 |
| `<module>/CHANGELOG.md` | 维护者 | 逐版本的变更 / 影响 / 文档同步记录 |

---

## 路线图

最新需求状态见 [`TODO.md`](TODO.md)。已完成里程碑（完整状态见下方模块一览表）：

1. **T-001 自定义销售订单号**（`sale_order_no`）— 已交付，目标环境已验证
2. **T-002 产品多参考号 + 可搜索**（`product_reference`，原名 `product_model`）— 已交付（验收状态见模块一览表）
3. **T-003 图片粘贴上传**（`web_image_paste`，原 `image_uploader`）— 已交付，目标环境已验证
4. **T-004 产品多图图库**（`product_image`，原名 `product_multi_image`）— 已交付，目标环境已验证（`19.0.2.2.7`）
5. **T-005 图片管理弹窗增强**（`product_image`）— 已交付，目标环境已验证（`19.0.2.4.2`）
6. **T-006 模块国际化（i18n）**（`product_image` 等）— 已交付，目标环境已验证（`19.0.2.5.0`）
7. **T-009 产品包装信息**（`product_packing`）— 已交付，目标环境已验证（`19.0.1.1.2`）
8. **T-010 产品变体多图**（`product_image`）— 已交付，目标环境验收通过（`19.0.2.6.1`：变体独立编辑表单多图 widget / 变体各自独立图集 / 主图原生回退；含 19.0.2.6.0 图库图片占位回归修复与复验；验收记录见模块 `CHANGELOG.md` →「交付记录（T-010）」）
9. **T-011 产品参考号界面改造 + 多变体参考号不共用**（`product_reference`）— 已交付，目标环境验收通过（`19.0.2.5.0`：移除「参考号」页 / 原生 Reference 输入框移到产品名下方（`Ref.`）/ 输入框内「+」弹窗管理额外参考号 / 徽标悬停清单 tooltip / 变体各自维护一份参考号 / 变体参考号可在产品列表搜索；验收记录见模块 `CHANGELOG.md` →「验收记录（T-011）」）
10. **T-012 产品列表卡片视图（瀑布流）**（`product_card_view`）— 已交付（`19.0.2.0.0`，2026-09-09）：注册新 view type `card`，官方 Products 切换器新增 Card 按钮（库存 / 销售 / 采购入口）；卡片多图轮播 / title / reference / on hand / 多变体按钮切换；`product_image` / `sale` / `purchase` 为可选依赖（未装则只显示主图 / 跳过注入）；Card 入口已确认，其余项待复验（清单见模块 `README.md`，技术设计见模块 `AGENTS.md`）

11. **T-013 应用列表（Apps）中文名称与描述**（全部 6 个模块）— **已完成，目标环境验收通过**（2026-09-09，6 项验收标准全部通过）：各模块 `i18n/zh_CN.po` 补 `model:ir.module.module,shortdesc|summary|description:base.module_<module>` 与自定义分类译文；规范沉淀在 [`AGENTS.md`](AGENTS.md) 4.8 与 [`DOCS_TEMPLATE.md`](DOCS_TEMPLATE.md) →「新模块 i18n 必备清单」；总览与示例见下方「应用列表（Apps）中文化」

新增需求请追加到 `TODO.md` 的「待办池」末尾，不要在对话里另立清单。

---

## 许可证

LGPL-3
