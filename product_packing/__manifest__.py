{
    "name": "Product Packing",
    "version": "19.0.1.1.3",
    "summary": "Add packing/carton fields (units per carton, dimensions, gross/net weight, auto CBM) to the product Inventory tab",
    "description": """
        Product carton packing module for foreign trade SOHO scenarios.

        Source language of this module is English (en_US); a Simplified Chinese
        translation ships in i18n/zh_CN.po.

        Key features:
        - Adds carton packing fields on product.template, displayed inside the
          standard Inventory tab so users do not leave the product form
        - Units per carton, carton length / width / height, gross weight and
          net weight are all editable and saved with the product
        - Carton dimension unit can be set per product to centimeters or meters
        - CBM is computed automatically from the dimensions and shown as a
          read-only field
        - A human-readable carton dimension spec (e.g. "50 x 40 x 30 cm") is
          also computed and available in list views as an optional column
        - Built-in validation keeps numbers non-negative and ensures net weight
          does not exceed gross weight
    """,
    "category": "Inventory/Product",
    "author": "edwinhuish",
    "depends": ["product"],
    "data": [
        "views/product_template_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
