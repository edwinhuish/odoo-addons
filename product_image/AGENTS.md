# AGENTS 工作指引

> 本文档用于指导 AI 助手或新开发者在维护、扩展本 Odoo 模块时的行为规范和关键上下文。

---

## 模块定位

- 模块名：`产品图片`（显示名）
- 技术目录 / 模块技术名：`product_image`（原名 `product_multi_image`，于 19.0.2.0.0 改名）
- 新建模型：`product.image.gallery`（模型名保持不变，避免与 `website_sale` 的 `product.image` 冲突）
- 继承模型：`product.template`
- 自定义 widget：`product_image_gallery`（registry key 不变，替换产品表单原生 `image_1920` 字段 widget）
- 自定义预览组件：`ProductImagePreviewDialog`（全屏预览，放大/缩小/旋转）
- 自定义图片管理弹窗：`ProductImageManageDialog`（点击「+」打开：上半部分大图（仅预览、无删除按钮；选中主图时名称行留空）+ 平铺缩略图（每张缩略图含主图右上角 ×——先确认后删除，删图库图删记录，删主图自动提升图库首张；缩略图可拖动排序、主图固定首位；点击缩略图只切弹窗大图；布局：大图列固定尺寸、缩略图占满剩余宽高并超高滚动），下半部分上传 dropzone（点击/拖放/Ctrl+V，上传中缩略图 + 动画，粘贴不自动关闭，上传不改变页面大图）；header「批量删除」勾选模式 + 批量确认（含缩略图清单）；走 `main_components` 注册表顶层 overlay）
- 主依赖：`product`（最小化，不依赖 `sale` / `website_sale` / `web_image_paste`）
- 当前版本：`19.0.2.4.2`（管理弹窗拖动排序（含主图，首位即主图）/ 删除确认 / 批量删除；`19.0.2.4.1` 调整确认框按钮顺序（取消置右），`19.0.2.4.2` 关闭按钮贴齐最右侧（去掉 `pe-1`）；`19.0.2.3.1` 修复拖动跟手与 XML `&nbsp;` 实体崩溃，`19.0.2.3.2` 修复拖拽布局（`position-relative !important` 覆盖），`19.0.2.4.0` 修复勾选模式无操作按钮（`<template t-if>` → `<t t-if>`）；`19.0.2.2.10~2.2.15` 布局与弹窗改动同批待验证）

---

## L1：不可破坏的核心约束

每次修改代码必须保证以下行为不变。

1. **在原有图片位置支持多图，禁止新增页签**
   - 产品表单头像区域 `image_1920` 字段 widget 改为 `product_image_gallery`
   - 同一位置渲染主图 + 右侧缩略图列，不新增「图库」页、不增加导航层级

2. **图片用独立明细模型，禁止塞进产品主图字段做多图**
   - `product.image.gallery` + `One2many` 挂在 `product.template` 上
   - 产品主图 `image_1920` 只是首图的同步镜像，不是图库本体

3. **模型名避开 `product.image`，禁止与 `website_sale` 共用模型**
   - 用 `product.image.gallery`，使本模块可在不依赖 eCommerce 的环境独立安装
   - 若日后与 `website_sale` 共存，两者模型互不干扰
   - **注意**：模块技术名虽为 `product_image`，但模型名是 `product.image.gallery`，二者不必一致

4. **主图与图库解耦；大图预览区无删除按钮，删除入口只在缩略图网格（含主图项：删主图自动提升图库首张）**
   - 产品主图 `image_1920` 由原生字段独立管理，列表 / 看板 / 报价单展示它
   - 图库 `product.image.gallery` 只存补充图，**后端不反向同步 / 不覆盖 / 不清空**产品主图
   - 已移除 `_sync_main_image_from_template`、`is_main`、`_get_main_image`、gallery 的 create/write/unlink override
   - 前端展示序列 = [原生主图（若有）] + [图库图片按 `sequence` 升序]，主图永远在第一位（无角标，靠首位隐含）
   - 头像区缩略图列**只用于选中/切换，不承载删除按钮**；「图片管理」弹窗（点击缩略图列末端「+」打开）中**大图预览区不提供删除按钮**（任何图片），删除入口只在**缩略图网格**——每张缩略图（含主图）右上角 ×：图库图删除记录，主图删除自动提升图库首张（`onMainRemove`）；大图列固定宽度与行高（名称单行、提示固定行高），缩略图网格占满剩余宽高并超高滚动——弹窗尺寸不随图片切换 / 数量变化
   - **可拖动排序的缩略图禁止使用 Bootstrap 的 `.position-relative` 工具类**：该工具类定义为 `position: relative !important`，会压过排序态 `.is-sorting .o_gallery_manage-tile { position: absolute }`，使 tile 不脱离流内、`transform` 叠加在流内位置之上（巨大间隙 + 横向滚动条 + 拖拽块不跟手）。常态定位必须写在模块 SCSS 的 `.o_gallery_manage-tile { position: relative; }`（无 `!important`）；同理，若要覆盖任何 Bootstrap 工具类，必须确认其是否带 `!important`，不能只靠选择器优先级
   - 管理弹窗操作增强（19.0.2.3.0 起，19.0.2.4.0 放开主图）：缩略图可**拖动排序**（含主图，至少 2 张图即可拖），拖动时其余缩略图按位次平滑避让（网格切为绝对定位 + transform 过渡），松手先落位动画再提交，写回走「统一数组 diff」：前端把主图 + 图库视为同一个数组（`displayItems` / `displayKeys`，顺序 = 下标），拖动后 `onManageReorder(after)` 与拖动前的 `displayKeys` diff——**序列首位即主图**，首位仍是 `main` 时只重排图库 `sequence`；首位是图库图且有主图时 `_writeOrderWithNewMain()` 把它提升为主图（数据写入 `image_1920` + 删除该图库记录），并**先读原主图 base64 再覆盖主图字段**、把原主图按其在新数组中的下标落位新建为图库记录（移动，不复制）；无主图时只重排图库、不造主图；顺序写回统一由 `_writeGalleryOrder()` 按 diff 完成——**只写位置真的变了的图库记录**（未变动的不产生写操作）；上传追加图库时显式写 `sequence = 当前最大 + 10`，保证重排后新增仍排末尾；**任何删除前先确认**（确认框含该图缩略图，主图提示“图库首张自动提升 / 图库空则清空”）——单张点右上角 ×、或 header「批量删除」进入勾选模式（缩略图左上角勾选圈，header 显示已选数量 + 删除 / 取消）后批量删除，批量确认框列出全部所选缩略图（主图带「主图」标签）；删除顺序**先图库后主图**（先删主图会触发提升、打乱剩余图库 key 定位）；**选中主图时大图名称行留空**（固定行高占位，不显示“主图”）
   - 选中缩略图用 wrap 的真实 border（默认透明占位，选中蓝色）一圈显示，避免被滚动容器 `overflow` 裁切左右
   - **上传时主图为空** → 上传图直接写 `image_1920`（成为首位主图）；主图已有值 → 追加为图库记录（不影响主图）
   - 「图片管理」弹窗走顶层 `main_components` overlay（`useProductImageManage` hook，与 gallery 渲染树解耦）：上半部分大图预览 + 平铺缩略图网格（仅图库项右上角 × 删除，按 type/key 分派），点击缩略图**只切换弹窗内大图预览、不回传 widget**（19.0.2.2.14 起不影响页面主图）；下半部分上传 dropzone（点击 / 拖放 / Ctrl+V）——**弃用 `web.FileUploader`**（仅有整体 `isUploading` 布尔态、上传时隐藏触发区，无法逐张反馈缩略图 + 动画），自实现文件选择与上传队列（每张图 `objectURL` 本地缩略图 + 转圈动画，读文件用原生 `getDataURLFromFile`、校验用原生 `checkFileSize`、写入走 `onFileUploaded`）；Ctrl+V 粘贴上传**不自动关闭**；关闭按钮为 header 右上角**正方形 × 按钮**（无文字、占满 header 高度、hover 背景变红 #dc3545，见 SCSS `.modal-header .o_gallery_manage-close`）；网格与「+」占位符无 `title` tooltip
   - **上传不改变页面展示**（19.0.2.2.15 起，点击 / 拖放 / Ctrl+V 皆然）：`onFileUploaded` 写记录前后不把页面 currentIndex 切到新图——上传前记录当前展示项的稳定 key（`_itemKey`：主图固定 `main`、图库 `g<记录 id>`），写完后按 key 在最新展示序列中重定位（主图为空上传会把新主图前插到首位、原图库项索引后移，用 key 才能锚定到同一张图）；新增项索引仍返回给弹窗做内部高亮（弹窗状态，不影响页面）
   - 保留 `onManageDelete('main')` / `onMainRemove` 防御性实现（图库非空时把首张图数据移动为 `image_1920`；binary size 经 ORM `read` 取真实 base64 再写主图），当前 UI 不触发

5. **`is_main` / 首图概念已移除**
   - 主图独立后图库不再有「首图即主图」语义，`is_main` 字段、`_compute_is_main`、`_get_main_image` 均已删除
   - 图库图片按 `sequence` 排序仅用于缩略图展示顺序（主图始终在最前）

6. **浏览切换为纯前端状态，禁止切换即写库**
   - widget 用 `state.currentIndex` 维护当前选中图，切换不触发 `record.update`
   - 只有上传 / 删除（写主图字段或删图库记录）才触发 `record.update` / One2many record 操作
   - 悬浮放大、点击预览、复制图片均为只读行为，不写库（只读态也允许）

7. **预览弹窗不全局 patch `web.FileViewer`，禁止影响其他附件预览**
   - 用模块内置 `ProductImagePreviewDialog` 独立组件实现放大/缩小/旋转
   - 不再提供「复制到剪贴板」功能（已于 19.0.2.0.2 移除）

8. **同一产品内图片名称不可重复**
   - `@api.constrains("name", "product_tmpl_id")` 中文提示带出具体值与产品名
   - 名称非必填，但若填了则同产品内唯一

9. **删除产品级联清理图片**
   - `product_tmpl_id` 的 `ondelete='cascade'`，禁止改成 `set null` 或 `restrict`

10. **Odoo 19 API 事实**
    - `image.mixin` 提供 `image_1920` + related 的 1024/512/256/128，继承即得
    - `name_get()` / `name_search()` 已移除，图库不需要自定义显示名
    - `_sql_constraints` 已废弃，用 `models.Constraint`（本模块当前未用 DB 约束，名称唯一仅应用层）
    - 自定义 widget 通过 `registry.category("fields").add` 注册，`fieldDependencies` 声明依赖字段
    - QWeb 模板内**不要**调用 `_t(...)`：翻译由构建期从 XML 字面量（`title=` / `aria-label=` / 元素文本）抽取，动态文案请在 JS 侧用 getter 返回 `_t(...)`

---

## 文件职责

| 文件 | 职责 |
|------|------|
| `__manifest__.py` | 模块元数据、依赖、数据文件声明、前端资源登记 |
| `models/product_image.py` | 图片明细模型：字段、名称去重、级联（与主图解耦，无同步） |
| `models/product_template.py` | 扩展 `product.template`：One2many、图片数量（无主图同步入口） |
| `views/product_template_views.xml` | 产品表单头像字段 widget 改为 `product_image_gallery`、列表图片数列 |
| `views/product_image_views.xml` | 图库独立列表/表单/搜索视图与动作 |
| `static/src/js/product_image_gallery.js` | `product_image_gallery` widget：主图 2 倍 / 悬浮局部放大（放大镜跟随鼠标）/ 点击预览入口 / 展示序列（主图+图库）/ 右侧缩略图（选中切换·滚动·「+」开管理弹窗·选中蓝边框）/ 管理弹窗回调（列表快照 getItems / 删除按 type+key 分派——图库 key 为 `g<id>` 需解析后定位 / 拖动排序 onReorder 按 10 步长写 sequence / 上传写入主图或追加图库且按稳定 key 锚定页面展示不上跳新图） |
| `static/src/xml/product_image_gallery.xml` | widget QWeb 模板：主图 + 悬浮浮层 + 右侧缩略图列（无删除按钮）+ 预览弹窗 |
| `static/src/js/product_image_preview.js` | `ProductImagePreviewDialog`：全屏预览，放大/缩小/旋转 |
| `static/src/xml/product_image_preview.xml` | 预览弹窗 QWeb 模板 |
| `static/src/js/product_image_manage.js` | `ProductImageManageDialog` + `useProductImageManage` hook：图片管理弹窗（顶层 overlay 走 main_components），上半大图（仅预览、无删除按钮；主图选中名称行留空）+ 平铺缩略图（拖动排序：pointer 拖拽 + hole 插入位 + transform 避让动画、主图固定首位；删除入口只在网格：每张缩略图含主图 ×，先确认后删，删主图自动提升；点击缩略图只切换弹窗内大图，不回传 widget）；header「批量删除」勾选模式 + 批量确认（先图库后主图）；下半 dropzone + 自实现上传队列（点击/拖放/Ctrl+V，缩略图 + 转圈动画，粘贴不自动关闭）；通过 getItems/onDelete/onReorder/onUploaded 回调与 widget 同步 |
| `static/src/xml/product_image_manage.xml` | 图片管理弹窗 QWeb 模板 |
| `static/src/scss/product_image_gallery.scss` | widget 与预览弹窗样式（主图棋盘格背景 / 缩略图选中 / 滚动条隐藏 / 工具条 / 管理弹窗样式） |
| `security/ir.model.access.csv` | 普通用户读写业务数据，销售经理可配置 |

---

## 常见扩展场景

### 调整 widget 渲染

改 `static/src/js/product_image_gallery.js` 与 `static/src/xml/product_image_gallery.xml`：
- 主图尺寸：模板内联 `style="width: 180px; height: 180px"`（同时改 SCSS 中主图背景棋盘格）
- 缩略图尺寸：模板内联 `style="width: 56px; height: 56px"`
- 悬浮放大尺寸：`onHoverEnter` 中 `DESIRED`（窗口 540）与 `IMG`（图片 1080，固定）；实际窗口存 `state.hoverWin`（屏幕不足时按比例缩小，下限 160），`hoverStyle` / `zoomImgStyle` / `onHoverMove` 均读 `state.hoverWin` / `hoverImg`，蓝色选框边长 = 原图宽 × (win/img) 动态计算
- 缩略图滚动步长：`onThumbScrollUp/Down` 的 `scrollBy` 比例

### 调整预览弹窗

改 `static/src/js/product_image_preview.js` 与 `static/src/xml/product_image_preview.xml`：
- 缩放步长 / 最小缩放：`zoomStep` / `scrollZoomStep` / `minScale`

### 复用原生 webp 转换链路

当前 widget 直接写原图 base64 到图库记录，多尺寸由 `image.mixin` related 字段自动生成。
如需报告用 webp/JPEG 附件（对应原生 `ImageField.onFileUploaded` 的 canvas 逻辑），
可在 `onFileUploaded` 内调用原生 `ImageField` 的 canvas 处理后写入。

### 改变图库排序规则

**前端是统一数组、后端是分开存储**：`displayItems` / `displayKeys` 把「主图 + 图库」合成一个数组
（顺序 = 数组下标，主图恒为下标 0）；后端则是产品 `image_1920` 字段 + `product.image.gallery` 的 `sequence`。
因此排序写回统一走「数组 diff」：`gallery.onManageReorder(after)`
（19.0.2.3.0 起，19.0.2.4.0 起含主图）先取拖动前的 `displayKeys` 作为 before，与 after 比对——
长度不一致（期间有增删）直接放弃；首位仍是 `main` 时只重排图库；首位是图库图且有主图时走
`_writeOrderWithNewMain()` 更换主图（提升该图为主图 + 原主图按其在新数组中的下标落位为图库记录）。
图库顺序统一由 `_writeGalleryOrder(galleryKeys)` 按 10 步长写入，**只写 sequence 真的变了的记录**。
上传追加时显式写「当前最大 sequence + 10」，避免重排后新图默认 10 插到中间。
改展示排序逻辑只改 `product.image.gallery` 的 `_order`、widget `galleryRecords` getter 的排序与
`onManageReorder` / `_writeGalleryOrder`；**更换主图是移动语义**（提升的图库记录被删除、
原主图新建为图库记录），图片不会重复，也不会凭空产生 / 丢失主图。

### 与 `website_sale` 共存

本模块用 `product.image.gallery` 模型名，与 `website_sale` 的 `product.image` 互不干扰。
若希望复用 `website_sale` 的 `product.image`（含视频），需另写桥接模块，不要改本模块模型名。

---

## 调试建议

- 头像区域仍显示单图：检查 widget 是否生效，`-u product_image` 升级后强刷浏览器
- 主图没放大：检查 SCSS 是否加载（`-u` 升级），主图尺寸由模板内联 style 控制
- 悬浮放大位置错乱：检查 `onHoverEnter` 的 `getBoundingClientRect` 计算与 `hoverStyle` getter
- 缩略图不滚动：检查 `.o_gallery_thumb_scroll` 的 `flex:1 1 auto; min-height:0; overflow-y:auto`
- 上传后未新增：检查 `galleryList.addNewRecord` 是否成功，看控制台报错
- 主图不在序列首位：主图有值时 widget `displayItems` 第一项即主图；若主图项缺失，检查 `hasMainImage`（`props.record.data[image_1920]`）是否有值
- 删除按钮位置与条件：缩略图网格内**每张缩略图（含主图）**渲染 `.o_gallery_manage-del`（无 type 条件）；大图预览区模板无删除按钮（19.0.2.2.15 起只作预览）。删除主图应走 `onManageDelete('main')` → `onMainRemove`（图库首张自动提升 / 图库空则清空），不要直接清主图字段。删除前都会先弹确认框（点 × 或批量），确认框打不开 / 没有缩略图：检查 `state.confirm.items` 是否有 `thumbUrl` 与 XML 确认框 overlay
- 拖动排序异常：网格未进入 `.is-sorting`（绝对定位 + transform）：检查指针事件是否被 × / 勾选圈拦截、主图项（`type==='main'`）不参与、图库需 ≥2 张；顺序保存后未生效：检查 `onReorder` 是否传入（manage props）以及 `gallery.onManageReorder` 写的 `sequence` 是否随产品保存（拖动只改 child record，需保存产品）；排序后新上传位置不对：检查 `onFileUploaded` 是否写 `sequence = 当前最大 + 10`
- Ctrl+V 粘贴无反应：粘贴在「图片管理」弹窗下半部 dropzone——先点「+」打开弹窗，弹窗获焦后再 Ctrl+V（上传后不自动关闭，可继续粘贴）；头像区域不再直接响应粘贴
- 选中缩略图无蓝框：检查 `.o_gallery_thumb_wrap.is-active` 的 `border-color: #0d6efd` 是否加载（`-u` 升级后强刷）；预览内缩略图选中用 `.o_preview_thumb.is-active` 的 `outline-color`
- 头像区缩略图列滚动突出 / 无法贴边：确认 `.o_gallery_thumb_scroll` **无 padding 也无负 margin**（内容盒 = 列内布局占位，行可贴顶/贴底滚动；`margin:-6px` 曾使可视区越出盒体导致滚动越界突出，`padding:6px` 又使首/末行无法贴边）、`.o_gallery_thumbs` / `.o_product_image_gallery` 为 `overflow: visible`；头像区缩略图列**已无删除按钮**（删除在管理弹窗网格内，`.o_gallery_manage-del` 凸出右上角，由 `.o_gallery_manage-grid` 的 padding 吸收，无负 margin）
- 看板无主图：产品主图 `image_1920` 为空时看板无图；主图独立，需直接上传/设置主图字段

---

## 变更记录规范

每次功能修改后必须更新：
- `__manifest__.py` 的 `version`（遵循 `19.0.x.y.z`）
- `CHANGELOG.md` 的版本说明（变更 / 影响 / 文档）
- 本 `AGENTS.md` 的相关约束（若涉及行为变更）
- `README.md` 的功能说明（若涉及用户可见功能）

版本号建议：
- 破坏性变更或架构调整：升第二位，如 `19.0.3.0.0`
- 功能新增：升第三位，如 `19.0.2.1.0`
- 修复或文档：升第四位，如 `19.0.2.0.1`

---

## 开发复盘与关键经验（T-004）

> 2026-09-04 验证通过，落地 `19.0.2.2.7`。以下记录供后续类似前端交互模块复用。

### 功能实现要点

- **主图与图库解耦**：`product.image.gallery` 仅存补充图，后端不反向同步主图 `image_1920`；展示序列在 widget 端拼 `[原生主图] + [图库按 sequence]`，主图恒在首位（无角标）。删主图时由 widget 主动把图库首张数据移动到主图字段（提升，非复制）。
- **继承 `image.mixin` 复用多尺寸**：图库记录写一次 base64，1920/1024/512/256/128 由 related 字段自动生成，无需自建缩放链路。
- **悬浮放大镜**：固定 1080 图在 540 窗口内 `transform: translate` 平移，鼠标点居中；窗口/图比例驱动蓝色选框尺寸，保证选框与预览内容一一对应。位置级联：左 → 下 → 按比例缩小适配屏幕。
- **全屏预览**：`translate3d` + `will-change:transform` 走 GPU 合成层、移除 transform 过渡实现 1:1 顺滑拖拽；每图独立状态缓存（scale/angle/translate/loaded），切换再切回不重置；body 滚动锁定消除页面滚动条。
- **图片管理弹窗顶层 overlay**：走 `main_components` 注册表，与 gallery 渲染树解耦，避免 gallery 重渲染闪烁；弹窗通过 `getItems` / `onDelete` / `onUploaded` 回调操作记录，删除 / 上传后由 widget 重新生成列表快照，弹窗不重建即同步；弹窗内「选中切换」是弹窗自身状态、不回传 widget（19.0.2.2.14 起点缩略图不影响页面主图）；上传自实现队列逐张显示本地缩略图 + 动画；Ctrl+V 粘贴上传后不自动关闭（19.0.2.2.12 起 widget 头像缩略图列不再放删除按钮，删除统一收进该弹窗；19.0.2.2.15 起大图预览区不提供删除按钮，删除入口在缩略图网格——每张缩略图（含主图）右上角 ×，删除主图经 `onManageDelete('main')` 自动提升图库首张；上半区布局恒定——大图列固定尺寸（名称单行 + 提示固定行高）、缩略图网格绝对定位占满剩余宽高并超高滚动，图片切换 / 增减均不改变弹窗高度；上传不切换页面展示——widget 上传前记录当前展示项稳定 key，写记录后按 key 锚定回原图）。19.0.2.3.0 起弹窗支持：缩略图拖动排序——pointer 拖拽 + hole 插入位 + 其余图块 transform 过渡形成避让动画（主图固定首位不参与），落位动画后提交，`gallery.onManageReorder` 把 keys 按 10 步长写回图库 `sequence`（新增图库显式 `sequence = 当前最大 + 10` 追加末尾）；删除统一确认——单张 × 与 header「批量删除」（勾选模式 + 已选计数）均先弹含缩略图清单的确认框，主图带「主图」标签与自动提升提示，删除按“先图库、后主图”顺序（先删主图会触发提升打乱剩余图库 key）；大图选中主图时名称行留空（固定行高保持布局稳定）。19.0.2.3.1 修复拖动体验：拖动中每次 `pointermove` 重建 drag 对象逐帧渲染、拖拽块自身 `transition: none`（松手瞬间加 `o_gm-snap` 类恢复过渡做落位动画）实现 1:1 跟手；排序占位高度精确等于原 flex 布局（去掉多算的 2px），避免临界溢出闪滚动条引发列数重排跳变；`availY` 改为只扣块尺寸使块可拖到内容底，坐标原点计入 grid border 消除 1px 偏差。19.0.2.3.2 修复拖拽布局根因：缩略图去掉 Bootstrap `.position-relative`（其 `!important` 压过排序态 `absolute`，transform 叠加在流内位置之上），常态定位改由 SCSS 的 `.o_gallery_manage-tile { position: relative; }` 提供；网格加 `overflow-x: hidden` 杜绝横向滚动条；排序首帧用 `is-sorting-init` 禁用 tile 过渡（避免全部从左上角飞入），`onPatched` 后切 `move` 阶段恢复避让动画；拖拽定位改为保持按下时的抓取点偏移（`grabX/grabY`），块随鼠标 1:1 移动、抓取瞬间不跳位。

### 遇到的问题及解决方案

1. **缩略图删除按钮被裁切 / 缩略图滚动突出 / 内容无法贴边（→ 19.0.2.2.12 头像列删除按钮收敛进管理弹窗）**
   - 现象：右上角红色 × 显示不完整；滚动时缩略图“突出”到上下滚动按钮与列边界之外；移除负 margin 后内容又无法与 180px 区顶 / 底贴边对齐。
   - 根因：`.o_gallery_thumb_scroll` 的 `overflow-y:auto` 使 `overflow-x` 计算为 `auto`（CSS 规范），水平方向会裁切；× 若悬挂在缩略图外侧（`top/right:-5px`），超出滚动可视区即被切掉。曾用 `margin:-6px` 抵消 `padding:6px` 让内容贴边，滚动可视区因此越出其在列内的布局占位，滚动时缩略图“突出”；只去掉 margin、保留 padding 则内容内缩，首 / 末行无法与 180px 区域顶 / 底对齐。
   - 头像区终解（19.0.2.2.7~2.2.11）：`.o_gallery_thumbs` / 根容器显式 `overflow: visible`；滚动容器**不加 padding、不加 margin**（内容盒 = 布局占位，行可贴顶 / 贴底滚动，不越界）；× 放缩略图**内侧角标** 才完整可见。
   - **19.0.2.2.12 迁移**：头像区缩略图列**整体移除删除按钮**（只用于选中切换），删除统一收进「图片管理」弹窗——弹窗下半 dropzone 之外，上半缩略图网格内的 `.o_gallery_manage-del` 凸出缩略图右上角，由 `.o_gallery_manage-grid` 自身 `padding` 吸收出血（仍无负 margin）；大图预览角标因预览盒 `overflow:hidden`，用内侧定位（根作用域默认 `top/right:4px`，网格内覆盖为 `-6px`）。
   - **几何结论**：行要贴齐滚动区上缘，按钮就不能画在行上方——「× 悬挂行外侧」与「贴边」不可兼得；要么按钮放内侧，要么按钮所在容器自带 padding 吸收出血（该容器内容是否贴边另说）。
   - **经验**：`overflow-y:auto` 会隐式让 `overflow-x` 变 `auto`（非 visible），凡是「子元素负偏移伸出滚动容器」的角标/badge 都会被裁；**负 margin 让滚动可视区越出盒体会导致滚动越界“突出”，padding 又让内容无法贴边**。若某容器既要贴边滚动又要放删除角标，角标只能放内侧，或（像管理弹窗网格一样）把删除按钮放到一个自带 padding 的容器里。
2. **预览图片消失（放大/缩小/旋转后）**
   - 根因：`t-att-style` 重渲染时把 `opacity` 重置回 0。
   - 终解：把 `opacity` 并入 `imageStyle` getter 一起返回，避免被覆盖。
3. **预览 Y 轴滚动条**
   - 根因：自定义全屏 modal 未触发 Odoo 的 `modal-open`（body 未锁）。
   - 终解：`onMounted` 锁 `document.body.style.overflow='hidden'`，`onWillUnmount` 恢复；根容器再 `overflow:hidden` 兜底。
4. **拖拽不顺滑**
   - 根因：zoomer 上 `transition: transform 0.05s` 让每次 mousemove 都被缓动滞后。
   - 终解：移除该过渡 + `translate3d` + `will-change:transform` 走 GPU，1:1 跟手。
5. **切换图片重置状态**
   - 终解：`imageStates` 缓存每图 `{scale,angle,x,y,loaded}`，切换前存、切回时恢复，已加载标记避免闪屏。
6. **QWeb 模板内 `_t()` 不生效**
   - 终解：翻译由构建期从 XML 字面量（`title`/`aria-label`/文本）抽取，动态文案在 JS getter 返回 `_t(...)`。

### 接口与字段变更

- **新模型 `product.image.gallery`**：继承 `image.mixin`（`image_1920` + related 1024/512/256/128）；字段 `name`、`sequence`、`product_tmpl_id`（`ondelete='cascade'`）；`_order = 'sequence'`；`@api.constrains("name","product_tmpl_id")` 同产品名称去重。**无 `is_main`**（已移除）。
- **扩展 `product.template`**：`One2many` → `product.image.gallery`、`image_gallery_count` 计数字段。主图 `image_1920` 由原生字段独立管理，无同步入口。
- **widget**：`product_image_gallery`（registry `fields`，替换产品表单 `image_1920` 字段 widget，`fieldDependencies` 声明依赖）；`ProductImagePreviewDialog`（全屏预览）、`ProductImageManageDialog` + `useProductImageManage` hook（顶层 overlay，19.0.2.2.12 替代原 `ProductImageUploadDialog`）。
- **视图**：产品表单头像字段 widget 改 `product_image_gallery`、列表增「图片数」列；图库独立列表/表单/搜索视图与动作。
- **安全**：`security/ir.model.access.csv`，普通用户读写业务数据、销售经理可配置。
- 仅支持全新安装（无迁移脚本）。

### 可复用设计思路

- **「主资源 + 补充资源」解耦模式**：核心字段（主图）由原生独立管理、对外展示用原生；补充资源走独立明细模型，展示序列在 widget 端拼接。若提供删主资源功能，由前端主动提升补充资源首条（移动数据，非复制），避免后端双向同步的复杂度与覆盖风险（本模块 19.0.2.2.14 起 UI 已不提供删主图入口，该提升逻辑保留为防御性实现）。
- **顶层 overlay 弹窗**：交互弹窗走 `main_components` 注册表（而非挂在字段组件树内），与宿主渲染树解耦，避免宿主重渲染导致的闪烁与状态丢失；hook 暴露 `open/close`。
- **悬浮放大镜参数化**：窗口/图分离（图固定大、窗按屏幕缩），选框 = 原图 × (窗/图)，平移量夹在 `[-(图-窗),0]`；一套公式适配任意尺寸与缩小场景。
- **预览弹窗性能套路**：`translate3d` + `will-change` 上 GPU、移除 transform 过渡求 1:1；每视图独立状态缓存避免重复操作丢失；挂 window 级 mousemove/mouseup 保证拖出区域仍能拖/能停。
- **overflow 裁切规避**：角标/badge 类负偏移元素，要么移入容器内侧，要么给滚动容器加同向 padding 吸收溢出，并显式 `overflow:visible` 上层容器。
- **Odoo 19 适配**：`name_get/name_search` 已废、`_sql_constraints` 已废（用 `models.Constraint`）、QWeb 内勿 `_t()`、自定义 widget 走 `registry.category("fields").add` + `fieldDependencies`。

---

## 开发复盘与关键经验（T-005）

> 2026-09-06 完成，落地 `19.0.2.4.2`（本轮批次 `19.0.2.3.0` ~ `19.0.2.4.2`）。以下记录供后续类似「网格拖拽排序 + 弹窗交互」需求复用。

### 本轮优化要点

- **统一数组 + diff 最小写回**：前端把「主图 + 图库」视为同一个数组（`displayItems` / `displayKeys`，顺序即下标），后端仍分开存（产品 `image_1920` 字段 + `product.image.gallery.sequence`）。拖动后 `onManageReorder(after)` 与拖动前的 `displayKeys` 比对：长度不一致即放弃（防并发增删错位）；图库顺序统一由 `_writeGalleryOrder()` 按 10 步长写入，且**逐项与当前 `sequence` 比对，只写位置真的变了的记录**，避免无谓 dirty 与重排抖动。
- **主图可拖动（首位即主图）**：`after[0]` 不是 `main` 且有主图时走 `_writeOrderWithNewMain()`——被拖到首位的图提升为主图（数据写入 `image_1920` + 删除其图库记录），原主图按它在新数组中的下标落位新建为图库记录。**移动语义**，图片不重复、不丢失；无主图时只重排图库、不凭空造主图。
- **拖拽排序几何**：排序态网格切「绝对定位 + `transform`」布局，格距常量 `SORT_CELL = 76`（图块 68 + gap 8），由 hole（插入位）映射其余图块的格位，`transition: transform` 形成避让动画；拖拽块按抓取点偏移跟随指针，松手 snap 到落位单元再提交。
- **删除确认 / 批量删除**：任何删除（单张 × / 批量）先弹含缩略图清单的确认框；批量删除走 header 勾选模式，删除按「先图库、后主图」顺序（先删主图会触发提升、打乱剩余图库 key 定位）。
- **弹窗细节**：大图选中主图时名称行留空（`&#160;` 占位保行高）；确认框底部按钮为「删除」→「取消」（取消在最右）；header 右侧操作区去掉 `pe-1`，关闭按钮与弹窗右缘贴齐。

### 遇到的问题及解决方案（坑点）

1. **`&nbsp;` 让整个后端前端崩溃**
   - 现象：QWeb 模板名称行占位写 `&nbsp;`，浏览器加载 `web.assets_web.bundle.xml` 抛 `Entity 'nbsp' not defined`，随后 `Missing template: web.WebClient`，**整个后台白屏**。
   - 根因：QWeb 模板按 **XML** 解析，XML 只内置 `&amp; &lt; &gt; &quot; &apos;` 五个实体，`&nbsp;` 是 HTML 实体、未定义即报错；又因资源按 bundle 整体编译，一处非法实体会连带整个 bundle 加载失败。
   - 解决：改用 XML 数字实体 `&#160;`（同样是不换行空格）。**经验：QWeb 里一律用数字实体，不要用 HTML 命名实体；改完必须 `-u` 升级并强刷（bundle 有缓存）**。
2. **Bootstrap `.position-relative` 的 `!important` 压过排序态定位（本轮最隐蔽的坑）**
   - 现象：一按下拖动，缩略图之间出现**巨大间隙**、网格冒出**横向滚动条**、拖拽块远离鼠标。
   - 根因：缩略图模板带 Bootstrap 工具类 `position-relative`，其定义为 `position: relative !important`（已核对 `web/static/lib/bootstrap/dist/css/bootstrap.css`），压过 `.is-sorting .o_gallery_manage-tile { position: absolute }`。tile 因此**从未脱离流内**，`transform: translate(col*76, row*76)` 叠加在流内位置之上，偏移随序号累积。
   - 解决：移除该工具类，常态定位改由模块 SCSS 的 `.o_gallery_manage-tile { position: relative; }` 提供（无 `!important`），排序态 `absolute` 才生效。
   - **经验：覆盖任何 Bootstrap 工具类前，先确认它是否带 `!important`；工具类几乎都带，选择器优先级再高也压不过**。
3. **`<template t-if>` 让按钮「凭空消失」**
   - 现象：点「批量删除」进入勾选模式后只剩缩略图勾选圈，「已选 N 张 / 删除 / 取消」全不可见，也不报错。
   - 根因：`<template>` 是 HTML **惰性容器元素**，其内容不会渲染到文档；QWeb 里条件分支必须用 `<t t-if>`。
   - 顺带核实（对照 `web/static/lib/owl/owl.js` 的 `setClass` / `updateClass`）：Owl 的 `t-att-class` 走 `classList.add/remove`，是 **token 级增删**，不会清掉元素静态 `class`——排查时应区分「没渲染」与「class 被覆盖」两类问题。
4. **`overflow-y: auto` 隐式让 `overflow-x` 变 `auto`**
   - 现象：横向越界（哪怕是过渡动画中途）就冒出横向滚动条。
   - 解决：网格显式 `overflow-x: hidden`。**经验：只要容器设了 `overflow-y:auto`，横向就等于可滚动，越界必出条**（与 T-004 坑 1 同源）。
5. **排序占位高度多算 2px → 滚动条闪现 → 列数跳变**
   - 现象：内容「刚好满高」时一进入排序就闪出滚动条，随后整网格重排、间隙错乱。
   - 根因：占位高度写成 `rows*76 - 8 + 2`，比原 flex 内容高 2px → 溢出 2px 出滚动条 → `clientWidth` 变小 → `cols` 变小 → 所有图块重排。
   - 解决：占位高度取**与原 flex 布局完全等高**的 `rows*SORT_CELL - SORT_GAP`（不含 padding，padding 由 grid 自身再加）。
6. **拖拽块不跟手（只在 hole 变化时才动 + 过渡滞后）**
   - 根因：① 原实现只在插入位 `hole` 变化时才重建 `drag` 触发渲染，行内平移时 `floatX/Y` 改了却不渲染；② 拖拽块自身带 `transition: transform 0.16s`，每次位移都被缓动 160ms。
   - 解决：每次 `pointermove` 都重建 `drag` 对象强制逐帧渲染；拖拽块 `transition: none`（1:1 跟手），松手落位时加 `o_gm-snap` 类恢复过渡保留落位动画。
7. **坐标原点漏算边框 / 夹取误扣 padding**
   - 原点：`getBoundingClientRect().left` 是 border box 外缘，内容区起点要再扣 `borderLeftWidth + paddingLeft`，否则拖拽块恒定偏离鼠标 1px。
   - 夹取：`availY` 原先额外扣了上下 padding，块到末行前 10px 就被夹住、对不齐底部；改为只扣块自身尺寸（`spacerH - 68`），块底可贴到内容底。
8. **排序首帧「全部缩略图从左上角飞入」**
   - 根因：排序开始时 position 由 relative 切 absolute、`transform` 由 `none` 起算，带过渡就会从网格左上角动画到目标格。
   - 解决：首帧加 `is-sorting-init` 禁用 tile 的 `transform` 过渡（目标格本就与流内位置重合，视觉完全不动），`onPatched` 后切 `move` 阶段恢复避让动画。
9. **已保存图片的 `image_1920` 可能是 binary size 占位**
   - 现象：把图库图提升为主图时，若直接把 `rec.data.image_1920` 写进主图字段，写进去的是 `"12.3 Kb"` 这类占位串。
   - 解决：`_readGalleryImageBase64()` / `_readMainImageBase64()` 在值为空或 `isBinarySize()` 时用 `orm.read` 取真实 base64；且**原主图必须在覆盖主图字段之前读取**，否则原图丢失。
10. **未保存图库记录的 key 不是数字 id**
    - 现象：原主图落位新建的图库记录 key 形如 `gvirtual_1`，`_gidFromKey` 原先 `Number("virtual_1")` 得 NaN → 记录匹配不到 → 后续再拖动 / 删除该图**静默失败**。
    - 解决：`_gidFromKey` 兼容虚拟 id（非数字时返回原始字符串），与 `record.resId || record.id` 严格相等命中。
11. **更换主图后 key 漂移**
    - 现象：主图变更后 `'main'` 指向另一张图，弹窗按旧 key 锚定会选中错误的图。
    - 解决：排序提交后按**落位索引** `prefer: hole` 重拉列表，不按 key 锚定。
12. **写回的并发保护**：`onManageReorder` 先比对 `displayKeys.length !== after.length`（期间发生过增删）就直接放弃，避免按过期顺序写错位。

### 接口与字段变更（本轮）

- **无模型 / 字段 / 视图 / 权限变更**，仅前端 JS / XML / SCSS 与 manifest 版本、描述；无需迁移脚本。
- widget 侧（`product_image_gallery.js`）：新增 `displayKeys` getter、`_galleryKeysOf()`、`_writeOrderWithNewMain()`、`_writeGalleryOrder()`、`_readGalleryImageBase64()`、`_readMainImageBase64()`；`onManageReorder(after)` 改为统一数组 diff 入口；`_gidFromKey()` 兼容虚拟 id。
- 弹窗侧（`product_image_manage.js`）：新增 `gridClass()`；`drag` 状态新增 `phase`（`init` / `move`）与 `snapping`；抓取偏移 `grabX/grabY`；`_dragEnabled` 改为「至少两张图片」；插入位允许为 0。
- 样式（`product_image_gallery.scss`）：新增 `.is-sorting-init`、`.o_gm-drag.o_gm-snap`；网格加 `overflow-x: hidden`；`.o_gallery_manage-tile` 承担常态 `position: relative`。
- 模板（`product_image_manage.xml`）：`<template t-if>` → `<t t-if>`；网格与缩略图 class 由 `gridClass()` + `t-attf-class` 统一输出；名称行占位 `&#160;`；确认框按钮顺序调整；header 去掉 `pe-1`。

### 可复用设计思路

- **前端统一数组 + diff 最小写回**：当后端把「首位资源」与「排序明细」分开存时，前端合成一个数组做唯一顺序来源，拖动后先 diff 再分别写回，并对未变动项**不产生任何写操作**（减少 dirty 与重排抖动）；diff 前先校验长度，防止并发增删错位。
- **网格拖拽排序套路**：排序态切「绝对定位 + `transform`」+ 插入位（hole）映射其余项格位；拖拽块与避让块用同一套「内容区坐标系」（原点 = border 内沿 + padding）；拖拽块无过渡逐帧跟手、落位时再开过渡；首帧必须禁过渡，否则从原点飞入。
- **覆盖 Bootstrap 工具类前先查 `!important`**：工具类（`.position-*`/`.d-*` 等）多带 `!important`，模块内需要被覆盖的定位/显示，一律写进模块 SCSS，不要依赖工具类。
- **Owl 模板两条硬规则**：条件分支用 `<t t-if>`（`<template>` 是惰性容器，内容不渲染）；`t-att-class` 是 token 级增删、不会清掉静态 class，需要整体控制时用 `t-attf-class` + 组件 getter 统一输出。
- **二进制图片字段的两条顺序规则**：① 已保存记录的值可能是 binary size 占位，写入前必须 `orm.read` 取真实 base64；② 「替换主资源」类操作必须**先读旧值再写新值**，否则旧数据丢失。
- **更换主资源用「移动」而非「复制」**：提升明细为主资源时删除该明细记录、把原主资源落位为明细，保证总数不变、不重复展示。
