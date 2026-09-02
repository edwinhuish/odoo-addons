# 产品多图

Odoo 19 产品模块扩展，用于在外贸 SOHO 场景下为一个产品维护多张图片，支持排序、首图即主图、图库内粘贴新增。

---

## 功能概述

- 一个产品可挂多张图片，独立明细模型 + `One2many` 挂在 `product.template` 上
- 每张图片继承 `image.mixin`，自动生成多尺寸（1920/1024/512/256/128）与 webp 转换
- 首图（排序最前）自动同步到产品主图 `image_1920`，保留与原生主图的关系
- 图库内支持拖拽排序，首图即主图
- 图库区域支持粘贴图片即新增一条记录（联动 `image_uploader` 的粘贴能力）
- 产品列表展示图片数量；看板展示主图缩略（原生 `image_128` 即主图缩略）
- 删除产品时图片行级联清理，无孤儿数据
- 仅依赖 `product`，不依赖 `website_sale`，避免与 eCommerce 冲突

---

## 核心设计

| 设计点 | 说明 |
|--------|------|
| 独立明细模型 | 图片存于 `product.image.gallery`，继承 `image.mixin` 复用多尺寸与 webp 转换 |
| 模型名避开 `product.image` | 刻意用 `product.image.gallery`，避免与 `website_sale` 的 `product.image` 冲突 |
| 首图即主图 | `sequence` 最小且 `id` 最小者即主图，`_sync_main_image_from_template` 自动同步到 `product.template.image_1920` |
| `is_main` 自动判定 | 由排序与 `active` 自动计算，勿手工编辑 |
| 级联清理 | 删除产品时图片行 `ondelete='cascade'`，无孤儿数据 |
| 粘贴新增 | patch `X2ManyField`，仅对 comodel 为 `product.image.gallery` 的图库生效，剪贴板图片逐张新增行 |

---

## 模型字段

### `product.template`（扩展）

| 字段 | 类型 | 说明 |
|------|------|------|
| `image_gallery_ids` | `One2many` → `product.image.gallery` | 该产品的所有图片 |
| `image_gallery_count` | `Integer`（compute） | 图片数量 |

### `product.image.gallery`（新建）

| 字段 | 类型 | 说明 |
|------|------|------|
| `image_1920` | `Image`（继承自 `image.mixin`） | 图片源数据，自动生成 1024/512/256/128 多尺寸 |
| `image_128` | `Image`（related） | 128 缩略，用于列表/看板展示 |
| `name` | `Char` | 图片名称，同一产品内不可重复 |
| `sequence` | `Integer` | 排序，数值小的在前；首图即主图 |
| `is_main` | `Boolean`（compute, store） | 是否为主图，自动判定 |
| `active` | `Boolean` | 启用状态，可停用而不删除 |
| `note` | `Char` | 备注 |
| `product_tmpl_id` | `Many2one` → `product.template`（required, index, cascade） | 所属产品 |

---

## 视图

- **产品表单**：「常规信息」页之后新增「图库」页，内嵌 One2many 行，可增删改排序，每行一个图片字段
- **产品列表**：新增「图片数」列（可选显示）
- **产品看板**：原生已展示 `image_128`（即主图缩略），无需改动
- **图库独立视图**：`产品图片` 动作，供按需检索与维护

---

## 依赖

- `product`（产品模块，最小化依赖，不依赖 `sale` / `website_sale`）
- 粘贴新增能力需配合 `image_uploader` 模块（T-003）；未安装时图库仍可点击选择文件上传

---

## 安装与使用

1. 将 `product_multi_image` 目录放入 Odoo 19 的 `addons_path`
2. 更新应用列表后安装模块：`产品多图`
3. 打开任意产品表单，在「图库」页新增图片行
4. 拖拽「排序」列调整顺序，首图自动成为产品主图
5. 在图库区域按 `Ctrl+V` 可粘贴剪贴板图片新增一条记录（需 `image_uploader` 模块）

### 粘贴新增

在产品表单「图库」页的 One2many 列表区域获得焦点后，按 `Ctrl+V` / `Cmd+V` 可直接粘贴剪贴板图片，
每张图片自动新增一条图库记录并写入 `image_1920`。一次粘贴多张图片逐张新增。

---

## 验证清单

> 待目标环境验证。

| 验证项 | 期望 |
|--------|------|
| 产品表单图库页 | 可增删改排序图片行 |
| 首图即主图 | 拖拽排序后首图变更，产品主图 `image_1920` 自动同步 |
| 图库粘贴新增 | 图库区域 Ctrl+V 粘贴剪贴板图片新增一条记录（需 image_uploader） |
| 产品列表图片数 | 「图片数」列显示正确数量 |
| 删除产品 | 图片行随之级联清理 |
| 重复图片名称 | 同一产品内被阻止并中文提示 |
| 图库独立动作 | 可打开列表/表单检索维护 |

### 执行流程

1. 首次安装：`odoo -d <db> -i product_multi_image --stop-after-init`
   自动建表、加载权限、注册前端资源
2. 产品表单「图库」页新增图片行，保存后首图自动同步到主图
3. 拖拽排序验证首图变更与主图同步
4. 图库区域粘贴图片验证新增（需 image_uploader）
5. 删除产品验证级联清理

### 异常情况与处理

- 图库为空：产品主图 `image_1920` 被清空，避免残留陈旧主图
- 历史产品无图库：`image_gallery_ids` 为空，不影响原生主图字段使用
- 同一产品重复图片名称：`@api.constrains` 阻止并中文提示
- 粘贴无反应：检查图库区域是否获得焦点（根 div 有 `tabindex="0"`），按 `Tab` 切到图库区域后再粘贴
- 粘贴新增失效：前端资源缓存，`-u product_multi_image` 升级后强刷浏览器

### 后续维护

- 改变首图判定规则：只改 `product_image.py` 的 `_compute_is_main` 与 `_get_main_image`
- 让其他模型支持图库粘贴新增：patch `X2ManyField` 的 `isImageGallery` 判断扩展 comodel 白名单
- 与 `website_sale` 共存：本模块用 `product.image.gallery` 模型名，与 `product.image` 互不干扰

---

## 许可证

LGPL-3
