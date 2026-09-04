/** @odoo-module **/

import { Component, onWillDestroy, useState } from "@odoo/owl";
import { useAutofocus, useService } from "@web/core/utils/hooks";
import { getDataURLFromFile } from "@web/core/utils/urls";
import { checkFileSize } from "@web/core/utils/files";
import { FileUploader } from "@web/views/fields/file_handler";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

/**
 * 产品图片上传弹窗。
 *
 * 点击「新增图片」按钮后弹出，提供三种上传方式：
 * - 点击拖放区域 → 唤起系统文件选择（复用原生 FileUploader）
 * - 拖放图片文件到区域 → 自动上传
 * - 弹窗打开时按 Ctrl+V / Cmd+V → 粘贴剪贴板图片上传
 *
 * 收集到的图片逐张调用 props.onUploaded(info)（info 含 base64），由父组件
 * （图库 widget）决定写入主图字段或追加图库记录。弹窗保持打开，用户传完手动关闭。
 */
export class ProductImageUploadDialog extends Component {
    static template = "product_image.ProductImageUploadDialog";
    static components = { FileUploader };
    static props = {
        acceptedFileExtensions: { type: String, optional: true },
        onUploaded: Function, // (info: { data, type, name }) => Promise，逐张调用
        close: Function,
    };

    setup() {
        useAutofocus();
        this.notification = useService("notification");
        this.state = useState({
            dragging: false, // 拖拽悬停态
            processing: false, // 正在处理文件
        });
    }

    // ------------------------------------------------------------------
    // 点击选择文件（FileUploader onUploaded）：单文件 info（已含 base64）
    // ------------------------------------------------------------------

    async onUploaderFileUploaded(info) {
        await this.props.onUploaded(info);
    }

    // ------------------------------------------------------------------
    // 拖放上传
    // ------------------------------------------------------------------

    onDragOver(ev) {
        ev.preventDefault();
        this.state.dragging = true;
    }

    onDragLeave(ev) {
        ev.preventDefault();
        this.state.dragging = false;
    }

    async onDrop(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this.state.dragging = false;
        const files = [...(ev.dataTransfer?.files || [])];
        if (files.length) {
            await this.processFiles(files);
        }
    }

    // ------------------------------------------------------------------
    // 粘贴上传（弹窗打开时焦点在弹窗上，paste 可靠触发）
    // ------------------------------------------------------------------

    async onPaste(ev) {
        const files = extractImageFiles(ev);
        if (!files.length) {
            return; // 非图片，放行
        }
        ev.preventDefault();
        ev.stopPropagation();
        await this.processFiles(files);
        // 粘贴上传完成后关闭弹窗（需求：Ctrl+V 粘贴时上传的 modal 应关闭）
        this.close();
    }

    // ------------------------------------------------------------------
    // 统一处理文件列表：逐张读 base64 → 调 onUploaded
    // ------------------------------------------------------------------

    async processFiles(files) {
        this.state.processing = true;
        try {
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
                        _t("图片“%s”读取失败，已跳过。", file.name || _t("图片")),
                        { type: "danger" }
                    );
                    continue;
                }
                await this.props.onUploaded({ data: base64, type: file.type, name: file.name });
            }
        } finally {
            this.state.processing = false;
        }
    }

    // ------------------------------------------------------------------
    // 关闭
    // ------------------------------------------------------------------

    onKeydown(ev) {
        if (ev.key === "Escape") {
            this.close();
        }
    }

    close() {
        this.props.close();
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
// 顶层 overlay 注册：把上传弹窗挂到 main_components（与原生 FileViewer 同模式），
// 与图库 widget 渲染树解耦——record.update 重渲染 gallery 时不再波及弹窗，
// 避免粘贴处理过程中弹窗重渲染/重建导致的闪烁与“重新出现”。
// ------------------------------------------------------------------

let uploadSeq = 1;

/**
 * 在 main_components 注册一个上传弹窗实例，返回 open/close。
 * open(props) 会先关闭已有实例再注册新的；close 从注册表移除。
 * props 不含 close（由本函数注入，移除自身）。
 */
export function useProductImageUpload() {
    const compId = `product_image.upload${uploadSeq++}`;
    function close() {
        registry.category("main_components").remove(compId);
    }
    function open(props) {
        close();
        registry.category("main_components").add(compId, {
            Component: ProductImageUploadDialog,
            props: { ...props, close },
        });
    }
    onWillDestroy(close);
    return { open, close };
}

