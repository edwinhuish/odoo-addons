{
    "name": "Product Card View",
    "version": "19.0.1.0.1",
    "summary": "Masonry product card view with image carousel and variant switcher",
    "description": """
        Modern product list card view for foreign trade SOHO scenarios.

        Source language: English (en_US); Simplified Chinese translation in i18n/zh_CN.po.

        Features:
        - Dedicated "Product Cards" action in Inventory, official views untouched
        - Card with main image carousel (arrows + swipe), title, reference, on hand
        - Multi-image sources follow product_image (template + per-variant, never mixed)
        - Variant switcher on the card for multi-variant products
        - Masonry (waterfall) responsive multi-column layout
    """,
    "category": "Inventory/Product",
    "author": "edwinhuish",
    "depends": ["product_image", "stock", "sale", "purchase"],
    "data": [
        "views/product_card_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "product_card_view/static/src/js/product_card_view.js",
            "product_card_view/static/src/js/product_card_model.js",
            "product_card_view/static/src/js/product_card_renderer.js",
            "product_card_view/static/src/js/product_card_record.js",
            "product_card_view/static/src/xml/product_card_templates.xml",
            "product_card_view/static/src/scss/product_card.scss",
        ],
    },
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
