/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { formatFloat } from "@web/core/utils/numbers";

/**
 * 订单行悬浮卡片的数据层。
 *
 * **两条取数路径**（对外都只暴露 `getLineHoverPayload(key)`，卡片组件不关心数据从哪来）：
 *
 * 1. **已保存行**：行已在库里，走自研接口 `/sale_product_hover/payload`（按行 id 批量，
 *    服务端用 `formatLang` 一次装配，含可用库存等）；
 * 2. **未保存的新行**：行还没落库，服务端根本没有这条记录，**按行 id 反查必然查不到**。
 *    所以改用**直接从产品取数**：按 `product_id` 用标准 ORM 读 `product.product`
 *    （任何后端版本都可用，不依赖自研接口），数字用 Odoo 前端格式化工具渲染。
 *
 * **卡片只展示产品侧信息**（图片 / 名称 / 型号 / 规格 / 描述 / 可用库存），
 * **不含任何价格**（行上的数量 / 单价与产品售价都不展示；浮层的定位是"产品详情"，
 * 价格信息在订单行与产品表单上本来就看得见）。
 * 因此这里连行的取值都不需要读：`context` 只有 `{key, product_id}`，装配结果只由产品决定。
 *
 * key 的取法见 `product_hover_list_patch.js` 的 `_getProductHoverKey()`：
 * **已保存行用数据库 id（数字）**，**未保存的新行用 Owl datapoint id（字符串
 * `"datapoint_N"`）**——两者不会冲突，新行也不必等落库才能预览。
 *
 * 缓存与「已请求」集合都是**模块级非 reactive 容器**：挂到 reactive 对象上会触发
 * Owl 的重渲染 / 重载循环（同 product_card_view 的 P1 踩坑），故此处不做响应式处理。
 *
 * **本文件刻意不拆成多个文件**：往 `__manifest__.py` 的 assets 里**新增文件**需要服务端
 * 重新读取 manifest（`-u` / 重启进程）才会出现在 bundle 里，否则浏览器会报
 * `The following modules are needed by other modules but have not been defined:
 * ['@sale_product_hover/js/…']`。只改本文件内容则不需要动服务端（`?debug=assets` 下
 * assets 会按文件 mtime 自动重建），只需要强刷浏览器。
 *
 * 本模块对外导出 `getLineHoverPayload` / `prefetchLineHoverPayload` / `prefetchDraftHoverPayload` /
 * `setClientVersion` / `ensureServerDiagnostics`。**整份重写本文件时务必逐个确认导出还在**
 * ——`19.0.1.3.1` 曾漏掉 `getLineHoverPayload`，表现为悬停时
 * `Uncaught TypeError: getLineHoverPayload is not a function`；改完请按根 `AGENTS.md`
 * 第 6 节的脚本跑一次「命名导入 vs 导出」自查。
 */
const payloadByKey = new Map();
/** 已请求过的**已保存**订单行（数据库 id）。 */
const requestedLineIds = new Set();
/** 未保存新行的取值签名：`key -> 上次装配时的产品 id`，变了才重新装配。 */
const draftSignatureByKey = new Map();

/** 产品数据缓存（未保存新行走它）：`productId -> 产品数据 | null`（null = 读不到，不再重试）。 */
const productById = new Map();

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
let selfChecked = false;
/** 服务端版本探测的 Promise（每会话只发一次请求，结果缓存）。 */
let serverVersionProbe = null;
/** 只告警一次，避免悬停时反复刷屏（重试逻辑照常执行）。 */
let serverReported = false;

/** 由 list 补丁在启动时调用，登记当前前端资源版本。 */
export function setClientVersion(version) {
    clientVersion = version;
}

function debugInfo(...args) {
    if (typeof odoo !== "undefined" && odoo.debug) {
        console.info(...args);
    }
}

/** 取某一行的展示数据（未预取到则返回 undefined）。 */
export function getLineHoverPayload(key) {
    return payloadByKey.get(key);
}

// ----------------------------------------------------------------------------
// 已保存行：走自研接口
// ----------------------------------------------------------------------------

/**
 * 探测服务端模块版本（每个会话只发一次请求，结果缓存）。
 *
 * 用**空 `line_ids`** 请求：接口在新旧两种后端上都**会成功返回**——旧后端返回 `{}`，
 * 新后端多一个保留键 `__server_version`。所以它能在不依赖任何新参数的前提下，
 * 干净地区分「服务端 Python 没升级」与「业务上确实没有数据」。
 *
 * 注意：**绝不能带 `drafts` / `version` 这类新参数**——旧后端的处理函数不认识它们会直接
 * 抛 TypeError，整个请求失败，那样连「旧后端」这个结论都拿不到，还会连带把已保存行的
 * 预览一起打没。
 *
 * @returns {Promise<string|null>} 服务端模块版本；旧后端 / 请求失败时为 null
 */
function probeServerVersion() {
    if (!serverVersionProbe) {
        serverVersionProbe = rpc("/sale_product_hover/payload", { line_ids: [] })
            .then((payload) => (payload && payload[SERVER_VERSION_KEY]) || null)
            .catch(() => null);
    }
    return serverVersionProbe;
}

const NOT_UPGRADED_HINT =
    "the server does NOT report __server_version, i.e. its Python code is not upgraded. " +
    "Run `odoo -d <db> -u sale_product_hover --stop-after-init` and RESTART the server process " +
    "(a running process keeps the old Python in memory), then hard refresh (Ctrl+Shift+R). " +
    "Note: in `?debug=assets` mode JS/SCSS are rebuilt from files on the fly, so the front-end can be " +
    "up to date while the back-end is not — that is why this happens.";

/**
 * 启动自检（每个会话一次，只在订单行列表出现时调用）。
 *
 * 结论汇总成**一行** `console.info`，排查时先看这一行：
 * `self-check: assets X, server Y` → 两端一致；`server NOT UPGRADED …` → 服务端没升级。
 * 它只影响**已保存行**的取数（未保存行是前端直接查产品，与服务端版本无关）。
 */
export function ensureServerDiagnostics() {
    if (selfChecked) {
        return Promise.resolve(null);
    }
    selfChecked = true;
    return probeServerVersion().then((serverVersion) => {
        if (serverVersion === clientVersion) {
            console.info(
                `[sale_product_hover] self-check: assets ${clientVersion}, server ${serverVersion} (ok)`
            );
        } else {
            console.error(
                `[sale_product_hover] self-check: assets ${clientVersion}, server ${
                    serverVersion || "NOT UPGRADED"
                } → ${NOT_UPGRADED_HINT}`
            );
        }
        return serverVersion;
    });
}

/** 成功路径的版本自证（只在第一次发现不一致时告警一次）。 */
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
    console.error(
        `sale_product_hover: server module version is ${serverVersion || "unknown"} while the ` +
            `loaded assets are ${clientVersion}. Run \`-u sale_product_hover\`, RESTART the server ` +
            "and hard refresh (Ctrl+Shift+R) — the hover card cannot work with mismatched versions."
    );
}

/** 已保存行取数失败时的统一诊断（只报一次）：现象 + 服务端版本结论。 */
function reportServerFailure(message, detail) {
    if (serverReported) {
        return;
    }
    serverReported = true;
    console.error(`[sale_product_hover] ${message}`, detail);
    probeServerVersion().then((serverVersion) => {
        if (serverVersion) {
            console.error(
                `sale_product_hover: the server runs ${serverVersion} (upgraded) — so this is a ` +
                    "**data/permission** problem, not a deployment one. Check the server log for " +
                    "`sale_product_hover: product … not found or not readable`."
            );
        } else {
            console.error(`sale_product_hover: ${NOT_UPGRADED_HINT}`);
        }
    });
}

/**
 * 批量预取**已保存**订单行的展示数据（自动去重 + 增量）。
 *
 * 列表页挂载与每次 DOM 更新后各调一次：第一页一次请求；翻页 / 筛选后按差集只请求
 * 新出现的行，悬停时不再发起任何请求。请求失败会回退「已请求」标记以便重试。
 */
export async function prefetchLineHoverPayload(lineIds) {
    clearCacheIfTooLarge();
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
        // 只发这一版接口本就认识的参数：多带一个未知 kwarg 会让旧后端整批报错
        const payload = await rpc("/sale_product_hover/payload", { line_ids: ids });
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
            // 一条都没回来：回退标记让下次能重试，并给出诊断结论
            for (const lineId of ids) {
                requestedLineIds.delete(lineId);
            }
            reportServerFailure(
                `no preview data returned for ${ids.length} saved order line(s) (${ids.join(", ")})`
            );
        }
        debugInfo(
            `[sale_product_hover] payload: requested ${ids.length} saved line(s), received ${received}`
        );
    } catch (error) {
        for (const lineId of ids) {
            requestedLineIds.delete(lineId);
        }
        reportServerFailure("unable to load product preview data (saved lines)", error);
    }
}

// ----------------------------------------------------------------------------
// 未保存的新行：直接从产品取数（标准 ORM）
//
// 展示内容全部来自产品（名称 / 型号 / 规格 / 描述 / 图片 / 可用库存），与订单
// 没有任何关系，所以按 `product_id` 读 `product.product` 就够了。库存数字用 Odoo 前端
// 格式化工具渲染，与已保存行走后端 `formatLang` 的输出等价（**不含任何价格**，故不再需要
// 读 `list_price`，也不必处理公司币种）。
// ----------------------------------------------------------------------------

/** 需要读取的产品字段（`stock` 是本模块的依赖，`qty_available` / `is_storable` 一定存在）。 */
const PRODUCT_FIELDS = [
    "display_name",
    "default_code",
    "description_sale",
    "uom_id",
    "qty_available",
    "is_storable",
    "product_template_attribute_value_ids",
];

/** "Product Unit" 小数位：与后端 `formatLang(..., dp="Product Unit")` 同口径，每会话只读一次。 */
let unitDigitsPromise = null;
function getUnitDigits(orm) {
    if (!unitDigitsPromise) {
        unitDigitsPromise = orm
            .searchRead("decimal.precision", [["name", "=", "Product Unit"]], ["digits"], {
                limit: 1,
            })
            .then((rows) => (rows.length ? rows[0].digits : 2))
            .catch(() => 2);
    }
    return unitDigitsPromise;
}

/**
 * 与 Odoo `_compute_display_name` 的 `display_default_code=False` 同口径：
 * 去掉名称开头的 `[参考号] ` 前缀（型号在卡片里单独展示，不重复）。
 */
function stripReference(displayName, defaultCode) {
    const name = displayName || "";
    const prefix = defaultCode ? `[${defaultCode}] ` : "";
    return prefix && name.startsWith(prefix) ? name.slice(prefix.length) : name;
}

/**
 * 批量读取产品数据（跳过已缓存的）。
 *
 * 用 `searchRead` 而不是 `read`：产品 id 来自表单，`searchRead` 会应用记录规则并**自动剔除**
 * 当前用户读不到的产品，不会因为一个越权 / 已删除的 id 让整批读取抛错。
 *
 * @param {object} orm `@web/core/orm_service` 的 orm 服务（`this.orm`）
 * @param {number[]} productIds
 * @returns {Promise<number>} 本次实际发起读取的产品数（0 = 全部缓存命中，未发请求）
 */
async function fetchProducts(orm, productIds) {
    const missing = [...new Set(productIds)].filter((id) => id && !productById.has(id));
    if (!missing.length) {
        return 0;
    }
    const rows = await orm.searchRead("product.product", [["id", "in", missing]], PRODUCT_FIELDS);
    for (const row of rows) {
        productById.set(row.id, row);
    }
    // 读不到的产品也记下来：否则每次悬停都会为一个无权限的产品重复请求
    for (const id of missing) {
        if (!productById.has(id)) {
            productById.set(id, null);
        }
    }
    return missing.length;
}

/**
 * 把产品数据装配成卡片 payload（字段与已保存行的口径完全一致）。
 *
 * @param {object} product `product.product` 的一行数据（`searchRead` 结果）
 * @param {object} context `{key, product_id}`
 * @param {number} unitDigits "Product Unit" 小数位
 * @returns {object} payload（字段说明见 README「卡片 payload 字段」）
 */
function buildProductHoverPayload(product, context, unitDigits) {
    // 规格：变体属性值在 searchRead 结果里就是 [id, display_name]（如 "颜色: 黑"）
    const specification = (product.product_template_attribute_value_ids || [])
        .map((value) => value[1])
        .join(", ");
    return {
        line_id: context.key,
        product_id: context.product_id,
        name: stripReference(product.display_name, product.default_code),
        reference: product.default_code || "",
        specification,
        image_url: `/web/image/product.product/${context.product_id}/image_256`,
        description: product.description_sale || "",
        qty_available_text: product.is_storable
            ? formatFloat(product.qty_available || 0, { digits: [1, unitDigits] })
            : "",
        available_uom_name: product.uom_id ? product.uom_id[1] : "",
    };
}

/** 未保存新行的取值签名：展示内容只由产品决定，所以签名就是产品 id。 */
function draftSignature(context) {
    return String(context.product_id);
}

/**
 * 预取**尚未保存**的新行（刚新增的产品行）展示数据。
 *
 * 不从订单里查（订单行还没落库，服务端查不到），而是**按 `product_id` 读产品**：
 * 产品数据一次批量读入 `productById` 缓存（同一产品的多行共用）。
 *
 * @param {object} orm `this.orm`（ListRenderer 已有）
 * @param {object[]} contexts `{key, product_id}`
 */
export async function prefetchDraftHoverPayload(orm, contexts) {
    clearCacheIfTooLarge();
    const pending = (contexts || []).filter((context) => {
        if (!context || !context.key || !context.product_id) {
            // 静默跳过会让「为什么没预览」更难查，故留下 debug 线索
            debugInfo("[sale_product_hover] skip draft without key / product:", context);
            return false;
        }
        return true;
    });
    if (!pending.length) {
        return;
    }
    try {
        const [unitDigits] = await Promise.all([
            getUnitDigits(orm),
            fetchProducts(
                orm,
                pending.map((context) => context.product_id)
            ),
        ]);
        let assembled = 0;
        for (const context of pending) {
            const signature = draftSignature(context);
            const product = productById.get(context.product_id);
            if (!product) {
                // 产品不存在 / 当前用户读不到：不装配（前端表现为不弹浮层）
                draftSignatureByKey.delete(context.key);
                payloadByKey.delete(context.key);
                debugInfo(
                    "[sale_product_hover] skip: product",
                    context.product_id,
                    "not found or not readable"
                );
                continue;
            }
            if (
                draftSignatureByKey.get(context.key) === signature &&
                payloadByKey.has(context.key)
            ) {
                continue;
            }
            payloadByKey.set(context.key, buildProductHoverPayload(product, context, unitDigits));
            draftSignatureByKey.set(context.key, signature);
            assembled += 1;
        }
        debugInfo(
            `[sale_product_hover] payload: requested ${pending.length} new line(s), assembled ${assembled}`
        );
    } catch (error) {
        console.warn("sale_product_hover: unable to build preview data from the product", error);
    }
}

function clearCacheIfTooLarge() {
    if (payloadByKey.size > MAX_CACHED_LINES) {
        payloadByKey.clear();
        requestedLineIds.clear();
        draftSignatureByKey.clear();
    }
}
