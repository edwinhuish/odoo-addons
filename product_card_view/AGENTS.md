# AGENTS 工作指引

> 本文档用于指导 AI 助手或新开发者在维护、扩展本 Odoo 模块时的行为规范和关键上下文。
> L1 约束段每次加载必读；L2 踩坑档案按主题触发条件加载。

---

## 模块定位

- 模块名：产品卡片视图（Product Card View）
- 技术目录：`product_card_view`
- 新建模型：无；无 `security/ir.model.access.csv`
- 扩展模型：`product.template`（仅新增方法 `_get_product_card_view_payload`，不新增字段）
- 新增 HTTP 控制器：`/product_card/payload`（`auth="user"`，内部 JSON 接口，`sudo` 读数据）
- 自定义前端：`views` 注册表 `product_cards`（kanbanView 派生）
- 主依赖：`product_image`、`stock`
- 当前版本：`19.0.1.0.1`

---

## L1：不可破坏的核心约束

1. **不新增模型 / 字段 / 权限**
   - 所有卡片数据通过 `product.template` 方法 + 控制器路由装配，沿用产品与库存既有权限
   - 违反后果：破坏「开箱即用、无需额外权限」的设计，引入迁移与安全配置负担

2. **不修改官方默认产品视图**
   - 卡片视图是独立动作 + 菜单（库存应用 → Products → Product Cards）；
     官方列表 / 看板 / 表单及库存 / 销售产品菜单一律不动
   - 违反后果：影响其他模块与官方视图的继承锚点、改动面扩散

3. **模板层与变体层两套图片互不叠加**
   - 模板层 = 模板主图 + 模板共享图库；变体层 = 变体主图（无则回退模板主图）+ 变体专属图库
   - 违反后果：卡片图库语义与 `product_image` 不一致，变体图片混入共享图

4. **变体按钮行必须真实反映可组合变体**
   - 行值来源于 active 变体的 `product_template_attribute_value_ids`（PTAV）并集
     （属性经 `PTAV.attribute_id`、值经 `PTAV.product_attribute_value_id`，不是
     `product.attribute.value` 直接关联）；
   - 已选其他属性下不存在组合的值必须禁用，避免选中不存在的组合
   - 违反后果：点选后无对应变体，信息无法切换

5. **默认口径：模板层；点选切变体**
   - 默认显示模板名 / 模板 `default_code` / 全部变体在手总量；选择变体后切为对应变体信息
   - 变体 `default_code` 为空时回退模板参考号
   - 违反后果：卡片信息口径混乱

6. **每页只发一次数据请求**
   - 由 ProductCardRenderer 的生命周期钩子 `onWillStart` / `onWillUpdateProps` 拉取
     `/product_card/payload`，填入**非 reactive 的 module-level 全局 Map**（key=resId → payload）；
     卡片通过 `getProductCardPayload(resId)` 取。`ProductCardModel` 只保留 `withCache = false`。
   - 必须在 Renderer 钩子拉取（不在 model 的 `_loadData` / `load`）：钩子不在 reactive
     effect 内，不触发 Owl DataModel 的 onUpdate / reload 循环；重写 model 方法会触发循环卡死
   - 卡片 getter **必须用非 reactive 的 `resId`**（setup 缓存到 `this._resId`，
     `onWillUpdateProps` 更新）：KanbanRecord 父类 setup 注册了 `useRecordObserver`
     （effect 监听 `props.record` 并写 `dataState.record` 触发 re-render）；若 payload
     getter 访问 `props.record.resId` 或 `dataState.record?.id?.value`（reactive），
     会与该 effect 冲突 → render 循环卡死
   - 违反后果：页面卡顿，后端压力大；payload 关联错误会导致卡片空白或前端卡死

7. **所有用户可见文本源语言为英文（`en_US`）**
   - Python / XML / JS / QWeb 不写中文界面文案；中文只在 `i18n/zh_CN.po` 的 `msgstr`
   - 违反后果：默认英文界面出现中文，或译文失效 / 重复 `msgid` 导致 po 解析失败

---

## 国际化约束（i18n）

1. 源语言英文；翻译键名按根 `AGENTS.md` 4.2 对照表：
   - 动作 / 菜单名 → `model:ir.actions.act_window,name:` / `model:ir.ui.menu,name:`
   - 动作 help → `model_terms:ir.actions.act_window,help:`
   - JS `_t()` 术语 → `code:addons/product_card_view/static/src/js/product_card_record.js:0`
2. JS `_t()` 字符串与 QWeb 里的文本、tooltip 文案保持一致，改了源文本必须同步 po。
3. 占位符 / 拼接：前端已全部用单词翻译或模板变量，禁止把翻译拆碎。
4. 收尾动作：改英文源文本 → 同步 `i18n/zh_CN.po` → 提升版本 → `-u` + 强刷浏览器，中英文各验一遍。

---

## 文件职责

| 文件 | 职责 |
|------|------|
| `models/product_card.py` | `_get_product_card_view_payload()`：一次性装配模板 / 变体 / 图库 / 在手数据 |
| `controllers/product_card_controller.py` | `/product_card/payload` JSON 接口 |
| `views/product_card_views.xml` | kanban 视图（`js_class="product_cards"`）+ 独立动作 + 库存菜单 |
| `static/src/js/product_card_view.js` | 注册 `views.product_cards`（kanbanView 派生） |
| `static/src/js/product_card_model.js` | RelationalModel 子类，`_loadData` 中批量请求 payload 填入非 reactive 全局 Map（按 resId 索引，导出 `getProductCardPayload`） |
| `static/src/js/product_card_renderer.js` | KanbanRenderer 子类，替换记录卡片组件并加根类 |
| `static/src/js/product_card_record.js` | 卡片组件：轮播 / 变体选择 / 信息同步 / 打开产品 |
| `static/src/xml/product_card_templates.xml` | 渲染器 primary 继承模板 + 卡片 QWeb |
| `static/src/scss/product_card.scss` | 瀑布流多列布局 + 卡片 / 轮播 / 变体按钮样式 |
| `i18n/zh_CN.po` | 简体中文译文 |
| `README.md` / `CHANGELOG.md` / `AGENTS.md` | 三件套文档 |

---

## 维护要点与调试建议

- **新增图片源字段**：改 `product_card_record.js` 中 `IMAGE_FIELD` 与 `images` getter
  （模板层与变体层需分别维护入口，勿破坏「互不叠加」约束）。
- **变体规则调整**：改 `isValueAllowed` / `selectValue` / `currentVariant` 三个方法，保持三者一致。
- **payload 缺数据**：先看 `models/product_card.py` 的字段是否被阅读权限挡住；
  卡片有 `record.productCardData` 兜底逻辑，空数据不应导致白屏，应显示空态或占位。
- **样式只在卡片视图生效**：所有选择器都以 `.o_product_card_view`（渲染器根类）开头；
  官方 kanban 记录卡不在该根类下，不会被命中。
- **视图加载机制**：arch 根 `<kanban js_class="product_cards">` → web 用注册表 `product_cards`
  替换 Model / Renderer；若改动注册名，必须同步 arch `js_class` 与 JS 注册键。

---

## T-012 开发复盘与关键经验

> 交付后补记：目标 / 关键决策 / 踩坑记录 / 可复用经验。验收通过后同步 README 交付记录。

---

## 变更记录规范

每次功能修改后必须更新：
- `__manifest__.py` 的 `version`（遵循 `19.0.x.y.z`）
- `CHANGELOG.md` 版本说明（变更 / 影响 / 文档）
- 本 `AGENTS.md` 相关约束（若涉及行为变更）
- `README.md` 用户可见功能（若涉及）

版本号建议：
- 破坏性变更或架构调整：升第二位，如 `19.0.2.0.0`
- 功能新增：升第三位，如 `19.0.1.1.0`
- 修复或文档：升第四位，如 `19.0.1.0.1`

---
