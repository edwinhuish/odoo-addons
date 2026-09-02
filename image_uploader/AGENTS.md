# AGENTS 工作指引

> 本文档用于指导 AI 助手或新开发者在维护、扩展本 Odoo 模块时的行为规范和关键上下文。

---

## 模块定位

- 模块名：`图片粘贴上传`
- 技术目录：`image_uploader`
- 类型：**纯前端模块**（无 Python 模型、无数据文件、无 `security/` 目录）
- 主依赖：`web`（最小化，不依赖 `product` / `sale`）
- 当前版本：`19.0.1.0.0`

---

## L1：不可破坏的核心约束

每次修改代码必须保证以下行为不变。

1. **用 `@web/core/utils/patch` 打补丁，不覆写整个组件**
   - patch `ImageField.prototype` 与 `FileUploader.prototype`
   - 禁止复制核心组件全文后重写

2. **复用 Odoo 原生上传链路，不重复实现**
   - `ImageField` 走自身 `onFileUploaded(info)`（含 webp 转换、多尺寸附件生成）
   - `FileUploader` 走自身 `onUploaded` 回调
   - 复用 `checkFileSize` 做大小检查，复用 `getDataURLFromFile` 做 base64 转换
   - 禁止自行实现上传请求或绕过原生校验

3. **只读态不触发上传**
   - 所有处理器（`onPaste` / `onDrop` / `onDragOver` / `onDragLeave`）入口判断 `this.props.readonly`，直接 `return`
   - 不依赖模板条件（模板在只读态可能仍渲染根 `div`，所以处理器必须自己判）

4. **剪贴板无图片时不拦截普通文本粘贴**
   - `extractImageFilesFromClipboard` 返回空数组时直接 `return`，不 `preventDefault`
   - 只处理 `kind === "file"` 且 `type.startsWith("image/")` 的剪贴板项

5. **不改核心模板文件**
   - 用 `t-inherit="web.ImageField"` + `t-inherit-mode="extension"` 扩展
   - 用 `t-inherit="web.FileUploader"` + `t-inherit-mode="extension"` 扩展
   - 禁止 `position="replace"` 删除原生节点

6. **静态资源走 `assets`，不走 `data`**
   - `__manifest__.py` 用 `assets` 字段注册到 `web.assets_backend`
   - JS 首行必须是 `/** @odoo-module **/`

7. **事件处理用 `ev.currentTarget` 取根元素，不依赖组件 ref**
   - `ImageField` 原生未定义 `rootRef`，patch 里也不要新增
   - 拖拽高亮通过 `ev.currentTarget.classList` 操作

8. **粘贴 / 拖拽即时预览，不允许出现"无反应"空窗期**
   - 粘贴开始时先用 base64 写入 `props.record.update({ [name]: info.data })` 触发缩略图重渲染
   - `state.isUploading` 标记上传中，模板 `img` 在上传中优先用 `uploadingUrl`（本地 `data:` URL）
   - 模板在上传中叠加进度条遮罩（`.o_image_uploader_progress`），`onFileUploaded` 完成后置回 `false`
   - 禁止先跑完 `onFileUploaded` 全部异步逻辑才更新字段

---

## 文件职责

| 文件 | 职责 |
|------|------|
| `__manifest__.py` | 模块元数据、依赖（`web`）、`assets` 资源声明 |
| `static/src/js/image_field_paste.js` | patch `ImageField` 与 `FileUploader`，含文件提取 / 大小检查 / MIME 校验工具函数 |
| `static/src/xml/image_field_paste.xml` | 扩展 `web.ImageField`、`web.FileUploader` 模板，挂载事件与 `tabindex` |
| `static/src/scss/image_uploader.scss` | 拖拽高亮样式 `o_image_uploader_drag_over` |

---

## 常见扩展场景

### 让多图控件（如 T-004 `product_multi_image`）支持粘贴新增

本模块已 patch `FileUploader`，任何使用 `FileUploader` 的控件自动获得粘贴能力。
若多图控件不走 `FileUploader` 而是自定义组件，需在其根元素挂 `t-on-paste` 并在处理器里调用该组件的「新增一条图片记录」入口。

### 调整接受的图片 MIME 类型

改 `DEFAULT_ACCEPTED_IMAGE_TYPES` 或在视图层给 `ImageField` 传 `accepted_file_extensions` 选项（原生支持）。

### 压缩超大图（而非报错）

当前按 T-003 要求「明确报错」。若改为压缩，在 `fileToUploadInfo` 里加 canvas 压缩逻辑，参考原生 `resizeBlobImg`（`web/static/src/core/utils/files.js`）。

---

## 调试建议

- 粘贴无反应：检查图片区域是否获得焦点（根 `div` 有 `tabindex="0"`），按 `Tab` 切到图片区域后再粘贴
- 拖拽无高亮：检查 `o_image_uploader_drag_over` 样式是否加载（`-u image_uploader` 升级后强刷浏览器）
- 只读态仍触发上传：检查处理器入口是否判 `this.props.readonly`
- 多图只保留最后一张：单图字段按原生行为覆盖当前值，属预期；多图场景由 T-004 处理

---

## 变更记录规范

每次功能修改后必须更新：
- `__manifest__.py` 的 `version`（遵循 `19.0.x.y.z`）
- `CHANGELOG.md` 的版本说明（变更 / 影响 / 文档）
- 本 `AGENTS.md` 的相关约束（若涉及行为变更）
- `README.md` 的功能说明（若涉及用户可见功能）

版本号建议：
- 破坏性变更或架构调整：升第二位，如 `19.0.2.0.0`
- 功能新增：升第三位，如 `19.0.1.1.0`
- 修复或文档：升第四位，如 `19.0.1.0.1`
