{
    "name": "Product Variants",
    "version": "19.0.13.0.5",
    "summary": "Change the attributes of a product without losing a single variant: the Attributes & Variants tab shows the attribute-to-variant mapping, flags the variants that lost their combination as unmapped and holds the save until each of them is mapped again",
    "description": """
        Safe attribute changes for foreign trade SOHO scenarios: add or extend the attributes of a product and keep every existing variant.

        Source language of this module is English (en_US); a Simplified Chinese translation ships in i18n/zh_CN.po.

        Odoo warns on the product form that adding or deleting attributes deletes and recreates the existing variants and loses their customizations. This module gives the safe path, without adding any button to the product form:

        - The "Attributes & Variants" tab gets a mapping table below the attribute lines: one row per existing variant, with the combination it carries and its status;
        - As soon as an attribute change leaves a variant without a combination, that variant becomes unmapped and the table shows which value is missing, so that the user can pick it right there;
        - The save is held back while a variant is unmapped: the user maps every variant from the tab and saves again. Nothing is written in the meantime, so no variant is ever archived or deleted silently;
        - A change that would drop variants altogether (removing a value or an attribute) is refused: those variants cannot be mapped to any combination, so the tab tells what to do with them first;
        - Every existing product.product record is kept, same id: stock quants, stock move lines, lots, sales order lines, purchase order lines, invoice lines, vendor prices and reordering rules keep pointing to it;
        - The variant level data of the product (its references, its barcode, its images) is left exactly as it is: the module only maps the existing variants to their resulting combination, it never rewrites what a variant carries;
        - The mapping is recorded: a conversion log and one lineage row per variant (which record was kept, which variant derives from which original one, which values were added), plus searchable fields on the product variant (Variant Conversion, Derived From) shown on the variant form, the variant list and the variant search;
        - The conversion runs inside a savepoint with pre and post checks: if anything is not as expected, nothing at all is written.
    """,
    "category": "Inventory/Product",
    "author": "edwinhuish",
    "depends": ["product"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_template_views.xml",
        "views/product_product_views.xml",
        "views/product_variant_conversion_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "product_variant/static/src/xml/variant_mapping_panel.xml",
            "product_variant/static/src/js/variant_mapping_panel.js",
            "product_variant/static/src/js/variant_conversion_form_patch.js",
            "product_variant/static/src/scss/variant_mapping_panel.scss",
        ],
    },
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
