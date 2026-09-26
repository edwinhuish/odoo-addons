# AGENTS 工作指引

> 本文档用于指导 AI 助手或新开发者在维护、扩展本 Odoo 模块时的行为规范和关键上下文。
> L1 约束段每次加载必读；L2 踩坑档案按主题触发条件加载。

---

## 模块定位

- 模块名：产品变体转换
- 技术目录：`product_variant`
- 新建模型：`product.variant.conversion`（转换台账）、`product.variant.lineage`（变体谱系）；**没有向导模型**（入口是保存拦截，不是按钮）
- 继承模型：`product.template`（保存拦截 + 转换核心）、`product.product`（来源字段）
- 自定义组件（前端模块）：`VariantMappingPanel`（「属性 ↔ 变体」映射表，field widget）+ `FormController.onWillSaveRecord` 补丁
- 主依赖：`product`（**不依赖** `stock` / `sale` / `purchase` / `account`；这些模型只用来给映射表补在手数量，运行时判断是否存在）
- 当前版本：`19.0.13.1.0`（19.0.13.1.0：**组合可以选择「不生成变体」** —— 映射表 Variant 下拉新增
  `Do not create a variant`（`store.skipped`），服务端在转换末尾丢弃标了不生成的组合**本次刚建出来**
  的那条变体；它与「由既有变体保留」互斥（两道闸门：前端禁用 + 服务端按锚点拒绝），见 L1 约束 1
  最后一条；19.0.13.0.7：**修「点 New 后映射表还是上一个产品的」** —— 点 New / 翻页走
  `model.load({resId})`，model 与面板组件实例都被复用（`setup()` 不再跑），「换记录」只能在
  `recompute()` 里认（作废整份状态 + 重取快照）；`resetMappingStore()` 改**原地**清空（换对象会让
  组件与保存钩子各拿一份、且不经代理不重画）；新建（没 id）与「快照还没取回来」时整块不显示，
  见 L2 P4 陷阱 24；19.0.13.0.6：**核查修订** —— README 同步到当前实现
  （映射表示例 / 签名 / 前端资源表 / 测试数口径）、把「原生直写的安全不变量」写成注释与用例
  （见 L2 P4 陷阱 22 第 4 条）；19.0.13.0.5：**面板说明 / 警告文字自动换行** —— 样式放
  `static/src/scss/variant_mapping_panel.scss`：`min-width: 0` + `overflow-wrap: anywhere`
  把 CSS Grid 轨道压住，长句（含无空格长词）不再顶出 `.o_form_sheet`，见 L2 P4 陷阱 23；
  19.0.13.0.4：**删唯一属性时守卫放行** —— 带着映射保存时，先校验「每条
  既有变体都有组合」，再带 `variant_conversion_keeps_variants` 上下文键走原生写入，
  `product_attribute_guards.py` 三处守卫认这个键放行（前提「变体会被连坐」不成立）；
  19.0.13.0.3：**删除唯一属性后自动复用既有变体** —— 没有属性时也要给一行「空组合」，让原来的变体继续挂靠，避免保存被拦；19.0.13.0.2：**修「Save manually 点了没反应」+ 面板不再放按钮** —— 保存钩子在 mutex 里调 `getChanges()` 会死锁（改用 `_getChanges()`）；顺带跳掉改属性行时那次多余的 `product.template` onchange；面板下方只留「未保存」徽标，保存 / 丢弃一律用标题右侧的原生按钮，见 L2 P4 陷阱 21；19.0.13.0.1：**面板标题改为 `Variants Mapping` / 「变体映射」**；19.0.13.0.0：**面板标题 + 显式保存/丢弃 + 移除原生警告** —— 映射一改就出现 `Save manually` / `Discard all changes`（靠 `FIELD_IS_DIRTY` 广播，**不**把映射塞进 record，否则自动保存会带走它），丢弃要能回滚到基线；删掉 `product.product_template_only_form_view` 里那句已不成立的 Warning 文本，见 L2 P4 陷阱 20；19.0.12.0.1：**Variant 下拉禁掉已被别行占用的变体** —— 「一条变体只能承载一个组合」要在**候选列表里**体现（灰显、选不了），想换位置就先把自己那行改回 `(new variant)` 让出来；不做「选到别处自动从原行让出」，见 L2 P4 陷阱 19；19.0.12.0.0：**前端穷举展示、后端按需预建** —— 映射表把「按需生成」属性的全部取值组合都列出来（用户要求「充分列举所有可能的组合」），但**预建**仍按属性规则：立即轴展开、按需轴只建被既有变体认领的取值，`(new variant)` 的行落在没被认领的按需取值上就**不会现在创建**（前端把这类行显示成灰色 + 提示 N 个组合等订单）；19.0.10.0.0：**映射表反向 —— 组合为行、为每个组合选变体** —— 行是固定组合，Variant 下拉留空=新建变体、选一条=由它保留；同一条变体只能占一行（选到别处自动让出，交换只需两下），「按需生成」属性的取值是行上的可改值（不预建其它取值），拦截条件变成「没被任何组合认领的既有变体」，见 L2 P4 陷阱 18；19.0.9.0.0：**一个组合只能被一条变体占用** —— 前端在下拉里禁掉已被占住的候选值，真重复时把那条标成未映射；与保存时的 `_check_variant_conversion_anchors()` 同口径，见 L2 P4 陷阱 18；19.0.8.0.4：**默认值不算用户选择** —— 单取值轴自动补的取值不能再写回 selection，否则该轴多出第二个取值时回不到「未映射」（轴状态带 `picked` 标记），见 L2 P4 陷阱 17；19.0.8.0.3：**子表编辑要订阅子表组件** —— `useRecordObserver` 的依赖是父 record，子行改字段不触发它；改为 patch `X2ManyField` / `ListX2ManyField` 的 `onPatched` + 保留 record observer + 面板低频本地自检兜底，见 L2 P4 陷阱 16；19.0.8.0.2：**新行必须保留 Odoo 的虚拟 id** —— 合并 `getChanges()` 命令时自己造 id 会让「选属性 / 勾取值」这两条后续命令落空，那一行永远不成为轴（单变体产品加属性就是这样「毫无反应」），见 L2 P4 陷阱 15；19.0.8.0.1：**用 `record.getChanges()` 合并快照基线来读表单编辑态** —— 原来读 `record.data` 的 x2many 内部结构，编辑中的取值是命令数组，会被读成空 → 加属性「毫无反应」，见 L2 P4 陷阱 14；19.0.8.0.0：**映射计算搬到前端** —— 面板挂载时取一次快照 `get_variant_mapping_snapshot()`，其后属性行增删 / 勾取值 / 挑映射全部由前端纯函数 `computeVariantMapping()` 在浏览器里算，**编辑期零 RPC**，保存时才把映射随表单提交；多取值轴（**含「按需生成」轴**）一律要求显式映射，见 L2 P4 陷阱 13；19.0.7.0.5：**给前端看的状态不再做成 compute** —— `variant_mapping_state` 降级为 `store=False` 的挂载点，面板挂载时自己 RPC 取；原来的 compute 会在每次 onchange 里被求值，那时表单里还有没保存的行（`NewId`），`json.dumps` 必炸，见 L2 P4 陷阱 12；19.0.7.0.4：**修「点 Add a line 就报必填缺失」** —— 产品表单会发出「新建但还没选属性」的半成品命令，预览 RPC 要清洗掉或兜住（前端 `hasIncompleteLine()` + 服务端 `_sanitize_attribute_line_commands()` / `NotNullViolation` 兜底），见 L2 P4 陷阱 11；19.0.7.0.3：**修映射表排版** —— 字段外层的 `.o_field_widget` 是 `inline-block`，不包一层块级 div 的话面板会被排到属性行**右边**并溢出表单宽度（「跑右边、看不见」），见 L2 P4 陷阱 10；19.0.7.0.2：**修映射表模板变量名** —— 模板里的 `state.blocked` / `state.rows` 必须写成组件上真实的 `store.`（OWL 模板表达式只认组件实例上的名字，`state` 不是保留字，写错只会得到 `undefined.x`，报错栈只指到模板），见 L2 P4 陷阱 9；19.0.7.0.1：**修字段 widget 注册方式** —— 字段组件必须注册成 `{ component, displayName, supportedTypes }` 描述对象，注册裸类会让 `web.Field` 拿到 `undefined` 的 `component`、渲染时崩在 `Component.name`（现象：打开产品表单 /「属性与变体」页报 `UncaughtPromiseError > OwlError` + `reading 'name'`，栈只落在 `Field.template`），见 L2 P4 陷阱 8；19.0.7.0.0：**模块改名 `product_variant` + 「属性 ↔ 变体」映射表** —— 改属性时属性行下方常驻一张映射表，缺取值的变体显示成**未映射**，还有未映射的变体就不放行保存；归属弹窗随之删除；**已装库必须走「原地改名」三条 SQL**（见 `README.md`），卸载重装会清空台账 / 谱系；19.0.6.1.0：**归属弹窗交互优化** —— 所有下拉选项都可选，选中已被别的组合占用的既有变体时两行**自动互换**（纯函数 `applyOwnershipSelection()`）；19.0.6.0.0：**`T-039` 支持「按需生成变体」的属性** —— 只展开「立即」轴、按需轴按既有变体现带取值钉住、缺失组合自己用 `_create_product_variant()` 补、带按需属性的产品不做价格分离；建产品时带按需属性仍然拦住；`19.0.5.3.2`：修**一次加两个属性**时 chatter 记录对多记录集取 `.display_name` 抛 `Expected singleton`、连累整单回滚；19.0.5.3.1：**按需生成属性**的拦截补齐 —— 报错点名属性并给出可执行的出路，建产品时就拦住（原生 `create()` 遇到按需生成的属性不会建任何变体，会留下「有属性、没变体」的产品）；`19.0.5.3.0`：**彻底与 `product_reference` 解耦** —— 删除编号上移与参考号交接两步、不再读写对方的任何字段，转换只做「按归属复用既有变体」，`product.product` 的值（含 `default_code`）原样保留；`19.0.5.0.0`：谱系来源改为按「转换前已存在的取值」判定，加取值场景不再丢来源；修掉未装 `product_reference` 时转换必崩；`19.0.4.1.0` 起含尺寸继承）
- 命名说明：技术名用**名词短语** `product_variant`，与显示名（`Product Variant Conversion`）、
  模型 `product.variant.conversion`、字段 `variant_conversion_id` 一致；原用名 `product_variant_convert`
  （裸动词，且容易被读成「把变体转成组合产品」，而 Odoo 19 里 `product.combo` 是另一个概念）已在交付前改掉
- ⚠ **不要再改技术名**：Odoo 视改名为不同模块，装过的库必须「先卸载旧名、再安装新名」；
  交付前改名是唯一一次机会（见根 `AGENTS.md` 命名约定）

---

## L1：不可破坏的核心约束

每次修改代码必须保证以下行为不变。每条只列约束与违反后果，实现细节见 L2 踩坑档案。

1. **绝不删除、重建或归档既有变体**
   - 转换只能新增 `product.product`；改动前存在的每一条变体记录都必须原地保留（id 不变），并各自成为用户确认的那个组合
   - 违反后果：`stock.move.line` 因 `ondelete='cascade'` 被连带删除（库存历史直接丢失）；`sale.order.line` / `purchase.order.line` / `account.move.line` / `stock.quant` 因 `ondelete='restrict'` 导致删除失败后退化为归档旧变体 + 新建同组合变体，单据与库存从此对不上
   - **`19.0.13.1.0` 起唯一的例外**：用户在映射表里把某个组合标成**「不生成变体」**时，可以删掉
     该组合**本次转换刚建出来**的那条变体（`_drop_variant_conversion_skipped_variants()`）——
     它是这一趟才建的，还没有任何库存 / 单据。硬前提：**只删 `originals` 之外的**
     （`self.product_variant_ids - originals`），既有变体一条都不能因为它被丢掉；
     前端在「还挂着既有变体」的行上禁用该选项，服务端按**改动后的锚点**再拒一次
     （`_check_variant_conversion_skipped()`），删完立即作废 `product_variant_ids` /
     `product_variant_count` 缓存，后置断言的预期数也扣掉本次删掉的数量。
     违反后果：既有多变体被连带删除 / 归档，回到上面那条违反后果

2. **入口只能是「保存时检测」，不能加按钮 / 向导**
   - 属性变更的归属确认必须发生在保存流程里（前端 `onWillSaveRecord` + 服务端 `write` 双层），
     不允许再加产品表单按钮、也不允许用「先打开向导再改属性」的入口
   - 违反后果：用户在原生界面改属性仍会绕过确认，数据照样被删；或入口分裂成两套、行为不一致

3. **`write()` 的三种结局必须区分清楚**
   - ① 既有变体一条不少、也不新增变体 → 原样 `super().write(vals)`；
   - ② 会新增变体（组合数 > 既有变体数）→ 还有**未映射**的变体就**拦住保存**（抛错，由前端映射表接管），都映射好了就先安全转换再落库；
   - ③ 会丢变体（`lost_variant_ids` 非空，或组合数 < 既有变体数）→ **直接拒绝**，绝不静默删除
   - 违反后果：把 ② 判成 ③ 会让主场景（加属性）永远弹不出确认框；把 ③ 判成 ①/② 会真删变体

4. **检测不能拿「原生写法」当判据**
   - 必须用 `_analyze_variant_conversion_write()`：带 `create_product_product=False` 只写配置（属性行 + ptav）、
     在保存点里跑一遍再回滚。原生写法在「加属性」时本来就会删掉既有变体，那是要防的结果
   - 违反后果：主场景被误判成「会丢变体」而拒绝；或为了测量而真的执行一次破坏性写入（虽然能回滚，但会引入 `stock.move.line` 级联删除、附件泄漏等副作用）

5. **每个既有变体都必须先锚定到它自己的归属组合，再调用 `_create_variant_ids()`**
   - 顺序固定：写配置（不碰变体）→ 预检（组合数、归属互不重复、默认组合不被排除）→ 逐个写
     `variant.product_template_attribute_value_ids` → `_create_variant_ids()`
   - 归属来自唯一的入口 `variant_mapping`（`{既有变体: 取值集合}`）；程序化调用留空时由
     `_get_variant_conversion_default_mapping()` 按「已有属性保持原取值、新加属性取第一个取值」补齐
   - 违反后果：某条既有变体的组合不匹配任何新组合，它就会被删 / 被归档，违反约束 1

6. **归属必须完整且不重复**
   - `_parse_variant_conversion_mapping()` 必须要求：每条既有变体恰好出现一次、取值必须存在；
     `_check_variant_conversion_anchors()` 必须拒绝「两条既有变体占同一个组合」
   - 违反后果：漏掉一条既有变体就会让它被删；重复会让 Odoo 的组合匹配字典碰撞，其中一条被删且谱系记错来源

7. **整个转换必须在 `savepoint` 内，且带前置校验 + 后置断言**
   - 后置断言必须包含：每条既有变体仍存在且启用、它携带的组合等于自己的归属组合、变体数等于用 Odoo 规则算出的预期数
   - 违反后果：出现一致性异常时数据库停留在半转换状态，比转换失败更难收拾

8. **只允许追加取值，不允许删除**
   - 删取值 / 删属性行一律在 `write()` 里被拒绝（`lost_variant_ids` / 组合数变少）
   - 违反后果：删取值会让 Odoo 归档 / 删除对应 ptav 并牵动变体，把删除风险重新引入

9. **归属与属性变更必须同一次写库**
   - 映射表确认的归属通过技术字段 `variant_conversion_mapping` 与用户那组属性命令一起提交；
     `write()` 先写配置、再做安全转换、最后写其余字段，失败整单回滚；技术字段写完即清空
   - 违反后果：出现「属性改了但归属没落库」或反之的半成品状态；技术字段残留还会污染下一次保存

10. **`create_product_product=False` 的写入必须直接放行**
    - `write()` 的第一道判断必须包含 `not self.env.context.get("create_product_product", True)` → `super().write(vals)`；
      这是模块自己的「只写配置、不碰变体」模式（分析用的一次试写、转换内部写属性行都走它）
    - 违反后果：无限递归（试写会再次进入拦截逻辑），直接 `RecursionError`

11. **归档变体必须先拒绝转换**
    - `_check_variant_conversion_allowed()` 必须拒绝带归档变体的产品（提示先恢复或删除）
    - 违反后果：`_create_variant_ids` 会自动激活组合仍然可能的老变体，转换悄悄把归档变体复活

12. **依赖最小化：只能依赖 `product`**
    - 需要 `stock` / `sale` / `purchase` / `account` 的信息时，一律用 `model_name in self.env` +
      `check_access_rights("read", raise_exception=False)` 降级；测试里 `is_storable`（stock 提供）也要先判断字段是否存在
    - 违反后果：只装库存的库装不上本模块，或映射表 / 台账因权限不足直接报错

13. **转换逻辑只能有一处实现**
    - 核心逻辑留在 `product.template._convert_to_multi_variant()`，`write()` 只做判定与编排；
      禁止在前端或另一个方法里另写一份写库逻辑
    - 违反后果：两处实现分叉，绕过校验的路径重新出现

14. **所有用户可见文本源语言为英文（`en_US`）**
    - Python / XML / JS 中不写中文界面文案；中文只放在 `i18n/zh_CN.po` 的 `msgstr`
    - 违反后果：默认英文界面出现中文；或重复 `msgid` 导致整份 po 解析失败

15. **新变体的继承只限「成本 / 体积 / 重量」，来源只能是谱系来源**
    - `_apply_variant_data_inheritance()` 只复制 `standard_price` / `volume` / `weight`，来源取 `variant.variant_origin_id`；
      来源为空时跳过该变体，保持空值、不做猜测
    - **禁止**复制内部参考号（本仓库 `product_reference` 的 L1 约束是「多变体产品不共用参考号」）与条码
      （`product.product._check_barcode_uniqueness()` 的唯一性约束会让写入直接报错、整单回滚）
    - 开关是系统参数 `product_variant.inherit_variant_data`（默认开启）；台账 `inherit_variant_data` 要如实记录
    - 违反后果：参考号在多变体间共用，与 `product_reference` 的既定规则打架；复制条码直接 ValidationError

16. **价格数据默认按变体分离：改一个变体的价格不得牵动别的变体**
    - `_separate_variant_prices()` 负责：本产品**模板级**的供应商价格 / 价格表规则拆成每条变体一份后
      **删除原记录**（值不变），新变体从谱系来源继承；勾了「应用到全部变体」时供应商价格退回模板级共享
      （价格表规则仍按变体分离）
    - **禁止**把「模板级共用」当默认：一条记录被所有变体共用，改它就会影响全部变体
    - 两道保险必须保留：① 变体在同一「价格表 + 数量门槛」上已有自己的规则时，模板规则不再拆过去（避免静默改价）；
      ② `_check_variant_price_separation()` 断言分离前后「供应商价格只多不少、原有变体**实际售价**一分未变、
      新变体售价与其来源一致」，不符即整单回滚
    - 开关：系统参数 `product_variant.separate_variant_prices`（默认开启）；台账 `separate_variant_prices` 如实记录
    - 违反后果：拆规则时静默改价（卖价变了却没人知道）；或所有变体共用一条价格记录，改一处影响全部

17. **属性主数据与属性行的直接写路径必须过「丢变体」守卫**（`models/product_attribute_guards.py`）
    - 三个模型都有守卫：`product.template.attribute.value.unlink()`、`product.attribute.value.unlink()`、
      `product.template.attribute.line.unlink()` / `.write()`（`value_ids` 移走在用变体携带的取值时拒绝）
    - 守卫在 `create_product_product=False` 时**必须放行**（那是本模块的沙盒写入，见 L1 约束 10）
    - 守卫在 `variant_conversion_keeps_variants=True` 时**也必须放行**：产品表单带着映射
      （`variant_conversion_mapping`）保存时，映射已说明每条既有变体改动后占哪个组合
      （典型：删掉唯一属性 → 那条变体承载空组合），守卫的前提「变体会被连坐」不成立；
      由 `product.template.write()` 解析校验过映射之后带上这个上下文键（见 L2 P4 陷阱 22）
    - 报错必须给出出路：「先归档或删除用到它的变体，再删取值」
    - 违反后果：属性主数据里删取值会连坐删 / 归档在用变体（库存与单据跟着消失），绕过整个归属确认
    - 已知不拦：**归档**属性取值（Odoo 原生也不拦）——归档后变体仍带着该取值，见 README →「已知边界」

18. **「按需生成」（`dynamic`）属性：改属性要支持，只展开「立即」轴；建产品时要拦住**（`T-039`）
    - 改属性（`write()` / 预览 / 转换）：**支持**。属性行按 `_split_variant_conversion_lines()` 分成
      「展开的（`always`）」与「固定取值的（`dynamic`）」；组合枚举 = **每条既有变体 × 各「立即」属性的取值组合**
      （按需轴取该变体现带的取值，没有则取第一个），因此按需轴的其它取值**永远不预建变体**（等订单创建）
    - 新增变体必须**自己建**：`_create_variant_ids()` 遇到按需属性整段跳过新建
      （`if not tmpl_id.has_dynamic_attributes()`），所以走 `_create_variant_conversion_missing_variants()`
      → `_create_product_variant()`（销售配置器同款入口）；**不要**自己拼 `product.product.create()`
    - 原生会丢变体时必须自己锚定：`needs_anchoring`（某条既有变体缺某个**多取值**属性行的取值）→
      不能走「原生保存」，走转换、用默认归属锚定（无新变体 → 映射表不阻断）；否则原生会把它当组合不完整删掉
    - **不做价格分离**：带按需属性的产品保持模板级价格（分离会拆走模板级记录并删除，之后订单期新建的
      变体会取不到价），台账 `separate_variant_prices` 记否，映射表也不显示勾选框
    - `create()`：**仍然拦住**带按需属性的产品 —— 原生会建出「有属性、没变体」的产品。
      文案由 `_get_variant_conversion_dynamic_message()` 一处提供（`#. odoo-python`），必须点名属性并给
      **能走通**的出路：「先不带该属性建产品、保存，再把属性加到产品上（届时转换会保住既有变体）」；
      只说「去改成「立即」」等于没有出路（Odoo 不允许修改已被产品使用的属性的变体生成方式）
    - 违背后果：回到 `19.0.5.3.1` 的死结 —— 导入来的产品（导入会把新建属性设成按需生成，
      见 `product.product._load_records_create()`）改不了任何属性，而属性设置也改不动

---

## 国际化约束（i18n）

每处用户可见文本都必须满足（通用规则见根 `AGENTS.md` 第 4 节）：

1. **源语言是英文（`en_US`）**：Python / XML / JS 里一律写英文；中文只能出现在 `i18n/zh_CN.po` 的 `msgstr` 里。
2. **可翻译入口正确**：见根 `AGENTS.md` 4.2「可翻译入口对照表」（`model:` / `model_terms:` / `code:` 三类键名）；前端术语走 `code:addons/<module>/static/src/js/<file>.js:0` 与 `code:addons/<module>/static/src/xml/<file>.xml:0`。
3. **禁止拼接句子**：占位符统一 `%(name)s`。映射表里夹在元素中的句子（如「还差 N 条」）**必须在 JS 侧用 `_t()` 拼好再 `t-esc`**，否则模板会把句子切成碎片；
   唯一允许的拼接是「属性: 取值」这类数据标签。
4. **`<span>` / `<option>` 等内联元素整块成术语**：见 L2 P2 陷阱 1；选项文案与提示句一律用 JS getter + `_t()`，不要写成模板里的文本节点。
5. **收尾动作**：改英文源文本 → 同步 `i18n/zh_CN.po` → 提升版本 → `-u` 升级 + 强刷浏览器，中英文各验一遍。
6. **代码注释保持中文**，不为 i18n 改英文。
7. **应用列表（Apps）元数据必须有中文**：改 `__manifest__.py` 的 `name` / `summary` / `description` 后，必须同步
   `model:ir.module.module,shortdesc|summary|description:base.module_product_variant` 三条
   （`description` 条的 `msgid` 必须等于 `textwrap.dedent(manifest["description"])`）；分类沿用官方的 `Inventory/Product`，
   自定义段 `base.module_category_inventory_product` 的「产品」译文与其它产品类模块**合并成同一条 `msgid`**。
   见根 `AGENTS.md` 4.8。
8. **每次改完视图 / 文案后，用官方导出重建 po 而不是手改**（见 L2 P2 的自查方式）。

---

## 文件职责

| 文件 | 职责 |
|------|------|
| `__manifest__.py` | 模块元数据、版本、依赖（仅 `product`）、数据文件与前端资源登记（assets 里三个文件） |
| `models/product_template.py` | 保存拦截 `write()`、预览 RPC `get_variant_conversion_preview()`、试写分析 `_analyze_variant_conversion_write()`、归属解析、核心转换 `_convert_to_multi_variant()`、校验与断言、谱系写入、台账入口 `action_open_variant_conversions()` |
| `models/product_product.py` | 变体上的可搜索来源字段 `variant_conversion_id` / `variant_origin_id` |
| `models/product_template_prices.py` | 价格数据按变体分离的实现（供应商价格 / 价格表规则的拆分、继承与守恒断言），从 `product_template.py` 拆出 |
| `models/product_attribute_guards.py` | T-017：属性主数据与属性行直接写路径的「丢变体」守卫（ptav / PAV / line 三个模型） |
| `models/product_variant.py` | 转换台账与变体谱系两个模型 |
| `models/product_variant_mapping.py` | 「属性 ↔ 变体」映射：挂载点字段 `variant_mapping_state`（`store=False`，**不做 compute**）、一次性快照 RPC `get_variant_mapping_snapshot()`、服务端侧判定 `get_variant_mapping_preview()` / 未映射判据 `_get_variant_mapping_rows()` |
| `static/src/js/variant_mapping_panel.js` | 映射表面板（field widget `variant_mapping_panel`）：逐变体逐轴渲染、属性行一改就防抖刷新、状态存在 `model.variantMapping` 上；载荷构造 / 未映射计数 / 属性行签名都是纯函数 |
| `static/src/xml/variant_mapping_panel.xml` | 映射表模板 `product_variant.VariantMappingPanel` |
| `static/src/scss/variant_mapping_panel.scss` | 面板样式：`min-width: 0` + `overflow-wrap: anywhere` 让说明 / 警告在 `.o_form_sheet` 内自动换行，表格 `table-layout: fixed`（见 L2 P4 陷阱 23） |
| `static/src/js/variant_conversion_form_patch.js` | patch `FormController.onWillSaveRecord`：保存前问映射状态；会丢变体 / 还有未映射的变体就提示并拦住；都映射好了就把归属放进本次 `changes` |
| `views/product_template_views.xml` | 产品表单的技术字段（不可见）、`Conversions` 智能按钮；产品搜索筛选。**刻意不加谱系页**：谱系明细在台账详情页里看，避免产品详情页多出页签 |
| `views/product_product_views.xml` | 变体表单的来源分组、变体列表可选列、变体搜索（按来源变体 / 所属转换） |
| `views/product_variant_conversion_views.xml` | 转换台账的列表 / 详情视图与动作 |
| `security/ir.model.access.csv` | 两个模型的访问规则（`base.group_user` 与 `product.group_product_variant`） |
| `tests/test_product_variant_conversion.py` | 47 项自动化测试（拦截、预览、归属确认、拒绝删减、属性主数据拦截、按需生成属性的「只展开『立即』轴 / 按需轴钉住既有取值 / 建产品时拦截」、**订单期自建变体不接管（边界）**、台账与谱系、库存与订单行不变、字段归属审计、变体级属性保留、新变体继承与开关、原产品资料保留、价格分离与共享边界、组合上限、钩子与 chatter（含**一次加两个属性**的 chatter 回归）、加取值时的来源映射与尺寸落到对应变体、装了 `product_dimension` 时的尺寸继承、装了 `product_reference` 时的共享参考号交接） |
| `i18n/zh_CN.po` | 简体中文译文（源语言 `en_US` 写在代码里，无需 `en_US.po`；`i18n/` 不进 `data`）；含应用列表元数据条目 |
| `tests/test_product_variant_mapping.py` | 8 项映射表自动化测试（当前配置全部已映射 / 加属性后变未映射 / 选值后恢复 / 未映射阻止保存 / 单取值轴自动补 / 按需轴自动补 / blocked 走不通 / 初始状态字段是合法 JSON） |
| `README.md` | 用户可见功能、字段表、映射怎么指定、被拒绝的情况、已有业务数据处理、验证清单 |
| `CHANGELOG.md` | 逐版本「变更 / 影响 / 文档」记录 |
| `AGENTS.md` | 本文件：核心约束、i18n 规则、文件职责、踩坑档案、变更规范 |

---

## L2：踩坑档案

> 按主题归档的实现陷阱。L1 约束标注的触发条件下必读，其他时候按需查阅。

### P1：变体生成、归属与保留原记录（改 `models/product_template.py` 前必读）

**触发条件**：任何触碰 `attribute_line_ids` / `_create_variant_ids` / `product.product.write` / 归属判定的改动。

**四条已核实的 Odoo 19 事实**（对照镜像内 `odoo/addons/product/models/`）：

1. `product.template.write()` 里触发变体生成的判断是
   `if self.env.context.get("create_product_product", True) and 'attribute_line_ids' in vals: self._create_variant_ids()`
   → 带 `create_product_product=False` 写 `attribute_line_ids` 不会生成变体。
   同一开关在 `product.template.attribute.line._update_product_template_attribute_values()` 末尾也有一份，
   所以 ptav 的增删同样不会顺带生成变体。
2. `_create_variant_ids()` 先算 `existing_variants = {variant.product_template_attribute_value_ids: variant}`，
   再用 `_filter_combinations_impossible_by_config()` 遍历所有可能组合：命中字典的进 `variants_to_activate`（复用），
   没命中的进 `variants_to_create`；最后 `variants_to_unlink += all_variants - current_variants_to_activate`。
   → 「把每条既有变体锚定到它自己的组合」= 让它们全部落进 `variants_to_activate`，它们就不会被删。
   字典键与查找值都是 **recordset**（`concat` 后的 `product.template.attribute.value`），
   靠 `BaseModel.__hash__ = hash((self._name, frozenset(self._ids)))` 匹配，顺序无关。
   **注意**：匹配用的组合元组每个属性只有一个取值，所以锚定值必须是「每属性恰好一个」。
3. `product.product.unlink()`：`if self.env.context.get('create_product_product') is False: return super().unlink()`
   —— 即绕过「删掉最后一个变体时连带删模板」的逻辑。**不要**在转换流程里带这个上下文去删变体。
4. `_create_variant_ids()` 里的 `single_value_lines` 分支：只有 1 个取值的属性行会被自动写到所有变体上
   （Odoo 保证「加单取值属性不重建变体」的机制）。因此「只加一个取值的属性」是一次合法转换：
   变体数不变、没有新变体，但每条既有变体都会带上这个取值 —— 也正是判断「需不需要映射」的依据
   （组合数变多才需要确认归属）。

**为什么不能拿「原生写法」当判据**：原生写法在「加属性 / 加取值」时本来就会把既有变体删掉重建
（它们不再匹配任何新组合）。所以分析用的是 `create_product_product=False` 的试写：
只写配置、ptav，既有变体完全不受影响，也没有「先删再回滚」带来的级联删除 / 附件残留风险。

**归属与新变体来源的判定**：

- 归属组合 = 「该变体在改动前就存在的属性行上的取值」∪「归属表里为本次处理的属性指定的取值」；
  改动前不存在的属性行（本次新加）必须由归属表指定（`_get_variant_conversion_anchor_values`）。
- 新变体的来源（谱系 `origin_variant_id`）= 它在**改动前就存在的属性轴**上的取值，与哪条既有变体一致；
  判定不唯一时宁可留空（`_create_variant_conversion_lineage`）。
- 「能不能再锚定」（会不会丢变体）= 变体现有取值里，凡属性还在新配置中的，其取值必须仍然保留；
  属性行被删掉本身不影响（那只是少一个属性轴），但组合数变少（< 既有变体数）同样会丢变体 → 一并拒绝。

**最终实现**（`models/product_template.py` 的 `write()`）：

```python
if "attribute_line_ids" not in vals or not self.env.context.get("create_product_product", True):
    return super().write(vals)          # 模块自己的「只写配置」模式，必须放行（否则递归）
...
affected = self._analyze_variant_conversion_write(vals["attribute_line_ids"])
if 会丢变体:  raise UserError(...)
if 不新增变体:  return super().write(vals)
if 还有未映射的变体:  raise UserError(...)   # 前端映射表接管
self.with_context(create_product_product=False).write({"attribute_line_ids": ...})  # ① 先写配置
self._convert_to_multi_variant(..., previous_attribute_lines=..., added_attributes=...)  # ② 再安全转换
return super().write(其余字段)              # ③ 其余字段照常落库
```

**维护提醒**：

- `_filter_combinations_impossible_by_config()` 与 `attribute_line._without_no_variant_attributes()` 是 Odoo 内部方法，
  Odoo 升级需回归（后置断言用「计算出的预期变体数 == 实际变体数」把这类 API 变化暴露成明确报错）。
- ③ 那一步会把属性行排除在外（`attribute_line_ids` 已在 ①②写过了）：再写一次会让 Odoo 为同一个属性
  建出**重复的属性行**。
- ①②之后调用的转换必须带 `previous_attribute_lines` / `added_attributes`（改动前快照），
  否则谱系会拿「改动后的属性轴」去判断来源，`variant_origin_id` 会全部留空。

### P2：i18n 术语抽取与 po 维护（改视图 / 文案 / po 时必读）

**触发条件**：新增 / 修改视图节点、模板文本、字段文案、Python `_()`、JS `_t()`、`i18n/zh_CN.po` 时。

**陷阱 1：内联元素整块成术语**
- 现象：`<span class="text-muted">Adds variants…</span>` 抽取出的术语是**含标签的整段 XML**，按纯文本写的 `msgid` 对不上，界面永远显示英文。
- 根因：`span` / `b` / `i` / `kbd` / `code` / `option` / `select` 等在 `odoo/tools/translate.py` 的 `TRANSLATED_ELEMENTS` 里，
  该元素及其内容会被当成**一个**术语；`div` / `p` / `th` / `td` 不在其中，文本节点才是独立术语（带 `t-*` 属性的元素也会退化成独立文本节点）。
- 正确做法：说明性文字放在 `div` / `p` 里；映射表里的选项文案、提示句一律用 JS getter + `_t()`（再 `t-esc`），不要写成模板文本节点。

**陷阱 2：句子被元素切碎**
- 现象：「还差 N 条」写成 `还有 <t t-esc="n"/> 条没指定` 会变成三个术语碎片。
- 正确做法：JS 侧 `_t("%(count)s existing variants still have no combination", {count})` + `t-esc`。

**陷阱 3：字段级 `domain` 会被 Odoo 19 应用到服务端查询**
- 现象：`domain=[("id", "in", "allowed_value_ids")]`（list 形式）读该字段时报
  `invalid input syntax for type integer: "allowed_value_ids"`。
- 根因：`fields_relational.py::_get_query_for_condition_value()` 会把字段 `domain` 注入 comodel 查询，
  而 `get_comodel_domain()` 只对**字符串** domain 返回 `Domain.TRUE`（字符串型 domain 是「只给客户端求值」的约定）。
- 正确做法：带字段引用的 domain 一律写成**字符串**；服务端安全靠自己的校验兜住。

**陷阱 4：`product.attribute.value.display_name` 已经是「属性: 取值」**
- 正确做法：拼「属性: 取值」时取值用 `.name`，属性用 `.display_name`。

**陷阱 5：模型 `_description` 与模块名同字面会撞 `msgid`**
- 现象：`check_repo.py` 报重复 `msgid`（模块名要进「应用」列表，模型描述也要翻译，同一个 `msgid` 却想要两种译文）。
- 正确做法：让模型 `_description` 与 manifest `name` 措辞不同（本模块用 `Variant Conversion Log`）；
  实在要同字面时把两条 `#:` 引用**合并**成一条。

**自查方式**（比 `task check` 更彻底）：

```bash
# 1) 用官方 CLI 导出术语骨架（含 #: 引用，msgid 与源码逐字符一致；JS _t 与模板文本都会带上）
docker compose -f .dev/compose.yml run --rm -T odoo \
    odoo i18n export -d dev -l pot -o /mnt/extra-addons/product_variant/_export.po product_variant
# 2) 核对 _export.po：新增 / 改过措辞的条目补译文，然后按 msgid 合并回 i18n/zh_CN.po
#    （元数据三条要单独手写，导出向导不会带出来，见根 AGENTS.md 4.8）
```

预期结果：只有 `Created by` / `Created on` / `Display Name` / `ID` / `Last Updated by` / `Last Updated on`
（标准审计字段标签，界面上不显示）不需要译文。

**每次改完必须跑**：`task check` → `task update` → `task i18n -- zh_CN product_variant`（确认 po 能正常导入）→ 强刷浏览器。

### P3：Odoo 19 的字段与命名坑（新增字段 / 模型时必读）

**触发条件**：给模型加字段、加 m2m、给 `product.product` / `product.template` 加字段时。

**陷阱 1：m2m 自动关系表名过长**
- 现象：`ValidationError: Table name '…' is too long`，模块直接装不上。
- 根因：自动表名是 `%s_%s_rel`（模型 `_table` + comodel 表名），PostgreSQL 标识符上限 63 字节。
- 正确做法：模型名 + comodel 名较长时显式指定 `relation=`。

**陷阱 2：o2m 子行 create 不会自动补父级必填字段**
- 现象：`null value in column "product_tmpl_id" ... violates not-null constraint`。
- 正确做法：`product.variant.conversion.lineage_ids` 的行里显式带 `product_tmpl_id`。

**陷阱 3：`is_storable` 属于 `stock` 模块**
- 正确做法：写入前先判断 `"is_storable" in model._fields`（测试里的 `_create_product` 已这么做）。

**陷阱 4：`product.product` 通过 `_inherits` 继承 `product.template` 的字段**
- 现象：给 `product.template` 加的字段会同时出现在 `field_product_product__…` 上（导出 po 时能看到两条引用）。
- 正确做法：正常现象，别去「修」；给模板加字段时注意不要与变体上已有字段语义冲突。

**陷阱 5：多记录集不能取 `.display_name` / `.id` 这类「单值」属性**（`19.0.5.3.2` 实测踩过）
- 现象：目标环境一次加两个属性时 `web_save` 报
  `ValueError: Expected singleton: product.attribute(2, 1)`，栈指向 `_log_variant_conversion()`。
- 根因：`added_attributes` 是**属性记录集**（一次加 Color + Size 就是两条），
  对多记录集取 `.display_name`（或 `.id`）会 `ensure_one()` 失败；它在转换的最后一步，抛错即**整单回滚**。
  一次只加一个属性时是单条记录，所以 44 项测试都没碰到 —— **凡「个数可变」的记录集，取值一律走 `mapped()` / 循环**。
- 正确做法：`", ".join(recordset.mapped("display_name")) or "-"`（空记录集要保留兜底值，
  本模块「只追加取值、不加新属性」时 `added_attributes` 就是空的）。
- 排查口径：`grep -rn "\.display_name\|\.id\b" models/`，逐个确认接收方是 `ensure_one()` 的记录还是记录集。

### P4：保存拦截与映射表（改 `static/src/**` 或 `write()` 时必读）

**触发条件**：改保存拦截、映射表、归属载荷格式时。

**机制（已核实 Odoo 19 源码）**：

- `web/static/src/model/relational_model/record.js::_save()` 里有
  `const canProceed = await this.model.hooks.onWillSaveRecord(this, changes); if (canProceed === false) return false;`
  → `onWillSaveRecord(record, changes)` 是官方保存前钩子：**返回 false 即阻止保存**，`record` 保持 dirty（用户的编辑不会丢）。
- 同一个 `_save()` 紧接着 `await this.model.orm.webSave(this.resModel, [this.resId], changes, kwargs)`
  → **`changes` 就是发给 `web_save` 的 `vals`**，所以在钩子里往 `changes` 里塞字段是官方支持的「随本次保存提交额外数据」写法。
- `FormController` 在 `getModelParams` 里把 `this.onWillSaveRecord.bind(this)` 注册成该钩子
  → patch `FormController.prototype.onWillSaveRecord` 即是官方扩展点（不要 patch `Record._save`）。

**本模块的用法**：

- 只在 `record.resModel === "product.template"`、有 `resId`、且本次 `changes` 里含 `attribute_line_ids` 时介入；
- 调 `orm.call("product.template", "get_variant_mapping_preview", [[resId], changes.attribute_line_ids, selection])`
  （把服务端原本要写的那组命令原样过去，服务端在保存点里试写 + 回滚后给出结论；`selection` 是映射表里用户
  已选的取值 `{变体 id: {属性 id: 取值 id}}`，面板没挂载时为 `{}`）；
- `preview.blocked` → 提示并 `return false`；`preview.unmapped_count > 0` → 提示还差几条并 `return false`；
  都映射好了 → 把归属塞进 `changes.variant_conversion_mapping` 后放行（`preview.required` 时）；
- 映射表的状态放在 **`model.variantMapping`**（`getMappingStore(model)`）而不是组件里：面板挂在「属性与变体」
  页里，切到别的页签会卸载；存在 model 上，保存钩子与面板共享同一份数据，切页签不丢选择。

**陷阱 1：递归**
- 服务端的 `_analyze_variant_conversion_write()` 与 `_convert_to_multi_variant()` 都会用
  `with_context(create_product_product=False)` 写 `attribute_line_ids`，而 `write()` 的第一道判断必须把这种写入放行，
  否则会无限递归（实测 `RecursionError`，且栈里全是 `sql_db.py` 的 savepoint，很难看出根因）。

**陷阱 2：还有未映射变体时必须真的不保存**
- 「先提示、保存照做」是错的：钩子必须返回 `false`（本次保存不执行），把「保存」这个动作交给用户在映射表里
  挑完之后的第二次保存。挑取值只改面板状态（在 `model.variantMapping` 上），不写库；表单一直保持 dirty，
  挑完再点保存才真正落库。

**陷阱 3：塞进 `changes` 的字段服务端要认**
- 钩子直接给 `changes.variant_conversion_mapping` 赋值（不经 `record.update()`），所以不依赖该字段在视图里
  是否可编辑；但**服务端 `write()` 必须处理它**。视图里仍以 `invisible="1" force_save="1"` 登记，
  排查时 `changes` 里能直接看到它。

**陷阱 4：`assets` 新增文件必须 `-u`**
- 本模块的三个前端文件登记在 `__manifest__.py` 的 `assets.web.assets_backend`；新增 / 改文件名后必须
  `-u`（或重启进程）+ 强刷浏览器，否则前端钩子不会生效（表现就是「点了保存但没有映射表，只报错误提示」）。

**陷阱 5：保存入口不是 `this.model.save()`（实测踩过）**
- 现象：弹窗点确认后控制台报 `Uncaught Promise > this.model.save is not a function`。
- 根因：`RelationalModel` 上**没有** `save`。保存入口在 **Record** 上（`this.model.root.save(options)`），
  控制器层还有 `FormController.save(params)`（内部 `record.save({ onError: this.onSaveError, ...params })`，
  并尊重 `props.saveRecord` / `props.onSave`）。
- 正确做法：在映射表 / 钩子的回调里用 `await this.save()`（`this` 是 FormController）；
  **不要**用 `this.model.save()`，也不要直接 `this.model.root.save()`（会绕过控制器的错误处理）。
- 参考：`web/static/src/views/form/form_controller.js` 里 `save()` / `create()` / `saveButtonClicked()`
  统一走 `this.model.root.save({ onError })`。

**陷阱 6：承载前端回传数据的技术字段必须 `force_save="1"`**
- 现象：映射表挑完后保存又被拦一次、提示反复出现，且没有任何报错。
- 根因：`Record._getChanges()` 对「在 activeFields 里、但 `_isReadonly(fieldName)` 为真且没标 `forceSave`」
  的字段直接 `continue`，该字段不会进 `changes`，也就不会随 `webSave` 提交。
- 正确做法：`variant_conversion_mapping` 在视图里写 `invisible="1" force_save="1"`（模型字段本身保持可写）。
  改这个字段的属性（尤其加 `readonly`）前，先确认 `changes` 里还能看到它。

**陷阱 7：映射表字段必须 `readonly="0"`**
- 现象：映射表渲染出来了，但每个下拉都是禁用的，用户补不了映射。
- 根因：`variant_mapping_state` 是 `store=False` 的字段（`19.0.7.0.5` 起**不做 compute**，见陷阱 12），
  非存储字段在表单里可能被当成只读 → 面板的 `props.readonly` 为真，下拉全禁用。
  （实测该字段现在 `readonly=False`，但视图里显式写 `readonly="0"` 最稳，防将来 Odoo 把非存储字段标只读。）
- 正确做法：视图里显式写 `readonly="0"`（Odoo 的视图修饰符解析认 `'0'` 为假：
  `base/models/ir_ui_view.py` 里 `node.get('readonly') not in ('1', 'True')` 那一路）。

**陷阱 8：字段组件必须注册成描述对象，不能注册裸类**（2026-09-24 实测踩过，整个产品表单打不开）
- 现象：打开产品表单（或点开「属性与变体」页签）报
  `UncaughtPromiseError > OwlError`，cause 是
  `TypeError: Cannot read properties of undefined (reading 'name')`，栈落在 `Field.template`。
  极易误判成「升级后没重启 / 浏览器缓存」（两者都不对：服务端 `get_views` 里字段与视图都正常，
  arch 也有这个字段节点）。
- 根因：`registry.category("fields").add("variant_mapping_panel", VariantMappingPanel)` 把**组件类**
  直接注册了。`web.Field` 模板渲染的是 `field.component`（`views/fields/field.xml`：
  `t-component="field.component"`），官方注册的是**描述对象**，所以裸类下 `field.component` 是
  `undefined` → owl 创建子组件时读它的 `name` → 崩。注意报错栈只指到 `Field.template`，
  **不会**提到你的组件名，很容易查错方向。
- 正确写法（对照 `web/static/src/views/fields/char/char_field.js` 末尾）：

  ```js
  export const variantMappingPanelField = {
      component: VariantMappingPanel,
      displayName: _t("Attribute / Variant Mapping"),
      supportedTypes: ["text"],   // 本组件只服务 Text 类型的字段
  };
  registry.category("fields").add("variant_mapping_panel", variantMappingPanelField);
  ```

- 自查：`grep -rn 'category("fields").add(' <module>/static/src/js/` —— 第二个参数必须是
  `{ component: ... }` 对象，不能是裸标识符。
- 顺带：改完前端资源仍然要 `-u`（或重启进程）+ Ctrl+F5 强刷，否则加载的还是旧 assets。

**陷阱 9：模板表达式只能引用组件实例上真实存在的名字**（2026-09-24 实测踩过）
- 现象：`UncaughtPromiseError > OwlError`，cause 是
  `TypeError: Cannot read properties of undefined (reading 'blocked')`，栈落在
  `VariantMappingPanel.template`（模板自己的函数名，好定位得多）。
- 根因：`setup()` 里这份状态叫 `this.store`（`useState(getMappingStore(...))`），而模板里写的是
  `state.blocked` / `state.rows` / `state.dynamic`。**`state` 在 OWL 模板里不是保留字**
  （只有 `props` 是），它只是一个不存在的名字 → `undefined.blocked`。
- 正确做法：模板里用 `store.xxx`；模板能直接访问的是**组件实例上的 getter / 方法 / 属性**，
  写法与 JS 里 `this.` 后面那段完全一致。
- 自查：改模板后把表达式里的根标识符过一遍 —— 每个都必须在组件上是
  `get x()` / `x()` / `this.x = ...`，或者来自 `t-as` 的循环变量（`t-foreach` / `t-esc` 的
  `<var>` 加 `_index` / `_value` / `_first` / `_last`），或 OWL 内置的 `props`。

**陷阱 10：自定义字段 widget 要在视图里自己撑满一行**（2026-09-24 实测）
- 现象：面板渲染出来了，但显示在「属性与变体」页**右侧**（与属性行并排），还被表单宽度裁掉、看不见。
- 根因：`web.Field` 给字段套的外层 `<div class="o_field_widget">` 是 `display: inline-block`，
  而同一页里的 `attribute_line_ids` 也是 inline-block 且宽度不是 100% → 两个字段并排，
  面板溢出 `o_form_sheet` 的可视宽度。
- 正确做法：视图里用一层块级 div 包住（字段本身也加 class，双保险）：

  ```xml
  <xpath expr="//page[@name='variants']/field[@name='attribute_line_ids']" position="after">
      <div class="d-block w-100">
          <field name="variant_mapping_state" widget="variant_mapping_panel" nolabel="1"
                 readonly="0" class="d-block w-100"/>
      </div>
  </xpath>
  ```

- 判断标准：组件是**表格 / 多行块**（不是 input / 单项）就一律按「独占一行」写；改完 `-u` + 强刷。

**陷阱 11：预览类 RPC 要能容忍「半成品」命令**（2026-09-24 实测踩过）
- 现象：在产品表单「属性与变体」页点 **Add a line**（还没选属性）就弹
  `Validation Error: Missing required value for the field 'Attribute' (attribute_id)`；
  可复现、且与保存无关 —— 只是点了个按钮。
- 根因：o2m 新增行时前端 `record.getChanges()` 生成的是
  ``[0, 0, {"value_ids": [...]}]``（**没有** ``attribute_id``）。映射表的防抖刷新把它原样发给
  ``get_variant_mapping_preview()``，服务端在 savepoint 里试写这条命令 → 必填缺失 →
  ``psycopg2.errors.NotNullViolation`` 冒泡到 RPC 层，被转成上面那句报错。
- 正确做法（三层都要，缺一层就漏）：
  1. **前端**：调预览前先过滤 —— `hasIncompleteLine(commands)` 认出「新建且没有 attribute_id」的命令，
     这种状态下*不调 RPC*，保持上一次的显示；
  2. **服务端分析入口**：`_sanitize_attribute_line_commands()` 丢掉这类行，
     同一次提交里正常的那几条照常参与分析；
  3. **服务端 RPC 兜底**：`get_variant_mapping_preview()` 捕获 `NotNullViolation` 回
     ``incomplete=True``（映射表不改状态、保存钩子 `return super.onWillSaveRecord(...)` 交回原生校验）。
     注意**只兜** ``NotNullViolation``：Odoo 原生的解释性 `UserError`
     （例如「不能把属性 A 改成 False」）要原样透出，吞掉用户就看不懂为什么改不了。
- 判断标准：任何「拿表单未保存内容去服务端算一遍」的 RPC 都要先问「这些命令在**写库的那一步**一定合法吗」。

**陷阱 12：给前端看的状态不要做成 compute 字段**（2026-09-24 实测踩过）
- 现象：点 Add a line 后随便选一个属性就 500 ——
  ``TypeError: Object of type NewId is not JSON serializable``，栈落在
  ``_compute_variant_mapping_state``，前端收到 ``RPC_ERROR``。
- 根因：该字段原本是 ``@api.depends("attribute_line_ids", ...)`` 的 compute。Odoo 的
  ``onchange``（``web/models/models.py::onchange`` 里对每个变更字段做 ``has_changed``）会**求值**它，
  而那一刻表单里还有**没保存的行**（用户刚 Add a line），这些行的 id 是 ``NewId`` ——
  ``json.dumps`` 序列化不了。
- 正确做法：把它降级成**纯挂载点**（``fields.Text(store=False)``，**不写 ``compute``**），面板挂载时自己
  调预览 RPC 取初始状态、属性行变化时防抖再取。字段只负责给 widget 一个挂载位置。
- 判断标准：**compute 会在 onchange（含未保存的虚拟记录）里被求值**，所以 compute 里不要做
  「序列化表单内容 / 假定 o2m 已保存 / 重活」；能给前端按需 RPC 的就别做成 compute。
  另外：写 ``json.dumps`` 之前一律先想「里面会不会混进 ``NewId``」。

**陷阱 13：编辑期的计算放前端，服务端只在保存时参与**（2026-09-24 实测，用户明确要求）
- 现象（``19.0.8.0.0`` 之前）：点 Add a line 就报 ``Missing required value for the field 'Attribute'``；
  把某个属性的取值逐条删到空时弹 ``The attribute X must have at least one value``；
  给产品加了有 3 个取值的属性，面板只认第一个取值、还标成「已映射」。
- 根因：映射表每改一下就把「表单还没保存的命令」发给服务端试算。表单的中间态（空行、空取值、
  新建行）在服务端眼里就是**非法写入**，用户一边填一边被校验拦；而「按需生成」轴又默认取了
  第一个取值，等于悄悄替用户做了归属决定。
- 正确做法：
  1. **挂载时取一次快照** ``get_variant_mapping_snapshot()``（既有变体带着哪些取值 + 各属性的
     ``create_variant``）；它只描述已保存的事实，天然不会被中间态污染；
  2. 其后属性行增删、勾取值、挑映射全部用**前端纯函数**算（``computeVariantMapping()`` /
     ``readColumnLines`` 的 ``readAttributeLines()``），属性行一改只做本地重算；
  3. **保存**时才把映射结果随表单一起提交，服务端照旧做权威判定与安全转换（会丢变体、未映射）；
  4. **每个组合都要有归属**：组合表里没被任何既有变体选走的组合 = 新建变体，没被任何组合认领的既有变体 = 拦住保存（映射表在上方点名）。
- 判断标准：凡是「拿表单未保存内容去服务端算一遍」的设计，先问「中间态在服务端是不是合法」；
  能用一次性快照 + 前端纯函数解决的，就别逐次 RPC。

**陷阱 14：读「表单当前编辑态」要用 `getChanges()` 合并基线，别读 record 内部结构**（2026-09-24 实测踩过）
- 现象：在表单里新加一个属性，映射表**毫无反应**（表格里没有新列）。
- 根因：原来读 ``record.data.attribute_line_ids.records[].data.value_ids.records`` 拿「编辑中的取值」。
  ``record.data`` 是 ``{..._values, ..._changes}`` 拼出来的，**编辑中的 o2m 子行 / m2m 取值可能是命令数组**
  （``[[0, 0, vals]]`` / ``[[1, id, vals]]``）而不是 record 列表 —— 于是取值被读成空，
  那一行就不成为轴（``computeVariantMapping()`` 只把「有取值的行」当轴）。
- 正确做法：
  1. 快照里给一份**已保存基线** ``lines``（``{id, attribute_id, value_ids}``）；
  2. 用 ``record.getChanges({ withReadonly: true })`` 拿命令（**本地，不发请求**），
     纯函数合并出编辑态：``mergeAttributeLines()`` 处理行级命令，``applyValueCommands()`` 处理 m2m 命令
     —— 注意 m2m 的 **set**（``[6,0,ids]``）与**增量**（``[4,id]`` / ``[3,id]`` / ``[5]``）语义不同，
     增量当替换会把用户原来勾的取值丢掉；
  3. 名称 / 属性归属 / 生成方式**一律从快照字典查**（前端手里只有 id）。
- 判断标准：凡是「从 record 里读 o2m / m2m 的当前编辑内容」，优先走 ``getChanges()``；
  要读字段值就用公开 API，别依赖内部表示。
- 自查：面板纯函数可以脱离浏览器验证 —— 跑 ``node product_variant/tests/js/variant_mapping_pure.mjs``
  （它自己抽纯函数段，喂真实形状的「基线 + 命令」跑断言，见陷阱 15 的脚本）。

**陷阱 15：合并 `getChanges()` 命令时，虚拟行的 id 必须原样保留**（2026-09-24 实测踩过）
- 现象：单变体产品里加一个多取值属性（Color: Black/Red），映射表**毫无反应**（没有 Color 列）。
- 根因：新建行时**自己造了 id**（``new-0``）。用户点 Add a line 之后，「选属性」「勾取值」在 Odoo 眼里
  是对**同一个虚拟行**的后续更新（``[1, 0, {...}]``，用的是它自己的虚拟 id ``0``）——
  找不到 ``new-0`` 那一行，``attribute_id`` / ``value_ids`` 永远落不到行上，那一行就不是轴。
- 正确做法：
  1. ``[0, first, vals]`` 的行 id 就用 **``first``**（Odoo 的虚拟 id，通常是 ``0`` 或 ``virtual_xx``），别另造；
  2. ``[1, id, vals]`` 在基线里找不到对应行时，**当成新建的虚拟行接住并追加**，不要 ``continue``；
  3. 自测一定覆盖「Add a line → 选属性 → 勾取值」这三步的命令序列（Add a line 只发 ``[0, id, {}]``，
     字段值是后面两条命令才带上来的）。
- 固化：``tests/js/variant_mapping_pure.mjs``（``node`` 直接跑，不需要 Odoo 与浏览器）。

**陷阱 16：`useRecordObserver` 不会因为「子表里改字段」而触发**（2026-09-24 实测踩过）
- 现象：在「属性与变体」页加属性、勾取值，映射表**一点都不动**（停在挂载时那一次的状态）。
- 根因：``useRecordObserver(cb)`` 的实现是 ``effect(cb, [props.record])``
  （``web/core/utils/reactive.js``）—— 依赖**只有 record 对象本身**；编辑表单时这个引用不变，
  而「选属性 / 勾取值」改的是**子 record** 的字段，不保证让父 record 的 effect 重跑。
  回调里如果**什么都不读**，就更没有其它触发点（``19.0.8.0.0`` 就把回调简化成了什么都不读）。
- 正确做法：**订阅承载子表的那个组件** —— patch ``X2ManyField`` 与 ``ListX2ManyField``
  （``@web/views/fields/x2many/x2many_field`` / ``list_x2many_field``），在 ``onPatched`` 里通知需要重算的
  组件：子表每次变化它们必然重渲染。再保留 ``useRecordObserver`` 覆盖 record 级变化，
  并在要求「必然生效」的地方加**低频本地自检**兜底（纯函数重算 + 签名去重，稳定时零开销）。
- 包装原 ``setup`` 用 ``const originalSetup = Klass.prototype.setup;`` + ``originalSetup?.call(this)``，
  不要假设每个类都有 ``setup``（``ListX2ManyField`` 直接继承 ``Component``）；
  判断「是不是我的表单」用 ``props.record?.resModel`` / ``props.name``，取值时两个来源都试
  （``props.record?.model`` 或 ``props.list?.model``）。
- 判断标准：**别指望「父 record 的 observer」感知子表编辑**；要感知就订阅子表组件本身。

**陷阱 17：「默认值 / 兜底值」不能当成「用户确认过的值」写回状态**（2026-09-24 实测踩过）
- 现象：某属性起初只有 1 个取值（面板替 Odoo 把那个取值显示到所有变体上、算「已映射」），
  用户随后又勾了第二个取值 → 面板**仍然**显示旧取值、仍算已映射，该回到未映射的变体一条都没进
  未映射列表（用户实测：Length 从只有 140 变成 140+120，6 条变体全被显示成 140 且 Mapped）。
- 根因：``buildSelectionPayload()`` 把「面板当前显示的取值」一律当「用户的选择」写回 selection，
  包括**自动补的默认值**；下一轮重算它又被当成用户选择 ⇒ 自我固化，回不到未映射。
- 正确做法：轴状态带 ``picked`` 标记（只有用户在控件里选过才是 true，含「选回空」），
  只把 ``picked`` 的项写回 selection；自动补的值、变体本来就带着的值都只是「当前显示」。
- 判断标准：「默认值 / 派生值 / 用户确认值」三者在状态里必须**分开记**，别混成一个 ``value_id``。

**陷阱 18：组合归属用「组合为行、选变体」，不要用「变体为行、选属性」**（2026-09-24 两次迭代后定稿）
- 需求：改属性后要让用户确认「每条既有变体落到哪个组合」，且**组合不能重复**、**要能交换位置**。
- 走过的弯路：
  1. 先是「变体为行、逐轴选值」+ 禁用会造成冲突的选项 —— 防重没问题，但**交换位置**很难受：
     两行互相占着对方的组合时，后改的那一行没有可选值（用户实测反馈「变体下拉需要能够清空，
     以便交换位置」）；
  2. 定稿为「**组合为行、选变体**」：行是算出来的组合，每行的 Variant 下拉留空 = 新建变体、
     选一条 = 由它保留；同一条变体只能占一行，**已被别的行选走的变体在这一行的下拉里禁用**
     （要换位置先把自己那行改回 `(new variant)` 让出来，见陷阱 19），组合也天然不重复（行就是组合）。
- 实现要点：
  1. 行 = 各属性有效取值的笛卡尔积（**含「按需生成」的全部取值**，属性列只读）——前端**穷举展示**是为了让人看清全貌、能提前分配；
  2. **预建仍按属性规则**：立即轴展开、按需轴只建「被既有变体认领的取值」（前端用 ``row.will_create`` 标出来，不会创建的行显示为灰色 + 提示）；带按需属性的产品仍然不做价格分离；
  3. 默认分配：把「本来就属于这一行」的变体（在**立即**轴上取值全等）放回它的行；用户**显式清空**过的行
     （``store.cleared``）不再自动填回；
  4. 拦截条件从「未映射」变成「**没被任何组合认领的既有变体**」；保存载荷仍是
     ``{mapping: [{values, origin_variant_id}]}``（组合 → 归属），与服务端契约天然一致，服务端零改动。
- 判断标准：两个集合做配对时，**让「另一侧必须满足的约束」当行**（这里组合是算出来的、变体是要保住的），
  另一侧用「可留空的下拉」选 —— 配对不会撞车，交换也不需要额外规则。

**陷阱 19：占位类交互要「禁用」而不是「隐式抢占」**（2026-09-24 用户实测反馈）
- 需求原话：下拉里**已选的变体应该变灰色、不能选**；要换位置只能先把其中一个改为 `(new variant)` 再换。
- 早期做法是「选到别的行时自动从原行让出」（`19.0.6.1.0` 的归属弹窗、映射表沿用）—— 两条变体互换时
  用户改哪一行都像是从另一行「抢走」，看不出谁让给谁，三条以上更容易改乱。
- 正确做法：
  1. 纯函数给出「当前被哪一行占着」：`buildVariantOptions(variants, rows)` → 每项 `taken_by`（组合 key）；
  2. 模板里禁用：`t-att-disabled="isOptionTaken(option, row)"`，`taken_by` 存在且不是自己这一行 → 灰显，
     并用 `title` 说明「先把那一行改回 (new variant)」；
  3. 事件里再防御：`onSelectVariant()` 若发现目标被别行占着就直接返回（程序化赋值绕过 UI 时也不改状态）。
- 判断标准：一对一 / 一对多的**占位**交互，让用户**显式释放**比隐式抢占好；同时别忘给「怎么换」的出路文案。


**陷阱 20：纯前端的「脏」要自己广播给状态指示器，别把状态塞进 record**（2026-09-24 实测）
- 需求：映射一改就要出现 **Save manually** / **Discard all changes**；同时不能让 Odoo 的自动保存
  把映射偷偷写进去；未映射的变体存在时必须拦住保存。
- 事实（Odoo 19 源码）：
  - 那两个按钮是**原生** `FormStatusIndicator`（`data-tooltip="Save manually"` / `"Discard all changes"`），
    显示条件是 `model.root.dirty || fieldIsDirty`，而 `fieldIsDirty` 由 `model.bus` 上的
    `FIELD_IS_DIRTY` 事件驱动（`web/static/src/views/form/form_status_indicator/form_status_indicator.js`）；
  - `Record._save()` 在「没有 changes」时**直接早退**（`return true`），**不会**调用
    `onWillSaveRecord` —— 只改了映射（属性行没动）时点保存，钩子根本不会被调用；
  - `beforeLeave()` / `beforeVisibilityChange()` 的自动保存判据是 `model.root.dirty`（record 的字段改动）。
- 正确做法：
  1. 映射改动时 `model.bus.trigger("FIELD_IS_DIRTY", true)`（本模块 `setMappingDirty()`），
     **千万不要**为了「让表单变脏」把映射塞进 record 的字段 —— 那会让离开页面 / 切标签时自动保存，
     违背「必须由用户显式保存」；
  2. patch `FormController.save()`：`const mappingOnly = record.resId && !record.dirty && store.dirty;`
     → `super.save()` 成功后补一次 `product.template.write({variant_conversion_mapping: ...})`；
  3. patch `FormController.discard()`：`super.discard()` 之后再 `discardMappingChanges(model)`，
     把 assignment 恢复成基线（`store.baseline`：面板首次算完、每次保存成功后重建）；
  4. 「有没有改动」用 `mappingDiffersFromBaseline()` 判定（**键顺序无关**的签名比较，
     `JSON.stringify` 直接比会因为插入顺序不同而误判），默认分配属于基线、不算改动。
- 判断标准：Odoo 的保存只认 record 的 changes。任何「表单之外的编辑状态」都要自己决定
  要不要参与保存，并把脏状态显式广播给状态指示器 + 自己实现丢弃。


**陷阱 21：保存钩子在 mutex 里 —— 别在里面调 `getChanges()`，顺带关掉属性行的 onchange**（2026-09-25 实测）
- 现象：改完属性行点标题右侧的 **Save manually** → 按钮变灰，网络里**一条保存请求都没发**，
  然后一直灰着点不动，怎么都存不进去。
- 根因（两处，都在 Odoo 19 源码里）：
  1. `Record.save()` 是 `await this.model._askChanges(); return this.model.mutex.exec(() => this._save(options));`
     —— **`_save()` 占着 mutex 跑**（`web/static/src/model/relational_model/record.js`）；
     而 `Record.getChanges()` 是 `mutex.exec(() => this._getChanges(...))`。
     保存钩子 `FormController.onWillSaveRecord()` 正是在 `Record._save()` 里被调用的，里面再
     `await record.getChanges()` 就是**等自己正占着的那把锁** → 死锁，`await` 永不返回；
     `executeButtonCallback()` 的 `enableButtons()` 写在 `finally` 里，也就永远不执行 → 按钮一直灰。
     （面板每秒一次的自检 `scheduleRefresh()` 同理，会把这次重算排到锁后面。）
  2. `ir.ui.view._postprocess_on_change()` 会给「视图里某个 compute 字段的依赖」**自动补**
     `on_change="1"`：`attribute_line_ids` 是 `valid_product_template_attribute_line_ids` 这类
     compute 字段的依赖，于是**每改一次属性行就发一次**
     `/web/dataset/call_kw/product.template/onchange`。本模块的属性改动**全在前端算**
     （挂载时一次快照 + 本地改动，见陷阱 13 / 14），这次调用纯属多余，还要占一次 mutex。
- 正确做法：
  1. **读编辑态走 `_getChanges()`，不走 `getChanges()`**：新增 `readLocalChanges(record)` =
     `record._getChanges(record._changes, { withReadonly: true })` —— `_getChanges()` 与它调的
     x2many `_getCommands()` 都是同步的，本来就不该抢锁；
  2. patch `Record.prototype._getOnchangeValues()`：模型是 `product.template` 且改动里**只有**
     `attribute_line_ids` 时直接 `return {}`（只跳这一次，`standard_price` / `type` / `uom_id`
     这些真有 onchange 的字段照旧）；
  3. 面板下方**不再放** Save manually / Discard all changes 按钮（只留「未保存」徽标 + 一句指向
     标题右侧按钮的提示），保存 / 丢弃一律用 `FormStatusIndicator` 那两个原生按钮；
  4. 保存成功后 `settleMappingAfterSave()`：**作废快照重取**再重建基线 —— 否则 `snapshot.lines`
     仍是上一次保存的属性行，保存后 `record._changes` 一清空，面板会把「旧基线 + 空改动」当成
     当前配置，界面退回保存前的样子，甚至又把「未保存」标记点亮。
- 判断标准：凡是**在 Odoo 的保存 / 丢弃链路里**（`onWillSaveRecord` / `save` / `discard` 的补丁）
  读表单编辑态，都不能用会抢 mutex 的 `getChanges()`；看到「改属性就发 onchange」先想
  `_postprocess_on_change()` 是不是给那个字段补了 `on_change="1"`。

> 附带修复（`19.0.13.0.3`）：删掉唯一属性后，``buildCombinationRows()`` 不能返回空表 ——
> 没有属性时产品本身就是一个**空组合**，要给一行让既有变体挂靠，否则原来的变体会被标成
> 「未分配」、保存被拦。

22. **删唯一属性时，自家的「丢变体」守卫会误伤（`19.0.13.0.4`）**
- 现象：把产品上唯一的属性删掉、点保存，弹出
  ``Removing the attribute … would affect 1 active variants … Archive or delete those variants
  first`` —— 可那条变体正是用户想留下的（映射表里已经把它挂在「空组合」上了）。
- 根因：`product.template.write()` 里 ``expected_count <= before_count`` 且不需要锚定时走
  **原生直写**（`super().write(vals)`），原生会先删属性行 →
  ``product.template.attribute.line.unlink()`` → 本模块 T-017 守卫（约束 17）拦下。
  守卫的前提是「删了它会连坐删 / 归档在用变体」，而映射已经说明变体会被保留。
- 正确做法：带映射保存时**先解析校验映射**（`_parse_variant_conversion_mapping()`，
  它会要求每条既有变体都有组合），再带上下文键
  ``variant_conversion_keeps_variants=True`` 走原生写入；三处守卫认这个键放行
  （`KEEP_VARIANTS_KEY` 常量统一口径）。**不带映射时守卫照旧拦住** —— 没人认领那条变体，
  不能替用户处理掉（用例 `test_removing_the_only_attribute_without_mapping_is_still_blocked`）。
- 判断标准：凡是「放宽守卫」的改动，都要有一个**可校验的前提**（这里是「每条既有变体都有
  组合」），并且**不带前提时行为不变**；不要直接把守卫删掉。
- 第 4 条（`19.0.13.0.6` 补）：**原生直写那条分支没有后置断言**，它的安全靠一条不变量 ——
  走到它意味着「组合数 ≥ 启用变体数」且每条既有变体都带全了所有**多取值**属性行的取值
  （否则 `needs_anchoring`）；**归档变体**若还带着某个活组合，那个组合必然计入
  `expected_count`，而 `before_count` 只数**启用**变体（`_analyze_variant_conversion_write()`
  里 `variants = self.product_variant_ids`），于是 `expected_count > before_count`，流程落到转换
  路径、被 `_check_variant_conversion_allowed()` 以「先恢复或删除归档变体」拒绝；它的组合
  已不是活组合时，`_create_variant_ids()` 用同一套排除规则也不会激活它。
  用例 `test_archived_variants_cannot_slip_through_the_native_save` 钉住这条不变量
  （归档变体 + 「不新增变体」形态 + 映射 → 报 `archived variants` 且整单回滚）。
  **改 `expected_count` / `before_count` / `needs_anchoring` 的算法时必须重跑这条用例。**

23. **面板的说明 / 警告文字必须自动换行、不能顶出 `.o_form_sheet`（`19.0.13.0.5`）**
- 现象：映射表上方那段说明与「N 条变体未分配」的警告是**一整行长句**，直接溢出产品表单纸面，
  横向出现滚动条 / 文字被切掉。
- 根因：面板字段的外层 `.o_field_widget` 在 Odoo 19 里可能是 **CSS Grid 的单元格**，
  长句会按 `max-content` 把网格轨道撑开；再加上参考号这类**没有空格的长词**，
  连普通换行也断不开（`white-space: nowrap` 之外，`overflow-wrap` 默认值也断不了长词）。
- 正确做法：面板的样式放 `static/src/scss/variant_mapping_panel.scss`（并登记进
  `assets` → `web.assets_backend`，见 L1 约束 3）：
  `.o_variant_mapping_panel { max-width: 100%; min-width: 0; }`，
  文本块加 `overflow-wrap: anywhere`（**不是** `break-word`：只有 `anywhere` 会把
  min-content 压小，网格轨道才不被撑开），表格 `table-layout: fixed`，
  「未保存」的 flex 行加 `flex-wrap: wrap`。
- 判断标准：面板里凡是**用户可见的整句文案**，都必须能换行、且整块宽度不超过纸面；
  新增文案后要窄屏（或把窗口拖窄）看一眼，别只看宽屏。

24. **「换了一条产品记录」要自己认：面板状态挂在 model 上，model 是复用的（`19.0.13.0.7`）**
- 现象：产品表单上点 **New**（或用分页翻到下一条产品），`Variants Mapping` 里挂的还是
  **上一条产品**的组合与变体映射；新建的产品还没保存，却显示着别人的映射。
- 根因（两处叠加，都在 Odoo 19 源码里）：
  1. `FormController.create()` / 翻页走的都是 `this.model.load({resId})`
     （`web/static/src/views/form/form_controller.js`），而 model 是 `useModel()` 在
     `setup()` 里建的 —— **同一个 model 实例被复用**，挂在它上面的 `model.variantMapping`
     自然跟着留下来；面板是表单里的字段组件，`t-component` 没有 `t-key` 变化，
     **组件实例也被复用 → `setup()` 不会再跑一次**。于是原来那句「`store.resId !==
     props.record.resId` 就重置」写在 `setup()` 里，根本没机会执行。
  2. `recompute()` 开头只判 `if (!record || !record.resId || !snapshot) return;` ——
     新记录没有 id，直接返回，**旧快照、旧行、旧分配原封不动留在界面上**。
- 正确做法（三处一起改）：
  1. **把「记录换了没有」的判断搬到 `recompute()`**：它同时被 `useRecordObserver`、
     o2m 的 `onPatched` 通知与每秒兜底自检调用，覆盖所有切换路径；发现
     `store.resId !== (record.resId || false)` 就 `resetForRecord()`（作废 + 重取快照）；
  2. `resetMappingStore(store, resId)` 改成**原地清空**（`delete` 老键 + `Object.assign`）：
     `this.store` 是 `useState()` 给的响应式代理，另建新对象 ① 组件与保存钩子
     （`FormController` 里那几个补丁都握着 `model.variantMapping`）各拿一份，
     ② 不经过代理的 set 陷阱，**界面根本不重画**；
  3. 模板根 div 加 `t-if="showPanel"`（已保存的产品 + 快照属于当前记录才显示）：
     新建时没有既有变体可映射；换记录后重算与取快照都是异步的，那几百毫秒里
     不能把上一条产品的映射当成这一条的。
- 判断标准：凡是**挂在 model / env 上、跨组件复用**的状态，都要回答「换记录时谁负责作废」；
  只写在 `setup()` 里的重置逻辑在 Odoo 的表单里**不可靠**（组件与 model 都被复用）。
  验证方式：打开一个有变体的产品 → 点 New（面板应消失）→ 再翻回原产品（映射重新算出来）。

25. **`product.product.unlink()` 会把产品模板一起删掉**（`19.0.13.1.0` 起本模块会删变体，必读）
- 源码（`product/models/product_product.py`）：`unlink()` 先判
  `self.env.context.get("create_product_product") is False` —— 不是 False 时，删完变体会检查
  「模板是不是已经没有变体了」，是就把**产品模板也删掉**；
  另一条分支 `_unlink_or_archive()` 则是「有单据引用就归档、否则真删」。
- 本模块删「不生成变体」的新建变体时必须走
  `to_drop.with_context(create_product_product=False).unlink()`：只删变体本身。
  少了这个上下文键，「这个产品只剩这一条变体」的场景会把整个产品删掉。
- 另一半坑：删 / 建之后 `product_variant_count`（非存储 compute）可能还留在记录缓存里 ——
  后置断言要用 `invalidate_recordset(["product_variant_ids", "product_variant_count"])` 作废缓存再读。
- 判断标准：本模块里任何 `unlink()` 都要回答「会不会连带删掉产品模板」「缓存有没有作废」；
  改动后跑一次「标掉最多的组合」的边界用例（见 L1 约束 1 的例外）。

### P5：业务场景、数据流与一致性边界（评估完整性 / 排障时读）

**触发条件**：判断「某个改动会不会被本模块拦住」、评估业务场景完整性、回答「库存 / 价格为什么没跟着走」时。
数据流时序图见模块 `README.md` →「数据流」；这里只放维护者视角的判据、同步规则与缺口清单。

**覆盖矩阵**（✅ = 有自动化测试锁住）：

| 场景 | 结局 | 处理 | 测试 |
|------|------|------|------|
| 单变体加多取值属性（1→N） | required | 映射表逐条指定组合 | ✅ |
| 多变体加新属性（N→N×M，主场景） | required | 映射表逐条指定组合 | ✅ |
| 给已有属性追加取值 | required | 映射表逐条指定组合 | ✅ |
| 加单取值属性 / 加 no_variant 属性 / 重提同配置 | 不涉及变体 | 原样 `super().write()` | ✅ |
| 删取值 / 删属性行 | blocked | 拒绝保存 | ✅ |
| 组合数变少（改动后被排除规则过滤） | blocked | 拒绝保存 | — |
| 多记录批量写入 | 视情况 | 会动到变体 → 拒绝（表达不了逐条归属）；不动到变体 → 放行 | — |
| 按需生成变体（dynamic）的属性（**改属性**） | required | **支持**（`T-039`）：只展开「立即」轴，按需轴按既有变体现带取值钉住，缺失组合自己建 | ✅ |
| **建产品时**带按需生成变体（dynamic）的属性 | blocked | 拒绝（原生会建出 0 变体），提示先建产品、保存再加属性 | ✅ |
| 带归档变体的产品 | blocked | 拒绝，要求先恢复 / 删除 | — |
| combo 产品 | blocked | 拒绝 | — |

**判据只有一条**：组合数 > 既有变体数 ⇒ 一定出现新记录 ⇒ 才需要归属确认。组合数不变（单取值属性、no_variant 属性、重提同配置）就没有可确认的东西。

**同步规则（写文档 / 排障时别搞错）**

- 库存：**完全不动**（`stock.quant` / `move.line` / `move` / `lot` / `orderpoint` 都留在各自那条原记录上）。
- **原产品资料不需要「转移」**：映射表里被指定承载某个组合的那条变体，**就是原 `product.product` 记录本身**（id 不变），
  所以参考号 / 条码 / 按变体的供应商价格（`supplierinfo.product_id`）/ 按变体的价格表规则
  （`pricelist.item.applied_on = 0_product_variant`）/ 补货规则（`orderpoint.product_id`）本来就在它身上，
  一个字段都不搬；已指向该变体的记录不动，模板级的记录保持模板级（对所有变体生效）。
  由 `test_product_data_stays_on_the_variant_that_keeps_the_product()` 与
  `test_reordering_rules_stay_on_the_variant_that_keeps_the_product()` 钉住。
- **价格数据默认按变体分离**（系统参数 `separate_variant_prices`，默认开启）：本产品模板级的供应商价格 /
  价格表规则拆成每条变体一份（数值不变）并删除原记录；新变体从谱系来源继承；同一「价格表 + 数量门槛」上
  变体已有规则时不覆盖（避免静默改价）；分离前后由 `_check_variant_price_separation()` 断言兜底。
  映射表勾选框**默认不勾选**，勾上时供应商价格退回模板级共享（`_share_vendor_prices_with_variants()`：
  所有变体取同一批数值；价格表规则仍按变体分离）。
- 模板级字段（`list_price`、`taxes_id`、`uom_id`）天然覆盖全部变体；ptav 级（`price_extra`）随取值走。
- **按需生成产品的「订单期变体」完全在本模块之外**（`19.0.5.3.2` 核实，`T-039` 后依然成立）：配置器 →
  `sale.order.line` → `product.template._create_product_variant()` → `product.product.create()`，
  全程不经过 `product.template.write()`，所以本模块**不拦、也不接管**：不写台账 / 谱系 / 来源字段，
  也不做按谱系继承（继承只发生在 `_apply_variant_data_inheritance()`，即**本模块自己的转换**里）。
  这些变体是「Odoo 的」；**之后**的属性改动会走本模块的转换，届时新增的变体才有来源与继承。
  （`webhook` 式地 hook `product.product.create` 会波及全库所有变体创建，风险远大于收益，**不要**顺手加。）
- **字段归属与「单变体桥接」（T-016 核实结论，完整表见 `README.md` →「属性归属审计」）**：
  - `product.product._inherits = {'product.template': 'product_tmpl_id'}`：模板字段在变体上是**委托**关系；
  - 但 `barcode` / `standard_price` / `volume` / `weight` / `default_code` 是 `product.product` **自己声明的存储字段**，
    在变体上**覆盖**了委托来的模板字段 → 模板侧那几个退化成「单变体桥接」；
  - 桥接规则（`_compute_template_field_from_variant_field()` / `_set_product_variant_field()`）：**单变体**时读 / 写都落到那条变体；
    **多变体**时读出默认值（空 / 0），写入**不落任何变体**。所以「普通产品 → 多变体」后产品表单上的条码 / 成本 / 体积 /
    重量 / 内部参考号显示空 / 0 是**原生语义，不是数据丢失**（真值在承载它的那条变体上）；
  - 因此**变体级字段不需要任何数据迁移**：值本来就在那条唯一的 `product.product` 记录上，而本模块保留该记录。
    由测试 `test_field_storage_layers_match_the_audit()` / `test_variant_level_values_stay_on_the_kept_variant()` 钉住；
  - **变体上的值一律原样保留（`19.0.5.3.0` 起）**：`default_code` / `barcode` / 成本 / 体积 / 重量
    这些字段的真身在变体上，转换只做「按归属复用既有变体」，**不读也不改写**它们；
    产品级编号（`product.template.base_reference` / 模板级 `default_code`）同样不碰 ——
    那是 `product_reference` 自己的两层约定（单变体产品两处同值、多变体产品只写产品级），
    与本模块无关（见该模块 AGENTS.md L1.3）。历史：`19.0.5.1.0`～`19.0.5.2.1` 曾把原变体编号
    「上移」成产品编号并清空变体编号，`19.0.5.3.0` 按「模块间彻底解耦」的要求移除；
  - **新变体的继承策略**（`19.0.3.2.0` 起默认开启，系统参数 `product_variant.inherit_variant_data`）：
    按谱系来源（`variant_origin_id`）复制 `standard_price` / `volume` / `weight`；**`default_code` 与 `barcode` 刻意不复制**
    （参考号受 `product_reference` 的 L1 约束「多变体不共用」约束、条码有 `_check_barcode_uniqueness()` 唯一性约束）；
    `product.pricelist.item` 与 `stock.warehouse.orderpoint` 也不继承（规则各自带适用条件，盲目复制会产生重复规则）；
    `supplierinfo` → 仍由映射表勾选框决定（一刀切共享，见下方 ⚠）。
    来源为空时跳过、保持空值，不猜测。
  - **来源怎么定**（`19.0.5.0.0` 起）：`_find_variant_conversion_origin()` 只拿**转换前就存在的取值**
    （`_get_variant_conversion_origin_key()`，按各变体转换前的组合拍快照）去比 —— 新变体在老属性轴上保留的取值
    与哪条原变体一致就跟哪条，多个候选取「最具体」的，仍并列才判为不唯一。**关键点**：本次新加的取值不参与比对，
    否则「给已有属性加取值」时新变体永远匹配不上任何原变体（旧算法即如此，多条原变体时新变体一律无来源，
    尺寸 / 体积 / 成本随之丢失）；因此也不再需要「改动前的属性行快照」这个参数。
  - **禁止与 `product_reference` 耦合**（`19.0.5.3.0` 起）：本模块**不读不写**该模块的任何字段
    （`base_reference` / `reference_code_line_ids` / `variant_reference_code_line_ids`）、也不调用它的
    方法 —— 转换只做「按归属复用既有变体」，参考号与原变体编号原样留在原主人身上
    （产品级留产品、变体级留变体，两层在各自表单上都可见）。新增功能时若发现「需要对方的字段」，
    先问「这件事是否属于对方」：属于对方就由对方做（例如产品级编号的 compute 由它叠加进
    `default_code`），本模块只读归属即可。
  - **可选模块不得让主流程崩**（适用于 `product_dimension` / `stock` / `sale` 等）：读字段前判
    `_fields`、取模型用 `env.get()`（未注册返回 `None`）、调对方方法用 `getattr` 探测，
    任何模块组合下转换都必须成功。历史教训：早期版本在未装 `product_reference` 时于跳过分支里
    `env["product.reference.code"]` → `KeyError` → 每次转换都失败（HEAD 上 33/43 条用例 error）。
  - ⚠ **本模块会拦截改属性的 `write()`**（功能本身）：其它模块的代码 / 测试若需要程序化产生多变体产品，
    请把属性行放进 `create()`（`create` 只拦「按需生成属性」，见 L1 约束 18）—— `product_reference` /
    `product_card_view` 的测试就是这么写的，别改回「先建单变体、再 `write` 属性行」。
- **跨模块协同：产品尺寸（`product_dimension`）**（`19.0.4.1.0` 起）：该模块把尺寸放在**变体**上
  （`dimension_*`），模板侧只是单变体桥接，所以「尺寸 + 各自的 Volume」天然逐变体独立；
  本模块的按谱系继承清单会在这些字段存在时带上它们（`_get_variant_conversion_inherited_fields()`），
  新变体因此继承来源变体的尺寸与体积。只在**来源尺寸齐全**（长宽高都 > 0）时才复制尺寸 ——
  否则会触发该模块「尺寸不齐 → Volume 归 0」的规则，把继承来的体积冲掉
  （由 `test_new_variants_inherit_variant_dimensions_when_installed()` 钉住）。
  `T-021`（原 `product_packing` 的尺寸同步在多变体下失效）已由该模块的 `19.0.2.0.0` 重写解决。
- **与 `product_reference` 的关系：零耦合**（`19.0.5.3.0` 起）：历史上曾做过两件事 —— 把产品级共享
  参考号「交接」给被保留的变体（`19.0.4.1.1`）、把原变体编号「上移」成产品编号（`19.0.5.1.0`）——
  两者都要求本模块知道对方的字段与归属规则，且各自都能被对方的模块内改动打断。
  `19.0.5.3.0` 全部移除：对方已把产品级那一层改成**永远可见**（两层各自独立），
  产品级编号也改由**对方叠加进原生 `default_code` 的 compute**，因此本模块只需要
  「保留既有变体记录」这一件事，其余一概不碰。测试 `test_references_are_left_untouched_by_the_conversion()`
  钉住「转换一行参考号都不搬」（未装对方模块时自动跳过）。
- ⚠ **共享供应商价格会抹平变体级价差**：同一供应商对不同变体给不同价时，共享后全是模板级同级记录，
  采购取价按 `price_discounted → sequence → id`（`product.product._select_seller`）只取一条，另一条静默失效。

**已识别的缺口**（明确记录在案的边界，不是「未知 bug」；对应需求见仓库 `TODO.md` → 待办池 T-017 ~ T-021）

1. **绕过路径（最重要）**：归属确认挂在 `product.template.write()` 上，但
   `product.template.attribute.value.unlink()` 会 `self.ptav_product_variant_ids._unlink_or_archive()` —— **直接删 / 归档变体**；
   `product.template.attribute.line.write()` 又会自己调 `product_tmpl_id._create_variant_ids()`。
   于是「在属性主数据里删取值」「直接写属性行」这两条路**不经过本模块**，照样丢变体。
   **`19.0.5.3.2` 实测补充**：`product.template.attribute.line.create()`（新增一行，非沙盒上下文）同样会调
   `_create_variant_ids()` —— 对**按需生成**的产品，新加一行让既有变体的组合变得「不完整」，
   原生会把它们**直接删掉**（实测 2 条在用变体消失）。属性行守卫目前只覆盖「`write()` 移走取值」与
   `unlink()`，**没覆盖 `create()`**；要补的话就在 `line.create()` 里做同一套判定（沙盒 `create_product_product=False` 必须放行，
   否则导入会被拦）。
2. ~~成本价不继承~~ **已解决**（`19.0.3.2.0`）：新变体按谱系继承来源的成本 / 体积 / 重量，可关。
3. ~~供应商价格共享抹平价差~~ **已解决**（`19.0.3.4.0`）：价格数据默认按变体分离并随谱系继承，共享改为需要主动勾选。
4. **谱系行随变体级联删除**：`product.variant.lineage` 的两个变体字段都是 `ondelete='cascade'`，删变体即丢审计行（台账本身不受影响）。
5. **组合枚举无前置上限**：`_get_variant_conversion_combinations()` 在 `product.dynamic_variant_limit` 检查之前就枚举全部组合，超大配置会先枚举再拒绝。
6. **试写在加锁之前**：`_analyze_variant_conversion_write()` 不带 `FOR UPDATE`，并发下分析结果可能过期 ——
   由 `_check_variant_conversion_anchors()` 与后置断言兜住（拒绝并整单回滚），不会写坏数据，但报错会指向「组合被排除 / 变体数不符」。
7. ~~展示在手数量~~ **已交付**（`19.0.7.0.0`）：映射表里每条变体后面附「在手 N」（未装 `stock` 时不显示）。
8. **前端无自动化测试**：55 项都是服务端测试，映射表与钩子靠手工验证（见 `README.md` →「验证清单」）。
9. **有代码无测试的服务端分支**（多记录写入、归档变体、dynamic 属性已于 `19.0.4.0.0` 补测）：combo 产品（构造合法组合产品需要先配 combo choice）、组合被排除规则过滤（排除规则本身会先让原生收编变体，难以构造）、无 `stock` / 无读权限时的降级。
10. ~~「按需生成」属性只做到「拦住 + 讲清楚」，没做到「支持」~~ **已解决**（`T-039`，`19.0.6.0.0`）：
    只展开 `always` 的属性轴、按需轴按既有变体现带取值钉住（`_split_variant_conversion_lines()` /
    `_get_variant_conversion_fixed_values()`），缺失组合自己调 `_create_product_variant()` 补；
    带按需属性的产品不做价格分离。**残留边界**：① 建产品时带按需属性仍然拒绝（原生会建出 0 变体，
    见 L1 约束 18）；② 纯按需且 0 变体的产品本模块不介入（没有既有变体可保，属性改动原样交给原生 ——
    这类产品的变体由订单创建，`_get_variant_conversion_combinations()` 在没有既有变体时返回空集）。

**扩展点**

| 想扩展什么 | 在哪扩 |
|-----------|--------|
| 默认归属规则 | override `_get_variant_conversion_default_mapping()` |
| 映射表里的新选项 | `variant_mapping_panel.js` 加选项 → 进 `buildMappingPayload()` → `_parse_variant_conversion_mapping()` 解析 → `write()` 落地（现有 `share_vendor_prices` 就是范例） |
| 转换后的数据补全（成本 / 参考号 / 图片 / 价格表规则） | 目前**没有正式钩子**，只能插在 `_create_variant_conversion_lineage()` 之后；`T-020` 要补 |
| 批量转换 | 新增独立入口（列表按钮 / 服务器动作），逐产品调用 `_convert_to_multi_variant()`，**各自包一个保存点** |
| 拦截「属性主数据」路径 | 在 `product.template.attribute.value` 上加同样的判定（`T-017`） |

**维护提醒**

- **任何新增的「改属性」入口都必须经过 `product.template.write()`**，否则等于绕过 L1 约束 1。
  建产品那条路另算：`create()` 只拦「按需生成属性」（见 L1 约束 18），其它情况不拦，
  所以其它模块要用 `create` 带属性行程序化产生多变体产品仍然可行。
- 升级 Odoo 必须回归的内部 API：`_filter_combinations_impossible_by_config()`、`_without_no_variant_attributes()`、
  `_create_variant_ids()`、`FormController.onWillSaveRecord`、`Record._getChanges()` 的 `forceSave` 语义、
  `product.template.attribute.value.unlink()` 里的 `_unlink_or_archive()` 行为。

---

## 常见扩展场景

### 想支持「给产品删属性 / 删取值」

不要在现有流程上开口子（会破坏 L1 约束 8 的推理链）。删取值会让 Odoo 归档 / 删除 ptav 并牵动变体，
属于另一个风险等级的功能，要做就得先回答：被删取值的库存与单据往哪条变体上挪？想不清楚就不要做。
当前设计给用户的路是「先归档 / 删除不想要的变体，再改属性配置」。

### 想在映射表里加选项（例如同时调整价格表规则）

- 前端：在 `variant_conversion_dialog.js` 加字段 + 在载荷里带出去（参考 `share_vendor_prices`）；
- 服务端：在 `_parse_variant_conversion_mapping()` 里解析并返回，`write()` 负责落地。
- 注意载荷格式变化后要同步改 `_parse_variant_conversion_mapping()` 的校验分支。

### 想批量转换多个产品（列表 / 服务器动作）

当前 `write()` 对多记录写入仅做安全判定（会动到变体就拒绝）。要支持批量，应新增一个独立入口
（服务器动作 / 列表按钮），逐条产品调用 `_convert_to_multi_variant()` 并各自包一个保存点：
不要在一个保存点里转换多个产品（一个失败会连累全部，且报错无法定位到具体产品）。

---

## 调试建议

- **点保存没映射表、只报错**：前端资源没生效（没 `-u` 或没强刷浏览器），按报错提示强刷一次；报错文案就是这条线索。
- **弹出了归属框但默认归属很奇怪**：默认归属来自 `_get_variant_conversion_default_mapping()`（已有属性保持原取值、新加属性取第一个取值）；确认预览里的 `combinations` 是否与 `_get_variant_conversion_combinations()` 的输出一致。
- **报「属性重复 / 取值不能删除 / 会删变体」**：都是 `write()` 的前置校验，报错不改库；按提示先处理变体再改属性。
- **报「变体数不符 / 原变体不见了 / 没带上该组合」**：后置断言触发，整单已回滚。重点看产品的属性排除配置
  （产品表单属性行的「Configure」弹窗里可以配置取值互斥）与归属表是否有重复。
- **`RecursionError`**：`write()` 的第一道判断丢了 `create_product_product` 放行分支，见 P4 陷阱 1。
- **谱系里 `variant_origin_id` 全是空**：`_convert_to_multi_variant()` 没拿到 `previous_attribute_lines`
  （改动前快照），来源判定用了改动后的属性轴，见 P1「维护提醒」。
- **中文界面还是英文**：先 `task i18n -- zh_CN product_variant` 强制刷新译文（元数据条目 `noupdate=True`），
  再强刷浏览器；后端字段标签刷新页面即可。
- **预览里的在手数量是 0**：没装 `stock`，或当前用户没有 `stock.quant` 的读权限（设计如此）。

---

## 变更记录规范

每次功能修改后必须更新：
- `__manifest__.py` 的 `version`（遵循 `19.0.x.y.z`）
- `CHANGELOG.md` 的版本说明（变更 / 影响 / 文档）
- 本 `AGENTS.md` 的相关约束（若涉及行为变更）
- `README.md` 的功能说明（若涉及用户可见功能）

版本号建议：
- 破坏性变更或架构调整：升第二位，如 `19.0.3.0.0`
- 功能新增：升第三位，如 `19.0.1.1.0`
- 修复或文档：升第四位，如 `19.0.1.0.1`
