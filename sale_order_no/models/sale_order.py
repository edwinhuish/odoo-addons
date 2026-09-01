# -*- coding: utf-8 -*-
"""销售订单 / 报价单的自定义订单编号。

编号规则：客户编码（快照）+ 两位年份 + 客户本年度流水号，例如 ``DZ2602``。
报价单与销售订单共用同一套编号。
"""

import re
from datetime import date, datetime, time

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain

UNKNOWN_BUYER_REF = "UNK"
MAX_INDEX_TRY = 500


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # 数据库层唯一约束，是 Python 校验之外的最后一道防线（并发创建、批量导入）
    _order_no_unique = models.Constraint(
        "UNIQUE(order_no)",
        "订单编号必须全局唯一。",
    )

    # ------------------------------------------------------------------
    # 字段定义
    # ------------------------------------------------------------------

    buyer_ref = fields.Char(
        string="客户编号(快照)",
        copy=False,
        readonly=True,
        help="创建时从客户编号（联系人 ref）复制，后续修改客户资料不影响本单据。",
    )

    buyer_order_idx = fields.Integer(
        string="客户年度流水号",
        copy=False,
        readonly=True,
        help="创建时一次性分配，作废或取消的单据依然占用流水号。",
    )

    order_no = fields.Char(
        string="订单编号",
        index="trigram",
        copy=False,
        help="格式：客户编号 + 两位年份 + 客户本年度流水号，例如 DZ2602；"
             "创建时自动生成，可手动修改，保存时校验全局唯一。",
    )

    # ------------------------------------------------------------------
    # 创建与编号分配
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record, vals in zip(records, vals_list):
            record._assign_order_fields(vals)
        return records

    def _assign_order_fields(self, vals=None):
        """分配客户编号快照、年度流水号与订单编号。

        仅在下列情况真正生成编号：尚未分配编号，或复制单据后编号被清空。
        已分配过的编号永不重算，保证历史单据稳定。
        """
        self.ensure_one()
        vals = vals or {}

        # 1. 客户编号快照（一次性写入）
        if not self.buyer_ref:
            self.buyer_ref = self._get_buyer_ref_snapshot()

        # 2. 批量导入历史单据：显式指定了编号则保留，并尽量还原流水号以便后续接续
        if vals.get("order_no") and self.order_no:
            self._restore_index_from_order_no()
            return True

        # 3. 已分配过编号：快照机制，不再变动
        if self.order_no and self.buyer_order_idx:
            return True

        # 4. 分配流水号并生成编号（自动避让已被占用的编号）
        order_date = fields.Datetime.to_datetime(self.date_order) or fields.Datetime.now()
        year = order_date.year
        idx = self._next_order_idx(year)
        self.buyer_order_idx = idx
        self.order_no = self._build_order_no(self.buyer_ref, year, idx)
        return True

    def _get_buyer_ref_snapshot(self):
        """读取客户编号快照；未设置客户编号时使用 UNK。"""
        self.ensure_one()
        return ((self.partner_id.ref or "").strip().upper()) or UNKNOWN_BUYER_REF

    @api.model
    def _build_order_no(self, buyer_ref, year, idx):
        """按规则拼接订单编号。"""
        return f"{(buyer_ref or UNKNOWN_BUYER_REF).upper()}{year % 100:02d}{idx:02d}"

    def _restore_index_from_order_no(self):
        """从导入的编号中还原年度流水号，保证后续新建单据能接续编号。"""
        self.ensure_one()
        if self.buyer_order_idx or not self.order_no or not self.buyer_ref:
            return
        match = re.fullmatch(
            rf"{re.escape(self.buyer_ref)}\d{{2}}(\d{{2,}})",
            (self.order_no or "").strip().upper(),
        )
        if match:
            self.buyer_order_idx = int(match.group(1))

    def _next_order_idx(self, year):
        """返回该客户该年度下一个可用流水号。

        先取该客户本年度已分配的最大流水号 + 1，再校验生成的编号是否已被占用；
        被占用（历史导入、手动改号）时自增，直到拿到可用编号。
        """
        self.ensure_one()
        last = self.sudo().search(
            self._year_index_domain(year), order="buyer_order_idx desc", limit=1
        )
        idx = (last.buyer_order_idx or 0) + 1

        for _ in range(MAX_INDEX_TRY):
            if not self._order_no_taken(self._build_order_no(self.buyer_ref, year, idx)):
                return idx
            idx += 1

        raise ValidationError(_(
            "客户“%s”在 %s 年度的流水号已连续占用 %s 个，无法自动分配订单编号，请手动指定。",
        ) % (self.partner_id.display_name, year, MAX_INDEX_TRY))

    def _year_index_domain(self, year):
        """该客户指定年度、已分配流水号的单据域。

        上下界用当天的 00:00:00 与 23:59:59，避免年末最后一天的单据被漏掉。
        """
        self.ensure_one()
        return [
            ("partner_id", "=", self.partner_id.id),
            ("date_order", ">=", datetime.combine(date(year, 1, 1), time.min)),
            ("date_order", "<=", datetime.combine(date(year, 12, 31), time.max)),
            ("buyer_order_idx", ">", 0),
        ]

    def _order_no_taken(self, order_no):
        """判断编号是否已被其他单据占用。"""
        self.ensure_one()
        return bool(self.sudo().search([
            ("order_no", "=", order_no),
            ("id", "!=", self.id),
        ], limit=1))

    # ------------------------------------------------------------------
    # 唯一性校验
    # ------------------------------------------------------------------

    @api.constrains("order_no")
    def _check_order_no_unique(self):
        """订单编号全局唯一校验：空值跳过，重复时给出可读的中文提示。"""
        for record in self:
            if not record.order_no:
                continue
            duplicate = self.sudo().search([
                ("order_no", "=", record.order_no),
                ("id", "!=", record.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    "订单编号“%s”已被单据 %s（客户：%s）占用，请使用其他编号。",
                ) % (
                    record.order_no,
                    duplicate.name or "",
                    duplicate.partner_id.display_name or "",
                ))

    # ------------------------------------------------------------------
    # 显示名称：优先使用订单编号（Odoo 19 已移除 name_get）
    # ------------------------------------------------------------------

    @api.depends("order_no", "partner_id")
    @api.depends_context("sale_show_partner_name")
    def _compute_display_name(self):
        """display_name 优先使用订单编号，未分配时回退到原生 name。"""
        super()._compute_display_name()
        for record in self:
            if not record.order_no:
                continue
            if self.env.context.get("sale_show_partner_name"):
                record.display_name = " - ".join(
                    part for part in (record.order_no, record.partner_id.name) if part
                )
            else:
                record.display_name = record.order_no

    @api.model
    def _search_display_name(self, operator, value):
        """让 Many2one 下拉、搜索建议、快速搜索都能按订单编号命中。"""
        domain = super()._search_display_name(operator, value)
        if not (isinstance(value, str) and value):
            return domain
        extra = Domain("order_no", operator, value)
        # 否定操作符必须取交集，否则会把所有非本编号的单据都查出来
        if operator in Domain.NEGATIVE_OPERATORS:
            return Domain.AND([domain, extra])
        return Domain.OR([domain, extra])

    # ------------------------------------------------------------------
    # 列表 API：把返回的 name 替换成订单编号
    # ------------------------------------------------------------------

    @api.model
    @api.readonly
    def web_search_read(self, domain, specification, offset=0, limit=None,
                        order=None, count_limit=None):
        """列表视图返回的 name 字段统一显示订单编号。

        列表主列渲染的是 name 原始值而非 display_name，故在此做替换；
        仅当视图确实请求了 name 时才做一次轻量查询。
        """
        result = super().web_search_read(
            domain, specification, offset=offset, limit=limit,
            order=order, count_limit=count_limit,
        )
        if "name" not in (specification or {}):
            return result

        record_ids = [rec["id"] for rec in result.get("records", []) if rec.get("id")]
        if not record_ids:
            return result

        order_no_map = {
            rec.id: rec.order_no
            for rec in self.sudo().search_fetch([("id", "in", record_ids)], ["order_no"])
        }
        for record in result["records"]:
            order_no = order_no_map.get(record["id"])
            if order_no:
                record["name"] = order_no
        return result

    # ------------------------------------------------------------------
    # 复制单据：重新分配编号
    # ------------------------------------------------------------------

    def copy(self, default=None):
        """复制时清空编号相关字段，由 create 逻辑重新分配，旧编号保留。"""
        default = dict(default or {})
        default.update({
            "buyer_ref": False,
            "buyer_order_idx": 0,
            "order_no": False,
        })
        return super().copy(default)

    # ------------------------------------------------------------------
    # 批量补号
    # ------------------------------------------------------------------

    def action_generate_order_no(self):
        """为尚未分配编号的单据补号（批量导入历史单据后使用）。"""
        todo = self.filtered(lambda order: not order.order_no)
        for order in todo:
            order._assign_order_fields()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("订单编号"),
                "message": _("已为 %s 张单据生成订单编号，%s 张单据已有编号未改动。") % (
                    len(todo), len(self - todo),
                ),
                "type": "success" if todo else "warning",
                "sticky": False,
            },
        }
