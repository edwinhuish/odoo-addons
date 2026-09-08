/** @odoo-module **/

import { kanbanView } from "@web/views/kanban/kanban_view";
import { registry } from "@web/core/registry";

import { ProductCardModel } from "./product_card_model";
import { ProductCardRenderer } from "./product_card_renderer";

// Kanban 允许在视图 arch 上写 js_class="product_cards"，web 加载时会用本注册表
// 项替换默认 kanban 的 Model / Renderer，其余（Controller/ArchParser/搜索等）原样复用。
export const productCardView = {
    ...kanbanView,
    Model: ProductCardModel,
    Renderer: ProductCardRenderer,
};

registry.category("views").add("product_cards", productCardView);
