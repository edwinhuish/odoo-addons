# 变更日志

> 倒序排列，最新版本在最前。每版本固定三段式：变更 / 影响 / 文档。
> 版本号规则见根 `AGENTS.md` 第 3 节：架构/破坏性 +x，功能新增 +y，修复 / 文档 +z。

---

## [19.0.2.0.1] - 2026-09-09（待验证）

### 变更（i18n / 文档）

- **应用列表（Apps）中文化**：`i18n/zh_CN.po` 补充「应用列表元数据」译文，中文环境下应用卡片与详情页显示中文模块名 / 摘要 / 描述。
  - `model:ir.module.module,shortdesc:base.module_product_card_view` → 「产品卡片视图」
  - `model:ir.module.module,summary:base.module_product_card_view`：摘要整句译文
  - `model:ir.module.module,description:base.module_product_card_view`：`description` 整段译文（`translate=True` 整值翻译，`msgid` 与 `textwrap.dedent(manifest["description"])` 逐字符一致）
  - `model:ir.module.category,name:base.module_category_inventory_product` → 「产品」（`Inventory/Product` 的自定义子分类，官方 `base` 无译文）
- 说明：视图切换器上的 **Card 按钮名称**属于 `session.view_info` 的 `display_name`，与本次应用列表元数据无关，仍是遗留问题（见 `README.md` →「遗留问题」）。

### 影响

- 纯译文改动，无模型 / 字段 / 视图 / 权限变更，**无需迁移脚本**。
- `odoo -d <db> -u product_card_view --stop-after-init` 升级后，中文环境「应用」列表显示中文名称 / 摘要 / 描述与中文分类；英文环境不变。
- 这些记录归属 `base`（xmlid `base.module_*` / `base.module_category_*`、`noupdate=True`）：po 导入只补齐缺失语种，**不覆盖库中已有的 `zh_CN` 值**；后续改译文的强制刷新方式见根 `AGENTS.md` 4.8。

### 文档

- 同步 `__manifest__.py`（版本 19.0.2.0.1）、`README.md`（国际化节）、`AGENTS.md`（当前版本 + i18n 约束）、根 `README.md` / `AGENTS.md` / `TODO.md`。
- 规范沉淀：根 `AGENTS.md` 新增 4.8「应用列表元数据（模块名 / 摘要 / 描述 / 分类）翻译规范」，并更正 4.1 中「写在自研模块 po 里匹配不到、无效果」的错误说法。

---

## [19.0.2.0.0] - 2026-09-09（Card 入口已确认，其余待复验）

### 交付记录（T-012）

- 验收日期：2026-09-09
- 验收环境：目标 Odoo 19 部署环境（`19.0-20260817`）
- 验收结果：Card 视图入口（库存 → Products 切换器）已由使用方确认可见可用；卡片内容 / 多图轮播 /
  变体联动 / Sales / Purchase 入口 / 中英双语 / 权限列入待复验清单
  （见模块 `README.md` →「验证清单」「测试用例」「遗留问题」）

### 变更

- **架构调整：从「独立动作 + `js_class`」改为注册新 view type `card`**（T-012 需求是官方产品列表
  右上角能切到卡片视图；`js_class` 变体不会在切换器产生新按钮，故必须新增 view type）：
  - Python：`ir.ui.view.type`、`ir.actions.act_window.view.view_mode` 的 Selection 追加 `card`。
  - JS：`registry.category("views").add("card", {...kanbanView, type:"card", ArchParser, Model, Renderer})`；
    **patch `session.view_info.card`**——核心 `view.js` 用 `type in session.view_info` 校验、
    `loadView` 用 `session.view_info[type]` 判存在、`action_service.js` 解构
    `{icon, display_name, multi_record}` 生成按钮；该白名单由服务端核心提供，模块级 Python 无法扩展。
  - 新增 `ProductCardArchParser`（继承 `KanbanArchParser`）：card arch 经 server 校验禁止 OWL 指令，
    不能写 `<templates>`，故在 `parse` 时注入虚拟 `<t t-name="card">` 以满足父类的模板检查。
- **注入官方产品动作**（只加 Card 视图入口，不改官方列表 / 看板 / 表单本身）：
  - 硬依赖：`product.product_template_action`、`product.product_template_action_all`、
    `stock.product_template_action_product`——`view_mode` 加 `card` + 各加一条 `act_window.view` 记录。
    （定位到库存入口实际绑定的是 `stock.product_template_action_product`，
    原先只扩展 product 的两条 action 不生效，这是「升级成功但无 Card 按钮」的根因）
  - 可选：`sale.product_template_action`、`purchase.product_normal_action_puchased` 由
    `<function>` → `_sync_product_card_views()` 条件注入。
- **移除独立的「Product Cards」动作与菜单**：Card 已成为官方 Products 的并列视图，独立入口不再需要
  （`i18n/zh_CN.po` 中对应的 3 条孤儿译文同步删除）。
- 切换器图标改为 `oi oi-view-kanban`（`session.view_info.card.icon`）。

### 影响

- 用户可见：官方 Products（库存 / 销售 / 采购入口）切换器新增 **Card** 按钮
  （顺序 Kanban / List / Card / Form）；默认视图不变，官方 list / kanban / form 的 arch 未改动。
- 依赖收敛：`depends` 仅为 `["stock"]`。
  - `product_image` 改可选：未安装时 `env.get("product.image.gallery")` 返回 `None`，图库留空，
    卡片**只显示主图**，其余功能不受影响。
  - `sale` / `purchase` 改可选：未安装时 `env.ref(..., raise_if_not_found=False)` 判空跳过，不注入也不报错；
    后装这两个模块时需再升级一次本模块才会注入。
- 数据库：无新建模型 / 字段 / 表结构变更，**无需迁移脚本**；仅新增 1 条 `ir.ui.view` 与若干
  `ir.actions.act_window.view` 记录，并扩展已有 action 的 `view_mode` 字段值。
- **卸载注意**：Odoo 不记录字段覆盖前的值，卸载后官方 action 的 `view_mode` 不会自动回滚为不含 `card`，
  需人工确认。
- 风险：`session.view_info` 的 patch 依赖 Odoo 内部实现（校验与解构方式），Odoo 升级需回归
  （见模块 `AGENTS.md` → L2 P2）。

### 文档

- 同步 `__manifest__.py`（版本 + description）、`README.md`（需求 / 接口 / 验收 / 截图 / 遗留问题）、
  `AGENTS.md`（技术设计 / L1 约束 2 改写 / L2 P1~P4 / T-012 复盘）、`i18n/zh_CN.po`
- 同步根 `TODO.md`（T-012 移出，标记已完成）、根 `README.md`（模块一览表 + 路线图）、
  根 `AGENTS.md`（模块速查表）

---

## [19.0.1.0.1] - 2026-09-08（待验证）

### 变更

- 代码结构 / 性能 / 可维护性优化（不改功能，不改 API）：
  - 后端 `models/product_card.py`：变体搜索加 `order="product_tmpl_id, id"`，合并两次属性
    收集循环为一次，删去构造 payload 时每模板的 `sorted`；逻辑等价、顺序一致。
  - 前端 `product_card_record.js`：
    - `selectionText` 直接读 `payload.rows`，避免重复走 `rows` getter；
    - 图片轮播区补 `pointerleave` / `pointercancel` 重置滑动起点，避免鼠标移出后残留误判；
    - 卡片补 `t-on-keydown`：聚焦时左右方向键翻图，提升键盘可访问性。
  - `__init__.py`：调整为 `models` 在前、`controllers` 在后（Odoo 惯例，无依赖影响）。
  - `product_card_model.js`：为 `withCache = false` 补注释说明原因。
  - 控制器 `/product_card/payload` 路由 `type="json"` → `type="jsonrpc"`（Odoo 19 起
    `type="json"` 为废弃别名，安装会出 `DeprecationWarning`）。
  - **修复** `_get_product_card_view_payload`：`product.product` 在 Odoo 19 经
    `product.template.attribute.value`（PTAV）关联属性与值，原代码误用已不存在的
    `attribute_value_ids`（且循环内引用未定义的 `value_id`），导致请求 500
    `AttributeError: 'product.product' object has no attribute 'attribute_value_ids'`。
    改用 `product_template_attribute_value_ids` + `attribute_id` /
    `product_attribute_value_id`。
  - **修复** 卡片模板里 `t-att-title="_t('Reference')"` / `_t('On hand')` 直接调
    `_t`：OWL 模板编译上下文无全局 `_t`，运行时报
    `TypeError: ctx._t is not a function`。改为组件 getter `referenceLabel` /
    `onHandLabel` 返回 `_t(...)`，po 入口（`code:addons/.../product_card_record.js:0`）不变。
  - **修复** 卡片空白 + 加载卡死（核心 bug，三版迭代）：
    ① 第一版在 `_loadData` 里把 payload 挂到 `super._loadData` 返回的 `result.records`
       原始对象上，但 `_createRoot` 随后用它们重建 Record 实例时丢弃自定义属性，
       导致卡片空白（空骨架 + 底部「—」）；
    ② 第二版改把 payload 存到 reactive model 实例 `productCardPayload`，触发了
       reload 循环（keepLast 竞争 + 第二次空响应 + 页面一直加载中）；
    ③ 第三版重写 `load`，按 resId 挂到 reactive `record.productCardData`，给 reactive
       Record 实例加属性触发 Owl DataModel 内部 effect（dirty/onUpdate）→ 前端卡死；
    ④ 第四版改用 module-level WeakMap by model（key=`toRaw(model)` → resId → payload），
       重写 `load` 在 `super.load` 后填充。toRaw 解决了 raw vs proxy 的 identity MISS，
       但又触发 `super.load` 的 `notify` → `onUpdate` → 再调 `load` → 无限循环卡死；
    ⑤ Renderer 方案：完全不重写 model 的 `_loadData` / `load`（前几版都触发 reactive 循环），
       改由 ProductCardRenderer 的 `onWillStart` / `onWillUpdateProps` 生命周期钩子拉取
       payload 填入**非 reactive 的 module-level 全局 Map**（按 resId 索引）。生命周期
       钩子不在 reactive effect 内，不触发 Owl DataModel 的 onUpdate / reload 循环。
       `ProductCardModel` 只保留 `withCache = false`，不重写任何方法。卡片通过
       `getProductCardPayload(resId)` 取；Renderer 钩子等 `await rpc` resolve 才渲染。
    ⑥ _resId 缓存切断 useRecordObserver 循环：KanbanRecord 父类 setup 注册了
       `useRecordObserver`（effect 监听 `props.record` 并写 `dataState.record` 触发
       re-render）；卡片 `payload` getter 若访问 `this.props.record.resId` 或
       `this.dataState.record?.id?.value`（reactive），会与该 effect 冲突 → render
       循环卡死。修复：setup 时把 `resId` 缓存到**非 reactive**实例属性 `_resId`
       （`onWillUpdateProps` 同步更新），payload / templateId getter 用 `_resId` 取，
       不访问任何 reactive state。
    ⑦ VariantRow sub-component 隔离嵌套 t-foreach：删 variants 不卡、加回卡，
       二分定位到 values t-foreach（内层嵌套 t-foreach）触发 Owl 重渲染循环。
       拆出 `ProductCardVariantRow` sub-component，外层只 t-foreach rows，内层
       values 的 t-foreach 在独立组件内，reactive 依赖不再跨层耦合，循环切断。
    - 卡片宽度固定 240px（`column-width: 15rem` + 卡片 `width`/`max-width: 15rem`），
      所有屏幕尺寸一致；变体按钮 active 样式加 `!important` + `box-shadow` 覆盖
      Bootstrap `.btn.active`，active 时显示对勾图标（`fa-check`）。
    同时修正 `templateId` 用 `record.resId`（原用 `record.id` 是 datapoint 内部编号，
    会导致图片 URL 404）。

### 影响

- 无功能 / API / 数据结构变更；无迁移脚本；无新字段或权限。
- T-012 待验证基线随本版本（`19.0.1.0.1`）；原验证清单仍适用，建议按本版本重验。
- 已自校验：JS（`node --check`）/ XML（minidom）/ lint 全部通过；无新增中文界面文本。

### 文档

- 同步 `__manifest__.py` 版本、模块 `CHANGELOG.md`、`AGENTS.md` / `README.md` 版本引用。

---

## [19.0.1.0.0] - 2026-09-08（待验证）

### 变更

- 初始版本，新增 `product_card_view` 模块：产品列表卡片视图（瀑布流），独立动作 + 菜单
  （库存应用 → Products → Product Cards），不修改官方默认产品视图。
- 后端（纯 `product.template` 方法扩展 + JSON 控制器路由 `/product_card/payload`）：
  - 每批产品一次返回卡片数据：模板信息、全部 active 变体（属性组合 / 参考号 / 在手）、
    模板共享图库与各变体专属图库引用；
  - 变体按钮行只保留真实存在于变体组合中的属性与值；
  - 在手读取 `product.product.qty_available`（不可追踪产品返回 `—`）；依赖 `product_image` + `stock`。
- 前端：
  - `views` 注册表新增 `product_cards`（`kanbanView` 派生，替换 Model / Renderer），
    kanban 视图 arch 声明 `js_class="product_cards"` 启用；
  - Model 在每页加载后批量拉取 payload 挂到 record 上；
  - 卡片组件实现顶部多图轮播（左右箭头 / 滑动 / 计数）、title / reference / on hand 信息区、
    按属性分行的变体按钮（选值切换图片 / 参考号 / 在手，禁掉不存在的组合），
    模板层与变体层两套图片不叠加；
  - 渲染器对 `web.KanbanRenderer` primary 继承仅加根类，未分组时以 CSS 多列实现瀑布流并自适应列数。
- 新增 `i18n/zh_CN.po`：动作 / 菜单 / help / JS 术语的中文译文（源语言英文，默认英文）。

### 影响

- 无新建模型、无数据库结构变更、无迁移脚本；无 `security/ir.model.access.csv` 需求。
- 官方默认产品列表 / 看板 / 表单均未修改；仅新增动作、菜单与一个 kanban 视图记录。
- 依赖 `product_image`（多图数据结构）与 `stock`（在手数量 + 库存应用菜单）。
- `19.0.1.0.0` 为初始版本。

### 文档

- 同步创建 `README.md`（功能 / 设计说明 / 安装 / 待验证清单 / 回滚）、`AGENTS.md`、`CHANGELOG.md`
- 同步更新根目录 `TODO.md`（T-012 进行中）、`README.md` 模块一览表与路线图、`AGENTS.md` 模块速查表

---
