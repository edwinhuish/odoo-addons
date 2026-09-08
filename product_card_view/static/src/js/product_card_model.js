/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { RelationalModel } from "@web/model/relational_model/relational_model";

// 全局 payload 缓存（按 resId 索引）。非 reactive，不触发 Owl effect。
// 单视图假设：reload 时 clear + 重新填充。多视图实例同时打开会冲突（SOHO 场景不发生）。
// 避开 by-model WeakMap：Owl reactive proxy 调方法时 this 是 raw，而 record.model 是
// proxy，identity 不等需 toRaw；且 payload getter 访问 record.model 会触发 reactive
// 依赖追踪。改用 resId 全局索引，payload getter 只访问 record.resId。
const payloadByResId = new Map();

export class ProductCardModel extends RelationalModel {
    // 关闭缓存：payload 在 load 后填充全局 Map，缓存命中的请求不会重新填充，
    // 会导致卡片数据陈旧。
    static withCache = false;

    async load(params = {}) {
        await super.load(params);
        const records = this._collectCardRecords();
        const templateIds = records
            .map((record) => record.resId)
            .filter((id) => id != null);
        payloadByResId.clear();
        if (templateIds.length) {
            const payload = await rpc("/product_card/payload", { template_ids: templateIds });
            for (const resId of templateIds) {
                if (payload && payload[resId]) {
                    payloadByResId.set(resId, payload[resId]);
                }
            }
        }
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

// 临时 debug：统计 payload getter 调用次数，定位渲染是否循环（卡死时若数字爆炸即循环）
let _payloadGetterCount = 0;

/** 卡片组件按 resId 取 payload（非 reactive，不触发 Owl effect）。 */
export function getProductCardPayload(resId) {
    if (resId == null) {
        return null;
    }
    const result = payloadByResId.get(resId) || null;
    if (_payloadGetterCount < 5) {
        _payloadGetterCount++;
        console.warn(
            "[PCV DEBUG] payload getter #%s resId=%s type=%s has=%s mapSize=%s",
            _payloadGetterCount, resId, typeof resId, !!result, payloadByResId.size,
        );
    }
    return result;
}
