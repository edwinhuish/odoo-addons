/** @odoo-module **/

import { Component, useRef, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { useAutofocus } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * 产品图片预览弹窗。
 *
 * 点击产品主图后弹出的全屏预览：
 * - 接收图片列表 images + 起始索引 startIndex，支持多图切换
 * - 右侧缩略图列（始终在最上层，z-index 高于主图），点击切换；键盘 ←/→ 切换
 * - 放大 / 缩小（按钮 + 鼠标滚轮）+ 重置 + 旋转
 * - 拖拽平移：任意大小均可拖拽（grab / grabbing 光标），放大后可覆盖全屏
 * - 关闭按钮（右上角，无背景栏，最顶层）/ 底部工具条：默认完全透明，鼠标移入才显示
 * - Esc / 点击背景关闭；打开期间锁定 body 滚动，避免出现滚动条
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
        // 每张图片的独立状态缓存：切换再切回时保留缩放/旋转/位移/已加载
        this.imageStates = {};

        this.zoomStep = 0.5;
        this.scrollZoomStep = 0.1;
        this.minScale = 0.5;

        this.state = useState({
            index: this.props.startIndex || 0,
            scale: 1,
            angle: 0,
            imageLoaded: false,
        });

        // 打开预览期间锁定 body 滚动（避免出现 Y 轴滚动条），关闭时恢复
        onMounted(() => {
            this._prevBodyOverflow = document.body.style.overflow;
            document.body.style.overflow = "hidden";
        });
        onWillUnmount(() => {
            document.body.style.overflow = this._prevBodyOverflow || "";
            this._cleanupDragListeners();
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

    /** 切换图片：保存当前状态，恢复目标图片之前的状态（缩放/旋转/位移/已加载）。 */
    selectImage(i) {
        const total = this.props.images?.length || 0;
        if (i < 0 || i >= total || i === this.state.index) {
            return;
        }
        // 保存当前图片状态，切回时恢复
        this._saveImageState(this.state.index);
        this.state.index = i;
        const s = this.imageStates[i] || { scale: 1, angle: 0, x: 0, y: 0, loaded: false };
        this.state.scale = s.scale;
        this.state.angle = s.angle;
        this.state.imageLoaded = s.loaded;
        this.translate.x = s.x;
        this.translate.y = s.y;
        this.translate.dx = 0;
        this.translate.dy = 0;
        this._updateZoomerStyle();
    }

    /** 保存指定图片的当前状态到缓存。 */
    _saveImageState(i) {
        this.imageStates[i] = {
            scale: this.state.scale,
            angle: this.state.angle,
            x: this.translate.x,
            y: this.translate.y,
            loaded: this.state.imageLoaded,
        };
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
        // 标记当前图片已加载，切回时立即可见（无闪烁）
        this._saveImageState(this.state.index);
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
        if (!zoomer) {
            return;
        }
        // 任意大小均可拖拽：始终应用位移（无“超出容器才允许”的门槛）；translate3d 走 GPU 合成层更顺滑
        const tx = this.translate.x + this.translate.dx;
        const ty = this.translate.y + this.translate.dy;
        zoomer.style.transform = `translate3d(${tx}px, ${ty}px, 0)`;
    }

    // ------------------------------------------------------------------
    // 拖拽平移（任意大小均可，grab / grabbing 光标）
    // ------------------------------------------------------------------

    onMousedown(ev) {
        if (this.isDragging || ev.button !== 0) {
            return;
        }
        this.isDragging = true;
        this.dragStartX = ev.clientX;
        this.dragStartY = ev.clientY;
        this.zoomerRef.el?.classList.add("is-dragging");
        // 挂到 window 上：即便鼠标移出图片/预览区域也能继续拖动并正确结束
        this._onWinMousemove = (e) => this.onMousemoveView(e);
        this._onWinMouseup = () => this.onMouseup();
        window.addEventListener("mousemove", this._onWinMousemove);
        window.addEventListener("mouseup", this._onWinMouseup);
        ev.preventDefault();
    }

    onMousemoveView(ev) {
        if (!this.isDragging) {
            return;
        }
        this.translate.dx = ev.clientX - this.dragStartX;
        this.translate.dy = ev.clientY - this.dragStartY;
        this._updateZoomerStyle();
    }

    onMouseup() {
        if (!this.isDragging) {
            return;
        }
        this.isDragging = false;
        this.translate.x += this.translate.dx;
        this.translate.y += this.translate.dy;
        this.translate.dx = 0;
        this.translate.dy = 0;
        this._updateZoomerStyle();
        this.zoomerRef.el?.classList.remove("is-dragging");
        this._cleanupDragListeners();
    }

    _cleanupDragListeners() {
        if (this._onWinMousemove) {
            window.removeEventListener("mousemove", this._onWinMousemove);
            this._onWinMousemove = null;
        }
        if (this._onWinMouseup) {
            window.removeEventListener("mouseup", this._onWinMouseup);
            this._onWinMouseup = null;
        }
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
