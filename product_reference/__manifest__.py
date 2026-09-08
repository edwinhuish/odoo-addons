{
    "name": "Product References",
    "version": "19.0.2.3.0",
    "summary": "Attach several references to one product and find the product from any of its references; the standard Odoo Reference is edited right under the product name and the extra references are managed from the + button next to it",
    "description": """
        Product reference management module for foreign trade SOHO scenarios.

        Source language of this module is English (en_US); a Simplified Chinese
        translation ships in i18n/zh_CN.po.

        Key features:
        - The standard Odoo Reference (default_code) is edited directly under the
          product name, on both the product form and the product variant form;
          no extra tab is added to the product form
        - The "+" button next to the Reference field opens a dialog listing the
          extra references of the product: add, edit, reorder, disable and delete
          lines; changes are kept on the product form and are written when the
          product is saved (a brand new product can get references right away)
        - When a product carries extra references, a "+N" badge appears next to
          the button and hovering it shows the list of references in a tooltip
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
        - Reference lines are removed with the product, no orphan data
    """,
    "category": "Inventory/Product",
    "author": "edwinhuish",
    "depends": ["product"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_template_views.xml",
        "views/product_product_views.xml",
        "views/product_reference_code_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "product_reference/static/src/scss/product_reference.scss",
            "product_reference/static/src/js/product_reference_manage.js",
            "product_reference/static/src/js/product_reference_editor.js",
            "product_reference/static/src/xml/product_reference_editor.xml",
            "product_reference/static/src/xml/product_reference_manage.xml",
        ],
    },
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
