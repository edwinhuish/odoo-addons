# 变更日志

> 倒序排列，最新版本在最前。每版本固定三段式：变更 / 影响 / 文档。
> 版本号规则见根 `AGENTS.md` 第 3 节：架构/破坏性 +x，功能新增 +y，修复/文档 +z。

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
