# 变更日志

## [19.0.2.0.3] - 2026-09-03（待验证）

### 变更

- **主图与图库完全解耦，主图独立于图库**：移除 `_sync_main_image_from_template`、`is_main` 字段、`_compute_is_main`、`_get_main_image`、`product.image.gallery` 的 create/write/unlink override。产品主图 `image_1920` 由原生字段独立管理，图库**不反向同步 / 不覆盖 / 不清空**主图。
- **展示序列重构**：widget 引入 `displayItems`，浏览序列 = [原生主图（若有值）] + [图库图片按 `sequence` 升序]，主图永远作为第一张；其余图库图片缩略图按顺序排在其后。`currentIndex` 改为索引 `displayItems`。
- **主图项可编辑**：主图项缩略图带铅笔「替换主图」按钮（`FileUploader` → 写 `image_1920` 字段）与 ×「清空主图」按钮（清空 `image_1920`），与图库项的 × 删除按钮区分。大图区不再放上传/删除按钮，编辑入口全部收敛到缩略图。
- **视图**：图库独立列表 / 表单 / 搜索视图移除 `is_main` 字段与「主图」筛选，动作帮助文案更新。
- 模型简化：`product.image.gallery` 仅保留字段 + 名称唯一约束 + 级联，无同步逻辑。

### 影响

- **数据库结构变化**：`product_image_gallery` 表不再有 `is_main` 列。模块仅支持全新安装（旧版本未在目标环境验证安装），全新安装自动建表无 `is_main`；若曾测试安装过旧版，需先卸载旧模块（删除表）再全新安装新模块。
- 主图与图库彻底独立：图库增删改 / 排序均不影响产品主图；列表 / 看板 / 报价单展示原生主图。
- 历史产品有主图无图库：主图作为序列首张展示，无图库缩略图；上传图库图后跟在主图后（不覆盖主图）。
- 无主图产品：序列首项为第一张图库图（如有）；可点主图项铅笔按钮上传主图。
- 模型 / 视图结构简化，前端 widget 重构；不修改 Odoo 核心源码。

### 文档

- 同步 `__manifest__.py`（版本 / 描述）、`README.md`、`AGENTS.md`（L1 约束 4/5、文件职责、调试、后续维护）、根 `TODO.md` / `README.md` / `AGENTS.md`。

---

## [19.0.2.0.2] - 2026-09-03（待验证）

### 变更

- **移除预览弹窗「复制到剪贴板」功能**：删除 `ProductImagePreviewDialog` 的 `onCopy` 方法、`copyTitle`/`copyLabel`/`copyIconClass` getter、`isCopying`/`copyState` state、`browser`/`notification`/`ui` service 引入；模板移除顶部与底部「复制」按钮；相关调试说明同步移除。预览弹窗现仅保留放大 / 缩小 / 重置 / 旋转。
- **主图与图库解耦，上传图片不再覆盖已有主图**：`_sync_main_image_from_template` 改为「仅当产品主图 `image_1920` 为空时用图库首图填充；已有主图保留不动，图库增删改 / 排序换首图均不覆盖；图库为空不清空主图」。修复用户反馈的「上传第一个图片时覆盖了原来主图」问题。`is_main` 语义改为「图库内部首图标识」，不保证等于产品主图。

### 影响

- 历史产品（有 `image_1920` 主图无图库）：上传图库图片不再覆盖原主图，保留原值；widget 仍回退显示原生主图。
- 新产品（主图为空）：上传首张图库图后用首图填充主图，列表/看板仍有主图。
- 排序换首图不再联动产品主图；如需更换产品主图，请直接编辑产品主图字段。
- 模型 / 字段 / 视图 / 权限结构未变，仅同步逻辑与前端预览组件改动，无需迁移脚本。

### 文档

- 同步 `__manifest__.py`（版本 / 描述）、`README.md`、`AGENTS.md`（L1 约束 4 与 7）、根 `TODO.md` / `README.md` / `AGENTS.md`。

---

## [19.0.2.0.1] - 2026-09-03（待验证）

### 变更

- **修复预览弹窗放大/缩小/旋转后图片消失**：`<img>` 初始 `opacity:0` 靠 `t-on-load` 置 1，但每次 `scale`/`angle` 变化触发 `imageStyle` getter 重算、`t-att-style` 重设整个 style 时把 `opacity` 重置回 0。改为把 `opacity` 纳入 `imageStyle`（由 `state.imageLoaded` 控制），`t-on-load` 调 `onImageLoaded` 设状态；SCSS 不再写 `opacity:0`。
- **修复历史产品原主图看不到**：widget 原先只看 `image_gallery_ids`，装模块前就有 `image_1920` 主图但无图库记录的产品会显示「暂无图片」，原主图被吞掉。新增 `hasMainImage`（图库有记录 或 原生 `image_1920` 字段有值），`mainImageUrl`/`fullImageUrl` 在图库为空时回退 `getUrl(this.props.record, this.props.name)` 显示原生主图 URL；悬浮放大与点击预览也对历史主图生效。`getUrl` 用 `record.resModel` 适配图库记录与主记录两类。

### 影响

- 仅前端 widget 与预览组件改动，模型 / 字段 / 视图 / 权限未变。
- 历史产品（有 `image_1920` 无图库）现可正常显示主图、悬浮放大、点击预览；如对其上传第一张图库图片，仍按「首图即主图」同步覆盖 `image_1920`（预期行为）。

### 文档

- 同步 `__manifest__.py` 版本号；CHANGELOG 补本条。

---

## [19.0.2.0.0] - 2026-09-03（待验证）

### 变更

- **模块改名**：技术目录 / 模块技术名 `product_multi_image` → `product_image`（显示名「产品多图」→「产品图片」）。
  模型 `product.image.gallery` 名称保持不变（避免与 `website_sale` 的 `product.image` 冲突，符合 L1 约束 3）。
- **多图浏览交互重做**，按用户要求优化：
  - **主图放大 2 倍**：由原生 90×90 头像放大到 180×180 显示。
  - **移除上一张 / 下一张按钮与序号指示**（如 `2/5`），改由右侧缩略图列直接点选切换。
  - **悬浮放大**：鼠标悬浮主图时弹出放大图（优先置于主图左侧；左侧空间不足放下方；下方超出视口且右侧有空间则放右侧），浮层 `position:fixed` 避免被表单裁切。
  - **点击预览弹窗**：点击主图弹出全屏预览（`ProductImagePreviewDialog`），支持放大 / 缩小 / 重置 / 旋转（按钮 + 鼠标滚轮 + 键盘 `+`/`-`/`0`/`r`/`Esc`），并支持**复制图片到系统剪贴板**（`navigator.clipboard.write` + `ClipboardItem`，data URL 与同源 web/image URL 统一走 `fetch → blob`）。
  - **缩略图竖排右侧**：缩略图竖向排列于主图右侧，每张带删除按钮（悬浮显示），点击切换主图。
  - **缩略图溢出滚动**：缩略图总高超出主图高度时，顶部 / 底部出现上下滚动按钮，点击滚动一屏；滚动条隐藏保持简洁。
  - **缩略图末端上传占位符**：编辑态在缩略图列末端显示虚线上传占位符（`+`），点击即新增图片（复用原生 `FileUploader`，支持一次多图）。
- **删除按钮挂在缩略图上**：可删除任意一张（不限于当前主图），删除后维持可视位置并重算溢出。
- **只读态**：隐藏上传占位符与删除按钮、禁用粘贴；悬浮放大与点击预览（含复制）仍可用（只读操作不写库）。
- 前端资源新增：`static/src/js/product_image_preview.js`、`static/src/xml/product_image_preview.xml`、`static/src/scss/product_image_gallery.scss`。
- 模型 / 字段 / 视图结构 / 权限规则均未改动，仅前端 widget 与文档变更。
- registry key `product_image_gallery` 保持不变，产品表单视图无需改动即可继续生效。

### 影响

- **模块技术名变更**：从 `product_multi_image` 改为 `product_image`。Odoo 视两者为不同模块。
  - 旧模块在目标环境**尚未验证安装**（T-004 一直处于待验证状态），无生产数据需迁移。
  - 切换方式：在目标环境**先卸载** `product_multi_image`（UI 卸载或 `odoo -d <db> -i product_multi_image --stop-after-init` 后卸载），再**全新安装** `product_image`。卸载会级联删除 `product.image.gallery` 表数据（仅测试数据，无业务影响）。
  - 仓库内不含 Odoo 源码与数据库，本改动需挂到目标 Odoo 环境安装后验证。
- 主图显示尺寸放大到 180×180，产品表单头像列宽度随之变宽；不影响列表 / 看板 / 报价单主图展示（仍用原生 `image_128`）。
- 不修改 Odoo 核心源码；前端通过自定义 widget + 独立预览组件实现，不复用、不 patch 全局 `web.FileViewer`（避免影响所有附件预览）。
- 仅依赖 `product`，不依赖 `sale` / `website_sale` / `image_uploader`；粘贴新增内建。

### 文档

- 同步更新 `__manifest__.py`（版本 / 描述 / 资源路径 / 显示名）、`README.md`、`AGENTS.md`、根 `TODO.md` / `README.md` / `AGENTS.md`。

### 待验证清单

- 产品表单主图按 180×180 显示，无上一张 / 下一张按钮、无序号
- 鼠标悬浮主图弹出放大图（左侧优先，空间不足转下侧 / 右侧）
- 点击主图弹出全屏预览：放大 / 缩小 / 重置 / 旋转可用（按钮 + 滚轮 + 键盘）
- 预览弹窗「复制」按钮把图片写入系统剪贴板，可在其他位置 Ctrl+V 粘贴出图片
- 缩略图竖排于主图右侧，点击切换主图
- 缩略图悬浮显示删除按钮，点击删除对应图片并维持位置
- 缩略图数量超出主图高度时出现上下滚动按钮，点击可滚动
- 缩略图末端有上传占位符，点击可新增图片（一次多图）
- 头像区域 Ctrl+V 粘贴剪贴板图片即新增图库记录
- 只读态：无上传占位符 / 删除按钮 / 粘贴；悬浮放大与点击预览（含复制）仍可用
- 保存产品后首图自动同步到主图，列表 / 看板展示主图
- 删除产品时图片行级联清理
- 切换流程：卸载 `product_multi_image` → 安装 `product_image` 后功能正常

### 回滚方式

- 卸载 `product_image`（UI 卸载，或先安装再卸载），数据随模块删除。
- 如需回到旧交互，回退到本仓库 `product_multi_image` 的 `19.0.1.0.0` 提交并重新安装（旧模块未经验证，仅作回退兜底）。

---

## [19.0.1.0.0] - 2026-09-02（待验证）

### 变更

- 初始版本，实现产品多图图库，**在原有图片位置（头像区域）直接支持多图浏览**，不新增页签：
  - 新建 `product.image.gallery` 明细模型，继承 `image.mixin`，自动生成多尺寸（1920/1024/512/256/128）
  - 模型名刻意避开 `website_sale` 的 `product.image`，使本模块可在不依赖 eCommerce 的环境独立安装
  - 扩展 `product.template`：`One2many` 挂图库行、`image_gallery_count` 图片数量计算字段
  - 首图（排序最前，id 兜底）自动同步到产品主图 `image_1920`，保留与原生主图关系；`is_main` 自动判定
  - 同一产品内图片名称不可重复：`@api.constrains` 中文提示
  - 自定义 `product_image_gallery` widget 替换产品表单原生 `image_1920` 字段的 widget：
    - 同一位置渲染当前图片 + 左右切换 + 计数指示（2/5）+ 缩略图条
    - 上传即新增一条图库记录并设为当前图；删除当前图后自动切换相邻图
    - 图库区域 `Ctrl+V` 粘贴剪贴板图片即新增图库记录（联动 T-003 体验）
    - 浏览切换为纯前端状态，不写产品主图；上传/删除走 One2many record 操作
  - 产品列表新增「图片数」列（可选显示）
  - 图库独立列表/表单/搜索视图与动作，供按需检索维护
  - 图片行 `ondelete='cascade'`，删除产品时无孤儿数据
  - 仅依赖 `product`，不依赖 `website_sale`，避免与 eCommerce 冲突
- 删除改走主 record `update` + `x2ManyCommands`（已保存 `delete` / 新记录 `unlink`），由 Odoo 内部 `_preprocessX2manyChanges` 统一处理，避免直接调 list 内部私有方法。

### 影响

- 新增模型 `product.image.gallery`，需在目标环境安装后由 `ir.model.access.csv` 授权
- `product.template` 新增 `image_gallery_ids`（One2many）与 `image_gallery_count`（compute）字段
- 首图自动写入产品主图 `image_1920`，与原生主图字段共用，列表 / 看板 / 报价单无需改动即可展示主图
- 产品表单头像区域的 `image_1920` 字段 widget 由原生 `image` 改为 `product_image_gallery`，同一位置支持多图浏览
- 不修改 Odoo 核心源码，全部通过 `_inherit` 扩展；前端通过自定义 widget 实现，不覆写原生组件
- 仅依赖 `product`，不依赖 `sale` / `website_sale`

### 文档

- 同步更新 `__manifest__.py`、`README.md`、`AGENTS.md`、根 `TODO.md` / `README.md` / `AGENTS.md`
