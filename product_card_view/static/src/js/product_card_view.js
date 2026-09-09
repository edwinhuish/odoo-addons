/** @odoo-module **/

import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanArchParser } from "@web/views/kanban/kanban_arch_parser";
import { registry } from "@web/core/registry";
import { session } from "@web/session";

import { ProductCardModel } from "./product_card_model";
import { ProductCardRenderer } from "./product_card_renderer";

// 方案 B：Odoo 核心限制——viewRegistry 验证 `type in session.view_info`，
// session.view_info 是服务端核心提供的 view type 白名单（kanban/list/form/...，不含 card）。
// 模块级 Python 无法让服务端补 card，故在模块加载时 patch session.view_info：
//   1) 通过 viewRegistry 的 type 验证（view.js L94，仅 debug 模式）；
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

// card arch 经 server 验证禁止 owl 指令（t-name），故 arch 无 <templates>；
// 但 KanbanArchParser 要求 <t t-name="card"> 模板（否则报 Missing 'card' template）。
// 此处 parse 时注入虚拟 card 模板让 super.parse 通过——实际卡片由
// ProductCardRenderer 自绘，不读此模板。
class ProductCardArchParser extends KanbanArchParser {
    parse(xmlDoc, models, modelName) {
        if (!xmlDoc.querySelector("templates")) {
            const doc = xmlDoc.ownerDocument;
            const templates = doc.createElement("templates");
            const t = doc.createElement("t");
            t.setAttribute("t-name", "card");
            t.appendChild(doc.createElement("div"));
            templates.appendChild(t);
            xmlDoc.appendChild(templates);
        }
        return super.parse(xmlDoc, models, modelName);
    }
}

// 卡片视图：复用 kanban 的 Controller/searchModel，换 ArchParser（注入虚拟模板）、
// Model（批量装载卡片 payload，WeakMap 非 reactive）、Renderer（瀑布流记录卡片）。
export const productCardView = {
    ...kanbanView,
    type: "card",
    ArchParser: ProductCardArchParser,
    Model: ProductCardModel,
    Renderer: ProductCardRenderer,
};

registry.category("views").add("card", productCardView);
