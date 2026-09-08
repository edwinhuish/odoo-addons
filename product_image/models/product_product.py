# -*- coding: utf-8 -*-
"""扩展 product.product（变体），挂载变体专属图库 One2many。

``product.product`` 通过 ``_inherits = {'product.template': 'product_tmpl_id'}`` 自动继承
模板上的全部字段，因此模板图库 ``image_gallery_ids``（反向到 ``product_tmpl_id``）对所有
变体共享、在模板表单维护。为了让**每个变体各自维护一组独立补充图**，这里另挂一个反向到
``product_id`` 的 One2many；两条链路的数据互不干扰：
- 模板共享补充图：``product.template.image_gallery_ids``（product 入口维护）
- 变体专属补充图：``product.product.variant_image_gallery_ids``（变体编辑表单维护）

主图仍是变体上原生计算字段 ``image_1920``（无变体专属主图时自动回退模板主图），写入沿用
原生 inverse（``_set_image_1920`` / ``_set_template_field``），本模块不做任何覆盖。
"""

from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    variant_image_gallery_ids = fields.One2many(
        string="Variant Image Gallery",
        comodel_name="product.image.gallery",
        inverse_name="product_id",
        copy=False,
        help="Additional images specific to this product variant, independent from the shared "
        "template gallery. In the variant form the main image (which falls back to the template "
        "main image when the variant has none) comes first and these images follow in sequence "
        "order.",
    )
