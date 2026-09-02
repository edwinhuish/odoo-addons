# 图片粘贴上传

Odoo 19 后台图片字段增强模块，让外贸 SOHO 录入产品图片时少点几下：剪贴板直接粘贴、拖拽上传、一次多张。

---

## 功能概述

- 图片字段（`ImageField`）在编辑态获得焦点后，`Ctrl+V` / `Cmd+V` 可直接粘贴剪贴板图片上传，效果与点选文件一致
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
| `static/src/js/image_field_paste.js` | patch `ImageField`（paste/drop）与 `FileUploader`（paste），含文件提取、大小检查、MIME 校验工具函数 |
| `static/src/xml/image_field_paste.xml` | 扩展 `web.ImageField`、`web.FileUploader` 模板，挂载事件与 `tabindex` |
| `static/src/scss/image_uploader.scss` | 拖拽高亮样式 `o_image_uploader_drag_over` |

> 本模块为**纯前端模块**，无 Python 模型、无数据文件、无 `security/` 目录。

---

## 安装与使用

1. 将 `image_uploader` 目录放入 Odoo 19 的 `addons_path`
2. 更新应用列表后安装模块：`图片粘贴上传`
3. 打开任意带图片字段的表单（如产品表单的 `image_1920`），点击图片区域使其获得焦点
4. 按 `Ctrl+V`（macOS：`Cmd+V`）粘贴剪贴板图片，或把图片文件拖到图片区域

### 操作要点

- **粘贴**：先复制图片到剪贴板（截图、右键复制图片、从文件管理器复制），再点击图片区域获得焦点，最后按 `Ctrl+V`
- **拖拽**：从文件管理器直接把图片文件拖到图片区域，松开鼠标即上传
- **多图**：一次粘贴 / 拖拽多张图片时，单图字段按原生行为覆盖当前值（保留最后一张），多图场景（如 T-004 `product_multi_image`）会逐张新增
- **只读态**：图片字段处于只读时，粘贴 / 拖拽均不触发上传
- **超大图**：超过服务器 `max_file_upload_size` 时弹出中文提示，带出具体大小

---

## 依赖

- `web`（最小化依赖，只复用其前端组件与工具）

---

## 验证清单

> 待目标环境验证。验证步骤见根目录 `TODO.md` 的 T-003 验收标准。

| 验证项 | 期望 |
|--------|------|
| 粘贴上传 | 图片区域获得焦点后 `Ctrl+V` 可直接上传，效果与点选文件一致 |
| 剪贴板无图片 | 不拦截普通文本粘贴 |
| 只读态 | 不触发上传 |
| 拖拽上传 | 拖入图片文件可上传，容器高亮提示 |
| 多图粘贴 | 一次粘贴多张图片逐张处理 |
| 超大图 | 弹出中文报错，带出具体大小 |
| 复用原生链路 | 不改核心模板文件 |

---

## 许可证

LGPL-3
