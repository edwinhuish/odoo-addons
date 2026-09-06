# -*- coding: utf-8 -*-
"""产品图片明细模型。

一个产品可挂多张补充图片，每张继承 ``image.mixin`` 自动生成多尺寸。

主图与图库完全解耦（详见模块 AGENTS.md L1 约束 4）：
- 产品主图 ``product.template.image_1920`` 由原生字段独立管理，列表 / 看板 / 报价单展示它
- 图库 ``product.image.gallery`` 只存补充图，**不反向同步、不覆盖、不清空**产品主图
- 前端 widget 展示时把「原生主图」作为浏览序列的第一张，其余图库图片按 ``sequence`` 跟在后面
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductImageGallery(models.Model):
    """产品图片明细（补充图）。

    设计要点：
    - 继承 ``image.mixin``，复用 Odoo 原生多尺寸（1920/1024/512/256/128）与 webp 转换链路
    - 模型名 ``product.image.gallery``，刻意避开 ``website_sale`` 的 ``product.image``
      使本模块可在不依赖 ``website_sale`` 的环境独立安装，且不与 eCommerce 冲突
    - 与产品主图解耦：本模型不写产品主图，前端展示时由 widget 把主图拼到序列首位
    - 删除产品时图片行随产品级联删除（``ondelete='cascade'``）
    """

    _name = "product.image.gallery"
    _description = "Product Image"
    _inherit = ["image.mixin"]
    _order = "sequence, id"

    name = fields.Char(
        string="Name",
        help="Short description of the image (optional), used for internal identification, "
             "e.g. \"Front\", \"Detail\", \"Packaging\".",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Lower values come first. Display order of the gallery images in the "
             "thumbnail list (the main image always stays first).",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to disable an image without deleting it, so historical material is kept.",
    )
    note = fields.Char(
        string="Note",
        help="Additional information about this image.",
    )

    product_tmpl_id = fields.Many2one(
        string="Product",
        comodel_name="product.template",
        ondelete="cascade",
        required=True,
        index=True,
        help="Product template this image belongs to; images are removed together with the product.",
    )

    # ------------------------------------------------------------------
    # 约束：同一产品内图片名称不可重复（便于识别）
    # ------------------------------------------------------------------

    @api.constrains("name", "product_tmpl_id")
    def _check_name_unique_per_template(self):
        """Raise a readable error when the image name is duplicated within a product.

        The name is optional, but once filled it must be unique inside the same
        product so images stay identifiable in the gallery.
        """
        for record in self:
            if not record.name or not record.product_tmpl_id:
                continue
            duplicate = self.sudo().search([
                ("product_tmpl_id", "=", record.product_tmpl_id.id),
                ("name", "=", record.name),
                ("id", "!=", record.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'The image name "%(name)s" already exists for product "%(product)s". '
                    "Image names must be unique within the same product.",
                    name=record.name,
                    product=record.product_tmpl_id.display_name,
                ))
