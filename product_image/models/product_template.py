# -*- coding: utf-8 -*-
"""扩展 product.template，挂载图库 One2many。

关键约束（详见模块 AGENTS.md L1）：
1. 图库用独立明细模型 ``product.image.gallery`` + One2many
2. 主图与图库解耦：产品主图 ``image_1920`` 由原生字段独立管理，
   图库不反向同步、不覆盖、不清空主图；前端展示时由 widget 把主图拼到序列首位
3. 不依赖 ``website_sale``，避免与 eCommerce 冲突
"""

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # ------------------------------------------------------------------
    # 字段定义
    # ------------------------------------------------------------------

    image_gallery_ids = fields.One2many(
        string="图片图库",
        comodel_name="product.image.gallery",
        inverse_name="product_tmpl_id",
        copy=True,
        help="该产品的补充图片（不含主图）。主图 image_1920 独立管理，"
        "前端展示时主图作为第一张，其余图库图片按排序跟在后面。",
    )
    image_gallery_count = fields.Integer(
        string="图片数量",
        compute="_compute_image_gallery_count",
        help="图库中的补充图片数量（不含产品主图）。",
    )

    @api.depends("image_gallery_ids")
    def _compute_image_gallery_count(self):
        for tmpl in self:
            tmpl.image_gallery_count = len(tmpl.image_gallery_ids)
