# TODO

> 本文件是**待处理需求**的唯一入口。仅记录待办 / 进行中 / 搁置项——已完成的需求不在本文件留存，其文档与说明归档在各模块的 `README.md` / `CHANGELOG.md` / `AGENTS.md` 与根 [`README.md`](README.md) 模块一览表。
> 新需求追加到「待办池」末尾，开工移入「进行中」，验收通过后整条移出本文件（信息沉淀到模块文档）。

## 追加规则

1. **新需求一律追加到「待办池」末尾**，ID 顺序递增（`T-001` → `T-002` → …），不要插队、不要重排已有 ID。
2. 一行一项，格式：`- [ ] T-0xx ｜ 模块名 ｜ P0/P1/P2 ｜ 需求一句话描述`。
3. **开工**：整行剪切到「进行中」，并在下方补「验收标准」清单。
4. **完成**：验收通过后整条移出本文件；完成信息（日期 / 落地版本 / 验收记录 / 异常情况与后续维护）沉淀到对应模块的 `CHANGELOG.md` 与 `README.md` / `AGENTS.md`，根 `README.md` 模块一览表更新模块状态。
5. 暂时不做：移入「搁置 / 放弃」并写明原因，不删除，保留决策痕迹。
6. 一个需求对应一个模块；跨模块需求在「模块」列用 `+` 连接（如 `product_reference + web_image_paste`）。
7. 需求被拆解时，子项直接在条目下用缩进 `- [ ]` 列出，不单独占用顶层 ID。

## 状态与优先级

| 标记 | 含义 |
|------|------|
| 🔜 | 待办（在待办池中排队） |
| 🚧 | 进行中（已开工，未验收） |
| ⏸️ | 搁置 / 放弃（附原因） |
| P0 | 阻塞日常业务，优先做 |
| P1 | 重要但不阻塞 |
| P2 | 优化 / 体验类，有空再做 |

> 已完成（✅）的需求不再在本文件留存；模块当前状态见根 `README.md` 模块一览表。

---

## 进行中

- [ ] T-010 ｜ product_image ｜ P1 ｜ 产品变体多图：图库增加变体维度（变体各自维护独立图集），变体独立编辑表单 `product_variant_easy_edit_view` 右上角图片区以多图 widget 替换原生单图，模板表单图片扩展保持不变

    需求来源：2026-09-08 会话（确保 product_image 扩展同样应用到 Product Variants 的产品图片）。
    设计约束：
    - `product.image.gallery` 需加变体维度（Many2one `product.product`），否则 `product.template` 上字段经 `_inherits` 对所有变体共享、无法做到「变体各自独立图集」；
    - `product.product` 因 `_inherits = {'product.template': 'product_tmpl_id'}`，图库 One2many 定义在 template 上会共享，变体独立图库需在 `product.product` 上新增独立 One2many（新反向 FK），避免与模板共享补充图 `image_gallery_ids` 混淆；
    - 模板表单（Products 默认入口）图片扩展保持不变；既有 `image_gallery_ids` 语义与模板表单行为不得回归；
    - 主图在变体上为原生计算字段 `image_1920`（无变体图时回退模板图），写主图/删除/提升沿用原生 inverse 落库逻辑；
    - 图库名称唯一约束需按「模板级图 / 变体级图」各自作用域生效；
    - 版本递增与模块 i18n/README/AGENTS/CHANGELOG 同步、交付附「待验证清单」。
    验收标准：
    1. 多属性模板的每个变体可各自上传/浏览/删除/重排一组专属补充图，互不串扰；
    2. `product_variant_easy_edit_view` 图片区用多图 widget，上传、删除主图自动提升、拖动重排等对变体图集生效；
    3. 模板表单图片区仍走既有模板共享补充图，行为不变；
    4. 名称唯一约束按变体维度校验正确、错误提示可读；
    5. 中英文界面文案齐全；模块文档与版本同步。

> T-005（product_image 图片管理弹窗增强）已于 2026-09-06 完成并移除，落地版本 `19.0.2.4.2`；
> 完成信息（日期 / 落地版本 / 验收记录 / 异常与后续维护）见
> [`product_image/CHANGELOG.md`](product_image/CHANGELOG.md) →「交付记录（T-005）」，
> 坑点与解法见 [`product_image/AGENTS.md`](product_image/AGENTS.md) →「开发复盘与关键经验（T-005）」。
>
> T-009（product_packing 产品包装信息）已于 2026-09-08 完成并移除，落地版本 `19.0.1.1.2`；
> 完成信息见 [`product_packing/CHANGELOG.md`](product_packing/CHANGELOG.md) →「交付记录（T-009）」。

---



## 待办池

（空）

---

## 搁置 / 放弃

（空）
