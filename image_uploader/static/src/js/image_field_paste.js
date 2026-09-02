/** @odoo-module **/

import { ImageField } from "@web/views/fields/image/image_field";
import { FileUploader } from "@web/views/fields/file_handler";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { getDataURLFromFile } from "@web/core/utils/urls";
import { checkFileSize } from "@web/core/utils/files";
import { fileTypeMagicWordMap } from "@web/views/fields/image/image_field";

/**
 * 图片粘贴 / 拖拽上传增强
 *
 * 设计要点（对照 AGENTS.md 第 5 节前端规范）：
 * - 用 @web/core/utils/patch 打补丁，不覆写整个组件
 * - 复用 Odoo 原生上传链路：FileUploader.onFileChange → getDataURLFromFile → onUploaded
 * - 复用 checkFileSize 做大小检查，超大图走原生提示（带出具体大小）
 * - 只读态不触发上传（处理器入口直接 return）
 * - 剪贴板无图片时不拦截普通文本粘贴（只处理 image/* 类型）
 * - 一次粘贴 / 拖拽可上传多张图片
 *
 * 粘贴 / 拖拽即时反馈：
 * - 粘贴开始时先把 base64 直接写入 props.record 触发缩略图即时渲染
 *   （对 base64 字段走 getUrl 的 magic-word data: URL 分支）
 * - state.isUploading 标记上传中，模板显示进度条与遮罩
 * - 后台继续执行原生 onFileUploaded 的 webp 转换 / 多尺寸附件生成
 */

const DEFAULT_ACCEPTED_IMAGE_TYPES = [
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "image/bmp",
];

/**
 * 从剪贴板事件中提取图片文件。
 * 非图片（文本 / 文件）返回空数组，调用方据此放行浏览器默认行为。
 */
function extractImageFilesFromClipboard(ev) {
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

/**
 * 从拖拽事件中提取图片文件。
 */
function extractImageFilesFromDrop(ev) {
    const files = [];
    const fileList = ev.dataTransfer?.files;
    if (!fileList) {
        return files;
    }
    for (const file of fileList) {
        if (file.type.startsWith("image/")) {
            files.push(file);
        }
    }
    return files;
}

/**
 * 把 File 对象转成 FileUploader.onFileChange 链路使用的 info 对象
 * { name, size, type, data }，复用原生大小检查与 base64 转换。
 */
async function fileToUploadInfo(file, notificationService) {
    if (!checkFileSize(file.size, notificationService)) {
        return null;
    }
    const data = await getDataURLFromFile(file);
    if (!file.size) {
        console.warn(`Error while uploading file : ${file.name}`);
        notificationService.add(_t("There was a problem while uploading your file."), {
            type: "danger",
        });
        return null;
    }
    return {
        name: file.name || `pasted-${Date.now()}.${file.type.split("/")[1] || "png"}`,
        size: file.size,
        type: file.type,
        data: data.split(",")[1],
    };
}

/**
 * 校验图片 MIME 类型是否在白名单内。
 * allowedFileExtensions 形如 "image/*" 或 "image/png,image/jpeg"。
 */
function isAcceptedImageType(file, allowedFileExtensions) {
    if (!allowedFileExtensions) {
        return DEFAULT_ACCEPTED_IMAGE_TYPES.includes(file.type);
    }
    const patterns = allowedFileExtensions
        .split(",")
        .map((p) => p.trim())
        .filter(Boolean);
    if (!patterns.length) {
        return DEFAULT_ACCEPTED_IMAGE_TYPES.includes(file.type);
    }
    if (patterns.includes("image/*")) {
        return file.type.startsWith("image/");
    }
    return patterns.some((pattern) => {
        if (pattern.endsWith("/*")) {
            const prefix = pattern.slice(0, -1);
            return file.type.startsWith(prefix);
        }
        return file.type === pattern;
    });
}

/* ---------------------------------------------------------------------------
 * 1) ImageField：挂 paste / drop 事件，即时预览 + 上传中进度条
 *
 * setup patch：在 state 上新增 isUploading / previewDataUrl，供模板渲染
 * 缩略图与进度条。
 * ------------------------------------------------------------------------- */
patch(ImageField.prototype, {

    /**
     * 拦截原生 setup，在其执行后追加 isUploading / previewDataUrl 状态。
     * 注意：patch 里直接覆写 setup，先调 super.setup() 保留原生初始化。
     */
    setup() {
        super.setup(...arguments);
        // 复用原生已存在的 state（isValid），追加上传状态
        this.state.isUploading = false;
        this.state.previewDataUrl = null;
    },

    /**
     * 粘贴：剪贴板含图片时上传，否则放行（不拦截文本粘贴）。
     * 只读态直接返回，不触发任何写操作。
     * 粘贴开始时立即写 base64 到 record 触发缩略图渲染，并标记 isUploading。
     */
    async onPaste(ev) {
        if (this.props.readonly) {
            return;
        }
        const files = extractImageFilesFromClipboard(ev);
        if (!files.length) {
            return; // 非图片，放行浏览器默认行为
        }
        ev.preventDefault();
        ev.stopPropagation(); // 防止冒泡到祖先元素重复处理
        const allowed = this.props.acceptedFileExtensions || "image/*";
        const accepted = files.filter((file) => isAcceptedImageType(file, allowed));
        if (!accepted.length) {
            this.notification.add(
                _t("粘贴的图片格式不被接受（仅允许：%(ext)s）。", { ext: allowed }),
                { type: "danger" }
            );
            return;
        }
        for (const file of accepted) {
            await this._processImageFile(file);
        }
    },

    /**
     * 拖拽进入：阻止浏览器默认打开文件，并给容器加高亮样式。
     * 用 ev.currentTarget 拿到绑事件的根元素，无需依赖组件 ref。
     */
    onDragOver(ev) {
        if (this.props.readonly) {
            return;
        }
        const hasFiles =
            ev.dataTransfer && ev.dataTransfer.types.includes("Files");
        if (!hasFiles) {
            return;
        }
        ev.preventDefault();
        if (ev.dataTransfer) {
            ev.dataTransfer.dropEffect = "copy";
        }
        ev.currentTarget?.classList?.add("o_image_uploader_drag_over");
    },

    /**
     * 拖拽离开：移除高亮样式。
     */
    onDragLeave(ev) {
        if (this.props.readonly) {
            return;
        }
        ev.currentTarget?.classList?.remove("o_image_uploader_drag_over");
    },

    /**
     * 拖拽释放：上传拖入的图片。
     * 只读态直接返回，不触发任何写操作。
     */
    async onDrop(ev) {
        if (this.props.readonly) {
            return;
        }
        ev.currentTarget?.classList?.remove("o_image_uploader_drag_over");
        const files = extractImageFilesFromDrop(ev);
        if (!files.length) {
            return;
        }
        ev.preventDefault();
        const allowed = this.props.acceptedFileExtensions || "image/*";
        const accepted = files.filter((file) => isAcceptedImageType(file, allowed));
        if (!accepted.length) {
            this.notification.add(
                _t("拖入的图片格式不被接受（仅允许：%(ext)s）。", { ext: allowed }),
                { type: "danger" }
            );
            return;
        }
        for (const file of accepted) {
            await this._processImageFile(file);
        }
    },

    /**
     * 处理单张图片文件：
     * 1) 大小检查 + base64 转换
     * 2) 立即把 base64 写入 record 字段，缩略图即时渲染（走 getUrl 的 magic-word data: URL 分支）
     * 3) 标记 isUploading，模板显示进度条遮罩
     * 4) 调用原生 onFileUploaded 完成 webp 转换 / 多尺寸附件生成
     * 5) 完成后置回 isUploading=false
     */
    async _processImageFile(file) {
        const info = await fileToUploadInfo(file, this.notification);
        if (!info) {
            return;
        }
        // 即时预览：先把 base64 写入字段触发缩略图重渲染
        this.props.record.update({ [this.props.name]: info.data });
        // 标记上传中，模板显示进度条
        this.state.isUploading = true;
        this.state.previewDataUrl = `data:${info.type};base64,${info.data}`;
        try {
            await this.onFileUploaded(info);
        } finally {
            this.state.isUploading = false;
            this.state.previewDataUrl = null;
        }
    },

    /**
     * 上传中时的缩略图 URL：优先用本地预览数据，否则走原生 getUrl。
     */
    get uploadingUrl() {
        if (this.state.isUploading && this.state.previewDataUrl) {
            return this.state.previewDataUrl;
        }
        return this.getUrl(this.props.previewImage || this.props.name);
    },
});

/* ---------------------------------------------------------------------------
 * 2) FileUploader：让根 div 拦截 paste 事件，触发其原生 onFileChange 链路
 *
 * 这样 any FileUploader 实例（包括 Many2many binary、附件上传等）都获得
 * 粘贴能力。其内部已对 state.isUploading 做了状态控制，复用即可。
 * ------------------------------------------------------------------------- */
patch(FileUploader.prototype, {
    /**
     * 粘贴事件：剪贴板含图片时走原生 onFileChange 链路，否则放行。
     */
    async onPaste(ev) {
        const files = extractImageFilesFromClipboard(ev);
        if (!files.length) {
            return; // 非图片，放行
        }
        ev.preventDefault();
        ev.stopPropagation(); // 防止冒泡到祖先元素重复处理
        for (const file of files) {
            if (this.props.checkSize && !checkFileSize(file.size, this.notification)) {
                return;
            }
            if (this.props.allowedMIMETypes && !this.props.allowedMIMETypes.includes(file.type)) {
                this.notification.add(
                    _t("Oops! '%(fileName)s' didn't upload since its format isn't allowed.", {
                        fileName: file.name,
                    }),
                    { type: "danger" }
                );
                continue;
            }
            this.state.isUploading = true;
            const data = await getDataURLFromFile(file);
            try {
                await this.props.onUploaded({
                    name: file.name || `pasted-${Date.now()}`,
                    size: file.size,
                    type: file.type,
                    data: data.split(",")[1],
                    objectUrl: null,
                });
            } finally {
                this.state.isUploading = false;
            }
        }
        if (this.props.multiUpload && this.props.onUploadComplete) {
            this.props.onUploadComplete({});
        }
    },
});
