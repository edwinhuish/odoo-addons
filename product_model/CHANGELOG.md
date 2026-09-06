# 变更日志

## [19.0.1.1.0] - 2026-09-06（待验证）

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
