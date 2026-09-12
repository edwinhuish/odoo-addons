/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

/**
 * 订单行悬浮卡片的数据缓存。
 *
 * 缓存与「已请求」集合都是**模块级非 reactive 容器**：挂到 reactive 对象上会触发
 * Owl 的重渲染 / 重载循环（同 product_card_view 的 P1 踩坑），故此处不做响应式处理。
 */
const payloadByLineId = new Map();
const requestedLineIds = new Set();

/** 取某一行的展示数据（未预取到则返回 undefined）。 */
export function getLineHoverPayload(lineId) {
    return payloadByLineId.get(lineId);
}

/**
 * 批量预取订单行展示数据（自动去重 + 增量）。
 *
 * 列表页挂载与每次 DOM 更新后各调一次：第一页一次请求；翻页 / 筛选后按差集只请求
 * 新出现的行，悬停时不再发起任何请求。请求失败会回退「已请求」标记以便重试。
 */
export async function prefetchLineHoverPayload(lineIds) {
    const ids = [];
    for (const lineId of lineIds || []) {
        if (lineId && !requestedLineIds.has(lineId)) {
            requestedLineIds.add(lineId);
            ids.push(lineId);
        }
    }
    if (!ids.length) {
        return;
    }
    try {
        const payload = await rpc("/sale_product_hover/payload", { line_ids: ids });
        let received = 0;
        for (const lineId of ids) {
            const data = payload && payload[lineId];
            if (data) {
                payloadByLineId.set(lineId, data);
                received += 1;
            }
        }
        if (typeof odoo !== "undefined" && odoo.debug) {
            console.debug(
                `[sale_product_hover] payload: requested ${ids.length}, received ${received}`
            );
        }
    } catch (error) {
        for (const lineId of ids) {
            requestedLineIds.delete(lineId);
        }
        console.warn("sale_product_hover: unable to load product preview data", error);
    }
}
