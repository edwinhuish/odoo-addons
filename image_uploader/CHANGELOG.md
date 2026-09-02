# 变更日志

## [19.0.1.0.0] - 2026-09-02

### 变更

- 初始版本，实现图片粘贴 / 拖拽上传增强：
  - patch `ImageField`：在根 `div` 挂 `t-on-paste` / `t-on-dragover` / `t-on-dragleave` / `t-on-drop` 事件，复用原生 `onFileUploaded(info)` 处理上传（含 webp 转换、多尺寸附件生成）
  - patch `FileUploader`：在根 `div` 挂 `t-on-paste`，让所有使用 `FileUploader` 的场景（Many2many binary、附件上传等）都获得粘贴能力
  - 模板扩展：`t-inherit` + `t-inherit-mode="extension"` 给根元素挂事件与 `tabindex="0"`（让图片区域可获焦点）
  - 工具函数：`extractImageFilesFromClipboard` / `extractImageFilesFromDrop` / `fileToUploadInfo` / `isAcceptedImageType`
  - 复用 `checkFileSize` 做大小检查，超大图走原生提示带出具体大小
  - 拖拽高亮样式 `o_image_uploader_drag_over`（虚线轮廓 + 半透明背景）
  - 只读态处理器入口直接 `return`；剪贴板无图片时不 `preventDefault`（放行文本粘贴）

### 影响

- **纯前端模块**，无 Python 模型、无数据文件、无 `security/` 目录
- 仅依赖 `web`，不依赖 `product` / `sale`
- 静态资源走 `assets`（`web.assets_backend`），不走 `data`
- 不修改 Odoo 核心源码，全部通过 `patch` + `t-inherit` 扩展
- 影响所有使用 `ImageField` 与 `FileUploader` 的场景（产品图片、联系人头像、附件上传等）

### 文档

- 同步更新 `__manifest__.py`、`README.md`、`AGENTS.md`
- 根目录 `TODO.md`：T-003 移入「进行中」并补验收标准
- 根目录 `README.md` / `AGENTS.md`：模块速查表更新 `image_uploader` 状态
