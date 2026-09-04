# 图片粘贴上传

Odoo 19 后台图片字段增强模块，让外贸 SOHO 录入产品图片时少点几下：剪贴板直接粘贴、拖拽上传、一次多张。

---

## 功能概述

- 图片字段（`ImageField`）在编辑态获得焦点后，`Ctrl+V` / `Cmd+V` 可直接粘贴剪贴板图片上传，**粘贴后缩略图立即显示**（用本地 base64 预览，无需等服务器）
- 上传过程中缩略图上叠加**进度条遮罩**（半透明黑底 + 旋转 spinner + 「上传中…」文字），后台 webp 转换 / 多尺寸附件生成完成后自动消失
- 支持把图片文件拖拽到图片区域完成上传，拖拽时容器高亮提示
- 一次粘贴 / 拖拽可上传多张图片（仅对支持多图上传的控件生效；单图字段按原生行为覆盖当前值）
- 上传中由原生 `FileUploader` 的 `state.isUploading` 控制状态提示
- 超过服务器最大上传尺寸（`max_file_upload_size`，默认 128 MB）的图片给出明确中文报错，带出具体大小
- 只读态不触发上传；剪贴板无图片时不拦截普通文本粘贴
- 复用 Odoo 原生上传链路（`FileUploader.onFileChange` → `getDataURLFromFile` → `onUploaded`），不改核心模板文件

---

## 核心设计

| 设计点 | 说明 |
|--------|------|
| `@web/core/utils/patch` | 给 `ImageField` 与 `FileUploader` 打补丁，不覆写整个组件 |
| `t-inherit` + `t-inherit-mode="extension"` | 扩展 `web.ImageField` 与 `web.FileUploader` 模板，给根元素挂 `t-on-paste` / `t-on-drop` 等事件 |
| 复用原生链路 | `ImageField` 走自身 `onFileUploaded(info)`（含 webp 转换、多尺寸附件生成）；`FileUploader` 走自身 `onUploaded` 回调 |
| 复用 `checkFileSize` | 超大图走原生提示，带出具体大小 |
| 只读态放行 | 处理器入口判断 `props.readonly`，直接 `return` |
| 剪贴板无图片放行 | 只处理 `image/*` 类型，非图片不 `preventDefault` |

---

## 模块资源

| 文件 | 职责 |
|------|------|
| `static/src/js/image_field_paste.js` | patch `ImageField`（paste/drop + 即时预览 + 进度条状态）与 `FileUploader`（paste），含文件提取、大小检查、MIME 校验工具函数 |
| `static/src/xml/image_field_paste.xml` | 扩展 `web.ImageField`、`web.FileUploader` 模板，挂载事件、`tabindex`、`img` 上传中切换 `uploadingUrl`、追加进度条遮罩节点 |
| `static/src/scss/web_image_paste.scss` | 拖拽高亮样式 `o_web_image_paste_drag_over` + 上传中进度条遮罩 `o_web_image_paste_progress` + spinner 旋转动画 |

> 本模块为**纯前端模块**，无 Python 模型、无数据文件、无 `security/` 目录。

---

## 安装与使用

1. 将 `web_image_paste` 目录放入 Odoo 19 的 `addons_path`
2. 更新应用列表后安装模块：`图片粘贴上传`
3. 打开任意带图片字段的表单（如产品表单的 `image_1920`），点击图片区域使其获得焦点
4. 按 `Ctrl+V`（macOS：`Cmd+V`）粘贴剪贴板图片，或把图片文件拖到图片区域

### 操作要点

- **粘贴**：先复制图片到剪贴板（截图、右键复制图片、从文件管理器复制），再点击图片区域获得焦点，最后按 `Ctrl+V`
- **拖拽**：从文件管理器直接把图片文件拖到图片区域，松开鼠标即上传
- **多图**：一次粘贴 / 拖拽多张图片时，单图字段按原生行为覆盖当前值（保留最后一张），多图场景（如 T-004 `product_image`）会逐张新增
- **只读态**：图片字段处于只读时，粘贴 / 拖拽均不触发上传
- **超大图**：超过服务器 `max_file_upload_size` 时弹出中文提示，带出具体大小

---

## 依赖

- `web`（最小化依赖，只复用其前端组件与工具）

---

## 验证清单

> 验收日期：2026-09-02，目标环境验证通过。

| 验证项 | 期望 | 结果 |
|--------|------|------|
| 粘贴上传 | 图片区域获得焦点后 `Ctrl+V` 可直接上传，**粘贴后缩略图立即显示**，上方有进度条 | 通过 |
| 上传进度 | 上传中缩略图叠加半透明遮罩 + spinner + 「上传中…」文字，完成后消失 | 通过 |
| 剪贴板无图片 | 不拦截普通文本粘贴 | 通过 |
| 只读态 | 不触发上传 | 通过 |
| 拖拽上传 | 拖入图片文件可上传，容器高亮提示 | 通过 |
| 多图粘贴 | 一次粘贴多张图片逐张处理 | 通过 |
| 超大图 | 弹出中文报错，带出具体大小 | 通过 |
| 复用原生链路 | 不改核心模板文件 | 通过 |

### 执行流程

1. 首次安装：`odoo -d <db> -i web_image_paste --stop-after-init`
   （纯前端模块，无数据库结构变更，无迁移脚本）
2. 打开任意带图片字段的表单（如产品表单 `image_1920`、联系人表单头像），点击图片区域使其获得焦点
3. 按 `Ctrl+V`（macOS：`Cmd+V`）粘贴剪贴板图片，验证缩略图立即显示 + 进度条遮罩
4. 从文件管理器拖拽图片文件到图片区域，验证高亮提示与上传
5. 只读态验证粘贴 / 拖拽均不触发上传
6. 粘贴超大图验证中文报错（阈值取自 `session.max_file_upload_size`，默认 128 MB）

### 异常情况与处理

- 粘贴无反应：检查图片区域是否获得焦点（根 `div` 有 `tabindex="0"`），按 `Tab` 切到图片区域后再粘贴
- 拖拽无高亮：前端资源缓存，`-u web_image_paste` 升级后强刷浏览器
- 多图只保留最后一张：单图字段按原生行为覆盖当前值，属预期；多图场景由 T-004 `product_image` 处理
- 超大图报错：由原生 `checkFileSize` 触发，阈值取自 `session.max_file_upload_size`（默认 128 MB）

### 后续维护

- 让多图控件（如 T-004 `product_image`）支持粘贴新增：本模块已 patch `FileUploader`，
  任何使用 `FileUploader` 的控件自动获得粘贴能力；若多图控件自定义组件，需在其根元素挂
  `t-on-paste` 并调用该组件的「新增一条图片记录」入口
- 调整接受的图片 MIME 类型：改 `DEFAULT_ACCEPTED_IMAGE_TYPES` 或视图层给 `ImageField`
  传 `accepted_file_extensions` 选项（原生支持）
- 压缩超大图（而非报错）：在 `fileToUploadInfo` 加 canvas 压缩逻辑，参考原生 `resizeBlobImg`
  （`web/static/src/core/utils/files.js`）

---

## 许可证

LGPL-3
