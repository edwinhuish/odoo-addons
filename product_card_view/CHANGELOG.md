# 变更日志

> 倒序排列，最新版本在最前。每版本固定三段式：变更 / 影响 / 文档。
> 版本号规则见根 `AGENTS.md` 第 3 节：架构/破坏性 +x，功能新增 +y，修复 / 文档 +z。

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
    ⑤ 最终回到 `_loadData`（在 root 创建前执行，不访问 root，super.load 用 result 创建
       root 后才 notify，不触发 onUpdate→load 循环）+ 全局 Map by resId（不挂对象 → 不被
       `_createRoot` 丢弃；不触发 reactive；不依赖 model identity → 无 toRaw 问题）。
       卡片通过 `getProductCardPayload(record.resId)` 取；`_loadData` 在 root 创建前完成
       填充，root 创建后 KanbanCard 渲染即有数据。
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
