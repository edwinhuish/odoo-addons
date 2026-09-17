# TODO

> 本文件是**待处理需求**的唯一入口。仅记录待办 / 进行中 / 搁置项——已完成的需求移入文末「已归档」，只留一行摘要便于追溯，详细说明与验收记录沉淀到各模块的 `README.md` / `CHANGELOG.md` / `AGENTS.md` 与根 [`README.md`](README.md) 模块一览表。
> 新需求追加到「待办池」末尾，开工移入「进行中」，验收通过后整条移出「待办池 / 进行中」（信息沉淀到模块文档）。

## 追加规则

1. **新需求一律追加到「待办池」末尾**，ID 顺序递增（`T-001` → `T-002` → …），不要插队、不要重排已有 ID。
2. 一行一项，格式：`- [ ] T-0xx ｜ 模块名 ｜ P0/P1/P2 ｜ 需求一句话描述`。
3. **开工**：整行剪切到「进行中」，并在下方补「验收标准」清单。
4. **完成**：验收通过后整条移出「待办池 / 进行中」，在文末「已归档」补一行摘要（完成日期 / 落地版本 / 验收记录位置 / 遗留项）；完成信息（日期 / 落地版本 / 验收记录 / 异常情况与后续维护）沉淀到对应模块的 `CHANGELOG.md` 与 `README.md` / `AGENTS.md`，根 `README.md` 模块一览表更新模块状态。
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

（空）

---

## 待办池

（空）

---

## 搁置 / 放弃

（空）

---

## 已归档

> 已完成需求不在「待办池 / 进行中」留存，仅在此留一行摘要以便追溯；
> 完整验收记录见各模块 `CHANGELOG.md` →「验收记录（T-0xx）」与根 [`README.md`](README.md) 模块一览表。

- **T-014 订单行产品悬浮卡** ｜ `sale_product_hover` ｜ P1
  - 完成日期：2026-09-17 ｜ 状态：**已完成**
  - 落地版本：`19.0.1.6.0`（首版 `19.0.1.0.0`，2026-09-12 ~ 2026-09-16 共 15 个版本）
  - 做法：patch `web.ListRenderer` + popover 浮层展示**产品详情**（图片 / 名称 / 型号 / 规格 / 描述 / 可用库存，**不含任何价格**）；document 捕获阶段事件委托 + 行 `data-id` 反查归属；已保存行走批量 payload、**未保存新行前端按 `product_id` 直读产品**；浮层跟随鼠标并屏蔽行内原生 tooltip，触屏长按；不改官方视图、不新增字段 / 权限
  - 验收记录：模块 [`README.md`](sale_product_hover/README.md) →「验证清单」与 [`CHANGELOG.md`](sale_product_hover/CHANGELOG.md) →「验收记录（T-014）」
  - 异常与维护：17 条坑点档案（现象 / 原因 / 规避）见 [`IMPLEMENTATION.md`](sale_product_hover/IMPLEMENTATION.md)、约束与陷阱见 [`AGENTS.md`](sale_product_hover/AGENTS.md)、过程复盘与排障脚本见 [`RETROSPECTIVE.md`](sale_product_hover/RETROSPECTIVE.md)
  - 遗留：无阻断项；后续若在目标环境发现偏差，按模块 `README.md` →「验证清单」逐条复核（控制台 `[sale_product_hover]` 开头日志为排障入口）

- **T-013 应用列表（Apps）中文名称与描述** ｜ `sale_order_no` + `web_image_paste` + `product_reference` + `product_image` + `product_packing` + `product_card_view` ｜ P1
  - 完成日期：2026-09-09 ｜ 状态：**目标环境验收通过**（6 项验收标准全部通过，中英文各验一遍）
  - 落地版本：`sale_order_no` `19.0.1.8.1`、`web_image_paste` `19.0.2.1.1`、`product_reference` `19.0.2.5.1`、`product_image` `19.0.2.6.3`、`product_packing` `19.0.1.1.3`、`product_card_view` `19.0.2.0.1`
  - 做法：各模块 `i18n/zh_CN.po` 补 `model:ir.module.module,shortdesc|summary|description:base.module_<module>` 三条 + 自定义分类段 `model:ir.module.category,name:base.module_category_<...>`；`__manifest__.py` 的 `name` / `summary` / `description` 仍保持英文源文本
  - 验收记录：各模块 `CHANGELOG.md` →「验收记录（T-013）」；总览见根 [`README.md`](README.md) →「应用列表（Apps）中文化」
  - 规范沉淀：根 [`AGENTS.md`](AGENTS.md) 4.8「应用列表元数据翻译规范」、[`DOCS_TEMPLATE.md`](DOCS_TEMPLATE.md) →「新模块 i18n 必备清单」
  - 遗留：`web_multi_tabs` 的 `19.0.2.0.0` 已按同一规范写入元数据，但整包升级仍待目标环境验证（见其 `README.md` →「验证清单」）
- **T-012 产品列表卡片视图**：2026-09-09 完成，落地版本 `product_card_view` `19.0.2.0.0`
  ——Card 视图入口（库存 → Products 切换器）已确认；卡片内容 / 多图 / 变体 / Sales / Purchase 入口 /
  双语 / 权限待目标环境复验，清单见 [`product_card_view/README.md`](product_card_view/README.md)
  →「验证清单」「遗留问题」；技术设计与踩坑见 [`product_card_view/AGENTS.md`](product_card_view/AGENTS.md)。
- **T-011 产品参考号界面改造 + 多变体参考号不共用**：2026-09-08 验收通过，落地版本
  `19.0.2.5.0`，记录见 [`product_reference/CHANGELOG.md`](product_reference/CHANGELOG.md)   →「验收记录（T-011）」。
