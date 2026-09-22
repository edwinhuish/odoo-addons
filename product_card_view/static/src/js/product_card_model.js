/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { RelationalModel } from "@web/model/relational_model/relational_model";

// 全局 payload 缓存（按 resId 索引）。非 reactive，不触发 Owl effect。
// 由 ProductCardRenderer 的生命周期钩子（onWillStart / onWillUpdateProps）与
// useEffect 填充，均不在 reactive effect 内，避免触发 Owl DataModel 的
// onUpdate / reload 循环。
// 单视图假设：每次成功取到数据后按「本页 id 列表」整体替换。
const payloadByResId = new Map();

// 请求序号：只有最后一次发出的请求允许写入，避免并发响应乱序覆盖
let requestSeq = 0;
// 已请求过的 id 批次：同一批 id 不重复发请求；请求失败会清空以便重试
let requestedKey = null;

export class ProductCardModel extends RelationalModel {
    // 关闭缓存：payload 由 Renderer 填充全局 Map，缓存命中的请求不会重新填充，
    // 会导致卡片数据陈旧。
    static withCache = false;
}

/**
 * 收集本页待取数的记录。
 *
 * - 未分组：`list.records`；
 * - 分组：`list.groups[].list.records`（多级分组时分组内仍是分组列表，继续下钻）。
 *
 * 只按这一处取数，分组视图才不会取到空列表（分组时 `list.records` 为空）。
 *
 * @param {Object} list props.list（DynamicRecordList / DynamicGroupList）
 * @returns {Array} Record 实例数组
 */
export function collectCardRecords(list) {
    const records = [];
    const walk = (node) => {
        if (!node) {
            return;
        }
        for (const record of node.records || []) {
            records.push(record);
        }
        for (const group of node.groups || []) {
            walk(group.list);
        }
    };
    walk(list);
    return records;
}

/**
 * 本页记录的数据库 id 列表（按渲染顺序）。
 *
 * @param {Object} list props.list
 * @returns {number[]}
 */
export function collectCardRecordIds(list) {
    const ids = [];
    for (const record of collectCardRecords(list)) {
        const resId = record.resId ?? record.id;
        if (resId != null) {
            ids.push(resId);
        }
    }
    return ids;
}

/** 批次 key：id 列表没变就不必重新请求。 */
export function cardRecordIdsKey(templateIds) {
    return templateIds.join(",");
}

/**
 * 拉取并填充本页产品的卡片 payload（按 resId 索引全局 Map）。
 *
 * 与「先 clear 再 await」的写法的区别（这是切换筛选 / 分组后卡片空白的关键）：
 * 1) 请求发出后到响应回来之间**不清空** —— 这期间若发生渲染，卡片仍能取到上一批
 *    数据，不会整页空白；
 * 2) 响应回来后整体替换（原子），并用 requestSeq 丢弃过期响应。
 *
 * @param {number[]} templateIds 本页 `product.template` 数据库 id
 * @returns {Promise<boolean>} Map 内容是否发生变化（调用方据此决定是否重渲染）
 */
export async function fillProductCardPayload(templateIds) {
    const key = cardRecordIdsKey(templateIds);
    if (key === requestedKey) {
        return false; // 同一批 id 已在请求中 / 已取到
    }
    requestedKey = key;
    const seq = ++requestSeq;
    let payload = {};
    if (templateIds.length) {
        try {
            payload =
                (await rpc("/product_card/payload", { template_ids: templateIds })) || {};
        } catch (error) {
            // 取数失败时清掉批次标记允许重试；卡片有空 payload 兜底，不让视图报错
            if (seq === requestSeq) {
                requestedKey = null;
            }
            console.error("[product_card_view] failed to load card payload", error);
            return false;
        }
    }
    if (seq !== requestSeq) {
        return false; // 已有更新的请求，丢弃本次结果
    }
    payloadByResId.clear();
    for (const resId of templateIds) {
        const data = payload[resId];
        if (data) {
            payloadByResId.set(resId, data);
        }
    }
    return true;
}

/** 卡片组件按 resId 取 payload（非 reactive，不触发 Owl effect）。 */
export function getProductCardPayload(resId) {
    return (resId != null && payloadByResId.get(resId)) || null;
}
