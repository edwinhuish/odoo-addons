/** @odoo-module **/

import { Component, onWillDestroy, useRef, useState } from "@odoo/owl";
import { useAutofocus, useService } from "@web/core/utils/hooks";
import { getDataURLFromFile } from "@web/core/utils/urls";
import { checkFileSize } from "@web/core/utils/files";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

/**
 * 图片管理弹窗（编辑态点击「新增图片」后弹出）。
 *
 * - 上半部分：左侧大图预览（仅作预览，不提供删除按钮）+ 右侧平铺缩略图网格；
 *   删除入口只在缩略图网格——每张缩略图（含主图）右上角 × 可删除；
 *   删除主图时图库首张自动提升为新主图（提升逻辑在 gallery widget）；
 *   点击缩略图只切换本弹窗大图预览，不影响页面上展示的主图（纯弹窗内状态）
 * - 下半部分：图片 dropzone（点击选择 / 拖放 / Ctrl+V），每张上传中的图片
 *   即时显示本地缩略图 + 转圈动画（上传队列），完成后自动移除并入上方网格；
 *   Ctrl+V 粘贴上传完成后不自动关闭弹窗
 *
 * 数据同步：
 * - 弹窗不直接持有记录，通过 props 回调与 gallery widget 交互：
 *   · getItems()：取最新展示列表快照（增删后重新拉取，避免快照过期）
 *   · onDelete(type, key)：删除图库记录 / 主图（主图删除自动提升图库首张；按 key 定位防漂移）
 *   · onUploaded(info)：写入主图或追加图库，返回新增项索引
 * - 以顶层 main_components overlay 挂载（与 gallery 渲染树解耦），
 *   避免 record.update 重渲染 gallery 时弹窗被重建 / 闪烁。
 *
 * 上传实现说明：
 * - 不依赖 web.FileUploader：其内部只有一个整体 isUploading 布尔态、上传时隐藏
 *   触发区并显示一行 "Uploading..."，无法做到「每张图缩略图 + 对应上传动画」。
 *   这里自实现文件选择（隐藏 input + 点击 dropzone / 拖放 / 粘贴），读文件仍走
 *   原生 getDataURLFromFile、校验仍走原生 checkFileSize，写入仍走 onUploaded。
 */
export class ProductImageManageDialog extends Component {
    static template = "product_image.ProductImageManageDialog";
    static props = {
        acceptedFileExtensions: { type: String, optional: true },
        initialIndex: { type: Number, optional: true },
        getItems: Function, // () => [{ type, key, name, thumbUrl, bigUrl }]
        onDelete: Function, // async (type, key) => void 删除图库记录 / 主图（删主图自动提升）
        onUploaded: Function, // async (info) => number 返回新增项索引
        close: Function,
    };

    setup() {
        useAutofocus();
        this.notification = useService("notification");
        this.fileInputRef = useRef("fileInput");
        this._uploadSeq = 1;
        // 删除/上传防重标记：防止快速连点同一删除按钮造成重复操作
        this._busy = false;
        const items = this.props.getItems() || [];
        this.state = useState({
            items,
            selected: this._clamp(this.props.initialIndex || 0, items.length),
            dragging: false,
            // 上传队列：{ key, name, objectUrl }，本地缩略图预览 + 转圈动画
            queue: [],
        });
    }

    // ------------------------------------------------------------------
    // 数据访问
    // ------------------------------------------------------------------

    /** 展示列表（模板中 items 即指这里；必须提供 getter，否则模板 items.length 读到 undefined）。 */
    get items() {
        return this.state.items;
    }

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
    // 选中：仅更新弹窗内大图预览，不回传 gallery（不影响页面主图）
    // ------------------------------------------------------------------

    selectItem(i) {
        const n = this.state.items.length;
        if (i < 0 || i >= n || i === this.state.selected) {
            return;
        }
        this.state.selected = i;
    }

    // ------------------------------------------------------------------
    // 删除：缩略图网格中每张图（含主图）右上角 ×。
    // 主图删除由 gallery widget 处理（图库非空时首张自动提升为新主图），
    // 弹窗只按 key 转发并重拉列表快照。
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

    // ------------------------------------------------------------------
    // 上传（下半部分 dropzone，点击选择 / 拖放 / Ctrl+V 汇总到 processFiles）
    // ------------------------------------------------------------------

    /** dropzone 点击 → 打开系统文件选择框。 */
    openPicker() {
        this.fileInputRef.el?.click();
    }

    /** 文件选择框回调：选完立即清空 value，允许再次选择同一文件。 */
    onFileInputChange(ev) {
        const files = [...(ev.target.files || [])];
        ev.target.value = null;
        this.processFiles(files);
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
        // 粘贴上传完成后不关闭弹窗（可连续粘贴多张 / 继续管理）
    }

    /**
     * 统一上传入口：过滤图片与大小 → 先全部入队（本地缩略图 + 动画即时可见），
     * 再逐张读 base64 调 onUploaded 写入，完成后出队并入网格高亮。
     */
    async processFiles(files) {
        const images = [];
        for (const file of files) {
            if (!file.type.startsWith("image/")) {
                continue;
            }
            if (!checkFileSize(file.size, this.notification)) {
                continue;
            }
            images.push(file);
        }
        if (!images.length) {
            return;
        }
        // 先入队，立即渲染缩略图与上传动画
        const tasks = [];
        for (const file of images) {
            const entry = {
                key: `up${this._uploadSeq++}`,
                name: file.name,
                objectUrl: URL.createObjectURL(file),
            };
            this.state.queue.push(entry);
            tasks.push({ file, entry });
        }
        for (const { file, entry } of tasks) {
            let idx;
            try {
                const data = await getDataURLFromFile(file);
                const base64 = data.split(",")[1];
                if (!base64) {
                    this.notification.add(_t("图片读取失败，已跳过。"), { type: "danger" });
                } else {
                    idx = await this.props.onUploaded({
                        data: base64,
                        type: file.type,
                        name: file.name,
                    });
                }
            } catch (_e) {
                this.notification.add(_t("上传失败，请重试。"), { type: "danger" });
            } finally {
                this._dequeue(entry);
                this._reload(typeof idx === "number" ? idx : undefined);
            }
        }
    }

    /** 从上传队列移除一项并撤销其本地 object URL。 */
    _dequeue(entry) {
        const i = this.state.queue.findIndex((q) => q.key === entry.key);
        if (i < 0) {
            return;
        }
        const [removed] = this.state.queue.splice(i, 1);
        if (removed?.objectUrl) {
            URL.revokeObjectURL(removed.objectUrl);
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

    onWillDestroy() {
        // 弹窗关闭时清理仍在队列中的本地预览 URL
        for (const q of this.state.queue) {
            if (q.objectUrl) {
                URL.revokeObjectURL(q.objectUrl);
            }
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
