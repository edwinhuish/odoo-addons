# 变更日志

## [19.0.1.0.0] - 2026-09-02（验收通过）

### 验收记录

- 验收日期：2026-09-02
- 验收环境：目标 Odoo 19 部署环境
- 验收结果：九项验收标准全部通过
  - [x] 图片区域获得焦点后 `Ctrl+V` 可直接上传，效果与点选文件一致
  - [x] 粘贴后缩略图立即显示（本地 base64 预览），无"无反应"空窗期
  - [x] 上传中缩略图叠加进度条遮罩（spinner + 「上传中…」），完成后消失
  - [x] 剪贴板无图片时不拦截普通文本粘贴
  - [x] 只读态不触发上传
  - [x] 拖拽图片文件到图片区域可上传，容器高亮提示
  - [x] 一次粘贴 / 拖拽多张图片逐张处理
  - [x] 超大图弹出中文报错，带出具体大小
  - [x] 复用 Odoo 原生上传链路，不改核心模板文件

### 执行流程

1. 首次安装：`odoo -d <db> -i image_uploader --stop-after-init`
   （纯前端模块，无数据库结构变更，无迁移脚本）
2. 打开任意带图片字段的表单（如产品表单 `image_1920`、联系人表单头像），点击图片区域使其获得焦点
3. 按 `Ctrl+V`（macOS：`Cmd+V`）粘贴剪贴板图片，验证缩略图立即显示 + 进度条遮罩
4. 从文件管理器拖拽图片文件到图片区域，验证高亮提示与上传
5. 只读态验证粘贴 / 拖拽均不触发上传
6. 粘贴超大图验证中文报错（阈值取自 `session.max_file_upload_size`，默认 128 MB）

### 异常情况与处理

- 粘贴无反应：检查图片区域是否获得焦点（根 `div` 有 `tabindex="0"`），按 `Tab` 切到图片区域后再粘贴
- 拖拽无高亮：前端资源缓存，`-u image_uploader` 升级后强刷浏览器
- 多图只保留最后一张：单图字段按原生行为覆盖当前值，属预期；多图场景由 T-004 `product_image` 处理
- 超大图报错：由原生 `checkFileSize` 触发，阈值取自 `session.max_file_upload_size`（默认 128 MB）

### 后续维护说明

- 让多图控件（如 T-004 `product_image`）支持粘贴新增：本模块已 patch `FileUploader`，
  任何使用 `FileUploader` 的控件自动获得粘贴能力；若多图控件自定义组件，需在其根元素挂
  `t-on-paste` 并调用该组件的「新增一条图片记录」入口
- 调整接受的图片 MIME 类型：改 `DEFAULT_ACCEPTED_IMAGE_TYPES` 或视图层给 `ImageField`
  传 `accepted_file_extensions` 选项（原生支持）
- 压缩超大图（而非报错）：在 `fileToUploadInfo` 加 canvas 压缩逻辑，参考原生 `resizeBlobImg`
  （`web/static/src/core/utils/files.js`）

### 变更

- 初始版本，实现图片粘贴 / 拖拽上传增强：
  - patch `ImageField`：在根 `div` 挂 `t-on-paste` / `t-on-dragover` / `t-on-dragleave` / `t-on-drop` 事件，复用原生 `onFileUploaded(info)` 处理上传（含 webp 转换、多尺寸附件生成）
  - **即时预览**：粘贴 / 拖拽开始时先用 base64 写入 `props.record` 触发缩略图立即渲染，无需等服务器；`state.isUploading` 标记上传中
  - **进度条遮罩**：上传中在缩略图上叠加半透明黑底 + spinner + 「上传中…」文字，`onFileUploaded` 完成后自动消失
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
- 根目录 `TODO.md`：T-003 移入「已完成」，补完成日期、落地版本、验收记录、异常情况与后续维护
- 根目录 `README.md` / `AGENTS.md`：模块速查表更新 `image_uploader` 状态为「已交付，目标环境已验证」
