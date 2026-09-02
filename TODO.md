# TODO

> 本文件是需求与任务的**唯一入口**。所有新增需求都追加到「待办池」，开工即移入「进行中」，验收后移入「已完成」。

## 追加规则

1. **新需求一律追加到「待办池」末尾**，ID 顺序递增（`T-001` → `T-002` → …），不要插队、不要重排已有 ID。
2. 一行一项，格式：`- [ ] T-0xx ｜ 模块名 ｜ P0/P1/P2 ｜ 需求一句话描述`。
3. **开工**：整行剪切到「进行中」，并在下方补「验收标准」清单。
4. **完成**：整行剪切到「已完成」，追加完成日期与落地版本号。
5. 暂时不做：移入「搁置 / 放弃」并写明原因，不删除，保留决策痕迹。
6. 一个需求对应一个模块；跨模块需求在「模块」列用 `+` 连接（如 `product_model + image_uploader`）。
7. 需求被拆解时，子项直接在条目下用缩进 `- [ ]` 列出，不单独占用顶层 ID。

## 状态与优先级

| 标记 | 含义 |
|------|------|
| 🔜 | 待办（在待办池中排队） |
| 🚧 | 进行中（已开工，未验收） |
| ✅ | 已完成（目标环境验证通过） |
| ⏸️ | 搁置 / 放弃（附原因） |
| P0 | 阻塞日常业务，优先做 |
| P1 | 重要但不阻塞 |
| P2 | 优化 / 体验类，有空再做 |

---

## 模块进度速查

| 状态 | 模块 | 版本 | 作用 |
|------|------|------|------|
| ✅ | `sale_order_no` | 19.0.1.7.0 | 销售订单/报价单自定义编号（客户编码+年份+流水号），含 PDF 文件名与门户预览定制 |
| ✅ | `product_model` | 19.0.1.0.0 | 产品多型号 + 可搜索（T-002），目标环境已验证 |
| ✅ | `image_uploader` | 19.0.1.0.0 | 图片粘贴 / 拖拽上传，即时预览 + 进度条，一次多图，超大图报错（T-003，已验证） |
| 🚧 | `product_multi_image` | 19.0.1.0.0 | 产品多图图库（T-004），待目标环境验证 |
| 🚧 | `web_multi_tabs` | 19.0.1.0.0 | 后台多标签页，未迁移按需（T-005） |


---

## 进行中

（空）

---

## 待办池

### T-005 ｜ 仓库规整 ｜ P2 ｜ 统一模块工程规范

- [ ] 决定是否统一模块命名前缀（现有模块为 `sale_order_no` / `image_uploader` / `web_multi_tabs`，风格不一致）
- [ ] 决定是否迁移 `web_multi_tabs`（多标签页，与进销存主流程无关，按需）
- [ ] 统一各模块 `README.md` / `CHANGELOG.md` / 模块级 `AGENTS.md` 模板

---

## 已完成

### T-001 ｜ `sale_order_no` ｜ P0 ｜ 自定义销售订单号（迁移 + 改良）

- 完成日期：2026-09-02
- 落地版本：`19.0.1.7.0`
- 功能：销售订单/报价单自定义编号（`order_no`，客户编码+两位年份+年度流水），含客户编码格式校验、报表正文替换、PDF 文件名定制（三个报表动作）、客户门户预览定制、批量补号
- 验证状态：目标环境已验证 PDF 文件名（中英文界面）、门户预览、编号生成、唯一校验均正常
- 依赖：`sale`、`sale_pdf_quote_builder`（Odoo 19 企业版标准模块）
- 仅支持全新安装（已删除 `migrations/` 目录）

### T-002 ｜ `product_model`（新） ｜ P0 ｜ 产品支持多型号，且支持搜索

- 完成日期：2026-09-02
- 落地版本：`19.0.1.0.0`
- 功能：产品可挂多条型号（客户型号 / 工厂型号 / 别名），独立明细模型 + One2many；
  冗余可存储字段 `model_code_index`（trigram 索引）保证数据库层搜索；
  `_search_display_name` 让 Many2one 下拉 / 搜索建议 / 快速搜索命中型号；
  `web_search_read` 在列表命中型号时附加「（命中型号：xxx）」提示；
  同产品去重（`@api.constrains` + `UNIQUE` 兜底）；删除产品级联清理。
- 验收标准（全部通过）：
  - [x] 产品表单可增/删/改/排序型号行
  - [x] 产品列表搜索框输入型号可命中对应产品
  - [x] 销售订单行选产品（Many2one 搜索）输入型号可命中
  - [x] 型号批量录入（粘贴多行）可用
  - [x] 删除产品时型号行级联清理，无孤儿数据
- 验证状态：目标环境已验证上述五项验收标准全部通过
- 依赖：`product`（最小化，不依赖 `sale`）
- 仅支持全新安装（首次安装自动建 `product.model.code` 表与 `model_code_index` 列及索引）
- 异常情况与处理：
  - 历史产品无型号时 `model_code_index` 为空，搜索框输入型号不命中（预期行为，不影响原生按 name/default_code/barcode 搜索）
  - 同产品重复型号：应用层 `@api.constrains` 阻止并中文提示，DB 层 `UNIQUE` 兜底并发与批量导入
  - 不同产品间同型号：允许，列表 `name` 附加「命中型号：xxx」以区分归属
  - `model_code_index` 与型号行不一致时（手工改库等）：在 shell 执行
    `env['product.model.code'].search([])._sync_template_index()` 重建
- 后续维护：
  - 改变型号拼接分隔符只改 `_sync_template_index`（当前用 `\n`），改后需触发一次同步
  - 新增型号类型只改 `model_type` 的 `selection`，无需改搜索逻辑
  - 让型号出现在其他单据的 Many2one 下拉无需额外改动，只要指向 `product.template`
- 文档同步：`__manifest__.py`、`CHANGELOG.md`、`AGENTS.md`、`README.md`、根 `TODO.md`/`README.md`/`AGENTS.md`

### T-003 ｜ `image_uploader` ｜ P1 ｜ 图片支持粘贴上传（迁移 + 增强）

- 完成日期：2026-09-02
- 落地版本：`19.0.1.0.0`
- 功能：后台图片字段（`ImageField`）在编辑态获得焦点后，`Ctrl+V` / `Cmd+V` 可直接粘贴剪贴板图片上传，
  **粘贴后缩略图立即显示**（本地 base64 预览，无需等服务器），上传中叠加**进度条遮罩**
  （半透明黑底 + 旋转 spinner + 「上传中…」文字），后台 webp 转换 / 多尺寸附件生成完成后自动消失；
  支持拖拽图片文件到图片区域上传（拖拽时容器高亮提示）；一次粘贴 / 拖拽可上传多张图片；
  超过服务器 `max_file_upload_size` 的图片给出中文报错带出具体大小；
  只读态不触发上传；剪贴板无图片时不拦截普通文本粘贴；
  复用 Odoo 原生上传链路（`getDataURLFromFile` → `onFileUploaded` / `onUploaded`），不改核心模板文件。
- 实现方式：历史备份目录不可用，基于 Odoo 19 原生 `FileUploader` / `ImageField` 组件重新实现并增强
  （纯前端模块，仅依赖 `web`，无 Python 模型 / 数据文件 / `security/` 目录）
- 验收标准（全部通过）：
  - [x] 图片区域获得焦点后 `Ctrl+V` 可直接上传，效果与点选文件一致
  - [x] **粘贴后缩略图立即显示**（本地 base64 预览），无"无反应"空窗期
  - [x] **上传中缩略图叠加进度条遮罩**（spinner + 「上传中…」），完成后消失
  - [x] 剪贴板无图片时不拦截普通文本粘贴
  - [x] 只读态不触发上传
  - [x] 拖拽图片文件到图片区域可上传，容器高亮提示
  - [x] 一次粘贴 / 拖拽多张图片逐张处理
  - [x] 超大图弹出中文报错，带出具体大小
  - [x] 复用 Odoo 原生上传链路，不改核心模板文件
- 验证状态：目标环境已验证上述九项验收标准全部通过
- 依赖：`web`（最小化，不依赖 `product` / `sale`）
- 仅支持全新安装（纯前端模块，无数据库结构变更，无迁移脚本）
- 异常情况与处理：
  - 粘贴无反应：检查图片区域是否获得焦点（根 `div` 有 `tabindex="0"`），按 `Tab` 切到图片区域后再粘贴
  - 拖拽无高亮：前端资源缓存，`-u image_uploader` 升级后强刷浏览器
  - 多图只保留最后一张：单图字段按原生行为覆盖当前值，属预期；多图场景由 T-004 处理
  - 超大图报错：由原生 `checkFileSize` 触发，阈值取自 `session.max_file_upload_size`（默认 128 MB）
- 后续维护：
  - 让多图控件（如 T-004 `product_multi_image`）支持粘贴新增：本模块已 patch `FileUploader`，
    任何使用 `FileUploader` 的控件自动获得粘贴能力；若多图控件自定义组件，需在其根元素挂
    `t-on-paste` 并调用该组件的「新增一条图片记录」入口
  - 调整接受的图片 MIME 类型：改 `DEFAULT_ACCEPTED_IMAGE_TYPES` 或视图层给 `ImageField`
    传 `accepted_file_extensions` 选项（原生支持）
  - 压缩超大图（而非报错）：在 `fileToUploadInfo` 加 canvas 压缩逻辑，参考原生 `resizeBlobImg`
    （`web/static/src/core/utils/files.js`）
- 文档同步：`__manifest__.py`、`CHANGELOG.md`、`AGENTS.md`、`README.md`、根 `TODO.md`/`README.md`/`AGENTS.md`

### T-004 ｜ `product_multi_image`（新） ｜ P1 ｜ 产品多图图库

- 完成日期：2026-09-02（代码完成，待目标环境验证）
- 落地版本：`19.0.1.0.0`
- 功能：产品图库，多图并存、拖拽排序、首图即主图、图库内粘贴即新增
  - 新建 `product.image.gallery` 明细模型，继承 `image.mixin` 复用多尺寸（1920/1024/512/256/128）与 webp 转换
  - 模型名刻意避开 `website_sale` 的 `product.image`，仅依赖 `product`，避免与 eCommerce 冲突
  - 扩展 `product.template`：`One2many` 挂图库行、`image_gallery_count` 计算字段
  - 首图（排序最前，id 兜底）自动同步到产品主图 `image_1920`，保留与原生主图关系；`is_main` 自动判定
  - 同一产品内图片名称不可重复：`@api.constrains` 中文提示
  - 图库区域粘贴图片即新增一条记录（patch `X2ManyField`，仅对 comodel 为 `product.image.gallery` 生效，联动 T-003）
  - 产品表单「常规信息」页之后新增「图库」页；产品列表新增「图片数」列；图库独立列表/表单/搜索视图与动作
  - 图片行 `ondelete='cascade'`，删除产品时无孤儿数据
- 验收标准：
  - [ ] 产品表单内可查看/新增/删除多张图片
  - [ ] 支持拖拽排序，可指定主图（首图）
  - [ ] 图库内粘贴图片即新增一条记录
  - [ ] 产品列表/看板展示主图
  - [ ] 报价单、销售订单行可引用产品图片（此项可后置）
- 验证状态：待目标环境验证（已附待验证清单，见模块 `CHANGELOG.md`）
- 依赖：`product`（最小化，不依赖 `sale` / `website_sale`）；粘贴新增需配合 `image_uploader`（T-003）
- 仅支持全新安装（首次安装自动建 `product.image.gallery` 表与 `product.template.image_gallery_ids` 列）
- 异常情况与处理：
  - 图库为空：产品主图 `image_1920` 被清空，避免残留陈旧主图（预期行为）
  - 历史产品无图库：`image_gallery_ids` 为空，不影响原生主图字段使用
  - 同一产品重复图片名称：`@api.constrains` 阻止并中文提示带出具体值与产品名
  - 粘贴无反应：检查图库区域是否获得焦点（根 div 有 `tabindex="0"`），按 `Tab` 切到图库区域后再粘贴
  - 粘贴新增失效：前端资源缓存，`-u product_multi_image` 升级后强刷浏览器
  - `is_main` 未刷新：检查 `@api.depends` 是否覆盖触发字段
- 后续维护：
  - 改变首图判定规则只改 `_compute_is_main` 与 `_get_main_image`，改后触发一次重算
  - 让其他模型支持图库粘贴新增：patch `X2ManyField` 的 `isImageGallery` 判断扩展 comodel 白名单
  - 与 `website_sale` 共存：模型名不同，互不干扰；若要复用其 `product.image`（含视频），另写桥接模块
- 文档同步：`__manifest__.py`、`CHANGELOG.md`、`AGENTS.md`、`README.md`、根 `TODO.md`/`README.md`/`AGENTS.md`

---

（空）
