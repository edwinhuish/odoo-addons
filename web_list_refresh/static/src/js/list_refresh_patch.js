/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListController } from "@web/views/list/list_controller";
import { KanbanController } from "@web/views/kanban/kanban_controller";

import { useViewRefresh } from "./view_refresh";

// 列表（树形）视图：内联编辑态先保存，校验失败则中止刷新、保留草稿
// （与原生分页器的处理一致，见 list_controller.js 的 usePager.onUpdate）。
patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);
        useViewRefresh(() => this.model, {
            onBeforeReload: async () => {
                if (this.editedRecord) {
                    return this.editedRecord.save();
                }
            },
        });
    },
});

// 看板视图：无内联编辑，直接刷新。
// 本仓库 product_card_view 的 card 视图复用 KanbanController，
// 以及任何 `...kanbanView` / `...listView` 派生的自定义视图都会一并拿到按钮。
patch(KanbanController.prototype, {
    setup() {
        super.setup(...arguments);
        useViewRefresh(() => this.model);
    },
});
