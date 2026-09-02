{
    "name": "产品多图",
    "version": "19.0.1.0.0",
    "summary": "产品图库：多图并存、拖拽排序、首图即主图，图库内粘贴即新增",
    "description": """
        外贸 SOHO 场景下的产品多图管理模块。

        核心能力：
        - 一个产品可挂载多张图片，独立明细模型 + One2many 挂在 product.template 上
        - 每张图片继承 image.mixin，自动生成多尺寸（1920/1024/512/256/128）
        - 首图（排序最前）自动同步到产品主图 image_1920，保留与原生主图的关系
        - 图库内支持拖拽排序，首图即主图
        - 图库区域支持粘贴图片即新增一条记录（联动 image_uploader 的粘贴能力）
        - 产品列表/看板展示主图（原生 image_128 即主图缩略）
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
            "product_multi_image/static/src/js/image_gallery_paste.js",
            "product_multi_image/static/src/xml/image_gallery_paste.xml",
        ],
    },
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
