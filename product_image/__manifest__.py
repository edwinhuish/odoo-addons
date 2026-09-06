{
    "name": "Product Images",
    "version": "19.0.2.5.0",
    "summary": "Multiple product images: the native main image stays independent and the gallery holds the extra images (the main image is the first one in the browsing sequence). In-place browsing / hover zoom / click to preview (zoom, rotate) / paste to add / management dialog with drag & drop reordering, delete confirmation and bulk delete",
    "description": """
        Product image management module for foreign trade SOHO scenarios.

        Source language of this module is English (en_US); a Simplified Chinese
        translation ships in i18n/zh_CN.po.

        Key features:
        - Multi-image browsing directly at the native image position (avatar area)
          of the product form; no extra tab, the UI stays clean
        - The main image and the gallery are decoupled: the product main image
          image_1920 is managed by the native field and is the one shown in
          lists / kanban / quotations; the gallery never overwrites nor clears it
        - Browsing sequence: the native main image (if any) comes first, the other
          gallery images follow, ordered by sequence
        - The main image is displayed at twice its size; no previous/next buttons
          and no position indicator
        - Hovering the main image shows an enlarged preview on the left (or below)
        - Clicking the main image opens a full screen preview with zoom in, zoom
          out, reset and rotate (buttons + mouse wheel + keyboard)
        - Thumbnails are stacked vertically on the right of the main image for
          switching (no delete button in edit mode); when the thumbnails are
          taller than the main image, scroll buttons appear at the top/bottom
        - Clicking the "+" at the end of the thumbnail column opens the image
          management dialog: top half is a large preview (preview only, no delete
          button; the name row stays empty when the main image is selected) plus a
          tiled thumbnail grid (every thumbnail, including the main image, has a
          top-right × that asks for a confirmation: deleting a gallery image
          deletes the record, deleting the main image promotes the first gallery
          image; thumbnails can be dragged to reorder, including the main image:
          dropping an image at the first position makes it the main image, the
          first position is always the main image; clicking a thumbnail only
          changes the large preview inside the dialog, not the page main image;
          the large preview has a fixed size and the grid fills the remaining
          space, scrolling internally when it overflows); bottom half is an
          upload dropzone (click / drag & drop / Ctrl+V paste, in-progress
          uploads show a local thumbnail and a spinner, the dialog does not close
          after a paste, uploading does not change the large image currently
          displayed on the page; built-in, no dependency on web_image_paste);
          the top-right of the modal header offers a "bulk delete" check mode and
          a confirmation dialog listing every selected image thumbnail is shown
          before deleting; the close button is the rightmost square button of the
          header and turns red on hover
        - Every image inherits image.mixin, so all sizes (1920/1024/512/256/128)
          are generated automatically
        - Gallery lines are removed with the product, no orphan data
        - Depends on product only, not on website_sale, to avoid conflicts with
          eCommerce
    """,
    "category": "Inventory/Product",
    "author": "edwinhuish",
    "depends": ["product"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_template_views.xml",
        "views/product_image_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "product_image/static/src/scss/product_image_gallery.scss",
            "product_image/static/src/js/product_image_gallery.js",
            "product_image/static/src/js/product_image_preview.js",
            "product_image/static/src/js/product_image_manage.js",
            "product_image/static/src/xml/product_image_gallery.xml",
            "product_image/static/src/xml/product_image_preview.xml",
            "product_image/static/src/xml/product_image_manage.xml",
        ],
    },
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
