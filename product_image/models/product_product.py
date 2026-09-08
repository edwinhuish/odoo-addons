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

from odoo import api, fields, models
from odoo.fields import Command


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

    # ------------------------------------------------------------------
    # 变体图库子记录：创建时必须剥离 context 的 default_product_tmpl_id
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        """变体图库子记录创建前清除模板默认，避免双归属。

        从模板页进入变体「独立编辑」表单时，其 act_window 的 context 携带
        ``default_product_tmpl_id``（官方 product 变体列表 action）；图库子记录经
        ``(0, 0, ...)`` 命令创建时，子模型 create 的 default_get 会把该默认值填进
        ``product_tmpl_id``，而同一行随后又被 One2many inverse 回填 ``product_id``，
        触发 ``_check_single_owner`` 的「一张图不能同时归属产品与变体」报错。
        变体专属图语义上只挂 ``product_id``，故对 create 子行无条件置空模板归属
        （模板共享图走 product.template 的 ``image_gallery_ids``，不受影响）。
        """
        self._strip_variant_gallery_template_default(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        """同 create：对 write 携带的 ``(0, 0)`` 图库命令同样剥离模板默认。"""
        self._strip_variant_gallery_template_default([vals])
        return super().write(vals)

    def _strip_variant_gallery_template_default(self, vals_list):
        """把 ``variant_image_gallery_ids`` 的 create 命令子行模板归属强制置空。"""
        for vals in vals_list:
            commands = vals.get("variant_image_gallery_ids")
            if not commands:
                continue
            cleaned = []
            for cmd in commands:
                if isinstance(cmd, (list, tuple)) and len(cmd) == 3 and cmd[0] == Command.CREATE:
                    child_vals = dict(cmd[2])
                    child_vals["product_tmpl_id"] = False
                    cleaned.append(Command.create(child_vals))
                else:
                    cleaned.append(cmd)
            vals["variant_image_gallery_ids"] = cleaned
