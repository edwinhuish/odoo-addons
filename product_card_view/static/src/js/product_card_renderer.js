/** @odoo-module **/

import {
    onMounted,
    onPatched,
    onWillStart,
    onWillUnmount,
    onWillUpdateProps,
    useEffect,
    useRef,
} from "@odoo/owl";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";

import {
    cardRecordIdsKey,
    collectCardRecordIds,
    fillProductCardPayload,
} from "./product_card_model";
import { ProductCardRecord } from "./product_card_record";

// 瀑布流参数
const CARD_MIN_WIDTH = 240; // 卡片最小宽（15rem）
const CARD_MAX_WIDTH = 360; // 卡片最大宽（22.5rem）
const GAP = 12; // 卡片间距（0.75rem）
const PAD = 12; // 容器内边距（0.75rem）

/**
 * 渲染器：结构沿用 KanbanRenderer，仅替换记录卡片组件并加自定义根类。
 *
 * 卡片 payload 的填充（详见 product_card_model.js 的 fillProductCardPayload）：
 * - 渲染前：onWillStart / onWillUpdateProps（Owl 会 await，渲染时数据已就位）；
 * - 渲染后：useEffect 监听本页 id —— 筛选 / 分组 / 翻页 / reload 常常只改 list
 *   内部数据，本组件由 Reactive 直接重渲染、**不走 updateProps**，此时只有
 *   useEffect 能感知到；payload 在非 reactive Map 里，取到后必须显式 render 一次。
 *
 * 布局：
 * - 未分组：JS 瀑布流（卡片 position absolute，按内容高度放最矮列，列高均衡；
 *   响应式列数；patch / resize / 图片 load / 变体切换后重算）；
 * - 分组：卡片按列内正常流布局（宽度上限与间距由 SCSS 控制），只清掉上一次
 *   未分组瀑布流写下的 inline 定位，避免残留导致卡片错位 / 过宽 / 无间距。
 *
 * 用 rootRef（KanbanRenderer 模板根 div 的 t-ref="root"）取容器，
 * 不用 this.el（在 onMounted 的 rAF 里可能为 null）。
 */
export class ProductCardRenderer extends KanbanRenderer {
    static template = "product_card_view.ProductCardRenderer";

    static components = {
        ...KanbanRenderer.components,
        KanbanRecord: ProductCardRecord,
    };

    setup() {
        super.setup();
        this.rootRef = useRef("root");
        this._payloadKey = null;
        this._onResize = this._debounce(() => this._layoutWaterfall(), 150);
        this._onImgLoad = () => this._layoutWaterfall();
        this._onPcvResize = () => requestAnimationFrame(() => this._layoutWaterfall());

        // 1) 渲染前填充：首屏与 props 更新
        onWillStart(() => this._ensurePayload(this.props.list));
        onWillUpdateProps((nextProps) => this._ensurePayload(nextProps.list));

        // 2) 渲染后兜底：useEffect 在 mount 与每次 patch 后比对本页 id，
        //    因此「只改 list 内部数据、不走 updateProps」的刷新也能补上 payload。
        //    注意：effect 回调不要返回 promise（Owl 会把它当 cleanup 调用后报错），
        //    异步补数在 _ensurePayload 内部自己 render。
        useEffect(() => {
            this._ensurePayload(this.props.list, true);
        }, () => [this._recordIdsKey()]);

        // 3) 布局：DOM patch 完成后（offsetHeight 才准）重算
        onPatched(() => this._layoutWaterfall());

        onMounted(() => {
            window.addEventListener("resize", this._onResize);
            // 卡片变体切换后高度可能变，通过 model.bus 通知重算
            this.props.list?.model?.bus?.addEventListener("pcv-resize", this._onPcvResize);
            // 容器宽度变化（侧栏收放、分组列数变化）时重算
            if (typeof ResizeObserver !== "undefined" && this.rootRef.el) {
                this._resizeObserver = new ResizeObserver(this._onResize);
                this._resizeObserver.observe(this.rootRef.el);
            }
            this._layoutWaterfall();
        });
        onWillUnmount(() => {
            window.removeEventListener("resize", this._onResize);
            this.props.list?.model?.bus?.removeEventListener("pcv-resize", this._onPcvResize);
            this._resizeObserver?.disconnect();
        });
    }

    _debounce(fn, wait) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), wait);
        };
    }

    // ---------------------------------------------------------------------
    // 数据：卡片 payload
    // ---------------------------------------------------------------------

    /** 本页 id 组成的 key（读 list.records / list.groups，供 useEffect 逐次比对） */
    _recordIdsKey() {
        return cardRecordIdsKey(collectCardRecordIds(this.props.list));
    }

    /**
     * 保证本页卡片的 payload 已就绪。
     *
     * payload 存在非 reactive 的全局 Map，取到后不会自动触发渲染：
     * - 渲染前调用（onWillStart / onWillUpdateProps）：Owl 会 await，随后那次渲染
     *   自然带上数据，不需要再 render；
     * - 渲染后调用（useEffect）：必须显式 render(true)，否则卡片一直是空白。
     *
     * @param {Object} list 当前 list（未分组是记录列表，分组是分组列表）
     * @param {boolean} [forceRender=false] 取数后是否强制重渲染
     */
    async _ensurePayload(list, forceRender = false) {
        const ids = collectCardRecordIds(list);
        const key = cardRecordIdsKey(ids);
        if (key === this._payloadKey && !forceRender) {
            return; // 同一批 id 已处理过
        }
        this._payloadKey = key;
        await fillProductCardPayload(ids);
        if (forceRender && this.rootRef.el) {
            this.render(true);
        }
    }

    // ---------------------------------------------------------------------
    // 布局：瀑布流
    // ---------------------------------------------------------------------

    /**
     * JS 瀑布流：按容器宽算列数，每个卡片放当前最矮列（top/left absolute），
     * 容器高度 = 最高列。图片未加载时 offsetHeight 不准，故监听 img load 重算。
     *
     * 分组视图不参与（卡片按列内正常流布局，见 SCSS），只需清掉瀑布流的 inline 定位。
     */
    _layoutWaterfall() {
        const container = this.rootRef.el;
        if (!container) {
            return;
        }
        // 分组判据同时看类与直接子元素（分组时直接子元素是 .o_kanban_group），
        // 不依赖渲染器根类是否带上 o_kanban_grouped，切换分组后不会误判
        const isGrouped =
            container.classList.contains("o_kanban_grouped") ||
            Boolean(container.querySelector(":scope > .o_kanban_group"));
        if (isGrouped) {
            this._clearCardLayout(container);
            return;
        }
        const cards = container.querySelectorAll(
            ":scope > .o_kanban_record:not(.o_kanban_ghost)"
        );
        if (!cards.length) {
            container.style.height = "";
            return;
        }
        const innerWidth = container.clientWidth - PAD * 2;
        if (innerWidth <= 0) {
            return; // 容器还没布局完（宽度为 0），算出来的列数没有意义
        }
        const numCols = Math.max(1, Math.floor((innerWidth + GAP) / (CARD_MIN_WIDTH + GAP)));
        let cardWidth = Math.floor((innerWidth - GAP * (numCols - 1)) / numCols);
        cardWidth = Math.min(cardWidth, CARD_MAX_WIDTH);
        const colHeights = new Array(numCols).fill(0);
        for (const card of cards) {
            const col = colHeights.indexOf(Math.min(...colHeights));
            card.style.position = "absolute";
            card.style.width = cardWidth + "px";
            card.style.left = PAD + col * (cardWidth + GAP) + "px";
            card.style.top = PAD + colHeights[col] + "px";
            colHeights[col] += card.offsetHeight + GAP;
            // 图片未加载完时监听 load，加载后重算（高度变化）
            for (const img of card.querySelectorAll("img")) {
                if (!img.complete) {
                    img.addEventListener("load", this._onImgLoad, { once: true });
                }
            }
        }
        container.style.height = PAD + Math.max(...colHeights) + "px";
    }

    /** 清掉瀑布流写下的 inline 定位（分组视图 / 空页时用），让卡片回到正常流布局。 */
    _clearCardLayout(container) {
        for (const card of container.querySelectorAll(".o_kanban_record")) {
            card.style.position = "";
            card.style.width = "";
            card.style.left = "";
            card.style.top = "";
        }
        container.style.height = "";
    }
}
