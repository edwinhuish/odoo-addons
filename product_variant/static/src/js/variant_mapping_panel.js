/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { useRecordObserver } from "@web/model/relational_model/utils";

/** 纯函数：还没拿到组合的变体数（> 0 就不许保存）。 */
export function countUnmapped(rows) {
    return rows.filter((row) => !row.mapped).length;
}

/** 纯函数：把已选的取值整理成服务端要的 ``{变体 id: {属性 id: 取值 id}}``。 */
export function buildSelectionPayload(rows) {
    const selection = {};
    for (const row of rows) {
        const axes = {};
        for (const axis of row.axes) {
            if (axis.value_id) {
                axes[axis.attribute_id] = axis.value_id;
            }
        }
        selection[row.variant_id] = axes;
    }
    return selection;
}

/** 纯函数：把已选的取值整理成服务端认的归属载荷（与 ``write()`` 的解析端一致）。 */
export function buildMappingPayload(rows, shareVendorPrices) {
    return {
        mapping: rows.map((row) => ({
            values: row.axes.filter((axis) => axis.value_id).map((axis) => axis.value_id),
            origin_variant_id: row.variant_id,
        })),
        share_vendor_prices: !!shareVendorPrices,
    };
}

/**
 * 纯函数：属性行当前内容的「签名」—— 用来判断属性配置是不是真的变了。
 *
 * 读一遍属性行与每行的取值，OWL 的 effect 会因此把这些值登记成依赖：属性行增删、
 * 某一行的取值增减都会让签名变化，面板随之刷新。读不到的结构（Odoo 升级改了内部
 * 表示）一律返回空串 —— 那也只是退化成「保存时才刷新」，保存拦截仍然正确。
 */
export function attributeLineSignature(record) {
    const list = record?.data?.attribute_line_ids;
    if (!list || !list.records) {
        return "";
    }
    try {
        return list.records
            .map((line) => {
                const values = line.data?.value_ids;
                const valueIds = values?.records
                    ? values.records.map((value) => value.resId).join(",")
                    : "";
                return [line.resId || "new", line.data?.attribute_id?.[0], valueIds].join(":");
            })
            .join("|");
    } catch {
        return "";
    }
}

/**
 * 映射表状态存在 ``model`` 上（不是组件里）：
 *
 * 面板挂在「属性与变体」页里，用户切到别的页签它就卸载了。把状态放在 model 上，
 * 保存钩子（``FormController.onWillSaveRecord``）与面板共享同一份数据 —— 无论面板
 * 当前有没有挂载，「用户选到哪一步」都不会丢。
 */
export function getMappingStore(model) {
    if (!model.variantMapping) {
        model.variantMapping = {
            rows: [],
            blocked: false,
            newCombinations: [],
            dynamic: false,
            shareVendorPrices: false,
            signature: undefined,
        };
    }
    return model.variantMapping;
}

/**
 * 「属性 ↔ 变体」映射表：产品表单「属性与变体」页、属性行下方的常驻面板。
 *
 * 每行是一条**既有变体**，每个属性轴一列：
 *
 * - 该轴由 Odoo 自己补取值（单取值轴 /「按需生成」轴）→ 直接显示取值，不可改；
 * - 其它轴 → 下拉，用户挑；挑完这条变体才回到「已映射」。
 *
 * 属性行一改，面板就问服务端（``get_variant_mapping_preview``）这次改动之后每条变体
 * 带哪个组合：缺了取值的那条立刻变成**未映射**，而只要还有未映射的变体，保存就被拦住
 * （见 ``variant_conversion_form_patch.js``）。全部映射好后，保存钩子把映射表里确认的
 * 归属随本次保存一起提交。
 */
export class VariantMappingPanel extends Component {
    static template = "product_variant.VariantMappingPanel";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.store = useState(getMappingStore(this.props.record.model));
        const initial = this.parseValue(this.props.value);
        const reopened = Boolean(this.store.rows.length);
        if (!reopened) {
            // 首次打开：字段里带的初始状态就是当前配置，不用再问服务端一次
            this.store.rows = initial.rows || [];
            this.store.blocked = initial.blocked || false;
            this.store.newCombinations = initial.new_combinations || [];
            this.store.dynamic = !!initial.dynamic;
        }
        // 重新挂回来（切回本页签）时属性行可能已经改过，先问一次服务端
        this.refreshOnFirstObservation = reopened;
        this.store.signature = undefined;
        let firstCall = true;
        useRecordObserver((record) => {
            const current = attributeLineSignature(record);
            if (firstCall) {
                firstCall = false;
                this.store.signature = current;
                if (this.refreshOnFirstObservation) {
                    this.scheduleRefresh();
                }
                return;
            }
            if (current === this.store.signature) {
                return;
            }
            this.store.signature = current;
            this.scheduleRefresh();
        });
    }

    willUnmount() {
        clearTimeout(this.refreshTimer);
    }

    parseValue(value) {
        try {
            return JSON.parse(value || "{}");
        } catch {
            return {};
        }
    }

    // ------------------------------------------------------------------
    // 数据：向服务端问「这次改动之后每条变体带哪个组合」
    // ------------------------------------------------------------------

    /** 属性行变化很密（加一行 / 勾一个取值都会触发），防抖后只问一次。 */
    scheduleRefresh() {
        clearTimeout(this.refreshTimer);
        this.refreshTimer = setTimeout(() => this.refresh(), 300);
    }

    async refresh() {
        const record = this.props.record;
        if (!record || !record.resId) {
            return;
        }
        if (this.refreshing) {
            this.refreshPending = true;
            return;
        }
        this.refreshing = true;
        try {
            do {
                this.refreshPending = false;
                // 本次尚未保存的属性行命令：服务端拿它做「只写配置、不碰变体」的试写
                const changes = await record.getChanges({ withReadonly: true });
                const preview = await this.orm.call(
                    "product.template",
                    "get_variant_mapping_preview",
                    [[record.resId], changes.attribute_line_ids || [], this.selectionPayload()]
                );
                this.applyPreview(preview);
            } while (this.refreshPending);
        } finally {
            this.refreshing = false;
        }
    }

    /** 保存钩子算完预览后推回来的最新状态（避免同一次改动问两遍）。 */
    applyPreview(preview) {
        this.store.blocked = preview.blocked || false;
        this.store.rows = preview.rows || [];
        this.store.newCombinations = preview.new_combinations || [];
        this.store.dynamic = !!preview.dynamic;
    }

    /** 面板里已选的取值，交给服务端去重算「改动之后的映射状态」。 */
    selectionPayload() {
        return buildSelectionPayload(this.store.rows);
    }

    // ------------------------------------------------------------------
    // 展示
    // ------------------------------------------------------------------

    get unmappedCount() {
        return countUnmapped(this.store.rows);
    }

    get axisLabels() {
        return (this.store.rows[0] || { axes: [] }).axes.map((axis) => axis.attribute_label);
    }

    get introLabel() {
        return _t(
            "Every existing variant and the combination it keeps. A variant that has no value on an attribute becomes unmapped and blocks the save until you pick one."
        );
    }

    get mappedLabel() {
        return _t("Mapped");
    }

    get unmappedAxisLabel() {
        return _t("Unmapped");
    }

    get chooseLabel() {
        return _t("Choose a value");
    }

    get unmappedHint() {
        return _t("%(count)s variants still have no combination", {
            count: this.unmappedCount,
        });
    }

    get newVariantsLabel() {
        return _t(
            "%(count)s combinations do not exist yet and will be created as new variants",
            { count: this.store.newCombinations.length }
        );
    }

    get shareVendorPricesLabel() {
        return _t("Apply the vendor prices of these variants to all variants");
    }

    get onDemandHint() {
        return _t(
            "This product creates some variants on demand: the other values of those attributes are not created now — Odoo creates them when they are ordered. Only the combinations listed here are created."
        );
    }

    /** 变体后面附上手数量（装了 stock 时），让「谁带哪个组合」的判断有依据。 */
    variantDisplay(row) {
        if (row.on_hand === null || row.on_hand === undefined) {
            return row.label;
        }
        return _t("%(label)s — %(count)s on hand", { label: row.label, count: row.on_hand });
    }

    /** 某一行在某个轴上的取值文本（自动补的轴没有下拉，直接显示）。 */
    axisDisplay(row, axis) {
        const option = axis.options.find((item) => item.id === axis.value_id);
        return option ? option.name : "";
    }

    // ------------------------------------------------------------------
    // 交互
    // ------------------------------------------------------------------

    onSelectValue(row, axis, ev) {
        for (const item of row.axes) {
            if (item.attribute_id === axis.attribute_id) {
                item.value_id = Number(ev.target.value) || false;
            }
        }
        row.mapped = row.axes.every((item) => item.value_id);
    }

    onToggleShareVendorPrices(ev) {
        this.store.shareVendorPrices = ev.target.checked;
    }
}

registry.category("fields").add("variant_mapping_panel", VariantMappingPanel);
