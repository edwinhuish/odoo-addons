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

    /** 该既有变体是否已被别的组合选走（一条既有变体只能承载一个组合） */
    isVariantUsed(index, variantId) {
        return Object.entries(this.state.selection).some(
            ([otherIndex, selected]) => Number(otherIndex) !== index && selected === variantId
        );
    }

    onSelect(index, ev) {
        this.state.selection[index] = Number(ev.target.value) || false;
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
