/** @odoo-module **/

import { onMounted, onWillStart, onWillUnmount, onWillUpdateProps } from "@odoo/owl";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";

import { fillProductCardPayload } from "./product_card_model";
import { ProductCardRecord } from "./product_card_record";

// 瀑布流参数
const CARD_MIN_WIDTH = 240; // 卡片最小宽（15rem）
const CARD_MAX_WIDTH = 360; // 卡片最大宽（22.5rem）
const GAP = 12; // 卡片间距（0.75rem）
const PAD = 12; // 容器内边距（0.75rem）

/**
 * 渲染器：结构沿用 KanbanRenderer，仅替换记录卡片组件并加自定义根类。
 * 在生命周期钩子（onWillStart / onWillUpdateProps）里批量拉取卡片 payload
 * 填入全局 Map（见 product_card_model.js），卡片组件按 resId 查。
 *
 * 未分组时启用 JS 瀑布流：卡片 position absolute，按内容高度放最矮列，
 * 各列高度均衡；响应式列数（容器宽 / CARD_MIN_WIDTH）；
 * resize + 图片 load 重算；卡片 transition 平滑过渡。
 *
 * 用 requestAnimationFrame 延迟一帧再算：等 KanbanRecord 子组件挂载完、
 * DOM 尺寸稳定（首次 / props 变更后）。
 */
export class ProductCardRenderer extends KanbanRenderer {
    static template = "product_card_view.ProductCardRenderer";

    static components = {
        ...KanbanRenderer.components,
        KanbanRecord: ProductCardRecord,
    };

    setup() {
        super.setup();
        this._onResize = this._debounce(() => this._layoutWaterfall(), 150);
        this._onImgLoad = () => this._layoutWaterfall();
        onWillStart(() => fillProductCardPayload(this.props.list?.records || []));
        onWillUpdateProps((nextProps) => {
            fillProductCardPayload(nextProps.list?.records || []);
            // props 变（翻页/筛选/reload）后下一帧重算（等 DOM 更新）
            requestAnimationFrame(() => this._layoutWaterfall());
        });
        onMounted(() => {
            window.addEventListener("resize", this._onResize);
            // 下一帧再算：等子组件挂载完、offsetHeight 稳定
            requestAnimationFrame(() => this._layoutWaterfall());
        });
        onWillUnmount(() => {
            window.removeEventListener("resize", this._onResize);
        });
    }

    _debounce(fn, wait) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), wait);
        };
    }

    /**
     * JS 瀑布流：按容器宽算列数，每个卡片放当前最矮列（top/left absolute），
     * 容器高度 = 最高列。图片未加载时 offsetHeight 不准，故监听 img load 重算。
     */
    _layoutWaterfall() {
        const container = this.el;
        console.warn("[PCV DEBUG] _layoutWaterfall: container=", !!container, "ungrouped=", container?.classList?.contains("o_kanban_ungrouped"));
        if (!container || !container.classList.contains("o_kanban_ungrouped")) {
            return;
        }
        const cards = container.querySelectorAll(
            ":scope > .o_kanban_record:not(.o_kanban_ghost)"
        );
        console.warn("[PCV DEBUG] cards.length=", cards.length, "innerWidth=", container.clientWidth - PAD * 2);
        if (!cards.length) {
            container.style.height = "";
            return;
        }
        const innerWidth = container.clientWidth - PAD * 2;
        const numCols = Math.max(1, Math.floor((innerWidth + GAP) / (CARD_MIN_WIDTH + GAP)));
        let cardWidth = Math.floor((innerWidth - GAP * (numCols - 1)) / numCols);
        cardWidth = Math.min(cardWidth, CARD_MAX_WIDTH);
        const colHeights = new Array(numCols).fill(0);
        let _dbg = 0;
        for (const card of cards) {
            const col = colHeights.indexOf(Math.min(...colHeights));
            card.style.position = "absolute";
            card.style.width = cardWidth + "px";
            card.style.left = PAD + col * (cardWidth + GAP) + "px";
            card.style.top = PAD + colHeights[col] + "px";
            colHeights[col] += card.offsetHeight + GAP;
            if (_dbg < 3) {
                _dbg++;
                console.warn("[PCV DEBUG] card #" + _dbg, "offsetHeight=", card.offsetHeight, "col=", col, "top=", card.style.top, "left=", card.style.left, "width=", card.style.width);
            }
            // 图片未加载完时监听 load，加载后重算（高度变化）
            for (const img of card.querySelectorAll("img")) {
                if (!img.complete) {
                    img.addEventListener("load", this._onImgLoad, { once: true });
                }
            }
        }
        container.style.height = PAD + Math.max(...colHeights) + "px";
    }
}
