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
- 自定义图片管理弹窗：`ProductImageManageDialog`（点击「+」打开：上半部分大图（仅预览、无删除按钮）+ 平铺缩略图（每张缩略图含主图右上角 ×——删图库图删记录，删主图自动提升图库首张；点击缩略图只切弹窗大图），下半部分上传 dropzone（点击/拖放/Ctrl+V，上传中缩略图 + 动画，粘贴不自动关闭，上传不改变页面大图）；走 `main_components` 注册表顶层 overlay）
- 主依赖：`product`（最小化，不依赖 `sale` / `website_sale` / `web_image_paste`）
- 当前版本：`19.0.2.2.15`

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
   - 头像区缩略图列**只用于选中/切换，不承载删除按钮**；「图片管理」弹窗（点击缩略图列末端「+」打开）中**大图预览区不提供删除按钮**（任何图片），删除入口只在**缩略图网格**——每张缩略图（含主图）右上角 ×：图库图删除记录，主图删除自动提升图库首张（`onMainRemove`）
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
| `static/src/js/product_image_gallery.js` | `product_image_gallery` widget：主图 2 倍 / 悬浮局部放大（放大镜跟随鼠标）/ 点击预览入口 / 展示序列（主图+图库）/ 右侧缩略图（选中切换·滚动·「+」开管理弹窗·选中蓝边框）/ 管理弹窗回调（列表快照 getItems / 删除按 type+key 分派 / 上传写入主图或追加图库且按稳定 key 锚定页面展示不上跳新图） |
| `static/src/xml/product_image_gallery.xml` | widget QWeb 模板：主图 + 悬浮浮层 + 右侧缩略图列（无删除按钮）+ 预览弹窗 |
| `static/src/js/product_image_preview.js` | `ProductImagePreviewDialog`：全屏预览，放大/缩小/旋转 |
| `static/src/xml/product_image_preview.xml` | 预览弹窗 QWeb 模板 |
| `static/src/js/product_image_manage.js` | `ProductImageManageDialog` + `useProductImageManage` hook：图片管理弹窗（顶层 overlay 走 main_components），上半大图（仅预览、无删除按钮）+ 平铺缩略图（删除入口只在网格：每张缩略图含主图 ×，删主图自动提升；点击缩略图只切换弹窗内大图，不回传 widget）；下半 dropzone + 自实现上传队列（点击/拖放/Ctrl+V，缩略图 + 转圈动画，粘贴不自动关闭）；通过 getItems/onDelete/onUploaded 回调与 widget 同步 |
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

图库图片按 `sequence` 升序展示（主图始终在最前，由 widget 拼到序列首位，不参与 `sequence` 排序）。
改排序规则只改 `product.image.gallery` 的 `_order` 与 widget `galleryRecords` getter 的排序逻辑。
主图与图库解耦，不涉及任何主图同步。

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
- 删除按钮位置与条件：缩略图网格内**每张缩略图（含主图）**渲染 `.o_gallery_manage-del`（无 type 条件）；大图预览区模板无删除按钮（19.0.2.2.15 起只作预览）。删除主图应走 `onManageDelete('main')` → `onMainRemove`（图库首张自动提升 / 图库空则清空），不要直接清主图字段
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
- **图片管理弹窗顶层 overlay**：走 `main_components` 注册表，与 gallery 渲染树解耦，避免 gallery 重渲染闪烁；弹窗通过 `getItems` / `onDelete` / `onUploaded` 回调操作记录，删除 / 上传后由 widget 重新生成列表快照，弹窗不重建即同步；弹窗内「选中切换」是弹窗自身状态、不回传 widget（19.0.2.2.14 起点缩略图不影响页面主图）；上传自实现队列逐张显示本地缩略图 + 动画；Ctrl+V 粘贴上传后不自动关闭（19.0.2.2.12 起 widget 头像缩略图列不再放删除按钮，删除统一收进该弹窗；19.0.2.2.15 起大图预览区不提供删除按钮，删除入口在缩略图网格——每张缩略图（含主图）右上角 ×，删除主图经 `onManageDelete('main')` 自动提升图库首张；上传不切换页面展示——widget 上传前记录当前展示项稳定 key，写记录后按 key 锚定回原图）。

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
