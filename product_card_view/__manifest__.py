{
    "name": "Product Card View",
    "version": "19.0.1.0.1",
    "summary": "Masonry product card view with image carousel and variant switcher",
    "description": """
        Modern product list card view for foreign trade SOHO scenarios.

        Source language of this module is English (en_US); a Simplified Chinese
        translation ships in i18n/zh_CN.po.

        Key features:
        - A dedicated "Product Cards" action (independent menu inside Inventory,
          official product list/kanban views are left untouched)
        - Each card shows the product main image on top, with left/right arrows
          and swipe gestures to browse multiple images
        - Multi-image sources follow product_image: template main image plus the
          template shared gallery, and per-variant main image plus its own
          gallery once a variant is selected (the two sets never mix)
        - Under the image, the card shows title, reference (default_code) and
          on hand quantity
        - For multi-variant products a variant switcher is rendered on the card
          (one row per attribute); picking a variant instantly switches image,
          reference and on hand to that variant
        - Masonry (waterfall) layout: cards of different heights flow into a
          responsive multi-column grid
    """,
    "category": "Inventory/Product",
    "author": "edwinhuish",
    "depends": ["product_image", "stock"],
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
