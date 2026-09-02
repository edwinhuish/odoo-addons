/** @odoo-module **/

import { ImageField } from "@web/views/fields/image/image_field";
import { FileUploader } from "@web/views/fields/file_handler";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { getDataURLFromFile } from "@web/core/utils/urls";
import { checkFileSize } from "@web/core/utils/files";
import { isBinarySize, fileTypeMagicWordMap } from "@web/views/fields/image/image_field";
import { imageUrl } from "@web/core/utils/urls";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { Component, useState } from "@odoo/owl";

const placeholder = "/web/static/img/placeholder.png";

/**
 * 产品多图图库 widget
 *
 * 替换原生 image_1920 字段的 widget，在同一位置（头像区域）渲染多图浏览：
 * - 当前图片 + 左右切换按钮 + 计数指示（如 2/5）+ 缩略图条
 * - 上传即新增一条图库记录（image_gallery_ids），并设为当前图
 * - 删除当前图库记录，自动切换到相邻图
 * - 粘贴剪贴板图片即新增图库记录（联动 T-003 的粘贴体验）
 * - 浏览切换为纯前端状态，不写产品主图；上传/删除走 One2many record 操作
 * - 产品主图 image_1920 由后端 create/write 同步首图，列表/看板/报价单沿用
 *
 * 数据来源：product.template.image_gallery_ids（One2many → product.image.gallery）
 * image.gallery 继承 image.mixin，image_1920/128 自动生成多尺寸。
 */
export class ProductImageGallery extends Component {
    static template = "product_multi_image.ProductImageGallery";
    static components = { FileUploader };
    static props = {
        ...standardFieldProps,
        acceptedFileExtensions: { type: String, optional: true },
        previewImage: { type: String, optional: true },
        convertToWebp: { type: Boolean, optional: true },
        enableZoom: { type: Boolean, optional: true },
        imgClass: { type: String, optional: true },
        zoomDelay: { type: Number, optional: true },
        alt: { type: String, optional: true },
        width: { type: Number, optional: true },
        height: { type: Number, optional: true },
        reload: { type: Boolean, optional: true },
    };
    static defaultProps = {
        acceptedFileExtensions: "image/*",
        alt: _t("产品图片"),
        imgClass: "",
        reload: true,
    };

    setup() {
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.state = useState({
            currentIndex: 0,
            isValid: true,
            isUploading: false,
        });
    }

    // ------------------------------------------------------------------
    // 图库数据访问
    // ------------------------------------------------------------------

    /**
     * 图库 One2many 记录列表（DynamicRecordList）。
     */
    get galleryList() {
        return this.props.record.data.image_gallery_ids;
    }

    /**
     * 当前图库所有图片记录（按 sequence/id 升序，与后端 _order 一致）。
     */
    get galleryRecords() {
        const list = this.galleryList;
        if (!list || !list.records) {
            return [];
        }
        // 复制后排序，避免改原数组
        return [...list.records].sort((a, b) => {
            const sa = a.data.sequence ?? 10;
            const sb = b.data.sequence ?? 10;
            if (sa !== sb) return sa - sb;
            return (a.resId || a.id) - (b.resId || b.id);
        });
    }

    /**
     * 当前选中的图库记录。
     */
    get currentRecord() {
        const records = this.galleryRecords;
        if (!records.length) {
            return null;
        }
        const idx = Math.min(this.state.currentIndex, records.length - 1);
        return records[idx] || null;
    }

    /**
     * 当前图片的 base64 数据（来自当前图库记录的 image_1920）。
     */
    get currentImageData() {
        const rec = this.currentRecord;
        return rec ? rec.data.image_1920 : false;
    }

    // ------------------------------------------------------------------
    // 图片 URL（复用原生 ImageField 的 URL 生成逻辑）
    // ------------------------------------------------------------------

    get sizeStyle() {
        let style = "";
        if (this.props.width) {
            style += `max-width: ${this.props.width}px;`;
            if (!this.props.height) {
                style += "height: auto; max-height: 100%;";
            }
        }
        if (this.props.height) {
            style += `max-height: ${this.props.height}px;`;
            if (!this.props.width) {
                style += "width: auto; max-width: 100%;";
            }
        }
        return style;
    }

    get imgClass() {
        return ["img", "img-fluid"].concat((this.props.imgClass || "").split(" ")).join(" ");
    }

    /**
     * 生成图片 URL。
     *
     * 对未保存的新记录或 image_128（related 字段，保存后才生成）为空时，
     * 回退到 image_1920 源数据（base64 data URL），保证用户刚上传的图片
     * 在保存前也能预览。已保存记录优先用 image_128 节省带宽。
     */
    getUrl(record, fieldName) {
        if (!record) {
            return placeholder;
        }
        let data = record.data[fieldName];
        // 优先请求的字段；为空时回退到 image_1920 源数据
        if (!data && fieldName !== "image_1920") {
            data = record.data.image_1920;
        }
        if (!data) {
            return placeholder;
        }
        // 已保存记录且字段是数据库存储的 binary size 形式 → 走 imageUrl（带缓存 key）
        if (!record.isNew && isBinarySize(data) && record.resId) {
            const urlField = (fieldName === "image_1920" || !record.data[fieldName]) ? "image_1920" : fieldName;
            return imageUrl("product.image.gallery", record.resId, urlField, {
                unique: record.data.write_date,
            });
        }
        // 新记录或 base64 字符串 → data URL
        const magic = fileTypeMagicWordMap[data[0]] || "png";
        return `data:image/${magic};base64,${data}`;
    }

    get currentImageUrl() {
        const rec = this.currentRecord;
        // 优先 image_128（已保存记录的缩略，节省带宽），回退 image_1920 源数据
        return this.getUrl(rec, "image_128");
    }

    get hasMultiple() {
        return this.galleryRecords.length > 1;
    }

    get totalCount() {
        return this.galleryRecords.length;
    }

    get currentPosition() {
        return this.galleryRecords.length ? this.state.currentIndex + 1 : 0;
    }

    // ------------------------------------------------------------------
    // 导航：上一张 / 下一张（纯前端状态，不写库）
    // ------------------------------------------------------------------

    onPrev() {
        if (!this.hasMultiple) {
            return;
        }
        const total = this.galleryRecords.length;
        this.state.currentIndex = (this.state.currentIndex - 1 + total) % total;
    }

    onNext() {
        if (!this.hasMultiple) {
            return;
        }
        const total = this.galleryRecords.length;
        this.state.currentIndex = (this.state.currentIndex + 1) % total;
    }

    onSelectByIndex(index) {
        if (index < 0 || index >= this.galleryRecords.length) {
            return;
        }
        this.state.currentIndex = index;
    }

    /**
     * 图库记录变化后校正 currentIndex（避免越界）。
     * 由 onUploaded / onRemove 调用。
     */
    _clampIndex() {
        const total = this.galleryRecords.length;
        if (total === 0) {
            this.state.currentIndex = 0;
        } else if (this.state.currentIndex >= total) {
            this.state.currentIndex = total - 1;
        }
    }

    // ------------------------------------------------------------------
    // 上传：新增一条图库记录，并设为当前图
    // ------------------------------------------------------------------

    async onFileUploaded(info) {
        const galleryList = this.galleryList;
        if (!galleryList) {
            this.notification.add(_t("图库不可用，无法新增图片。"), { type: "danger" });
            return;
        }
        // 新增一行图库记录
        const newRecord = await galleryList.addNewRecord(false);
        await newRecord.update({ image_1920: info.data });
        // 选中新图
        this.state.currentIndex = this.galleryRecords.length - 1;
        this._clampIndex();
    }

    // ------------------------------------------------------------------
    // 删除：移除当前图库记录，切换到相邻图
    // ------------------------------------------------------------------

    async onFileRemove() {
        const rec = this.currentRecord;
        if (!rec) {
            return;
        }
        const list = this.galleryList;
        if (rec.isNew) {
            list.removeRecord(rec);
        } else {
            await rec.delete();
        }
        this._clampIndex();
    }

    // ------------------------------------------------------------------
    // 粘贴：剪贴板图片逐张新增图库记录（联动 T-003 体验）
    // ------------------------------------------------------------------

    async onPaste(ev) {
        if (this.props.readonly) {
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
            if (!checkFileSize(file.size, this.notification)) {
                continue;
            }
            const data = await getDataURLFromFile(file);
            const base64 = data.split(",")[1];
            if (!base64) {
                this.notification.add(
                    _t("图片“%s”读取失败，已跳过。", file.name || _t("粘贴图片")),
                    { type: "danger" }
                );
                continue;
            }
            await this.onFileUploaded({ data: base64, type: file.type, name: file.name });
        }
    }
}

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

// ------------------------------------------------------------------
// 注册为字段 widget，复用原生 image 字段的 options 解析
// ------------------------------------------------------------------

export const productImageGalleryField = {
    component: ProductImageGallery,
    displayName: _t("产品多图"),
    supportedAttributes: [
        { label: _t("Alternative text"), name: "alt", type: "string" },
    ],
    supportedOptions: [
        { label: _t("Reload"), name: "reload", type: "boolean", default: true },
        { label: _t("Enable zoom"), name: "zoom", type: "boolean" },
        { label: _t("Convert to webp"), name: "convert_to_webp", type: "boolean" },
        { label: _t("Zoom delay"), name: "zoom_delay", type: "number" },
        { label: _t("Accepted file extensions"), name: "accepted_file_extensions", type: "string" },
        {
            label: _t("Size"),
            name: "size",
            type: "selection",
            choices: [
                { label: _t("Small"), value: "[0,90]" },
                { label: _t("Medium"), value: "[0,180]" },
                { label: _t("Large"), value: "[0,270]" },
            ],
        },
        { label: _t("Preview image"), name: "preview_image", type: "field", availableTypes: ["binary"] },
    ],
    supportedTypes: ["binary"],
    fieldDependencies: [
        { name: "write_date", type: "datetime" },
        { name: "image_gallery_ids", type: "one2many" },
    ],
    isEmpty: () => false,
    extractProps: ({ attrs, options }) => ({
        alt: attrs.alt,
        enableZoom: options.zoom,
        convertToWebp: options.convert_to_webp,
        imgClass: options.img_class || "",
        zoomDelay: options.zoom_delay,
        previewImage: options.preview_image,
        acceptedFileExtensions: options.accepted_file_extensions,
        width: options.size && Boolean(options.size[0]) ? options.size[0] : undefined,
        height: options.size && Boolean(options.size[1]) ? options.size[1] : undefined,
        reload: "reload" in options ? Boolean(options.reload) : true,
    }),
};

registry.category("fields").add("product_image_gallery", productImageGalleryField);
