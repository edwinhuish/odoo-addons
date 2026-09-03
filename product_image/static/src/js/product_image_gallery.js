/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { getDataURLFromFile, imageUrl } from "@web/core/utils/urls";
import { checkFileSize } from "@web/core/utils/files";
import { isBinarySize } from "@web/core/utils/binary";
import { x2ManyCommands } from "@web/core/orm_service";
import { fileTypeMagicWordMap } from "@web/views/fields/image/image_field";
import { FileUploader } from "@web/views/fields/file_handler";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { registry } from "@web/core/registry";

import { Component, useState, useRef, useEffect } from "@odoo/owl";
import { ProductImagePreviewDialog } from "./product_image_preview";

const placeholder = "/web/static/img/placeholder.png";

/**
 * 产品多图图库 widget
 *
 * 替换原生 image_1920 字段的 widget，在同一位置（头像区域）渲染多图浏览：
 * - 主图放大 2 倍显示（180x180），无上一张/下一张按钮、无序号
 * - 鼠标悬浮主图时在左侧（空间不足时下侧）显示放大的图片
 * - 点击主图弹出全屏预览弹窗（放大/缩小/复制，见 product_image_preview.js）
 * - 缩略图竖向排列于主图右侧，每张带删除按钮
 * - 缩略图总高超出主图高度时，顶部/底部出现上下滚动按钮
 * - 缩略图末端有上传占位符（编辑态），点击即新增图片
 * - 头像区域 Ctrl+V 粘贴剪贴板图片即新增图库记录
 * - 浏览切换为纯前端状态，不写产品主图；上传/删除走 One2many record 操作
 * - 产品主图 image_1920 由后端 create/write 同步首图，列表/看板/报价单沿用
 *
 * 数据来源：product.template.image_gallery_ids（One2many → product.image.gallery）
 * image.gallery 继承 image.mixin，image_1920/1024/128 自动生成多尺寸。
 */
export class ProductImageGallery extends Component {
    static template = "product_image.ProductImageGallery";
    static components = { FileUploader, ProductImagePreviewDialog };
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
            hoverZoom: false,
            hoverSide: "left", // "left" | "below" | "right"
            hoverLeft: 0,
            hoverTop: 0,
            previewOpen: false,
            // 缩略图滚动状态
            thumbCanScrollUp: false,
            thumbCanScrollDown: false,
        });
        // 主图容器与缩略图滚动容器引用，用于位置/溢出计算
        this.mainRef = useRef("main");
        this.thumbScrollRef = useRef("thumbScroll");

        // 记录 / 容器尺寸变化后重算缩略图溢出与 currentIndex 边界
        useEffect(() => {
            this._updateThumbOverflow();
            this._clampIndex();
        }, () => [this.galleryRecords.length, this.state.currentIndex]);
    }

    // ------------------------------------------------------------------
    // 图库数据访问
    // ------------------------------------------------------------------

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
        return [...list.records].sort((a, b) => {
            const sa = a.data.sequence ?? 10;
            const sb = b.data.sequence ?? 10;
            if (sa !== sb) return sa - sb;
            return (a.resId || a.id) - (b.resId || b.id);
        });
    }

    get currentRecord() {
        const records = this.galleryRecords;
        if (!records.length) {
            return null;
        }
        const idx = Math.min(this.state.currentIndex, records.length - 1);
        return records[idx] || null;
    }

    get hasImages() {
        return this.galleryRecords.length > 0;
    }

    /**
     * 是否有可显示的主图：图库有记录，或原生 image_1920 字段有值（历史产品）。
     * 历史产品在装模块前就有 image_1920 主图但无图库记录，需回退显示字段值，
     * 否则原主图会被 widget「吞掉」显示占位。
     */
    get hasMainImage() {
        return this.hasImages || Boolean(this.props.record.data[this.props.name]);
    }

    get totalCount() {
        return this.galleryRecords.length;
    }

    // ------------------------------------------------------------------
    // 图片 URL（复用原生 ImageField 的 URL 生成逻辑）
    // ------------------------------------------------------------------

    /**
     * 生成图片 URL。
     *
     * 对未保存的新记录或相关尺寸字段（image_128/1024）为空时，
     * 回退到 image_1920 源数据（base64 data URL），保证刚上传的图片
     * 在保存前也能预览。已保存记录优先用请求字段以节省带宽。
     *
     * record 既可以是图库记录（product.image.gallery），也可以是主记录
     * （product.template）——后者用于图库为空时回退显示原生 image_1920 字段值。
     */
    getUrl(record, fieldName) {
        if (!record) {
            return placeholder;
        }
        let data = record.data[fieldName];
        if (!data && fieldName !== "image_1920") {
            data = record.data.image_1920;
        }
        if (!data) {
            return placeholder;
        }
        if (!record.isNew && isBinarySize(data) && record.resId) {
            const urlField =
                fieldName === "image_1920" || !record.data[fieldName] ? "image_1920" : fieldName;
            return imageUrl(record.resModel || "product.image.gallery", record.resId, urlField, {
                unique: record.data.write_date,
            });
        }
        const magic = fileTypeMagicWordMap[data[0]] || "png";
        return `data:image/${magic};base64,${data}`;
    }

    /**
     * 主图：图库有记录时取首图 image_1024（180px 显示足够，比 image_128 清晰）；
     * 图库为空时回退到原生 image_1920 字段值（历史产品主图不丢失）。
     */
    get mainImageUrl() {
        if (this.hasImages) {
            return this.getUrl(this.currentRecord, "image_1024");
        }
        return this.getUrl(this.props.record, this.props.name);
    }

    /**
     * 悬浮放大 / 预览弹窗：图库有记录时取首图 image_1920 源数据；
     * 图库为空时回退到原生 image_1920 字段值。
     */
    get fullImageUrl() {
        if (this.hasImages) {
            return this.getUrl(this.currentRecord, "image_1920");
        }
        return this.getUrl(this.props.record, this.props.name);
    }

    get currentName() {
        return this.currentRecord?.data.name || "";
    }

    // ------------------------------------------------------------------
    // 选择缩略图（纯前端状态，不写库）
    // ------------------------------------------------------------------

    onSelectByIndex(index) {
        if (index < 0 || index >= this.galleryRecords.length) {
            return;
        }
        this.state.currentIndex = index;
    }

    _clampIndex() {
        const total = this.galleryRecords.length;
        if (total === 0) {
            this.state.currentIndex = 0;
        } else if (this.state.currentIndex >= total) {
            this.state.currentIndex = total - 1;
        } else if (this.state.currentIndex < 0) {
            this.state.currentIndex = 0;
        }
    }

    // ------------------------------------------------------------------
    // 悬浮放大
    // ------------------------------------------------------------------

    onHoverEnter() {
        if (!this.hasMainImage) {
            return;
        }
        // 计算放置位置与像素坐标（position:fixed 需相对视口的 top/left）。
        // 优先左侧；左侧空间不足放下方；下方又超出视口底部且右侧有空间则放右侧。
        const el = this.mainRef.el;
        if (!el) {
            this.state.hoverZoom = true;
            return;
        }
        const rect = el.getBoundingClientRect();
        const panelW = 320;
        const panelH = 320;
        const gap = 8;
        if (rect.left >= panelW + gap) {
            this.state.hoverSide = "left";
            this.state.hoverLeft = Math.round(rect.left - panelW - gap);
            this.state.hoverTop = Math.round(rect.top);
        } else if (rect.bottom + panelH + gap <= window.innerHeight) {
            this.state.hoverSide = "below";
            this.state.hoverLeft = Math.round(rect.left);
            this.state.hoverTop = Math.round(rect.bottom + gap);
        } else if (rect.right + panelW + gap <= window.innerWidth) {
            this.state.hoverSide = "right";
            this.state.hoverLeft = Math.round(rect.right + gap);
            this.state.hoverTop = Math.round(rect.top);
        } else {
            // 兜底：下方
            this.state.hoverSide = "below";
            this.state.hoverLeft = Math.round(rect.left);
            this.state.hoverTop = Math.round(rect.bottom + gap);
        }
        this.state.hoverZoom = true;
    }

    onHoverLeave() {
        this.state.hoverZoom = false;
    }

    /** 悬浮放大浮层的内联样式（position:fixed + 视口坐标）。 */
    get hoverStyle() {
        return (
            `position: fixed; left: ${this.state.hoverLeft}px; top: ${this.state.hoverTop}px; ` +
            `max-width: 320px; max-height: 320px; z-index: 1080; pointer-events: none;`
        );
    }

    // ------------------------------------------------------------------
    // 点击主图 → 弹出预览
    // ------------------------------------------------------------------

    onMainClick() {
        if (!this.hasMainImage) {
            return;
        }
        this.state.hoverZoom = false;
        this.state.previewOpen = true;
    }

    closePreview() {
        this.state.previewOpen = false;
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
        const newRecord = await galleryList.addNewRecord(false);
        await newRecord.update({ image_1920: info.data });
        this.state.currentIndex = this.galleryRecords.length - 1;
        this._clampIndex();
    }

    // ------------------------------------------------------------------
    // 删除：移除指定缩略图对应的图库记录（不限于当前主图）
    // ------------------------------------------------------------------

    async onThumbRemove(index, ev) {
        // 阻止冒泡触发缩略图选中
        ev?.stopPropagation?.();
        ev?.preventDefault?.();
        if (this.props.readonly) {
            return;
        }
        const records = this.galleryRecords;
        const rec = records[index];
        if (!rec) {
            return;
        }
        const list = this.galleryList;
        if (!list) {
            return;
        }
        // 通过主 record 的 update + x2ManyCommands 删除图库记录，
        // 由 Odoo 内部 _preprocessX2manyChanges 统一处理（已保存走 DELETE/orm.unlink，
        // 新记录走 UNLINK/从 records 移除）。
        const command = rec.isNew
            ? x2ManyCommands.unlink(rec.id) // (3, id) 移除关联
            : x2ManyCommands.delete(rec.resId); // (2, id) 删除已保存记录
        await this.props.record.update({
            image_gallery_ids: [command],
        });
        // 删除后维持可视位置：若删除的是当前或之前的索引，索引可能需要前移
        this._clampIndex();
        // 等下一帧 DOM 更新后重算溢出
        requestAnimationFrame(() => this._updateThumbOverflow());
    }

    // ------------------------------------------------------------------
    // 缩略图滚动：上下按钮
    // ------------------------------------------------------------------

    get thumbCanScrollUp() {
        return this.state.thumbCanScrollUp;
    }

    get thumbCanScrollDown() {
        return this.state.thumbCanScrollDown;
    }

    onThumbScrollUp() {
        const el = this.thumbScrollRef.el;
        if (!el) {
            return;
        }
        el.scrollBy({ top: -el.clientHeight * 0.8, behavior: "smooth" });
    }

    onThumbScrollDown() {
        const el = this.thumbScrollRef.el;
        if (!el) {
            return;
        }
        el.scrollBy({ top: el.clientHeight * 0.8, behavior: "smooth" });
    }

    onThumbScroll() {
        this._updateThumbOverflow();
    }

    /** 计算缩略图是否超出容器，决定上下按钮显隐。 */
    _updateThumbOverflow() {
        const el = this.thumbScrollRef.el;
        if (!el) {
            this.state.thumbCanScrollUp = false;
            this.state.thumbCanScrollDown = false;
            return;
        }
        this.state.thumbCanScrollUp = el.scrollTop > 1;
        this.state.thumbCanScrollDown =
            el.scrollTop + el.clientHeight < el.scrollHeight - 1;
    }

    // ------------------------------------------------------------------
    // 粘贴：剪贴板图片逐张新增图库记录
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
// 注册为字段 widget（registry key 保持 product_image_gallery，视图无需改动）
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
