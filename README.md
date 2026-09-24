# Odoo 19 外贸 SOHO 进销存自研模块

以 Odoo 19 社区版为基础，面向外贸 SOHO（一人 / 小团队）场景的进销存扩展模块集合。

核心链路：**产品（参考号 / 图片）→ 报价单 → 销售订单 → 采购 → 出入库 → 收付款 / 发票**

设计取向：单据录入步骤尽量少、对外单据编号符合外贸习惯、界面支持中英双语（**源语言英文，默认英文，中文由 `i18n/zh_CN.po` 提供**）。

---

## 目录结构

仓库根目录**即 Odoo 的 `addons_path`**，一个模块一个一级目录，根目录只放文档与统一开发入口
（`Taskfile.yml`）；开发环境相关的东西一律收进 `.dev/`，编辑器配置收进 `.vscode/`。

```text
odoo-addons/           # 本目录即 addons_path
|-- README.md           # 本文件：项目说明与上手指南
|-- AGENTS.md           # AI 助手 / 开发者的行为规范与关键约束
|-- TODO.md             # 需求唯一入口，任务在这里流转
|-- DEV_WORKFLOW.md     # 本地开发与热重载工作流（怎么跑、怎么调、怎么拉数据）
|-- DEV_ENV_SETUP.md    # 开发环境的搭建总结（方案选型 / 实施步骤 / 踩坑与最佳实践）
|-- STAGE_REPORT_2026-09-22.md  # 阶段总结与交接报告（按模块/任务归档：目标 / 成果 / 关键问题与解法 / 经验教训 / 后续建议 / 交接清单）
|-- STAGE_REPORT_2026-09-24.md  # 同日报告（product_variant_conversion：按需属性支持 / 弹窗互换 / 两处线上报错修复；product_image：产品列表 Images 列改显主图 T-038，见第 7 节）
|-- Taskfile.yml        # 统一开发命令入口（task --list）
|-- .dev/               # 本地开发环境：compose.yml + odoo.conf + docker/（镜像）+ scripts/（脚本）
|-- .vscode/            # 调试 / 任务 / 设置 / 推荐扩展配置
|-- sale_order_no/      # 订单编号（已迁入）
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
| [`product_reference`](product_reference/README.md) | 19.0.3.0.0 | 产品多参考号 + 可在列表 / 选产品时按参考号搜索 + **产品级编号** `base_reference`（`19.0.3.0.0` 起叠加进原生 `default_code` 的 compute：产品表单 / 列表 / 搜索 / 卡片都直接可见；单变体产品与变体编号两处同值、多变体产品各管一层；产品级与变体级参考号都可见）；`19.0.2.3.0` 起移除「参考号」页，原生 `default_code`（Reference）输入框移到产品名下方（标签 `Ref.`），输入框内右端「+」以弹窗管理额外参考号 |
| `product_image` | 19.0.2.6.5 | 产品多图（**产品列表「Images」列可选显示，渲染产品主图缩略、不含图库补充图；库存 / 销售 / 采购三处产品列表生效**）：产品 / 产品变体双入口（19.0.2.6.0 起，每个变体各自维护一组独立补充图）+ 原生主图独立 + 图库补充图 / 主图无删除入口/ 首张上传即主图 / 主图 2 倍 / 悬浮局部放大（540窗口+1080图片平移·左侧不足转下方/缩小·选框按比例·留白区白色）/ 点击预览（多图切换+右侧缩略图·关闭按钮暗色半透明·底部条默认透明悬浮淡入·图片初始避开上下条放大可覆盖全屏·任意大小可拖拽grab/grabbing·GPU 1:1顺滑·切图保留状态·无滚动条·缩略图未选中无边框）/ 右侧竖排缩略图（蓝色选中边框·编辑态无删除按钮·滚动不越界且与主图区顶底贴边·仅切换不写库）/ 图片管理弹窗（「+」打开·顶层overlay：上半大图（仅预览、无删除按钮）+平铺缩略图（每张含主图右上角×：删图库删记录·删主图自动提升图库首张·点缩略图只切弹窗大图·缩略图可拖排序(含主图·首位即主图·避让动画)·删除均先确认(含缩略图·主图提示提升)·批量删除(勾选模式+含缩略图清单确认)·大图固定尺寸缩略图占满余量超高滚动·选中主图名称行留空）·下半dropzone 点击/拖放/Ctrl+V（上传中缩略图+动画·粘贴后不自动关闭·上传不改页面大图）·header 最右侧正方形×关闭按钮 hover 变红） | 已交付，目标环境已验证（T-005，19.0.2.4.2，含 19.0.2.2.10~4.2：拖动排序（含主图·首位即主图）/ 删除确认 / 批量删除 / 选中主图名称行留空 / 确认框按钮顺序 / 关闭按钮贴边；T-006 i18n 在 19.0.2.5.0 完成）；坑点与风险提示见模块 `AGENTS.md` →「会话修改总结与风险提示」/「开发复盘与关键经验（T-005）」（原名 `product_multi_image`）；T-010 变体多图（19.0.2.6.1）已完成，目标环境验收通过（2026-09-08，含图库图片占位回归修复与复验；验收记录见模块 `CHANGELOG.md` →「交付记录（T-010）」）；19.0.2.6.2（2026-09-08）修复变体上传报「双归属」Validation Error（变体 action context `default_product_tmpl_id` 污染图库子行创建，见模块 `CHANGELOG.md` → `[19.0.2.6.2]`），待目标环境复验；`19.0.2.6.4`（T-013，2026-09-09）补应用列表（Apps）中文名 / 摘要 / 描述 + 分类「产品」译文，目标环境已验收通过；`19.0.2.6.5`（T-038，2026-09-23）修复产品列表「Images」列看不到图片——原列绑图库计数 `image_gallery_count`（只显示数字），改绑原生 `image_128`（主图缩略）+ `image` widget，列仍为可选只读（默认隐藏），继承基础列表视图故三处入口同时生效（本地 7 项自动化用例 + dev 库三入口 arch 实测通过，见模块 `CHANGELOG.md` → `[19.0.2.6.5]`），**待目标环境界面复验** |
| [`product_dimension`](product_dimension/README.md) | 19.0.4.1.1 | 为产品 Logistics 组增加物流尺寸（尺寸单位 cm / m + 长宽高，**`Dimension Unit` 默认厘米**；**存放在变体上**、每条变体各持一份，尺寸变化自动同步原生 Volume）；`19.0.2.0.0`（T-021）由 `product_packing` 改名而来，**移除纸箱与包装**字段，并把尺寸从模板下沉到变体 | `product_packing` 时期（T-009 / T-013）目标环境已验证；`19.0.2.0.1`（T-021，2026-09-22）改名 + 尺寸下沉 + 移除纸箱：本地已验证（旧数据搬运实测、**17 项**自动化测试、三表单合成 arch 实测、前端资源已确认进 `web.assets_backend`；`19.0.2.0.1` 修复 i18n 静默失效并打磨中文，字段 / 视图术语 / 应用列表已按数据库核对；`19.0.3.0.0` 补齐「变体快速编辑表单」挂载点、明确与原生 Volume 同进同退、`19.0.3.1.0` 表单填完尺寸立刻算出体积、`19.0.4.0.0` 体积改由前端算（后端只兜底、不再返回体积）、`19.0.4.1.0` 修 cm 小体积被显示成 0（前端取整参数 + Volume 精度提到 6 位）、`19.0.4.1.1` 修新建产品时 `Dimension Unit` 默认是空的），**待目标环境验证** |
| [`product_card_view`](product_card_view/README.md) | 19.0.2.1.4 | 产品列表卡片视图（瀑布流）：为官方 Products 视图切换器新增 **Card** 按钮（库存 / 销售 / 采购入口），卡片顶部多图轮播（模板 / 变体两层图源不叠加）+ title / reference / on hand + 多变体按钮切换；**编号随选择切换**（未选变体=产品编号，选中变体=该变体编号；已选组合行只显示属性组合）；编号只读原生 `default_code`（**与 `product_reference` 零耦合**）；官方 list / kanban / form 本身不改；`product_image` / `sale` / `purchase` 为可选依赖 |
| [`product_variant_conversion`](product_variant_conversion/README.md) | 19.0.6.1.0 | 给产品**追加属性 / 取值**而不丢变体，**入口不是按钮**：用户照常在原生「属性与变体」页改属性、点保存，保存这一步自己检测这次变更（服务端用「只写配置、不碰变体」的试写分析）；会新增变体就弹窗逐组合确认归属，确认后属性变更与归属同一次写库；会丢既有变体则拒绝保存。每条既有 `product.product` 记录（id 不变）都保留自己的库存、单据、价格与补货规则；**变体上的值（含编号、参考号、图片）一律原样保留**（`19.0.5.3.0` 起与 `product_reference` 零耦合）；转换留下**台账 + 谱系**供追溯。仅依赖 `product`。**支持「按需生成变体」的属性**（`19.0.6.0.0` / `T-039`）：改属性**只展开「立即」轴**，按需轴按既有变体现带取值钉住、其它取值等订单创建（带按需属性的产品不做价格分离）；**建产品**时带这种属性仍会拦住并给出出路（原生会建出 0 变体的产品） |
| [`sale_product_hover`](sale_product_hover/README.md) | 19.0.1.6.0 | 报价单 / 销售订单订单行悬停（触屏为长按）展示**产品详情**浮层：产品图片、名称、型号、规格（变体属性）、销售描述、可用库存（**不含任何价格**：无订单行的数量与单价，也无产品售价）；**新增（未保存）的产品行也能预览**；浮层跟随鼠标并自带越界收敛，同时屏蔽行内原生 tooltip；每页一次批量 payload + 浏览器缓存，悬停不发请求；仅作用于 `sale.order.line` 列表，不新增字段 / 权限 / 视图 | **已完成（T-014，2026-09-17 归档）**；`19.0.1.1.0`（2026-09-14）重做触发链路、补齐规格与价格展示、新增触屏长按与响应式；`19.0.1.1.1` 修复 `data-id` 被判成数字导致行归属反查恒失败（**悬停一直没反应的真正根因**，见模块 `AGENTS.md` P1 陷阱 11）；`19.0.1.2.0` 浮层改为跟随鼠标并屏蔽行内原生 tooltip（陷阱 12 / 13）；`19.0.1.3.0` 让新增（未保存）的产品行也能预览（陷阱 14），`19.0.1.3.1` 修复「接口成功但没返回该行数据 → 该行永久失效」（陷阱 15）并加前后端版本自证，`19.0.1.3.2` 修复整份重写缓存模块时漏掉 `getLineHoverPayload` 导出导致的悬停报错，`19.0.1.3.3` 加「空 `line_ids` 探测 + 启动自检」以区分「服务端 Python 没升级」与数据 / 权限问题，`19.0.1.4.0` 把**新行改为前端按 `product_id` 直接查产品**（不再走服务端接口，也无需升级服务端），`19.0.1.4.1` 把该逻辑并入已有文件以避免「新增 assets 文件需 `-u`」导致模块加载失败，`19.0.1.5.0` 按需求**移除浮层里的订单数量与本单单价**，`19.0.1.5.1` 后端版本改为自动读 `__manifest__.py`（版本只剩 manifest + JS 两处），`19.0.1.6.0` 再**移除浮层里的产品售价**（浮层自此不含任何价格）；验证清单见模块 `README.md` |

历史模块（`sale_order_no`、`web_image_paste`（原 `image_uploader`）、`web_multi_tabs`）早期在仓库之外维护，
现已全部纳入本仓库统一迭代：`sale_order_no`、`web_image_paste` 较早纳入；`web_multi_tabs` 于 2026-09-09 在
`19.0.1.0.0` 基础上升级优化至 `19.0.2.0.0`（此前曾评估为「搁置」，本次按需求重启并完成规范对齐，详见模块
`CHANGELOG.md` → `[19.0.2.0.0]`）。
> 此处原标注的 `T-005` 与 `TODO.md` 中 product_image 需求编号重复，已去掉编号避免混淆。

---

## 扩展解耦矩阵（三个相互关联的自研模块）

`product_reference`（参考号 / 产品级编号）、`product_variant_conversion`（属性转换）、
`product_card_view`（卡片视图）三者**互相没有 `depends`**：交叉点全部是**运行期软探测**，
每个模块对可选模块的了解都收在**一处适配层**里。任意一个缺席，其余两个照常工作。

| 装了哪些 | `product_reference` | `product_variant_conversion` | `product_card_view` |
|----------|--------------------|------------------------------|---------------------|
| 三个都装 | 产品编号由自己的 compute 提供，卡片读原生 `default_code` 就有值 | 只做「按归属复用既有变体」，不碰编号与参考号 | 卡片编号栏显示产品编号（多变体产品） |
| 缺 `product_variant_conversion` | 无影响（本模块只依赖 `product`） | — | 无影响（卡片只读原生字段） |
| 缺 `product_reference` | — | 无影响（零耦合） | 多变体产品的编号为空 → 卡片显示 `—`（原生语义：模板级 `default_code` 对多变体产品恒为空） |
| 缺 `product_card_view` | 无影响 | 无影响 | — |

**边界约定**（三条，模块 `AGENTS.md` 里各自有对应约束）：

1. **只允许软探测**：可选模块一律不写进 `depends`；读它的字段前先判 `_fields`，拿它的模型用
   `env.get()`（不能 `env[模型名]`，模型缺失时那是 `KeyError`，会让主流程整条崩掉）。
2. **提供方不感知消费方**：`product_reference` 只管定义字段与契约（谁在什么时候写它由
   `product_variant_conversion` 负责）；消费方全部自带降级，缺谁都不报错、只是少一层数据。
3. **`product_variant_conversion` 会改动核心写行为**（拦截改属性的 `write()` —— 这是它的功能本身）：
   其它模块的程序化代码 / 测试若要产生多变体产品，请把属性行放进 **`create()`**（`create` 只拦一种情况：
   产品带「按需生成变体」的属性 —— 那种产品原生一条变体都不会建；`always` 属性照常放行，
   `create_product_product=False` 的沙盒调用（如产品导入）也一律放行）。

> 落地验证：四组环境实测（`product_reference` 单装、`product_card_view` 单装（含 `stock`）、
> `product_variant_conversion` 单装、三者同装）各 0 failed / 0 error，降级分支由测试分别断言；
> 明细见各模块 `CHANGELOG.md`。

---

## 快速开始

**本地开发（推荐）**：Odoo 与 PostgreSQL 跑在 `.dev/compose.yml` 里，仓库直接挂进容器，
代码与调试器都留在宿主机——不连远程容器，改完代码即生效（`--dev=all` 负责热重载）。

```bash
# 首次：装 go-task（单文件二进制，不需要 sudo；装了 go 就是这一行）
GOBIN="$HOME/.local/bin" go install github.com/go-task/task/v3/cmd/task@latest
export PATH="$HOME/.local/bin:$PATH"

task up        # 启动 → http://localhost:8069（首次自动建库、按 .dev/init.yaml 装模块与扩展、装 en_US/zh_CN）
task           # 列出所有命令（up / init / logs / update / test / pull / check / todo / deploy ...）
```

首次 `task up` 会把 `dev` 库一次配好，**不用手工装模块或改密码**：

| 项 | 值 |
|----|-----|
| 网页登录 | `admin` / `admin` |
| 数据库账号 | `odoo` / `odoo` |
| 模块 | `.dev/init.yaml` 的 `modules`（默认 Sales `sale_management`、Purchase、Inventory `stock`），改完跑 `task init` |
| 仓库扩展 | `.dev/init.yaml` 的 `addons`（当前全部 9 个模块；**留空 = 自动发现全部**，新模块不用登记），改完跑 `task init` |
| 语言 | `.dev/init.yaml` 的 `langs`：`en_US`（English US）+ `zh_CN`（Chinese, Simplified），缺哪个装哪个（含译文） |
| 演示数据 | 随首次安装加载（重建镜像不会丢，数据库在 `.dev/data/` 绑定挂载里） |
| 批次 | 演示数据写死的 `tracking=lot` 装完会被清回 `none`（自录产品不碰）；要留着就 `DEV_KEEP_DEMO_LOTS=1 task init` |

要重新来一遍：`task init -- --fresh`（删库重建，含演示数据）或 `task reset && task up`（连 filestore 一起清）。
详见 [`DEV_WORKFLOW.md`](DEV_WORKFLOW.md) 第 2 节。

VS Code 里等价入口是任务面板（`Ctrl+Shift+B`）——它调的是同一个 `Taskfile.yml`。
完整流程见 [`DEV_WORKFLOW.md`](DEV_WORKFLOW.md)。

下面几节是**服务器侧**的安装 / 升级步骤（本地验收通过后一次性同步过去，见 `task deploy`）。

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
| `product_reference` | 19.0.3.0.0 | 产品参考号 | 库存 / **产品** | `19.0.2.5.3` 及以前已验收；`19.0.2.6.0` ~ `19.0.3.0.0` 产品级编号 `base_reference`（叠加进原生 `default_code` 的 compute + 单变体两处同值 + 两层参考号都可见 + 存量回填）：本地已验证、**待目标环境验证** |
| `product_image` | 19.0.2.6.5 | 产品图片 | 库存 / **产品** | 已验收；`19.0.2.6.5` 产品列表「Images」列改为主图缩略（本地 7 项测试 0 failed），**待目标环境界面复验** |
| `product_dimension` | 19.0.4.1.1 | 产品尺寸 | 库存 / **产品** | 待目标环境验证；`19.0.4.1.1` 修新建产品时 `Dimension Unit` 默认是空的（本地 17 项测试 0 failed） |
| `product_card_view` | 19.0.2.1.4 | 产品卡片视图 | 库存 / **产品** | Card 入口已核对，卡片内容待复验；`19.0.2.0.7` 修分组切换后空白；`19.0.2.1.3` 编号与 `product_reference` 零耦合（4 项 payload 用例，本地 0 failed）；`19.0.2.1.4` 编号随选择切换（未选=产品编号 / 选中=变体编号）+ 已选组合行只显示属性组合（前端改动，需强刷浏览器） |
| `web_multi_tabs` | 19.0.2.0.0 | 后台多标签页 | 生产力（官方） | 元数据已写入，**整包待验证** |
| `product_variant_conversion` | 19.0.6.1.0 | 产品变体转换 | 库存 / **产品** | 元数据已写入，**整包待验证**；`19.0.6.1.0` 归属弹窗交互优化（所有选项可选、重复选择自动互换，换归属从两步变一步）；`19.0.6.0.0`（`T-039`）**支持「按需生成变体」的属性**：改属性只展开「立即」轴、按需轴按既有变体现带取值钉住，带按需属性的产品不做价格分离；建产品时带按需属性仍拦住（原生会建出 0 变体）；47 项测试本地 0 failed；`19.0.5.3.2` 修「一次加两个属性」时的 chatter `Expected singleton`；`19.0.5.3.0` 与 `product_reference` 零耦合、变体值原样保留 |
| `sale_product_hover` | 19.0.1.6.0 | 订单行产品悬浮卡 | 销售（官方） | 已验收（随 T-014 完成归档，2026-09-17） |

> 加粗的分类段是自定义段（官方 `base` 无译文），必须自己译；「销售 / 库存 / 生产力」是官方分类，沿用 `base` 自带译文，**不要**重复翻译。

### 使用方式

1. 目标环境升级（可一次带全部模块）：

   ```bash
   odoo -d <db> -u sale_order_no,web_image_paste,product_reference,product_image,product_dimension,product_card_view --stop-after-init
   ```

2. 确认已安装中文：设置 → 语言 → 安装「简体中文 (zh_CN)」，然后切换到中文。
3. 打开「应用」，搜模块技术名（如 `product_dimension`）：卡片标题 / 摘要 / 详情描述 / 左侧分类应为中文。
4. 切回英文：应回到 `__manifest__.py` 里的英文原文。

> 应用列表元数据是**后端字段**，`-u` 后刷新页面即可，**不需要**强刷浏览器；只有前端 JS / QWeb 术语才需要强刷。

### 示例（`product_dimension/i18n/zh_CN.po` 节选）

```po
#. module: base
#: model:ir.module.module,shortdesc:base.module_product_dimension
msgid "Product Dimensions"
msgstr "产品尺寸"

#. module: base
#: model:ir.module.module,summary:base.module_product_dimension
msgid "Add a dimension unit and length / width / height per product variant, and keep the native Volume in sync"
msgstr "为每条产品变体增加尺寸单位与长宽高，并同步原生 Volume"

#. module: base
#: model:ir.module.module,description:base.module_product_dimension
msgid ""
"\n"
"Product dimension module for foreign trade SOHO scenarios.\n"
"\n"
"Source language of this module is English (en_US); a Simplified Chinese translation ships in i18n/zh_CN.po.\n"
"..."
msgstr ""
"\n"
"面向外贸 SOHO 场景的产品尺寸模块。\n"
"\n"
"本模块源码语言为英文（en_US），简体中文译文见 i18n/zh_CN.po。\n"
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
| [`TODO.md`](TODO.md) | 需求管理 | 待办池 / 进行中 / 搁置（已完成需求不在此留存，完成信息与验收记录见模块一览表与各模块 `CHANGELOG.md`）；结构由 `task check` 校验，进度看板用 `task todo`（跑条目自带的「检测：」条件） |
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
7. **T-009 产品包装信息**（`product_packing`，现名 `product_dimension`）— 已交付，目标环境已验证（`19.0.1.1.2`）；该模块在 `19.0.2.0.0`（T-021，2026-09-22）改名为 `product_dimension` 并移除纸箱字段、尺寸下沉到变体，见模块 [`README.md`](product_dimension/README.md) →「从 product_packing 迁移」
8. **T-010 产品变体多图**（`product_image`）— 已交付，目标环境验收通过（`19.0.2.6.1`：变体独立编辑表单多图 widget / 变体各自独立图集 / 主图原生回退；含 19.0.2.6.0 图库图片占位回归修复与复验；验收记录见模块 `CHANGELOG.md` →「交付记录（T-010）」）
9. **T-011 产品参考号界面改造 + 多变体参考号不共用**（`product_reference`）— 已交付，目标环境验收通过（`19.0.2.5.0`：移除「参考号」页 / 原生 Reference 输入框移到产品名下方（`Ref.`）/ 输入框内「+」弹窗管理额外参考号 / 徽标悬停清单 tooltip / 变体各自维护一份参考号 / 变体参考号可在产品列表搜索；验收记录见模块 `CHANGELOG.md` →「验收记录（T-011）」）
10. **T-012 产品列表卡片视图（瀑布流）**（`product_card_view`）— 已交付（`19.0.2.0.0`，2026-09-09）：注册新 view type `card`，官方 Products 切换器新增 Card 按钮（库存 / 销售 / 采购入口）；卡片多图轮播 / title / reference / on hand / 多变体按钮切换；`product_image` / `sale` / `purchase` 为可选依赖（未装则只显示主图 / 跳过注入）；Card 入口已确认，其余项待复验（清单见模块 `README.md`，技术设计见模块 `AGENTS.md`）

11. **T-013 应用列表（Apps）中文名称与描述**（全部 6 个模块）— **已完成，目标环境验收通过**（2026-09-09，6 项验收标准全部通过）：各模块 `i18n/zh_CN.po` 补 `model:ir.module.module,shortdesc|summary|description:base.module_<module>` 与自定义分类译文；规范沉淀在 [`AGENTS.md`](AGENTS.md) 4.8 与 [`DOCS_TEMPLATE.md`](DOCS_TEMPLATE.md) →「新模块 i18n 必备清单」；总览与示例见下方「应用列表（Apps）中文化」

12. **T-014 订单行产品悬浮卡**（`sale_product_hover`）— **已完成**（`19.0.1.6.0`，2026-09-16 完成、2026-09-17 归档）：报价单 / 销售订单订单行悬停（触屏长按）弹出**产品详情**浮层（图片 / 名称 / 型号 / 规格 / 描述 / 可用库存，**不含任何价格**：无订单行的数量与单价，也无产品售价）；浮层跟随鼠标、越界自动翻侧 / 贴边，并屏蔽行内原生 tooltip；**新增（未保存）的产品行同样可预览**；每页一次批量 payload + 浏览器缓存，悬停不发请求；不改官方视图、不新增字段与权限；`19.0.1.0.1` / `19.0.1.0.2` 曾尝试修复悬停不触发，`19.0.1.1.0` 重做触发链路，`19.0.1.1.1` 修掉真正的根因（行 `data-id` 是字符串却被当成数字反查），`19.0.1.2.0` 改为跟随鼠标，`19.0.1.3.0` 支持新增产品行预览、`19.0.1.3.1` 修复新行「接口无数据即永久失效」并加版本自证、`19.0.1.3.2` 修复缓存模块少导出的回归、`19.0.1.3.3` 加服务端版本探测与启动自检、`19.0.1.4.0` **新行改为前端直接查产品**（不再依赖服务端升级）、`19.0.1.4.1` 把该逻辑并入已有文件（新增 assets 文件需 `-u`，会报 modules 未定义）、`19.0.1.5.0` 移除浮层里的数量与单价、`19.0.1.5.1` 后端版本改为自动读 `__manifest__.py`（版本只剩 manifest + JS 两处）、`19.0.1.6.0` 移除产品售价（浮层自此不含任何价格），排障步骤见模块 `README.md`

13. **T-015 产品变体转换（追加属性 / 取值而不丢变体 + 归属谱系）**（`product_variant_conversion`）— 已交付（T-015，2026-09-21；交付版本 `19.0.4.0.0`，现为 `19.0.6.1.0`），**待目标环境验证**：**不加按钮、不用向导**，用户照常在原生「属性与变体」页改属性、点保存；保存这一步自己检测这次变更（服务端用 `create_product_product=False` 的试写分析，既有变体毫发无损），会新增变体就弹出归属弹窗、逐组合指定「由哪条既有变体继续承载」（默认已按「什么都不指定时的结果」填好，可逐行改），**用户确认之前保存不继续**，确认后属性变更与归属映射同一次写库、同一个事务；会丢既有变体（删取值 / 删属性 / 组合数变少）直接拒绝保存，绝不静默归档或删除；每条既有 `product.product` 记录（id 不变）保留自己的库存、库存移动明细、销售 / 采购 / 发票行、供应商价格与补货规则；转换落成**转换台账 + 变体谱系**，变体上有可搜索的「所属转换 / 来源变体」，产品表单有智能按钮（谱系明细在台账详情页），变体表单 / 列表 / 搜索都能追溯来源与归属；弹窗可勾选把既有变体的供应商价格应用到全部变体。本地两个环境各 38 项自动化测试全部通过，归属怎么指定（供应商价格勾选框默认不勾选）、被拒绝的情况、来源怎么追溯、**价格数据默认按变体分离**（改一个变体的价格不影响别的）、**字段归属审计**（条码 / 成本 / 体积 / 重量 / 内部参考号的真身在变体上，转换**不需要任何数据迁移**）与**新变体继承策略**（成本 / 体积 / 重量按 `Derived From` 继承，可关）见模块 `README.md`，技术约束与源码事实（含保存前钩子与递归陷阱、场景覆盖矩阵、价格 / 库存同步规则、已知边界）见模块 `AGENTS.md` → L1 / L2（P1~P5）；后续迭代需求见 `TODO.md`：`T-016` ~ `T-024` 已归档，待办池剩 `T-021`

新增需求请追加到 `TODO.md` 的「待办池」末尾，不要在对话里另立清单。

---

## 许可证

LGPL-3
