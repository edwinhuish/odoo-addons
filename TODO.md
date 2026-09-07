# TODO

> 本文件是**待处理需求**的唯一入口。仅记录待办 / 进行中 / 搁置项——已完成的需求不在本文件留存，其文档与说明归档在各模块的 `README.md` / `CHANGELOG.md` / `AGENTS.md` 与根 [`README.md`](README.md) 模块一览表。
> 新需求追加到「待办池」末尾，开工移入「进行中」，验收通过后整条移出本文件（信息沉淀到模块文档）。

## 追加规则

1. **新需求一律追加到「待办池」末尾**，ID 顺序递增（`T-001` → `T-002` → …），不要插队、不要重排已有 ID。
2. 一行一项，格式：`- [ ] T-0xx ｜ 模块名 ｜ P0/P1/P2 ｜ 需求一句话描述`。
3. **开工**：整行剪切到「进行中」，并在下方补「验收标准」清单。
4. **完成**：验收通过后整条移出本文件；完成信息（日期 / 落地版本 / 验收记录 / 异常情况与后续维护）沉淀到对应模块的 `CHANGELOG.md` 与 `README.md` / `AGENTS.md`，根 `README.md` 模块一览表更新模块状态。
5. 暂时不做：移入「搁置 / 放弃」并写明原因，不删除，保留决策痕迹。
6. 一个需求对应一个模块；跨模块需求在「模块」列用 `+` 连接（如 `product_reference + web_image_paste`）。
7. 需求被拆解时，子项直接在条目下用缩进 `- [ ]` 列出，不单独占用顶层 ID。

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

- [ ] 🚧 T-006 ｜ product_image + product_reference + sale_order_no + web_image_paste ｜ P1 ｜ 四模块国际化：源语言改为英文（en_US，默认展示英文），各模块新增 `i18n/zh_CN.po` 简体中文译文，切换语言后界面随之更新

  - 设计约束（动工前必读）
    - 源语言固定 `en_US`：所有用户可见文本写入源码时用英文；中文只出现在 `.po` 的 `msgstr`，禁止写回源码。
    - 占位符统一 `%(name)s` 命名形式（`_()` 与 `_t()` 都支持），禁止按位置拼接整句。
    - 模板中夹子元素的句子（如 `<kbd>Ctrl</kbd>+<kbd>V</kbd>` 提示、含计数的「已选 N 张」）拆成完整可译片段，由 JS 侧 `_t()` 提供后 `t-esc` 输出。
    - 代码注释保持中文（不参与翻译）。

  - 验收标准
    - [ ] 四模块 Python / XML / JS / QWeb 模板中用户可见文本均为英文，无硬编码中文界面文案
    - [ ] 每模块存在 `i18n/zh_CN.po`，覆盖字段标签 / help / selection / 约束与校验报错 / 通知 / 视图与动作文案 / 前端 `_t()` 与模板术语
    - [ ] 目标环境 `odoo -d <db> -u <module> --stop-after-init` 升级 + 强刷浏览器：英文界面全部为英文
    - [ ] 安装「简体中文 (zh_CN)」并切换语言后，界面 / 报错 / 弹窗显示中文；切回英文恢复英文
    - [ ] `sale_order_no`：两种语言下 PDF 文件名与门户标题仍使用 `order_no`
    - [ ] `product_reference`（原名 `product_model`）：中文界面搜索命中参考号时列表 `name` 后缀为「（命中参考号：xxx）」，英文为 `(Matching reference: xxx)`

  - 备注
    - 跨模块需求（4 个模块同时改造），按规则 6 用 `+` 连接模块名。
    - 2026-09-07：`product_model` 已改名为 `product_reference`（`19.0.2.0.0`，模型 `product.reference.code`、字段 `reference_code*`），本条目的模块名与验收文案同步更新；升级需先执行改名 SQL，详见 [`product_reference/README.md`](product_reference/README.md) →「从 product_model 升级」。
    - 仓库内无 Odoo 运行环境，**无法自验**，需在目标环境升级后逐项确认；验证通过后整条移出本文件，信息沉淀到各模块 `CHANGELOG.md` / `README.md` / `AGENTS.md`。

  - 执行要点（下次同类需求直接照做，详见根 `AGENTS.md` 第 4 节）
    1. 盘点：`grep -rnP '[\x{4e00}-\x{9fff}]'` 扫 py/xml/js/csv，剔除注释即为待改清单；同时搜 `_t(` / `_(` 看已有入口。
    2. 改源文本为英文，占位符统一 `%(name)s`（`_()` 与 `_t()` 都支持命名占位符）。
    3. 修模板：拼接句 / 夹子元素的句子（`<kbd>`、`<t t-esc>`）下沉到 JS getter；可译文本压成单行。
    4. 写 `i18n/zh_CN.po`：键名按根 `AGENTS.md` 4.2 对照表；同一 `msgid` 只能一条，多来源合并成多 `#:` 引用。
    5. 自校验：重复 msgid 检查 + 残留中文检查 + XML/JS 语法（脚本见根 `AGENTS.md` 4.6）。
    6. 提版本并同步 5 处文档（manifest / CHANGELOG / README / 模块 AGENTS / 根 README+AGENTS+TODO）。

  - 注意事项（本次踩到的坑）
    - 最容易漏的中文在 **Python 运行期拼接**（如 `（命中参考号：%s）`）与 **动态属性**（`t-att-aria-label="'删除' + name"`），字段 `string` 之外的位置必须单独扫。
    - 术语 `.strip()` 但**保留内部换行缩进** → 多行文本节点会让 `msgid` 带换行，必须单行化。
    - 一个 `.po` 里重复 `msgid` 会导致**整份译文解析失败**，已踩（"Product Image" / "Order Number"）。
    - 前端术语有缓存，`-u` 升级后**必须强刷浏览器**才看得到新译文。
    - 只做 i18n **不需要迁移脚本**，但必须 `-u` 升级，否则新译文与新的字段标签不写库。
    - manifest 的 name/summary/description 保持英文即可（模块描述译文由 Odoo 在 `base` 的 po 集中维护，自研 po 写了也不生效）。

  - 优化建议（后续可考虑）
    - 引入 `i18n/<module>.pot` 模板或在 CI 里跑 `odoo --i18n-export` 生成 po，避免手写键名出错。

- [ ] 🚧 T-007 ｜ product_reference ｜ P1 ｜ 模块改名：`product_model` → `product_reference`（模型 `product.model.code` → `product.reference.code`，字段 `model_code*` → `reference_code*`），文案 `model` → `reference` 与 Odoo 原生「内部参考」语义对齐，配套幂等迁移脚本

  - 设计约束（动工前必读）
    - 改名范围：模块目录与技术名、模型名、字段名、约束名、方法名、xmlid、视图 / 动作 / 权限、`.po` 的 `msgid` / `msgstr` 与所有引用处的文案。
    - 中文术语随源语言改：`reference` ↔「参考号」（原「型号」）；代码注释仍保持中文。
    - 结构变更必须配套 `migrations/<版本>/pre-migration.py`，脚本幂等、只改名不删数据。
    - 模块改名 Odoo 无法自动识别，必须先手工执行改名 SQL 再 `-u` 升级（见模块 README「从 product_model 升级」）。

  - 验收标准
    - [ ] 目标库执行改名 SQL 后 `odoo -d <db> -u product_reference --stop-after-init` 不报错
    - [ ] 旧型号数据完整保留：产品「参考号」页与 `product_reference_code` 表数据与升级前一致
    - [ ] 应用列表只剩 `product_reference`，无 `product_model` 残留；`product_model` 目录已删除
    - [ ] 列表搜索框 / Many2one 下拉按参考号仍能命中，命中提示中英双语正确
    - [ ] 同产品重复参考号报错带出具体值；删除参考号行不报错；删除产品仍级联清理
    - [ ] 索引 `product_template__reference_code_index_index`（trigram）与唯一约束 `product_reference_code_reference_code_unique_per_template` 存在

  - 备注
    - 落地版本 `19.0.2.0.0`（破坏性改名，第二位 +1）；改动清单与回滚方式见 [`product_reference/CHANGELOG.md`](product_reference/CHANGELOG.md)。
    - 回滚：恢复升级前数据库备份 + 切回旧模块目录（旧版本 `19.0.1.1.0`）。
    - 仓库内无 Odoo 运行环境，**无法自验**，需在目标环境升级后逐项确认；验证通过后整条移出本文件。

- [ ] 🚧 T-008 ｜ product_reference ｜ P1 ｜ 产品「参考号」页第一行固定为 Odoo Reference（`default_code`）镜像，双向同步且不可删除

  - 设计约束（动工前必读）
    - 用 `product.reference.code.is_internal` 标识内部参考行；`_order` 用 `is_internal desc` 置顶。
    - 内部参考行随 `product.template.default_code` 创建 / 更新 / 删除而同步；修改内部参考行的 `reference_code` 要回写 `default_code`。
    - 禁止用户删除 / 归档内部参考行（`unlink` 抛 `ValidationError`；视图把 `active`、`reference_type`、`sequence`、`note` 设为 readonly）。
    - 若普通参考号行代码与 `default_code` 相同，同步时直接提升为内部参考行，避免唯一约束冲突。
    - 已有数据通过 `migrations/19.0.2.1.0/post-migration.py` 回填。

  - 验收标准
    - [ ] 在「常规信息」页填写 `Reference`，保存后「参考号」页第一行自动出现 Internal Reference 行
    - [ ] 修改「常规信息」页 `Reference`，内部参考行同步更新；清空 `Reference`，内部参考行自动消失
    - [ ] 在「参考号」页修改第一行代码，`Reference` 字段同步更新
    - [ ] 内部参考行始终排在第一，不可删除（点击删除给出中文提示）
    - [ ] 普通参考号行可正常增删改排序；同产品重复参考号仍被阻止
    - [ ] 独立参考号视图可筛选 Internal / Other References
    - [ ] 从旧版本升级后，`default_code` 非空的产品自动出现 Internal Reference 行，无重复

  - 备注
    - 落地版本 `19.0.2.1.0`（功能新增，第三位 +1）；改动清单见 [`product_reference/CHANGELOG.md`](product_reference/CHANGELOG.md)。
    - 回滚：恢复升级前数据库备份 + 切回旧版本目录（`19.0.2.0.0`）。
    - 仓库内无 Odoo 运行环境，**无法自验**，需在目标环境升级后逐项确认；验证通过后整条移出本文件。
    - 把 4.6 的自校验脚本固化为仓库脚本（如 `scripts/check_i18n.py`），提交前一键跑。
    - 若中文用户为主，可评估再加 `zh_TW` 或把默认语言配置写进部署文档，减少每次手工切语言。

> T-005（product_image 图片管理弹窗增强）已于 2026-09-06 完成并移除，落地版本 `19.0.2.4.2`；
> 完成信息（日期 / 落地版本 / 验收记录 / 异常与后续维护）见
> [`product_image/CHANGELOG.md`](product_image/CHANGELOG.md) →「交付记录（T-005）」，
> 坑点与解法见 [`product_image/AGENTS.md`](product_image/AGENTS.md) →「开发复盘与关键经验（T-005）」。

---



## 待办池

（空）

---

## 搁置 / 放弃

（空）
