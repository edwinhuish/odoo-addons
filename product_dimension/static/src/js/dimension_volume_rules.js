/** @odoo-module **/

/**
 * 体积计算的**纯规则**：不依赖任何 Odoo 模块，因此可以用 node 直接跑单元测试
 * （模块测试 `test_frontend_rules_produce_the_same_volumes_as_the_backend()` 就是这么用的）。
 *
 * 与后端 `models/product_product.py::volume_from_dimensions()` 必须一致：改这里就要同步那边。
 */

export const DIMENSION_UNIT_FIELD = "dimension_unit";
export const DIMENSION_SIZE_FIELDS = ["dimension_length", "dimension_width", "dimension_height"];
export const DIMENSION_FIELDS = [DIMENSION_UNIT_FIELD, ...DIMENSION_SIZE_FIELDS];
export const VOLUME_FIELD = "volume";

/* 立方厘米 → 立方米 */
export const CM3_PER_M3 = 1000000;

/**
 * 按小数位数取整。
 *
 * 注意 `decimals` 是**小数位数**（2 表示两位小数）：Odoo 的 `roundPrecision()` 要的是
 * **精度因子**（`0.01` 才是两位小数），早前把 `2` 当因子传进去，等于「按 2 的整数倍取整」，
 * 于是任何小于 1 的体积都被算成了 0（就是「填了尺寸、体积显示 0」那个 bug）。
 */
export function roundToDecimals(value, decimals) {
    const factor = Math.pow(10, decimals);
    return Math.round(value * factor) / factor;
}

/**
 * 按尺寸算体积（立方米），再按 `decimals` 位小数取整。
 *
 * - 单位 `cm` → `长 × 宽 × 高 / 1 000 000`；其余（`m` 或未设置）→ 直接相乘；
 * - 长宽高任一非正 → 0（尺寸不齐则体积不成立，与后端同规则）。
 */
export function volumeFromDimensions(dimensionUnit, length, width, height, decimals) {
    const sizes = [length || 0, width || 0, height || 0];
    if (!sizes.every((size) => size > 0)) {
        return 0;
    }
    const factor = dimensionUnit === "cm" ? CM3_PER_M3 : 1;
    const volume = sizes.reduce((total, size) => total * size, 1) / factor;
    return roundToDecimals(volume, decimals);
}
