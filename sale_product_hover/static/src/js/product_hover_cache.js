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

/** 接口回显的服务端版本保留键（见 controllers/product_hover_controller.py）。 */
const SERVER_VERSION_KEY = "__server_version";

/** 前端资源版本，由 product_hover_list_patch.js 注入（避免两处各写一份）。 */
let clientVersion = "";
let versionChecked = false;
/** 「接口没返回数据」只告警一次，避免悬停时反复刷屏（重试逻辑照常执行）。 */
let noDataWarned = false;

/** 由 list 补丁在启动时调用，登记当前前端资源版本。 */
export function setClientVersion(version) {
    clientVersion = version;
}

function debugInfo(...args) {
    if (typeof odoo !== "undefined" && odoo.debug) {
        console.info(...args);
    }
}

/**
 * 版本自证：比对服务端回显的模块版本与前端资源版本。
 *
 * 二者不一致（或服务端没有回显 = Python 还是旧版本）时给出可执行的提示——
 * 本模块踩过多次「静态资源已更新、Python 没升级」的坑，而这在界面上只表现为
 * 「浮层不弹 / 字段缺失」，很难自己看出来。只在第一次发现不一致时告警一次。
 */
function checkServerVersion(payload) {
    const serverVersion = payload && payload[SERVER_VERSION_KEY];
    if (!clientVersion || serverVersion === clientVersion) {
        versionChecked = true;
        return;
    }
    if (versionChecked) {
        return;
    }
    versionChecked = true;
    console.warn(
        `sale_product_hover: server module version is ${serverVersion || "unknown"} ` +
            `while the loaded assets are ${clientVersion}. ` +
            "Run `-u sale_product_hover`, restart the server and hard refresh " +
            "(Ctrl+Shift+R) — the hover card cannot work with mismatched versions."
    );
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
        const payload = await rpc("/sale_product_hover/payload", {
            line_ids: ids,
            version: clientVersion,
        });
        checkServerVersion(payload);
        let received = 0;
        for (const lineId of ids) {
            const data = payload && payload[lineId];
            if (data) {
                payloadByKey.set(lineId, data);
                received += 1;
            }
        }
        if (!received) {
            // 一条都没回来：多半是后端未升级 / 接口报错，回退标记让下次能重试
            for (const lineId of ids) {
                requestedLineIds.delete(lineId);
            }
            if (!noDataWarned) {
                noDataWarned = true;
                console.warn(
                    `sale_product_hover: no preview data returned for ${ids.length} order line(s); ` +
                        "the hover card will retry on next list update. Check that the module was " +
                        "upgraded (-u sale_product_hover) and see the server log."
                );
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
        const payload = await rpc("/sale_product_hover/payload", {
            drafts: pending,
            version: clientVersion,
        });
        checkServerVersion(payload);
        const missing = [];
        let received = 0;
        for (const draft of pending) {
            const data = payload && payload[draft.key];
            if (data) {
                payloadByKey.set(draft.key, data);
                received += 1;
            } else {
                missing.push(draft.key);
            }
        }
        if (missing.length) {
            // 请求成功但这一行没有数据：**必须**回退签名，否则该行会被永久判为
            // 「已请求过」，之后每次悬停都被静默跳过、再也取不到数据。
            for (const key of missing) {
                requestedDraftSignatures.delete(key);
            }
            if (!noDataWarned) {
                noDataWarned = true;
                console.warn(
                    `sale_product_hover: no preview data returned for ${missing.length} newly ` +
                        `added line(s) (${missing.join(", ")}). If the module was just updated, ` +
                        "check that the server runs the new Python code (-u sale_product_hover " +
                        "+ restart) and that /sale_product_hover/payload accepts 'drafts'; " +
                        "otherwise check the server log for `sale_product_hover: product ... " +
                        "not found or not readable`."
                );
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
