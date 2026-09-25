/** @odoo-module **/

import { useSubEnv } from "@odoo/owl";

/**
 * 把一个「刷新处理器」注册进当前视图的 sub-env，供控制面板里的刷新按钮消费。
 *
 * 为什么是「无参 model.load()」而不是自己拼搜索参数：
 * - 视图的数据模型（RelationalModel）的 config 里已经存着上一次加载用的
 *   domain / context / groupBy / orderBy / limit / offset / currentGroups；
 * - model.load() 不传参时 `_getNextConfig()` 直接复用这份 config，
 *   因此搜索条件、分组（含展开态）、排序、分页位置全部原样保留；
 * - 反过来，一旦显式把搜索状态传回去（`model.load({ domain, ... })`），
 *   核心会因为「params.domain 非空」把 offset 归零，刷新后跳回第 1 页。
 * 搜索状态本身由 `WithSearch` 持有的 SearchModel 管理，刷新全程不重建它。
 *
 * 未注册处理器的视图（表单等）控制面板里 `t-if="env.viewRefresh"` 为假，
 * 按钮不渲染 —— 缺谁都不报错，只是少一个按钮。
 *
 * @param {() => import("@web/model/relational_model/relational_model").RelationalModel} getModel
 *   返回本视图的数据模型（list / kanban / card 都是控制器的 `this.model`）。
 * @param {{ onBeforeReload?: () => Promise<boolean|void> }} [options]
 *   `onBeforeReload` 返回 `false` 时中止刷新（例如列表内联编辑校验失败）。
 */
export function useViewRefresh(getModel, { onBeforeReload } = {}) {
    useSubEnv({
        viewRefresh: {
            refresh: async () => {
                if (onBeforeReload && (await onBeforeReload()) === false) {
                    return;
                }
                await getModel().load();
            },
        },
    });
}
