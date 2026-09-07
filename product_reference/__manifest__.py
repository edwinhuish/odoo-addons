{
    "name": "Product References",
    "version": "19.0.2.1.0",
    "summary": "Attach several references to one product (customer reference / factory reference / alias) and find the product from any of its references, both in lists and when selecting a product",
    "description": """
        Product reference management module for foreign trade SOHO scenarios.

        Source language of this module is English (en_US); a Simplified Chinese
        translation ships in i18n/zh_CN.po.

        Key features:
        - One product can carry several reference lines (internal / customer /
          factory / alias); the first line mirrors the standard Odoo Reference
          (default_code) and cannot be deleted
        - The Odoo Reference shown in the General Information tab is kept in
          sync with the internal reference row on the References tab
        - References live in a dedicated line model exposed as a One2many on
          product.template; they are never squeezed into a comma separated Char
        - A reference cannot be repeated inside the same product; different
          products may share the same reference
        - Search happens in the database: the stored redundant field
          reference_code_index is backed by a trigram index
        - Many2one dropdowns, search suggestions, quick search and the list
          search box all find a product by any of its references
        - When a reference is hit, the result shows
          "Product (Matching reference: xxx)" so products can be told apart
        - Reference lines can be added, edited, deleted and reordered, and
          several lines can be pasted at once
        - Reference lines are removed with the product, no orphan data
    """,
    "category": "Inventory/Product",
    "author": "edwinhuish",
    "depends": ["product"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_template_views.xml",
        "views/product_reference_code_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
