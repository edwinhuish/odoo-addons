# 变更日志

## [19.0.4.0.0] - 2026-09-23（**评估记录，当日回退，未发布**：曾试「产品编号直接用原生 default_code 那一列」）

> ⚠ **本版未发布、已全部回退**：实现完成后按要求回到 `base_reference` 方案（`19.0.3.0.0`）。
> 保留此条是因为「为什么不直接用原生 `default_code` 存产品编号」会被反复问到 —— 下面记录了
> 当时的实现、代价与回退原因（证据均为开发库实测 + Odoo 19 源码核对）。
> 类型：架构变更（未发布）｜ 涉及文件：`models/product_template.py` / `models/product_product.py` /
> `views/product_template_views.xml` / `hooks.py`（已删除）/ `__manifest__.py`（`uninstall_hook` 已撤）/
> `i18n/zh_CN.po` / `tests/test_base_reference.py`（已还原）

### 优化目标

`19.0.3.0.0` 用自有字段 `base_reference` 存产品编号，再把它「叠加」进模板级 `default_code`
的 compute —— 值是两份（字段 + 计算列），且必须靠一段额外的 compute/inverse 去对齐。
按要求改为：**产品编号就用 `product.template.default_code` 自己那一列**，不新增字段、
不改字段声明，并把「卸载后不留痕」做成显式钩子。

### 变更

1. **删除 `base_reference` 字段**及随之而来的全部代码（`_set_default_code()` 覆写、
   `_sync_single_variant_default_code()`、`create`/`write` 同步、视图里的 `Base Ref.` 输入框、
   列表列、搜索并入、i18n 条目）。
2. **`_compute_default_code()` 改为「保全」实现**：先 `flush_all()` 从库里读回模板级已存值，
   `super()`（原生单变体镜像 / 多变体赋空）之后再把值放回去 —— 单变体产品一行都不干预，
   多变体产品的**产品编号不会被重算清掉**（原生赋空是这一列唯一的「丢失」时机）。
3. **inverse 回归原生**：不复写 `_set_default_code()`。单变体产品它写回那条变体（原生行为），
   多变体产品它不落任何变体 —— 值留在这一列上（实测：写入 + flush 即落库，重算后仍在）。
4. **搜索**：`product.product._search_display_name()` 的并入项由 `base_reference` 改为
   `product_tmpl_id.default_code`（原生只查模板 name + 变体编号，多变体产品的产品编号在模板列里）；
   模板层不必额外并入（原生 `('default_code', …)` 本来就是这一列）。
5. **卸载清理**（新增 `hooks.py` + manifest `uninstall_hook`）：卸载前把多变体产品的模板级编号
   清空，回到原生状态（该列为空）。⚠ **卸载会丢掉这些产品编号** —— 「不遗留任何数据」的必然代价。
6. **存量数据**（`migrations/19.0.4.0.0/pre-migration.py`）：把旧字段 `base_reference` 的值搬进
   `default_code`（只处理多变体产品；单变体产品的模板列由原生镜像自己维护）。
   **必须 pre-migration**：模块里已无该字段，加载时那一列会被 `_auto_init` 删掉。
7. 契约测试重写（`tests/test_base_reference.py`）：单变体镜像（两个方向）、多变体编号只落模板列、
   **重算后仍在**（直接调 `_compute_default_code()` 验证）、产品层与变体层可搜到。

### 优化前后对比

| 场景 | 优化前（`19.0.3.0.0`） | 优化后（`19.0.4.0.0`） |
|------|------------------------|------------------------|
| 产品编号存在哪 | 自有字段 `base_reference`（+ 叠加进 `default_code` 的 compute，两份值） | **原生列 `product.template.default_code`**（一份值） |
| 字段声明 | 新增一个 `Char`（trigram 索引 + `copy=True`） | 不新增字段、不改字段声明 |
| 单变体写入 | `base_reference` 与变体编号「两处同值」，靠 `_sync_*` 双向兜底 | 完全原生镜像（改哪边都一样），本模块零代码 |
| 多变体写入 | 写 `base_reference`，再由 compute 叠进 `default_code` | 直接写 `default_code`（原生 inverse 不落变体，值留库里） |
| 多变体重算 | `default_code` 的 compute 里 `base_reference` 优先，天然有值 | `_compute_default_code()` 把已存值放回去，值不被清空 |
| 卸载 | 字段随模块删除（列被 drop），`default_code` 里的叠加值是否残留取决于是否被重算 | 字段元数据自动复原 + `uninstall_hook` 清掉写进原生列的产品编号 |

### 影响

- 产品编号从此只在**一处**（原生列），不再有「字段 + 计算列」两份值需要对齐；
- 产品表单 `Ref.`、产品列表 `[编号] 名称`、列表搜索、卡片视图（读原生字段）全部照旧可见；
- 单变体产品的行为与未装本模块时**完全一致**（本模块一行都不干预）；
- 未改写字段声明，因此不触碰原生单变体桥接（`display_name` / `create` 传播 / 单据口径不变）；
- 升级会搬运旧 `base_reference` 的值（多变体产品），不丢编号；卸载会清掉这些编号（有意为之）。

### 文档

- 模块 `AGENTS.md`（L1.3 重写为新契约 + 版本行）、`README.md`、本条目
- 根 `README.md` / `AGENTS.md` 版本行、`TODO.md`

### 验证记录

| 项 | 结果 |
|----|------|
| 多变体产品写入模板级编号 | 开发库实测：写入 + `flush_all()` 后列里就是新值 ✓ |
| 增删变体 / 改变体编号后仍保留 | 开发库实测：值未被清空（`_compute_default_code` 保全）✓ |
| 单变体产品 | 原生镜像不受影响（本模块跳过单变体记录）✓ |
| 自动化测试 / `task check` / 迁移 | 见本轮执行记录（`19.0.4.0.0` 相关） |
| 目标环境 | 表单 / 列表 / 卡片界面与卸载流程**待验证** |

---

## [19.0.3.0.0] - 2026-09-23（产品级编号叠加进原生 default_code + 两层参考号都可见）

> 修订日期：2026-09-23 ｜ 类型：架构 / 行为变更（+x）｜ 影响文件：`models/product_template.py` /
> `models/product_product.py` / `views/product_template_views.xml` / `tests/test_base_reference.py` /
> `i18n/zh_CN.po` / `__manifest__.py` / `migrations/19.0.3.0.0/post-migration.py`（新增）/
> `migrations/19.0.2.7.0/`（**删除**）

### 优化目标

`19.0.2.7.1` 的方案里，产品级编号 `base_reference` 是**独立于原生字段**的：只有本模块自己
（以及当时愿意探测它的 `product_card_view`）读得到，其它地方（产品列表、`[编号] 名称`、
Many2one、列表搜索）看不到多变体产品的产品编号。按新要求改为**把它叠加进原生
`default_code`**，并让产品级参考号层**在多变体产品上也有入口**：

1. **模板级 `default_code` 的 compute 优先取 `base_reference`** —— 产品编号从此在所有原生口径里可见，
   消费方（卡片视图等）只要读原生字段就行，不需要知道本模块存在；
2. **inverse 按变体数分流写** —— 单变体产品同时写 `base_reference` 与那条变体的 `default_code`（两处同值）；
   多变体产品只写 `base_reference`（各变体编号各归各的）；
3. **产品级参考号不再按变体数隐藏** —— 产品表单两种形态都显示 `Ref.` 与额外参考号入口，
   变体表单继续维护变体自己那一层。

### 变更

1. `ProductTemplate._compute_default_code()`：先 `super()`（保留原生单变体桥接），
   再对 `base_reference` 有值的记录覆盖 —— **产品编号优先级最高**（依赖声明含 `base_reference`）。
2. `ProductTemplate._set_default_code()`：`super()` 之后写 `base_reference`（多变体产品的唯一落点）。
   ⚠ 这里**只写一个字段**：实现时顺手写 `default_code` 会再次触发 inverse → `RecursionError`（实测踩到）。
3. 新增 `ProductTemplate._sync_single_variant_default_code()`（`create` / 写 `base_reference` 时收口：
   单变体产品两处同值），以及 `ProductProduct._sync_single_variant_base_reference()`（从变体侧改编号时
   反向同步产品级编号，**仅单变体产品**）。
4. 视图：删除按变体数隐藏的逻辑与独立的 `Base Ref.` 输入框（它就是 `Ref.` 里那个值），
   删除冗余的列表列与搜索分支（产品编号已被原生 `default_code` 覆盖）。
5. 迁移：删除 `migrations/19.0.2.7.0/`（它清掉单变体镜像值，与现在的「两处同值」相反），
   新增 `migrations/19.0.3.0.0/post-migration.py`：单变体产品按变体 `default_code` 回填 `base_reference`，
   并把存储列 `default_code` 对齐 `base_reference`（升级前那列是原生桥接算出来的，多变体时为空；
   列表搜索走存储列，不对齐就搜不到）。
6. 契约测试 `tests/test_base_reference.py` 重写为 6 项：单变体两处同值（两个方向）、
   多变体只写产品编号、两层互不驱动、compute 优先级、产品层 / 变体层都可搜到。
7. i18n：字段标签改「产品编号」、help 重写、删除 `Base Ref.` / `e.g. G001` 两条孤儿条目；
   manifest 摘要与描述同步（「两层各自独立且都可见」+「产品编号算进原生 Reference」）。

### 优化前后对比

| 场景 | 优化前（`19.0.2.7.1`） | 优化后（`19.0.3.0.0`） |
|------|------------------------|------------------------|
| 多变体产品的产品编号在哪 | 只在本模块的 `base_reference` 字段里 | `base_reference` **且**计算进原生 `default_code` |
| 产品列表 / `[编号] 名称` / Many2one / 列表搜索 | 多变体产品编号为空（要搜得靠本模块的搜索扩展） | 直接显示 / 命中产品编号（原生口径） |
| 第三方模块要显示产品编号 | 得探测 `base_reference` 字段 | 读原生 `default_code` 即可（零耦合） |
| 单变体产品改主编号 | 只改变体编号，产品侧为空 | **两处同值**（`base_reference` + 变体编号） |
| 多变体产品改主编号 | 只能改 `base_reference`（表单上是一个单独的 `Base Ref.` 框） | 改 `Ref.`（写 `base_reference`，表单只有一个编号框） |
| 产品级参考号（额外参考号）多变体时 | 整块隐藏（只能去变体表单维护变体那一层） | **两层都可见**（产品表单维护产品级，变体表单维护变体级） |

### 影响

- 产品编号在**所有原生口径**里可见：产品表单 `Ref.`、列表、`display_name` 前缀、Many2one 下拉、
  列表搜索、卡片视图（对方读 `default_code` 即可）—— 这是本次改动最大的可见变化
- 单变体产品两处编号保持同步（表单 / 变体侧 / 导入 / API 四条路径都有收口），
  多变体产品两层互不影响
- 升级会回填单变体产品的 `base_reference` 并对齐存储列；**多变体产品的产品编号仍需人工补录**
  （没有可自动推断的来源，缺它只影响编号那一栏）
- ⚠ 维护者注意：模板级 `default_code` 的 compute / inverse 已被本模块叠加，
  改这两个方法必须同步读 `AGENTS.md` → L1.3（含递归陷阱与写入收口的位置）

### 文档

- 模块 `AGENTS.md`（L1.1 两层都可见 / L1.3 重写 / 版本行 / 搜索约束说明）、`README.md`
  （功能概述、核心设计、模型字段、产品级编号一节、验证清单）、本条目
- 根 `README.md` 解耦矩阵与版本行、根 `AGENTS.md` 模块行、`TODO.md`（`T-035`）同步

### 验证记录

| 项 | 结果 |
|----|------|
| `task test -- product_reference`（只装本模块 + `product`） | 6 项 0 failed / 0 error ✓ |
| `task test -- product_variant_conversion,product_reference` | 48 项 0 failed / 0 error ✓ |
| `task test -- product_card_view,product_reference` | 10 项 0 failed / 0 error（卡片读原生字段就能拿到产品编号）✓ |
| 开发库升级 + 迁移回填 | 见本轮实测记录（单变体回填、存储列对齐）✓ |
| 目标环境 | 表单 / 列表 / 搜索 / 卡片界面**待验证** |

---

## [19.0.2.7.1] - 2026-09-22（补母型号契约测试 + 明确「只做提供方」的解耦边界）

> 修订日期：2026-09-22 ｜ 类型：文档 / 测试（+z）｜ 影响文件：`tests/`（**新增**）/
> `AGENTS.md` / `README.md` / `__manifest__.py`（**无源码逻辑、无数据、无 i18n 改动**）

### 优化目标

母型号 `base_reference` 是另外两个模块（`product_variant_conversion` / `product_card_view`）**可选消费**的
接口，但本模块此前**一个自动化用例都没有**，「谁在什么时候写它」的契约只写在文档里；
同时也没有明确写清「本模块不感知消费方」。本版把这两件事补齐。

### 变更

1. 新增 `tests/test_base_reference.py`（本模块首次带自动化用例），只钉**对外契约**：
   - 单变体产品写 `default_code` **不会**在产品侧留下副本（没有镜像）；
   - 两个字段互不驱动（写谁都不会顺手改另一个，单变体 / 多变体各验一遍）；
   - 母型号可被搜索：产品与变体都能在 `display_name` 搜索里按母型号命中。
   转换行为（什么时候写入）不在这里测 —— 那是 `product_variant_conversion` 的职责。
2. 测试建产品的写法固定为「属性行放进 `create()`」并注明原因：`product_variant_conversion` 装了之后会
   拦截「写 `attribute_line_ids`」的保存（要求确认变体归属），`create` 不受拦截 —— 本模块的测试
   不该被另一个模块的可选行为绊住（这是审计时真实踩到的坑）。
3. 文档补「与其它扩展的边界（可选集成）」：本模块**不依赖也不感知**消费方，卸载它们不影响本模块；
   反过来**缺 `product_variant_conversion` 时母型号不会自动产生**（需人工补录）。

### 影响

- 无行为变化、无数据结构变化、无迁移
- 测试 **0 → 4 项**（本模块首次带自动化用例），在「单装」「三模块同装」两种环境下均通过

### 文档

- 模块 `README.md` → 新增「与其它扩展的边界（可选集成）」；`AGENTS.md` → L1.3 补「只做提供方、
  不感知消费方」约束与测试要求
- 根 `README.md` 新增「扩展解耦矩阵」；`TODO.md`（`T-034`）

### 验证记录

| 跑法 | 结果 |
|------|------|
| `task test -- product_reference --test-tags=/product_reference`（只装本模块 + `product`） | 4 项 0 failed / 0 error ✓ |
| `task test -- product_variant_conversion,product_reference,product_card_view`（三模块同装） | 54 项 0 failed / 0 error（本模块 4 项在其中）✓ |

---

## [19.0.2.7.0] - 2026-09-22（母型号写入策略：单变体只写变体，转多变体时上移）

> 修订日期：2026-09-22 ｜ 类型：功能新增 / 行为调整（+y）｜ 影响文件：`models/product_template.py` /
> `models/product_product.py` / `__manifest__.py` / `i18n/zh_CN.po` /
> `migrations/19.0.2.7.0/post-migration.py`（新增）、`migrations/19.0.2.6.0/`（**删除**）

### 优化目标

`19.0.2.6.0` 让单变体产品的编号**同时**写进变体的 `default_code` 与产品的 `base_reference`
（两处同值，靠 `_sync_base_reference_vals` + `_sync_single_variant_base_reference` 双向维持）。
同一份数据写两处意味着**只要有一条写入路径漏掉就会长期不一致**（产品表单 / 变体表单 / 变体列表 /
导入 / 外部集成 / SQL 改数据），而这类偏差不会报错、只能靠人工比对发现。本版把编号收敛成**单一真值**。

### 变更

1. **删掉单变体镜像写入**：移除 `product_template._sync_base_reference_vals()` 与
   其 `create` / `write` 挂钩，同时移除 `product_product._sync_single_variant_base_reference()`
   与变体 `write` 里的调用 —— 单变体产品的编号**只写变体的 `default_code`**，
   产品侧 `base_reference` 保持为空。
2. **母型号改为「转换时上移」**：`base_reference` 只有两个写入时机 ——
   ① 多变体产品在产品表单 `Base Ref.` 里维护；② 单变体 → 多变体时由
   `product_variant_conversion` 把原变体的编号覆盖式上移（见该模块 `19.0.5.2.0`）。
3. **收尾清理旧镜像值**（`migrations/19.0.2.7.0/post-migration.py`）：把 `19.0.2.6.0` 留在
   **单变体产品**上的 `base_reference`（值恰好等于该变体 `default_code`）置空；多变体产品的母型号不动。
   同时**删除** `migrations/19.0.2.6.0/`（回填已不再是期望行为，留着会在新版上反复写入又清掉）。
4. **字段 help 与应用列表描述同步**：`base_reference` 的 help 不再写「单变体产品上与内部参考号一致」，
   改为「单变体产品转为多变体时写入」；manifest `description` 与 `i18n/zh_CN.po` 的
   `help:` / `description:` 条目同步（`summary` 不变）。

### 影响

- 单变体产品的编号只有一处（变体），任何写入路径都不会再出现「两处不一致」；产品列表 / 卡片上
  单变体产品的编号仍与以前一致（读的本来就是变体编号）
- 升级会清掉单变体产品上的镜像值（本模块旧版本的产物），**变体上的编号一个字节不动**；
  多变体产品的母型号不受影响
- 行为变化：`product.template.write({"base_reference": ...})` 不再自动改写 `default_code`，
  反之亦然 —— 两个字段从此各管一层
- 无数据结构变化（字段已在 `19.0.2.6.0` 建好）；迁移只清冗余镜像列

### 文档

- 模块 `AGENTS.md`（L1.3 重写为「单一真值、不做镜像」+ 版本行）、`README.md`
  （母型号节重写为「编号写在哪」表 + 新增「单一真值、不做镜像」设计点 + 验证清单更新）、本条目
- `19.0.2.6.0` 条目已加注：其第 2 点（单变体镜像写入）被本版替换
- 根 `README.md` / `AGENTS.md` 版本行、仓库 `TODO.md`（`T-033`）同步

### 验证记录

| 项 | 结果 |
|----|------|
| `task test -- product_variant_conversion,product_reference` | 45 项 0 failed / 0 error（含改写后的两条母型号用例）✓ |
| `task test -- product_variant_conversion`（未装本模块） | 45 项 0 failed / 0 error，两条用例按预期 skip ✓ |
| 开发库升级 | 日志 `cleared the mirrored base_reference of 22 single-variant product(s)`，升级后单变体产品 `base_reference` 残留 **0** 条 ✓ |
| 多变体产品母型号未被误清 | 6 条多变体模板母型号计数仍为 0（升级前也是 0，无一条被本次清理误伤）✓ |
| 中文标签 / help 落库 | 标签 `母型号`，help 已更新为「单变体产品不写这个字段……」✓ |
| 应用列表元数据一致性（AGENTS 4.6 校验） | 通过 ✓ |
| 单/多变体表单可见性、搜 `G001`、卡片显示 | **目标环境待验证** |

---

## [19.0.2.6.0] - 2026-09-22（新功能：产品母型号 base_reference）

> 修订日期：2026-09-22 ｜ 类型：功能新增（+y）｜ 影响文件：`models/product_template.py` /
> `models/product_product.py` / `views/product_template_views.xml` / `i18n/zh_CN.po` /
> `__manifest__.py` / `migrations/19.0.2.6.0/post-migration.py`
>
> ⚠ **本条的第 2、3 点已被 `19.0.2.7.0` 替换**：单变体产品不再镜像写 `base_reference`，
> 改为「转多变体时上移」；`19.0.2.6.0` 的回填迁移已删除，改由 `19.0.2.7.0` 清理旧镜像值。
> 字段 / 视图 / 搜索 / 卡片部分不变。

### 变更

1. **新增产品母型号 `product.template.base_reference`**（`Char` + trigram 索引 + `copy=True`）：
   多变体产品的产品型号（`G001` 对应 `G001-WT` / `G001-BK`）终于有地方存。
   原生 `default_code` 是 `product.product` 的自有存储字段，模板侧在多变体时只是「读出空、写入不落任何变体」
   的桥接（`_compute_template_field_from_variant_field()`），因此**不复用也不改写它**。
2. **单变体产品：型号同时落在两处**（`_sync_base_reference_vals`）。产品 `create` / `write` 里
   把 `default_code` 与 `base_reference` 写进**同一份 vals**（一次写库、不会二次触发同步、也不会循环）；
   变体侧直接改编号（变体表单 / 变体列表 / 变体导入）由
   `product.product._sync_single_variant_base_reference()` 补同步，且**只在单变体时**同步。
3. **多变体产品：两个字段互不代表对方**，不做镜像 —— 镜像会把产品母型号误改成某条变体的编号。
4. **视图按变体数分流**（`views/product_template_views.xml`）：单变体只显示 `Ref.`（原生 `default_code`
   编辑器 + 额外参考号入口），多变体只显示 `Base Ref.`（母型号）。原先**整块**隐藏的
   `div[name='product_reference']` 改为元素级 `invisible`，否则多变体产品的母型号输入框会被一起藏掉。
5. **搜索并入母型号**：模板 `_search_display_name`、变体 `_search_display_name`（经 `_inherits` 委托）、
   搜索视图 `filter_domain`（顶部搜索框 + 独立「Reference」搜索项）三处。
   多变体产品的模板级 `default_code` 是空的，不并入就等于「搜 `G001` 找不到产品 / 订单行选不到产品」。
6. **产品列表新增 `Base Reference` 列**（列选择器里默认隐藏）。
7. **存量数据回填**（`migrations/19.0.2.6.0/post-migration.py`）：单变体产品按变体的 `default_code`
   回填母型号（这正是新写法的既成结果，不是启发式猜测）；多变体产品没有可回填的值（模板级 `default_code`
   一直是空），保持空、由人工补录。**必须放 post-migration**：新列要到模型加载（`_auto_init`）之后才存在。
8. **应用列表元数据同步**：manifest `summary` / `description` 增补母型号说明，`i18n/zh_CN.po` 的
   `summary:` / `description:` 条目同步（含新增的字段标签、help、`Base Ref.`、`e.g. G001` 四条译文）。

### 影响

- 多变体产品在产品表单上有了可维护的产品型号，并能在 Products 列表 / Many2one 下拉 / 销售订单行等
  选产品处按母型号搜到；卡片视图（装了 `product_card_view` 时）也能显示它
- 单变体产品对「只填过 `Ref.`」的用户完全无感：`product.product.default_code` 的口径不变，
  区别只是产品上多了一份同值镜像（存的是同一个值，没有第二处真值）
- 升级会新增一列并回填单变体产品，**不需要**手工改数据；多变体产品的母型号需人工补录一次
- 未改写任何原生字段语义、未改原生桥接行为
- 新增可选协同：`product_variant_conversion` 转多变体时会把母型号留在产品上、清空原变体编号
  （见该模块 `19.0.5.1.0`）

### 文档

- 模块 `README.md`（功能概述 / 核心设计表 / 模型字段表 / 新增「母型号 Base Reference」节 / 验证清单）、
  `AGENTS.md`（命名语义 + 新增 L1.3 + 搜索约束补充）、本条目
- 根 `README.md` / `AGENTS.md` 模块版本行同步；仓库 `TODO.md`：`T-033` 落地 → 归档

### 验证记录

| 项 | 结果 |
|----|------|
| `task test -- product_variant_conversion,product_reference` | 45 项用例 0 failed / 0 error（本模块无自带用例，跑的是跨模块协同）✓ |
| 开发库升级（`task update -- product_reference product_variant_conversion product_card_view`） | 升级成功；迁移日志 `backfilled base_reference for 22 single-variant product(s)` ✓ |
| 回填一致性（SQL 核对） | 22 条单变体产品 **22 条** `base_reference = 该变体 default_code`；6 条多变体模板 `base_reference` 全为空（待人工补录）✓ |
| 中文标签落库 | `ir_model_fields.field_description->>'zh_CN'` = `母型号` ✓ |
| 应用列表元数据一致性（AGENTS 4.6 校验） | 通过（`summary` / `description` / `shortdesc` 与 manifest 逐字符一致）✓ |
| 描述 RST 渲染 | 与改动前一致（原有告警未增加，新增条目正常渲染为列表项）✓ |
| 单/多变体表单可见性、搜 `G001`、卡片显示 | **目标环境待验证**（清单见 README「验证清单」） |

---

## [19.0.2.5.3] - 2026-09-22（修复：权限硬编码了可选模块 sale 的用户组）

### 变更

- **删掉 `security/ir.model.access.csv` 里 `sales_team.group_sale_manager` 那一行**：本模块 `depends` 只有
  `product`，却在数据文件里引用 `sales_team`（`sale` / `sale_management` 才带进来的模块）的用户组 ——
  在**没装 `sale`** 的库上安装会直接失败：
  `No matching record found for external id 'sales_team.group_sale_manager' in field 'Group'`。
- **判定依据（为什么删而不是换组）**：删掉的那行给的是 `1,1,1,1`，与保留的 `base.group_user` 行**完全相同**；
  而 `sales_team.group_sale_manager` 的隐含链是
  `group_sale_manager → group_sale_salesman_all_leads → group_sale_salesman → base.group_user`，
  即销售经理本来就是内部用户，已经被 `base.group_user` 那行覆盖 —— 该行**一点权限都没多给**，
  纯属冗余。删除后权限模型完全等价，且不再依赖任何可选模块。

### 影响

- 权限行为不变（内部用户对本模块模型仍有完整读写权限）；模块现在可单独安装（无需 `sale`）
- 升级时 Odoo 会自动清理该行对应的 `ir.model.access` 记录（实测开发库中旧记录已消失）
- 无数据结构变化、无迁移

### 文档

- 模块 `README.md` →「依赖」：把原先的「已知问题」改成权限模型说明（只用核心组）
- 模块 `AGENTS.md` → L1 新增第 3 条「禁止硬编码可选模块的用户组」
- 仓库 `.dev/scripts/check_repo.py`：新增「权限 / 视图里引用的用户组必须来自 `base` 或已声明依赖」检查，
  用已知坏数据自证会报错后才入库

### 验证记录

| 项 | 结果 |
|----|------|
| `task test -- product_reference`（**不装 `sale`**） | 30 个模块加载成功、0 failed（此前直接安装失败）✓ |
| 权限记录 | 库里只剩 `..._user` → `base.group_user` 一行，旧的 manager 行被自动清理 ✓ |
| `task check` | 通过（新增的用户组检查无告警）✓ |

---

## [19.0.2.5.2] - 2026-09-22（修复：主变体表单在编产品级共享行）

### 变更

- **主变体表单（`product.product_normal_form_view`）的参考号编辑器改为维护变体专属行**：
  该视图里 `default_code` 的 widget 补上
  `options="{'lines_field': 'variant_reference_code_line_ids'}"`，隐藏的元数据 One2many
  同步换成 `variant_reference_code_line_ids`。
- **根因**：变体侧有两张表单 —— 「变体独立编辑表单」（`product_variant_easy_edit_view`）早已带了
  `lines_field`（维护变体专属行），而**主变体表单漏写**这个 option → widget 回落到该视图里那个隐藏的
  `reference_code_line_ids`（**产品级共享行**）。于是多变体产品的每个变体打开主表单时，编辑的都是
  同一组共享参考号，与 L1「多变体不共用」以及模块 README「视图」节的描述不一致（实现与文档不符）。

### 影响

- 打开任一变体的主表单，「+」弹窗管理的是**该变体自己的**参考号，与产品表单的共享行互不干扰
- 单变体产品从变体表单录入的参考号会落在变体级（产品表单看到的是产品级共享行）—— 这正是模块既有的
  两层语义，与「变体独立编辑表单」保持一致
- 无数据结构变化、无迁移；已有数据不动（此前误挂在产品级上的行，可用
  `product_variant_conversion` 的转换交接，或手工改归属）

### 文档

- 模块 `README.md`：视图节说明主变体表单同样维护变体专属行；验证清单同步
- 模块 `AGENTS.md`：L1 1.1 补「变体侧任何表单都必须显式指定 `lines_field`」这条硬要求

### 遗留（另行登记）

- 权限 CSV 引用了 `sales_team.group_sale_manager`，而 `depends` 只有 `product` ——
  在没有 `sale` 的库里安装本模块会直接失败（`No matching record found for external id
  'sales_team.group_sale_manager' in field 'Group'`）。已登记 `TODO.md` → `T-027`。

### 验证记录

| 项 | 结果 |
|----|------|
| 视图 arch | `ir_ui_view.arch_db->>'en_US' LIKE '%variant_reference_code_line_ids%'` → `t` ✓ |
| 与快速编辑表单一致 | 两张变体表单的 widget 都指向变体专属行 ✓ |
| 回归 | `product_variant_conversion` 连同本模块跑 41 项测试 0 failed ✓ |

---

## [19.0.2.5.1] - 2026-09-09（验收通过）

### 变更（i18n / 文档）

- **应用列表（Apps）中文化**：`i18n/zh_CN.po` 补充「应用列表元数据」译文，中文环境下应用卡片与详情页显示中文模块名 / 摘要 / 描述。
  - `model:ir.module.module,shortdesc:base.module_product_reference` → 「产品参考号」（并入已有 `Product References` 条目，作为多引用，避免重复 `msgid`）
  - `model:ir.module.module,summary:base.module_product_reference`：摘要整句译文
  - `model:ir.module.module,description:base.module_product_reference`：`description` 整段译文（`translate=True` 整值翻译，`msgid` 与 `textwrap.dedent(manifest["description"])` 逐字符一致）
  - `model:ir.module.category,name:base.module_category_inventory_product` → 「产品」（`Inventory/Product` 的自定义子分类，官方 `base` 无译文；并入已有 `Product` 条目）

### 影响

- 纯译文改动，无模型 / 字段 / 视图 / 权限变更，**无需迁移脚本**。
- `odoo -d <db> -u product_reference --stop-after-init` 升级后，中文环境「应用」列表显示中文名称 / 摘要 / 描述与中文分类；英文环境不变。
- 这些记录归属 `base`（xmlid `base.module_*` / `base.module_category_*`、`noupdate=True`）：po 导入只补齐缺失语种，**不覆盖库中已有的 `zh_CN` 值**；后续改译文的强制刷新方式见根 `AGENTS.md` 4.8。

### 文档

- 同步 `__manifest__.py`（版本 19.0.2.5.1）、`README.md`（国际化节）、`AGENTS.md`（当前版本 + i18n 约束）、根 `README.md` / `AGENTS.md` / `TODO.md`。
- 规范沉淀：根 `AGENTS.md` 新增 4.8「应用列表元数据（模块名 / 摘要 / 描述 / 分类）翻译规范」，并更正 4.1 中「写在自研模块 po 里匹配不到、无效果」的错误说法。

### 验收记录（T-013）

- 验收日期：2026-09-09
- 验收环境：目标 Odoo 19 部署环境（已安装「简体中文 (zh_CN)」）
- 验收结果：6 项验收标准全部通过（中英文各验一遍）
  - [x] `odoo -d <db> -u product_reference --stop-after-init` 升级无报错
  - [x] 中文「应用」列表：卡片标题显示「产品参考号」，摘要为中文
  - [x] 中文「应用」详情：描述整段为中文
  - [x] 中文「应用」左侧分类：显示「库存 / 产品」——父级 `Inventory` 沿用官方译文，自定义段 `Product` → 「产品」由本模块提供（并入已有 `Product` 条目，避免重复 `msgid`）
  - [x] 切回英文界面：名称 / 摘要 / 描述回到 `__manifest__.py` 的英文原文
  - [x] 仓库内自校验通过：无重复 `msgid`；`shortdesc` / `summary` / `description` 的 `msgid` 与 manifest 逐字符一致；源码无残留中文界面文本（脚本见根 `AGENTS.md` 4.6）

> 后续若只改译文（`msgstr`），这些记录是 `noupdate=True`，`-u` 不会覆盖库里已有的 `zh_CN`，
> 需按根 `AGENTS.md` 4.8 第 9 条用 `TranslationImporter.save(force_overwrite=True)` 或先清 `zh_CN` key 再升级。

---

## [19.0.2.5.0] - 2026-09-08（验收通过）

### 变更（产品列表可按变体参考号搜索）

- **产品级搜索并入变体参考号**：`product.template._search_display_name` 在
  `reference_code_index` 之外并入 `product_variant_ids.variant_reference_code_index`
  （`any` 条件），产品列表 / Many2one 下拉 / 快速搜索输入任一变体的参考号都能找到该产品。
- **搜索视图同步**：顶部搜索框与独立「参考号」搜索项的 `filter_domain` 均加入变体参考号路径
  `('product_variant_ids.variant_reference_code_index', 'ilike', self)`。
- **命中提示覆盖变体参考号**：`_extract_reference_code_search_terms` 支持
  `('product_variant_ids', 'any', [...])` 子域与 `Domain` 对象递归；`web_search_read`
  命中判断同时比对产品拼串与其变体拼串（新增 `_variant_reference_indexes_by_template()`
  一次取回，避免逐记录查询）。
- 变体参考号仍**不**写回 `reference_code_index`（多变体产品参考号不共用），只是在搜索时纳入。

### 影响

- 在变体里新增的参考号，现在能在 Products 列表 / 选产品时按该参考号命中，
  命中时 `name` 同样附加「（命中参考号：xxx）」。
- 变体级搜索不变（本变体参考号 + 所属产品的共享参考号）。
- 仅需 `-u` 升级（无数据结构变更），升级后强刷浏览器。

### 文档

- 同步更新 `__manifest__.py`（版本与 `description`）、`README.md`（搜索与验证清单）、
  `AGENTS.md`（L1 搜索约束与 T-011 复盘）、根 `README.md` 与根 `TODO.md`（T-011 完成归档）。

### 验收清单（目标环境，已于 2026-09-08 随 T-011 验收通过）

1. `odoo -d <db> -u product_reference --stop-after-init` 升级不报错
2. 在多变体产品的某个变体里加 `ABC-123` → Products 搜索框输入 `ABC-123` 能搜到该产品
3. 搜索结果 `name` 附加「（命中参考号：ABC-123）」（中英各验一遍）
4. 独立「参考号」搜索项同样能命中变体参考号
5. 选产品（Many2one 指向 `product.template`）输入变体参考号能命中
6. 回归：产品共享参考号 / 名称 / barcode 搜索不受影响；否定条件（`not ilike`）不误伤

---

## [19.0.2.4.0] - 2026-09-08（验收通过，随 `19.0.2.5.0` 一并验收）

### 变更（多变体产品的参考号不共用）

- **参考号行新增变体归属**：`product.reference.code` 增加 `product_id`（产品变体），
  `product_tmpl_id` 改为非必填；新增 `_check_single_owner`（产品 / 变体二选一，不可双归属）
  与 `UNIQUE(product_id, reference_code)`；`_check_reference_code_unique_per_template`
  改为按主人去重的 `_check_reference_code_unique_per_owner`。
- **新增 `product.product` 扩展**（`models/product_product.py`）：`variant_reference_code_line_ids`
  （变体专属行）、`variant_reference_code_index`（trigram 索引）、`_sync_variant_reference_index()`；
  `_search_display_name` 并入变体参考号与其产品的共享参考号；`web_search_read` 命中变体参考号时
  同样在 `name` 后附加「（命中参考号：xxx）」。
- **widget 按主人分流**：产品模板表单 → `reference_code_line_ids`（共享行），
  变体表单 → `variant_reference_code_line_ids`（变体专属行，arch 用
  `options="{'lines_field': ...}"` 显式指定）。
- **多变体产品的模板表单整块隐藏**：Reference 区域 `invisible="product_variant_count > 1"`，
  参考号只在各变体上维护。
- **子行创建剥离模板默认**：`product.product.create/write` 对变体参考号行的 `(0, 0, ...)` 命令
  强制 `product_tmpl_id=False`，避免变体 action context 的 `default_product_tmpl_id`
  造成「同时归属产品与变体」报错（与 product_image 变体图库同一坑）。
- **i18n / 文档同步**。

### 影响

- 历史数据不受影响：已有的参考号行都只有 `product_tmpl_id`（产品级共享），`product_id` 为空，
  无需迁移脚本（新增列 + trigram 索引 + 唯一约束由 ORM 自动创建）。
- 多变体产品：产品表单不再显示 Reference 区域；每个变体各自维护一组参考号，互不共用。
- 单变体 / 无变体产品：产品表单维护共享行（原行为不变）；变体表单可另外维护变体专属行。
- 搜索：变体（Many2one 指向 `product.product`、变体列表）可按本变体参考号或其所属产品的共享
  参考号命中；产品级搜索仍只走 `reference_code_index`（不含变体专属参考号）。
- 升级后必须强刷浏览器。

### 验收清单（目标环境，已于 2026-09-08 随 T-011 验收通过）

1. `odoo -d <db> -u product_reference --stop-after-init` 升级不报错（新增列 / 索引 / 唯一约束自动创建）
2. 多变体产品：产品表单不显示 Reference 区域；打开某变体可维护自己的参考号
3. 变体 A 新增的参考号不会出现在变体 B（两套独立）
4. 单变体 / 无变体产品：产品表单维护共享行正常；变体表单维护变体行正常
5. 变体表单新增参考号行不报「不能同时归属产品与变体」
6. 搜索：订单行选产品（Many2one 指向变体）输入变体参考号 / 产品共享参考号都能命中
7. 变体列表按参考号搜索命中时 `name` 附加「（命中参考号：xxx）」
8. 删除变体 / 产品：对应参考号行级联清理，索引按剩余行重算

> 以上 8 项已于 2026-09-08 在目标环境验收通过，见下方「验收记录（T-011）」。

### 验收记录（T-011）

- 验收日期：2026-09-08
- 验收环境：目标 Odoo 19 部署环境
- 落地版本：`19.0.2.5.0`（含 `19.0.2.3.0` 界面改造、`19.0.2.4.0` 多变体参考号归属、`19.0.2.5.0` 变体参考号纳入产品搜索）
- 验收结果：14 项验收标准全部通过
  - [x] `odoo -d <db> -u product_reference --stop-after-init` 升级不报错（升级后强刷浏览器）
  - [x] 产品模板表单：产品名下方出现 `Ref.` 标签 + Reference 输入框，可编辑并保存；常规信息页不再重复出现 Reference
  - [x] 变体主表单 / 变体独立编辑表单：同样出现编辑器；常规信息 / Codes 组不再重复出现 Reference
  - [x] 输入框内右端「+」打开管理弹窗：新增 / 改值 / 改类型 / 停用 / 删除 / 上移下移均正常，关闭后徽标数量正确
  - [x] 标签 `Ref.`：中英界面都显示 `Ref.`（不随语言变化）
  - [x] 新建未保存产品：先加参考号再保存产品，保存后参考号落库且索引已同步
  - [x] 徽标 tooltip：悬停「+N」徽标显示参考号清单（中英双语各验一遍）
  - [x] 只读态：只显示 Reference 文本与徽标 tooltip
  - [x] 回归：按参考号搜索 / Many2one 命中提示 / 同产品去重 / 删除产品级联清理均正常
  - [x] 多变体产品：产品表单整块隐藏；变体 A 加的参考号不出现在变体 B
  - [x] 变体表单新增参考号行不报「不能同时归属产品与变体」
  - [x] 变体搜索：订单行选产品输入变体参考号 / 产品共享参考号都能命中；变体列表命中时 name 附加提示
  - [x] 删除变体 / 产品：对应参考号行级联清理，索引按剩余行重算
  - [x] 在变体里加 `ABC-123`：Products 搜索框 / 独立「参考号」搜索项 / Many2one 都能命中，并附加「（命中参考号：ABC-123）」

### 交付记录（T-011，2026-09-08）

- **完成日期 / 落地版本**：2026-09-08，`19.0.2.5.0`。
- **需求**：移除产品表单「参考号（References）」页签；原生 `Reference`（`default_code`）输入框移到产品名下方（模板 + 变体表单，标签 `Ref.`），输入框内右端「+」以弹窗管理额外参考号；存在额外参考号时悬停徽标显示清单 tooltip；多变体产品的参考号不共用（各变体维护自己的一份）。
- **实现要点**：
  - 视图：继承 `product.product_template_form_view`（模板）、`product.product_normal_form_view` 与 `product.product_variant_easy_edit_view`（变体）；多处原生 Reference 隐藏避免重复。
  - 前端：字段 widget `product_reference_editor`（复用原生 `CharField`）+ 管理弹窗（顶层 `main_components` overlay）+ `data-tooltip-template` / `data-tooltip-info` tooltip；改动挂表单 record，随保存提交。
  - 模型：参考号行归属二选一（`product_tmpl_id` / `product_id`），变体侧新增 `variant_reference_code_line_ids` 与 `variant_reference_code_index`（trigram）；产品与变体两侧 `_search_display_name` / `web_search_read` 互覆盖。
- **验收记录**：见上方「验收记录（T-011）」。
- **异常与后续维护**：
  - 前端资源改动后必须 `-u` 升级并强刷浏览器，否则看不到新交互与新译文。
  - 变体参考号不写回产品 `reference_code_index`；索引与行不一致时在 shell 执行
    `env['product.product'].search([])._sync_variant_reference_index()`。
  - 「变体里加的参考号在 Products 搜不到」属搜索覆盖问题，检查搜索视图 `filter_domain`
    是否含 `product_variant_ids.variant_reference_code_index`（`19.0.2.5.0` 已修）。
  - 变体子行双归属由 `product.product.create/write` 剥离 `default_product_tmpl_id` 兜底，勿删。
  - 新增产品表单入口时需同步：挂 widget（变体用 `options.lines_field`）、声明不可见 One2many、
    隐藏该表单里重复的原生 Reference。
- **遗留**：无。

---

## [19.0.2.3.0] - 2026-09-08（验收通过，随 `19.0.2.5.0` 一并验收）

### 变更（界面改造：移除「参考号」页，Reference 上移到产品名称下方）

- **移除产品表单的「参考号（References）」页**：额外参考号不再以页签内 One2many 列表呈现，
  改为「产品名称下方 Reference 输入框 + 右侧「+」弹窗管理」，更贴近 SOHO「少点几下」的习惯。
- **原生 Reference 输入框移到产品名称下方**：产品模板表单与产品变体表单（变体主表单
  `product.product.form` 与变体独立编辑表单 `product_variant_easy_edit_view`）的 `oe_title` 内、
  产品名下方放置 Odoo 原生 `default_code`；输入框前标签固定为 `Ref.`
  （中文界面同样显示 `Ref.`，不做本地化翻译）；复用原生 `CharField` 组件渲染，
  编辑 / dirty / 校验体验与原生一致。
- **输入框内右端「+」按钮 → 额外参考号管理弹窗**：「+」内置在输入框右端（外层套原生 `.o_input`，
  嵌套 input 自动去边框），点击打开弹窗，列表式维护（参考号 / 类型 / 启用 / 备注 / 上移下移 / 删除），
  改动作用在产品表单 record 上，点产品「保存」才入库（未保存的新产品也能先录入参考号）；
  弹窗挂顶层 overlay（`main_components`），与表单渲染树解耦，不闪烁。
- **数量徽标 + tooltip**：产品存在启用中的额外参考号时显示「+N」徽标，悬停徽标弹出参考号清单
  （Odoo 原生 `data-tooltip-template` + `data-tooltip-info`）。
- **多变体模板**：模板级 Reference 由各变体维护，输入框位置显示提示文本，管理入口与徽标保留。
- **隐藏重复的原生 Reference**：常规信息页分类栏（模板 `product_template_only_form_view`、变体主表单
  `product_normal_form_view`）与变体独立编辑表单 Codes 组的原生 `default_code` 均隐藏。
- **新增前端资源**：`static/src/js/product_reference_editor.js`（字段 widget）、
  `static/src/js/product_reference_manage.js`（管理弹窗 + overlay 注册）、
  `static/src/xml/product_reference_editor.xml`、`static/src/xml/product_reference_manage.xml`、
  `static/src/scss/product_reference.scss`，走 `web.assets_backend`。
- **i18n**：新增弹窗 / tooltip / 徽标相关术语与 JS `_t` 文案；移除已删除页面的术语（`References`、
  `Reference Lines` 页内引用、页面提示段落）；`Product Reference` 合并为一条多引用条目。
- **文档同步**：`README.md`、`AGENTS.md`、根 `README.md` / `TODO.md`。

### 影响

- 产品表单不再有「参考号」页；历史数据不受影响（参考号行仍在 `product_reference_code` 表）。
- 额外参考号仍是**产品级**（挂在 `product.template` 上）；变体表单经 `_inherits` 委托读写同一组行，
  同一产品的多个变体共享同一份额外参考号。
  （`19.0.2.4.0` 起改为**变体各自一份**、多变体产品模板表单整块隐藏，见上一版本条目。）
- 弹窗内改动随产品表单「保存」提交：不保存则不入库；关闭弹窗不会回滚已在 record 上的改动。
- 只读态只显示 Reference 文本与徽标 tooltip，不再显示输入框与「+」按钮。
- 升级后必须强刷浏览器（前端资源有缓存）。

### 验收清单（目标环境，已于 2026-09-08 随 T-011 验收通过）

1. `odoo -d <db> -u product_reference --stop-after-init` 升级不报错
2. 产品模板表单：产品名下方可见 `Ref.` 标签与 Reference 输入框，可编辑并保存；常规信息页不再重复出现
3. 输入框内右端「+」打开管理弹窗：新增 / 改值 / 改类型 / 停用 / 删除 / 上移下移均正常，关闭后徽标数量正确
4. 未保存的新产品：先加参考号再保存产品，保存后参考号落库且 `reference_code_index` 已同步
5. 变体主表单与变体独立编辑表单：同样出现编辑器；常规信息 / Codes 组不再重复出现 Reference
6. 徽标悬停显示参考号清单 tooltip（中英双语各验一遍）
7. 标签：中英界面输入框前都显示 `Ref.`（不随语言变化）
8. 只读态：只显示 Reference 文本与徽标 tooltip
9. 多变体模板：显示「按变体维护」提示，管理入口可用
   （`19.0.2.4.0` 起改为整块隐藏，该项已被取代）
10. 回归：列表搜索框 / Many2one 下拉按参考号仍能命中并显示「（命中参考号：xxx）」；
   同产品重复参考号仍被阻止；删除产品级联清理

---

## [19.0.2.2.0] - 2026-09-07（验收通过）

### 变更（功能回退与简化）

- **不在参考号表中存储 Odoo Reference**：移除 `19.0.2.1.0` 引入的
  `product.reference.code.is_internal` 字段、`("internal", "Internal Reference")`
  selection 值以及所有双向同步逻辑（`_sync_internal_reference_line`、
  `product.template.create/write` 重写、`product.product.write` 钩子、内部行保护）。
- **前端直接显示原生 `default_code`**：在产品表单「参考号（References）」页顶部放置
  Odoo 原生 `default_code` 字段（标签 `Reference`），用户可在该页直接查看和修改，
  与「常规信息」页共享同一个字段，无需维护同步。
- **参考号明细行恢复纯扩展角色**：`product.reference.code` 只保存 customer / factory /
  alias 等额外参考号；`_order` 恢复为 `sequence, product_tmpl_id, id`。
- **清理历史内部行**：新增 `migrations/19.0.2.2.0/pre-migration.py`，在 ORM 删除
  `is_internal` 列前，先删除 `19.0.2.1.0` 遗留的 `is_internal = TRUE` 或
  `reference_type = 'internal'` 行（如该版本未部署则无影响）。
- **i18n 清理**：移除 `Internal` / `Internal Reference` / `Other References` 及内部行
  不可删除提示；恢复 `reference_type` help、active help、sequence help、页面提示等
  到 `19.0.2.0.0` 状态。
- **文档同步**：更新 `README.md`、`AGENTS.md`。

### 影响

- `default_code` 仍是 Odoo 原生字段，不进入 `product_reference_code` 表；
  修改它不会在参考号行列表中生成/删除任何记录。
- 已升级到 `19.0.2.1.0` 并产生内部参考行的库，再次升级到 `19.0.2.2.0` 时
  pre-migration 会自动清理这些行；请确保升级前已备份。
- 如果 `19.0.2.1.0` 从未部署，此版本升级与 `19.0.2.0.0` → `19.0.2.2.0` 等价，
  仅新增参考号页顶部的 `default_code` 字段。

### 验收记录（T-008）

- 验收日期：2026-09-07
- 验收环境：目标 Odoo 19 部署环境
- 验收结果：六项验收标准全部通过
  - [x] 「参考号」页顶部可见 `Reference` 字段，可查看和编辑
  - [x] 在「参考号」页修改 `Reference` 保存后，「常规信息」页同步变化
  - [x] 在「常规信息」页修改 `Reference` 保存后，「参考号」页同步变化
  - [x] `Reference` 为空时，参考号行列表不受影响，不会自动生成任何内部行
  - [x] 普通参考号行可正常增删改排序；同产品重复参考号仍被阻止
  - [x] 从 `19.0.2.1.0` 升级后，旧的 `is_internal` / `reference_type='internal'` 行被清理

### 交付记录（T-007 / T-008，2026-09-07）

- **完成日期 / 落地版本**：2026-09-07，`19.0.2.2.0`。
- **T-007 需求**：模块改名 `product_model` → `product_reference`（模型 `product.model.code` → `product.reference.code`，字段 `model_code*` → `reference_code*`），文案 `model` → `reference` 与 Odoo 原生「内部参考」语义对齐，配套幂等迁移脚本。落地版本 `19.0.2.0.0`。
- **T-008 需求**：产品「参考号」页顶部直接显示 Odoo 原生 `Reference`（`default_code`）供统一编辑。落地版本 `19.0.2.2.0`。
- **验收记录**：目标库执行改名 SQL 后 `odoo -d <db> -u product_reference --stop-after-init` 升级不报错；旧型号数据完整保留；应用列表无 `product_model` 残留；列表 / Many2one 按参考号命中且命中提示中英双语正确；同产品重复参考号报错带出具体值；删除参考号行与删除产品均正常；索引与唯一约束存在；参考号页顶部 `Reference` 可编辑且与「常规信息」页同步。
- **异常与后续维护**：
  - 模块改名必须先执行 README 中的改名 SQL，否则 Odoo 会把 `product_reference` 当成新模块安装。
  - 若从 `19.0.2.1.0`（内部参考行版本）升级，`pre-migration` 会自动清理 `is_internal` 行，升级前务必备份。
- **遗留**：无。

---

## [19.0.2.1.0] - 2026-09-07（待验证，已被 `19.0.2.2.0` 回退，未部署，仅供历史参考）

### 变更（功能）

- **新增内部参考行**：`product.reference.code` 增加 `is_internal` 字段，用于把
  `product.template.default_code`（General Information 中的 `Reference`）镜像到
  「参考号」页的第一行。
- **参考号类型扩展**：`reference_type` selection 增加 `("internal", "Internal Reference")`，
  排在 customer/factory/alias 之前，方便界面展示。
- **排序规则调整**：`_order` 改为 `is_internal desc, sequence, product_tmpl_id, id`，
  确保内部参考行始终置顶。
- **双向同步**：
  - 修改 `product.template.default_code` → `product.template.write()` 调用
    `_sync_internal_reference_line()`，自动创建 / 更新 / 删除内部参考行。
  - 修改内部参考行的 `reference_code` → `product.reference.code.write()` 回写
    `product.template.default_code`。
  - 变体 `product.product.default_code` 被直接修改时，也通过 `product.product.write()`
    钩子同步到模板侧。
- **保护内部参考行**：`product.reference.code.unlink()` 对 `is_internal=True` 的行
  抛出 `ValidationError`（同步上下文 `reference_sync=True` 除外）。
- **视图调整**：
  - 产品「参考号」页 One2many 列表：隐藏 `is_internal`，内部参考行的
    `sequence` / `reference_type` / `active` / `note` 均设为 readonly。
  - 参考号独立列表 / 表单：显示 `is_internal`，相关字段 readonly。
  - 搜索视图增加「Internal」与「Other References」筛选。
  - 页面提示更新，说明第一行为 Odoo Reference 镜像且不可删除。
- **数据回填**：新增 `migrations/19.0.2.1.0/post-migration.py`，升级后为所有
  `default_code` 非空的产品自动补建内部参考行。
- **i18n 同步**：新增 `Internal` / `Internal Reference` / `Other References` 及
  不可删除提示的 `msgid` / `msgstr`；更新 `reference_type` help、active help、
  sequence help、页面提示等中文译文。

### 影响

- 首次保存产品时，若 `default_code` 已填写，会自动在「参考号」页出现一条
  Internal Reference 行。
- 内部参考行不可删除、不可归档、不可改类型；只能通过「常规信息」页的
  `Reference` 字段间接维护。
- 若普通参考号行与 `default_code` 同码，同步时会自动提升为内部参考行，避免
  `UNIQUE(product_tmpl_id, reference_code)` 冲突。
- 升级 `19.0.2.1.0` 时，post-migration 会对所有 `default_code` 非空的产品执行一次
  回填；数据量大的库请安排在低峰期升级。

### 文档

- 同步更新 `README.md`、`AGENTS.md`。

### 待验证

- 产品表单的 `Reference` 与「参考号」页第一行双向同步，清空 `Reference` 后内部行消失。
- 内部参考行始终排在第一，删除时弹出中文提示。
- 独立参考号视图可筛选 Internal / Other References。
- 旧数据升级后，`default_code` 非空的产品自动出现 Internal Reference 行。

---

## [19.0.2.0.0] - 2026-09-07（验收通过）

### 变更（破坏性：模块 / 模型 / 字段改名）

- **模块改名**：`product_model` → `product_reference`（目录、模块技术名、`author` 归属不变）。
- **模型改名**：`product.model.code` → `product.reference.code`（表 `product_model_code` → `product_reference_code`）。
- **字段改名**：
  - `product.reference.code`：`model_code` → `reference_code`、`model_type` → `reference_type`
  - `product.template`：`model_code_line_ids` → `reference_code_line_ids`、
    `model_code_count` → `reference_code_count`、`model_code_index` → `reference_code_index`
- **约束改名**：`_model_code_unique_per_template` → `_reference_code_unique_per_template`
  （DB 唯一约束 `UNIQUE(product_tmpl_id, reference_code)`，提示语同步改为
  `Reference codes must be unique within the same product.`）。
- **方法改名**：`_compute_model_code_count` → `_compute_reference_code_count`、
  `_check_model_code_unique_per_template` → `_check_reference_code_unique_per_template`、
  `_extract_model_code_search_terms` → `_extract_reference_code_search_terms`。
- **外部 ID 改名**：模型 / 字段 / 视图 / 动作 / 权限的 xmlid 全部同步
  （如 `action_product_model_code` → `action_product_reference_code`、
  `access_product_model_code_user` → `access_product_reference_code_user`）。
- **文案语义**：源码与视图里所有 `model`（型号）改为 `reference`（参考号），与 Odoo 原生
  「内部参考 Internal Reference」语义一致；`i18n/zh_CN.po` 的 `msgid` / `msgstr` 同步
  （英文 `Reference` ↔ 中文「参考号」，命中提示 ` (Matching reference: %(codes)s)` ↔「（命中参考号：%(codes)s）」）。
- **新增迁移**：`migrations/19.0.2.0.0/pre-migration.py`，负责模块名、模型、字段、表、序列、
  索引、唯一约束与 `ir_*` 元数据的改名；脚本幂等，只改名不删数据。
- **顺带修复**：`product.reference.code.unlink()` 原来对 `product.template` 调用不存在的
  `_sync_template_index()`（删除参考号行会 `AttributeError`）。拼接逻辑下沉到
  `product.template._sync_reference_index()`，明细模型只负责调用。

### 影响

- **必须先在目标库执行改名 SQL 再升级**，否则 Odoo 会把 `product_reference` 当成新模块安装，
  旧数据不会自动接上：

  ```sql
  UPDATE ir_module_module SET name = 'product_reference' WHERE name = 'product_model';
  UPDATE ir_model_data SET module = 'product_reference' WHERE module = 'product_model';
  UPDATE ir_model_data SET name = 'module_product_reference'
   WHERE module = 'base' AND name = 'module_product_model';
  ```

  然后 `odoo -d <db> -u product_reference --stop-after-init`。
- 旧目录 `product_model` 必须删除（否则应用列表会出现两个模块）。
- 自定义代码 / 报表 / 搜索域若引用了 `model_code_index`、`model_code` 等旧字段名，需同步改为新名。
- 界面文案随源语言改动：英文界面为 `Reference` 系列，中文界面为「参考号」系列。
- 旧译文由升级时重新导入的 `i18n/zh_CN.po` 覆盖（Odoo 19 已无 `ir_translation` 表，译文落在记录自身）。

### 文档

- 同步 `README.md`（改名说明 + 升级步骤 + 验证清单）、`AGENTS.md`（命名语义与迁移约束）、
  根 `README.md` / `AGENTS.md` / `TODO.md` / `DOCS_TEMPLATE.md` 中的模块名与示例。

### 待验证

- 目标库执行改名 SQL 后 `-u product_reference` 不报错，历史型号数据完整保留。
- 应用列表只剩 `product_reference`，无 `product_model` 残留；`product_reference_code` 表有数据。
- 列表搜索框 / Many2one 下拉按参考号仍能命中，命中提示中英双语正确。
- 删除参考号行不再报错；删除产品仍级联清理。
- `product_template__reference_code_index_index`（trigram）与
  `product_reference_code_reference_code_unique_per_template` 存在。

---

## [19.0.1.1.0] - 2026-09-06（待验证，改名前的 i18n 版本，已被后续版本取代，仅供历史参考）

### 变更（功能）

- **国际化（i18n）**：源码用户可见文本全部改为英文（源语言 `en_US`），新增 `i18n/zh_CN.po` 提供简体中文翻译，支持中英双语、默认英文。
  - 模型：`_description`、字段 `string` / `help`、selection 标签（客户型号 / 工厂型号 / 别名）、数据库约束消息、`ValidationError` 提示。
  - 列表命中提示「（命中型号：xxx）」改为 `_(" (Matching model: %(codes)s)")`，由 `zh_CN.po` 提供中文，不再硬编码中文。
  - `_()` 调用改用命名占位符 `%(xxx)s`。
  - 视图 / 动作：列表 / 表单 / 搜索视图 `string`、型号页标题、占位提示、页面底部提示段落、`ir.actions.act_window` 名称与空视图帮助文案。

### 影响

- **默认展示语言变为英文**：`-u` 升级后，未启用中文的数据库全部显示英文文案。
- 需要中文的库：设置 → 语言安装「简体中文 (zh_CN)」，`odoo -d <db> -u product_model --stop-after-init` 升级并强刷浏览器。
- 列表搜索命中型号时，英文界面显示 `产品名 (Matching model: xxx)`，中文界面显示 `产品名（命中型号：xxx）`;该提示写入列表 `name`，仅用于展示，不落库。
- 代码注释仍为中文（不参与翻译）。

### 文档

- 同步 `__manifest__.py`（版本 19.0.1.1.0、name / summary / description 英文化）、`README.md`、`AGENTS.md`、根 `README.md`。

### 待验证

- 英文界面：产品表单「Models」页、型号字段标签 / help、去重报错均为英文。
- 中文界面：上述内容显示为中文；搜索型号命中时列表 `name` 后缀为「（命中型号：xxx）」。
- 语言切换后无需重启服务，刷新页面即可生效。

---

## [19.0.1.0.0] - 2026-09-02（验收通过）

### 验收记录

- 验收日期：2026-09-02
- 验收环境：目标 Odoo 19 部署环境
- 验收结果：五项验收标准全部通过
  - [x] 产品表单可增/删/改/排序型号行
  - [x] 产品列表搜索框输入型号可命中对应产品
  - [x] 销售订单行选产品（Many2one 搜索）输入型号可命中
  - [x] 型号批量录入（粘贴多行）可用
  - [x] 删除产品时型号行级联清理，无孤儿数据

### 执行流程

1. 首次安装：`odoo -d <db> -i product_model --stop-after-init`
   自动创建 `product.model.code` 表、`product.template.model_code_index` 列与 trigram 索引、加载 `ir.model.access.csv` 权限
2. 在产品表单「型号」页逐条新增型号行；保存后 `model_code_index` 自动同步
3. 验证搜索：在产品列表搜索框输入型号 → 命中对应产品，`name` 附加「（命中型号：xxx）」
4. 验证 Many2one：在销售订单行选产品处输入型号 → 命中对应产品
5. 验证去重：同产品录入重复型号 → 阻止并中文提示带出具体值与产品名
6. 验证级联：删除产品 → 确认 `product.model.code` 中对应行随之删除

### 异常情况与处理

- 历史产品无型号：`model_code_index` 为空，搜索框输入型号不命中（预期行为，不影响原生按 name/default_code/barcode 搜索）
- 同产品重复型号：应用层 `@api.constrains` 阻止并中文提示，DB 层 `UNIQUE(product_tmpl_id, model_code)` 兜底并发与批量导入
- 不同产品间同型号：允许，列表 `name` 附加「命中型号：xxx」以区分归属
- `model_code_index` 与型号行不一致（手工改库等）：在 shell 执行
  `env['product.model.code'].search([])._sync_template_index()` 重建

### 后续维护说明

- 改变型号拼接分隔符：只改 `_sync_template_index`（当前用 `\n`），改后对历史数据触发一次同步
- 新增型号类型：只改 `model_type` 的 `selection`，无需改搜索逻辑
- 让型号出现在其他单据的 Many2one 下拉：无需额外改动，只要指向 `product.template`，
  `_search_display_name` 已让型号参与搜索

### 变更

- 初始版本，实现产品多型号 + 可搜索：
  - 新建 `product.model.code` 明细模型（型号 / 类型 / 排序 / 启用 / 备注 / 归属产品）
  - 扩展 `product.template`：`One2many` 挂型号行、冗余可存储字段 `model_code_index`（trigram 索引）
  - 同产品内型号不可重复：`@api.constrains` 中文提示 + 数据库 `UNIQUE(product_tmpl_id, model_code)` 兜底
  - 搜索能力在数据库层：`_search_display_name` 让 `model_code_index` 参与搜索，否定操作符取交集
  - `web_search_read` 在列表命中型号时，把 `name` 附加「命中型号：xxx」提示
  - 产品表单「常规信息」页之后新增「型号」页，One2many 行可增删改排序
  - 产品列表新增「型号」列；搜索框并入型号搜索，新增独立「型号」搜索项
  - 型号独立列表/表单/搜索视图与菜单动作，供管理员批量检索维护
  - 型号行 `ondelete='cascade'`，删除产品时无孤儿数据

### 影响

- 新增模型 `product.model.code`，需在目标环境安装后由 `ir.model.access.csv` 授权
- `product.template` 新增 `model_code_index` 字段（`Text` + trigram 索引），首次安装自动建列与索引
- 不修改 Odoo 核心源码，全部通过 `_inherit` 扩展
- 仅依赖 `product`，不依赖 `sale`

### 文档

- 同步更新 `__manifest__.py`、`README.md`、`AGENTS.md`
