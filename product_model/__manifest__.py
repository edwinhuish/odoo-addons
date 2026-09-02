{
    "name": "产品多型号",
    "version": "19.0.1.0.0",
    "summary": "一个产品可挂多个型号（客户型号/工厂型号/别名），列表与选产品时按任一型号可搜到对应产品",
    "description": """
        外贸 SOHO 场景下的产品多型号管理模块。

        核心能力：
        - 一个产品可挂载多个型号明细（客户型号 / 工厂型号 / 别名等）
        - 型号用独立明细模型 + One2many 挂在 product.template 上，禁止逗号分隔塞进单个 Char
        - 型号在同一产品内不允许重复；不同产品间允许同型号
        - 搜索能力在数据库层实现：冗余可存储字段 model_code_index 配合 trigram 索引
        - Many2one 下拉、搜索建议、快速搜索、列表搜索框均可按任一型号命中对应产品
        - 命中型号时，搜索结果显示「产品名（命中型号：xxx）」，便于区分
        - 型号行支持增删改排序，支持批量粘贴多行录入
        - 删除产品时型号行级联清理，无孤儿数据
    """,
    "category": "Inventory/Product",
    "author": "SOHO外贸",
    "depends": ["product"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_template_views.xml",
        "views/product_model_code_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
