/** @odoo-module **/

import { Component, useRef, useState } from "@odoo/owl";
import { useAutofocus } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * 产品图片预览弹窗。
 *
 * 点击产品主图后弹出的全屏预览：
 * - 接收图片列表 images + 起始索引 startIndex，支持多图切换
 * - 右侧缩略图列（始终在最上层，z-index 高于主图），点击切换；键盘 ←/→ 切换
 * - 放大 / 缩小（按钮 + 鼠标滚轮）+ 重置 + 旋转
 * - 拖拽平移（放大后查看局部）
 * - 顶部关闭条 / 底部工具条：暗色半透明，鼠标悬浮时才不透明，避免遮挡图片
 * - Esc / 点击背景关闭
 */
export class ProductImagePreviewDialog extends Component {
    static template = "product_image.ProductImagePreviewDialog";
    static props = {
        images: Array, // [{ url, name }]
        startIndex: { type: Number, optional: true },
        close: Function,
    };

    setup() {
        useAutofocus();
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
            index: this.props.startIndex || 0,
            scale: 1,
            angle: 0,
            imageLoaded: false,
        });
    }

    // ------------------------------------------------------------------
    // 当前图片
    // ------------------------------------------------------------------

    get hasMultiple() {
        return (this.props.images?.length || 0) > 1;
    }

    get currentImage() {
        return this.props.images?.[this.state.index] || null;
    }

    get currentUrl() {
        return this.currentImage?.url || "";
    }

    get displayName() {
        return this.currentImage?.name || _t("产品图片");
    }

    /** 切换图片：重置缩放 / 旋转 / 位移 / 加载状态。 */
    selectImage(i) {
        const total = this.props.images?.length || 0;
        if (i < 0 || i >= total || i === this.state.index) {
            return;
        }
        this.state.index = i;
        this.state.scale = 1;
        this.state.angle = 0;
        this.state.imageLoaded = false;
        this.translate.x = 0;
        this.translate.y = 0;
        this.translate.dx = 0;
        this.translate.dy = 0;
    }

    next() {
        const n = this.props.images?.length || 0;
        if (n) {
            this.selectImage((this.state.index + 1) % n);
        }
    }

    prev() {
        const n = this.props.images?.length || 0;
        if (n) {
            this.selectImage((this.state.index - 1 + n) % n);
        }
    }

    // ------------------------------------------------------------------
    // 缩放与旋转
    // ------------------------------------------------------------------

    onImageLoaded() {
        this.state.imageLoaded = true;
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
            case "ArrowRight":
                this.next();
                break;
            case "ArrowLeft":
                this.prev();
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
    // 关闭
    // ------------------------------------------------------------------

    close() {
        this.props.close();
    }
}
