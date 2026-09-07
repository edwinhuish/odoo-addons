{
    "name": "Product References",
    "version": "19.0.2.2.0",
    "summary": "Attach several references to one product and find the product from any of its references; the standard Odoo Reference is also editable on the References tab",
    "description": """
        Product reference management module for foreign trade SOHO scenarios.

        Source language of this module is English (en_US); a Simplified Chinese
        translation ships in i18n/zh_CN.po.

        Key features:
        - One product can carry several reference lines (customer / factory /
          alias), in addition to the standard Odoo Reference
        - The standard Odoo Reference (default_code) is displayed and editable
          directly on the References tab, so users do not need to switch back
          to General Information
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
