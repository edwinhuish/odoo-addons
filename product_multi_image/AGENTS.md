# AGENTS 工作指引

> 本文档用于指导 AI 助手或新开发者在维护、扩展本 Odoo 模块时的行为规范和关键上下文。

---

## 模块定位

- 模块名：`产品多图`
- 技术目录：`product_multi_image`
- 新建模型：`product.image.gallery`
- 继承模型：`product.template`
- 主依赖：`product`（最小化，不依赖 `sale` / `website_sale`）
- 当前版本：`19.0.1.0.0`

---

## L1：不可破坏的核心约束

每次修改代码必须保证以下行为不变。

1. **图片用独立明细模型，禁止塞进产品主图字段做多图**
   - `product.image.gallery` + `One2many` 挂在 `product.template` 上
   - 产品主图 `image_1920` 只是首图的同步镜像，不是图库本体

2. **模型名避开 `product.image`，禁止与 `website_sale` 共用模型**
   - 用 `product.image.gallery`，使本模块可在不依赖 eCommerce 的环境独立安装
   - 若日后与 `website_sale` 共存，两者模型互不干扰

3. **首图自动同步到产品主图，禁止手工双写**
   - 首图定义：`active=True` 中 `sequence` 最小、`id` 最小兜底
   - `product.image.gallery` 的 create/write/unlink 触发 `product.template._sync_main_image_from_template`
   - 图库为空时清空主图，避免残留陈旧主图

4. **`is_main` 由排序与 active 自动判定，禁止手工编辑**
   - `@api.depends("sequence", "product_tmpl_id", "active")` 计算
   - `store=True` 便于列表展示与过滤

5. **同一产品内图片名称不可重复**
   - `@api.constrains("name", "product_tmpl_id")` 中文提示带出具体值与产品名
   - 名称非必填，但若填了则同产品内唯一

6. **删除产品级联清理图片**
   - `product_tmpl_id` 的 `ondelete='cascade'`，禁止改成 `set null` 或 `restrict`

7. **图库粘贴新增只对 `product.image.gallery` 生效**
   - patch `X2ManyField.onPasteGallery`，入口判断 `isImageGallery`（comodel 为 `product.image.gallery`）
   - 非图库 X2many 直接 return，不拦截
   - 只读态不触发；剪贴板无图片不拦截

8. **Odoo 19 API 事实**
   - `image.mixin` 提供 `image_1920` + related 的 1024/512/256/128，继承即得
   - `name_get()` / `name_search()` 已移除，图库不需要自定义显示名
   - `_sql_constraints` 已废弃，用 `models.Constraint`（本模块当前未用 DB 约束，名称唯一仅应用层）

---

## 文件职责

| 文件 | 职责 |
|------|------|
| `__manifest__.py` | 模块元数据、依赖、数据文件声明、前端资源登记 |
| `models/product_image.py` | 图片明细模型：字段、主图判定、主图同步触发、名称去重、级联 |
| `models/product_template.py` | 扩展 `product.template`：One2many、图片数量、主图同步入口 |
| `views/product_template_views.xml` | 产品表单图库页、列表图片数列 |
| `views/product_image_views.xml` | 图库独立列表/表单/搜索视图与动作 |
| `static/src/js/image_gallery_paste.js` | patch `X2ManyField`：图库区域粘贴新增 |
| `static/src/xml/image_gallery_paste.xml` | 扩展 `web.X2ManyField` 模板：根 div 挂 paste 事件与 tabindex |
| `security/ir.model.access.csv` | 普通用户读写业务数据，销售经理可配置 |

---

## 常见扩展场景

### 让其他模型支持图库粘贴新增

patch `X2ManyField.prototype` 的 `isImageGallery` getter，把目标 comodel 加入判断：
```js
get isImageGallery() {
    const field = this.props.record.fields[this.props.name];
    return field && [
        "product.image.gallery",
        // 新增其他图库型 comodel
    ].includes(field.relation);
}
```

### 改变首图判定规则

只改 `product_image.py` 的 `_compute_is_main` 与 `_get_main_image`；改后对历史数据需触发一次重算：
```python
env['product.image.gallery'].search([])._compute_is_main()
templates = env['product.image.gallery'].search([]).mapped('product_tmpl_id')
templates._sync_main_image_from_template()
```

### 与 `website_sale` 共存

本模块用 `product.image.gallery` 模型名，与 `website_sale` 的 `product.image` 互不干扰。
若希望复用 `website_sale` 的 `product.image`（含视频），需另写桥接模块，不要改本模块模型名。

---

## 调试建议

- 主图未同步：检查图片行的 `sequence` 与 `active`，首图判定依赖两者
- 粘贴新增失效：确认 `image_uploader` 已安装且图库区域获得焦点（根 div 有 `tabindex="0"`）
- `is_main` 未刷新：检查 `@api.depends` 是否覆盖触发字段
- 看板无主图：确认首图存在且 `image_1920` 已同步到 `product.template`

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
