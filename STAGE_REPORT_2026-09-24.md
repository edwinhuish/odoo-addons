# 阶段总结与交接报告（2026-09-24）

> **本文件定位**：汇总本阶段（2026-09-23 夜 ~ 2026-09-24 一轮迭代）的全部工作。本阶段有**两条并行工作流**：
> 主战场 `product_variant_conversion`（两次线上报错修复、一次边界核实、两个需求 `T-039` / `T-040`），
> 以及同期并行的 `product_image`（`T-038`：产品列表「Images」列改显主图缩略）。
> 按「目标 / 成果 / 关键问题与解法 / 验证 / 遗留」组织，并附交接清单（命令、界面复验步骤、文件地图）。
>
> **权威细节仍在模块三件套**：`README.md`（使用者）、`CHANGELOG.md`（逐版本变更）、`AGENTS.md`（约束与踩坑）。
> 本文件只做汇总、索引与横切归纳，冲突时以模块文档为准。
>
> 规范依据：根 [`AGENTS.md`](AGENTS.md) 第 7/8 节、[`DOCS_TEMPLATE.md`](DOCS_TEMPLATE.md)；
> 上一轮报告见 [`STAGE_REPORT_2026-09-22.md`](STAGE_REPORT_2026-09-22.md)。

---

## 0. 一页速览

| 项 | 内容 |
|---|---|
| 阶段 | 2026-09-23 夜 ~ 2026-09-24（`product_variant_conversion` 四轮迭代 + 同期并行的 `product_image` 一轮修复） |
| 提交 | `9748eeb`（`product_image` `19.0.2.6.5` 列表图片列，2026-09-23 17:30）→ `4167303`（`19.0.5.3.1` 按需属性拦截）→ `0d21c07`（`19.0.5.3.2` chatter 崩溃修复）；`T-039`（`19.0.6.0.0`）、`T-040`（`19.0.6.1.0`）与边界文档**尚未提交** |
| 涉及模块 | `product_variant_conversion`（主战场，`19.0.5.3.0` → **`19.0.6.1.0`**，4 个版本）+ `product_image`（并行修复，`19.0.2.6.4` → **`19.0.2.6.5`**，1 个版本，见第 7 节） |
| 交付任务 | **`T-039`**（支持按需生成属性）、**`T-040`**（弹窗选项自动互换）、**`T-038`**（`product_image` 产品列表「Images」列改显主图）；两次线上报错修复 + 一次边界核实（无独立任务号） |
| 版本变化 | `19.0.5.3.1`（+z 修复）→ `19.0.5.3.2`（+z 修复）→ `19.0.6.0.0`（+y 功能）→ `19.0.6.1.0`（+y 交互）；并行：`product_image` `19.0.2.6.4` → `19.0.2.6.5`（+z 修复 + 定向译文迁移） |
| 自动化测试 | `product_variant_conversion` **47 项**；四组配置全绿（只装 `product` / +`stock`+`sale_management` / +`product_dimension` / +`product_reference`+`product_card_view`+`sale_management` = 47 / 47 / 47 / **57** 项，0 failed / 0 error）；`product_image` 新增 **7 项**（装齐 `stock`+`sale_management`+`purchase` 时 7 项全部执行，0 failed / 0 error） |
| 仓库门禁 | `task check` 通过；顺手修掉本模块 1 条 `code:` 条目缺 `#. odoo-javascript` 标记（`T-026` 在本模块的那 1 条） |
| 待目标环境验证 | `product_variant_conversion`：按需属性产品的转换、弹窗「选项全可选 + 自动互换」、建产品拦截文案、中英文界面（清单见第 6.2 节）；`product_image`：库存 / 销售 / 采购三处产品列表勾选「Images」列显示主图、取消勾选隐藏、中英各一遍（清单见第 7.3 节） |
| 工作树状态 | `product_image` 修复与前两轮 `product_variant_conversion` 修复**已提交**（`9748eeb` / `4167303` / `0d21c07`）；`T-039` + `T-040` + 边界文档 + 本轮文档同步（本报告、根 `README.md` / `AGENTS.md`、`TODO.md`）**未提交**，提交后工作树恢复干净 |

> **一句话概括**：把一个「改属性时保住既有变体」的模块，从「只支持『立即生成』属性」扩展到
> **同时支持『按需生成』属性**（只展开「立即」轴、按需轴留给订单），并把归属弹窗从
> 「已被占用的选项置灰」改成 **「所有选项可选、重复选择自动互换」**；过程中修掉两个真实线上问题
> （按需属性建产品留下「有属性、没变体」的产品；一次加两个属性时 chatter 抛 `Expected singleton` 导致整单回滚）。
>
> **并行的另一件事（`T-038`，第 7 节）**：把产品列表里那个「名叫 `Images`、实则只显示图库计数」的列换成
> 真正的**产品主图缩略**（`image_128` + `image` widget，仅主图），并顺带解决了「改了 po 里**已有**译文、
> `-u` 却不覆盖」的升级陷阱（用一个定向刷新视图 `arch_db` 术语的迁移兜住）。

---

## 1. 任务总表

| 轮次 | 问题 / 需求 | 一句话目标 | 落地版本 | 状态 | 提交 |
|---|---|---|---|---|---|
| 1 | 线上/表单上报错：加属性时提示「按需生成变体…」且**新建产品带按需属性时无报错却没变体** | 定位根因（属性 `create_variant='dynamic'`）并在建产品/改属性两处拦住，报错点名属性 + 给可执行出路 | `19.0.5.3.1` | 已交付，待目标环境验证 | `4167303` |
| 2 | 目标环境 RPC：`ValueError: Expected singleton: product.attribute(2, 1)` | 修 `_log_variant_conversion()` 对多记录集取 `.display_name`，并加回归用例 | `19.0.5.3.2` | 已交付，待目标环境复验 | `0d21c07` |
| 3 | 提问：「按需属性在订单期生成变体时本模块能正确处理吗？」 | 核实订单期路径与本模块的介入情况，写进文档并补边界用例 | （无版本变化，测试 45 → 46） | 已核实并归档，未提交 | 未提交 |
| 4 | **`T-039`** | 支持「按需生成变体」的属性：**只展开「立即」轴**，按需轴按既有变体现带取值钉住 | `19.0.6.0.0` | 已交付，待目标环境验证 | 未提交 |
| 5 | **`T-040`** | 归属弹窗交互优化：所有选项可选，重复选择**自动互换** | `19.0.6.1.0` | 已交付，待目标环境复验（前端） | 未提交 |
| 并行 | **`T-038`**（`product_image`） | 产品列表「Images」列原本绑的是图库计数（**只显示数字**），改为渲染**产品主图**缩略（仅主图） | `19.0.2.6.5` | 已交付，待目标环境界面复验 | `9748eeb`（2026-09-23 17:30） |

---

## 2. 工作明细（`product_variant_conversion`）

### 版本链（自上而下为演进顺序）

```text
19.0.5.3.0  与 product_reference 彻底解耦（上一阶段）
19.0.5.3.1  按需生成属性：建产品拦截 + 点名文案（+z 修复）
19.0.5.3.2  修「一次加两个属性」时 chatter 抛 Expected singleton（+z 修复）
19.0.6.0.0  T-039 支持按需生成属性（只展开「立即」轴）（+y 功能）
19.0.6.1.0  T-040 弹窗选项全可选 + 重复选择自动互换（+y 交互）
```

### 2.1 两次线上报错的根因与修法

**① 按需生成属性（`19.0.5.3.1`）**

- 报错文案在仓库里**唯一**（只有本模块抛）→ 直接反推：产品带 `create_variant='dynamic'` 的属性。
- 实测复现三个现象（dev 库 shell，事务内回滚）：给已有变体的产品加按需属性 → 抛该错；**`create()` 带按需属性 → 不报错但 0 变体**（原生 `_create_variant_ids()` 里 `if not tmpl_id.has_dynamic_attributes()` 整段跳过建变体）；之后任何改属性 → 抛该错。对照组：两个「立即」属性建产品 → 正常 2 变体。
- 原文案的出路**不可执行**：Odoo 不允许修改「已被产品使用」的属性的变体生成方式（`product.attribute.write()` 的 `number_related_products` 检查）。
- 修法：新增 `create()` 拦截（此时属性还没被任何产品使用，出路可执行）+ 文案点名属性 + 给出「先建产品、保存，再把属性加回产品」的两步出路；`create_product_product=False`（导入等沙盒调用）放行。
- 顺带发现（写进文档）：**Odoo 的产品导入会把新建属性自动设成「按需生成」**（`product.product._load_records_create()`），且导入自己逐行建变体 —— 这是后续 `T-039` 的直接动因。

**② `Expected singleton`（`19.0.5.3.2`）**

- 栈指向 `_log_variant_conversion()`：`added_attributes.display_name` 对**多记录集**（一次加 Color + Size 就是两条属性）取单值 → `ensure_one()` 失败。它在转换的最后一步，抛错即**整单回滚**。
- 修法：`", ".join(added_attributes.mapped("display_name")) or "-"`（空记录集保留 `-` 兜底）。
- **回归用例先在旧代码上跑出同一条错**（`ValueError: Expected singleton: product.attribute(1, 2)`）才算锁住；一次只加一个属性时不会触发，这正是旧 44 项测试漏掉它的原因。

### 2.2 `T-039`：支持「按需生成变体」的属性（`19.0.6.0.0`）

| 设计点 | 做法（关键决策） |
|---|---|
| 轴分类 | `_split_variant_conversion_lines()`：`always` = **展开轴**，`dynamic` = **固定轴**（钉住既有变体现在带的取值，没有则第一个取值） |
| 组合枚举 | **每条既有变体 × 各「立即」属性的取值组合**（按需轴的其它取值**永不预建**），仍过 Odoo 排除规则 + 去重。只有「立即」属性时结果与老版本**逐条一致**（46 项老用例零改动通过） |
| 新增变体 | `_create_variant_ids()` 对按需属性整段跳过新建 → 自己调 `_create_variant_conversion_missing_variants()` → Odoo 的 `_create_product_variant()`（销售配置器同款入口）；`_create_variant_conversion_combination()` 给「不生成变体」的属性行补占位取值以通过 `_is_combination_possible()` 校验（Odoo 建变体时会把它们丢掉） |
| 原生会丢变体时自己锚定 | 新增 `needs_anchoring`：某条既有变体缺某个**多取值**属性行的取值时，原生会把它的组合判成「不完整」而**删掉它** —— 这种情况即便不新增变体也走转换、用默认归属锚定（不弹窗） |
| 价格分离 | 带按需属性的产品**不做分离**（分离会拆走模板级记录并删除，之后订单期新建的变体就取不到价）→ 台账 `separate_variant_prices=False`，弹窗隐藏勾选框 |
| 组合数上限 | 带按需属性时 = `既有变体数 × 各「立即」属性有效取值数乘积`（按需轴不乘） |
| 保留的拦截 | **建产品**时带按需属性仍然拒绝（原生会建出「有属性、没变体」的产品），文案给出「先建产品、保存，再加属性」的出路 |
| 弹窗 | 预览接口新增 `dynamic`；弹窗多一行「按需轴的其它取值不会现在建变体」提示，并隐藏供应商价格勾选框 |

### 2.3 `T-040`：弹窗选项自动互换（`19.0.6.1.0`）

- 原来把「已被别的组合选走」的既有变体在下拉里**置灰**：换归属要「先腾位置、再选」两步，且用户看不出为什么点不了。
- 现在：**所有选项可选**；选中已被占用的既有变体时与占用行**自动互换**（新增纯函数 `applyOwnershipSelection()`；`onSelect()` 生成新 selection 赋回 `state.selection`，OWL 响应式刷新两行显示）。
- 不变量：任意时刻**每条既有变体只被一行占用** → `countUnassigned() == 0` 依然等价于「载荷合法」，`Confirm` 门槛不用改。
- 用户给的示例（单变体产品 → Black / White 两个组合，Black 初始占原变体，White 也选原变体）已作为验证用例固化。

### 2.4 边界核实（无版本变化，测试 45 → 46）

- **订单期变体完全在本模块之外**：配置器 → `sale.order.line` → `product.template._create_product_variant()` → `product.product.create()`，不经过 `product.template.write()` → 本模块**不拦也不接管**（无来源字段 / 台账 / 谱系，不做按谱系继承）；`T-039` 之后「之后再改属性」会走转换，那时新增的变体才有来源与继承。
- **另一条会丢变体的路**：非沙盒的 `product.template.attribute.line.create()`（其它模块 / 脚本）会自己调 `_create_variant_ids()`，对按需产品会把组合「不完整」的既有变体**直接删掉**（实测 2 条在用变体消失）——属性行守卫只覆盖「移走取值 / 删行」，**未覆盖「新增行」**（`T-017` 遗留，已记入模块 `AGENTS.md` → L2 P5 缺口 1）。

---

## 3. 横切归纳：本阶段问题的两个根因模式

| 模式 | 表现 | 本阶段的处置 |
|---|---|---|
| **模块自己的假设与 Odoo 原生行为不一致** | 「按需生成」属性下 `_create_variant_ids()` 不建变体、原生会删掉缺取值的既有变体；「组合数 == 变体数」不再成立 | 显式建模：轴分类 + `needs_anchoring` + 自己建缺失变体；把「原生会怎么干」写成代码注释与 L1 约束 |
| **Odoo 会「静默」造出反直觉状态** | 产品导入把新建属性设成 `dynamic`；按需产品的组合数 ≠ 变体数；`create()` 不报错却 0 变体 | 不假设用户知道：报错**点名对象 + 给可执行出路**；把「为什么是这个状态」写进 README「已知边界」，并给 `T-039` 这类真支持留出实现路径 |
| **「静默失效」比报错更难发现**（`product_image`，第 7 节） | `Images` 列绑的是图库计数 → 勾选后**没有图片也不报错**；改了 po 里**已有**译文 → `-u` 升级后中文界面仍是旧词、也不报错 | 用**可执行断言 / 显式刷新**兜住：列定义 + 数据绑定用例（含「必须绑 `image_128`」）、迁移定向刷 `arch_db` 术语，而不是靠「看起来对」 |

另外两条通用教训：

1. **报错文案也是功能**：只说「去改属性设置」而 Odoo 不允许改（属性已被产品使用）＝ 没有出路；必须给「按什么顺序做才能走通」。
2. **测试通过 ≠ 场景覆盖**：44 项测试漏掉「一次加两个属性」（只加一个属性能通过）与「订单期变体」；补测时**先在旧代码上复现同一条错**再收进用例。
3. **「改了已有译文」这一类改动，`-u` 不可信**（`product_image` 本轮实测）：po 导入只补齐缺失语种、不覆盖库里已有值 —— 根 `AGENTS.md` 4.8 第 9 条只把这条写在「应用列表元数据（`noupdate=True`）」名下，**本轮确认视图术语（`model_terms:ir.ui.view,arch_db`）同样适用**；处置要么写定向刷新迁移，要么升级后跑 `task i18n -- zh_CN <模块>`。
4. **「加一列」这种最小改动也要先确认列名与语义是否一致**：`Images` 这个名字与「图库计数」这个实现长期不符，直到有人真去勾选才发现 —— 列的 `string` 应当能被字段与 `widget` 兑现。

---

## 4. 经验教训

1. **线上报错先做「唯一性定位」**：文案在仓库里 grep 唯一 → 立刻确定是哪条边界，比按现象猜快得多（第 1 轮与第 2 轮都是这样定性的）。
2. **能反证才算锁住**：`19.0.5.3.2` 的回归用例与 `T-040` 的互换纯函数都用「跑一遍旧逻辑 / 一次性脚本」证明了它会失败或通过，而不是只看新代码绿了。
3. **边界的「出路」必须可执行**：凡是报错里写「请先去改 X」的，都要确认 X 在当前状态下真的改得动（本次第 1 轮就是反例）。
4. **按需（on demand）语义 ≠ 少建几个变体**：它的关键约束是「按需轴的其它取值永远不预建」，违反它会让「按需」名存实亡（本模块把这条写成测试断言）。
5. **纯函数是前端可测性的最低成本**：`buildOwnershipPayload()` / `countUnassigned()` / `applyOwnershipSelection()` 都不依赖 OWL，等仓库上 Hoot 单测时可零改动接入。

---

## 5. 后续建议

### 5.1 待办池现状（`TODO.md`）

- 待办池剩 **`T-026`**（补齐 po 里 `code:` 条目的运行期注释标记：本模块那 1 条已随 `T-039` 修掉，其余 6 个模块待做）与 **`T-028`**（manifest `description` 悬挂缩进触发 docutils 告警，同样 7 个模块待做）。
- `T-039`、`T-040` 已归档（见 `TODO.md` →「已归档」）。
- `T-038`（`product_image`：产品列表「Images」列改显主图）也已归档（2026-09-23，见第 7 节）。

### 5.2 未闭环的两条边界（已记档，未立项）

| 边界 | 影响 | 建议 |
|---|---|---|
| 订单期由 Odoo 自建的变体不带来源 / 继承 | 这类变体没有 `Variant Conversion` / `Derived From`，成本 / 体积 / 重量为空 | 若要补，接入点应选在「订单期创建」这条路（例如 `_create_product_variant()` 包装或 `_post_variant_conversion_hook` 之外的新钩子）；**不要**全局 hook `product.product.create` |
| 非沙盒的 `product.template.attribute.line.create()` 绕过守卫 | 对按需产品会把缺取值的既有变体**直接删掉** | 按 `T-017` 的手法给 `line.create()` 加同一套「会丢变体就拒绝」判定（沙盒 `create_product_product=False` 必须放行，否则产品导入会被拦） |

### 5.3 可选加固

- 前端纯函数上 **Hoot 单测**（`applyOwnershipSelection()` / `buildOwnershipPayload()` / `countUnassigned()`），把 `T-040` 的互换不变量固化进 CI。
- 给「一次加多个属性」「订单期变体」这两类场景在模块 `README.md` →「验证清单」里保留手工复验行（已在本次补齐）。
- 把「**任何**已有译文的 `msgstr` 改动都不会被 `-u` 覆盖」从根 `AGENTS.md` 4.8 第 9 条（现只写「应用列表元数据」）提升为 4.7 的通用提醒 —— 本轮 `product_image` 在视图术语上实测踩到同一坑（第 7 节、§4 经验 3）。

### 5.4 风险提示

- **前端改动必须 `-u` + 强浏览器刷新**（Ctrl+F5）：弹窗互换、按需提示、弹窗文案（含中文）都属于前端资源；没 `-u` 会表现为「点了保存没变化 / 还是旧文案」。
- **带按需属性的产品不做价格分离是刻意行为**：不要「顺手修」成默认分离，否则之后订单期新建的变体会取不到供应商价格。
- **建产品拦截只在 `create_product_product=True` 的路径生效**（产品导入等沙盒路径不受影响），别把它当成「动态产品整体不可创建」的保证。
- **不要按「组合数 == 变体数」去断言按需产品**：按需轴不展开，所以变体数可能少于「取值全组合数」——这是设计语义。

---

## 6. 交接清单

### 6.1 目标环境动作（按顺序执行）

```bash
# 1) 升级模块（一次覆盖本轮 4 个版本；含前端资源与视图，必须 -u）
-u product_variant_conversion

# 2) 需要中文界面时刷新一次译文（元数据条目 noupdate=True，正常升级不会覆盖）
task i18n -- zh_CN product_variant_conversion

# 3) 门禁（本地即可跑，确认仓库结构与 po 没问题）
task check
```

> 之前失败过的那次「一次加两个属性」的保存**没有写入任何数据**（转换在 savepoint 内，报错即整单回滚），升级后直接重做即可。

### 6.2 界面复验清单（目标环境）

| # | 场景 | 期望 |
|---|---|---|
| 1 | 给既有产品加一个「立即」属性（如 Color 两取值） | 保存时弹出归属确认框，默认归属正确，`Confirm` 在未分配完时不可点 |
| 2 | 弹窗里在第二行也选「原变体」 | 两行**自动互换**（第一行变「新建变体」、第二行变原变体），显示同步更新，`Confirm` 状态随之变化 |
| 3 | 单变体产品加两个属性并同时保存（一次加两个属性） | 转换正常完成，产品 chatter 出现一条 `Variant conversion: … (added attributes: A, B).` |
| 4 | 导入来的、属性为「按需生成」的产品 → 在表单里加一个「立即」属性 | 弹窗多一行「按需轴的其它取值不会现在建变体」提示、不显示供应商价格勾选框；确认后既有变体全保留，只多出「展开轴」的变体，**未被使用的按需取值不建变体** |
| 5 | 已有产品加一个**多取值**的「按需生成」属性 | 不弹窗、保存成功，原变体记录仍在（原生原本会删掉它） |
| 6 | 新建产品时直接带「按需生成」属性 | 保存被拦，报错点名属性并提示「先建产品、保存，再加该属性」 |
| 7 | 中文界面 | 弹窗说明 / 「在手 N」/ 报错文案均为中文（前端文案需强刷浏览器） |
| 8 | 台账与谱系 | 产品表单 **Conversions** 按钮可进台账；详情页谱系行数 = 变体数；带按需属性的产品台账 `Separate Variant Prices` 为否 |

### 6.3 改动文件地图（本阶段）

| 路径 | 职责 / 本阶段改动 |
|---|---|
| `product_variant_conversion/models/product_template.py` | `create()` 拦截（按需属性）、`_split_variant_conversion_lines()` / `_get_variant_conversion_fixed_values()`（轴分类与钉住）、`_get_variant_conversion_combinations()`（按需产品：每条既有变体 × 展开轴）、`_create_variant_conversion_missing_variants()` / `_create_variant_conversion_combination()`（自己建缺失变体）、`needs_anchoring` 判定、价格分离跳过、`_log_variant_conversion()` 多记录集修复、预览新增 `dynamic` |
| `product_variant_conversion/static/src/js/variant_conversion_dialog.js` | `applyOwnershipSelection()`（互换纯函数）、`onSelect()` 赋值新 selection、按需提示 getter、删除 `isVariantUsed()` |
| `product_variant_conversion/static/src/xml/variant_conversion_dialog.xml` | 去掉 `t-att-disabled`（选项全可选）、按需提示行、按需时隐藏价格勾选框、说明文案补一句互换 |
| `product_variant_conversion/tests/test_product_variant_conversion.py` | 47 项：新增按需产品只展开「立即」轴、加多取值按需属性不丢变体、`create` 拦截、沙盒放行、一次加两个属性的 chatter 回归、订单期变体边界 |
| `product_variant_conversion/i18n/zh_CN.po` | 删 2 条失效文案、改 2 条（建产品拦截 / 弹窗说明）、新增 1 条（按需提示）、补 1 条 `#. odoo-javascript` 标记（`T-026` 本模块部分） |
| `product_variant_conversion/__manifest__.py` | 版本 `19.0.5.3.0` → `19.0.6.1.0` |
| `product_variant_conversion/README.md` / `CHANGELOG.md` / `AGENTS.md` | 场景矩阵 S11/S11b、使用前提、被拒绝的改动、核心设计、数据流、价格分离、已知边界、后续迭代、验证清单；四个版本条目；L1 约束 18、L2 P3 陷阱 5、P4 互换约定、P5 矩阵与缺口 1/10 |
| 根 `README.md` / `AGENTS.md` / `TODO.md` | 模块一览表版本与状态、模块表描述（按需支持 / 互换）、`T-039` / `T-040` 归档、`T-026` 口径更新、文件结构块新增本报告 |
| 本报告 `STAGE_REPORT_2026-09-24.md` | 本阶段汇总与交接 |

### 6.4 常用命令速查

```bash
task check                                                            # 仓库门禁（po / XML / JS 语法 / TODO 结构）
task test -- product_variant_conversion                               # 47 项（只装 product）
task test -- product_variant_conversion,stock,sale_management --test-tags=/product_variant_conversion
task test -- product_variant_conversion,product_dimension --test-tags=/product_variant_conversion
task test -- product_variant_conversion,product_reference,product_card_view,sale_management \
      --test-tags=/product_variant_conversion,/product_reference,/product_card_view   # 57 项
task update -- product_variant_conversion                             # 升级（前端资源改动必须 -u）
task i18n -- zh_CN product_variant_conversion                         # 强制刷新中文译文
```

### 6.5 交付状态说明

- **已提交**：`4167303`（`19.0.5.3.1`）、`0d21c07`（`19.0.5.3.2`）。
- **未提交**（工作树内）：`19.0.6.0.0`（`T-039`）、`19.0.6.1.0`（`T-040`）、边界核实相关的测试与文档、
  以及本轮文档同步（根 `README.md` / `AGENTS.md`、`TODO.md`、本报告）。提交后工作树恢复干净。
- 「待目标环境验证」状态以根 `README.md` 模块一览表与模块 `README.md` →「验证清单」为准；本报告第 6.2 节是它们的可执行版本。
- `product_image`（下文第 7 节）的升级 / 复验动作见第 7.3、7.5 节。

---

## 7. 同期并行：`product_image` `T-038`（产品列表「Images」列改显主图）

> 与第 1~6 节的 `product_variant_conversion` 是**两条并行的工作流**（同一工作区、各自独立提交）。
> 本节给出目标 / 根因 / 改动 / 验证 / 复验清单；**权威细节**见模块
> [`product_image/CHANGELOG.md`](product_image/CHANGELOG.md) → `[19.0.2.6.5]` 与
> [`product_image/AGENTS.md`](product_image/AGENTS.md) →「开发复盘与关键经验（T-038）」（含操作时间线、
> 备选方案与取舍、坑点 7 条）。

### 7.1 目标与结论

**需求**：产品列表勾选「Images」列后要能看到产品图片（**仅主图**），且在「库存 / 产品」「销售 / 产品」
「采购 / 产品」三处都生效、显示 / 隐藏切换正常、数据绑定无误。

**结论**：原列**根本不是图片列** —— 它绑的是 `image_gallery_count`（`Integer` 计算字段 = 图库补充图条数，
**不含主图**），由默认整数控件渲染，所以勾选后只能看到数字（没有补充图的产品恒为 `0`）。现改为绑原生
`image_128`（`image.mixin`：`related="image_1920"` + `store=True` 的缩略 = 主图）+ `widget="image"`，
列仍是 `optional="hide"` 的可选只读列，位置仍在 `default_code` 之后。

| 项 | 内容 |
|---|---|
| 任务 | **`T-038`** ｜ 模块 `product_image` ｜ P1 |
| 版本 | `19.0.2.6.4` → **`19.0.2.6.5`**（+z 修复） |
| 提交 | `9748eeb fix(product_image): 产品列表 Images 列改显主图缩略`（2026-09-23 17:30:39 +0800，11 个文件，+319 / -16） |
| 实现与验证时间 | 2026-09-23 17:0x ~ 17:20（+0800；容器日志打印为同日 09:1x UTC） |
| 状态 | 已交付（已提交），**待目标环境界面复验** |

### 7.2 改动清单（文件 / 变更 / 原因）

| 文件 | 变更 | 原因 |
|---|---|---|
| `product_image/views/product_template_views.xml` | 列表列改 `<field name="image_128" string="Images" widget="image" options="{'size': [0, 48]}" optional="hide" readonly="1"/>` | 原列只显示数字；改绑主图缩略 |
| `product_image/i18n/zh_CN.po` | 列标题术语 `Images` 的 `msgstr`：「图片数」→「图片」 | 列语义变了，标题须跟着变 |
| `product_image/migrations/19.0.2.6.5/post-migration.py`（新增） | 定向设置该视图 `arch_db` 的 `{"zh_CN": {"Images": "图片"}}`；未装 zh_CN 跳过 | po 导入不覆盖已有译文，只跑 `-u` 会留着旧标题 |
| `product_image/tests/__init__.py` + `tests/test_product_list_image_column.py`（新增） | 7 项回归用例 | 三处入口 / 显示隐藏 / 仅主图绑定都要有回归 |
| `product_image/__manifest__.py` | `19.0.2.6.4` → `19.0.2.6.5` | 修复类（+z） |
| 模块三件套 + 根 `README.md` / `TODO.md` | 功能说明、版本条目、L1 约束 12、`T-038` 归档 | 仓库文档规范 |
| `product_image/models/product_template.py` | **未改** | `image_gallery_count` 字段保留（导出 / 分组 / 自建视图仍可用），只是不再作为列表列 |

**为什么只继承基础视图就能覆盖三处入口**：三个页面的列表视图 —— 库存 = 模型默认列表视图；销售 =
`account.product_template_list_view_sellable_inherit`；采购 = `account.product_template_list_view_purchasable_inherit`
—— 都是 `product.product_template_tree_view` 的后代（`ir.ui.view._get_combined_archs()` 会沿 `inherit_id`
上溯到根并收集**根的全部子视图**），而本模块的 `inherit_id` 一直指向该基础视图，因此三处自动同时生效。

**影响范围**：只影响 `product.template` 的列表视图（变体列表 / 看板 / 表单 / 图库独立视图不变）；无字段、
无数据结构、无权限变化；本模块 `depends` 仍只有 `product`，不新增任何可选模块依赖。

### 7.3 界面复验清单（目标环境）

| # | 场景 | 期望 |
|---|---|---|
| 1 | 库存 / 产品、销售 / 产品、采购 / 产品三处列表 → 右上角「可选列」勾选 **Images** | 有主图的产品显示主图缩略；无主图的产品显示占位图；**只有图库补充图的产品不显示图** |
| 2 | 同上，取消勾选 | 该列隐藏（可反复切换） |
| 3 | 中文界面（升级后由迁移刷新译文） | 列标题为「图片」；英文界面为 `Images` |
| 4 | 打开产品表单对照 | 列表显示的就是产品**主图**（`image_1920`），与表单头像一致 |

> 前置动作：`-u product_image`（含 `19.0.2.6.5` 迁移）→ 强刷一次浏览器 → 中英各看一遍。

### 7.4 改动文件地图（`product_image` 本轮）

| 路径 | 职责 / 本轮改动 |
|---|---|
| `product_image/views/product_template_views.xml` | 产品列表列由 `image_gallery_count` 改为 `image_128` + `widget="image"`（48px 高、可选、只读） |
| `product_image/i18n/zh_CN.po` | 列标题译文「图片数」→「图片」 |
| `product_image/migrations/19.0.2.6.5/post-migration.py` | 定向刷新该视图 `arch_db` 的 zh_CN 术语（幂等、未装 zh_CN 跳过） |
| `product_image/tests/test_product_list_image_column.py` | 7 项：列定义（image widget / `optional="hide"` / 只读 / 位于 `default_code` 之后）、不再是计数列、绑 `image_128`（`related == "image_1920"`）、仅主图数据绑定、三个动作**实际使用**的列表视图 |
| `product_image/AGENTS.md` / `README.md` / `CHANGELOG.md` | L1 约束 12、T-038 复盘、功能 / 验证 / 执行流程 / 异常处理 / 后续维护、版本条目 |

### 7.5 常用命令速查（`product_image`）

```bash
task test -- product_image                                                           # 7 项（3 项页面用例按配置 skip）
task test -- product_image,stock,sale_management,purchase --test-tags=/product_image # 7 项全部执行（无 skip）
task update -- product_image                                                         # 升级（含 19.0.2.6.5 定向译文迁移）
# 仅当「改了已有 msgstr 且没写迁移」时才需要下面这条；本轮已用迁移覆盖
task i18n -- zh_CN product_image
```

### 7.6 验证记录与遗留

| 验证 | 结果 |
|---|---|
| `task test -- product_image` | 7 项（3 项页面用例按配置 skip），0 failed / 0 error |
| `task test -- product_image,stock,sale_management,purchase --test-tags=/product_image` | 7 项**全部执行（无 skip）**，0 failed / 0 error |
| dev 库实测三个动作**实际使用**的列表视图 arch | 均为 `('Images', 'image', 'hide', '1')` |
| dev 库真跑升级（已装版本退回 `19.0.2.6.4` 再 `-u`） | 迁移 `[19.0.2.6.5>] post-migration` 执行；zh_CN 列标题「图片数」→「图片」，en_US 仍 `Images` |
| `task check` | 通过（未新增结构性问题） |

**遗留**：① 目标环境界面复验（第 7.3 节）；② `image_gallery_count` 字段保留但**已无 UI 入口**，日后若要
展示图库数量请另开列或在搜索 / 分组里用（不要与「图片」压在同一列，这正是本次缺陷的来源）。
