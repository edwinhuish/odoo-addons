/** @odoo-module **/

import { Component, useRef, useState } from "@odoo/owl";
import { useAutofocus, useService } from "@web/core/utils/hooks";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";

/**
 * 产品图片预览弹窗。
 *
 * 点击产品主图后弹出的全屏预览：
 * - 放大 / 缩小（按钮 + 鼠标滚轮）+ 重置
 * - 复制图片到系统剪贴板（navigator.clipboard.write + ClipboardItem）
 * - 拖拽平移（放大后查看局部）
 * - Esc / 点击背景关闭
 *
 * 不复用原生 web.FileViewer：原生无「复制」功能，且全局 patch FileViewer 会影响
 * 所有附件预览。本弹窗仅服务于产品图片，行为收敛在模块内部。
 */
export class ProductImagePreviewDialog extends Component {
    static template = "product_image.ProductImagePreviewDialog";
    static props = {
        url: String,
        name: { type: String, optional: true },
        close: Function,
    };

    setup() {
        useAutofocus();
        this.notification = useService("notification");
        this.ui = useService("ui");
        this.imageRef = useRef("image");
        this.zoomerRef = useRef("zoomer");

        this.isDragging = false;
        this.dragStartX = 0;
        this.dragStartY = 0;
        // 翻译位移：x/y 为提交后的基准，dx/dy 为拖动中的增量
        this.translate = { dx: 0, dy: 0, x: 0, y: 0 };

        this.zoomStep = 0.5;
        this.scrollZoomStep = 0.1;
        this.minScale = 0.5;

        this.state = useState({
            scale: 1,
            angle: 0,
            isCopying: false,
            copyState: "", // "" | "ok" | "fail"
            imageLoaded: false,
        });
    }

    // ------------------------------------------------------------------
    // 缩放与旋转
    // ------------------------------------------------------------------

    onImageLoaded() {
        this.state.imageLoaded = true;
    }

    get displayName() {
        return this.props.name || _t("产品图片");
    }

    /** 复制按钮标题（按当前状态切换）。 */
    get copyTitle() {
        if (this.state.copyState === "ok") {
            return _t("已复制，可再点一次复制");
        }
        return _t("复制到剪贴板");
    }

    /** 复制按钮文字（按当前状态切换）。 */
    get copyLabel() {
        if (this.state.isCopying) {
            return _t("复制中");
        }
        if (this.state.copyState === "ok") {
            return _t("已复制");
        }
        if (this.state.copyState === "fail") {
            return _t("复制失败");
        }
        return _t("复制");
    }

    get copyIconClass() {
        if (this.state.isCopying) {
            return "fa fa-spinner fa-spin fa-fw";
        }
        if (this.state.copyState === "ok") {
            return "fa fa-check fa-fw text-success";
        }
        if (this.state.copyState === "fail") {
            return "fa fa-times fa-fw text-danger";
        }
        return "fa fa-clone fa-fw";
    }

    get imageStyle() {
        // 旋转 90/270 时宽高互换，避免被容器裁切
        let style =
            "transform: " +
            `scale3d(${this.state.scale}, ${this.state.scale}, 1) ` +
            `rotate(${this.state.angle}deg);`;
        if (this.state.angle % 180 !== 0) {
            style += `max-height: ${window.innerWidth}px; max-width: ${window.innerHeight}px;`;
        } else {
            style += "max-height: 100%; max-width: 100%;";
        }
        style +=
            "background: repeating-conic-gradient(#ccc 0deg 90deg, #fff 90deg 180deg) 50% / 20px 20px;";
        // opacity 必须放进 imageStyle，避免 t-att-style 重渲染时被重置回 0 导致图片消失
        style += `opacity: ${this.state.imageLoaded ? 1 : 0};`;
        return style;
    }

    resetZoom() {
        this.state.scale = 1;
        this.translate.x = 0;
        this.translate.y = 0;
        this.translate.dx = 0;
        this.translate.dy = 0;
        this._updateZoomerStyle();
    }

    zoomIn({ scroll = false } = {}) {
        this.state.scale = this.state.scale + (scroll ? this.scrollZoomStep : this.zoomStep);
        this._updateZoomerStyle();
    }

    zoomOut({ scroll = false } = {}) {
        if (this.state.scale === this.minScale) {
            return;
        }
        const next = this.state.scale - (scroll ? this.scrollZoomStep : this.zoomStep);
        this.state.scale = Math.max(this.minScale, next);
        this._updateZoomerStyle();
    }

    rotate() {
        this.state.angle += 90;
    }

    _updateZoomerStyle() {
        const zoomer = this.zoomerRef.el;
        const image = this.imageRef.el;
        if (!zoomer || !image) {
            return;
        }
        // 放大后图片超出容器时才允许横向 / 纵向位移，否则吸附居中
        const tx =
            image.offsetWidth * this.state.scale > zoomer.offsetWidth
                ? this.translate.x + this.translate.dx
                : 0;
        const ty =
            image.offsetHeight * this.state.scale > zoomer.offsetHeight
                ? this.translate.y + this.translate.dy
                : 0;
        if (tx === 0) {
            this.translate.x = 0;
        }
        if (ty === 0) {
            this.translate.y = 0;
        }
        zoomer.style.transform = `translate(${tx}px, ${ty}px)`;
    }

    // ------------------------------------------------------------------
    // 拖拽平移
    // ------------------------------------------------------------------

    onMousedownImage(ev) {
        if (this.isDragging || ev.button !== 0) {
            return;
        }
        this.isDragging = true;
        this.dragStartX = ev.clientX;
        this.dragStartY = ev.clientY;
    }

    onMousemoveView(ev) {
        if (!this.isDragging) {
            return;
        }
        this.translate.dx = ev.clientX - this.dragStartX;
        this.translate.dy = ev.clientY - this.dragStartY;
        this._updateZoomerStyle();
    }

    onMouseupImage() {
        if (!this.isDragging) {
            return;
        }
        this.isDragging = false;
        this.translate.x += this.translate.dx;
        this.translate.y += this.translate.dy;
        this.translate.dx = 0;
        this.translate.dy = 0;
        this._updateZoomerStyle();
    }

    onWheelImage(ev) {
        ev.preventDefault();
        if (ev.deltaY > 0) {
            this.zoomOut({ scroll: true });
        } else {
            this.zoomIn({ scroll: true });
        }
    }

    // ------------------------------------------------------------------
    // 键盘
    // ------------------------------------------------------------------

    onKeydown(ev) {
        switch (ev.key) {
            case "Escape":
            case "q":
                this.close();
                break;
            case "+":
                this.zoomIn();
                break;
            case "-":
                this.zoomOut();
                break;
            case "0":
                this.resetZoom();
                break;
            case "r":
                this.rotate();
                break;
        }
    }

    // ------------------------------------------------------------------
    // 复制图片到剪贴板
    // ------------------------------------------------------------------

    /**
     * 把当前预览图片复制到系统剪贴板。
     *
     * data: URL 与同源 web/image URL 都能通过 fetch → blob 统一处理。
     * 跨域附件 URL 不可复制时给出中文提示，回退建议用户用「下载」。
     */
    async onCopy() {
        if (this.state.isCopying) {
            return;
        }
        this.state.isCopying = true;
        this.state.copyState = "";
        try {
            const response = await fetch(this.props.url, { credentials: "same-origin" });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const blob = await response.blob();
            if (!blob || !blob.size) {
                throw new Error("empty blob");
            }
            const ClipboardItemCtor = browser.ClipboardItem || window.ClipboardItem;
            if (!ClipboardItemCtor || !browser.navigator?.clipboard?.write) {
                throw new Error("unsupported");
            }
            await browser.navigator.clipboard.write([
                new ClipboardItemCtor({ [blob.type]: blob }),
            ]);
            this.state.copyState = "ok";
            this.notification.add(_t("图片已复制到剪贴板，可在其他位置 Ctrl+V 粘贴。"), {
                type: "success",
            });
        } catch (err) {
            this.state.copyState = "fail";
            this.notification.add(
                _t("复制图片失败，浏览器可能不支持该功能。可改用「下载」获取图片。"),
                { type: "danger" }
            );
            browser.console?.warn?.(err);
        } finally {
            this.state.isCopying = false;
        }
    }

    // ------------------------------------------------------------------
    // 关闭
    // ------------------------------------------------------------------

    close() {
        this.props.close();
    }
}
