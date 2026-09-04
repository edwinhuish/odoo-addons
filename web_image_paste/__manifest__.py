{
    "name": "图片粘贴上传",
    "version": "19.0.2.0.0",
    "summary": "后台图片字段支持剪贴板 Ctrl+V / Cmd+V 粘贴与拖拽上传，一次可粘贴多图，超大图明确报错",
    "description": """
        外贸 SOHO 场景下的图片录入增强模块。

        核心能力：
        - 图片字段（ImageField）在编辑态获得焦点后，Ctrl+V / Cmd+V 可直接粘贴剪贴板图片上传
        - 支持把图片文件拖拽到图片区域完成上传
        - 一次粘贴 / 拖拽可上传多张图片（仅对支持多图上传的控件生效）
        - 上传中显示进度提示，完成后自动刷新预览
        - 超过服务器最大上传尺寸的图片给出明确的中文报错，带出具体大小
        - 只读态不触发上传；剪贴板无图片时不拦截普通文本粘贴
        - 完全复用 Odoo 原生上传链路（FileUploader.onFileChange → getDataURLFromFile → onUploaded），
          不改核心模板文件，只通过 @web/core/utils/patch 与 t-inherit 扩展
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
