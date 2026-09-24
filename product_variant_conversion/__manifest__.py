{
    "name": "Product Variant Conversion",
    "version": "19.0.6.1.0",
    "summary": "Add attributes to a product and keep every existing variant: saving the product form asks for the variant ownership, keeps every variant record (with its stock, orders and invoices) and records the origin of each variant",
    "description": """
        Safe attribute addition and variant expansion for foreign trade SOHO
        scenarios.

        Source language of this module is English (en_US); a Simplified Chinese
        translation ships in i18n/zh_CN.po.

        Odoo warns on the product form that adding or deleting attributes deletes
        and recreates the existing variants and loses their customizations. This
        module gives the safe path, without adding any button to the product form:

        - The user edits the attributes as usual ("Attributes & Variants" tab) and
          saves: the save itself detects whether the change affects the existing
          variants;
        - When it creates new variants, a modal dialog asks, for every resulting
          combination, which existing variant record keeps it (pre-filled with
          what would happen without any mapping); the save does not go through
          before the ownership is confirmed;
        - When it would drop existing variants (removing a value or an attribute),
          the save is refused, so no variant is ever archived or deleted silently;
        - Every existing product.product record is kept, same id: stock quants,
          stock move lines, lots, sales order lines, purchase order lines,
          invoice lines, vendor prices and reordering rules keep pointing to it;
        - The variant level data of the product (its references, its barcode,
          its images) is left exactly as it is: the conversion only maps the
          existing variants to their resulting combination, it never rewrites
          what a variant carries;
        - The ownership is recorded: a conversion log and one lineage row per
          variant (which record was kept, which variant derives from which
          original one, which values were added), plus searchable fields on the
          product variant (Variant Conversion, Derived From) shown on the variant
          form, the variant list and the variant search;
        - The conversion runs inside a savepoint with pre and post checks: if
          anything is not as expected, nothing at all is written.
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
            "product_variant_conversion/static/src/xml/variant_conversion_dialog.xml",
            "product_variant_conversion/static/src/js/variant_conversion_dialog.js",
            "product_variant_conversion/static/src/js/variant_conversion_form_patch.js",
        ],
    },
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
