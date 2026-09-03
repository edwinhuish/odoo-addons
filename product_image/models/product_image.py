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
        help="数值小的排在前面；图库图片在缩略图列表中的展示顺序（主图始终在最前）。",
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
