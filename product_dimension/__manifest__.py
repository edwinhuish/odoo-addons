{
    "name": "Product Dimensions",
    "version": "19.0.2.0.1",
    "summary": "Add a dimension unit and length / width / height per product variant, and keep the native Volume in sync",
    "description": """
        Product dimension module for foreign trade SOHO scenarios.

        Source language of this module is English (en_US); a Simplified Chinese translation ships in i18n/zh_CN.po.

        Key features:
        - Dimension unit (centimeters or meters) plus length / width / height are stored on product variants, and shown inside the native Logistics group of the product form next to the standard Volume field
        - The native Volume of a variant is recomputed from its own dimensions, so every variant of a multi-variant product keeps its own volume
        - On the product form the fields mirror the single variant, and are hidden as soon as the product has several variants, exactly like the standard Volume field does natively
        - Dimensions follow the variants when a product is converted to a multi-variant one with the product_variant_conversion module: each new variant inherits the dimensions of the variant it derives from
        - Built-in validation keeps dimensions non-negative
        - This module replaces the former product_packing module (carton and packing fields); its template level dimension data is copied to the variants by a pre-init hook when this module is installed

        Known limitation:
        - The native Volume field is stored with the Odoo "Volume" decimal precision (2 decimals by default), so volumes below 0.01 cubic meter are rounded to 0; raise that decimal precision in Settings > Technical > Decimal Accuracy if your products are that small
    """,
    "category": "Inventory/Product",
    "author": "edwinhuish",
    "depends": ["product"],
    "data": [
        "views/product_template_views.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
