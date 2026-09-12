{
    "name": "Sale Product Hover",
    "version": "19.0.1.0.2",
    "summary": "Show a product detail popover when hovering order lines in quotations and sales orders",
    "description": """
        Product hover preview for quotation and sales order lines, for foreign
        trade SOHO scenarios.

        Source language of this module is English (en_US); a Simplified Chinese
        translation ships in i18n/zh_CN.po.

        Key features:
        - Hovering an order line opens a popover with the product image, name,
          reference, sales description, prices and available quantity
        - Quotations and sales orders are covered alike: they share the same
          model and the same view
        - Data is fetched with one batch payload per list page and cached in the
          browser, so hovering a line never triggers an extra request
        - The popover opens after a short delay, closes when the pointer leaves
          the line, and can be entered with the pointer before it closes
        - Normal row behaviour is untouched: click to open, inline edit,
          selection and deletion keep working as before
        - Only sales order lines are targeted; other list views are untouched
        - No new model, no new field and no extra access right is introduced
    """,
    "category": "Sales/Sales",
    "author": "edwinhuish",
    "depends": ["sale", "stock"],
    "assets": {
        "web.assets_backend": [
            "sale_product_hover/static/src/js/product_hover_cache.js",
            "sale_product_hover/static/src/js/product_hover_card.js",
            "sale_product_hover/static/src/js/product_hover_list_patch.js",
            "sale_product_hover/static/src/xml/product_hover_templates.xml",
            "sale_product_hover/static/src/scss/product_hover.scss",
        ],
    },
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
