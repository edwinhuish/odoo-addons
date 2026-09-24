{
    "name": "Product References",
    "version": "19.0.3.1.0",
    "summary": "Attach several references to one product and find the product from any of its references; the standard Odoo Reference is edited right under the product name and the extra references are managed from the + button inside it (on a product with several variants it is the product reference, and every variant keeps its own set as well)",
    "description": """
        Product reference management module for foreign trade SOHO scenarios.

        Source language of this module is English (en_US); a Simplified Chinese
        translation ships in i18n/zh_CN.po.

        Key features:
        - The standard Odoo Reference (default_code) is edited directly under the
          product name, on both the product form and the product variant form;
          no extra tab is added to the product form
        - The "+" button inside the Reference field opens a dialog listing the
          extra references of the product (or of the variant on a variant form):
          add, edit, reorder, disable and delete lines; changes are kept on the
          form record and are written when the record is saved (a brand new
          product can get references right away)
        - A product with several variants keeps its references on two
          independent levels, both visible at the same time: the product form
          maintains the product reference and the product references, while
          every variant also keeps its own set (like the variant image gallery)
        - The product reference of such a product (e.g. G001 for the variants
          G001-WT and G001-BK) is stored on the template and computed into the
          native Reference field, so the product form, the product list, the
          searches and the product cards show it without any other module
          knowing about this one; on a single-variant product the product
          reference and the variant reference are kept equal
        - When a product carries extra references, a "+N" badge appears next to
          the button and hovering it shows the list of references in a tooltip
        - References live in a dedicated line model exposed as a One2many on
          product.template; they are never squeezed into a comma separated Char
        - A reference cannot be repeated inside the same product; different
          products may share the same reference
        - Search happens in the database: the stored redundant fields
          reference_code_index (product references) and
          variant_reference_code_index (variant references) are backed by trigram
          indexes; searching a product by the reference of one of its variants
          also finds the product
        - Many2one dropdowns, search suggestions, quick search and the list
          search box all find a product by any of its references, and by the
          product reference of a product with several variants
        - When a reference is hit, the result shows
          "Product (Matching reference: xxx)" so products can be told apart
        - Reference lines are removed with the product, no orphan data
        - References are stored in uppercase: what you type in the form (or import from a file) is uppercased right away
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
