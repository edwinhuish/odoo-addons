/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

import { VariantConversionDialog } from "./variant_conversion_dialog";

/**
 * 保存时自动检测变体变化，取代原来产品表单上的「添加属性与变体」按钮。
 *
 * 用户在产品表单的原生「属性与变体」页改完属性、点保存时，这里先问服务端
 * （``product.template.get_variant_conversion_preview``）这次改动会不会动到既有变体：
 *
 * - 会丢既有变体（删取值 / 删属性）→ 提示并拦住保存，绝不静默删除变体；
 * - 会新增变体 → 弹出归属确认框，用户在弹窗里确认每条既有变体占哪个组合之前，
 *   保存不继续（返回 false，表单保持未保存状态）；确认后把归属映射放进本次保存的
 *   ``changes``（服务端字段 ``variant_conversion_mapping``）再重走一次保存，
 *   属性改动与归属映射因此是同一次写库、同一个事务；
 * - 两种之外（例如只加「不生成变体」的属性、只调顺序）→ 正常保存。
 *
 * 注：``onWillSaveRecord(record, changes)`` 是 Odoo 表单控制器的官方保存前钩子
 * （返回 false 即阻止保存，``changes`` 会原样发给 ``web_save``），见模块 AGENTS.md → L2 P4。
 */
patch(FormController.prototype, {
    async onWillSaveRecord(record, changes) {
        if (
            record.resModel !== "product.template" ||
            !record.resId ||
            !("attribute_line_ids" in changes)
        ) {
            return super.onWillSaveRecord(...arguments);
        }
        const attributeLines = JSON.stringify(changes.attribute_line_ids);
        // 已经就这组属性命令确认过归属 → 直接放行（确认后的第二次保存走这一支）。
        // 记的是命令本身而不是「确认过一次」：保存失败后用户又改了属性，就应当重新弹窗确认。
        if (changes.variant_conversion_mapping && this._variantConversionConfirmedFor === attributeLines) {
            return super.onWillSaveRecord(...arguments);
        }
        const preview = await this.env.services.orm.call(
            "product.template",
            "get_variant_conversion_preview",
            [[record.resId], changes.attribute_line_ids]
        );
        if (preview.blocked) {
            this.env.services.notification.add(preview.blocked, {
                type: "danger",
                sticky: true,
            });
            return false;
        }
        if (!preview.required) {
            return super.onWillSaveRecord(...arguments);
        }
        this.env.services.dialog.add(VariantConversionDialog, {
            preview,
            onConfirm: async (mapping) => {
                await record.update({ variant_conversion_mapping: JSON.stringify(mapping) });
                this._variantConversionConfirmedFor = attributeLines;
                // 保存入口是控制器的 save()（内部走 Record.save()），**不是** this.model.save()：
                // RelationalModel 上没有 save 方法（保存挂在 Record 上：this.model.root.save()），
                // 而且控制器这层才负责挂 onSaveError。写错会报
                // "Uncaught Promise > this.model.save is not a function"。
                await this.save();
            },
        });
        return false;
    },
});
