# 变更日志

> 倒序排列，最新版本在最前。每版本固定三段式：变更 / 影响 / 文档。
> 版本号规则见根 `AGENTS.md` 第 3 节：架构/破坏性 +x，功能新增 +y，修复/文档 +z。

## [19.0.4.0.0] - 2026-09-22（T-017 / T-018 / T-019 / T-020 一次交付）

### 变更

- **T-017 属性主数据路径的拦截**（新增 `models/product_attribute_guards.py`，三个模型四道闸）：
  - `product.template.attribute.value.unlink()`：仍有在用变体携带该取值时拒绝（原生会把它们连坐删 / 归档）；
  - `product.attribute.value.unlink()`：正被产品使用的取值不允许删（会破坏变体组合）；
  - `product.template.attribute.line.unlink()` / `.write()`：直接删属性行、写 `value_ids` 移走在用变体携带的取值时拒绝；
  - `create_product_product=False` 的沙盒写入放行（与 L1 约束 10 同源）；报错都给出「先处理变体」的出路。
- **T-018 健壮性**：
  - 组合数**前置上限**：`_check_variant_conversion_combination_cap()` 用「各属性有效取值数乘积」在
    `itertools.product` 枚举**之前**对照 `product.dynamic_variant_limit` 拒绝（分析与转换两条路都拦）；
  - `write()` 在分析**之前**对模板行 `FOR UPDATE`（并发下分析结论不再可能过期）；
  - 取值被归档导致的「会丢变体」报错单独措辞，指向「先恢复取值」而不是「先删变体」。
- **T-019 在手数量与测试**：
  - 预览的 `on_hand` 改为「未装 stock / 无权限时为 null」，弹窗据此在每条既有变体选项后附「在手 N」；
  - 归属载荷构造与未分配计数抽成纯函数（`buildOwnershipPayload()` / `countUnassigned()`，供单测复用）；
  - 补测未覆盖分支：多记录写入、归档变体、dynamic 属性（combo 因构造组合产品需要先配 choice 而未测）。
- **T-020 扩展点与可维护性**：
  - 新增 `_post_variant_conversion_hook(originals, new_variants, anchors)`（保存点内的扩展点，其它模块在此给新变体补数据）；
  - 转换完成后在产品 chatter 留一条转换记录（`_log_variant_conversion()`）；
  - 价格归属逻辑拆到 `models/product_template_prices.py`；
  - **批量转换入口不做**：多产品批量无法逐条确认归属，与「绝不静默改归属」冲突（已写入 AGENTS）。

### 影响

- **行为变化**：属性主数据里删除被变体使用的取值 / 属性行会被拒绝（此前是静默删 / 归档变体）——
  这是本模块承诺的补全；报错里给出处置办法
- 新增 2 个模型文件（守卫 / 价格拆分）；无数据结构变化、无迁移
- i18n +12 条；测试 28 → 38 项

### 文档

- 模块 `README.md`：功能概述 / 已知边界（归档取值不拦、combo 未测）/ 验证清单同步
- 模块 `AGENTS.md`：新增 L1 约束 17（属性主数据拦截）；文件职责与缺口清单同步；「常见扩展场景」注明批量转换不做的原因
- 仓库 `TODO.md`：T-017 / T-018 / T-019 / T-020 交付归档

---

## [19.0.3.5.0] - 2026-09-22（产品详情页移除「Variant Lineage」页签）

### 变更

- **产品表单不再显示「Variant Lineage」页**（用户反馈：产品详情页多出一个多数时候用不上的页签）。
  谱系明细与归属信息没有丢，都还在：
  - **Conversions** 智能按钮 → 转换台账**详情页**（每条结果变体一行：来源变体 → 结果变体、
    `is_kept`、转换前后的组合文本、新增取值，以及上一版加的参考号 / 条码 / 成本三列）；
  - **变体表单 / 变体列表 / 变体搜索**上的「来源变体 / 所属转换」（`variant_origin_id` / `variant_conversion_id`）不变；
  - 产品搜索「With Converted Variants」筛选不变。

### 影响

- 只删视图页签，模型 / 数据 / 其它视图不变；`-u` 升级 + 强刷浏览器即可
- 模块 `README.md` 的「变体来源与归属怎么追溯」「视图」「操作」「验证清单」同步改为指向台账详情页

### 文档

- 模块 `AGENTS.md` → 文件职责注明「刻意不加谱系页」
- 仓库 `TODO.md`：登记并归档 `T-024`（当日提出、当日完成）

---

## [19.0.3.4.0] - 2026-09-22（价格数据按变体分离：改一个变体的价格不再牵动别的变体）

### 变更

- **默认把价格数据按变体分离**（新增系统参数 `product_variant_conversion.separate_variant_prices`，默认开启）：
  - 本产品**模板级**的供应商价格（`supplierinfo.product_id` 为空）与价格表规则（`applied_on = '1_product'`）
    **按变体各复制一份（数值不变）后删除原记录** → 从此每条变体一份、各自可改；
  - **新变体**从谱系来源（`Derived From`）继承一份；来源没有就留空；
  - `3_global`（所有产品）与 `2_product_category`（按分类）的价格表规则**绝不触碰**；
  - 弹窗「把这些变体的供应商价格应用到全部变体」勾选框（默认不勾选）保留原语义：勾上则退回模板级共享；
    价格表规则始终按变体分离（与勾选框无关）。
- **两道安全线**（避免拆分过程中静默改价）：
  1. 变体在同一「价格表 + 数量门槛」上已有自己的规则时，模板级规则**不再拆过去**（否则会多出一条同档规则、
     把原来生效的那条挤掉）；
  2. 新增 `_check_variant_price_separation()` 后置断言：分离前后「供应商价格只多不少、**原有变体的实际售价一分未变**、
     新变体售价与其来源一致」（用 `pricelist._get_product_price()` 逐价格表 / 逐门槛比对），不符即整单回滚。
- 转换台账新增 `separate_variant_prices` 字段（列表可选列 + 详情页）。
- `_share_vendor_prices_with_variants()` 保持「只改按变体记录」的守卫，并返回被改写的记录集。

### 影响

- **行为变化（重要）**：转换后模板级的价格记录会被拆分并删除 —— 值完整保留在各变体上（有断言保证售价不变），
  但**记录条数会变多**（每条变体一份）。不想要这个行为就把系统参数 `separate_variant_prices` 设为 `0`。
- 新增 1 个存储布尔字段（`product.variant.conversion.separate_variant_prices`）→ 有列新增，`-u` 自动完成，无迁移脚本
- 测试 25 → 28 项

### 文档

- 模块 `README.md`：新增「价格数据按变体分离（默认）」小节（含两条安全线与关闭方式）；「价格与库存的同步规则」
  「新变体继承策略」「已有业务数据怎么处理」「模型字段」「已知边界」「后续迭代」「验证清单」同步
- 模块 `AGENTS.md`：新增 L1 约束 16（价格按变体分离）；L2 P5 同步规则更新、缺口 3 标记为已解决
- 仓库 `TODO.md`：`T-022` 落地 → 归档

---

## [19.0.3.3.0] - 2026-09-22（原产品资料保留核查 + 供应商价格勾选框默认不勾选）

### 变更

- **供应商价格勾选框默认值改为「不勾选」**：`VariantConversionDialog` 的 `shareVendorPrices` 初值由 `true` 改为 `false`。
  勾选后仍是原行为：`product_id` 指向既有变体的价格记录改为模板级「适用于全部变体」，**所有变体取到同一批数值**；
  不勾选（默认）则价格只对原来那条变体生效。
- **`_share_vendor_prices_with_variants()` 显式化守卫并返回被改写的记录集**：只改 `product_id` 指向既有变体的记录；
  本来就是模板级（对所有变体生效）的记录不动 —— 「已属于全部变体就不需要转移」，便于调用方 / 测试核对。
- **「把原产品资料保留给指定变体」= 保留原记录本身，确认无需转移**（本轮用测试钉住，**没有**新增搬数据的代码）：
  内部参考号 / 条码 / 按变体的供应商价格（`supplierinfo.product_id`）/ 按变体的价格表规则
  （`pricelist.item.applied_on = 0_product_variant`）/ 补货规则（`orderpoint.product_id`）本来就在被指定的那条
  变体（原 `product.product` 记录，id 不变）上；模板级记录保持模板级。

### 影响

- 行为变化：**弹窗里供应商价格默认不再共享** —— 要共享得主动勾选（避免无意中抹平同一供应商对不同变体的价差）
- 无数据结构变化、无迁移脚本；JS 改动需 `-u` + 强刷浏览器
- 测试 21 → 25 项（新增：原产品资料保留、补货规则保留、共享只改按变体记录、共享后所有变体同价）

### 文档

- 模块 `README.md`：「已有业务数据怎么处理」新增「为什么不需要转移」说明段，并逐类更新数据状态；
  功能概述 / 操作步骤 / 价格与库存同步规则 / 新变体继承策略 / 已知边界 / 验证清单同步勾选框默认值
- 模块 `AGENTS.md` → L2 P5「同步规则」补「原产品资料不需要转移」与共享守卫两条；文件职责与缺口清单同步
- 仓库 `TODO.md`：登记并归档 `T-023`（本条目当日提出、当日完成）

---

## [19.0.3.2.0] - 2026-09-22（T-016 完成：新变体按谱系继承，可开关）

### 变更

- **新变体按谱系继承变体级数据**：`_apply_variant_data_inheritance()` 把新变体的
  **成本 `standard_price` / 体积 `volume` / 重量 `weight`** 从它的谱系来源（`Derived From`，即 `variant_origin_id`）复制过来，
  在转换第 ⑦ 步（写完谱系之后）执行；来源为空时跳过该变体，保持空值、不做猜测。
- **可配置**：系统参数 `product_variant_conversion.inherit_variant_data`，默认开启；
  设为 `0` / `false` / `no` / `off` 则新变体保持 Odoo 默认的空 / 0。
- **刻意不继承**（各有硬约束，详见 README →「新变体继承策略」）：
  - 内部参考号 `default_code`：本仓库 `product_reference` 的 L1 约束「多变体产品不共用参考号」；
  - 条码 `barcode`：`product.product._check_barcode_uniqueness()` 有唯一性约束，复制必然报错；
  - 价格表规则 / 补货规则：规则各自带适用条件，盲目复制会产生重复规则（`T-022` / 另议）；
  - 供应商价格：仍由弹窗勾选框决定（拟升级为按谱系逐变体继承，`T-022`）。
- 转换台账新增 `inherit_variant_data` 字段（列表可选列 + 详情页），记录本次是否启用了继承。

### 影响

- **行为变化**：默认开启继承 → 转换后新变体的成本 / 体积 / 重量不再为空 / 0，而是等于来源变体的值；
  需要旧行为就把系统参数设为 `0`
- 新增 1 个存储布尔字段（`product.variant.conversion.inherit_variant_data`）→ 有列新增，`-u` 自动完成，无迁移脚本
- 测试 19 → 21 项

### 文档

- 模块 `README.md` 新增「新变体继承策略」表（继承什么 / 不继承什么 / 为什么 + 关闭方式）；
  「属性归属审计」「已知边界」「后续迭代」「模型字段」「验证清单」同步更新
- 模块 `AGENTS.md` 新增 L1 约束 15（继承范围与来源）；L2 P5 同步规则与缺口清单同步（缺口 2 标记为已解决）
- 仓库 `TODO.md`：`T-016` 四项验收标准全部完成 → 归档；新增 `T-022`（供应商价格按谱系逐变体继承）

---

## [19.0.3.1.0] - 2026-09-22（T-016 核实：属性归属审计 + 变体级属性关联展示）

### 变更

- **核实结论：转换不需要任何数据迁移**（源码 + 自动化测试双重证据）
  - **真身在变体上**：`barcode` / `standard_price` / `volume` / `weight` / `default_code` 都是 `product.product` **自己声明的存储字段**，
    在变体上**覆盖**了 `_inherits` 委托来的模板字段；
  - 模板侧那几个退化为**单变体桥接**（`_compute_template_field_from_variant_field()` / `_set_product_variant_field()`）：
    单变体时读 / 写都落到那条变体；多变体时读出空 / 0、写入**不落任何变体**（Odoo 原生语义）；
  - 本模块保留原 `product.product` 记录（id 不变）→ 默认变体（= 原记录）天然带着全部原值，**一个字节都不用搬**；
  - 模板级字段（销售价、税、计量单位、`product_packing` 的纸箱与产品尺寸）全变体共享，转换根本不碰；
  - 唯一变化是**查看位置**：多变体后产品表单上那几个字段显示空 / 0，真值在对应变体上。
- **前端：把结果变体上的变体级属性关联展示出来**（非存储 `related`，不新增数据库列、不需要迁移）
  - `product.variant.lineage` 新增 `result_default_code` / `result_barcode` / `result_standard_price`；
  - 产品表单 **Variant Lineage** 页与转换台账详情页的谱系表新增这三列，并在产品表单补一句字段归属说明。
- 自动化测试 17 → 19 项：新增 `test_field_storage_layers_match_the_audit()`（字段层级审计，Odoo 改存储层时先失败）
  与 `test_variant_level_values_stay_on_the_kept_variant()`（原值保留 / 新变体为空 / 多变体下模板桥接字段语义 / 谱系关联展示）。

### 影响

- **无数据结构变化**（新字段全部是非存储 `related`）、无迁移脚本；`-u` 升级即可
- 界面新增三列与一句提示文案（中英双语已补）；既有的转换与归属逻辑未改动
- 若你在产品表单上看不到条码 / 成本 / 体积 / 重量：那是 Odoo 多变体产品的原生表现，值在变体表单 / 变体列表里（见 README →「属性归属审计」）

### 文档

- 模块 `README.md` 新增「属性归属审计」表（逐字段：真身 / 单变体时 / 转换后 / 默认变体上的值 / 是否需要迁移）与 `_inherits` + 单变体桥接机制说明
- 模块 `AGENTS.md` → L2 P5「同步规则」补字段归属审计结论、桥接规则，以及 `product_packing` 尺寸 → Volume 在多变体下失效的跨模块注意
- 仓库 `TODO.md`：`T-016` 移入「进行中」（补验收标准）；新增 `T-021`（`product_packing` 的产品尺寸同步在多变体产品上不再落到变体）

---

## [19.0.3.0.2] - 2026-09-21（文档：业务场景覆盖、数据流与一致性边界评估）

### 变更

- **无代码行为变更**，只补文档（`19.0.3.0.1` 的前端修复已实测通过）
- 模块 `README.md` 新增四节：
  - **场景覆盖矩阵**：12 类属性改动的结局（弹窗 / 拒绝 / 放行）与测试覆盖一览
  - **数据流**：从点保存到落库的完整时序（预览 RPC 的试写 + 回滚、三结局分支、转换五步、失败整单回滚）
  - **价格与库存的同步规则**：逐字段说明归属（模板级 / ptav 级 / 变体级），并写明两处代价——「新变体成本为 0」「共享供应商价格会抹平同一供应商对不同变体的价差」
  - **已知边界与后续迭代**：8 条边界 + 5 条迭代方向（带 `TODO.md` 条目号）
- 模块 `AGENTS.md` 新增 L2 **P5：业务场景、数据流与一致性边界**：覆盖矩阵、判据、同步规则、9 条已识别缺口、扩展点表、升级回归的内部 API 清单

### 影响

- 无代码、无视图、无 i18n 变化；照常 `-u` 更新版本号即可，不需要数据迁移

### 文档

- 本轮核实的三条新源码事实已写进文档：
  1. 成本 `standard_price` 是**变体级**字段（模板侧只是单变体时的 compute/inverse 通道）→ 新变体成本为 0；
  2. **删 / 归档属性取值会直接删 / 归档既有变体**（`product.template.attribute.value.unlink()` → `_unlink_or_archive()`），
     直接写 `product.template.attribute.line` 也会自己调 `_create_variant_ids()` —— 两条路都**绕过**本模块的保存拦截；
  3. 采购取价按 `price_discounted → sequence → id`（`product.product._select_seller`）→ 共享供应商价格后会静默只取一条。
- 迭代需求登记进仓库 `TODO.md` 待办池：`T-016` 变体级数据按谱系继承、`T-017` 属性主数据路径拦截、
  `T-018` 组合枚举前置上限与并发锁顺序、`T-019` 弹窗展示在手数量与测试补齐、`T-020` 扩展点与可维护性。

---

## [19.0.3.0.1] - 2026-09-21（修复弹窗确认后的保存错误；本地开发库已验证，待目标环境验证）

### 变更

- **修复：弹窗里点确认后保存报 `Uncaught Promise > this.model.save is not a function`**
  - 根因：`RelationalModel` 上**没有** `save` 方法——保存入口在 `Record` 上（`this.model.root.save()`），
    控制器层另有 `FormController.save()`（它负责挂 `onSaveError`、尊重 `props.saveRecord`、触发 `props.onSave`）
  - 修法：改调 `await this.save()`，并在代码注释里写明正确入口
- **加固：技术字段 `variant_conversion_mapping` 在视图里加 `force_save="1"`**
  - 原因：`Record._getChanges()` 会把「在 activeFields 里、但只读且未标 `forceSave`」的字段从 `changes` 里剔除。
    这个字段承载弹窗确认后的归属映射，一旦有人给它加 `readonly="1"`，映射会静默不随保存提交，
    表现为「确认后保存又被拦一次、弹窗反复出现」，且没有任何报错线索
- 架构与判定逻辑未变（仍是保存拦截 + 归属确认弹窗 + 只增不删）

### 影响

- 只改前端保存调用与一个视图属性，无数据结构变化、无迁移
- 升级后必须强刷浏览器（Ctrl+F5）：前端资源有缓存，不刷新仍会跑到旧代码

### 文档

- 模块 `AGENTS.md` → L2 P4 补两条陷阱：保存入口只能是 `FormController.save()` / `Record.save()`；
  承载前端回传数据的技术字段必须 `force_save="1"`

---

## [19.0.3.0.0] - 2026-09-21（本地开发库已验证，待目标环境验证）

### 验收记录

- 验收日期：2026-09-21
- 验收环境：本地开发库（`dev`）；自动化测试分别在「只装 `product`」与「加装 `stock` + `sale_management`」两种库上跑
- 验收结果：两轮各 17 项测试全部通过（0 failed / 0 error）
  - [x] `-i` / `-u` 无报错（含删除旧的向导模型与视图、加载 3 个前端资源）
  - [x] 加属性但未确认归属 → 写入被拒绝，产品与变体均不变
  - [x] 预览接口给出「是否需要确认 / 改动后的组合 / 既有变体的默认归属」，且自己不改库
  - [x] 确认归属后：2 变体 + 新属性 → 4 变体，两条原记录各自保留自己的组合，另两个组合是新记录
  - [x] 归属可逐条交叉指定；归属漏项 / 重复指向都被拒绝且不改库
  - [x] 给已有属性追加取值同样需要确认；只加单取值属性 / 「不生成变体」属性 / 重提同样配置都不需要确认
  - [x] 删取值 / 删属性行被拒绝（预览给出 blocked 提示）
  - [x] 转换台账、变体谱系、变体来源字段内容正确
  - [x] 两个变体各有库存：预览能看到各自在手数量，转换后库存仍分别挂在原来那条记录上
  - [x] 销售订单行仍指向原来那条变体
  - [ ] 目标环境：保存时弹窗、取消不保存、按钮消失、中英文界面（待验证）

### 变更

- **入口改为「保存时自动检测 + 归属确认弹窗」**，移除产品表单上的「Add Attributes To Variants」按钮与整个向导：
  - 用户照常在原生「属性与变体」页改属性、点保存；
  - 前端 patch `FormController.onWillSaveRecord(record, changes)`（官方保存前钩子，返回 false 即阻止保存），
    保存前调 `product.template.get_variant_conversion_preview()` 问这次改动的影响；
  - 需要确认时弹出新的归属弹窗：按「改动后的组合」逐行选择**由哪条既有变体继续承载**
    （默认值 = 什么都不指定时的结果），每条既有变体必须恰好被指定一次；
  - **用户确认之前保存不继续**（取消 / 关掉弹窗 = 本次不保存，表单保持未保存状态）；
  - 确认后把归属映射放进本次保存的 `changes`（技术字段 `variant_conversion_mapping`）重走一次保存，
    属性变更与归属在同一次写库、同一个事务里落地。
- **`write()` 保存拦截的三种结局**：不影响变体 → 原生保存；会新增变体 → 没有归属映射就拦住（由弹窗接管）/
  有映射就先安全转换再落库；会丢变体（删取值 / 删属性 / 组合数变少）→ 直接拒绝，绝不静默删除
- **新增试写分析 `_analyze_variant_conversion_write()`**：带 `create_product_product=False` 只写配置（属性行 + ptav）
  并在保存点里回滚，既有变体毫发无损。**刻意不用原生写法当判据**——原生写法在「加属性」时本来就会删掉既有变体
- 新增预览 RPC `get_variant_conversion_preview()`，返回 `blocked` / `required` / `variants`（含在手数量）/ `combinations`（含默认归属）
- 新增归属载荷与校验 `_parse_variant_conversion_mapping()`：格式 `{"mapping": [{values, origin_variant_id}], "share_vendor_prices": bool}`，
  校验「每条既有变体恰好一次、取值必须存在、不能两条既有变体占同一组合」；技术字段 `variant_conversion_mapping` 写完即清空
- **新增前端资源**：`static/src/js/variant_conversion_form_patch.js`（保存拦截）、
  `static/src/js/variant_conversion_dialog.js` + `static/src/xml/variant_conversion_dialog.xml`（归属确认弹窗，
  含「把这些变体的供应商价格应用到全部变体」勾选框）
- **删除向导模型**：`product.variant.conversion.wizard` / `.line` / `.variant.line` 与向导视图、对应安全规则
- 供应商价格共享从「向导选项」改成「弹窗勾选框」（默认勾选），语义不变
- 多记录写入保护：一次改多个产品的属性无法逐条记录归属 → 拒绝并提示逐个产品保存
- 新增拦截：产品上有「按需生成变体」的属性时明确提示（那种情况下变体由 Odoo 自己创建，没有归属可确认）
- `_convert_to_multi_variant()` 新增 `previous_attribute_lines` / `added_attributes` 两个可选参数：
  属性行已被 `write()` 写成目标配置后调用时，谱系与台账要用「改动前快照」才不会把来源判空、把新增属性记空

### 影响

- **不需要迁移脚本**：删除的是瞬态向导模型（无历史数据）；`product.template` 只新增一个技术字段 `variant_conversion_mapping`（Text，通常为空）
- **升级后必须强刷浏览器**（Ctrl+F5）：保存拦截与弹窗是前端资源，缓存里没有它们时保存会被服务端拒绝并给出提示
- 产品表单上原来的「Add Attributes To Variants」按钮消失，改为「改属性 → 保存 → 需要时确认归属」
- 已按旧版本转换过的产品不受影响：台账、谱系、变体来源字段与转换逻辑都没变
- 依赖仍只有 `product`；新增的 `stock` 调用（预览里的在手数量）已做存在性与权限降级

### 文档

- 同步更新 `__manifest__.py`（版本 `19.0.3.0.0`、`summary` / `description`、assets 登记）、
  `README.md`（按新流程重写：功能概述 / 核心设计 / 怎么用与归属怎么指定 / 会被拒绝的改动 / 没有弹窗时 / 模块资源 / 验证清单）、
  `AGENTS.md`（L1 扩到 14 条，L2 新增 P4「保存拦截与弹窗」并重写 P1 的判定与来源说明）
- `i18n/zh_CN.po` 用官方导出骨架重建（101 条：删除向导词条，新增弹窗模板与 JS `_t()` 词条、保存拦截的报错文案）
- 根 `README.md` 模块一览表 / 路线图、根 `AGENTS.md` 模块速查表、根 `TODO.md`（T-015）同步

---

## [19.0.2.0.0] - 2026-09-21（本地开发库已验证，待目标环境验证）

### 验收记录

- 验收日期：2026-09-21
- 验收环境：本地开发库（`dev`，Odoo 19 官方镜像；另一轮测试库额外装了 `stock` / `sale_management`）
- 验收结果：两轮自动化测试均 14 项全部通过（0 failed / 0 error）；`i18n/zh_CN.po` 148 条 `msgid` 直接来自官方术语导出，与源码逐字符一致
  - [x] `-i` / `-u` 安装与升级无报错（含 5 个模型、安全规则、6 个视图文件）
  - [x] 只有 `product` 与加上 `stock` / `sale_management` 两种环境下测试都全绿
  - [x] 2 个变体 + 新属性 → 4 个变体：两条原记录各自保留自己的组合，另两条为新记录
  - [x] 归属可逐条交叉指定（把 Blue 那条记录改指 Blue + L）
  - [x] 两条原变体被指到同一组合时拒绝，且不改库
  - [x] 只加单取值属性：变体数不变，每条既有变体都带上该取值
  - [x] 删除已有取值被拒绝；带归档变体的产品被拒绝
  - [x] 转换台账、变体谱系、`product.product` 上的来源字段内容正确
  - [x] 两个变体各有库存时，转换后库存仍分别挂在原来那条记录上
  - [x] 销售订单行仍指向原来那条变体
  - [x] 供应商价格共享选项两种情况均符合预期
  - [ ] 目标环境界面显隐（按钮 / 智能按钮 / 谱系页 / 变体列表可选列 / 搜索筛选）待验证
  - [ ] 目标环境界面中英文各验一遍待验证

### 执行流程

1. 升级：`odoo -d <db> -u product_variant_conversion --stop-after-init`
2. 打开有变体的产品 → 「属性与变体」页 → **Add Attributes To Variants**
3. 加属性 / 加取值 → 在 **Variant Ownership** 表里核对或修改每条既有变体转换后占有的取值 → **Convert**
4. 核对：产品表单 `Conversions` 智能按钮看台账，`Variant Lineage` 页看归属；变体列表按 `Derived From` 排序或搜索
5. 本地可复跑：`task test -- product_variant_conversion,stock,sale_management --test-tags=/product_variant_conversion`

### 变更

- **模块技术名由 `product_variant_convert` 改为 `product_variant_conversion`**（交付前定名调整，目录 / xmlid 前缀 / 五个模型名 / 关系表名 / po 引用 / 文档全部同步）：
  - 原名词性与家族不一致（仓库模块都是名词短语：`product_reference` / `product_packing` / `product_card_view`…），且 `convert` 没说「转成什么」——Odoo 19 里还有 `product.combo`，容易被读成「把变体转成组合产品」（本模块恰恰明确拒绝 combo 产品）
  - 新名与显示名（`Product Variant Conversion`）、与模块内部命名天然对齐（模型 `product.variant.conversion`、字段 `variant_conversion_id`、界面 `Variant Conversion` / `Variant Conversions`、动作 `product_variant_conversion_action`）
  - 向导模型一并统一为 `product.variant.conversion.wizard` / `.line` / `.variant.line`（原 `product.variant.convert.*`）
  - 改名时机：目标环境尚未交付过本模块（只有本地 dev 库），先 `odoo module uninstall` 干净卸载旧模块再安装新名，**无需生产库卸载重装**；仓库文档也写明交付后改名的代价极高
- **支持多变体产品的转换**（原 `19.0.1.0.0` 只支持「仅含单一变体」的产品）：现在只要产品有变体就能追加属性 / 取值，例如「2 个颜色」再加「2 个尺码」变成 4 个变体
- **新增「变体归属表」**（`product.variant.conversion.variant.line`）：每条既有变体一行，显式指定它转换后占有的取值（每属性一个），表格自动预填（已有属性保持原取值、新加属性取本次第一个取值）并可逐行修改；同一属性写多行时按并集合并
  - 归属表由 `_sync_variant_lines()` 统一补齐，`line_ids` 的 onchange 与 `action_convert()` 都会调用，保证界面与执行用的是同一份配置
  - 归属表每行显示该变体的在手数量，库存归属一目了然
- **移除** `product.variant.conversion.line.default_value_id`（原「逐属性指定原变体取值」）：归属改由归属表逐条变体表达，避免「同一件事两个地方表达」
- 核心算法从「单个默认组合」推广为「逐条变体锚定」：`variant_mapping` 是唯一入口，未提供时由 `_get_variant_conversion_default_mapping()` 补齐；预检新增「归属组合互不重复」与「预期变体数不得少于既有变体数」；后置断言改为逐条变体检查
- **新增归属追溯**：
  - `product.variant.conversion` 转换台账：产品、转换前后的变体数、新增变体数、本次真正新增的属性、是否共享供应商价格、时间与操作人
  - `product.variant.lineage` 变体谱系：来源变体 → 结果变体、`is_kept`（结果是否就是原记录）、转换前后组合快照、本次为该变体新增的取值；新变体的来源按「转换前就存在的属性轴」判定，判定不唯一时留空
  - `product.product` 新增可搜索字段 `variant_conversion_id` / `variant_origin_id`
- **新增界面**：产品表单 `Conversions` 智能按钮与 `Variant Lineage` 页、产品搜索「含转换产生的变体」筛选、变体表单来源分组、变体列表两个可选列、变体搜索按来源变体 / 所属转换检索与筛选、转换台账列表 / 详情视图
- **新增拒绝规则**：产品存在归档变体时直接拒绝转换（避免 `_create_variant_ids` 悄悄把老变体重新激活）
- 审计面板改为按**全部既有变体**聚合；`product.variant.conversion` 的 `_description` 取 `Variant Conversion Log`（与模块名区分，避免 `msgid` 撞车）
- 测试从 12 项扩到 14 项并改成覆盖多变体场景（归属映射 / 交叉指定 / 归属互斥 / 谱系 / 库存与订单行不变），且在只有 `product` 的环境下也能跑（`is_storable` 由 `stock` 提供，先判断字段是否存在）
- i18n：`i18n/zh_CN.po` 改为用官方 `odoo i18n export` 导出的术语骨架重建（148 条，含应用列表元数据 3 条），杜绝手写 `msgid` 与源码不一致

### 影响

- **不涉及任何数据库结构变更迁移**：新增的 2 个模型由 Odoo 正常建表；向导字段与向导模型名的变化都发生在瞬态模型上（无历史数据），**无需迁移脚本**
- **改名影响**：本模块从未在目标环境交付过，改名只需在开发库 `odoo module uninstall product_variant_convert` 后安装 `product_variant_conversion`（本地已实测：旧模块的表与数据随卸载一并清理，无残留表）。若某个库已经装过旧名模块，必须按「先卸载旧名、再安装新名」处理——Odoo 视改名为不同模块
- 不改动任何官方模型字段与视图节点，只新增按钮 / 智能按钮 / 页签 / 可选列 / 搜索项、2 个新模型与 2 个变体字段
- 已按 `19.0.1.0.0` / 旧名版本转换过的产品不受影响：转换结果与新版本读的是同一批数据（变体的实际取值组合、台账与谱系行），不依赖向导字段名
- 依赖仍只有 `product`；新增的 UI 元素在 `stock` / `sale` / `purchase` / `account` 未安装时同样可用

### 文档

- 同步更新 `__manifest__.py`（版本、`summary` / `description`）、`README.md`（新增「如何指定每条既有变体的归属」「变体来源与归属怎么追溯」两节，字段表与验证清单扩写）、`AGENTS.md`（L1 扩到 11 条，L2 新增 P1 归属算法、P2 i18n 与 po 维护、P3 Odoo 19 字段与命名坑）
- 根 `README.md` 模块一览表 / 路线图 / 应用列表元数据总览、根 `AGENTS.md` 模块速查表、根 `TODO.md`（T-015 归档内容更新）

---

## [19.0.1.0.0] - 2026-09-21（开发期中间版本，已被 19.0.2.0.0 取代；当时技术名为 `product_variant_convert`）

### 验收记录

- 验收日期：2026-09-21
- 验收环境：本地开发库（`dev`，Odoo 19 官方镜像；自动化测试库额外装了 `stock` / `sale_management`）
- 验收结果：本地 12 项自动化测试全部通过（0 failed / 0 error），i18n 85 条 `msgid` 与 Odoo 术语抽取结果逐条对齐

  - [x] `-i product_variant_conversion` 安装无报错
  - [x] `-u product_variant_conversion` 升级无报错，安全规则与两个视图加载成功
  - [x] 单变体产品转换后原变体记录 id 不变，并成为指定的默认变体
  - [x] 两个属性时生成全部组合，原变体占用户指定的那一组
  - [x] 已有单取值属性行可追加取值，只新增变体
  - [x] 删除已有取值被拒绝，且不改库
  - [x] 库存量记录与销售订单行仍指向原变体
  - [x] 供应商价格共享选项两种情况均符合预期
  - [x] 已是多变体的产品拒绝进入向导
  - [ ] 目标环境中文「应用」列表显示中文元数据（待验证）
  - [ ] 目标环境界面中英文各验一遍（待验证）

### 执行流程

1. 安装：`odoo -d <db> -i product_variant_conversion --stop-after-init`
2. 打开只有 1 个变体的产品 → 「属性与变体」页 → **Convert to Multi-Variant**
3. 填属性与取值，逐属性指定「Original Variant Value」（原变体取值）→ **Convert**
4. 核对：变体列表中新旧变体齐备；默认变体上仍能看到原有的在手数量与订单行
5. 本地可复跑：`task test -- product_variant_conversion,stock,sale_management --test-tags=/product_variant_conversion`

### 变更

- 初始版本，新建模块 `product_variant_conversion`（产品变体转换）
- 在 `product.template` 上新增转换入口与核心实现 `_convert_to_multi_variant()`：
  - 带 `create_product_product=False` 上下文写 `attribute_line_ids`，只生成 `product.template.attribute.value`，不触发 `_create_variant_ids()`（不新建、不删除任何变体）
  - 把用户指定的「默认组合」锚定到原变体的 `product_template_attribute_value_ids` 上，再调用 `_create_variant_ids()`：原变体因组合匹配而被复用，缺失组合才新建
  - 全过程包在 `savepoint` 内，配前置校验（只允许追加取值、默认取值必须落在选值内、属性不能是按需生成等）与后置断言（原变体仍在且等于默认组合、变体数等于用 Odoo 规则算出的预期数），任何不符即整单回滚
  - 同一产品的转换用 `SELECT ... FOR UPDATE` 串行化，避免并发改同一产品的属性行
  - 可选把仅挂在原变体上的 `product.supplierinfo` 改为适用于全部变体（`product_id = False`）
- 新建瞬态模型 `product.variant.conversion.wizard` 与 `product.variant.conversion.line`：
  - 逐属性指定「原变体取值」；同属性写多行时自动合并取值（默认取值必须一致）
  - 打开时自动预填产品已有的属性行（取值与原变体取值取当前配置）
  - 转换前审计面板：在手数量、库存量记录、库存移动明细、未完成库存移动、批次、销售 / 采购订单行（总数与未完结数）、发票行、供应商价格、补货规则、价格表规则
  - 审计通过 `model_name in self.env` + `check_access_rights` 降级，模块不依赖 `stock` / `sale` / `purchase` / `account`
- 产品表单「属性与变体」页新增按钮与说明（仅单变体产品显示）
- 新增 `tests/test_product_variant_conversion.py`：12 项测试覆盖保留原变体、多属性组合、追加取值、拒绝删取值、拒绝无新变体、供应商价格共享，以及（装了 `stock` / `sale` 时）库存量记录与销售订单行仍指向原变体
- i18n：源语言英文 + `i18n/zh_CN.po`（85 条 `msgid`，含应用列表元数据 3 条与分类 `Product`）

### 影响

- 不涉及任何数据库结构变更（未新增字段、未改字段类型），**无需迁移脚本**
- 不改动任何官方模型字段与视图节点，只新增按钮、两个瞬态模型与安全规则；卸载模块后转换能力消失，但已转换的产品不受影响
- 转换会写 `product.template.attribute.line` / `product.template.attribute.value` / `product.product.product_template_attribute_value_ids`，并可选择性质地写 `product.supplierinfo.product_id`（仅在勾选时）
- 依赖最小：只依赖 `product`；审计面板对未安装模型自动降级为 0

### 文档

- 同步更新 `__manifest__.py`、`README.md`、`AGENTS.md`、`CHANGELOG.md`（本文件）
- 根 `TODO.md`（T-015 归档）、根 `README.md`（模块一览表 / 路线图 / 应用列表元数据总览）、根 `AGENTS.md`（第 9 节模块速查表）
- `.dev/init.yaml` 与 `DEV_WORKFLOW.md` 的开发库模块清单加入本模块，`DEV_ENV_SETUP.md` 的验收描述同步模块数量
