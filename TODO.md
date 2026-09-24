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


- [ ] T-026 ｜ `product_reference` + `sale_product_hover` + `product_image` + `product_variant_conversion` + `sale_order_no` ｜ P2 ｜ 补齐 po 里 `code:` 条目缺失的运行期注释标记（这些前端 / Python 文案一直没翻译）
  - 背景：前端译文由 `web/controllers/utils.py::_local_web_translations()` 读 po 时按 `#. odoo-javascript` 过滤，Python `_()` 由 `CodeTranslations._load_python_translations()` 按 `#. odoo-python` 过滤 —— 缺标记的条目**永远不下发且不报错**（界面一直英文）。`task check` 现在会给警告（`--strict` 算失败），实测受影响条目（`task check` 口径，共 25 条）：`product_reference` 20 条、`sale_product_hover` 2 条、`product_image` 1 条（JS）、`sale_order_no` 1 条（Python）；`product_card_view` 的 5 条已随 T-025 修掉、`product_variant_conversion` 的 1 条已随 `T-039`（`19.0.6.0.0`）修掉
  - 建议：给这些模块的 `code:` 条目补上对应注释（按引用文件后缀区分 `.py` → `odoo-python`，`.js` / `.xml` → `odoo-javascript`），逐模块升 `+z` 版本并记 CHANGELOG；补完把 `check_repo.py` 里这两条从 `report.warn` 改回 `report.fail`
  - 验收方式：`task check -- --strict` 不再报这两类警告（`检测：` 条件只能做单条文本匹配，覆盖不了「所有 `code:` 条目都带上标记」，故本条目不写检测行）
  - 关联：`product_card_view/AGENTS.md` → L2 P5；根 `AGENTS.md` 4.3「`code:` 译文在运行时按注释标记放行」

- [ ] T-028 ｜ `product_image` + `product_reference` + `product_variant_conversion` + `sale_order_no` + `sale_product_hover` + `web_image_paste` + `web_multi_tabs` ｜ P2 ｜ manifest description 用悬挂缩进，触发 docutils RST 告警（每次安装都打日志）
  - 背景：安装时日志出现 `<string>:9: (ERROR/3) Unexpected indentation.` 与 `<string>:11: (WARNING/2) Block quote ends without a blank line; unexpected unindent.`。原因是 description 的列表项用了**悬挂缩进**（bullet 与续行分行），Odoo 渲染 Apps 描述时用 docutils 报警告。已装库实测确认会打告警的是 `product_image` 与 `product_reference`；另有 5 个模块（`product_variant_conversion` / `sale_order_no` / `sale_product_hover` / `web_image_paste` / `web_multi_tabs`）扫出同样写法、尚未逐个装库验证 —— **共 7 个模块**。`product_dimension` 重写时已修过同一问题，可参照它的写法
  - 建议：逐模块把列表项改成「一条一行」（不换行）；改完必须同步该模块 `i18n/zh_CN.po` 里 `model:ir.module.module,description:base.module_<模块>` 的 `msgid`（必须与 `textwrap.dedent(manifest["description"])` 逐字符一致，`task check` 会卡住）；每模块升 `+z` 版本并记 CHANGELOG
  - 验收方式：安装该模块时日志不再出现上述 docutils 告警（暂无自动检测条件：`检测：` 语法只支持单条文本 / 正则匹配，覆盖不了「描述整体 RST 合法」；试过用 docutils 复现该告警未成功，装库看日志最可靠）
  - 关联：`product_dimension/__manifest__.py` 的描述写法；根 `AGENTS.md` → i18n 约束

## 搁置 / 放弃

（空）

---

## 已归档

> 已完成需求不在「待办池 / 进行中」留存，仅在此留一行摘要以便追溯；
> 完整验收记录见各模块 `CHANGELOG.md` →「验收记录（T-0xx）」与根 [`README.md`](README.md) 模块一览表。

- **T-040 归属弹窗交互优化：所有选项可选，重复选择自动互换** ｜ `product_variant_conversion` ｜ P2
  - 完成日期：2026-09-24 ｜ 状态：**已交付，待目标环境复验（前端改动需 `-u` + 强刷）**
  - 落地版本：`product_variant_conversion` `19.0.6.1.0`
  - 做法：去掉 `t-att-disabled`（不再把「已被别的组合占用」的既有变体置灰）；新增纯函数 `applyOwnershipSelection(selection, index, variantId)` —— 选中的既有变体若已被另一行占用，就把占用行改成本行原先的选项，再给本行赋新值，于是任意时刻「每条既有变体只被一行占用」；`onSelect()` 生成新 selection 赋回 `state.selection`（OWL 响应式，两行显示同步刷新）；弹窗顶部与中文译文同步补一句说明
  - 验收记录：模块 [`CHANGELOG.md`](product_variant_conversion/CHANGELOG.md) → `[19.0.6.1.0]`；`node` 一次性验证纯函数 6 组用例（含用户给的 Black/White 互换示例）与「无重复占用」不变量全部通过；四组配置 47 项服务端测试 0 failed（回归）
  - 遗留：目标环境手工复验「所有选项可选 / 互换后两行显示同步 / `Confirm` 状态随互换变化 / 中英文提示」；前端逻辑仍无自动化测试（待前端纯函数上 Hoot 单测时一并补）

- **T-039 支持「按需生成变体」（`create_variant == 'dynamic'`）的属性：改属性只展开「立即」轴** ｜ `product_variant_conversion` ｜ P1
  - 完成日期：2026-09-24 ｜ 状态：**已交付，待目标环境验证**
  - 落地版本：`product_variant_conversion` `19.0.6.0.0`
  - 做法：属性行按 `_split_variant_conversion_lines()` 分成「展开的（`always`）」与「固定取值的（`dynamic`）」；组合枚举 = **每条既有变体 × 各「立即」属性的取值组合**（按需轴取该变体现带的取值，没有则第一个取值），按需轴的其它取值**不预建变体**；缺失组合自己调 `_create_product_variant()` 补（`_create_variant_ids()` 对按需属性整段跳过）；新增 `needs_anchoring` 判定，拦住「原生把缺取值的既有变体当组合不完整删掉」那条路；带按需属性的产品**不做价格分离**（否则以后订单期新建的变体取不到价）；**建产品**时带按需属性仍然拦住（原生会建出「有属性、没变体」的产品），文案给出「先建产品、保存，再加属性」的出路
  - 验收记录：模块 [`CHANGELOG.md`](product_variant_conversion/CHANGELOG.md) → `[19.0.6.0.0]`；47 项测试 0 failed / 0 error（`product` 单装、`+stock,sale_management`、`+product_dimension`、`+product_reference,product_card_view,sale_management` 四组）；shell 实测「只展开『立即』轴、未被使用的按需取值不建变体」「加多取值按需属性时既有变体存活并锚定到第一个取值」
  - 遗留：目标环境验证「导入来的按需产品加属性」「弹窗按需提示与中文文案」；`19.0.5.3.2` 实测的两条边界仍未闭环 —— ① 订单期由 Odoo 自建的变体不带来源 / 继承（本模块当时不接管，**之后**的属性改动才会走转换）；② 非沙盒的 `product.template.attribute.line.create()`（其它模块 / 脚本）会把按需产品的既有变体**直接删掉**，属性行守卫目前未覆盖 `create()`

- **T-038 修复产品列表「Images」列看不到图片（列绑的是图库计数，应显示产品主图）** ｜ `product_image` ｜ P1
  - 完成日期：2026-09-23 ｜ 状态：**已交付，待目标环境界面复验**
  - 落地版本：`product_image` `19.0.2.6.5`
  - 现象：库存 / 销售 / 采购三处「产品」列表勾选「Images」列后**看不到任何图片**——该列绑的是 `image_gallery_count`（`Integer` 计算字段，只统计图库补充图数量），由默认整数控件渲染，因此只显示数字（没有补充图的产品恒为 `0`）；且该计数**不含主图**，语义与列名不符
  - 做法：列改绑原生 `image_128`（`image.mixin`，`related="image_1920"` + `store=True`，即**产品主图**缩略）+ `widget="image"`；仍为可选列（`optional="hide"`，默认隐藏、可由列表右上角「可选列」勾选）与只读，列高 48px 保持行紧凑。**只显示主图**：只有补充图、没有主图的产品该列为空（占位图）。继续继承基础列表视图 `product.product_template_tree_view`，故库存（默认列表视图）、销售（`account.product_template_list_view_sellable_inherit`）、采购（`account.product_template_list_view_purchasable_inherit`）三处一并生效；`i18n/zh_CN.po` 列标题译文「图片数」→「图片」，并加 `migrations/19.0.2.6.5/post-migration.py` 定向刷新该视图 `arch_db` 的 zh_CN 术语（**po 不覆盖已有译文，只跑 `-u` 旧标题会留着**；等价手工方式是 `task i18n -- zh_CN product_image`）；`image_gallery_count` 字段保留（仅供导出 / 分组 / 自建视图，不再作为列表列）
  - 验收记录：模块 [`product_image/CHANGELOG.md`](product_image/CHANGELOG.md) → `[19.0.2.6.5]`；新增 `product_image/tests/test_product_list_image_column.py`（7 项：列定义 / 只读可选 / 仅主图数据绑定 + 三个动作实际使用的列表视图）；`task test -- product_image` 7 项（3 项页面用例按配置 skip）0 failed / 0 error；`task test -- product_image,stock,sale_management,purchase --test-tags=/product_image` **7 项全部执行（无 skip）** 0 failed / 0 error；dev 库 `task update -- product_image` 升级无报错；dev 库实测三个动作实际使用的列表视图 arch 均为 `('Images', 'image', 'hide', '1')`；dev 库把已装版本退回 `19.0.2.6.4` 真跑一次升级：迁移 `[19.0.2.6.5>] post-migration` 执行、zh_CN 列标题由「图片数」→「图片」（en_US 仍为 `Images`）；`task check` 通过
  - 遗留：目标环境界面复验——三处列表勾选 / 取消勾选「Images」列（显示、隐藏与数据绑定），有主图 / 无主图 / 仅有补充图三种产品各看一遍，中英界面各一遍 + 强刷浏览器

- **T-037 产品编号承载方式定稿 + 卡片编号口径（含两次回退的评估记录）** ｜ `product_reference` + `product_card_view` ｜ P1
  - 完成日期：2026-09-23 ｜ 状态：**已交付，待目标环境验证**
  - 落地版本：`product_card_view` `19.0.2.1.4`；`product_reference` `19.0.3.0.0` 与 `product_variant_conversion` `19.0.5.3.0` **不变**（产品编号仍存自有字段 `base_reference`，未改用原生列）
  - 起因（三条要求，逐条有结论）：
    1. 「不再单独存储 —— 产品编号直接用 `product.template.default_code`，并把该字段由计算字段改成实际存储字段（stored field），卸载后不遗留任何数据或行为变更」→ **实现后按要求回退**；
    2. 「卡片上产品编号紧跟产品名」→ 实现后**使用方手改回退**（版式维持原样）；
    3. 「卡片选中变体时编号显示该变体编号，已选组合行移除变体编号」→ **已定稿落地**（`19.0.2.1.4`）。
  - 结论与依据：
    - ① **不做**。字段继承是「参数合并」（`Field._get_attrs()`：先并基础定义、再并本模块定义，显式 `compute=None` 能摘掉 compute），但摘掉即拆毁原生单变体桥接 —— `display_name` 的 `[编号] 名称`、`create()` 的 related 传播、单据 / 报表口径全变；且写进那一列的值卸载后会残留（原生多变体产品该列应为空），必须再加 `uninstall_hook` 清值。若「直接存原生列」还要在 compute 里「先 `flush_all()` 再从库读回」才不被赋空 —— 脆弱、属非文档化扩展面。故**保留 `base_reference` + compute 叠加**。源码与实测证据见 `product_reference/AGENTS.md` → L2 P1 / P2 / P3 / P5，评估记录见其 `CHANGELOG.md` → `[19.0.4.0.0]`（标注未发布 / 已回退）
    - ② **不做**。flex 子项默认 `min-width: auto`：长产品名会撑破卡片、`text-truncate` 失效；要让编号不被长名字挤掉得 `flex: 0 0 auto` + `max-width: 45%`。陷阱已归档到 `product_card_view/AGENTS.md` → P8（含回退经过）
    - ③ **定稿**：`referenceText = (variant && variant.reference) || data.reference || "—"`（未选=产品编号；选中=该变体编号，变体无编号回退产品编号；都空显示 `—`）；`selectionText` 只拼属性组合（`Blue / Large`），同一编号只出现一次。判据是「卡片默认代表产品、点选后代表该变体」，与图片 / 在手数量的切换口径一致 —— 见 `product_card_view/AGENTS.md` → P7
  - 验收记录：模块 [`product_card_view/CHANGELOG.md`](product_card_view/CHANGELOG.md) → `[19.0.2.1.4]`、[`product_reference/CHANGELOG.md`](product_reference/CHANGELOG.md) → `[19.0.4.0.0]`（评估记录）；`task test -- product_card_view` 6 项 0 failed / 0 error（2 项按配置 skip）；`task test -- product_reference,product_card_view,product_variant_conversion --test-tags=/product_reference` 8 项 0 failed / 0 error；`task check` 通过；开发库实测：多变体产品写模板级 `default_code` 确实落库、增删变体与 `add_to_compute` 均未清空（**观察到的行为，非契约** —— 正因如此没采用该路径）
  - 遗留：① **卡片编号与已选组合行没有自动化用例**（无头环境断言不了渲染）→ 目标环境人工验证四态（未选 / 选中且变体有编号 / 选中且变体无编号 / 两层都空）+ 强刷浏览器 + 中英各一遍；② `product_reference` **卸载即丢产品编号**（自有字段随模块消失）→ 卸载前先导出；③ 存量**多变体**产品的产品编号需人工补录一次；④ 本地工作树残留空目录 `product_reference/migrations/19.0.4.0.0/`（评估版迁移文件已删除，目录待手工删）

- **T-036 修「新建产品时产品表单的 Dimension Unit 是空的」** ｜ `product_dimension` ｜ P1
  - 完成日期：2026-09-23 ｜ 状态：**已交付，待目标环境界面复验**
  - 落地版本：`product_dimension` `19.0.4.1.1`
  - 现象：产品表单点「新建」，`Dimension Unit` 下拉框默认是空的（该字段还是必填，不选存不了）；但变体快速编辑表单里默认就是厘米，同一个字段名两边行为不一致
  - 根因（实测复现）：模板侧那个字段是「单变体桥接」的 compute（依赖 `product_variant_ids.dimension_unit`），而 **`default_get()` 只认 context / `ir.default` / `field.default`、不触发任何 compute**（`odoo/orm/models.py::default_get`）；全新产品的表单是「先有表单、后有变体」，compute 那一刻没有变体可镜像 → 读出空值。变体侧不空是因为它自己带了 `default="cm"`。实测 `product.template.default_get(['dimension_unit'])` → `{}`、`Form(product.template).dimension_unit` → `False`
  - 做法：真身文件新增常量 `DEFAULT_DIMENSION_UNIT = "cm"`，变体侧与模板侧两个字段共用它；镜像字段仍保持 `compute + inverse + store`（不违反「真身在变体」的归属约束），只是新建表单的默认值不再依赖 compute
  - 验收记录：模块 [`product_dimension/CHANGELOG.md`](product_dimension/CHANGELOG.md) → `[19.0.4.1.1]`；dev 库实测 `default_get` / `Form` 均得 `cm`、多变体模板仍为 `False`、升级日志无 `Redundant default on ...` 告警；`task test -- product_dimension` 17 项 0 failed；`task check` 通过
  - 遗留：目标环境界面复验（新建产品打开表单看 `Dimension Unit` 是否为 `Centimeters`）

- **T-034 三个关联模块的解耦审计与接口边界固化** ｜ `product_reference` + `product_variant_conversion` + `product_card_view` ｜ P1
  - 完成日期：2026-09-22 ｜ 状态：**已交付，待目标环境验证**
  - 落地版本：`product_reference` `19.0.2.7.1`、`product_variant_conversion` `19.0.5.2.1`、`product_card_view` `19.0.2.1.2`
  - 起因：三个模块在业务上相互关联（母型号 / 转换 / 卡片），需要确保**任意一个未安装时其余仍能独立正常运行**，并把依赖关系与接口边界写死
  - 审计结论（只读盘点，逐行核对）：三者**互相没有任何 `depends`**，`data` / `assets` / XML `inherit_id` / `env.ref` 也没有任何跨模块引用；交叉点全部是运行期软探测（`_fields` / `env.get` / `in env`）。发现两处「间接假设」隐患：① `_transfer_shared_references_to_original()` 里 `env["product.reference.code"]`（模型缺失即 `KeyError`）只靠上一行的字段判断间接保证；② 交接后调 `self._sync_reference_index()` 只靠「字段在 ⟺ 方法在」的隐含前提
  - 做法：① `product_variant_conversion` 新增「可选集成适配层」（`_has_base_reference_field()` / `_has_shared_reference_lines()` / `_get_reference_code_model()`），字段名与模型名只出现在那里；取模型改 `env.get()`、调对方方法改 `getattr` 探测；② `product_card_view` 把可选依赖探测收敛进 `_get_optional_base_reference()`（未装 / 单变体两种情形合并为一个降级判断）；③ `product_reference` 明确「只做提供方、不感知消费方」，补字段契约测试；④ 三模块 README 各加「可选集成与解耦边界」表，根 `README.md` 新增「扩展解耦矩阵」（含四种安装组合下的行为）、根 `AGENTS.md` 第 3 节新增「模块间可选集成必须解耦」约定
  - 验收记录：模块 [`product_reference/CHANGELOG.md`](product_reference/CHANGELOG.md) → `[19.0.2.7.1]`、[`product_variant_conversion/CHANGELOG.md`](product_variant_conversion/CHANGELOG.md) → `[19.0.5.2.1]`、[`product_card_view/CHANGELOG.md`](product_card_view/CHANGELOG.md) → `[19.0.2.1.2]`；**四组环境实测**：`product_reference` 单装 4 项、`product_card_view`（+`stock`）单装 4 项（2 项按预期 skip）、`product_variant_conversion` 单装 46 项、三者同装 54 项，全部 **0 failed / 0 error**；新用例：`tests/test_base_reference.py`（4 项）、`tests/test_product_card_payload.py`（4 项）、`test_reference_handling_degrades_gracefully_without_product_reference()`（两种配置分别断言）；`task check` 通过
> ⚠ 本条的「适配层 + 软探测」方案已被 **`T-035`**（`product_reference 19.0.3.0.0` / `product_card_view 19.0.2.1.3` / `product_variant_conversion 19.0.5.3.0`）取代：产品编号改由原生字段承载，两个消费方不再需要探测任何自研字段。

  - 遗留：目标环境验证界面（卡片编号显示、加属性弹窗、中英双语各一遍、强刷浏览器）；`product_card_view` 卡片其余项本就待复验（见 `T-012` 相关记录）

- **T-035 产品级编号叠加进原生 default_code + 三个模块彻底解耦** ｜ `product_reference` + `product_variant_conversion` + `product_card_view` ｜ P1
  - 完成日期：2026-09-23 ｜ 状态：**已交付，待目标环境验证**
  - 落地版本：`product_reference` `19.0.3.0.0`、`product_variant_conversion` `19.0.5.3.0`、`product_card_view` `19.0.2.1.3`
  - 起因：多变体产品的产品编号此前只存在本模块自己的 `base_reference` 字段里 —— 产品列表、`[编号] 名称`、Many2one、列表搜索都看不到它；而 `product_card_view` 为了显示它被迫运行期探测该字段（跨模块耦合），`product_variant_conversion` 也为它做了「编号上移」与「参考号交接」（同样耦合）。按要求改为：**让原生字段承载产品编号**，另两个模块回到只读原生字段
  - 做法：① `product_reference` 把 `base_reference` **叠加进模板级 `default_code` 的 compute**（`base_reference` 优先，`super()` 保底单变体桥接）—— 产品编号从此在所有原生口径可见，消费方零耦合；② inverse 按变体数分流（单变体两处同值 / 多变体只写 `base_reference`），并从变体侧改编号时反向同步（仅单变体）—— 写入路径全部收口，实现时踩到「inverse 里再写 `default_code` → `RecursionError`」并修掉；③ 产品级参考号层**不再按变体数隐藏**（两层各自独立、都可见）；④ `migrations/19.0.3.0.0/` 回填单变体产品并按需对齐存储列 `default_code`，删除相反的 `19.0.2.7.0` 清理迁移；⑤ `product_variant_conversion` 删除编号上移与参考号交接两步（含 `19.0.5.2.1` 的适配层）—— 转换只做「按归属复用既有变体」，`product.product` 的值（含 `default_code`）原样保留；⑥ `product_card_view` 删除 `_get_optional_base_reference()`，编号只读原生 `default_code`，并修复「编号栏被选中的变体编号顶替」（编号栏固定为产品编号，变体编号移到已选组合行）
  - 验收记录：三模块 `CHANGELOG.md` → `[19.0.3.0.0]` / `[19.0.5.3.0]` / `[19.0.2.1.3]`；测试：`product_reference,product_variant_conversion,product_card_view` **52 项 0 failed / 0 error**，单模块三组（`product_reference` 6 项、`product_card_view` 4 项含 2 项 skip、`product_variant_conversion` 42 项）同样 0 failed；开发库升级实测：回填 23 条单变体产品、对齐存储列 1 条，多变体产品 `AM-235` 的 `default_code` 与卡片编号均为 `AM-235`、原生搜索可命中，单变体产品 `base_reference` / `default_code` / 变体编号三者同值；`task check` 通过
  - 遗留：目标环境验证界面（产品表单 `Ref.`、列表 `Reference` 列、搜索、卡片两态、中英双语 + 强刷）；**存量多变体产品的产品编号需人工补录**（无可自动推断的来源，缺它只影响编号那一栏）；编号口径的最终定稿见 **`T-037`**（`product_card_view 19.0.2.1.4` 起改为「随选择切换 + 组合行只显示属性」）
  - ⚠ 本条第 ⑥ 项的原口径（「编号栏固定为产品编号、变体编号移到已选组合行」）已被 **`T-037`** 推翻：卡片代表产品、点选变体后代表该变体 —— 编号随选择切换、组合行只显示属性组合。判据与四态验证清单见 `product_card_view/AGENTS.md` → L2 P7

- **T-033 产品母型号 base_reference（多变体产品的产品型号无处可存）** ｜ `product_reference` + `product_variant_conversion` + `product_card_view` ｜ P1
  - 完成日期：2026-09-22 ｜ 状态：**已交付，待目标环境验证**
  - 落地版本：`product_reference` `19.0.2.7.0`（母型号字段 `19.0.2.6.0` 引入、写入策略 `19.0.2.7.0` 定稿）、`product_variant_conversion` `19.0.5.2.0`、`product_card_view` `19.0.2.1.1`
  - 起因：多变体产品（`G001-WT` / `G001-BK`）的母型号 `G001` **无处可存** —— 原生 `default_code` 是 `product.product` 的自有字段，模板侧在多变体时只是「读出空、写入不落任何变体」的桥接；产品表单的 Ref. 区又整块隐藏，于是多变体产品在产品层没有任何型号字段，卡片视图也显示不出编号
  - 选型：**新增模板级 `base_reference`**，不改写原生 `default_code` 的桥接语义。曾评估「把模板级 `default_code` 改成可写、多变体时保留」，会破坏 `product_variant_conversion` 用测试钉住的桥接契约（`test_variant_level_values_stay_on_the_kept_variant`）、且订单行 Many2one 仍搜不到母型号，故放弃；理由与反面方案对比见 `product_reference/AGENTS.md` → L1.3 与本条
  - 做法：① `product_reference` 新增 `product.template.base_reference`（存储 + trigram 索引 + `copy=True`）；**写入策略取「单一真值、不做镜像」**（`19.0.2.7.0` 定稿）：单变体产品的编号**只写**变体的 `default_code`，产品侧不写副本 —— 同一份数据写两处，任何一条写入路径（产品表单 / 变体表单 / 导入 / 集成 / SQL）漏掉就会长期不一致，且不会报错；② 母型号只有两个写入时机：多变体产品在产品表单 `Base Ref.` 维护、单变体转多变体时由 `product_variant_conversion` 上移；产品表单按变体数分流显示 `Ref.` / `Base Ref.`（原先「整块隐藏」改为元素级隐藏），模板与变体 `_search_display_name`、搜索视图 `filter_domain`、列表列一并接入；③ 迁移：删除 `19.0.2.6.0` 的回填（不再是期望行为），改由 `migrations/19.0.2.7.0/post-migration.py` 清理旧镜像值（单变体产品上「母型号 = 变体编号」的行置空；多变体产品不动）；④ `product_variant_conversion` 转多变体时把原变体编号**覆盖式上移**成产品母型号并清空变体编号（仅单变体转多变体；变体没有编号时什么都不做，残留母型号保留）；⑤ `product_card_view` 编号取值链改为「变体 `default_code` → 母型号 `base_reference`（**仅多变体产品**）→ 模板 `default_code`」（可选依赖，按字段存在性软适配，前端零改动）
  - 验收记录：模块 [`product_reference/CHANGELOG.md`](product_reference/CHANGELOG.md) → `[19.0.2.6.0]` / `[19.0.2.7.0]`、[`product_variant_conversion/CHANGELOG.md`](product_variant_conversion/CHANGELOG.md) → `[19.0.5.1.0]` / `[19.0.5.2.0]`、[`product_card_view/CHANGELOG.md`](product_card_view/CHANGELOG.md) → `[19.0.2.1.0]` / `[19.0.2.1.1]`；`task test -- product_variant_conversion,product_reference` **45 项 0 failed / 0 error**（含两条母型号用例），`task test -- product_variant_conversion`（未装该模块）同样 0 failed / 0 error、两条用例按预期 skip；开发库升级实测：清理旧镜像值 **22** 条且升级后单变体产品残留 **0** 条、6 条多变体模板的母型号计数不受影响、`ir_model_fields.field_description->>'zh_CN'` = `母型号`（help 已同步）；`task check` 未新增告警，`i18n/zh_CN.po` 应用列表元数据与 manifest 逐字符一致
> ⚠ 本条的字段语义与写入规则已被 **`T-035`**（`19.0.3.0.0`）调整：产品级编号改由**原生 `default_code` 的 compute** 承载、单变体产品两处同值、产品级参考号不再隐藏。

  - 遗留：目标环境验证「单 / 多变体表单可见性、单变体填编号后产品侧确实为空、搜 `G001` 命中产品与订单行、加属性后母型号被上移、卡片显示母型号、中英双语各一遍、强刷浏览器」；存量**多变体**产品的母型号需人工补录一次（无法从变体编号可靠推断）；`product_card_view` 卡片其余项本就待复验（见 `T-012` 相关记录）

- **T-032 修「cm 尺寸的小体积被显示 / 保存成 0」** ｜ `product_dimension` ｜ P1
  - 完成日期：2026-09-22 ｜ 状态：**已交付，待目标环境界面复验**
  - 落地版本：`product_dimension` `19.0.4.1.0`
  - 现象：Dimension Unit = Centimeters 时，体积有小数就显示成 0（如 50×40×30 cm 应为 0.06，界面与库里都是 0）
  - 两个根因（都实测复现）：① 前端把 `roundPrecision()` 的第二参数当小数位数传了 `2`，而它要的是**精度因子**（`0.01`）→ 等于按 2 的整数倍取整，**任何小于 1 的体积都变 0**，再随表单提交把 0 存进库（后端收到 `volume` 就不再兜底）；② 原生「Volume」全局精度出厂 2 位，cm 尺寸下 20³ cm（0.008 m³）也被舍成 0
  - 做法：① 前端纯规则抽到 `static/src/js/dimension_volume_rules.js`（无 Odoo 依赖），自己实现 `roundToDecimals(value, decimals)`，补丁只负责挂钩与写回；② 新增 `hooks.ensure_volume_precision()`，安装（`post_init_hook`）与升级（`migrations/19.0.4.1.0/`）各调一次，把「Volume」精度提到 6 位（只升不降、幂等）
  - 验收记录：模块 `CHANGELOG.md` → `[19.0.4.1.0]`；dev 库迁移日志 `raising the Volume decimal precision from 2 to 6`，实测 10³/20³/50³ cm → 0.001 / 0.008 / 0.125（此前 0 / 0.01 / 0.13）；`product_dimension` 17 项（含 **node 实跑前端规则**的新用例）、`product_variant_conversion,product_dimension` 43 项 0 failed；`task check` 通过
  - 遗留：界面即时显示需目标环境复验；「Volume」精度是全局设置（模块只升不降），其他模块的体积显示会一并变精确

- **T-031 体积计算改由前端负责（后端只兜底、不再返回体积）** ｜ `product_dimension` ｜ P1
  - 完成日期：2026-09-22 ｜ 状态：**已交付，待目标环境界面复验**
  - 落地版本：`product_dimension` `19.0.4.0.0`
  - 目标：界面里改尺寸 / 单位时由前端即时算出 `volume`，不再让后端为界面计算，也不再在 onchange 响应里返回体积
  - 做法：① 新增 `static/src/js/dimension_volume.js`（`Record._update` 补丁：改尺寸 / 单位即算好并写回同一个 `Volume` 字段，按字段 `digits` 取整）；② 删掉两个尺寸 onchange（`product.product` / `product.template`），Odoo 不再为这些字段发 onchange 请求；③ 后端改为 `_should_sync_volume()`：带 `volume` 就不算、不带才兜底补算，`create` / `write` 共用
  - 规则一致性：前端与后端同一套规则（`cm → cm³ / 1 000 000`、`m` 直接相乘、长宽高任一为 0 归 0、按 `digits` 取整），后端唯一出处 `volume_from_dimensions()`，由 `test_frontend_computation_matches_the_backend_rules()` 守住两处不能只改一边
  - 验收记录：模块 `CHANGELOG.md` → `[19.0.4.0.0]`；`ir.asset._get_asset_paths("web.assets_backend", {})` 确认前端文件已进包（2464 条之一）；`product_dimension` 15 项、`product_variant_conversion,product_dimension` 43 项 0 failed；`task check` 通过
  - 遗留：浏览器里的即时显示需目标环境复验（无头环境无法断言前端行为）；`depends` 保持仅 `product`（`web` 是 `auto_install`，缺失时只是少了界面即时计算，落库仍由后端保证正确）

- **T-030 输入尺寸后即时算出 Volume（补齐产品表单预览）** ｜ `product_dimension` ｜ P1
  - 完成日期：2026-09-22 ｜ 状态：**已交付，待目标环境验证**
  - 落地版本：`product_dimension` `19.0.3.1.0`
  - 起因：产品表单上填完长宽高，`Volume` 一直是 0.00、**保存后才出现**（用户会以为模块没生效）。根因是预览 onchange 只挂在 `product.product` 上，而产品表单的模型是 `product.template`；模板侧尺寸要等保存时 inverse 才落到变体，原生 `volume` 又是 `compute + inverse + store`，保存前不会自己算出来
  - 做法：① 新增 `product.template._onchange_dimension_fields()`（单变体时把算好的体积写进模板 `volume`，保存时由原生 `_set_volume` 落到那条变体）；② 换算口径收敛为唯一函数 `product_product.volume_from_dimensions()`，表单预览与写库同步共用，字段名常量统一到真身文件
  - 验收记录：模块 `CHANGELOG.md` → `[19.0.3.1.0]`；`odoo.tests.common.Form` 实测「未保存即 `0.06` / `0.2`」（改造前 `0.0`）；`product_dimension` 13 项 0 failed、`product_variant_conversion,product_dimension` 43 项 0 failed；`task check` 通过
  - 遗留：无（`volume` 仍可手工填，但改动任一尺寸字段后即以尺寸为准，已写进模块 README「操作要点」）

- **T-029 尺寸挂载点补齐 + 转换来源映射可靠性** ｜ `product_dimension` + `product_variant_conversion` ｜ P1
  - 完成日期：2026-09-22 ｜ 状态：**已交付，待目标环境验证**
  - 落地版本：`product_dimension` `19.0.3.0.0`、`product_variant_conversion` `19.0.5.0.0`
  - 起因一（挂载）：多变体产品在界面上没有尺寸入口 —— 产品的「变体」按钮（`product_variant_action`）用的是 `product_variant_easy_edit_view`，它是**独立 primary 视图、不继承模板表单**，原先完全没挂载；完整变体表单则是靠继承模板表单自动获得（`is_product_variant = True` 让门控为假）
  - 起因二（映射）：「给已有属性加取值」时新变体永远匹配不上任何原变体（旧判定把**新加的取值**也算进比对），多条原变体时新变体一律无来源 → 尺寸 / 体积 / 成本丢失
  - 做法：① 补挂变体快速编辑表单；收紧模板表单锚点为 `//group[@name='group_lots_and_weight']/label[@for='volume']`（防字段挂两遍）；用测试钉住「三表单都挂」与「尺寸块与原生 `volume` 同进同退（原生 Logistics 组受 `groups="uom.group_uom"` 门控）」。② 谱系来源改为按**转换前已存在的取值**判定（`_find_variant_conversion_origin()`）：只看新变体保留老取值的属性轴、投影比较、多候选取最具体，仍并列才留空。③ 顺带修掉既有 bug：未装 `product_reference` 时 `_transfer_shared_references_to_original()` 在跳过分支里 `browse` 不存在的模型 → `KeyError` → **每一次转换都失败**（HEAD 上实测 33/43 条用例 error）；以及 `_log_variant_conversion()` 程序化调用拿到 `None` 报错的隐患；移除了不再需要的 `previous_attribute_lines` 参数
  - 验收记录：模块 [`product_dimension/CHANGELOG.md`](product_dimension/CHANGELOG.md) → `[19.0.3.0.0]`、[`product_variant_conversion/CHANGELOG.md`](product_variant_conversion/CHANGELOG.md) → `[19.0.5.0.0]`；`product_dimension` **10 项**、`product_variant_conversion` **43 项 × 四种配置**（只装 `product` / 加装 `product_dimension` / 加装 `product_reference` / 加装 `stock` + `sale_management`）全部 0 failed / 0 error；干净库（只装 `product_dimension`）合成 arch 实测三表单均含尺寸块；`task check` 通过
  - 遗留：目标环境复验界面（多变体产品从「变体」按钮进表单能填尺寸）；`T-028` 仍是 7 个模块的告警待清理

- **T-027 权限文件去掉对 sale 用户组的硬编码（`sales_team.group_sale_manager`）** ｜ `product_reference` + `product_image` ｜ P1
  - 完成日期：2026-09-22 ｜ 状态：**已交付，待目标环境验证**
  - 落地版本：`product_reference` `19.0.2.5.3`、`product_image` `19.0.2.6.4`
  - 判定（为什么是「删」而不是「换组」）：那行权限是 `1,1,1,1`，与保留的 `base.group_user` 行**完全相同**；
    而 `sales_team.group_sale_manager` 的隐含链是 `→ group_sale_salesman_all_leads → group_sale_salesman
    → base.group_user`，销售经理本来就是内部用户 → 该行**不额外授予任何权限**，删除即等价
  - 影响范围：同一次全仓库排查还发现 `product_image` 有同样写法，一并修掉；新增门禁检查防止复发
  - 验收记录：模块 `CHANGELOG.md` → `[19.0.2.5.3]` / `[19.0.2.6.4]`；
    `task test -- product_reference` 与 `task test -- product_image`（均**不装 `sale`**）安装通过；
    开发库中旧的 `ir.model.access` 记录被 Odoo 自动清理；`task check` 新增「引用未声明依赖模块的用户组」检查
  - 遗留：`product_image` 的 manifest description 仍会触发 docutils RST 告警，见 `T-028`
- **T-025 切换器 Card 按钮名国际化（改为 `_t()` getter）** ｜ `product_card_view` ｜ P2 ｜ 视图切换器里的 Card 按钮名未国际化（硬编码 "Card"）
  - 完成日期：2026-09-22 ｜ 状态：**已交付，待目标环境验证（界面）**
  - 背景：按钮名来自 JS 侧 patch 的 `session.view_info.card.display_name`（写死 `"Card"`），中文界面仍显示英文；`session.view_info` 是服务端核心提供的白名单、模块级 Python 无法扩展，只能在前端处理；模块 `README.md` →「遗留问题」已记录
  - 建议：改为 `_t("Card")`（`@web/core/l10n/translation`）并在 `i18n/zh_CN.po` 补 `code:addons/product_card_view/static/src/js/product_card_view.js:0` + `#. odoo-javascript` 的条目；若模块加载时翻译尚未就绪，用 `Object.defineProperty` 的 getter 让它在切换器渲染时才求值
  - 关联：模块 `README.md` →「国际化」/「遗留问题」；`AGENTS.md` → L2 P2
  - 检测：product_card_view/static/src/js/product_card_view.js 不含 display_name: "Card"
- **T-021 产品尺寸模块重写：product_packing → product_dimension（移除纸箱 + 尺寸下沉到变体）** ｜ `product_dimension` + `product_variant_conversion` ｜ P2
  - 完成日期：2026-09-22 ｜ 状态：**已交付，待目标环境验证**
  - 落地版本：`product_dimension` `19.0.2.0.0`、`product_variant_conversion` `19.0.4.1.0`
  - 起因：原 `product_packing` 的产品尺寸靠写**模板侧** `volume` 同步，而 Odoo 的桥接写入只在单变体时落到变体 → 产品一旦变成多变体，改尺寸就不再更新任何变体的 Volume
  - 做法：模块改名为 `product_dimension` 并**只保留物流尺寸**（尺寸单位 cm / m + 长宽高）；**尺寸下沉到 `product.product`**（模板侧退化为单变体桥接，与原生 `volume` / `weight` 同构）；移除全部纸箱字段 / 分组 / 列表列 / 校验；新增 `pre_init_hook` 把旧模块留在模板上的尺寸数据搬到变体并按单位重算 Volume；补 6 项自动化测试；`product_variant_conversion` 的按谱系继承清单带上尺寸四件套（只在来源尺寸齐全时复制，避免把继承来的体积冲掉）
  - 验收记录：模块 [`product_dimension/README.md`](product_dimension/README.md)（含「从 product_packing 迁移」与验证清单）、[`product_dimension/CHANGELOG.md`](product_dimension/CHANGELOG.md) → `[19.0.2.0.0]`、[`product_variant_conversion/CHANGELOG.md`](product_variant_conversion/CHANGELOG.md) → `[19.0.4.1.0]`
  - 实测：开发库旧数据搬运成功（`filled 56 variant rows` + `recomputed volume for 1 variants`，变体侧得到 `cm / 50 / 40 / 30`、`volume = 0.06`，模板侧镜像同步）；卸掉旧模块记录后加载无告警；`product_dimension` 6 项、`product_variant_conversion`（连同本模块）39 项测试全部通过
  - 遗留：目标环境需按「**先装新模块、再卸旧模块**」的顺序迁移并核对界面；`Volume` 默认只有 2 位小数属 Odoo 原生设置（见模块 README →「已知限制」）；纸箱能力已移除，如需要请另立模块


---

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
  - 后续修订（追溯）：`19.0.2.0.7`（2026-09-22）修复「切换筛选 / 分组后卡片空白、过宽、无间隙」——
    取数范围覆盖分组、payload 成功后整体替换 + `useEffect` 兜底重渲染、分组布局改由 SCSS 给；
    文档见模块 `CHANGELOG.md` → `[19.0.2.0.7]`、`README.md` →「筛选 / 分组下的取数与布局」、
    `AGENTS.md` → L2 P6；复验项 TC-12 / TC-13（待目标环境验证）
- **T-011 产品参考号界面改造 + 多变体参考号不共用**：2026-09-08 验收通过，落地版本
  `19.0.2.5.0`，记录见 [`product_reference/CHANGELOG.md`](product_reference/CHANGELOG.md)   →「验收记录（T-011）」。
