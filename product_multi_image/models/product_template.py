# -*- coding: utf-8 -*-
"""扩展 product.template，挂载图库 One2many 并维护主图同步。

关键约束（详见模块 AGENTS.md L1）：
1. 图库用独立明细模型 ``product.image.gallery`` + One2many
2. 首图（排序最前）自动同步到产品主图 ``image_1920``，保留与原生主图的关系
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
        help="该产品的所有图片；首图（排序最前）自动作为产品主图。",
    )
    image_gallery_count = fields.Integer(
        string="图片数量",
        compute="_compute_image_gallery_count",
    )

    @api.depends("image_gallery_ids")
    def _compute_image_gallery_count(self):
        for tmpl in self:
            tmpl.image_gallery_count = len(tmpl.image_gallery_ids)

    # ------------------------------------------------------------------
    # 主图同步入口：供 product.image.gallery 的 unlink 调用
    # ------------------------------------------------------------------

    def _sync_main_image_from_template(self):
        """图库增删改后，把首图同步到产品主图 ``image_1920``。

        由 ``product.image.gallery`` 的 create/write/unlink 触发；
        此处只负责按当前图库状态刷新主图，不反向触发图库改动。
        """
        for tmpl in self:
            main = tmpl.image_gallery_ids.filtered("active")._get_main_image()
            if main:
                tmpl.image_1920 = main.image_1920
            else:
                tmpl.image_1920 = False
