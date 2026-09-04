{
    "name": "产品图片",
    "version": "19.0.2.2.2",
    "summary": "产品多图：原生主图独立 + 图库补充图（主图作为浏览序列首张，图库按序其后），原位多图浏览 / 悬浮放大 / 点击预览（放大缩小旋转）/ 粘贴新增",
    "description": """
        外贸 SOHO 场景下的产品多图管理模块。

        核心能力：
        - 在产品表单原有图片位置（头像区域）直接支持多图浏览，不新增页签，保持界面简洁
        - 主图与图库解耦：产品主图 image_1920 由原生字段独立管理，列表 / 看板 / 报价单展示它，图库不覆盖 / 不清空
        - 浏览序列：原生主图（若有）作为第一张，其余图库图片按 sequence 跟在后面
        - 主图放大 2 倍显示，移除上一张/下一张按钮与序号指示
        - 鼠标悬浮主图时在左侧（或下侧）显示放大的图片预览
        - 点击主图弹出全屏预览弹窗，支持放大、缩小、重置、旋转（按钮 + 滚轮 + 键盘）
        - 缩略图竖向排列于主图右侧：主图项带替换/清空按钮，图库项带删除按钮，末端有上传占位符
        - 缩略图高度超出主图时，顶部/底部出现上下滚动按钮移动缩略图
        - 头像区域支持粘贴图片即新增一条图库记录（内建，无需 image_uploader 依赖）
        - 每张图片继承 image.mixin，自动生成多尺寸（1920/1024/512/256/128）
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
            "product_image/static/src/js/product_image_upload.js",
            "product_image/static/src/xml/product_image_gallery.xml",
            "product_image/static/src/xml/product_image_preview.xml",
            "product_image/static/src/xml/product_image_upload.xml",
        ],
    },
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
