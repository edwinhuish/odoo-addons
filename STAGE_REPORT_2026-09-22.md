# 阶段总结与交接报告（2026-09-22）

> **本文件定位**：汇总本阶段（2026-09-22 一轮迭代）的全部工作，按模块与任务分类，给出**目标 / 主要成果 /
> 关键问题与解决方案 / 验证 / 遗留**，并附交接清单（命令、界面复验步骤、文件地图）。
>
> **权威细节仍在各模块三件套**：`README.md`（使用者）、`CHANGELOG.md`（逐版本变更）、`AGENTS.md`（约束与踩坑）。
> 本文件只做汇总、索引与横切归纳，冲突时以模块文档为准。
>
> 规范依据：根 [`AGENTS.md`](AGENTS.md) 第 7/8 节、[`DOCS_TEMPLATE.md`](DOCS_TEMPLATE.md)。

---

## 0. 一页速览

| 项 | 内容 |
|---|---|
| 阶段 | 2026-09-22（单日一轮，5 个提交） |
| 提交 | `74fdade`（T-021 改名 + 尺寸下沉）→ `368f3a7`（i18n 静默失效）→ `44ad9ed`（po 检查 + Card 视图与入口）→ `66b8dda`（可选模块用户组 + 参考号归属）→ `6be1a3f`（前端算体积 + 转换映射） |
| 涉及模块 | `product_dimension`（主战场）、`product_variant_conversion`、`product_reference`、`product_image`、`product_card_view` |
| 交付任务 | **T-021**、**T-025**（收尾）、**T-027**、**T-029**、**T-030**、**T-031**、**T-032** |
| 版本变化 | `product_dimension` 19.0.1.1.3 → **19.0.4.1.0**；`product_variant_conversion` 19.0.4.0.0 → **19.0.5.0.0**；`product_reference` → **19.0.2.5.3**；`product_image` → **19.0.2.6.4**；`product_card_view` **19.0.2.0.6** |
| 自动化测试 | `product_dimension` **17 项**、`product_variant_conversion` **43 项 × 4 种配置**（只装 `product` / +`product_dimension` / +`product_reference` / +`stock`+`sale_management`）全绿 |
| 仓库门禁 | `task check` 新增 **4 类**校验（po 三类静默失效 + 可选模块用户组引用），均用已知坏数据自证有效 |
| 待目标环境验证 | `product_dimension` 界面即时计算与精度、`product_variant_conversion` 弹窗、Card 入口覆盖；清单见第 6 节 |
| 工作树状态 | 干净（本阶段改动全部已提交）；仅本报告文件为新增未提交 |

> **一句话概括**：把「产品尺寸」从一个放错层级的模块（模板级、夹带纸箱字段）重做成**变体级 + 前后端职责清晰**
> 的模块；过程中修掉 **3 个会造成数据不一致的真 bug**（多变体共用参考号、无 `product_reference` 时转换必崩、
> cm 小体积被算成 0），并把这几类问题的防护**固化进仓库门禁与自动化测试**。

---

## 1. 任务总表

| 任务 | 模块 | 一句话目标 | 落地版本 | 状态 | 提交 |
|---|---|---|---|---|---|
| **T-021** | `product_dimension` + `product_variant_conversion` | `product_packing` 改名 `product_dimension`；移除纸箱；尺寸从模板下沉到变体 | `19.0.2.0.0` / `19.0.4.1.0` | 已交付，待目标环境验证 | `74fdade` |
| （T-021 配套） | `product_dimension` | 修 i18n 三类静默失效（中文界面一直英文）+ 中文打磨 | `19.0.2.0.1` | 已交付，已按数据库核对 | `368f3a7` |
| **T-025** | `product_card_view` | 视图切换器 Card 按钮名国际化（改 `_t()` getter）+ 补 5 条失效 JS 译文 | `19.0.2.0.6` | 已交付 | `44ad9ed` |
| （Card 入口） | `product_card_view` | 销售 / 采购 / 发票入口也注入 Card；所有产品列表默认视图为 Card | `19.0.2.0.6` | 已交付，界面待复验 | `44ad9ed` |
| **T-027** | `product_reference` + `product_image` | 权限文件不再硬编码 `sale` 相关用户组（导致无 `sale` 的库装不上） | `19.0.2.5.3` / `19.0.2.6.4` | 已交付 | `66b8dda` |
| （参考号归属） | `product_reference` + `product_variant_conversion` | 多变体产品不再共用一组参考号；转换时产品级共享参考号交接给被保留的变体 | `19.0.2.5.3` / `19.0.4.1.1` | 已交付 | `66b8dda` |
| **T-029** | `product_dimension` + `product_variant_conversion` | 补尺寸挂载点（多变体产品原本无入口）；转换来源映射更准；修「无 `product_reference` 时转换必崩」 | `19.0.3.0.0` / `19.0.5.0.0` | 已交付，待目标环境验证 | `6be1a3f` |
| **T-030** | `product_dimension` | 表单填完尺寸即算出 `Volume`（服务端预览） | `19.0.3.1.0` | 已交付（**被 T-031 重做取代**） | `6be1a3f` |
| **T-031** | `product_dimension` | 体积改由**前端**算、后端只兜底且不再返回体积 | `19.0.4.0.0` | 已交付，界面待复验 | `6be1a3f` |
| **T-032** | `product_dimension` | 修「cm 尺寸的小体积显示 / 保存成 0」（前端取整参数 + Volume 精度提到 6 位） | `19.0.4.1.0` | 已交付，界面待复验 | `6be1a3f` |

---

## 2. 按模块的工作明细

### 2.1 `product_dimension`（本阶段改动最重，共 5 个版本）

**阶段起点**：前身 `product_packing` 把尺寸与纸箱字段放在**产品模板**上，并用「写模板侧 `volume`」来同步体积 ——
Odoo 的桥接写入只在单变体时落到变体，产品一旦变成多变体，改尺寸就不再更新任何变体的体积（原 `T-021` 的病灶）。

**阶段终点**：尺寸真身在 `product.product`，模板侧退化为与原生 `volume` / `weight` 同构的**单变体桥接**；
界面侧体积由**浏览器**算、后端只在非界面路径兜底；三个表单都有挂载点；精度够小体积用。

#### 版本链（自上而下为演进顺序）

| 版本 | 主题 | 关键内容 |
|---|---|---|
| `19.0.2.0.0` | 改名 + 尺寸下沉（T-021） | `git mv` 保留历史；删 10 个 `carton_*` 字段与相关视图 / 校验；尺寸落到变体；`pre_init_hook` 搬旧数据；零测试 → 6 项 |
| `19.0.2.0.1` | i18n 静默失效修复 | po 三类失效（`#:` 双前缀 / 多行 `msgstr` 语法错 / 缺 `#. odoo-python`）；中文界面一直英文却「导入不报错」 |
| `19.0.3.0.0` | 挂载点补齐（T-029） | 变体快速编辑表单（「变体」按钮入口）此前**没有尺寸入口**；锚点带组名；明确「与原生 `Volume` 同进同退」 |
| `19.0.3.1.0` | 表单填完即算（T-030） | 补模板侧 onchange，产品表单填完尺寸立刻显示体积（**后续被 T-031 重做**） |
| `19.0.4.0.0` | 前后端职责重划分（T-031） | 体积改由前端算、后端只兜底；删两个尺寸 onchange；`_should_sync_volume()` |
| `19.0.4.1.0` | 小体积显示 0（T-032） | 前端取整参数用错（任何小于 1 的体积变 0）+ 「Volume」精度 2 → 6 位 |

#### 关键问题与解决方案

| # | 问题 | 根因 | 解决方案 |
|---|---|---|---|
| 1 | 模板级尺寸在多变体下永不生效 | 写模板侧 `volume` 的桥接只在单变体时落到变体（`_set_product_variant_field` 语义） | 尺寸真身下沉到 `product.product`；模板侧改为 `compute + inverse + store` 的单变体桥接；转换模块按谱系继承尺寸 |
| 2 | 改名后旧数据会丢 | 模块改名 = Odoo 视为新模块，旧模块的 migration 脚本不会执行；旧字段已不在注册表 | `pre_init_hook` 只按 **SQL 列名**搬运（`ADD COLUMN IF NOT EXISTS` + `COALESCE`，幂等），并按单位重算 `volume`；实测日志 `filled 56 variant rows` / `recomputed volume for 1 variants` |
| 3 | 中文界面一直英文，导入却不报错 | ① `#:` 引用行被多加一层前缀 → `PoFileReader` 匹配不到记录，条目静默丢弃；② 多行 `msgstr` 写成真实换行 → `polib` 语法错，**整份 po** 一条都读不进；③ `code:` 条目缺 `#. odoo-python` / `odoo-javascript` 标记 → 运行期与前端译文永不生效 | 重写 po（引用行、多行写法、标记）；`task check` 新增对应校验；**验收一律回数据库 / 运行时核对**（不信任「导入成功」） |
| 4 | 多变体产品的尺寸在界面上没有入口 | 产品的「变体」按钮用的是 `product_variant_easy_edit_view`：**独立 primary 视图、不继承模板表单**，原本没有挂载 | 单独挂载该表单；模板表单锚点收紧为 `//group[@name='group_lots_and_weight']/label[@for='volume']`（防字段挂两遍）；用测试钉住「三表单都挂」与「与原生 `volume` 同进同退」 |
| 5 | 转换时新变体拿不到来源（尺寸 / 体积丢失） | 旧来源判定比对「转换前属性轴上的取值组合」，而**本次新加的取值**也落在这些轴上 → 新变体永远匹配不上任何原变体（只有一条原变体时靠兜底指对） | 改为按「**转换前已存在的取值**」匹配（投影比较 + 最具体优先，仍并列才留空）；补两条测试（映射准确 + 尺寸落到对应变体） |
| 6 | 没装 `product_reference` 时**每一次转换都失败** | 跳过分支里 `browse` 了 `product.reference.code`，模块未装时该模型不在注册表 → `KeyError`（HEAD 实测 33/43 条用例 error） | 返回硬依赖模型的空记录集；测试跑四种配置（含未装该模块） |
| 7 | 产品表单填完尺寸，`Volume` 还是 0（要保存后才出现） | 预览 onchange 只挂在 `product.product`，而产品表单的模型是 `product.template`；模板侧是单变体桥接，inverse 只在保存时跑，原生 `volume` 又是 `compute + inverse + store` | v1（T-030）补模板侧 onchange；v2（T-031）整体改为**前端计算**，后端不再为界面算 |
| 8 | cm 尺寸的体积显示 0 | ① 前端把 `roundPrecision()` 的第二参数当小数位数传 `2`（它要的是**精度因子** `0.01`）→ 按 2 的整数倍取整，任何小于 1 的体积变 0，且随表单提交把 0 存库；② 原生「Volume」精度出厂 2 位 → 20×20×20 cm = 0.008 m³ 被舍成 0 | 前端纯规则抽成无依赖文件并自己实现 `roundToDecimals`；新增 node 实跑单测；`hooks.ensure_volume_precision()` 在**安装**与**升级**两处把精度提到 6 位（只升不降） |

#### 验证结果（本地）

| 项 | 结果 |
|---|---|
| 旧数据搬运 | dev 库实测：`filled 56 variant rows` + `recomputed volume for 1 variants`；变体侧 `cm / 50 / 40 / 30`、`volume = 0.06`；卸掉旧模块记录后加载无告警 |
| 三表单挂载 | 干净库合成 arch：模板表单 / 变体表单 / 变体快速编辑表单均含四个尺寸字段（快速编辑表单改造前 0 处 → 改造后 9 处） |
| 前端资源进包 | `ir.asset._get_asset_paths("web.assets_backend", {})` 共 2464 条，含 `product_dimension/static/src/js/dimension_volume.js` |
| 小体积 | dev 库实测 `10³ cm → 0.001`、`20³ cm → 0.008`、`50³ cm → 0.125`（修复前 0 / 0.01 / 0.13） |
| 精度提升 | 迁移日志 `raising the Volume decimal precision from 2 to 6`；库内 Volume = 6 |
| 自动化测试 | **17 项 0 failed**（含 node 实跑前端规则、小体积精度、职责划分 4 条） |
| 门禁 | `task check` 通过（含 JS 语法） |

**遗留**：界面即时显示与精度效果需目标环境复验；`Volume` 是全局精度设置（模块只升不降，其它模块的体积显示会一并变精确）。

---

### 2.2 `product_variant_conversion`

| 项 | 内容 |
|---|---|
| 目标 | 让「加属性 / 加取值」不丢既有变体（既有 `product.product` 记录 id 不变），并让转换结果与尺寸模块、参考号模块正确协同 |
| 本阶段成果 | ① `19.0.4.1.0`：按谱系继承清单带上尺寸四件套（尺寸齐全才复制，避免触发「尺寸不齐归 0」把继承来的体积冲掉）；② `19.0.4.1.1`：新增 `_transfer_shared_references_to_original()`，把单变体时期留在产品级的共享参考号交接给被保留的变体（否则「两处都看不到」表现为参考号丢失）；③ `19.0.5.0.0`：来源判定换算法 + 修「没装 `product_reference` 时转换必崩」+ 实现 `product_dimension` 的挂载 / 映射要求 |
| 关键问题 | 见上表 #5、#6；另有 `_log_variant_conversion()` 在程序化调用（不传 `added_attributes`）时拿到 `None` 报错的隐患，一并改为用推断值 |
| 接口变化 | 移除不再需要的 `previous_attribute_lines` 参数（来源判定按各变体携带的取值认，不再依赖「改动前的属性行快照」） |
| 验证 | **43 项 × 4 种配置全绿**（只装 `product` / +`product_dimension` / +`product_reference` / +`stock`+`sale_management`）；修复前同一跑法 33 error |
| 遗留 | 弹窗交互、取消不保存、中英文界面需目标环境复验 |

---

### 2.3 `product_reference` / `product_image`

| # | 问题 | 根因 | 解决方案 |
|---|---|---|---|
| 1 | 没装 `sale` 的库**装不上本模块** | `security/ir.model.access.csv` 引用了 `sales_team.group_sale_manager`，而 `depends` 只有 `product`（`sale` / `purchase` / `stock` / `account` 都是可选模块） | 删掉该行：其权限（`1,1,1,1`）与保留的 `base.group_user` 行**完全相同**，且 `sales_team.group_sale_manager` 的隐含链最终包含 `base.group_user`（销售经理本来就是内部用户）→ 纯冗余，删除即等价，无需换组 |
| 2 | `product_image` 有同样写法 | 同一次全仓库排查发现 | 一并删除；两模块版本各 +z |
| 3 | 同类问题会复发 | 门禁没有覆盖「数据文件里引用可选模块的用户组」 | `check_repo.py` 新增该检查（引用未声明依赖的模块用户组 → 失败），并用**已知坏数据自证**会报错 |
| 4 | 多变体产品的每个变体都在编辑**同一组共享参考号** | 变体表单里的 `reference_code_line_ids` 缺 `lines_field` option，默认落到继承来的产品级共享行上（与「多变体不共用」的 L1 约束冲突） | 显式指定 `options="{'lines_field': 'variant_reference_code_line_ids'}"`，并保证变体级行与产品级共享行互不干扰 |

**验证**：`task test -- product_reference`（**不装 `sale`**）与 `task test -- product_image` 均安装成功、0 failed；dev 库里旧权限记录被 Odoo 自动清理，只剩 `base.group_user` 一行。

---

### 2.4 `product_card_view`

| 项 | 内容 |
|---|---|
| 目标 | 修复「Card 视图在 销售/库存 与 采购/库存 入口不显示」，并让 Card 名称中文化 |
| 成果 | ① 注入改为**读取时计算**（覆盖 `_compute_views()`），修掉「全新安装时 `sale` / `purchase` 尚未安装导致漏注入」——开发库核对 7 个产品动作的 `action.views`；② 让销售 / 采购 / 发票入口也注入 Card，并把所有产品列表的默认视图定为 Card（按模型扫描 + 记录带 `sequence`）；③ Card 按钮名改走 `_t()` getter 并补 5 条此前失效的 JS 译文 |
| 验证 | 开发库逐动作核对 `action.views`；`task init -- --fresh` 实测全新安装路径；界面待复验 |
| 风险 | 依赖 Odoo 内部 `session.view_info` 的 JS patch，Odoo 升降级需回归（见模块 `AGENTS.md` → L2 P2） |

---

### 2.5 仓库工程能力（本阶段的「副产品」，价值长期）

| 能力 | 内容 | 位置 |
|---|---|---|
| po 三类静默失效校验 | 引用行写法 / 条目缺引用行 / 缺 `odoo-python`·`odoo-javascript` 标记 / 行结构不合法 | `.dev/scripts/check_repo.py` |
| 可选模块用户组校验 | 数据文件里的用户组必须来自 `base` 或已声明依赖 | 同上 |
| 应用列表元数据一致性 | `shortdesc` / `summary` / `description` 的 `msgid` 必须与 manifest **逐字符一致** | 同上（本阶段多次拦住失同步） |
| TODO 看板 | `task todo` 跑每条需求的 `检测：` 条件，输出「可能已实现 / 未实现」；门禁校验条目格式 / ID 唯一递增 / 模块目录与文档链接存在 | `TODO.md` + `.dev/scripts/todo_status.py` |
| 文档体系 | 模块三件套骨架与同步关系（README / CHANGELOG / AGENTS） | `DOCS_TEMPLATE.md`（本阶段多次按此对齐） |

---

## 3. 关键问题与解决方案（横切归纳）

| 类别 | 典型现象 | 通用解法 | 沉淀位置 |
|---|---|---|---|
| **改名 / 重构的数据安全** | 模块改名后旧数据静默丢失 | 改名 = 新模块；旧 migration 不跑 → 用 `pre_init_hook` + SQL 列名搬运，幂等可重跑；升级顺序必须**先装新模块再卸旧模块** | `product_dimension/AGENTS.md` L1-6、L2 P4 |
| **「没报错」≠「生效」** | 中文界面一直英文，导入日志正常 | i18n 有 3 类静默失效；验收必须回 `ir_model_fields` / `ir_ui_view` / `ir_module_module` / 运行期报错去核对；把三类问题写成门禁规则 | 根 `AGENTS.md` 4.x、`product_dimension/AGENTS.md` L2 P5 |
| **可选模块依赖** | 没装 `sale` 就装不上；没装 `product_reference` 转换全崩 | 数据文件不得引用可选模块的**用户组**；代码里用**字段存在性**判断，且跳过分支不得 `browse` 未安装的模型（返回硬依赖模型的空记录集） | `product_reference/AGENTS.md` L1-1.2、`product_variant_conversion/AGENTS.md` |
| **视图挂载** | 多变体产品在界面上没有尺寸入口；字段被挂两遍 | 认清三件事：变体表单**继承**模板表单（别重复挂）、快速编辑表单是**独立 primary**（必须单独挂）、锚点要带组名；可见性与原生 `volume` 同进同退 | `product_dimension/AGENTS.md` L1-2.1、L2 P6 |
| **前后端职责** | 同一件事两处各算一遍、结果还不一致 | 明确「界面归前端、后端只兜底」；`_should_sync_volume()` 作为唯一判定；规则两处一致要有测试守卫 | `product_dimension/AGENTS.md` L1-3、L2 P7 |
| **精度与取整** | 体积该有小数却显示 0 | 取整 API 的语义要查文档（`roundPrecision` 收的是**精度因子**）；数值字段的全局精度会吃掉小数值；模块在安装 / 升级两处统一提升 | `product_dimension/AGENTS.md` L2 P8 |

---

## 4. 经验教训

1. **改名前先定数据搬运方案**。模块改名在 Odoo 里等价于「换了一个模块」，旧 migration 不会执行 —— 必须在安装前钩子里按列名搬，并把「先装新、再卸旧」写进迁移步骤。
2. **「导入成功」是最不可信的验收口径**。i18n 的 `#:` 前缀、多行 `msgstr`、缺注释标记这三类问题都不报错，只是静默失效；**去数据库与运行时看**才是证据。
3. **可选模块的东西一律不许硬编码**。用户组、模型、字段都可能不存在：组引用会让安装直接失败，`browse` 未安装的模型会让主流程每次崩（本阶段真遇到：转换 100% 失败）。
4. **测试要在「干净库」跑**。本阶段两个严重 bug（权限组导致装不上、未装可选模块导致转换崩）都只在只装 `product` 的环境暴露；开发库因为装了全量模块，一直看不出来。
5. **前端逻辑必须有可执行的测试**。T-032 的 bug（体积全变 0）就是「前端没人测」的典型：把纯规则抽成无依赖文件、用 `node` 跑断言，是成本最低的保护（`task check` 已能跑 JS 语法，测试里已能跑 JS 行为）。
6. **职责划分要写死，不能靠默契**。「界面算、后端兜底」明确后，才谈得上「不重复计算」；规则两处一致必须有守卫，否则一定漂移。
7. **门禁要用已知坏数据自证**。新增校验后，把导致问题的坏数据临时放回去跑一遍，确认它真的会拦（本阶段新增的几条检查都做了这一步）。
8. **沉默的默认值会吃掉功能**。「Volume 精度出厂 2 位」不是 bug 报告，而是让 20 cm 见方的货物体积显示 0 —— 默认值与业务场景不匹配时，要主动调整并在文档里写明理由与影响面。
9. **同一功能可能被重做**（T-030 → T-031）。第一次只补了「服务端预览」，第二次才想清楚职责边界；重做时把旧文档、CHANGELOG 与 L1 约束同步改写，避免文档与实际实现互相矛盾。

---

## 5. 后续建议

### 5.1 待办池（`TODO.md`，均已登记）

| 任务 | 模块 | 内容 | 建议优先级 |
|---|---|---|---|
| `T-026` | `product_reference` + `sale_product_hover` + `product_image` + `product_variant_conversion` + `sale_order_no` | po 里 `code:` 条目缺 `odoo-python` / `odoo-javascript` 标记（共 25 条），这些前端 / Python 文案一直没翻译；补完把 `check_repo.py` 的这两条从「警告」改回「失败」 | P2 |
| `T-028` | 7 个模块（`product_image` / `product_reference` / `product_variant_conversion` / `sale_order_no` / `sale_product_hover` / `web_image_paste` / `web_multi_tabs`） | manifest `description` 用悬挂缩进 → 安装日志每次打 docutils RST 告警；改成「一条一行」并同步 po 的 description `msgid` | P2 |

### 5.2 可选加固（未登记，视需要立项）

1. **前端交互的真测试**：本阶段已能跑「纯规则」的 node 测试，但 OWL 补丁本身（`Record._update` 挂钩、写回 `volume`）仍只能靠目标环境人工复验；若后续前端逻辑继续变厚，建议引入浏览器端测试。
2. **`Volume` 精度改为可配置**：目前模块把全局精度提到 6 位（只升不降）。若某部署有别的诉求，可考虑读系统参数（如 `product_dimension.volume_precision`）来决定提升目标。
3. **规则一致性的守卫升级**：现在 JS ↔ Python 的一致性靠「字段名 / 常数 / 取整」的断言 + node 行为测试；若规则再复杂，建议把规则参数化后由两侧共同读取同一份声明。
4. **模板侧桥接的长期风险**：尺寸 / 体积的模板侧字段与原生 `volume` / `weight` 同构，长期依赖 Odoo 的桥接语义；Odoo 大版本升级时需回归（已写入模块 `AGENTS.md`）。

### 5.3 风险提示

- `product_variant_conversion` 的转换链路改动面大（来源判定、价格分离、参考号交接），**依赖 43 项测试 + 目标环境复验**兜底；弹窗交互属于纯前端，无法在无浏览器环境自动化。
- `product_card_view` 依赖 Odoo 内部 `session.view_info` 的 JS patch，Odoo 升降级需回归。
- `product_dimension` 的前端即时计算依赖 `web` 模块（Odoo `auto_install`，实际总在）；即使缺失也只是少了界面即时计算，落库仍由后端兜底。

---

## 6. 交接清单

### 6.1 目标环境动作（按顺序执行）

```bash
# 1) 升级本轮涉及的模块（product_dimension 会跑迁移脚本提升 Volume 精度）
task update -- product_dimension product_variant_conversion product_reference product_image product_card_view

# 2) 可选：确认精度已提升（应显示 6）
#    设置 → 技术 → 小数精度 → Volume

# 3) 门禁与看板
task check
task todo
```

> ⚠ `product_packing` → `product_dimension` 的迁移顺序是**先装新模块、再卸旧模块**（旧列在卸载时才被删除；
> 搬运已由安装前钩子完成）。目标环境若尚未完成这一步，见模块 `README.md` →「从 product_packing 迁移」。

### 6.2 界面复验清单

| 模块 | 步骤 | 期望 |
|---|---|---|
| `product_dimension` | 单变体产品 → Logistics 组填 `Dimension Unit = Centimeters` + 长宽高 `20 / 20 / 20` | `Volume` **当场**显示 `0.008`（不保存即出现；此前显示 0） |
| `product_dimension` | 同上，改长宽高为 `50 / 40 / 30` | `Volume` 显示 `0.06`；保存后不变 |
| `product_dimension` | 多变体产品 → 点「**变体**」按钮 → 进任一变体的表单 | 能看到 `Dimension Unit` 与 `Dimensions` 并可逐条填写，各自 `Volume` 独立；产品表单上这些字段隐藏 |
| `product_dimension` | 同一多变体产品在有 / 无「计量单位管理」权限的用户下对比 | 尺寸块与原生 `Volume` **同进同退**（不允许「体积在、尺寸没了」） |
| `product_variant_conversion` | 给带尺寸的产品做一次「给已有属性加取值」的转换 | 新变体挂在对应原变体（`Derived From`）、继承其尺寸与体积；无 `product_reference` 的环境下转换仍可保存 |
| `product_variant_conversion` | 转换弹窗：改组合归属 / 取消保存 / 中文界面 | 归属逐组合可改；取消不落库；文案为中文 |
| `product_card_view` | 库存 / 销售 / 采购三个入口打开产品列表 | 视图切换器有 **Card**（中文名），且默认进入 Card；卡片内容 / 多图 / 变体按钮正常 |
| `product_reference` | 多变体产品的变体表单编辑参考号 | 编辑的是**本变体专属**参考号，不影响其它变体；单变体 → 多变体转换后原参考号仍可查到 |

### 6.3 改动文件地图（本阶段）

| 路径 | 职责 / 本阶段改动 |
|---|---|
| `product_dimension/models/product_product.py` | 尺寸真身、`volume_from_dimensions()`（唯一换算口径）、`_should_sync_volume()`（是否兜底重算）、非负校验 |
| `product_dimension/models/product_template.py` | 单变体桥接（读镜像 + 写回变体） |
| `product_dimension/static/src/js/dimension_volume_rules.js` | 体积计算纯规则（无 Odoo 依赖，可被 node 直接测） |
| `product_dimension/static/src/js/dimension_volume.js` | `Record._update` 补丁：改尺寸 / 单位即算好并写回 `volume` |
| `product_dimension/views/product_template_views.xml` | 挂载地图：模板表单插入 + 变体快速编辑表单挂载（锚点带组名） |
| `product_dimension/hooks.py` | 安装前搬旧数据；`ensure_volume_precision()`（Volume 精度 ≥ 6，只升不降） |
| `product_dimension/migrations/19.0.4.1.0/` | 升级路径补一次精度提升（`post_init_hook` 只在安装时跑） |
| `product_dimension/tests/test_product_dimension.py` | 17 项（含 node 实跑前端规则） |
| `product_variant_conversion/models/product_template.py` | 转换主流程、来源判定 `_find_variant_conversion_origin()`、参考号交接、尺寸继承清单 |
| `product_variant_conversion/tests/test_product_variant_conversion.py` | 43 项（含加取值映射、尺寸落到对应变体、参考号交接） |
| `product_reference/security/ir.model.access.csv` / `product_image/security/ir.model.access.csv` | 删掉硬编码的 `sales_team.group_sale_manager` 行 |
| `product_reference/views/product_product_views.xml` | 变体表单指定 `lines_field: variant_reference_code_line_ids`（多变体不共用） |
| `.dev/scripts/check_repo.py` | 新增 po 三类失效校验 + 可选模块用户组校验 + 应用列表元数据一致性校验 |
| 各模块 `README.md` / `CHANGELOG.md` / `AGENTS.md`、根 `README.md` / `AGENTS.md` / `TODO.md` | 版本、验证清单、L1/L2 约束、任务状态同步 |

### 6.4 常用命令速查

```bash
task check                                   # 仓库门禁（po / XML / JS 语法 / TODO 结构 / 用户组引用）
task todo                                    # 需求看板（待办池 + 检测条件探测）
task test -- product_dimension               # 17 项
task test -- product_variant_conversion,product_dimension --test-tags=/product_variant_conversion
task update -- product_dimension             # 升级（含迁移脚本）
task i18n -- zh_CN product_dimension         # 导入中文译文
```

### 6.5 交付状态说明

- 本阶段全部代码与文档改动**已提交**（`74fdade` → `6be1a3f`），工作树干净。
- 本报告文件 `STAGE_REPORT_2026-09-22.md` 为**新增内容，尚未提交**（由你决定是否入库）。
- 各模块的「待目标环境验证」状态以根 `README.md` 模块一览表与模块 `README.md` →「验证清单」为准；
  完成复验后把状态改为「已验收」并同步 `CHANGELOG.md` 的版本标题括号内容（`（待验证）` → `（已验证）`）。
