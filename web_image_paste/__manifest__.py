{
    "name": "Image Paste Upload",
    "version": "19.0.2.1.0",
    "summary": "Image fields in the backend accept Ctrl+V / Cmd+V paste and drag & drop: several images at once, with a clear error when a file is too large",
    "description": """
        Image capture enhancement module for foreign trade SOHO scenarios.

        Source language of this module is English (en_US); a Simplified Chinese
        translation ships in i18n/zh_CN.po.

        Key features:
        - Once an image field (ImageField) has focus, Ctrl+V / Cmd+V pastes the
          clipboard image and uploads it
        - Image files can also be dragged onto the image area to upload them
        - One paste / drop may upload several images (only for widgets that
          support multiple uploads)
        - A progress hint is displayed while uploading and the preview is
          refreshed when it is done
        - Images larger than the maximum server upload size raise a clear error
          that includes the actual size
        - Read-only mode never triggers an upload; a clipboard without images
          does not block normal text pasting
        - The native Odoo upload pipeline is fully reused
          (FileUploader.onFileChange → getDataURLFromFile → onUploaded); no core
          template is modified, everything is done with
          @web/core/utils/patch and t-inherit
    """,
    "category": "Productivity/Images",
    "author": "edwinhuish",
    "depends": ["web"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "web_image_paste/static/src/js/image_field_paste.js",
            "web_image_paste/static/src/xml/image_field_paste.xml",
            "web_image_paste/static/src/scss/web_image_paste.scss",
        ],
    },
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
