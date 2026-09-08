/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { RelationalModel } from "@web/model/relational_model/relational_model";

// 非模块实例级的 payload 缓存：model 实例（WeakMap）→ resId → payload。
// 故意用普通 Map / WeakMap（非 Owl reactive）：给 reactive model / record 实例加
// 自定义属性会触发 Owl DataModel 内部 effect（dirty / onUpdate 检测）→ reload 循环
// → 页面卡死。ViewController await load，渲染时已填充；reload 重建 root 会触发
// KanbanRenderer 重新渲染，卡片重新查（已填充），无需 record 级 reactivity
// （变体切换走卡片内 useState）。
const payloadByModel = new WeakMap();

export class ProductCardModel extends RelationalModel {
    // 关闭缓存：payload 在 load 后填充 WeakMap，缓存命中的请求不会重新填充，
    // 会导致卡片数据陈旧。
    static withCache = false;

    async load(params = {}) {
        await super.load(params);
        const records = this._collectCardRecords();
        const templateIds = records
            .map((record) => record.resId)
            .filter((id) => id != null);
        const resIdMap = new Map();
        if (templateIds.length) {
            const payload = await rpc("/product_card/payload", { template_ids: templateIds });
            for (const resId of templateIds) {
                if (payload && payload[resId]) {
                    resIdMap.set(resId, payload[resId]);
                }
            }
        }
        payloadByModel.set(this, resIdMap);
    }

    /**
     * 从 root 收集当前展示的 Record 实例：
     * - 非分组：DynamicRecordList.records（数组）；
     * - 分组：DynamicGroupList.records（getter，含所有非折叠组的记录）。
     * mono record（表单 / 快速编辑）无 records，返回空数组跳过。
     */
    _collectCardRecords() {
        const root = this.root;
        if (!root) {
            return [];
        }
        return root.records || [];
    }
}

/** 卡片组件按 (model, resId) 取 payload（非 reactive，不触发 Owl effect）。 */
export function getProductCardPayload(model, resId) {
    return (resId != null && payloadByModel.get(model)?.get(resId)) || null;
}
