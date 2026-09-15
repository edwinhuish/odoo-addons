/** @odoo-module **/

import { user } from "@web/core/user";
import { formatFloat } from "@web/core/utils/numbers";
import { formatMonetary } from "@web/views/fields/formatters";

/**
 * 未保存的新行（刚新增的产品行）的卡片数据：**直接从产品取**。
 *
 * 为什么不走订单行的接口：订单行还没保存，服务端根本没有这条记录，
 * 按行 id 反查必然查不到；而这条行上要展示的东西，来源其实很干净：
 *
 * - **产品侧**（名称 / 型号 / 规格 / 描述 / 图片 / 产品售价 / 可用库存）→ 按 `product_id`
 *   读 `product.product`，与订单没有任何关系；
 * - **行侧**（数量 / 单位 / 单价 / 币种）→ 就是表单里**正在编辑**的值，前端本来就有。
 *
 * 因此这里用**标准 ORM**（`searchRead`，任何后端版本都可用、也应用记录规则），
 * 不依赖任何自研接口，数字用 Odoo 自己的前端格式化工具渲染
 * （`formatFloat` / `formatMonetary`），与已保存行走服务端 `formatLang` 的效果一致。
 */

/** 需要读取的产品字段（`stock` 是本模块的依赖，`qty_available` / `is_storable` 一定存在）。 */
const PRODUCT_FIELDS = [
    "display_name",
    "default_code",
    "description_sale",
    "list_price",
    "uom_id",
    "qty_available",
    "is_storable",
    "product_template_attribute_value_ids",
];

/** "Product Unit" 小数位：与后端 `formatLang(..., dp="Product Unit")` 同口径，每会话只读一次。 */
let unitDigitsPromise = null;
export function getUnitDigits(orm) {
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
 * @param {object} orm `@web/core/orm_service` 的 orm 服务
 * @param {number[]} productIds
 * @param {Map<number, object>} cache productId -> 产品数据（读不到时存 null，避免反复请求）
 * @returns {Promise<number>} 本次实际发起读取的产品数（0 = 全部缓存命中，未发请求）
 */
export async function fetchProducts(orm, productIds, cache) {
    const missing = [...new Set(productIds)].filter((id) => id && !cache.has(id));
    if (!missing.length) {
        return 0;
    }
    const rows = await orm.searchRead("product.product", [["id", "in", missing]], PRODUCT_FIELDS);
    for (const row of rows) {
        cache.set(row.id, row);
    }
    // 读不到的产品也记下来：否则每次悬停都会为一个无权限的产品重复请求
    for (const id of missing) {
        if (!cache.has(id)) {
            cache.set(id, null);
        }
    }
    return missing.length;
}

/**
 * 把「产品数据 + 行上正在编辑的值」装配成卡片 payload（字段与已保存行的口径完全一致）。
 *
 * @param {object} product `product.product` 的一行数据（`searchRead` 结果）
 * @param {object} context `{key, product_id, quantity, uom_name, price_unit, currency_id}`
 * @param {number} unitDigits "Product Unit" 小数位
 * @returns {object} payload
 */
export function buildProductHoverPayload(product, context, unitDigits) {
    const companyCurrencyId = user.activeCompany?.currency_id || null;
    const orderCurrencyId = context.currency_id || companyCurrencyId;
    const listPrice = product.list_price || 0;
    const priceUnit = context.price_unit || 0;
    // 规格：变体属性值在 searchRead 结果里就是 [id, display_name]（如 "颜色: 黑"）
    const specification = (product.product_template_attribute_value_ids || [])
        .map((value) => value[1])
        .join(", ");
    const uom = product.uom_id;
    const productUomName = uom ? uom[1] : "";
    const lineUomName = context.uom_name || productUomName;
    return {
        line_id: context.key,
        product_id: context.product_id,
        name: stripReference(product.display_name, product.default_code),
        reference: product.default_code || "",
        specification,
        image_url: `/web/image/product.product/${context.product_id}/image_256`,
        description: product.description_sale || "",
        qty_ordered_text: formatFloat(context.quantity || 0, { digits: [1, unitDigits] }),
        uom_name: lineUomName,
        unit_price_text: formatMonetary(priceUnit, { currencyId: orderCurrencyId }),
        list_price_text: formatMonetary(listPrice, { currencyId: companyCurrencyId }),
        // 本单单价（订单币种）与产品售价（公司币种）相同时不重复展示，与后端口径一致
        show_list_price:
            orderCurrencyId !== companyCurrencyId || Math.abs(priceUnit - listPrice) > 1e-6,
        qty_available_text: product.is_storable
            ? formatFloat(product.qty_available || 0, { digits: [1, unitDigits] })
            : "",
        available_uom_name: productUomName || lineUomName,
    };
}
