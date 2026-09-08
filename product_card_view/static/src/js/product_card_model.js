/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { RelationalModel } from "@web/model/relational_model/relational_model";

// 全局 payload 缓存（按 resId 索引）。非 reactive，不触发 Owl effect。
// 由 ProductCardRenderer 的生命周期钩子（onWillStart / onWillUpdateProps）填充，
// 不在 reactive effect 内，避免触发 Owl DataModel 的 onUpdate / reload 循环。
// 单视图假设：reload 时 clear + 重新填充。
//
// 历史教训（不可重蹈）：
// ① 重写 _loadData 挂 result.records：_createRoot 重建 Record 丢弃 → 空白；
// ② 给 reactive model / record 实例加属性：触发 Owl DataModel 内部 effect → 卡死；
// ③ 重写 _loadData 给 model 赋值 / 重写 load：触发 notify → onUpdate → 再调 load → 无限循环卡死。
// 故 payload 关联只能放在 Renderer 生命周期钩子 + 全局 Map by resId。
const payloadByResId = new Map();

export class ProductCardModel extends RelationalModel {
    // 关闭缓存：payload 由 Renderer 钩子填充全局 Map，缓存命中的请求不会重新填充，
    // 会导致卡片数据陈旧。
    static withCache = false;
}

/**
 * 拉取并填充本页产品的卡片 payload（按 resId 索引全局 Map）。
 * 由 Renderer 的 onWillStart / onWillUpdateProps 调用，不在 reactive effect 内。
 * @param {Array} records Record 实例数组（非分组）或 group.records（分组）
 */
let _fillCount = 0;
export async function fillProductCardPayload(records) {
    _fillCount++;
    console.warn("[PCV DEBUG] fillProductCardPayload #" + _fillCount, "records=", records?.length);
    const templateIds = records
        .map((r) => r.resId ?? r.id)
        .filter((id) => id != null);
    payloadByResId.clear();
    if (!templateIds.length) {
        return;
    }
    const payload = await rpc("/product_card/payload", { template_ids: templateIds });
    for (const resId of templateIds) {
        if (payload && payload[resId]) {
            payloadByResId.set(resId, payload[resId]);
        }
    }
}

/** 卡片组件按 resId 取 payload（非 reactive，不触发 Owl effect）。 */
let _getCount = 0;
export function getProductCardPayload(resId) {
    _getCount++;
    if (_getCount <= 5 || _getCount % 50 === 0) {
        console.warn("[PCV DEBUG] getProductCardPayload #" + _getCount, "resId=", resId);
    }
    return (resId != null && payloadByResId.get(resId)) || null;
}
