/** @odoo-module **/

import { onWillStart, onWillUpdateProps } from "@odoo/owl";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";

import { fillProductCardPayload } from "./product_card_model";
import { ProductCardRecord } from "./product_card_record";

/**
 * 渲染器：结构沿用 KanbanRenderer，仅替换记录卡片组件并加自定义根类。
 * 在生命周期钩子（onWillStart / onWillUpdateProps）里批量拉取卡片 payload
 * 填入全局 Map（见 product_card_model.js），卡片组件按 resId 查。
 * 生命周期钩子不在 reactive effect 内，不触发 Owl DataModel 的 onUpdate / reload 循环。
 */
export class ProductCardRenderer extends KanbanRenderer {
    static template = "product_card_view.ProductCardRenderer";

    static components = {
        ...KanbanRenderer.components,
        KanbanRecord: ProductCardRecord,
    };

    setup() {
        super.setup();
        // 首次挂载：model 已加载（ViewController onWillStart await model.load），
        // props.list.records 有数据，拉取 payload；Owl 等 onWillStart resolve 才渲染卡片。
        onWillStart(() => fillProductCardPayload(this.props.list?.records || []));
        // props 变化（翻页 / 筛选 / reload 重建 root）：重新拉取。
        onWillUpdateProps((nextProps) =>
            fillProductCardPayload(nextProps.list?.records || [])
        );
    }
}
