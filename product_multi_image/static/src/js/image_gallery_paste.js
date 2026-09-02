/** @odoo-module **/

import { X2ManyField } from "@web/views/fields/x2many/x2many_field";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { getDataURLFromFile } from "@web/core/utils/urls";
import { checkFileSize } from "@web/core/utils/files";

/**
 * 图库粘贴新增（与 T-003 image_uploader 联动）
 *
 * 设计要点：
 * - 复用 image_uploader 已 patch 的 FileUploader 单图粘贴能力处理「编辑某行图片」
 * - 本 patch 在 X2ManyField 根元素拦截 paste，剪贴板含图片时**新增一行图片记录**
 *   并把 base64 写入 image_1920，满足「图库内粘贴即新增一条记录」验收标准
 * - 只对 comodel 为 product.image.gallery 的 X2ManyField 生效，其他 X2many 无影响
 * - 只读态直接返回，不触发写操作
 * - 剪贴板无图片时不拦截，放行浏览器默认行为（文本粘贴等）
 * - 一次粘贴多张图片逐张新增
 */

patch(X2ManyField.prototype, {
    /**
     * 是否为产品图库 X2Many（comodel = product.image.gallery）。
     * 仅对图库启用粘贴新增，其他 X2many 不受影响。
     */
    get isImageGallery() {
        const field = this.props.record.fields[this.props.name];
        return field && field.relation === "product.image.gallery";
    },

    /**
     * 粘贴：剪贴板含图片时逐张新增图库行，否则放行。
     * 只读态不触发。
     */
    async onPasteGallery(ev) {
        if (!this.isImageGallery || this.props.readonly) {
            return;
        }
        const files = extractImageFiles(ev);
        if (!files.length) {
            return; // 非图片，放行
        }
        ev.preventDefault();
        ev.stopPropagation();
        for (const file of files) {
            if (!file.type.startsWith("image/")) {
                continue;
            }
            if (!checkFileSize(file.size, this.notificationService)) {
                continue;
            }
            const data = await getDataURLFromFile(file);
            const base64 = data.split(",")[1];
            if (!base64) {
                this.notificationService.add(
                    _t("图片“%s”读取失败，已跳过。", file.name || _t("粘贴图片")),
                    { type: "danger" }
                );
                continue;
            }
            // 新增一行图库记录并写入主图字段
            const newRecord = await this.list.addNewRecord(false);
            await newRecord.update({ image_1920: base64 });
        }
    },
});

/**
 * 从剪贴板事件提取图片文件列表。
 */
function extractImageFiles(ev) {
    const files = [];
    const items = ev.clipboardData?.items;
    if (!items) {
        return files;
    }
    for (const item of items) {
        if (item.kind === "file" && item.type.startsWith("image/")) {
            const file = item.getAsFile();
            if (file) {
                files.push(file);
            }
        }
    }
    return files;
}
