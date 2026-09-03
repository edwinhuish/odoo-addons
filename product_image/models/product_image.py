# -*- coding: utf-8 -*-
"""产品图片明细模型。

一个产品可挂多张图片，每张继承 ``image.mixin`` 自动生成多尺寸。
首图（排序最前）即主图，自动同步到 ``product.template.image_1920``，
保留与原生主图的关系，使列表 / 看板 / 报价单等均无需改动即可展示主图。
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductImageGallery(models.Model):
    """产品图片明细。

    设计要点：
    - 继承 ``image.mixin``，复用 Odoo 原生多尺寸（1920/1024/512/256/128）与 webp 转换链路
    - 模型名 ``product.image.gallery``，刻意避开 ``website_sale`` 的 ``product.image``
      使本模块可在不依赖 ``website_sale`` 的环境独立安装，且不与 eCommerce 冲突
    - 首图（``sequence`` 最小且 ``id`` 最小）即主图，由 ``_sync_main_image`` 同步到产品主图
    - 删除产品时图片行随产品级联删除（``ondelete='cascade'``）
    """

    _name = "product.image.gallery"
    _description = "产品图片"
    _inherit = ["image.mixin"]
    _order = "sequence, id"

    name = fields.Char(
        string="名称",
        help="图片的简短说明（可选），用于内部识别，如「正面」「细节」「包装」。",
    )
    sequence = fields.Integer(
        string="排序",
        default=10,
        help="数值小的排在前面；首图（排序最前）自动作为产品主图。",
    )
    is_main = fields.Boolean(
        string="主图",
        compute="_compute_is_main",
        store=True,
        help="是否为该产品的首图（主图）；由排序与 id 自动判定，勿手工编辑。",
    )
    active = fields.Boolean(
        string="启用",
        default=True,
        help="取消勾选可停用某张图片而不删除，便于保留历史素材。",
    )
    note = fields.Char(
        string="备注",
        help="对该图片的补充说明。",
    )

    product_tmpl_id = fields.Many2one(
        string="产品",
        comodel_name="product.template",
        ondelete="cascade",
        required=True,
        index=True,
        help="该图片所属的产品模板；删除产品时图片行随之级联清理。",
    )

    # ------------------------------------------------------------------
    # 主图判定：首图（sequence 最小，id 最小兜底）即主图
    # ------------------------------------------------------------------

    @api.depends("sequence", "product_tmpl_id", "active")
    def _compute_is_main(self):
        """判定每张图片是否为其产品图库的首图（主图）。

        首图定义：同一产品下 ``active=True`` 的图片中 ``sequence`` 最小者；
        并列时取 ``id`` 最小者，保证稳定唯一。
        """
        # 按产品分组，各取首图 id
        product_ids = self.mapped("product_tmpl_id").ids
        if not product_ids:
            for img in self:
                img.is_main = False
            return
        # 一次性查出每个产品的首图 id，避免逐记录查询
        self.env.cr.execute(
            "SELECT product_tmpl_id, MIN(id) "
            "FROM product_image_gallery "
            "WHERE product_tmpl_id IN %s AND active = true "
            "GROUP BY product_tmpl_id",
            (tuple(product_ids),),
        )
        main_map = {pid: mid for pid, mid in self.env.cr.fetchall()}
        for img in self:
            main_id = main_map.get(img.product_tmpl_id.id) if img.product_tmpl_id else None
            img.is_main = (main_id == img.id)

    # ------------------------------------------------------------------
    # 主图同步：图片增删改后把首图写入产品主图 image_1920
    # ------------------------------------------------------------------

    def _get_main_image(self):
        """返回当前图集的首图（sequence 升序、id 升序的第一条）。"""
        return self.sorted(lambda r: (r.sequence, r.id))[:1]

    # ------------------------------------------------------------------
    # 约束：同一产品内图片名称不可重复（便于识别）
    # ------------------------------------------------------------------

    @api.constrains("name", "product_tmpl_id")
    def _check_name_unique_per_template(self):
        """同一产品内图片名称重复时给出可读中文提示。

        名称非必填，但若填了则在同一产品内不可重复，便于在图库中识别。
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
                    "图片名称“%s”在产品“%s”中已存在，同一产品内图片名称不可重复。"
                ) % (
                    record.name,
                    record.product_tmpl_id.display_name,
                ))

    # ------------------------------------------------------------------
    # create / write / unlink：触发主图同步与主图标记重算
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # 新建图片后重算受影响产品所有图片的 is_main，再同步主图
        templates = records.mapped("product_tmpl_id")
        if templates:
            self.search([("product_tmpl_id", "in", templates.ids)])._compute_is_main()
            templates._sync_main_image_from_template()
        return records

    def write(self, vals):
        res = super().write(vals)
        # 影响首图判定的字段变动时重算 is_main 并同步主图
        if any(k in vals for k in (
            "sequence", "product_tmpl_id", "active", "image_1920",
        )):
            templates = self.mapped("product_tmpl_id")
            if templates:
                self.search([("product_tmpl_id", "in", templates.ids)])._compute_is_main()
                templates._sync_main_image_from_template()
        return res

    def unlink(self):
        templates = self.mapped("product_tmpl_id")
        res = super().unlink()
        if templates:
            self.search([("product_tmpl_id", "in", templates.ids)])._compute_is_main()
            templates._sync_main_image_from_template()
        return res
