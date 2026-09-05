/** @odoo-module **/

import { Component, onWillDestroy, useState } from "@odoo/owl";
import { useAutofocus, useService } from "@web/core/utils/hooks";
import { getDataURLFromFile } from "@web/core/utils/urls";
import { checkFileSize } from "@web/core/utils/files";
import { FileUploader } from "@web/views/fields/file_handler";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

/**
 * 图片管理弹窗（编辑态点击「新增图片」后弹出）。
 *
 * - 上半部分：左侧大图预览（跟随选中项）+ 右侧平铺缩略图网格；
 *   缩略图右上角 × 删除（主图删除后自动提升下一张为主图，规则由 gallery widget 实现）
 * - 下半部分：图片 dropzone（点击选择 / 拖放 / Ctrl+V 粘贴）
 *
 * 数据同步：
 * - 弹窗不直接持有记录，通过 props 回调与 gallery widget 交互：
 *   · getItems()：取最新展示列表快照（增删后重新拉取，避免快照过期）
 *   · onSelect(index)：切换选中（同步 gallery 主图区选中态）
 *   · onDelete(type, key)：删除主图 / 图库图片（按 key 定位，防索引漂移）
 *   · onUploaded(info)：写入主图或追加图库，返回新增项索引
 * - 以顶层 main_components overlay 挂载（与 gallery 渲染树解耦），
 *   避免 record.update 重渲染 gallery 时弹窗被重建 / 闪烁。
 */
export class ProductImageManageDialog extends Component {
    static template = "product_image.ProductImageManageDialog";
    static components = { FileUploader };
    static props = {
        acceptedFileExtensions: { type: String, optional: true },
        initialIndex: { type: Number, optional: true },
        getItems: Function, // () => [{ type, key, name, thumbUrl, bigUrl }]
        onSelect: Function, // (index) => void
        onDelete: Function, // async (type, key) => void
        onUploaded: Function, // async (info) => number 返回新增项索引
        close: Function,
    };

    setup() {
        useAutofocus();
        this.notification = useService("notification");
        const items = this.props.getItems() || [];
        this.state = useState({
            items,
            selected: this._clamp(this.props.initialIndex || 0, items.length),
            dragging: false,
            processing: false,
        });
        // 删除/上传进行中标记：防止快速连点同一删除按钮造成重复操作
        this._busy = false;
    }

    // ------------------------------------------------------------------
    // 数据访问
    // ------------------------------------------------------------------

    get currentItem() {
        return this.state.items[this.state.selected] || null;
    }

    get currentName() {
        return this.currentItem?.name || "";
    }

    _clamp(i, len) {
        if (!len) {
            return 0;
        }
        if (i < 0) {
            return 0;
        }
        return Math.min(i, len - 1);
    }

    /** 重新拉取最新列表快照；prefer 存在时优先选中该项索引（再夹取）。 */
    _reload(prefer) {
        const items = this.props.getItems() || [];
        this.state.items = items;
        this.state.selected = this._clamp(
            typeof prefer === "number" ? prefer : this.state.selected,
            items.length
        );
    }

    // ------------------------------------------------------------------
    // 选中
    // ------------------------------------------------------------------

    selectItem(i) {
        const n = this.state.items.length;
        if (i < 0 || i >= n || i === this.state.selected) {
            return;
        }
        this.state.selected = i;
        this.props.onSelect(i);
    }

    // ------------------------------------------------------------------
    // 删除
    // ------------------------------------------------------------------

    async deleteItem(i) {
        const item = this.state.items[i];
        if (!item || this._busy) {
            return;
        }
        this._busy = true;
        try {
            await this.props.onDelete(item.type, item.key);
        } finally {
            this._busy = false;
            this._reload();
        }
    }

    deleteCurrent() {
        return this.deleteItem(this.state.selected);
    }

    // ------------------------------------------------------------------
    // 上传（下半部分 dropzone，沿用原上传弹窗交互）
    // ------------------------------------------------------------------

    async onUploaderFileUploaded(info) {
        const idx = await this.props.onUploaded(info);
        this._reload(typeof idx === "number" ? idx : undefined);
    }

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

    async onPaste(ev) {
        const files = extractImageFiles(ev);
        if (!files.length) {
            return; // 非图片，放行
        }
        ev.preventDefault();
        ev.stopPropagation();
        await this.processFiles(files);
        // 粘贴上传完成后关闭弹窗（与历史上传弹窗行为一致）
        this.close();
    }

    /** 逐张读 base64 → 调 onUploaded 写入 → 拉取最新列表。 */
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
                    this.notification.add(_t("图片读取失败，已跳过。"), { type: "danger" });
                    continue;
                }
                const idx = await this.props.onUploaded({
                    data: base64,
                    type: file.type,
                    name: file.name,
                });
                this._reload(typeof idx === "number" ? idx : undefined);
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
// 顶层 overlay 注册：把管理弹窗挂到 main_components（与原生 FileViewer 同模式），
// 与图库 widget 渲染树解耦——record.update 重渲染 gallery 时不再波及弹窗，
// 避免粘贴 / 连续上传处理过程中弹窗重渲染 / 重建导致的闪烁与“重新出现”。
// ------------------------------------------------------------------

let manageSeq = 1;

/**
 * 在 main_components 注册一个图片管理弹窗实例，返回 open/close。
 * open(props) 会先关闭已有实例再注册新的；close 从注册表移除。
 * props 不含 close（由本函数注入，移除自身）。
 */
export function useProductImageManage() {
    const compId = `product_image.manage${manageSeq++}`;
    function close() {
        registry.category("main_components").remove(compId);
    }
    function open(props) {
        close();
        registry.category("main_components").add(compId, {
            Component: ProductImageManageDialog,
            props: { ...props, close },
        });
    }
    onWillDestroy(close);
    return { open, close };
}
