/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { RelationalModel } from "@web/model/relational_model/relational_model";

// 全局 payload 缓存（按 resId 索引）。非 reactive，不触发 Owl effect。
// 在 _loadData（root 创建前）填充：super._loadData 返回 result 后、_createRoot
// 用 result 重建 Record 之前填好，root 创建后 KanbanCard 渲染时按 resId 查。
// 单视图假设：reload 时 clear + 重新填充。
//
// 为什么不用其他方案：
// ① 挂 result.records：_createRoot 重建 Record 时丢弃 → 卡片空白；
// ② 给 reactive model 赋值：触发 reload 循环（keepLast 竞争 + 空响应 + 卡死）；
// ③ 给 reactive Record 加属性：触发 Owl DataModel 内部 effect（dirty/onUpdate）→ 卡死；
// ④ 重写 load（super.load 后做事）：super.load 的 notify 触发 onUpdate，onUpdate
//   又调 load → 无限循环卡死；
// ⑤ by-model WeakMap：load 里 this 是 raw、record.model 是 proxy，identity 不等需 toRaw。
// 全局 Map by resId 全部避开：不挂对象、不触发 reactive、不依赖 identity。
const payloadByResId = new Map();

export class ProductCardModel extends RelationalModel {
    // 关闭缓存：payload 在 _loadData 后填充全局 Map，缓存命中的请求不会重新填充，
    // 会导致卡片数据陈旧。
    static withCache = false;

    async _loadData(params) {
        const result = await super._loadData(...arguments);
        // 单条记录模式（如快速编辑）无卡片网格需求，跳过
        if (params.isMonoRecord) {
            return result;
        }
        // 收集本页 resId：
        // - 非分组：result.records 是 webSearchRead 返回的原始对象，.id 即数据库 resId；
        // - 分组：group.records 已是 Record 实例，.id 是 datapoint 内部编号、.resId 才是
        //   数据库 id。统一用 resId（原始对象无 resId，回退 .id）。
        let rawRecords;
        if (params.groupBy?.length) {
            rawRecords = [];
            const stackGroups = [...(result.groups || [])];
            while (stackGroups.length) {
                const group = stackGroups.pop();
                if (group.groups?.length) {
                    stackGroups.push(...group.groups);
                }
                if (group.records?.length) {
                    rawRecords.push(...group.records);
                }
            }
        } else {
            rawRecords = result.records || [];
        }
        const templateIds = rawRecords
            .map((r) => r.resId ?? r.id)
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
        return result;
    }
}

/** 卡片组件按 resId 取 payload（非 reactive，不触发 Owl effect）。 */
export function getProductCardPayload(resId) {
    return (resId != null && payloadByResId.get(resId)) || null;
}
