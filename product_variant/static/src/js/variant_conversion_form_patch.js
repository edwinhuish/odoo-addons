/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { _t } from "@web/core/l10n/translation";

import {
    buildMappingPayload,
    discardMappingChanges,
    getMappingStore,
    snapshotMappingBaseline,
} from "./variant_mapping_panel";

/**
 * 表单侧负责三件事：
 *
 * 1. **保存前把关**：还有既有变体没被分配到任何组合 → 提示并拦住保存；都在某一行里 →
 *    把「组合 → 归属变体」的映射塞进本次提交（属性变更与归属同一次写库、同一个事务）。
 * 2. **只改映射时也要能保存**：属性行没动时原生保存会因为「没有 changes」直接返回
 *    （``Record._save()`` 里的 ``!Object.keys(changes).length`` 早退），映射得在这里自己写一次 ——
 *    用户点 **Save manually** 就能落库。
 * 3. **丢弃**：原生 Discard all changes 会把字段恢复成最后一次保存的状态，映射那份改动
 *    要跟着一起回到基线（``discardMappingChanges()``）。
 *
 * 关于「规避 Odoo 自动保存」：映射改动只存在于本模块的 store 里（不是 record 的字段改动），
 * 所以 ``beforeLeave()`` / ``beforeVisibilityChange()`` 这些自动保存路径不会带上它 ——
 * 映射只能由用户显式点保存（或属性行改动触发的正常保存）提交，见 AGENTS.md → L2 P4 陷阱 20。
 */
patch(FormController.prototype, {
    /** 重算面板并返回映射 store（面板可能没挂载，例如用户从别的页签保存）。 */
    async ensureMappingStore() {
        const store = getMappingStore(this.model);
        await this.model.variantMappingPanel?.recompute();
        this.model.variantMappingPanel?.refreshRows();
        return store;
    },

    /** 还有既有变体没被分配到任何组合：点名 + 拦住保存。 */
    notifyUnassigned(count) {
        this.env.services.notification.add(
            _t(
                "%(count)s variants have not been assigned to a combination yet: pick each of them in the Variant column of the mapping table below the attribute lines, then save again.",
                { count }
            ),
            { type: "danger", sticky: true }
        );
    },

    async onWillSaveRecord(record, changes) {
        if (
            record.resModel !== "product.template" ||
            !record.resId ||
            !("attribute_line_ids" in changes)
        ) {
            return super.onWillSaveRecord(...arguments);
        }
        const store = await this.ensureMappingStore();
        // 面板就在本页，正常都算过；没算过（例如从别处改属性）就交给服务端兜底
        if (!store.rows.length) {
            return super.onWillSaveRecord(...arguments);
        }
        if ((store.unassigned || []).length) {
            this.notifyUnassigned(store.unassigned.length);
            return false;
        }
        changes.variant_conversion_mapping = JSON.stringify(
            buildMappingPayload(store.rows, store.shareVendorPrices)
        );
        return super.onWillSaveRecord(...arguments);
    },

    async save(params) {
        const record = this.model.root;
        // 只管产品表单：别的模型不该被这里的映射逻辑碰（尤其不能乱广播 FIELD_IS_DIRTY）
        if (record?.resModel !== "product.template") {
            return super.save(params);
        }
        const store = getMappingStore(this.model);
        // 只改了映射（属性行没动）：原生保存不会带任何 changes，映射要在这里自己写一次
        const mappingOnly = Boolean(record.resId) && !record.dirty && store.dirty;
        if (mappingOnly) {
            await this.ensureMappingStore();
            if ((store.unassigned || []).length) {
                this.notifyUnassigned(store.unassigned.length);
                return false;
            }
        }
        const saved = await super.save(params);
        if (saved === false) {
            return false;
        }
        if (mappingOnly && store.rows.length) {
            await this.env.services.orm.call("product.template", "write", [
                [record.resId],
                {
                    variant_conversion_mapping: JSON.stringify(
                        buildMappingPayload(store.rows, store.shareVendorPrices)
                    ),
                },
            ]);
        }
        await this.settleMappingAfterSave();
        return saved;
    },

    /**
     * 保存成功后的收尾：**作废快照重取**，再以「刚保存完的状态」作为新的未修改基线。
     *
     * 不重取的话 ``snapshot.lines`` 还是**上一次保存**的属性行；保存后 ``record._changes``
     * 已被清空，面板下一次重算会把「基线（旧） + 空改动」当成当前配置 —— 界面退回保存前的
     * 样子，甚至又把「未保存」标记点亮（见模块 AGENTS.md → L2 P4 陷阱 21）。
     */
    async settleMappingAfterSave() {
        const store = getMappingStore(this.model);
        const panel = this.model.variantMappingPanel;
        if (panel) {
            panel.store.snapshot = null;
            try {
                await panel.load();
            } catch {
                // 快照取不回来就等面板下次挂载时再取：保存已经成功了，不该因为它而失败
                store.snapshot = null;
            }
        } else {
            store.snapshot = null;
        }
        snapshotMappingBaseline(store);
        store.dirty = false;
        this.model.bus?.trigger("FIELD_IS_DIRTY", false);
    },

    async discard() {
        const result = await super.discard(...arguments);
        if (this.model.root?.resModel !== "product.template") {
            return result;
        }
        // record 已经恢复成最后一次保存的状态 → 映射按恢复后的属性行回到基线
        discardMappingChanges(this.model);
        return result;
    },
});
