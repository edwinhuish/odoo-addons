# AGENTS 工作指引

> 本文档用于指导 AI 助手或新开发者在维护、扩展本 Odoo 模块时的行为规范和关键上下文。

---

## 模块定位

- 模块名：`产品图片`（显示名）
- 技术目录 / 模块技术名：`product_image`（原名 `product_multi_image`，于 19.0.2.0.0 改名）
- 新建模型：`product.image.gallery`（模型名保持不变，避免与 `website_sale` 的 `product.image` 冲突）
- 继承模型：`product.template`
- 自定义 widget：`product_image_gallery`（registry key 不变，替换产品表单原生 `image_1920` 字段 widget）
- 自定义预览组件：`ProductImagePreviewDialog`（全屏预览，放大/缩小/复制）
- 主依赖：`product`（最小化，不依赖 `sale` / `website_sale` / `image_uploader`）
- 当前版本：`19.0.2.0.0`

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

4. **首图自动同步到产品主图，禁止手工双写**
   - 首图定义：`active=True` 中 `sequence` 最小、`id` 最小兜底
   - `product.image.gallery` 的 create/write/unlink 触发 `product.template._sync_main_image_from_template`
   - 图库为空时清空主图，避免残留陈旧主图

5. **`is_main` 由排序与 active 自动判定，禁止手工编辑**
   - `@api.depends("sequence", "product_tmpl_id", "active")` 计算
   - `store=True` 便于列表展示与过滤

6. **浏览切换为纯前端状态，禁止切换即写库**
   - widget 用 `state.currentIndex` 维护当前选中图，切换不触发 `record.update`
   - 只有上传 / 删除 / 设为主图 才走 One2many record 操作
   - 悬浮放大、点击预览、复制图片均为只读行为，不写库（只读态也允许）

7. **预览弹窗不全局 patch `web.FileViewer`，禁止影响其他附件预览**
   - 用模块内置 `ProductImagePreviewDialog` 独立组件实现放大/缩小/复制
   - 复制走 `navigator.clipboard.write` + `ClipboardItem`（经 `browser` 抽象）
   - data URL 与同源 `web/image` URL 统一走 `fetch → blob`，避免对两类 URL 分别处理

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
| `models/product_image.py` | 图片明细模型：字段、主图判定、主图同步触发、名称去重、级联 |
| `models/product_template.py` | 扩展 `product.template`：One2many、图片数量、主图同步入口 |
| `views/product_template_views.xml` | 产品表单头像字段 widget 改为 `product_image_gallery`、列表图片数列 |
| `views/product_image_views.xml` | 图库独立列表/表单/搜索视图与动作 |
| `static/src/js/product_image_gallery.js` | `product_image_gallery` widget：主图 2 倍 / 悬浮放大 / 点击预览入口 / 右侧缩略图（删除/滚动/上传占位）/ 粘贴新增 |
| `static/src/xml/product_image_gallery.xml` | widget QWeb 模板：主图 + 悬浮浮层 + 右侧缩略图列 + 预览弹窗挂载 |
| `static/src/js/product_image_preview.js` | `ProductImagePreviewDialog`：全屏预览，放大/缩小/旋转/复制到剪贴板 |
| `static/src/xml/product_image_preview.xml` | 预览弹窗 QWeb 模板 |
| `static/src/scss/product_image_gallery.scss` | widget 与预览弹窗样式（主图棋盘格背景 / 缩略图选中 / 滚动条隐藏 / 工具条） |
| `security/ir.model.access.csv` | 普通用户读写业务数据，销售经理可配置 |

---

## 常见扩展场景

### 调整 widget 渲染

改 `static/src/js/product_image_gallery.js` 与 `static/src/xml/product_image_gallery.xml`：
- 主图尺寸：模板内联 `style="width: 180px; height: 180px"`（同时改 SCSS 中主图背景棋盘格）
- 缩略图尺寸：模板内联 `style="width: 56px; height: 56px"`
- 悬浮放大尺寸：`onHoverEnter` 中 `panelW`/`panelH` 与 `hoverStyle` getter 的 `max-width/max-height`
- 缩略图滚动步长：`onThumbScrollUp/Down` 的 `scrollBy` 比例

### 调整预览弹窗

改 `static/src/js/product_image_preview.js` 与 `static/src/xml/product_image_preview.xml`：
- 缩放步长 / 最小缩放：`zoomStep` / `scrollZoomStep` / `minScale`
- 复制文案：`copyLabel` / `copyTitle` / `copyIconClass` getter

### 复用原生 webp 转换链路

当前 widget 直接写原图 base64 到图库记录，多尺寸由 `image.mixin` related 字段自动生成。
如需报告用 webp/JPEG 附件（对应原生 `ImageField.onFileUploaded` 的 canvas 逻辑），
可在 `onFileUploaded` 内调用原生 `ImageField` 的 canvas 处理后写入。

### 改变首图判定规则

只改 `product_image.py` 的 `_compute_is_main` 与 `_get_main_image`；改后对历史数据需触发一次重算：
```python
env['product.image.gallery'].search([])._compute_is_main()
templates = env['product.image.gallery'].search([]).mapped('product_tmpl_id')
templates._sync_main_image_from_template()
```

### 与 `website_sale` 共存

本模块用 `product.image.gallery` 模型名，与 `website_sale` 的 `product.image` 互不干扰。
若希望复用 `website_sale` 的 `product.image`（含视频），需另写桥接模块，不要改本模块模型名。

---

## 调试建议

- 头像区域仍显示单图：检查 widget 是否生效，`-u product_image` 升级后强刷浏览器
- 主图没放大：检查 SCSS 是否加载（`-u` 升级），主图尺寸由模板内联 style 控制
- 悬浮放大位置错乱：检查 `onHoverEnter` 的 `getBoundingClientRect` 计算与 `hoverStyle` getter
- 缩略图不滚动：检查 `.o_gallery_thumb_scroll` 的 `flex:1 1 auto; min-height:0; overflow-y:auto`
- 复制失败：浏览器非 HTTPS 或不支持 `ClipboardItem`，控制台查 `browser.navigator.clipboard`
- 上传后未新增：检查 `galleryList.addNewRecord` 是否成功，看控制台报错
- 主图未同步：检查图片行的 `sequence` 与 `active`，首图判定依赖两者
- 粘贴无反应：确认头像区域获得焦点（根 div 有 `tabindex="0"`）
- 看板无主图：确认首图存在且 `image_1920` 已同步到 `product.template`

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
