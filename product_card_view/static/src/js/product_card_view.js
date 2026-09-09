/** @odoo-module **/

import { kanbanView } from "@web/views/kanban/kanban_view";
import { registry } from "@web/core/registry";
import { session } from "@web/session";

import { ProductCardModel } from "./product_card_model";
import { ProductCardRenderer } from "./product_card_renderer";

// 方案 B：Odoo 核心限制——viewRegistry 验证 `type in session.view_info`，
// session.view_info 是服务端核心提供的 view type 白名单（kanban/list/form/...，不含 card）。
// 模块级 Python 无法让服务端补 card，故在模块加载时 patch session.view_info：
//   1) 通过 viewRegistry 的 type 验证（view.js L94）；
//   2) 通过 loadView 的 `session.view_info[type]` 存在性检查（view.js L253）；
//   3) 让视图切换器取到 icon/display_name/multi_record（action_service.js L1222）。
// 升级风险：view.js / action_service.js 改 view_info 用法时需复核此处。
if (!session.view_info) {
    session.view_info = {};
}
if (!("card" in session.view_info)) {
    session.view_info.card = {
        icon: "fa-id-card-o",
        display_name: "Card",
        multi_record: true,
    };
}

// 卡片视图：复用 kanban 的 Controller/ArchParser/searchModel，仅换 Model/Renderer。
// Model 批量装载卡片 payload（WeakMap 非 reactive），Renderer 渲染瀑布流记录卡片。
export const productCardView = {
    ...kanbanView,
    type: "card",
    Model: ProductCardModel,
    Renderer: ProductCardRenderer,
};

registry.category("views").add("card", productCardView);
