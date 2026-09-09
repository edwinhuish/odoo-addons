/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { imageUrl } from "@web/core/utils/urls";
import { Component, onWillUpdateProps, useRef, useState } from "@odoo/owl";
import { KanbanRecord } from "@web/views/kanban/kanban_record";

import { getProductCardPayload } from "./product_card_model";

const IMAGE_FIELD = "image_512";

/**
 * 变体按钮行（sub-component）：
 * 单独成组件以隔离内层 t-foreach（values）的 reactive 上下文——
 * Owl 19 在 ProductCardRecord 主模板里嵌套 t-foreach（rows × values）会触发
 * 重渲染循环；拆成 sub-component 后，外层只 t-foreach rows，内层 values 的
 * t-foreach 在独立组件内，reactive 依赖不再跨层耦合。
 */
class ProductCardVariantRow extends Component {
    static template = "product_card_view.VariantRow";
    static props = ["row", "record", "selectedValues"];
}

/**
 * 单张产品卡片：顶部主图轮播（左右箭头 / 滑动），主体 title / reference /
 * on hand，多变体产品底部按属性分行渲染变体按钮。
 *
 * 数据均来自 model 渲染器（fillProductCardPayload）填充的全局 Map（按 resId 索引，
 * 见 product_card_model.js），切换变体仅改前端 state，不发请求。
 *
 * 关键：payload getter 用 setup 缓存的 _resId（非 reactive），不访问
 * dataState.record / props.record——KanbanRecord 父类的 useRecordObserver effect
 * 监听 props.record 并写 dataState.record，若 getter 再访问这些 reactive state
 * 会与 effect 冲突触发 render 循环卡死。
 */
export class ProductCardRecord extends KanbanRecord {
    static template = "product_card_view.Card";

    static components = {
        ...KanbanRecord.components,
        ProductCardVariantRow,
    };

    setup() {
        super.setup();
        this.cardRef = useRef("card");
        this.cardState = useState({
            selected: {}, // {attribute_id: value_id}
            imgIndex: 0,
        });
        this._swipeSuppressUntil = 0;
        this._pointerX = null;
        // 缓存 resId 到非 reactive 实例属性
        this._resId = this.props.record?.resId;
        onWillUpdateProps((nextProps) => {
            this._resId = nextProps.record?.resId;
        });
    }

    // ---------------------------------------------------------------------
    // 数据访问
    // ---------------------------------------------------------------------

    get payload() {
        return getProductCardPayload(this._resId);
    }

    get templateId() {
        return this._resId;
    }

    get title() {
        return this.payload?.name || "";
    }

    get rows() {
        // 单变体产品没有组合可选，不渲染按钮行
        const data = this.payload;
        if (!data || data.variants.length <= 1) {
            return [];
        }
        return data.rows || [];
    }

    /** 依据已选属性找出唯一匹配变体（部分选择时优先匹配，找不到则返回模板层） */
    get currentVariant() {
        const data = this.payload;
        if (!data) {
            return null;
        }
        const selected = this.cardState.selected;
        const entries = Object.entries(selected).filter(([, valueId]) => valueId != null);
        if (!entries.length) {
            return null;
        }
        return (
            data.variants.find((variant) =>
                entries.every(([attrId, valueId]) => variant.values[attrId] === valueId)
            ) || null
        );
    }

    /** 当前展示口径：有选中变体用变体，否则用模板 */
    get referenceText() {
        const data = this.payload;
        if (!data) {
            return "";
        }
        const variant = this.currentVariant;
        return (variant?.reference || data.reference || "") || "—";
    }

    /** 在手数量文本（模板层=全部变体和；变体层=该变体在手；不可追踪显示 —） */
    get onHandText() {
        const data = this.payload;
        if (!data || !data.has_stock) {
            return "—";
        }
        const variant = this.currentVariant;
        const value = variant ? variant.on_hand : data.on_hand_total;
        if (!data.tracked) {
            return "—";
        }
        return formatQuantity(value);
    }

    /** 已选组合的展示文本（如 "Blue / Large"），仅选中变体时显示 */
    get selectionText() {
        const variant = this.currentVariant;
        if (!variant) {
            return "";
        }
        const data = this.payload;
        const names = [];
        for (const row of data.rows || []) {
            const valueId = variant.values[row.attr_id];
            const value = row.values.find((val) => val.id === valueId);
            if (value) {
                names.push(value.name);
            }
        }
        return names.length ? names.join(" / ") : "";
    }

    /**
     * 图片序列：
     * - 模板层：模板主图 + 模板共享图库；
     * - 变体层：变体主图（无则原生回退模板主图）+ 变体专属图库（两套互不叠加）。
     *
     * 缓存到 this._images，按 (variant || templateId) 作 key：每次渲染返回稳定引用，
     * 避免 Owl t-foreach 因数组引用变化反复 re-render。
     */
    get images() {
        const data = this.payload;
        if (!data) {
            return this._emptyImages || (this._emptyImages = []);
        }
        const variant = this.currentVariant;
        const key = variant ? `v${variant.id}` : `t${this.templateId}`;
        if (this._imagesKey !== key) {
            this._imagesKey = key;
            this._images = variant
                ? [
                      { model: "product.product", id: variant.id },
                      ...(data.variant_images[variant.id] || []).map((id) => ({
                          model: "product.image.gallery",
                          id,
                      })),
                  ]
                : [
                      { model: "product.template", id: this.templateId },
                      ...(data.template_images || []).map((id) => ({
                          model: "product.image.gallery",
                          id,
                      })),
                  ];
        }
        return this._images;
    }

    get imageCount() {
        return this.images.length;
    }

    get activeImageIndex() {
        const length = this.imageCount;
        return length ? Math.min(this.cardState.imgIndex, length - 1) : 0;
    }

    // ---------------------------------------------------------------------
    // 交互：图片轮播
    // ---------------------------------------------------------------------

    imageSrc(image) {
        return imageUrl(image.model, image.id, IMAGE_FIELD);
    }

    imageAlt() {
        return _t("Product image");
    }

    get referenceLabel() {
        return _t("Reference");
    }

    get onHandLabel() {
        return _t("On hand");
    }

    nextImage() {
        const length = this.imageCount;
        if (!length) {
            return;
        }
        this.cardState.imgIndex = (this.activeImageIndex + 1) % length;
    }

    previousImage() {
        const length = this.imageCount;
        if (!length) {
            return;
        }
        this.cardState.imgIndex = (this.activeImageIndex - 1 + length) % length;
    }

    arrowTitle(direction) {
        return direction === "next" ? _t("Next image") : _t("Previous image");
    }

    // 触屏 / 鼠标拖扫翻页（图片区外点击仍打开产品）
    onImagePointerDown(ev) {
        this._pointerX = ev.clientX;
    }

    onImagePointerUp(ev) {
        if (this._pointerX == null) {
            return;
        }
        const delta = ev.clientX - this._pointerX;
        this._pointerX = null;
        if (Math.abs(delta) > 35) {
            if (delta > 0) {
                this.previousImage();
            } else {
                this.nextImage();
            }
            // 滑动翻页后抑制本次抬起产生的 click，避免误打开产品
            this._swipeSuppressUntil = performance.now() + 350;
        }
    }

    // 指针离开图片区 / 被系统取消时重置起点，避免下次点击误判为滑动
    onImagePointerCancel() {
        this._pointerX = null;
    }

    // ---------------------------------------------------------------------
    // 交互：变体按钮
    // ---------------------------------------------------------------------

    isValueSelected(attrId, valueId) {
        return this.cardState.selected[attrId] === valueId;
    }

    /** 在某属性已被当前选择占用的前提下，某值是否仍有对应变体可点 */
    isValueAllowed(attrId, valueId) {
        const data = this.payload;
        if (!data) {
            return false;
        }
        const selected = this.cardState.selected;
        const otherEntries = Object.entries(selected).filter(
            ([id, val]) => val != null && Number(id) !== attrId
        );
        return data.variants.some(
            (variant) =>
                variant.values[attrId] === valueId &&
                otherEntries.every(([aId, val]) => variant.values[aId] === val)
        );
    }

    selectValue(attrId, valueId) {
        const next = { ...this.cardState.selected };
        if (next[attrId] === valueId) {
            delete next[attrId]; // 再点一次取消该行选择，回到模板层
        } else {
            next[attrId] = valueId;
        }
        this.cardState.selected = next;
        this.cardState.imgIndex = 0;
        // 变体切换可能改变卡片高度（按钮行 / selectionText 变），
        // 下一帧（re-render 后 DOM 更新）通知渲染器重算瀑布流
        requestAnimationFrame(() => {
            this.cardRef.el?.dispatchEvent(new CustomEvent("pcv-resize", { bubbles: true }));
        });
    }

    // ---------------------------------------------------------------------
    // 打开产品
    // ---------------------------------------------------------------------

    onCardClick(ev) {
        // 图片切换、变体按钮等交互区不触发打开
        if (ev.target.closest(".o_product_card__stop")) {
            return;
        }
        // 滑动翻页后的 click 抑制
        if (performance.now() < this._swipeSuppressUntil) {
            return;
        }
        this.props.openRecord(this.props.record);
    }

    // 键盘可访问性：卡片聚焦时左右键翻图，不拦截其他键
    onCardKeyDown(ev) {
        if (ev.key === "ArrowLeft") {
            ev.preventDefault();
            this.previousImage();
        } else if (ev.key === "ArrowRight") {
            ev.preventDefault();
            this.nextImage();
        }
    }
}

/** 数量展示：整数不带小数点，小数最多保留 3 位（去掉尾零） */
function formatQuantity(value) {
    if (value === null || value === undefined || Number.isNaN(value)) {
        return "—";
    }
    const num = Number(value);
    if (!Number.isFinite(num)) {
        return "—";
    }
    return String(Math.round(num * 1000) / 1000);
}
