# AGENTS 工作指引

> 本文档用于指导 AI 助手或新开发者在维护、扩展本 Odoo 模块时的行为规范和关键上下文。
> L1 约束段每次加载必读；L2 踩坑档案按主题触发条件加载。

---

## 模块定位

- 模块名：产品尺寸
- 技术目录：`product_dimension`
- 前身：`product_packing`（纸箱与包装，已移除；改名见 `19.0.2.0.0`）
- 新建模型：无，纯 `_inherit` 扩展
- 继承模型：`product.product`（尺寸真身）、`product.template`（单变体桥接）
- 自定义组件（前端模块）：无
- 主依赖：`product`（不依赖 `stock` / `sale` / `purchase`）
- 当前版本：`19.0.2.0.1`（19.0.2.0.1 修复 i18n：po 的 `#:` 引用行 / 多行 msgstr / `#. odoo-python` 标记三类静默失效，并打磨中文；19.0.2.0.0 改名 + 尺寸下沉到变体）

---

## L1：不可破坏的核心约束

每次修改代码必须保证以下行为不变。每条只列约束与违反后果，实现细节见 L2 踩坑档案。

1. **尺寸的真身在 `product.product`，模板侧只能是桥接**
   - `dimension_unit` / `dimension_length` / `dimension_width` / `dimension_height` 定义在变体上；
     模板上的同名字段必须是 `compute` + `inverse` 的镜像（`store=True`），不得变成独立存储的第二份真数据
   - 违反后果：多变体产品里尺寸与 Volume 归属错位，改模板尺寸牵动 / 不动变体都说不清（这正是 `T-021` 修掉的问题）

2. **模板侧桥接的语义与原生 `volume` / `weight` 完全一致**
   - 单变体：读镜像该变体、写回该变体；多变体：读出空值（`False` / `0.0`）、写入不碰任何变体
   - 视图上这些字段必须带 `invisible="product_variant_count > 1 and not is_product_variant"`，避免「填了却不生效」
   - 违反后果：用户在产品表单填了尺寸却悄悄丢失；或模板与变体数据互相覆盖

3. **尺寸变化必须同步原生 `Volume`（表单与后台两条路）**
   - `@api.onchange` 覆盖表单实时预览，`create` / `write` 覆盖导入 / API / 批量写入
   - 厘米按 `cm³ / 1 000 000` 换算，米直接相乘，结果恒为立方米
   - 长宽高任一为 0 时 `volume` 归 0（与前身模块一致）
   - 违反后果：表单与数据库体积不一致，运费 / 装载 / 报价计算出错

4. **所有用户可见文本源语言为英文（`en_US`）**
   - Python / XML 中不写中文界面文案；中文只放在 `i18n/zh_CN.po` 的 `msgstr`
   - 违反后果：默认英文界面出现中文；或重复 `msgid` 导致整份 po 解析失败

5. **校验信息必须带具体数值且可翻译**
   - 使用 `@api.constrains` + `ValidationError`，占位符用 `%(name)s`
   - 违反后果：用户看不懂报错位置；译者无法调整语序

6. **从 `product_packing` 升级必须走安装前钩子搬数据**
   - `hooks.py::pre_init_hook` 检测 `product_template` 上的旧列并复制到变体，可重复执行（`COALESCE` + `IF NOT EXISTS`）
   - 只认列名、不读 ORM 字段（旧模块代码已不在 addons 里）
   - 违反后果：目标环境已录入的尺寸数据静默丢失

---

## 国际化约束（i18n）

每处用户可见文本都必须满足（通用规则见根 `AGENTS.md` 第 4 节）：

1. **源语言是英文（`en_US`）**：Python / XML 里一律写英文；中文只能出现在 `i18n/zh_CN.po` 的 `msgstr` 里。
2. **可翻译入口正确**：见根 `AGENTS.md` 4.2「可翻译入口对照表」（`model:` / `model_terms:` / `code:` 三类键名）。
3. **禁止拼接句子**：占位符统一 `%(name)s`，禁止按位置 `%s`。
4. **收尾动作**：改英文源文本 → 同步 `i18n/zh_CN.po` → 提升版本 → `-u` 升级 + 强刷浏览器，中英文各验一遍。
5. **代码注释保持中文**，不为 i18n 改英文。
6. **应用列表（Apps）元数据必须有中文**：改 `__manifest__.py` 的 `name` / `summary` / `description` 后，必须同步 `i18n/zh_CN.po` 的 `model:ir.module.module,shortdesc|summary|description:base.module_product_dimension` 三条（`description` 条的 `msgid` 必须等于 `textwrap.dedent(manifest["description"])`，逐字符一致），分类沿用 `model:ir.module.category,name:base.module_category_inventory_product` → 「产品」并与其它产品类模块**合并成同一条 `msgid`**。
7. **`description` 的 RST 安全**：Apps 详情页用 RST 渲染描述，列表项的不同行缩进不一致会报 `Unexpected indentation`；因此描述里每条列表项**写成一行**（长行没关系），段落之间留空行。

---

## 文件职责

| 文件 | 职责 |
|------|------|
| `__manifest__.py` | 模块元数据、版本、依赖、数据文件登记、`pre_init_hook` 声明 |
| `hooks.py` | 安装前钩子：把旧 `product_packing` 留在模板上的尺寸数据搬到变体上 |
| `models/product_product.py` | 尺寸真身（单位 + 长宽高）、尺寸 → 原生 `Volume` 同步、非负校验 |
| `models/product_template.py` | 单变体桥接：读镜像 + 写回变体（与原生 `volume` / `weight` 同构） |
| `views/product_template_views.xml` | 在产品表单 Logistic 组内插入尺寸单位与尺寸 |
| `tests/test_product_dimension.py` | 6 项自动化测试（Volume 同步、单变体桥接、多变体独立、非负校验） |
| `i18n/zh_CN.po` | 简体中文译文（源语言 `en_US` 写在代码里；`i18n/` 不进 `data`） |
| `README.md` | 用户可见功能、字段表、迁移步骤、已知限制、验证清单 |
| `CHANGELOG.md` | 逐版本「变更 / 影响 / 文档」记录 |
| `AGENTS.md` | 本文件：核心约束、i18n 规则、文件职责、变更规范 |

---

## L2 踩坑档案

### P1：`digits='Volume'` 只有 2 位小数（实测）

- 现象：填 10 × 10 × 10 cm，`Volume` 显示 0.00；测试里断言 0.001 直接失败。
- 根因：原生 `product.product.volume` 用 `digits='Volume'`，而 `product` 模块定义的「Volume」小数精度默认是 **2**（`decimal_precision` 表），ORM 写入即四舍五入。
- 处置：模块**不**去改全局精度（会影响所有模块的体积展示）；把它写进 README「已知限制」并在 manifest 描述里提示，需要更高精度的部署自己在 设置 → 技术 → 小数精度 调整。测试里请用能被 2 位小数精确表示的体积（如 0.06 / 0.2 / 1.0）。

### P2：给 `api.constrains` / `api.onchange` 传动态字段元组会产生额外术语

- 现象：po 骨架里出现 `dimension_width` / `dimension_height` 这类「裸字段名」条目。
- 根因：Odoo 的术语提取会把装饰器里出现的字符串字面量当作 `code:` 术语。
- 处置：无害，但要给它们 `msgstr`（本模块译成「宽度」「高度」），否则 `task check` 之外的人工核对会以为漏翻。

### P3：字段名撞名的历史教训（沿用自前身模块）

- 现象：前身模块同时有「产品尺寸」与「纸箱尺寸」两组字段，升级时报 `Two fields (...) of product.template() have the same label`。
- 根因：同一模型上两组字段共用了 `Length` / `Width` / `Height` 标签。
- 处置：本模块只保留一组尺寸字段，因此可以放心使用 `Length` / `Width` / `Height`；**新增字段前先确认同模型上没有同标签字段**（`_inherits` 会让变体字段以委托形式出现在模板上，注意别和自己撞）。

### P4：改名 / 换模块技术名时，DB 里的旧模块记录要手工卸

- 现象：目录改名后每次加载都报 `module product_packing: not installable, skipped` + `Some modules are not loaded`。
- 根因：`ir_module_module` 里旧记录仍是 `installed`，但 addons 里已没有它的代码。
- 处置：装好新模块（数据搬运完成）后，用 `ir.module.module.button_immediate_uninstall()` 卸掉旧记录。

---

### P5：po 的三类「静默失效」（实测踩过：中文界面一直英文，导入却不报任何错）

**触发条件**：改完 `i18n/zh_CN.po`，`task update` / `task i18n` 都显示成功，但界面仍是英文。

三种原因互相独立，必须同时满足才能生效：

1. **`#:` 引用行多了一层前缀**：写成 `#: #: model_terms:...` → `PoFileReader` 用
   `re.match(r'(model|model_terms):([\w.]+),([\w]+):(\w+)\.([^ ]+)', occurrence)` 逐 occurrence 匹配，
   多一层前缀就定位不到记录，条目被直接丢弃。
2. **多行值没加引号**：多行 `msgstr` 直接写成带真实换行的字符串 → `polib` 抛
   `Syntax error in po file (line N)`，**整份文件**一条都读不进来。必须写成 `msgstr ""` + 多行 `"...\n"`。
3. **Python `_()` 条目缺 `#. odoo-python`**：运行期文案由 `CodeTranslations._load_python_translations()`
   从 po 里**按注释过滤**读取（`PYTHON_TRANSLATION_COMMENT = 'odoo-python'`；JS / OWL 模板条目要
   `odoo-javascript`），缺标记的条目永不生效。注意 `TranslationImporter` 本身**跳过** `code:` 条目
   （`if row.get('type') == 'code': continue`），所以 `_()` 文案只走这个运行期通道。

**验收方式（唯一可靠）**：去数据库 / 运行时看，别相信「导入没报错」——

| 面 | 核对方式 |
|----|----------|
| 字段标签 / help | `ir_model_fields.field_description->>'zh_CN'`、`help->>'zh_CN'` |
| selection | `ir_model_fields_selection.name->>'zh_CN'` |
| 视图术语 | `ir_ui_view.arch_db->>'zh_CN'` |
| 应用列表 | `ir_module_module.shortdesc / summary / description ->'zh_CN'` |
| 运行期 `_()` | `odoo shell` 里 `with_context(lang='zh_CN')` 触发一次报错看文案 |
| po 语法 | 容器内 `python3 -c "import polib; polib.pofile('<path>')"` |

**预防**：`task check` 已内建四类校验（引用行写法 / 条目缺引用行 / 缺 `odoo-python`·`odoo-javascript`
标记 / 行结构不合法），这几类问题都会在提交前卡住。

---

## 常见扩展场景

### 新增尺寸单位（如 inch）

- 扩展两处 `dimension_unit` 的 `selection`（变体侧与模板侧都要改，保持一致）
- 在 `_sync_volume_from_dimensions()` 的换算因子处补 inch → 立方米
- 同步 `i18n/zh_CN.po` 的 selection 译文与 `README.md` 示例

### 调整 Volume 同步规则

- 只改 `product.product._sync_volume_from_dimensions()`；`volume` 是普通存储字段，改完对已有记录不会自动重算
- 若希望历史数据一并刷新，需要单独的数据脚本或升级时的一次性计算

### 让尺寸参与其它模块（报价 / 报表 / 物流）

- 直接读变体上的 `dimension_*`（这是真身）；**不要**读模板字段做批量逻辑——多变体时它是空的
- 需要按尺寸筛选 / 分组时可以用模板字段（stored compute，跟随变体重算），但只对单变体产品有意义

---

## 调试建议

- `Volume` 不更新：确认改动走的是变体（多变体产品在模板表单上写尺寸是不生效的）；再查 `create` / `write` 是否被其它模块的 `super()` 链截断
- 报错未翻译：检查 `i18n/zh_CN.po` 中 `code:` 条目的 `msgid` 与源码 `_()` 文本是否一字不差
- 视图字段不出现：确认 `-u` 升级；多变体产品的模板表单上它们本来就是隐藏的
- 旧数据没搬过来：确认安装 `product_dimension` 时旧列还在（先装新模块、再卸旧模块）；钩子只在 `product_template` 上有旧列时执行

---

## 变更记录规范

每次功能修改后必须更新：
- `__manifest__.py` 的 `version`（遵循 `19.0.x.y.z`）
- `CHANGELOG.md` 的版本说明（变更 / 影响 / 文档）
- 本 `AGENTS.md` 的相关约束（若涉及行为变更）
- `README.md` 的功能说明（若涉及用户可见功能）

版本号建议：
- 破坏性变更或架构调整：升第二位，如 `19.0.2.0.0`（本模块改名 + 尺寸下沉到变体即属此类）
- 功能新增：升第三位，如 `19.0.2.1.0`
- 修复或文档：升第四位，如 `19.0.2.0.1`

---

## T-021 交付记录（改名 + 尺寸下沉到变体）

### 需求

把 `product_packing` 改名为 `product_dimension`，移除「纸箱与包装」，只保留物流用的尺寸单位与尺寸；并解决 `T-021` 原本的问题——转为变体后这些属性要跟随变体。

### 关键决策

1. **尺寸下沉到 `product.product`**（模板侧退化为单变体桥接）：照抄原生 `volume` / `weight` 的归属，才谈得上「跟随变体」。
2. **`store=True` 的模板镜像**：与原生 `volume` 一致，可搜索 / 分组，避免额外的非存储字段语义分叉。
3. **可见性沿用原生规则**：多变体产品的模板表单上隐藏，既不误导用户，也不新增「写入被忽略」的路径。
4. **保留原字段语义（单位 cm/m、体积恒为 m³、不清空手动 Volume 以外的行为）**，只换归属层。
5. **改名后的数据搬运放在 `pre_init_hook`**：模块改名意味着旧模块的 migration 脚本不会执行，只能用安装前钩子 + SQL 列名。

### 实测记录

- 开发库（旧模块已装、有 1 条尺寸数据）：安装 `product_dimension` → 钩子日志 `filled 56 variant rows ...` + `recomputed volume for 1 variants`；变体侧得到 `cm / 50 / 40 / 30`、`volume = 0.06`，模板侧镜像同步
- 卸载旧模块后加载无告警；`product_dimension` 6 项测试通过；与 `product_variant_conversion` 的集成用例通过（39 项）
