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

- [ ] T-014 ｜ sale_product_hover ｜ P1 ｜ 报价单 / 销售订单产品行鼠标悬浮显示产品详情浮层
  - 需求：在报价单与销售订单的订单行列表上，鼠标悬停某一行时弹出浮层，展示该行产品的图片、名称、型号、描述、价格（产品售价与本单单价）、可用库存；移开鼠标后浮层消失（或延迟关闭）。
  - **设计约束**（动工前必读，不得自行放宽）：
    1. **不改官方视图与核心源码**：不新增字段、不加隐藏列、不改 `sale` 的视图 / 动作；只 `_inherit` 扩展与前端 patch。
    2. **只对 `sale.order.line` 列表生效**：其他模型（采购行、发票行等）的列表不得出现浮层。
    3. **不影响原有行点击与编辑**：浮层渲染在 overlay 容器，不改变表格 DOM；编辑态（`props.list.editedRecord`）不弹浮层。
    4. **不新增权限配置**：只读产品既有字段，控制器以当前用户身份读取（不用 `sudo`），沿用产品 / 订单行既有权限。
    5. **源语言英文（`en_US`）**：界面文案写英文，中文译文进 `i18n/zh_CN.po`；含应用列表元数据 3 条（4.8）。
    6. **性能**：每页列表只发一次批量 payload（按行 id），鼠标悬停不再发请求；缓存放模块级非 reactive `Map`，禁止挂到 reactive 对象上（参考 `product_card_view` P1 踩坑）。
  - **验收标准**：
    - [ ] 报价单（`draft` / `sent`）与销售订单（`sale`）的订单行列表，悬停行后浮层显示产品图片 / 名称 / 型号 / 描述 / 售价 / 本单单价 / 可用库存
    - [ ] 鼠标移开后浮层消失；移入浮层内部不关闭；快速划过不弹出
    - [ ] 悬停/移开不影响行的点击进入、编辑、勾选与删除等原操作
    - [ ] 采购订单行、发票行等非销售订单行列表不出现浮层
    - [ ] 未保存的新行不弹浮层且无报错；产品无图片时显示占位图标
    - [ ] 英文（默认）与中文（安装 `zh_CN` 后）界面文案均正确
    - [ ] `-u sale_product_hover` 升级无报错，控制台无 JS 报错

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
