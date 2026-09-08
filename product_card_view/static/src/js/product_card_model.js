/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { RelationalModel } from "@web/model/relational_model/relational_model";

// 全局 payload 缓存（按 resId 索引）。非 reactive，不触发 Owl effect。
// 由 ProductCardRenderer 的生命周期钩子（onWillStart / onWillUpdateProps）填充，
// 不在 reactive effect 内，避免触发 Owl DataModel 的 onUpdate / reload 循环。
// 单视图假设：reload 时 clear + 重新填充。
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
export async function fillProductCardPayload(records) {
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
export function getProductCardPayload(resId) {
    return (resId != null && payloadByResId.get(resId)) || null;
}
