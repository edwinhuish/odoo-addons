# 变更日志

## [19.0.1.0.0] - 2026-09-02（待验证）

### 变更

- 初始版本，实现产品多图图库：
  - 新建 `product.image.gallery` 明细模型，继承 `image.mixin`，自动生成多尺寸（1920/1024/512/256/128）与 webp 转换
  - 模型名刻意避开 `website_sale` 的 `product.image`，使本模块可在不依赖 eCommerce 的环境独立安装
  - 扩展 `product.template`：`One2many` 挂图库行、`image_gallery_count` 图片数量计算字段
  - 首图（排序最前，id 兜底）自动同步到产品主图 `image_1920`，保留与原生主图关系
  - 图库内拖拽 `sequence` 排序，首图即主图；`is_main` 由排序与 active 自动判定
  - 同一产品内图片名称不可重复：`@api.constrains` 中文提示
  - 图库区域支持粘贴图片即新增一条记录（patch `X2ManyField`，仅对 comodel 为 `product.image.gallery` 生效，联动 T-003）
  - 产品表单「常规信息」页之后新增「图库」页，One2many 行可增删改排序
  - 产品列表新增「图片数」列（可选显示）
  - 图库独立列表/表单/搜索视图与动作，供按需检索维护
  - 图片行 `ondelete='cascade'`，删除产品时无孤儿数据
  - 仅依赖 `product`，不依赖 `website_sale`，避免与 eCommerce 冲突

### 影响

- 新增模型 `product.image.gallery`，需在目标环境安装后由 `ir.model.access.csv` 授权
- `product.template` 新增 `image_gallery_ids`（One2many）与 `image_gallery_count`（compute）字段
- 首图自动写入产品主图 `image_1920`，与原生主图字段共用，列表 / 看板 / 报价单无需改动即可展示主图
- 不修改 Odoo 核心源码，全部通过 `_inherit` 扩展；前端通过 `patch` 与 `t-inherit` 扩展
- 仅依赖 `product`，不依赖 `sale` / `website_sale`

### 文档

- 同步更新 `__manifest__.py`、`README.md`、`AGENTS.md`、根 `TODO.md` / `README.md` / `AGENTS.md`

### 待验证清单

- 产品表单「图库」页增删改排序图片行
- 拖拽排序后首图变更，产品主图 `image_1920` 自动同步
- 图库区域 Ctrl+V 粘贴剪贴板图片新增一条记录（需 image_uploader 已安装）
- 产品列表「图片数」列显示正确数量
- 删除产品时图片行级联清理
- 同一产品内重复图片名称被阻止并中文提示
- 图库独立动作可打开列表/表单检索维护
- 回滚方式：卸载模块 `odoo -d <db> -u product_multi_image --stop-after-init`（卸载前图片数据保留在 `product.image.gallery` 表，卸载后表随模块删除）
