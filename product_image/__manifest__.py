{
    "name": "产品图片",
    "version": "19.0.2.0.0",
    "summary": "产品多图：原位多图浏览（右侧竖排缩略图 / 悬浮放大 / 点击预览（放大缩小复制） / 粘贴新增，首图即主图",
    "description": """
        外贸 SOHO 场景下的产品多图管理模块。

        核心能力：
        - 在产品表单原有图片位置（头像区域）直接支持多图浏览，不新增页签，保持界面简洁
        - 主图放大 2 倍显示，移除上一张/下一张按钮与序号指示
        - 鼠标悬浮主图时在左侧（或下侧）显示放大的图片预览
        - 点击主图弹出全屏预览弹窗，支持放大、缩小、复制（到剪贴板）功能
        - 缩略图竖向排列于主图右侧，每张带删除按钮
        - 缩略图高度超出主图时，顶部/底部出现上下滚动按钮移动缩略图
        - 缩略图末端有上传占位符，点击即可新增图片
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
            "product_image/static/src/scss/product_image_gallery.scss",
            "product_image/static/src/js/product_image_gallery.js",
            "product_image/static/src/js/product_image_preview.js",
            "product_image/static/src/xml/product_image_gallery.xml",
            "product_image/static/src/xml/product_image_preview.xml",
        ],
    },
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
