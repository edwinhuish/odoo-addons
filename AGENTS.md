# AGENTS

本仓库是 **Odoo 19 外贸 SOHO 进销存**的自研 addons 集合。给 AI 助手与新开发者看的行为规范与关键上下文。

## 1. 业务背景

- 使用者：外贸 SOHO（一人 / 小团队），要求操作简单、少点几下就能录完单据。
- 核心链路：产品（型号 / 图片）→ 报价单 → 销售订单 → 采购 → 出入库 → 收付款 / 发票。
- 语言：界面、提示、注释、文档统一**简体中文**；金额默认涉及多币种（报价常用 USD）。
- 对外单据编号是业务刚需：客户编码 + 年份 + 流水号（如 `DZ2602`），内部 `SOxxxx` 不对外。

## 2. 仓库约定

- 仓库根目录（`<addons-path>`）**即 `addons_path`**：一个模块一个一级目录，根目录只放文档。
  文档中出现的 `<addons-path>`、`<db>`、`<module>`、`<version>` 均为占位符，按实际部署值替换，不要写死本机路径。
- 历史模块（`sale_order_no`、`image_uploader`、`web_multi_tabs`）来自仓库之外的本地备份目录，
  仅作为迁移参考，**不纳入本仓库、不直接在该目录开发**。
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
|-- migrations/<version>/  # 仅在字段/数据需要迁移时
|-- README.md  CHANGELOG.md  AGENTS.md
```

## 3. 模块规范

- `version` 一律 `19.0.x.y.z`：架构/破坏性变更 +x，功能新增 +y，修复与文档 +z。
- `__manifest__.py` 必填：`name`（中文）、`summary`、`description`、`category`、`author`、`depends`、`installable: True`、`license`。静态资源走 `assets`（`web.assets_backend`），不走 `data`。
- `depends` 最小化：能用 `product` 就不要依赖 `sale`；不要为了方便依赖 `website`。
- 新增模型必须配 `security/ir.model.access.csv`，权限最小化（普通用户可读写业务数据，管理员可配置）。
- 数据文件（视图/报表/权限）必须登记进 `data`，顺序：security → views → reports → data。

## 4. Python 规范

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

## 5. 前端规范

- JS 文件首行必须是 `/** @odoo-module **/`；用 `@web/core/utils/patch` 打补丁，不覆写整个组件。
- QWeb 用 `t-inherit` + `t-inherit-mode="extension"` 扩展原模板，不复制核心模板全文。
- 静态资源放 `static/src/{js,xml,scss}/`（历史 `image_uploader` 为此结构，迁移时保持一致）。
- 事件处理要判 `props.readonly`，只读态不得触发写操作。
- 复用原生上传 / 校验链路（如 `onFileUploaded`、`checkFileSize`），不重复实现。

## 6. 文档与变更规范

每次功能改动必须同步更新，缺一不可：

1. `__manifest__.py` 的 `version`（按第 3 节规则递增）与 `description`（涉及用户可见行为时）
2. 模块 `CHANGELOG.md`：变更 / 影响 / 文档同步三段式，注明日期
3. 模块 `README.md`：用户可见功能、字段表、安装与使用步骤
4. 模块 `AGENTS.md`：**不可破坏的核心约束**清单（约束变化时更新）
5. 根目录 `TODO.md`：任务状态流转（见第 7 节）

## 7. TODO.md 使用规则

- `TODO.md` 是需求唯一入口，所有任务都在里面流转，不要在对话里另立清单。
- 新需求追加到「待办池」末尾并取下一个 ID；开工移入「进行中」并补齐验收标准；验收通过移入「已完成」并记录日期与版本号；不做则移入「搁置」并写原因。
- 动工前先读该条目的「设计约束」，有疑问在条目下以备注形式记录，不要自行放宽约束。

## 8. 已有模块速查

| 模块 | 版本 | 作用 | 状态 |
|------|------|------|------|
| `sale_order_no` | 19.0.1.3.0 | 销售订单 / 报价单自定义编号（`order_no`，客户编码 + 两位年份 + 年度流水），含客户编码格式校验、报表替换、批量补号 | 已迁入，待环境验证（T-001） |
| `image_uploader` | 19.0.1.0.0 | 后台图片字段粘贴 / 拖拽上传（patch `ImageField` + `FileUploader`，复用原生上传链路，即时预览 + 进度条） | 已交付，目标环境已验证（T-003） |
| `web_multi_tabs` | 19.0.1.0.0 | 后台内部多标签页，适配 PWA standalone | 未迁移，按需（T-005） |
| `product_model` | 19.0.1.0.0 | 产品多型号 + 可搜索（One2many 明细 / 冗余 trigram 索引 / 命中提示） | 目标环境已验证（T-002） |
| `product_multi_image` | 19.0.1.0.0 | 产品多图（原位多图浏览：不新增页签 / 左右切换 / 缩略图 / 粘贴新增 / 首图即主图，继承 image.mixin 复用多尺寸） | 已交付，待目标环境验证（T-004） |

## 9. 验证流程

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
