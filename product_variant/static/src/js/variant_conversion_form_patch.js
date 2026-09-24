/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { _t } from "@web/core/l10n/translation";

import { buildMappingPayload, buildSelectionPayload, getMappingStore } from "./variant_mapping_panel";

/**
 * 保存时按映射表的状态决定这次保存能不能继续。
 *
 * 用户在产品表单的原生「属性与变体」页改完属性、点保存时，这里先问服务端
 * （``product.template.get_variant_mapping_preview``）这次改动之后每条变体带哪个组合：
 *
 * - 会丢既有变体（删取值 / 删属性）→ 提示并拦住保存，绝不静默删除变体；
 * - 还有变体是**未映射**（这次改动让它失去了某个属性的取值）→ 提示并拦住保存：
 *   页面下方的映射表已经把缺取值的行标了出来，用户就地选好再保存；
 * - 每条变体都有组合 → 把映射表里确认好的归属塞进本次保存一起提交
 *   （属性变更与归属因此是同一次写库、同一个事务，见模块 AGENTS.md → L1 约束 9）；
 * - 不改属性 → 与原生保存完全一致。
 *
 * 映射表的状态挂在 model 上（``getMappingStore``），所以不管映射表当前有没有渲染
 * （用户可能已经切到别的页签），这里拿到的都是用户选好的最新结果。
 *
 * 注：``onWillSaveRecord(record, changes)`` 是 Odoo 表单控制器的官方保存前钩子
 * （返回 false 即阻止保存，``changes`` 会原样发给 ``web_save``），见模块 AGENTS.md → L2 P4。
 */
patch(FormController.prototype, {
    async onWillSaveRecord(record, changes) {
        if (
            record.resModel !== "product.template" ||
            !record.resId ||
            !("attribute_line_ids" in changes)
        ) {
            return super.onWillSaveRecord(...arguments);
        }
        const store = getMappingStore(this.model);
        const preview = await this.env.services.orm.call(
            "product.template",
            "get_variant_mapping_preview",
            [
                [record.resId],
                changes.attribute_line_ids,
                buildSelectionPayload(store.rows),
            ]
        );
        // 映射表（若正渲染着）用的是同一份 store，改这里它就跟着更新；
        // 没渲染也没关系，用户切回「属性与变体」页时看到的就是这份状态
        store.blocked = preview.blocked || false;
        store.rows = preview.rows || [];
        store.newCombinations = preview.new_combinations || [];
        store.dynamic = !!preview.dynamic;
        if (preview.blocked) {
            this.env.services.notification.add(preview.blocked, {
                type: "danger",
                sticky: true,
            });
            return false;
        }
        if (preview.unmapped_count) {
            this.env.services.notification.add(
                _t(
                    "%(count)s variants still have no combination: pick the combination each of them keeps in the mapping table below the attribute lines, then save again.",
                    { count: preview.unmapped_count }
                ),
                { type: "danger", sticky: true }
            );
            return false;
        }
        if (preview.required) {
            // 会新增变体：归属随本次保存一起提交。缺映射时服务端同样会拒绝
            // （那是「有未映射变体就不许保存」的服务端兜底，前端资源没生效时也靠它）
            changes.variant_conversion_mapping = JSON.stringify(
                buildMappingPayload(store.rows, store.shareVendorPrices)
            );
        }
        return super.onWillSaveRecord(...arguments);
    },
});
