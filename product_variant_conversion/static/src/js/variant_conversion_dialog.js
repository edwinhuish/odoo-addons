/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

/** 纯函数：按当前选择组装回传给服务端的归属载荷（独立出来便于单测与复用）。 */
export function buildOwnershipPayload(combinations, selection, shareVendorPrices) {
    return {
        mapping: combinations.map((combination, index) => ({
            values: combination.values,
            origin_variant_id: selection[index] || false,
        })),
        share_vendor_prices: !!shareVendorPrices,
    };
}

/** 纯函数：还没被分配组合的既有变体数量（必须为 0 才能确认）。 */
export function countUnassigned(variants, selection) {
    const assigned = new Set(Object.values(selection).filter((id) => id));
    return variants.length - assigned.size;
}

/**
 * 纯函数：把「第 index 行」改选成 `variantId`（`false` = 新变体），必要时与占用它的那行**互换**。
 *
 * 弹窗里每一个下拉都能选（不为「已被别人占用」而禁用）：一旦选中某条既有变体已经占着的选项，
 * 就把「占用者」换成当前这行原先的选项 —— 两条变体互换，任意时刻每条既有变体仍然只被一行占用，
 * 也不会出现「重复占用」或「两边都空着」。
 *
 * 例：单变体产品（只有「原变体」一个候选）转成 Black / White 两个组合，默认原变体落在 Black；
 * 用户在 White 那行也选「原变体」→ Black 拿到 White 原先的选项（新变体）、White 拿到原变体。
 *
 * @param {Object} selection 行号（字符串，Object.keys 的结果）→ 既有变体 id 或 false
 * @param {Number} index 被改动的行号
 * @param {Number|false} variantId 该行新选的既有变体 id（false = 新变体）
 * @returns {Object} 新的 selection（不改原对象，便于比较与单测）
 */
export function applyOwnershipSelection(selection, index, variantId) {
    const next = { ...selection };
    if (variantId) {
        const takenBy = Object.keys(next).find(
            (otherIndex) => Number(otherIndex) !== index && next[otherIndex] === variantId
        );
        if (takenBy !== undefined) {
            next[takenBy] = next[index] || false;
        }
    }
    next[index] = variantId || false;
    return next;
}

/**
 * 归属确认弹窗：列出这次属性改动后会出现哪些组合，让用户逐个指定
 * 「由哪条既有变体继续承载」（等价于「这条既有变体转换后占哪个组合」）。
 *
 * 默认值来自服务端（什么都不指定时的结果），用户确认后才把映射交回保存流程；
 * 取消 / 直接关掉弹窗都不会保存，表单内容保持未保存状态。
 */
export class VariantConversionDialog extends Component {
    static template = "product_variant_conversion.VariantConversionDialog";
    static components = { Dialog };
    static props = {
        preview: Object,
        onConfirm: Function,
        close: Function,
    };

    setup() {
        const selection = {};
        for (const [index, combination] of this.props.preview.combinations.entries()) {
            selection[index] = combination.origin_variant_id || false;
        }
        // 供应商价格共享默认**不勾选**：勾选会把「仅挂某条变体」的价格记录改成对所有变体生效，
        // 同一供应商对不同变体的价差会被抹平（见模块 README →「价格与库存的同步规则」⚠）。
        this.state = useState({ selection, shareVendorPrices: false });
    }

    get combinations() {
        return this.props.preview.combinations;
    }

    get variants() {
        return this.props.preview.variants;
    }

    get newVariantLabel() {
        return _t("New variant (created by the conversion)");
    }

    get shareVendorPricesLabel() {
        return _t("Apply the vendor prices of these variants to all variants");
    }

    /** 产品是否带「按需生成」的属性（T-039）：这类产品只展开「立即」轴。 */
    get isOnDemand() {
        return !!this.props.preview.dynamic;
    }

    get onDemandHint() {
        return _t(
            "This product creates some variants on demand: the other values of those attributes are not created now — Odoo creates them when they are ordered. Only the combinations listed here are created."
        );
    }

    /** 还没被分配组合的既有变体数量：必须为 0 才能确认 */
    get unassignedCount() {
        return countUnassigned(this.variants, this.state.selection);
    }

    /** 选项文案：装了 stock 时附上在手数量，让「谁来承载」的判断有库存依据。 */
    variantDisplay(variant) {
        if (variant.on_hand === null || variant.on_hand === undefined) {
            return variant.label;
        }
        return _t("%(label)s — %(count)s on hand", {
            label: variant.label,
            count: variant.on_hand,
        });
    }

    get unassignedLabel() {
        return _t(
            "%(count)s existing variants still have no combination",
            { count: this.unassignedCount }
        );
    }

    /**
     * 改选某一行：所有选项都允许选；选中已被别的行占用的既有变体时与该行互换（见纯函数说明）。
     */
    onSelect(index, ev) {
        const variantId = Number(ev.target.value) || false;
        this.state.selection = applyOwnershipSelection(this.state.selection, index, variantId);
    }

    onToggleShareVendorPrices(ev) {
        this.state.shareVendorPrices = ev.target.checked;
    }

    onConfirm() {
        if (this.unassignedCount > 0) {
            return;
        }
        this.props.onConfirm(
            buildOwnershipPayload(this.combinations, this.state.selection, this.state.shareVendorPrices)
        );
        this.props.close();
    }
}
