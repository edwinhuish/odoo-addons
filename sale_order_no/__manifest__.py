{
    "name": "订单编号",
    "version": "19.0.1.5.2",
    "summary": "按客户编码+年份生成订单编号，支持手动编辑、批量补号、全局唯一校验、PDF文件名与门户预览定制",
    "description": """
        外贸SOHO场景下的销售订单/报价单编号定制模块。

        编号规则：客户编码 + 两位年份 + 客户本年度流水号
        - 报价单和销售订单统一编号：DZ2602

        核心特性：
        - 不修改系统原生 reference，保留 SOxxxx 作为内部主键
        - 新增 order_no 存储字段用于对外展示、打印和详情页标题
        - order_no 创建时自动生成，同时支持手动编辑
        - 保存时校验全局唯一性，数据库层另有 UNIQUE 约束兜底
        - 自动避让已被占用的编号（历史导入、手动改号、复制单据）
        - display_name 优先显示 order_no，Many2one/下拉/搜索建议/页面标题一致
        - Many2one 下拉与快速搜索可按订单编号命中
        - 列表 API (web_search_read) 返回的 name 字段统一替换为 order_no
        - 流水号创建时一次性分配，后续不会因其他单据变动而重算
        - 客户编码在创建时快照，修改客户信息不影响历史单据
        - 年份直接从 date_order 读取，不再单独快照
        - 客户编码格式校验（仅允许大写英文字母），保存时自动转大写
        - 列表视图提供"生成订单编号"批量补号动作
        - 打印预览与PDF正文优先显示订单编号，未分配时回退到系统编号
        - PDF文件名（报价单/订单/形式发票）包含订单编号，替代原生SOxxxx命名规则
        - 客户门户预览页面的面包屑与 H2 标题也使用订单编号
    """,
    "category": "Sales",
    "author": "SOHO外贸",
    "depends": ["sale"],
    "data": [
        "views/partner_views.xml",
        "views/sale_order_views.xml",
        "views/portal_templates_inherit.xml",
        "data/sale_order_actions.xml",
        "reports/report_saleorder.xml",
    ],
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
