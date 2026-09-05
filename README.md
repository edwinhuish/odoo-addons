# Odoo 19 外贸 SOHO 进销存自研模块

以 Odoo 19 社区版为基础，面向外贸 SOHO（一人 / 小团队）场景的进销存扩展模块集合。

核心链路：**产品（型号 / 图片）→ 报价单 → 销售订单 → 采购 → 出入库 → 收付款 / 发票**

设计取向：单据录入步骤尽量少、对外单据编号符合外贸习惯、界面与提示全中文。

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
| [`sale_order_no`](sale_order_no/README.md) | 19.0.1.7.0 | 销售订单 / 报价单自定义编号：客户编码 + 两位年份 + 年度流水（如 `DZ2602`）；含客户编码格式校验、报表替换、PDF 文件名定制、门户预览定制、批量补号 | 已交付，目标环境已验证 |
| [`web_image_paste`](web_image_paste/README.md) | 19.0.2.0.0 | 后台图片字段支持剪贴板 `Ctrl+V` / `Cmd+V` 粘贴与拖拽上传，即时预览 + 进度条，一次多图，超大图报错（原名 `image_uploader`） | 已交付，目标环境已验证 |
| `web_multi_tabs` | 19.0.1.0.0 | 后台内部多标签页，适配 PWA standalone | **不迁移**（与进销存主流程无关，T-005 决策搁置） |
| `product_model` | 19.0.1.0.0 | 产品多型号 + 可在列表 / 选产品时按型号搜索 | 已交付，目标环境已验证 |
| `product_image` | 19.0.2.3.0 | 产品多图：原生主图独立 + 图库补充图 / 主图无删除入口/ 首张上传即主图 / 主图 2 倍 / 悬浮局部放大（540窗口+1080图片平移·左侧不足转下方/缩小·选框按比例·留白区白色）/ 点击预览（多图切换+右侧缩略图·关闭按钮暗色半透明·底部条默认透明悬浮淡入·图片初始避开上下条放大可覆盖全屏·任意大小可拖拽grab/grabbing·GPU 1:1顺滑·切图保留状态·无滚动条·缩略图未选中无边框）/ 右侧竖排缩略图（蓝色选中边框·编辑态无删除按钮·滚动不越界且与主图区顶底贴边·仅切换不写库）/ 图片管理弹窗（「+」打开·顶层overlay：上半大图（仅预览、无删除按钮）+平铺缩略图（每张含主图右上角×：删图库删记录·删主图自动提升图库首张·点缩略图只切弹窗大图·缩略图可拖排序(主图固定·避让动画)·删除均先确认(含缩略图·主图提示提升)·批量删除(勾选模式+含缩略图清单确认)·大图固定尺寸缩略图占满余量超高滚动·选中主图名称行留空）·下半dropzone 点击/拖放/Ctrl+V（上传中缩略图+动画·粘贴后不自动关闭·上传不改页面大图）·header 最右侧正方形×关闭按钮 hover 变红） | 已交付，目标环境已验证（T-004，截至 19.0.2.2.7）；19.0.2.2.10~15 与 19.0.2.3.0（拖动排序 / 删除确认 / 批量删除 / 选中主图名称行留空）改动待验证（原名 `product_multi_image`） |

历史模块（`sale_order_no`、`web_image_paste`（原 `image_uploader`）、`web_multi_tabs`）来自仓库之外的本地备份目录，
仅作为迁移参考。其中 `sale_order_no`、`web_image_paste` 已迁入本仓库；`web_multi_tabs` 经 T-005 评估**决定不迁移**（与进销存主流程无关）。

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

## 开发约定（摘要）

完整规范见 [`AGENTS.md`](AGENTS.md)，以下为最容易踩坑的部分：

- **禁止修改 Odoo 核心源码**，一律 `_inherit` 扩展或 patch。
- 版本格式固定 `19.0.x.y.z`：破坏性变更 +x，功能新增 +y，修复 / 文档 +z。
- 界面、提示、注释、文档统一**简体中文**；错误信息要能直接给用户看，并带上出错的具体值。
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
| [`TODO.md`](TODO.md) | 需求管理 | 待办池 / 进行中 / 已完成 / 搁置，含验收标准与待验证清单 |
| [`DOCS_TEMPLATE.md`](DOCS_TEMPLATE.md) | 维护者 | 模块 `README.md` / `CHANGELOG.md` / `AGENTS.md` 三类文档统一骨架与命名约定 |
| `<module>/README.md` | 使用者 | 单个模块的功能、字段、安装与操作步骤 |
| `<module>/AGENTS.md` | 维护者 | 该模块不可破坏的核心约束 |
| `<module>/CHANGELOG.md` | 维护者 | 逐版本的变更 / 影响 / 文档同步记录 |

---

## 路线图

当前进度记录在 [`TODO.md`](TODO.md)，近期四项：

1. **T-001 自定义销售订单号**（`sale_order_no`）— 代码已交付，待环境验证
2. **T-002 产品多型号 + 可搜索**（`product_model`）
3. **T-003 图片粘贴上传**（`web_image_paste`，原 `image_uploader`）— 迁移并扩展到多图场景
4. **T-004 产品多图图库**（`product_image`，原名 `product_multi_image`）— 已交付，目标环境已验证

新增需求请追加到 `TODO.md` 的「待办池」末尾，不要在对话里另立清单。

---

## 许可证

LGPL-3
