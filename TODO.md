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
8. **可选：`检测：` 条件**（给 `task todo` 看板用）。在条目下缩进写一行
   `- 检测：<路径> 含 <正则>` / `- 检测：<路径> 不含 <正则>` / `- 检测：<路径> 存在`
   （路径相对仓库根，支持目录与 glob；写多行则全部满足才算「可能已实现」）。
   它是「已实现」的**必要条件**，不是验收结论；语法由 `task check` 校验、状态由 `task todo` 执行；
   条目归档时这几行跟着一起移走，脚本里不维护任何清单。

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

- [ ] T-021 ｜ `product_packing` + `product_variant_conversion` ｜ P2 ｜ 产品尺寸 → 原生 Volume 的同步在多变体产品上不再落到变体
  - 背景：`product_packing` 的产品尺寸靠写模板侧 `volume` 同步，而 Odoo 的桥接写入（`_set_product_variant_field()`）只在单变体时落到变体（见模块 `AGENTS.md` → L2 P5「同步规则」）；产品一旦变成多变体，改尺寸不再更新任何变体的 Volume —— 原生行为与该模块的假设冲突
  - 建议：改为按变体写入（建议命名 `_sync_volume_to_variants()`，只写各变体侧的 `volume`）；先在一个多变体产品上复现现状再定方案
  - 关联：`product_packing/AGENTS.md`；`product_variant_conversion/AGENTS.md` → L2 P5
  - 检测：product_packing/models/ 含 _sync_volume_to_variants


---

## 搁置 / 放弃

（空）

---

## 已归档

> 已完成需求不在「待办池 / 进行中」留存，仅在此留一行摘要以便追溯；
> 完整验收记录见各模块 `CHANGELOG.md` →「验收记录（T-0xx）」与根 [`README.md`](README.md) 模块一览表。

- **T-022 价格数据按变体分离（供应商价格 / 价格表规则不再被所有变体共用）** ｜ `product_variant_conversion` ｜ P2
  - 完成日期：2026-09-22 ｜ 状态：**已交付，待目标环境验证**
  - 落地版本：`19.0.3.4.0`
  - 起因：模板级价格记录是「一条记录被所有变体共用」，改一个变体就会影响全部变体，与「变体的价格要各自独立」冲突
  - 做法：默认把本产品模板级的供应商价格（`supplierinfo.product_id` 为空）与价格表规则（`applied_on = '1_product'`）**按变体各复制一份（数值不变）后删除原记录**；新变体从谱系来源继承；`3_global` / `2_product_category` 规则绝不触碰；系统参数 `product_variant_conversion.separate_variant_prices` 可关闭；弹窗勾选框（默认不勾选）勾上时供应商价格退回模板级共享
  - 安全线：① 变体在同一「价格表 + 数量门槛」上已有自己的规则时不覆盖（避免静默改价）；② 后置断言校验「供应商价格只多不少、原有变体实际售价一分未变、新变体售价与其来源一致」，不符即整单回滚
  - 验收记录：模块 [`README.md`](product_variant_conversion/README.md) →「价格数据按变体分离」「验证清单」与 [`CHANGELOG.md`](product_variant_conversion/CHANGELOG.md) → `[19.0.3.4.0]`；两个环境各 28 项自动化测试全部通过
  - 遗留：目标环境需验证「转换后各变体价格可独立修改」「模板级记录被拆成各变体一份」「关闭系统参数后保持模板级」；新变体仍不自动获得补货规则（见待办池 `T-021` 与模块 README →「已知边界」）

- **T-024 产品详情页移除「Variant Lineage」页签** ｜ `product_variant_conversion` ｜ P2
  - 完成日期：2026-09-22 ｜ 状态：**已交付，待目标环境验证**（本条目当日提出、当日完成，未在待办池停留）
  - 落地版本：`19.0.3.5.0`
  - 起因：用户反馈产品详情页多出「变体谱系」页签，没有必要出现
  - 做法：删除产品表单上的 `variant_lineage` 页（模型 / 数据 / 其它视图不变）；谱系明细改由 **Conversions** 智能按钮 → 台账**详情页**查看（含来源变体 → 结果变体、`is_kept`、组合前后文本、新增取值与结果变体的参考号 / 条码 / 成本三列）；变体表单 / 列表 / 搜索上的来源追溯不变
  - 验收记录：模块 [`README.md`](product_variant_conversion/README.md) →「视图」「变体来源与归属怎么追溯」「验证清单」与 [`CHANGELOG.md`](product_variant_conversion/CHANGELOG.md) → `[19.0.3.5.0]`；只装 product 环境 28 项自动化测试全部通过
  - 遗留：目标环境需确认产品详情页不再出现该页签、台账详情页可正常打开

- **T-020 扩展点与可维护性（钩子 / chatter / 拆分；批量转换不做）** ｜ `product_variant_conversion` ｜ P2
  - 完成日期：2026-09-22 ｜ 状态：**已交付，待目标环境验证**
  - 落地版本：`19.0.4.0.0`
  - 做法：新增 `_post_variant_conversion_hook(originals, new_variants, anchors)`（保存点内的扩展点，其它模块在此给新变体补数据）；转换完成在产品 chatter 留一条转换记录；价格归属逻辑拆到 `models/product_template_prices.py`
  - **批量转换入口不做**：多产品批量无法逐条确认归属，与「绝不静默改归属」冲突（见模块 `AGENTS.md` →「常见扩展场景」）
  - 验收记录：模块 [`CHANGELOG.md`](product_variant_conversion/CHANGELOG.md) → `[19.0.4.0.0]`；钩子调用与 chatter 留痕有自动化测试
- **T-019 弹窗在手数量 + 测试补齐** ｜ `product_variant_conversion` ｜ P2
  - 完成日期：2026-09-22 ｜ 状态：**已交付，待目标环境验证**
  - 落地版本：`19.0.4.0.0`
  - 做法：预览的 `on_hand` 改为「未装 stock / 无权限时为 null」，弹窗在既有变体选项后附「在手 N」；归属载荷构造 / 未分配计数抽成纯函数（`buildOwnershipPayload()` / `countUnassigned()`）；补测多记录写入、归档变体、dynamic 属性三个分支
  - 验收记录：模块 [`README.md`](product_variant_conversion/README.md) →「验证清单」；两个环境各 38 项自动化测试全部通过
  - 遗留：Hoot 前端单测未做（本仓库尚无前端测试基建）；combo 与「组合被排除」两分支仍未自动化测试
- **T-018 组合数前置上限 + 试写加锁 + 归档取值措辞** ｜ `product_variant_conversion` ｜ P2
  - 完成日期：2026-09-22 ｜ 状态：**已交付，待目标环境验证**
  - 落地版本：`19.0.4.0.0`
  - 做法：`_check_variant_conversion_combination_cap()` 用「各属性有效取值数乘积」在枚举前对照 `product.dynamic_variant_limit` 拒绝（分析与转换两条路都拦）；`write()` 在分析前对模板行 `FOR UPDATE`；取值被归档的报错单独措辞（指向「恢复取值」）
  - 验收记录：模块 [`CHANGELOG.md`](product_variant_conversion/CHANGELOG.md) → `[19.0.4.0.0]`；上限拒绝有自动化测试
- **T-017 属性主数据路径的拦截** ｜ `product_variant_conversion` ｜ P1
  - 完成日期：2026-09-22 ｜ 状态：**已交付，待目标环境验证**
  - 落地版本：`19.0.4.0.0`（新增 `models/product_attribute_guards.py`）
  - 做法：三道闸 —— `product.template.attribute.value.unlink()`（在用变体仍携带时拒绝）、`product.attribute.value.unlink()`（正被产品使用时拒绝）、`product.template.attribute.line.unlink()` / `.write()`（删行 / 移走取值时拒绝）；`create_product_product=False` 的沙盒写入放行；报错给出「先处理变体」的出路
  - 验收记录：模块 [`README.md`](product_variant_conversion/README.md) →「验证清单」与 [`AGENTS.md`](product_variant_conversion/AGENTS.md) → L1 约束 17；5 项自动化测试
  - 遗留：**归档**属性取值不拦（Odoo 原生也不拦），归档后变体仍带着该取值——处置办法与删取值相同（见模块 `README.md` →「已知边界」）

- **T-023 原产品资料保留给指定变体 + 供应商价格勾选框默认不勾选** ｜ `product_variant_conversion` ｜ P1
  - 完成日期：2026-09-22 ｜ 状态：**已交付，待目标环境验证**（本条目当日提出、当日完成，未在待办池停留）
  - 落地版本：`19.0.3.3.0`
  - 核实结论：**原产品资料无需转移** —— 弹窗里被指定承载某个组合的那条变体，就是原 `product.product` 记录本身（id 不变）；内部参考号 / 条码 / 按变体的供应商价格（`supplierinfo.product_id`）/ 按变体的价格表规则（`applied_on = 0_product_variant`）/ 补货规则（`orderpoint.product_id`）本来都挂在它身上，「已属于该变体」的记录不动、模板级记录保持模板级
  - 做法：弹窗供应商价格勾选框默认值改为**不勾选**（勾选后仍是「改为适用于全部变体、所有变体统一为同一批数值」）；`_share_vendor_prices_with_variants()` 显式化守卫并返回被改写的记录集；新增 4 项测试把结论钉住（**未新增搬数据的代码**）
  - 验收记录：模块 [`README.md`](product_variant_conversion/README.md) →「已有业务数据怎么处理」「验证清单」与 [`CHANGELOG.md`](product_variant_conversion/CHANGELOG.md) → `[19.0.3.3.0]`；两个环境（只装 product / 加装 stock+sale）各 25 项自动化测试全部通过
  - 遗留：目标环境需验证弹窗勾选框默认未勾选、勾选后所有变体取到同一价格（清单见模块 `README.md` →「验证清单」）

- **T-016 变体级数据按谱系继承（属性归属审计 + 新变体继承 + 可开关）** ｜ `product_variant_conversion` ｜ P1
  - 完成日期：2026-09-22 ｜ 状态：**已交付，待目标环境验证**
  - 落地版本：`19.0.3.1.0`（属性归属审计 + 结果变体的变体级属性关联展示）、`19.0.3.2.0`（新变体按谱系继承 + 系统参数开关）
  - 核实结论：**不需要任何数据迁移** —— 条码 / 成本 / 体积 / 重量 / 内部参考号的真身在变体上（`product.product` 自有的存储字段覆盖了 `_inherits` 委托来的模板字段），而本模块保留原 `product.product` 记录 → 默认变体天然带着原值；模板级（销售价 / 税 / 计量单位 / `product_packing` 的纸箱与产品尺寸）全变体共享。唯一变化是多变体后产品表单上那几个桥接字段显示空 / 0（Odoo 原生语义，任何多变体产品都一样）
  - 做法：`product.variant.lineage` 加三个**非存储 `related`** 字段（`result_default_code` / `result_barcode` / `result_standard_price`）在谱系与台账里展示结果变体带着什么；`_apply_variant_data_inheritance()` 按 `variant_origin_id`（`Derived From`）复制新变体的成本 / 体积 / 重量，系统参数 `product_variant_conversion.inherit_variant_data` 可关；台账加 `inherit_variant_data` 记录；参考号与条码因硬约束刻意不继承（`product_reference` 的「多变体不共用」/ `_check_barcode_uniqueness()` 唯一性）
  - 验收记录：模块 [`README.md`](product_variant_conversion/README.md) →「属性归属审计」「新变体继承策略」「验证清单」与 [`CHANGELOG.md`](product_variant_conversion/CHANGELOG.md) → `[19.0.3.1.0]` / `[19.0.3.2.0]`；两个环境（只装 product / 加装 stock+sale）各 21 项自动化测试全部通过
  - 异常与维护：字段层级由 `test_field_storage_layers_match_the_audit()` 钉成升级闸门（Odoo 改存储层会先失败）；继承范围与来源见模块 [`AGENTS.md`](product_variant_conversion/AGENTS.md) → L1 约束 15 与 L2 P5
  - 遗留：目标环境需验证「Variant Lineage 页新增三列 + 提示文案」「继承后的成本 / 体积 / 重量」的界面表现（清单见模块 `README.md` →「验证清单」）；供应商价格仍是一刀切共享、会抹平价差，拟改为按谱系逐变体继承（见待办池 `T-022`）

- **T-015 产品变体转换（追加属性 / 取值而不丢变体 + 归属谱系）** ｜ `product_variant_conversion` ｜ P1
  - 完成日期：2026-09-21 ｜ 状态：**已交付，待目标环境验证**
  - 落地版本：`19.0.3.0.0`（新建模块；`19.0.1.0.0` 是只支持单变体产品的开发期中间版本、`19.0.2.0.0` 用「按钮 + 向导」，均已被取代；技术名在交付前由 `product_variant_convert` 定名调整为 `product_variant_conversion`，见模块 `CHANGELOG.md`）
  - 做法：**入口是保存拦截、不是按钮**——前端 patch `FormController.onWillSaveRecord`（官方保存前钩子，返回 false 即阻止保存），保存前调 `get_variant_conversion_preview()`；服务端用带 `create_product_product=False` 的「只写配置、不碰变体」试写分析判定三种结局（不影响变体→原生保存；会新增变体→无归属映射就拦住、有映射先安全转换再落库；会丢变体→拒绝）；归属由弹窗逐组合确认「由哪条既有变体继续承载」（默认已填好），确认前不保存，确认后归属随技术字段 `variant_conversion_mapping` 与属性变更同一次写库；转换内部按归属把**每条**既有变体锚定到自己的组合再调 `_create_variant_ids()` 逐条复用、只新建缺失组合，全程 `savepoint` + 前置校验 + 后置断言；同时写 `product.variant.conversion` 台账与 `product.variant.lineage` 谱系，并在 `product.product` 上留下可搜索的「所属转换 / 来源变体」
  - 验收记录：模块 [`README.md`](product_variant_conversion/README.md) →「验证清单」与 [`CHANGELOG.md`](product_variant_conversion/CHANGELOG.md) →「验收记录」；本地两个环境（只装 `product` / 加装 `stock`+`sale_management`）各 `task test -- product_variant_conversion,stock,sale_management --test-tags=/product_variant_conversion` 17 项全部通过
  - 异常与维护：Odoo 19 变体生成 / 删除机制的四条源码事实、试写分析的必要性、归属与来源判定算法见模块 [`AGENTS.md`](product_variant_conversion/AGENTS.md) → L2 P1；保存前钩子 `onWillSaveRecord(record, changes)` 的机制、`create_product_product` 递归陷阱、`assets` 新增文件必须 `-u` 见 L2 P4；字段级 `domain` 被服务端求值、内联元素整体成术语、模型描述撞模块名等 i18n / 命名坑见 L2 P2 / P3；后置断言用的 `_filter_combinations_impossible_by_config()` 属 Odoo 内部 API，升级需回归
  - 遗留：目标环境弹窗交互（默认归属 / 下拉改选 / 未分配完不可确认 / 取消不保存）与中英文界面待验证（清单见模块 `README.md` →「验证清单」）；本流程不支持「删除已有取值 / 删除属性」与「带归档变体的产品」，多记录写入也只做拒绝保护（见模块 `README.md` →「使用前提与限制」）
  - 后续迭代：`19.0.3.0.2` 完成场景覆盖 / 数据流 / 一致性边界评估后，把 8 条边界与 5 类改进整理成待办池 `T-016` ~ `T-020`（变体级数据按谱系继承、属性主数据路径拦截、组合枚举前置上限、弹窗展示在手数量与测试补齐、扩展点与可维护性），评估结论见模块 [`README.md`](product_variant_conversion/README.md) →「场景覆盖矩阵 / 数据流 / 价格与库存的同步规则 / 已知边界」与 [`AGENTS.md`](product_variant_conversion/AGENTS.md) → L2 P5

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
