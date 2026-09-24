/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { _t } from "@web/core/l10n/translation";

import { buildMappingPayload, getMappingStore } from "./variant_mapping_panel";

/**
 * 保存时用**前端算好的映射表状态**决定这次保存能不能继续。
 *
 * 编辑期间一次 RPC 都不发（映射表自己在前端算，见 AGENTS.md → L2 P4 陷阱 13），所以这里只是
 * 读那份状态：
 *
 * - 还有既有变体**没被分配到任何组合** → 提示并拦住保存：那条变体一旦不参与本次转换，
 *   就会被 Odoo 当作多余变体归档 / 删除（它的库存、单据都跟着走），本模块绝不静默丢变体；
 * - 每条既有变体都在某一行里 → 把「组合 → 归属变体」的映射塞进本次保存一起提交
 *   （属性变更与归属因此是同一次写库、同一个事务，见模块 AGENTS.md → L1 约束 9）；
 * - 不改属性 → 与原生保存完全一致。
 *
 * 会丢既有变体（删取值 / 删属性）这类判定仍由服务端在做（``write()`` 里），
 * 前端拦不住的情况下用户会看到服务端给出的解释。
 *
 * 映射表的状态挂在 model 上（``getMappingStore``），所以不管映射表当前有没有渲染
 * （用户可能已经切到别的页签），这里拿到的都是用户分配好的最新结果。
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
        // 面板就在本页，正常都算过；没算过（例如从别处改属性）就交给服务端兜底
        if (!store.rows.length) {
            return super.onWillSaveRecord(...arguments);
        }
        // 用表单当前状态重算一遍（本地，不发请求）：不依赖观察回调的时机
        await this.model.variantMappingPanel?.recompute();
        this.model.variantMappingPanel?.refreshRows();
        const unassigned = store.unassigned || [];
        if (unassigned.length) {
            this.env.services.notification.add(
                _t(
                    "%(count)s variants have not been assigned to a combination yet: pick each of them in the Variant column of the mapping table below the attribute lines, then save again.",
                    { count: unassigned.length }
                ),
                { type: "danger", sticky: true }
            );
            return false;
        }
        changes.variant_conversion_mapping = JSON.stringify(
            buildMappingPayload(store.rows, store.shareVendorPrices)
        );
        return super.onWillSaveRecord(...arguments);
    },
});
