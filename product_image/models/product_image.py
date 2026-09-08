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
        index=True,
        help="Product template (shared gallery) this image belongs to. Either this field or "
             "'Product Variant' must be set: template images are shared by all the variants "
             "and are removed together with the product.",
    )
    product_id = fields.Many2one(
        string="Product Variant",
        comodel_name="product.product",
        ondelete="cascade",
        index=True,
        help="Product variant this image belongs to (variant gallery, independent from the "
             "shared template gallery). Either this field or 'Product' must be set; the "
             "image is removed together with the variant.",
    )

    # ------------------------------------------------------------------
    # 约束：图片必须归属产品或变体（二选一）；同一归属内图片名称不可重复
    # ------------------------------------------------------------------

    @api.constrains("product_tmpl_id", "product_id")
    def _check_single_owner(self):
        """Each gallery image belongs either to a product or to a product variant.

        Variant images are stored independently (only ``product_id``) so that the
        shared template gallery ``product_tmpl_id`` is never polluted; template
        images only set ``product_tmpl_id``. An image without owner or with both
        owners is rejected with a readable error.
        """
        for record in self:
            if not record.product_tmpl_id and not record.product_id:
                raise ValidationError(_(
                    "An image must belong either to a product (shared gallery) or to a "
                    "product variant (variant gallery)."
                ))
            if record.product_tmpl_id and record.product_id:
                raise ValidationError(_(
                    "An image cannot belong to both a product and a product variant: "
                    "choose either the shared product gallery or the variant gallery."
                ))

    @api.constrains("name", "product_tmpl_id", "product_id")
    def _check_name_unique_per_owner(self):
        """Raise a readable error when the image name is duplicated within its owner.

        The name is optional, but once filled it must be unique inside the same
        product (shared gallery) or the same product variant so images stay
        identifiable in the gallery.
        """
        for record in self:
            if not record.name:
                continue
            if record.product_id:
                # 变体专属图：在所属变体内去重
                domain = [
                    ("product_id", "=", record.product_id.id),
                    ("name", "=", record.name),
                    ("id", "!=", record.id),
                ]
                owner = record.product_id.display_name
            elif record.product_tmpl_id:
                # 模板共享图：在所属产品内去重（原逻辑）
                domain = [
                    ("product_tmpl_id", "=", record.product_tmpl_id.id),
                    ("name", "=", record.name),
                    ("id", "!=", record.id),
                ]
                owner = record.product_tmpl_id.display_name
            else:
                # 归属校验由 _check_single_owner 负责，此处避免重复报错
                continue
            duplicate = self.sudo().search(domain, limit=1)
            if duplicate:
                raise ValidationError(_(
                    'The image name "%(name)s" already exists for "%(owner)s". '
                    "Image names must be unique within the same product or product variant.",
                    name=record.name,
                    owner=owner,
                ))
