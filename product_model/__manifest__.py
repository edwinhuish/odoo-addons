{
    "name": "Product Models",
    "version": "19.0.1.1.0",
    "summary": "Attach several models to one product (customer model / factory model / alias) and find the product from any of its models, both in lists and when selecting a product",
    "description": """
        Product model management module for foreign trade SOHO scenarios.

        Source language of this module is English (en_US); a Simplified Chinese
        translation ships in i18n/zh_CN.po.

        Key features:
        - One product can carry several model lines (customer / factory / alias)
        - Models live in a dedicated line model exposed as a One2many on
          product.template; they are never squeezed into a comma separated Char
        - A model cannot be repeated inside the same product; different products
          may share the same model
        - Search happens in the database: the stored redundant field
          model_code_index is backed by a trigram index
        - Many2one dropdowns, search suggestions, quick search and the list
          search box all find a product by any of its models
        - When a model is hit, the result shows "Product (Matching model: xxx)"
          so products can be told apart
        - Model lines can be added, edited, deleted and reordered, and several
          lines can be pasted at once
        - Model lines are removed with the product, no orphan data
    """,
    "category": "Inventory/Product",
    "author": "edwinhuish",
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
