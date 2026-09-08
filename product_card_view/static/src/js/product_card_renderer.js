/** @odoo-module **/

import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";

import { ProductCardRecord } from "./product_card_record";

/**
 * 渲染器：结构完全沿用 KanbanRenderer，仅替换记录卡片组件并加自定义根类。
 * 模板 product_card_view.ProductCardRenderer 是对 web.KanbanRenderer 的
 * primary 继承副本（加 o_product_card_view 类），样式里据此切到瀑布流布局。
 */
export class ProductCardRenderer extends KanbanRenderer {
    static template = "product_card_view.ProductCardRenderer";

    static components = {
        ...KanbanRenderer.components,
        KanbanRecord: ProductCardRecord,
    };
}
