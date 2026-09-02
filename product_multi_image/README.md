# 产品多图

Odoo 19 产品模块扩展，用于在外贸 SOHO 场景下为一个产品维护多张图片，在原有图片位置直接支持多图浏览，不新增页签，保持界面简洁。

---

## 功能概述

- 在产品表单原有图片位置（头像区域）直接支持多图浏览，不新增页签、不增加导航层级
- 多图并存：左右切换、计数指示（如 2/5）、缩略图条点击跳转
- 上传即新增一条图库记录并设为当前图；删除当前图后自动切换相邻图
- 头像区域支持 `Ctrl+V` 粘贴剪贴板图片即新增图库记录（无需 `image_uploader` 依赖）
- 每张图片继承 `image.mixin`，自动生成多尺寸（1920/1024/512/256/128）
- 首图（排序最前）自动同步到产品主图 `image_1920`，保留与原生主图的关系
- 产品列表展示图片数量；看板/报价单展示主图缩略（原生 `image_128` 即主图缩略）
- 删除产品时图片行级联清理，无孤儿数据
- 仅依赖 `product`，不依赖 `website_sale`，避免与 eCommerce 冲突

---

## 核心设计

| 设计点 | 说明 |
|--------|------|
| 原位多图浏览 | 自定义 `product_image_gallery` widget 替换原生 `image_1920` 字段 widget，同一位置渲染当前图 + 导航 + 缩略图条 |
| 独立明细模型 | 图片存于 `product.image.gallery`，继承 `image.mixin` 复用多尺寸 |
| 模型名避开 `product.image` | 刻意用 `product.image.gallery`，避免与 `website_sale` 的 `product.image` 冲突 |
| 首图即主图 | `sequence` 最小且 `id` 最小者即主图，`_sync_main_image_from_template` 自动同步到 `product.template.image_1920` |
| `is_main` 自动判定 | 由排序与 `active` 自动计算，勿手工编辑 |
| 浏览不写库 | 切换为纯前端 `currentIndex` 状态，不写产品主图；上传/删除走 One2many record 操作 |
| 级联清理 | 删除产品时图片行 `ondelete='cascade'`，无孤儿数据 |

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
| `image_128` | `Image`（related） | 128 缩略，用于列表/看板/widget 展示 |
| `name` | `Char` | 图片名称，同一产品内不可重复 |
| `sequence` | `Integer` | 排序，数值小的在前；首图即主图 |
| `is_main` | `Boolean`（compute, store） | 是否为主图，自动判定 |
| `active` | `Boolean` | 启用状态，可停用而不删除 |
| `note` | `Char` | 备注 |
| `product_tmpl_id` | `Many2one` → `product.template`（required, index, cascade） | 所属产品 |

---

## 视图

- **产品表单**：头像区域 `image_1920` 字段 widget 改为 `product_image_gallery`，同一位置支持多图浏览/上传/删除/粘贴新增
- **产品列表**：新增「图片数」列（可选显示）
- **产品看板**：原生已展示 `image_128`（即主图缩略），无需改动
- **图库独立视图**：`产品图片` 动作，供按需检索与维护

---

## 依赖

- `product`（产品模块，最小化依赖，不依赖 `sale` / `website_sale`）
- 粘贴新增能力内建，无需 `image_uploader` 依赖

---

## 安装与使用

1. 将 `product_multi_image` 目录放入 Odoo 19 的 `addons_path`
2. 更新应用列表后安装模块：`产品多图`
3. 打开任意产品表单，头像区域即多图控件：
   - 点击编辑按钮（铅笔）选择图片文件上传，自动新增图库记录
   - 多图时左右箭头切换，点击底部缩略图跳转
   - 删除按钮移除当前图，自动切换相邻图
   - 头像区域获得焦点后按 `Ctrl+V` 粘贴剪贴板图片新增
4. 保存产品后首图自动同步为产品主图，列表/看板/报价单展示主图

### 粘贴新增

在产品表单头像区域获得焦点后（按 `Tab` 切到图片区域），按 `Ctrl+V` / `Cmd+V` 可直接粘贴剪贴板图片，
每张图片自动新增一条图库记录并设为当前图。一次粘贴多张图片逐张新增。

---

## 验证清单

> 待目标环境验证。

| 验证项 | 期望 |
|--------|------|
| 头像区域多图浏览 | 显示当前图片，多图时可左右切换、点击缩略图跳转 |
| 上传新增 | 点击编辑按钮选图后新增图库记录并设为当前图 |
| 删除切换 | 删除当前图后自动切换相邻图，图库为空时显示占位图 |
| 粘贴新增 | 头像区域 Ctrl+V 粘贴剪贴板图片新增图库记录 |
| 首图同步 | 保存产品后首图同步到主图，列表/看板展示主图 |
| 产品列表图片数 | 「图片数」列显示正确数量 |
| 删除产品 | 图片行随之级联清理 |
| 重复图片名称 | 同一产品内被阻止并中文提示 |
| 图库独立动作 | 可打开列表/表单检索维护 |

### 执行流程

1. 首次安装：`odoo -d <db> -i product_multi_image --stop-after-init`
   自动建表、加载权限、注册 `product_image_gallery` widget 前端资源
2. 产品表单头像区域上传图片，保存后首图同步到主图
3. 多图时验证左右切换与缩略图跳转
4. 头像区域粘贴图片验证新增
5. 删除当前图验证切换
6. 删除产品验证级联清理

### 异常情况与处理

- 图库为空：头像区域显示占位图，产品主图 `image_1920` 被清空
- 历史产品无图库：`image_gallery_ids` 为空，头像区域显示占位图，不影响原生主图字段使用
- 同一产品重复图片名称：`@api.constrains` 阻止并中文提示
- 粘贴无反应：检查头像区域是否获得焦点（根 div 有 `tabindex="0"`），按 `Tab` 切到图片区域后再粘贴
- widget 不生效：前端资源缓存，`-u product_multi_image` 升级后强刷浏览器
- 切换不写库：浏览切换是纯前端状态，不触发保存；上传/删除才写库

### 后续维护

- 改变首图判定规则：只改 `product_image.py` 的 `_compute_is_main` 与 `_get_main_image`
- widget 行为调整：改 `static/src/js/product_image_gallery.js` 与对应 QWeb 模板
- 与 `website_sale` 共存：本模块用 `product.image.gallery` 模型名，与 `product.image` 互不干扰
- 复用原生 webp 转换链路：当前 widget 直接写原图 base64，多尺寸由 `image.mixin` related 字段自动生成；如需报告用 webp/JPEG 附件，可在 `onFileUploaded` 内调用原生 `ImageField.onFileUploaded` 的 canvas 逻辑

---

## 许可证

LGPL-3
