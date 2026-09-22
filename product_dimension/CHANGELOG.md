# 变更日志

> 倒序排列，最新版本在最前。每版本固定三段式：变更 / 影响 / 文档。
> 版本号规则见根 `AGENTS.md` 第 3 节：架构/破坏性 +x，功能新增 +y，修复 / 文档 +z。
> **注意**：本模块在 `19.0.2.0.0` 由 `product_packing` 改名而来，更早的条目是旧名时期的历史记录。

---

## [19.0.4.1.0] - 2026-09-22（修「cm 小体积显示 0」：前端取整参数 + Volume 精度）

### 变更

- **修复：前端取整参数用错，导致任何小于 1 的体积被算成 0。** `roundPrecision()` 的第二参数是
  **精度因子**（两位小数要传 `0.01`，Odoo 核心的写法是 `parseFloat("1e" + -decimals)`），此前把字段
  `digits[1]`（`2`）直接传了进去 —— 等于「按 2 的整数倍取整」，于是 50×40×30 cm 的正确体积 0.06
  在**界面**上显示成 0，随表单提交后**存进库的也是 0**（后端因收到 `volume` 而不再兜底）。
- **修复：原生「Volume」精度只有 2 位，cm 尺寸的小体积被舍成 0。** 20 × 20 × 20 cm = 0.008 m³、
  10 × 10 × 10 cm = 0.001 m³ 都会被舍成 0（界面上只看到「Volume = 0」）。新增
  `hooks.ensure_volume_precision()`：安装（`post_init_hook`）与升级（`migrations/19.0.4.1.0/`）
  各调一次，把全局「Volume」精度提到 **6 位**（1 cm³ = 0.000001 m³ 刚好能表示），**只升不降**、
  幂等；管理员自己调更高不会被覆盖，想改小在 设置 → 技术 → 小数精度 里改（模块之后不再干预）。
- **重构：前端纯规则抽到 `static/src/js/dimension_volume_rules.js`**（不依赖任何 Odoo 模块），
  补丁只负责挂钩与写回；这样规则能被 **node 直接跑单元测试**
  （`test_frontend_rules_produce_the_expected_volumes()`）——上面那个 bug 正是「前端逻辑没人测」漏掉的。

### 影响

- 修复后：50×40×30 cm → `Volume = 0.06`；20×20×20 cm → `0.008`；10×10×10 cm → `0.001`（此前均为 0）
- **全局设置变化**：安装 / 升级会把「Volume」小数精度从 2 位提到 6 位（影响所有模块的体积显示，
  数值更精确；只升不降，不会覆盖管理员调过的更高值）
- 无数据结构变化；自动化测试 15 → **17 项**（新增：小体积保留小数、node 实跑前端规则）

### 文档

- 模块 `README.md`：已知限制改写为「精度会被模块提到 6 位」，计算职责小节与验证清单同步
- 模块 `AGENTS.md`：L1 第 3 条补精度要求；文件职责表加入前端规则文件 / 钩子 / 迁移目录；
  L2 新增 P8（体积显示 0 的两个真凶 + 「前端逻辑要能测」的教训）

### 验证记录

| 项 | 结果 |
|----|------|
| dev 库升级 | 迁移日志 `raising the Volume decimal precision from 2 to 6`，`decimal_precision` 中 Volume = 6 ✓ |
| 小体积实测（dev 库） | 10³ cm → 0.001、20³ cm → 0.008、50³ cm → 0.125 ✓（修复前 0 / 0.01 / 0.13） |
| `task test -- product_dimension` | 17 项 0 failed（含 node 实跑前端规则的用例）✓ |
| `task test -- product_variant_conversion,product_dimension` | 43 项 0 failed ✓ |
| `task check` | 通过 ✓ |

---

## [19.0.4.0.0] - 2026-09-22（前后端职责重划分：体积在浏览器里算，后端只兜底）

### 变更

- **界面侧的体积计算移到前端**：新增 `static/src/js/dimension_volume.js`（`Record._update` 补丁）。
  表单里改 `dimension_unit` / 长 / 宽 / 高时，浏览器即时算出 `volume` 写回同一个字段、随表单一起提交 ——
  不需要服务端往返，后端也不再为界面算一遍。
- **删掉两个尺寸 onchange**（`product.product` 与 `product.template` 上的 `_onchange_dimension_fields`）：
  Odoo 只为注册过 onchange 的字段发 onchange 请求，去掉之后那些字段的 RPC 响应里自然也不再带体积。
  模板侧那个 onchange 原本只是为了让产品表单能预览（`19.0.3.1.0` 的补丁），现在统一由前端负责。
- **后端改为「带体积就不算，不带才兜底」**：新增 `_should_sync_volume()`，`create` / `write` 共用 ——
  写入值里含 `volume` 时原样采信；只有「写了尺寸、没带体积」的路径（导入 / API / RPC / 其它模块，
  含 `product_variant_conversion` 的谱系继承与模板桥接的 inverse）才补算，保证库里的体积不落后。
- **换算口径仍是唯一一处**：后端 `volume_from_dimensions()`；前端按同一规则实现（字段名 / `1 000 000` /
  按 `digits` 取整），并由 `test_frontend_computation_matches_the_backend_rules()` 守住两处不能只改一边。
- manifest 描述与 `i18n/zh_CN.po` 按新的职责划分改写（中英同步）。

### 影响

- **职责变化（行为等价）**：界面上的体积仍即时显示且与落库一致；非界面写入仍会自动补算 ——
  区别只是「界面那次计算」从服务端搬到了浏览器，少一次往返、少一次重复计算
- `volume` 仍可手工填：改的是 `volume` 本身时前端不介入，后端也因为值里带了 `volume` 而不重算
- 前端资源需要 `web`（Odoo 的 `auto_install` 模块，实际总在）；万一没有，只是少了界面即时计算，
  落库仍由后端兜底保证正确 —— 因此 `depends` 保持只有 `product`
- 自动化测试 13 → **15 项**（新增职责划分的 5 条断言，替换掉 3 条已不适用的服务端预览用例）

### 文档

- 模块 `README.md`：新增「Volume 的计算职责」小节（触发条件 / 完整性校验 / 计算逻辑 / 展示方式 / 职责表），
  核心设计表、操作要点与验证清单同步
- 模块 `AGENTS.md`：L1 第 3 条改写为「界面归前端、后端只兜底」；文件职责表加入前端文件；L2 P7 重写为前端即时计算的三条坑

### 验证记录

| 项 | 结果 |
|----|------|
| 前端资源是否真的进包 | `ir.asset._get_asset_paths("web.assets_backend", {})` 共 2464 条，其中含 `product_dimension/static/src/js/dimension_volume.js` ✓ |
| `task test -- product_dimension` | 15 项 0 failed ✓ |
| `task test -- product_variant_conversion,product_dimension` | 43 项 0 failed（谱系继承写入尺寸 + 体积：采信与兜底两条路都覆盖）✓ |
| `task check` | 通过（含 JS 语法检查）✓ |
| 界面交互（浏览器里改尺寸即见体积） | **待目标环境复验**（前端行为无法在无浏览器环境里断言） |

---

## [19.0.3.1.0] - 2026-09-22（表单里填完尺寸立刻算出 Volume）

### 变更

- **补上模板侧的表单预览**：新增 `product.template._onchange_dimension_fields()`。此前预览 onchange 只挂在
  `product.product` 上，而**产品表单的模型是 `product.template`** —— 模板侧是单变体桥接，尺寸要等保存时的
  inverse 才落到变体上，原生 `volume` 又是 `compute + inverse + store`，于是在产品表单上填完长宽高，
  `Volume` 一直是 0.00、**保存后才出现**（实测：50×40×30 cm 未保存时 `volume = 0.0`，保存后 0.06）。
  变体表单侧本来就有 onchange，不受影响。
- **换算口径收敛为一处**：新增 `product_product.volume_from_dimensions()`，变体侧的写库同步
  （`_sync_volume_from_dimensions()`）与模板侧的表单预览共用它；字段名常量（`DIMENSION_UNIT_FIELD` /
  `DIMENSION_FIELDS`）也统一到真身文件，模板侧改为 import —— 免得两处各算一套、慢慢漂移。
- manifest 描述与 `i18n/zh_CN.po` 补「填完尺寸立刻显示体积」说明（中英同步，门禁校验 msgid 逐字符一致）。

### 影响

- 纯体验修复：模板侧落库语义不变（仍是保存时 inverse 落到那条变体）；多变体产品不受影响（字段在界面上隐藏，
  预览也不会介入）
- `volume` 仍可手工填 —— 但只要改动任一尺寸字段，体积即以尺寸为准（长宽高不齐时按既有规则归 0）
- 自动化测试 10 → **13 项**（新增：产品表单预览、变体表单预览、预览随单位与尺寸齐全度变化）

### 文档

- 模块 `README.md`：功能概述与「操作要点」补即时计算与体积归属优先级，验证清单补三条，测试数同步
- 模块 `AGENTS.md`：L1 第 3 条改为「两个模型都要有 onchange + 换算口径唯一」；L2 新增 P7（onchange 只在视图所属模型上生效）

### 验证记录

| 项 | 结果 |
|----|------|
| 产品表单（`Form` 模拟）输入 50×40×30 cm | 未保存 `volume = 0.06`（改造前 0.0）；保存后模板与变体均 0.06 ✓ |
| 变体表单（`Form` 模拟）输入 1×0.5×0.4 m | 未保存 `volume = 0.2`，保存后一致 ✓ |
| `task test -- product_dimension` | 13 项 0 failed ✓ |
| `task test -- product_variant_conversion,product_dimension`（尺寸模块回归） | 43 项 0 failed ✓ |
| `task check` | 通过 ✓ |

---

## [19.0.3.0.0] - 2026-09-22（挂载点补齐：多变体产品的尺寸终于有地方填）

### 变更

- **新增挂载点：变体快速编辑表单**。尺寸块挂到 `product.product` 的
  `product_variant_easy_edit_view` 上（原生 Logistics 组的 Volume 之前）。这个表单是
  **独立 primary 视图、不继承模板表单**，而产品的「变体」按钮
  （`product_variant_action`）用的正是它 —— 也就是说多变体产品逐条维护变体数据的默认入口
  原本**看不到也填不了尺寸**，只能靠导入 / API。挂上之后三条入口齐了：

  | 表单 | 挂载方式 | 可见性 |
  |------|----------|--------|
  | 产品表单（`product_template_form_view`） | 本模块挂载（Logistics 组、Volume 之前） | 多条变体时隐藏（与原生 Volume 同款门控） |
  | 变体完整表单（`product_normal_form_view`） | **继承模板表单**，随继承链自动获得，勿重复挂载 | 变体侧 `is_product_variant=True` → 门控为假 → 可见 |
  | 变体快速编辑表单（`product_variant_easy_edit_view`） | 本模块单独挂载 | 无单变体门控（它本身就是变体） |

- **收紧模板表单的 xpath 锚点**：`//label[@for='volume']` → `//group[@name='group_lots_and_weight']/label[@for='volume']`。
  松锚点在原生别处再出现 Volume 标签时会命中多个节点、字段被挂两遍（重复字段不报错，只会让用户看到两套输入框）。
- **明确「与原生 Volume 同进同退」**：尺寸块位于原生 Logistics 组内，而该组受祖先组
  `groups="uom.group_uom"` 门控 —— 只装 `product` 时没有该组的用户连 `volume` / `weight` 都看不到，
  尺寸随之一起隐没。这不是挂载缺失，而是与原生一致；已用测试钉住，避免出现「体积还在、尺寸没了」的半截状态。
- **manifest 描述与 `i18n/zh_CN.po`** 补挂载说明与可见性限制（中英同步，门禁校验 msgid 逐字符一致）。

### 影响

- 用户可见的能力变化：多变体产品现在可以在「变体」快速编辑表单里逐条填尺寸（此前只能在单变体产品上填）
- 无字段 / 数据结构变化；视图与文案变化，升级即生效
- 自动化测试 6 → **10 项**（新增：真身归属、三表单挂载、可见性门控、与原生 Volume 同进同退）

### 文档

- 模块 `README.md` →「视图」重写为挂载地图，「已知限制」补可见性门控，测试数同步
- 模块 `AGENTS.md` → L1 新增「挂载点必须齐全且与原生 Volume 同进同退」；L2 新增挂载类踩坑（继承链、门控、锚点）

### 验证记录

| 项 | 结果 |
|----|------|
| `task test -- product_dimension` | 10 项 0 failed ✓ |
| 三表单合成 arch（干净库 + 开发库） | 产品表单 / 变体表单 / 变体快速编辑表单均含四个尺寸字段 ✓ |
| 快速编辑表单 | 独立 primary 视图，改造前 `dimension = 0` 次、改造后 9 次 ✓ |

---

## [19.0.2.0.1] - 2026-09-22（修复 i18n 静默失效 + 中文打磨）

### 变更

- **修复：整份 `i18n/zh_CN.po` 从未生效**（中文界面一直是英文，导入过程却不报任何错）。三层原因逐层修掉：
  1. **`#:` 引用行多了一层前缀**（写成 `#: #: model_terms:...`）→ `PoFileReader` 的
     `re.match(r'(model|model_terms):...')` 匹配不上，条目定位不到记录；
  2. **多行 `msgstr` 写成了带真实换行的字符串**（没有引号）→ `polib` 直接报 `Syntax error in po file`，
     整份文件一条都读不进来；
  3. **含 `code:` 引用的条目缺 `#. odoo-python` 注释** → Python 的 `_()` 译文在运行时按注释过滤
     （`CodeTranslations._load_python_translations`），缺标记就永远显示英文。
- **中文打磨**：术语与 Odoo 官方 zh_CN 对齐（用「原生体积」而不是「原生 Volume」，「采用所选尺寸单位」
  而不是「按所选尺寸单位」等）；应用列表摘要改为「为每条产品变体增加尺寸单位与长宽高，并同步更新原生体积」；
  `description` 整段重写。
- **顺带清理**：`_check_dimension_values` 改用 `zip(DIMENSION_FIELDS[1:], labels)` 取字段名，
  不再产生 `dimension_width` / `dimension_height` 这类「裸字段名」术语（po 条目 27 → 25）。

### 影响

- 中文界面的字段标签 / help / selection / 视图术语 / 报错文案 / 应用列表元数据现在**全部**为中文
- 校验行为不变（仍是非负校验，报错仍带产品名、字段名与具体数值）；无数据结构变化、无迁移

### 文档

- 模块 `AGENTS.md` → L2 新增 P5：po 的三类静默失效、`#. odoo-python` 标记的作用，以及「用数据库核对译文」的验收配方
- 仓库 `.dev/scripts/check_repo.py`（`task check`）新增三条门禁：
  `#:` 引用行写法与条目缺引用行；`code:` 条目缺 `odoo-python` / `odoo-javascript` 标记；
  po 行结构合法性（多行文本必须写成带引号的续行）

### 验证记录（数据库口径，不是「导入没报错」）

| 面 | 核对方式 | 结果 |
|----|----------|------|
| 字段标签 / help | `ir_model_fields.field_description->>'zh_CN'` | 尺寸单位 / 长度 / 宽度 / 高度 ✓ |
| selection | `ir_model_fields_selection.name->>'zh_CN'` | 厘米 / 米 ✓ |
| 视图术语 | `ir_ui_view.arch_db->>'zh_CN'` | 含「尺寸单位」，无残留英文 ✓ |
| 应用列表 | `ir_module_module.shortdesc / summary / description ->'zh_CN'` | 产品尺寸 / 摘要 / 描述 ✓ |
| 运行期报错 | `with_context(lang='zh_CN')` 触发校验 | 「T-021 i18n Probe3 的长度不能为负数（-1.0）。」✓ |
| po 语法 | 容器内 `polib.pofile()` | 27 条条目解析通过 ✓ |

---

## [19.0.2.0.0] - 2026-09-22（改名 + 尺寸下沉到变体；T-021 交付）

### 变更

- **模块改名 `product_packing` → `product_dimension`**（显示名 `Product Packing` → **`Product Dimensions`**）：目录、manifest、i18n 术语、文档全部改名。
- **移除「纸箱与包装」**：`carton_*` 系列字段（装箱数 / 纸箱长宽高 / 纸箱单位 / 毛重 / 净重 / CBM / 尺寸规格）、
  产品表单的 `Carton & Packing` 组、产品列表的「Carton」「CBM」列、纸箱校验全部删除。
- **只保留物流尺寸**：尺寸单位（cm / m）+ 长 × 宽 × 高，仍在产品表单的原生 Logistics 组里、`Volume` 之前。
- **尺寸下沉到变体（T-021 的核心）**：
  - 真身改为 `product.product.dimension_unit / dimension_length / dimension_width / dimension_height`，
    原生 `volume` 由**该变体自己的**尺寸算出；
  - `product.template` 上的同名字段改为 `compute + inverse + store` 的**单变体桥接**（与原生 `volume` / `weight` 同构）：
    多变体产品的模板表单上隐藏、读出空值、写入不牵动任何变体；
  - 结果：多变体产品的每条变体各持一份尺寸与体积，改一条不影响别的。
- **数据搬运**：新增 `pre_init_hook`（`hooks.py`）：安装时把旧模块留在 `product_template` 上的
  `product_dimension_unit / product_length / product_width / product_height` 复制给该模板的**全部**变体，
  并按单位重算 `volume`（幂等，旧列不存在时什么都不做）。
- **补自动化测试**：本模块此前零测试，新增 6 项（Volume 同步 cm / m、清空尺寸归零、单变体桥接读写、多变体各自独立、非负校验）。
- **与 `product_variant_conversion` 打通**：该模块的按谱系继承清单在装了本模块时带上尺寸四件套，
  转换出的新变体继承其来源变体的尺寸与体积（该模块 `19.0.4.1.0`）。

### 影响

- **破坏性**：尺寸字段从模板移到变体（新字段名 `dimension_*`）。旧列经安装前钩子搬运后即可卸载旧模块；
  引用旧字段名 `product_dimension_unit` / `product_length` 等的外部脚本 / 报表需改用 `dimension_*`（读变体）。
- **纸箱能力移除**：原纸箱字段与其数据不再保留；如需纸箱信息请另立模块。
- 无新增依赖；`i18n/zh_CN.po` 按新术语集重建（含应用列表元数据改名）。
- 迁移顺序必须是**先装新模块、再卸旧模块**（卸载会删掉旧列）。

### 文档

- `README.md` 重写：功能概述 / 核心设计（归属 + 桥接）/ 字段表 / 视图 / **已知限制**（`Volume` 默认只有 2 位小数、尺寸不齐体积归 0、多变体产品的模板表单不显示）/ **从 product_packing 迁移** / 验证清单 / i18n
- `AGENTS.md` 重写：L1 六条约束（真身在变体、桥接语义与原生一致、必须同步 Volume、迁移必须走钩子等）、i18n 约束（含 `description` 的 RST 安全）、文件职责、L2 踩坑档案、T-021 交付记录
- 根 `README.md` / `AGENTS.md` / `TODO.md` 同步模块名与版本

### 验收记录（T-021）

- 开发库实测：安装新模块 → 钩子搬运日志 `filled 56 variant rows ...` + `recomputed volume for 1 variants`；
  变体侧得到 `cm / 50 / 40 / 30`、`volume = 0.06`，模板侧镜像同步；卸载旧模块后加载无告警
- 自动化测试：`product_dimension` 6 项通过；`product_variant_conversion` 连同本模块跑 39 项通过
- 待目标环境验证：全新安装、中英文界面、应用列表中文名、旧库迁移后的界面核对

---

## [19.0.1.1.3] - 2026-09-09（验收通过）

### 变更（i18n / 文档）

- **应用列表（Apps）中文化**：`i18n/zh_CN.po` 补充「应用列表元数据」译文，中文环境下应用卡片与详情页显示中文模块名 / 摘要 / 描述。
  - `model:ir.module.module,shortdesc:base.module_product_packing` → 「产品装箱」
  - `model:ir.module.module,summary:base.module_product_packing`：摘要整句译文
  - `model:ir.module.module,description:base.module_product_packing`：`description` 整段译文（`translate=True` 整值翻译，`msgid` 与 `textwrap.dedent(manifest["description"])` 逐字符一致）
  - `model:ir.module.category,name:base.module_category_inventory_product` → 「产品」（`Inventory/Product` 的自定义子分类，官方 `base` 无译文）
- 修复 `i18n/zh_CN.po` 中 `Dimension Unit` 的**重复 `msgid`**（19.0.1.1.2 遗留）：字段标签与视图术语两条合并为一条多引用条目，符合根 `AGENTS.md` 4.4「同一 `msgid` 只能有一条」。

### 影响

- 纯译文改动，无模型 / 字段 / 视图 / 权限变更，**无需迁移脚本**。
- `odoo -d <db> -u product_packing --stop-after-init` 升级后，中文环境「应用」列表显示中文名称 / 摘要 / 描述与中文分类；英文环境不变。
- 这些记录归属 `base`（xmlid `base.module_*` / `base.module_category_*`、`noupdate=True`）：po 导入只补齐缺失语种，**不覆盖库中已有的 `zh_CN` 值**；后续改译文的强制刷新方式见根 `AGENTS.md` 4.8。

### 文档

- 同步 `__manifest__.py`（版本 19.0.1.1.3）、`README.md`（国际化节）、`AGENTS.md`（当前版本 + i18n 约束）、根 `README.md` / `AGENTS.md` / `TODO.md`。
- 规范沉淀：根 `AGENTS.md` 新增 4.8「应用列表元数据（模块名 / 摘要 / 描述 / 分类）翻译规范」，并更正 4.1 中「写在自研模块 po 里匹配不到、无效果」的错误说法。

### 验收记录（T-013）

- 验收日期：2026-09-09
- 验收环境：目标 Odoo 19 部署环境（已安装「简体中文 (zh_CN)」）
- 验收结果：6 项验收标准全部通过（中英文各验一遍）
  - [x] `odoo -d <db> -u product_packing --stop-after-init` 升级无报错
  - [x] 中文「应用」列表：卡片标题显示「产品装箱」，摘要为中文
  - [x] 中文「应用」详情：描述整段为中文
  - [x] 中文「应用」左侧分类：显示「库存 / 产品」——父级 `Inventory` 沿用官方译文，自定义段 `Product` → 「产品」由本模块提供
  - [x] 切回英文界面：名称 / 摘要 / 描述回到 `__manifest__.py` 的英文原文
  - [x] 仓库内自校验通过：无重复 `msgid`（顺带修掉 `Dimension Unit` 的重复条目）；`shortdesc` / `summary` / `description` 的 `msgid` 与 manifest 逐字符一致；源码无残留中文界面文本（脚本见根 `AGENTS.md` 4.6）

> 后续若只改译文（`msgstr`），这些记录是 `noupdate=True`，`-u` 不会覆盖库里已有的 `zh_CN`，
> 需按根 `AGENTS.md` 4.8 第 9 条用 `TranslationImporter.save(force_overwrite=True)` 或先清 `zh_CN` key 再升级。

---

## [19.0.1.1.2] - 2026-09-08（已验证）

### 变更

- 修复 Odoo 启动时 `ir.model` 的字段标签重复 WARNING：
  - 为产品自身尺寸字段 `product_dimension_unit` / `product_length` / `product_width` / `product_height`
    设置唯一字段标签（`Product Dimension Unit` / `Product Length` / `Product Width` / `Product Height`）
  - 纸箱尺寸字段保持原标签不变；视图中的 `<label>` 仍显示「Dimension Unit / Dimensions」，用户界面不变
- 同步拆分 `i18n/zh_CN.po` 中产品尺寸与纸箱尺寸的字段描述翻译条目
- 补充 `i18n/zh_CN.po` 中视图术语 `Dimension Unit` 的简体中文翻译，使产品表单中的「尺寸单位」标签在中文环境下正确显示

### 影响

- 无数据库结构变更、无业务逻辑变更，无需迁移脚本
- 视图/导出/高级搜索中产品尺寸字段的显示名从「Dimension Unit / Length / Width / Height」
  变为「Product Dimension Unit / Product Length / Product Width / Product Height」，纸箱字段不变
- `19.0.1.1.2` 直接替代 `19.0.1.1.1`

### 文档

- 同步更新 `__manifest__.py` 版本至 `19.0.1.1.2`
- 同步更新 `AGENTS.md` 当前版本，新增 T-009 开发复盘与关键经验
- 同步更新 `README.md`：修正 Volume 联动描述、补充完整 T-009 交付记录（目标 / 方案 / 关键代码 / 测试结果 / 后续计划）
- 同步更新 `CHANGELOG.md`，新增「交付记录（T-009）」
- 同步更新根目录 `README.md` / `AGENTS.md` / `TODO.md` 版本号与模块状态

---

## [19.0.1.1.1] - 2026-09-07（待验证）

### 变更

- 调整产品尺寸与原生 `volume` 的联动逻辑：
  - 由「仅当 `volume == 0` 时自动填充」改为「只要产品尺寸变化，就自动重算并更新 `volume`」
  - 增加 `create` / `write` 覆盖，保证通过导入、API 或表单保存时 `volume` 都能同步更新
  - 保留 `@api.onchange`，表单端实时可见
- 新增 `_compute_volume_from_dimensions` 辅助方法，统一厘米 / 米到立方米的换算逻辑
- 视图布局调整：把 `Dimension Unit` 与 `Dimensions` 放在原生 `Volume` 之前，更符合「先输入尺寸再得到体积」的操作习惯

### 影响

- 仍为纯 `product.template` 扩展，无数据库结构变更，无需迁移脚本
- 用户手工录入的 `volume` 会被产品尺寸覆盖；后续如需独立维护体积，需先将尺寸清空或单独扩展开关
- 19.0.1.1.1 直接替代 19.0.1.1.0，无需先验证旧逻辑

### 文档

- 同步更新 `__manifest__.py` 版本至 `19.0.1.1.1`
- 同步更新 `README.md` 操作要点与验证清单
- 同步更新 `AGENTS.md` L1 约束
- 同步更新根目录 `README.md` / `AGENTS.md` / `TODO.md` 版本与验收标准

---

## [19.0.1.1.0] - 2026-09-07（待验证）

### 变更

- 在产品表单的 Logistics 组中新增产品自身尺寸字段：
  - `product_dimension_unit`：产品尺寸单位（厘米 / 米）
  - `product_length` / `product_width` / `product_height`：产品长宽高
- 新增 `@api.onchange`：当原生 `volume` 字段为 0 且输入了有效长宽高时，自动按所选单位计算并填充 `volume`
- 视图继承原生 Logistics 组，将 Dimension Unit 与 Dimensions 放在 Volume 下方，保持与 Odoo 原生字段一致的显隐规则
- 更新 `i18n/zh_CN.po`，覆盖新增字段标签 / help / selection / 视图术语

### 影响

- 仍为纯 `product.template` 扩展，无新建模型，无数据库结构变更，无需迁移脚本
- 原生 `volume` 字段仅在当前值为 0 时被自动填充；已有非 0 体积不会被覆盖
- 19.0.1.0.0 与 19.0.1.1.0 可连续验证，无额外升级前置条件

### 文档

- 同步更新 `__manifest__.py` 版本至 `19.0.1.1.0`
- 同步更新 `README.md` 字段表、功能说明与验证清单
- 同步更新 `AGENTS.md` 当前版本与文件职责
- 同步更新根目录 `README.md` / `AGENTS.md` 模块一览表版本

---

## [19.0.1.0.0] - 2026-09-07（待验证）

### 变更

- 初始版本，新增 `product_packing` 模块
- 扩展 `product.template`，新增外贸常用纸箱字段：
  - `carton_qty_per_carton`：每个纸箱可装产品数
  - `carton_dimension_unit`：尺寸单位（厘米 / 米）
  - `carton_length` / `carton_width` / `carton_height`：纸箱长宽高
  - `carton_gross_weight` / `carton_net_weight`：纸箱毛重 / 净重（千克）
  - `carton_cbm`：根据长宽高自动计算的纸箱立方米数（store=True）
  - `carton_dimension_spec`：可读尺寸文本，如 `50 x 40 x 30 cm`（store=True）
- 继承 `product.product_template_form_view`，在 Inventory 标签页 Logistics 组后新增「纸箱与包装」组，CBM 只读展示
- 继承 `product.product_template_tree_view`，新增「纸箱」「CBM」可选列
- 增加 `@api.constrains` 校验：装箱数 / 尺寸 / 重量非负，净重不超过毛重
- 新增 `i18n/zh_CN.po`，覆盖字段标签、help、selection、校验报错与视图术语

### 影响

- 仅在产品模板上新增字段与视图继承，不涉及已有模型改名或数据迁移，无需 `migrations` 脚本
- 现有产品升级后新增字段为空，CBM 与纸箱规格显示为 0 / 空，用户按需补录
- 依赖最小化：仅 `product`，不引入 `stock` / `sale` / `purchase`

### 文档

- 同步更新 `__manifest__.py`、`README.md`、`AGENTS.md`
- 同步更新根目录 `TODO.md` / `README.md` / `AGENTS.md`

---

## 交付记录（T-009）

- **需求**：为产品 Inventory 标签页增加产品自身尺寸（自动同步原生 Volume）与外贸纸箱字段（装箱数、长宽高、毛重、净重、自动 CBM），尺寸单位厘米 / 米可配置。
- **落地版本**：`19.0.1.1.2`
- **验收日期**：2026-09-08
- **验收结果**：全部通过
  - 安装无报错，启动无 `ir.model` 标签重复 WARNING。
  - 产品尺寸字段位于 Logistics 组 `Volume` 之前，输入后实时同步 `Volume`。
  - 纸箱字段位于 Logistics 组之后的「纸箱与包装」组，CBM 随尺寸自动重算。
  - 负数、净重大于毛重等非法保存被阻止，报错支持中英双语。
  - 列表视图可选显示「纸箱」「CBM」列。
  - 中文界面字段标签、报错、单位均正确翻译。
- **实现要点**：见 `README.md` →「交付记录（T-009）」。
- **遗留问题**：无。
- **后续计划**：可扩展英寸单位、增加单件重量字段、在报表/导出模板中加入 CBM 与纸箱规格。

---
