/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

/**
 * 订单行悬浮卡片：纯展示组件。
 *
 * 数据由 ListRenderer 补丁预取后经 props.payload 传入（见 product_hover_cache.js），
 * 组件自身不发请求；无图或图片加载失败时降级为占位图标，避免出现破图。
 *
 * 数量 / 价格等数值都由后端 `formatLang` 按用户语言与货币（单位）精度格式化成字符串，
 * 组件只负责把「数量 + 单位」拼成可翻译的一句话（`_t("%(qty)s %(uom)s")`）。
 */
export class ProductHoverCard extends Component {
    static template = "sale_product_hover.ProductHoverCard";
    static props = {
        payload: { type: Object },
        targetEl: { type: Object, optional: true },
        close: { type: Function },
    };

    setup() {
        this.state = useState({ imageFailed: false });
    }

    get showImage() {
        return Boolean(this.props.payload.image_url) && !this.state.imageFailed;
    }

    get showQuantity() {
        return Boolean(this.quantityText);
    }

    /** 订单数量："数量 单位"。 */
    get quantityText() {
        return this._quantityText(
            this.props.payload.qty_ordered_text,
            this.props.payload.uom_name
        );
    }

    /** 可用库存："数量 单位"；不跟踪库存的产品为空串（模板据此隐藏该项）。 */
    get onHandText() {
        return this._quantityText(
            this.props.payload.qty_available_text,
            this.props.payload.available_uom_name
        );
    }

    _quantityText(qty, uom) {
        if (!qty) {
            return "";
        }
        return uom ? _t("%(qty)s %(uom)s", { qty, uom }) : qty;
    }

    /**
     * 鼠标离开浮层：若指针回到触发行上，则交给行自身的移出逻辑处理（避免来回抖动），
     * 否则立即关闭（此时已不能通过行的 mouseout 触发，故必须显式关闭）。
     */
    onPointerLeave(ev) {
        if (this.props.targetEl?.contains(ev.relatedTarget)) {
            return;
        }
        this.props.close();
    }
}
