/** @odoo-module **/

import { kanbanView } from "@web/views/kanban/kanban_view";
import { registry } from "@web/core/registry";

import { ProductCardModel } from "./product_card_model";
import { ProductCardRenderer } from "./product_card_renderer";

// 注册新 view type "card"：复用 kanban 的 Controller/ArchParser/search，
// 换 Model/Renderer 为产品卡片瀑布流。arch 用 <card>（KanbanArchParser 不
// 检查根元素名，读属性 + 遍历子节点，<card> 可被解析）。
export const cardView = {
    ...kanbanView,
    type: "card",
    display_name: "Card",
    icon: "fa-th-large",
    Model: ProductCardModel,
    Renderer: ProductCardRenderer,
};

registry.category("views").add("card", cardView);
