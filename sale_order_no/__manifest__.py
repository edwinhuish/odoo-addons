{
    "name": "Order Number",
    "version": "19.0.1.8.0",
    "summary": "Order numbers built from the customer code plus the year, with manual editing, bulk numbering, a global uniqueness check and custom PDF file names and portal titles",
    "description": """
        Sales order / quotation numbering module for foreign trade SOHO
        scenarios.

        Source language of this module is English (en_US); a Simplified Chinese
        translation ships in i18n/zh_CN.po.

        Numbering rule: customer code + two digit year + customer sequence of the
        year
        - Quotations and sales orders share the same numbering: DZ2602

        Key features:
        - The native reference is never modified: SOxxxx stays the internal key
        - The stored field order_no is used for customer facing documents,
          printouts and the form title
        - order_no is generated at creation and can still be edited manually
        - Uniqueness is checked on save, with a database UNIQUE constraint as a
          safety net
        - Numbers that are already taken (imported history, manual changes,
          duplicated documents) are skipped automatically
        - display_name shows order_no first, so Many2one fields, dropdowns,
          search suggestions and page titles stay consistent
        - Many2one dropdowns and the quick search find an order by its number
        - The list API (web_search_read) returns order_no as the name field
        - Sequence numbers are assigned once at creation and are never
          recomputed when other documents change
        - The customer code is snapshotted at creation, so editing the customer
          does not affect historical documents
        - The year is read straight from date_order, no extra snapshot
        - The customer code format is validated (uppercase letters only) and is
          uppercased on save
        - The list view offers a "Generate Order Number" bulk action
        - Print preview and the PDF body show the order number, falling back to
          the system reference when none is assigned
        - The PDF file name is overridden on three report actions
          (sale.action_report_saleorder / sale.action_report_pro_forma_invoice /
          sale_pdf_quote_builder.action_report_saleorder_raw); the order number is
          used in every language
        - The customer portal breadcrumb and H2 title also use the order number
    """,
    "category": "Sales",
    "author": "edwinhuish",
    "depends": ["sale", "sale_pdf_quote_builder"],
    "data": [
        "views/partner_views.xml",
        "views/sale_order_views.xml",
        "views/portal_templates_inherit.xml",
        "data/sale_order_actions.xml",
        "reports/report_saleorder.xml",
    ],
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
