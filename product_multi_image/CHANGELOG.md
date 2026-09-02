# 变更日志

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

### 影响

- 新增模型 `product.image.gallery`，需在目标环境安装后由 `ir.model.access.csv` 授权
- `product.template` 新增 `image_gallery_ids`（One2many）与 `image_gallery_count`（compute）字段
- 首图自动写入产品主图 `image_1920`，与原生主图字段共用，列表 / 看板 / 报价单无需改动即可展示主图
- 产品表单头像区域的 `image_1920` 字段 widget 由原生 `image` 改为 `product_image_gallery`，同一位置支持多图浏览
- 不修改 Odoo 核心源码，全部通过 `_inherit` 扩展；前端通过自定义 widget 实现，不覆写原生组件
- 仅依赖 `product`，不依赖 `sale` / `website_sale`

### 文档

- 同步更新 `__manifest__.py`、`README.md`、`AGENTS.md`、根 `TODO.md` / `README.md` / `AGENTS.md`

### 待验证清单

- 产品表单头像区域显示当前图片，多图时可左右切换、点击缩略图跳转
- 上传图片即新增图库记录并设为当前图
- 删除当前图后自动切换到相邻图，图库为空时显示占位图
- 头像区域 Ctrl+V 粘贴剪贴板图片新增图库记录（无需 image_uploader）
- 保存产品后首图自动同步到主图，列表/看板展示主图
- 产品列表「图片数」列显示正确数量
- 删除产品时图片行级联清理
- 同一产品内重复图片名称被阻止并中文提示
- 图库独立动作可打开列表/表单检索维护
- 回滚方式：卸载模块 `odoo -d <db> -u product_multi_image --stop-after-init`（卸载前图片数据保留在 `product.image.gallery` 表，卸载后表随模块删除）
