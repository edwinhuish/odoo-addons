{
    "name": "产品多图",
    "version": "19.0.1.0.0",
    "summary": "产品多图：原位多图浏览（不新增页签）/ 左右切换 / 缩略图 / 粘贴新增，首图即主图",
    "description": """
        外贸 SOHO 场景下的产品多图管理模块。

        核心能力：
        - 在产品表单原有图片位置（头像区域）直接支持多图浏览，不新增页签，保持界面简洁
        - 多图并存、左右切换、缩略图条、计数指示（如 2/5）
        - 上传即新增一条图库记录并设为当前图；删除当前图后自动切换相邻图
        - 头像区域支持粘贴图片即新增一条记录（内建，无需 image_uploader 依赖）
        - 每张图片继承 image.mixin，自动生成多尺寸（1920/1024/512/256/128）
        - 首图（排序最前）自动同步到产品主图 image_1920，保留与原生主图的关系
        - 产品列表/看板/报价单展示主图（原生 image_128 即主图缩略）
        - 删除产品时图片行级联清理，无孤儿数据
        - 仅依赖 product，不依赖 website_sale，避免与 eCommerce 冲突
    """,
    "category": "Inventory/Product",
    "author": "SOHO外贸",
    "depends": ["product"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_template_views.xml",
        "views/product_image_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "product_multi_image/static/src/js/product_image_gallery.js",
            "product_multi_image/static/src/xml/product_image_gallery.xml",
        ],
    },
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
