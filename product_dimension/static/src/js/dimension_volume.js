/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Record } from "@web/model/relational_model/record";

import {
    DIMENSION_FIELDS,
    DIMENSION_SIZE_FIELDS,
    DIMENSION_UNIT_FIELD,
    VOLUME_FIELD,
    volumeFromDimensions,
} from "./dimension_volume_rules";

/**
 * 表单里改尺寸 / 单位时，**在浏览器里**算好 `volume` 并写回同一个字段，不再让后端为界面算一遍。
 *
 * - **触发条件**：表单中的 `dimension_unit` / `dimension_length` / `dimension_width` /
 *   `dimension_height` 任一被改动。改的是 `volume` 自己（用户手填）或只是加载记录时都不触发。
 * - **完整性校验**：单位 `cm` 按厘米换算、其余按米；长宽高必须都 > 0，否则体积给 0。
 * - **计算**：见 `./dimension_volume_rules`（与后端同一套规则），再按键位 `digits`
 *   （原生 `Volume` 的精度，模块安装时会确保不低于 6 位）取整。
 * - **展示**：写回的就是表单里那个原生 `Volume` 字段（同一位置、不新增只读副本），
 *   随表单一起提交；后端收到 `volume` 后不再重算（见 `models/product_product.py::write()`）。
 *
 * 钩在 `_update`（变更已落到 `data` 之后）而不是 `update`：`update` 内部要排队执行，
 * 在那里同步读 `this.data` 会读到改动前的旧值。
 */
patch(Record.prototype, {
    async _update(changes, options) {
        const dimensionsChanged =
            Boolean(changes) && DIMENSION_FIELDS.some((name) => name in changes);
        const result = await super._update(changes, options);
        if (dimensionsChanged && !(VOLUME_FIELD in changes)) {
            this._setVolumeFromDimensions();
        }
        return result;
    },

    /** 按当前尺寸重算体积并写回 `volume`；单位 / 长宽高不完整时给 0。 */
    _setVolumeFromDimensions() {
        const volumeField = this.fields && this.fields[VOLUME_FIELD];
        if (!volumeField || volumeField.type !== "float") {
            return; // 视图里没有 Volume 字段（例如被隐藏的表单）就不介入
        }
        const data = this.data;
        const volume = volumeFromDimensions(
            data[DIMENSION_UNIT_FIELD],
            data[DIMENSION_SIZE_FIELDS[0]],
            data[DIMENSION_SIZE_FIELDS[1]],
            data[DIMENSION_SIZE_FIELDS[2]],
            volumeDecimals(volumeField)
        );
        if (volume !== data[VOLUME_FIELD]) {
            // 走公开 update（与用户手填同一个入口），变更会随表单一起提交
            this.update({ [VOLUME_FIELD]: volume });
        }
    },
});

/** 字段的 `digits` → 小数位数（原生 `Volume` 按全局「Volume」精度；没配时按 Odoo 的出厂值 2 位）。 */
function volumeDecimals(volumeField) {
    const digits = volumeField.digits;
    if (Array.isArray(digits) && digits.length > 1 && digits[1] >= 0) {
        return digits[1];
    }
    return 2;
}
