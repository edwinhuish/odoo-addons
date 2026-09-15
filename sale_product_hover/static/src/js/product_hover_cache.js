/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

/**
 * 订单行悬浮卡片的数据缓存。
 *
 * key 的取法见 `product_hover_list_patch.js` 的 `_getProductHoverKey()`：
 * **已保存行用数据库 id（数字）**，**未保存的新行用 Owl datapoint id（字符串
 * `"datapoint_N"`）**——两者不会冲突，也不依赖记录是否已入库。
 *
 * 缓存与「已请求」集合都是**模块级非 reactive 容器**：挂到 reactive 对象上会触发
 * Owl 的重渲染 / 重载循环（同 product_card_view 的 P1 踩坑），故此处不做响应式处理。
 */
const payloadByKey = new Map();
/** 已请求过的**已保存**订单行（数据库 id）。 */
const requestedLineIds = new Set();
/**
 * 已请求过的**未保存**新行：`key -> 上次请求时的取值签名`。
 * 数量 / 单价 / 单位一变签名就变，会重新取数——这就是「新增产品实时预览」的实现方式。
 */
const requestedDraftSignatures = new Map();

/**
 * 缓存上限：只在一次会话里翻过非常大量订单行时才会触发（清空后按需重新预取），
 * 避免长时间使用后内存无上限增长。
 */
const MAX_CACHED_LINES = 2000;

function debugInfo(...args) {
    if (typeof odoo !== "undefined" && odoo.debug) {
        console.info(...args);
    }
}

/** 取某一行的展示数据（未预取到则返回 undefined）。 */
export function getLineHoverPayload(key) {
    return payloadByKey.get(key);
}

/**
 * 批量预取**已保存**订单行的展示数据（自动去重 + 增量）。
 *
 * 列表页挂载与每次 DOM 更新后各调一次：第一页一次请求；翻页 / 筛选后按差集只请求
 * 新出现的行，悬停时不再发起任何请求。请求失败会回退「已请求」标记以便重试。
 */
export async function prefetchLineHoverPayload(lineIds) {
    // 超过上限先整体清空（含「已请求」标记），随后按本次 ids 重新建立缓存
    if (payloadByKey.size > MAX_CACHED_LINES) {
        payloadByKey.clear();
        requestedLineIds.clear();
        requestedDraftSignatures.clear();
    }
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
                payloadByKey.set(lineId, data);
                received += 1;
            }
        }
        debugInfo(
            `[sale_product_hover] payload: requested ${ids.length} saved line(s), received ${received}`
        );
    } catch (error) {
        for (const lineId of ids) {
            requestedLineIds.delete(lineId);
        }
        console.warn("sale_product_hover: unable to load product preview data", error);
    }
}

/** 未保存新行的取值签名：任一与展示相关的取值变化都要重新取数。 */
function draftSignature(draft) {
    return [
        draft.product_id,
        draft.quantity,
        draft.uom_name,
        draft.price_unit,
        draft.currency_id,
    ].join("|");
}

/**
 * 预取**尚未保存**的新行（刚新增的产品行）展示数据。
 *
 * 新行没有数据库 id，只能把表单里正在编辑的值交给后端格式化；签名未变（用户没改数量 /
 * 单价 / 单位）时直接命中上一次结果、**不发请求**，所以悬停通常依然不发请求。
 * 只有「改了数量 / 单价之后再悬停」才会补一次请求，从而做到实时预览。
 */
export async function prefetchDraftHoverPayload(drafts) {
    const pending = [];
    for (const draft of drafts || []) {
        if (!draft || !draft.key || !draft.product_id) {
            continue;
        }
        const signature = draftSignature(draft);
        if (requestedDraftSignatures.get(draft.key) === signature) {
            continue;
        }
        requestedDraftSignatures.set(draft.key, signature);
        pending.push(draft);
    }
    if (!pending.length) {
        return;
    }
    try {
        const payload = await rpc("/sale_product_hover/payload", { drafts: pending });
        let received = 0;
        for (const draft of pending) {
            const data = payload && payload[draft.key];
            if (data) {
                payloadByKey.set(draft.key, data);
                received += 1;
            }
        }
        debugInfo(
            `[sale_product_hover] payload: requested ${pending.length} draft line(s), received ${received}`
        );
    } catch (error) {
        for (const draft of pending) {
            requestedDraftSignatures.delete(draft.key);
        }
        console.warn("sale_product_hover: unable to load product preview data", error);
    }
}
