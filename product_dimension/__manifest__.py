{
    "name": "Product Dimensions",
    "version": "19.0.4.1.0",
    "summary": "Add a dimension unit and length / width / height per product variant, and keep the native Volume in sync",
    "description": """
        Product dimension module for foreign trade SOHO scenarios.

        Source language of this module is English (en_US); a Simplified Chinese translation ships in i18n/zh_CN.po.

        Key features:
        - Dimension unit (centimeters or meters) plus length / width / height are stored on product variants, and shown inside the native Logistics group next to the standard Volume field
        - The native Volume of a variant is recomputed from its own dimensions, so every variant of a multi-variant product keeps its own volume
        - The Volume is computed in the browser as soon as the dimensions or the unit are changed (no server round trip), rounded with the field precision and submitted with the form; the server then refrains from recomputing it, and only fills it in when dimensions are written without a volume (imports, API, variant conversion)
        - The fields are mounted on the product form and on both product variant forms (the full variant form and the variant quick-edit form opened from the "Variants" button), so a multi-variant product keeps its dimensions variant by variant
        - On the product form the fields mirror the single variant, and are hidden as soon as the product has several variants, exactly like the standard Volume field does natively
        - Dimensions follow the variants when a product is converted to a multi-variant one with the product_variant_conversion module: each new variant inherits the dimensions of the variant it derives from
        - Built-in validation keeps dimensions non-negative
        - This module replaces the former product_packing module (carton and packing fields); its template level dimension data is copied to the variants by a pre-init hook when this module is installed

        Known limitation:
        - The native Volume field is stored with the Odoo "Volume" decimal precision; the module raises it to 6 decimals on install and upgrade (only upwards), because with centimetre dimensions the factory default of 2 decimals rounds common volumes such as 20 x 20 x 20 cm (0.008 m3) to 0. Change it any time in Settings > Technical > Decimal Accuracy
        - The fields sit inside the native Logistics group, so they are visible exactly when the native Volume field is (that group is not shown to users who do not manage units of measure)
    """,
    "category": "Inventory/Product",
    "author": "edwinhuish",
    "depends": ["product"],
    "data": [
        "views/product_template_views.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "post_init_hook": "post_init_hook",
    "assets": {
        # 浏览器端即时计算体积（`web` 是 Odoo 的 auto_install 模块，实际总在；
        # 没装时只是少了界面即时计算，落库仍由后端兜底保证正确）
        "web.assets_backend": [
            "product_dimension/static/src/js/dimension_volume_rules.js",
            "product_dimension/static/src/js/dimension_volume.js",
        ],
    },
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
