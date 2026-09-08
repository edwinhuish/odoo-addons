/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { RelationalModel } from "@web/model/relational_model/relational_model";

/**
 * 加载页面内所有产品后，批量请求一次卡片 payload 并挂到对应 record 上，
 * 渲染器与记录组件从 record.productCardData 读取数据（含变体/图库/在手等）。
 */
export class ProductCardModel extends RelationalModel {
    // 关闭缓存：productCardData 是在 _loadData 中挂到 record 实例上的自定义字段，
    // 缓存命中的 record 副本不会带上该字段，会导致卡片无数据。强制每次重新装载以确保正确性。
    static withCache = false;

    async _loadData(params) {
        const result = await super._loadData(...arguments);
        // 单条记录模式（如快速编辑）无卡片网格需求，跳过额外请求
        if (params.isMonoRecord) {
            return result;
        }
        // 收集本页实际展示的产品 id（分组展开后同样逐组收集）
        let records;
        if (params.groupBy?.length) {
            records = [];
            const stackGroups = [...(result.groups || [])];
            while (stackGroups.length) {
                const group = stackGroups.pop();
                if (group.groups?.length) {
                    stackGroups.push(...group.groups);
                }
                if (group.records?.length) {
                    records.push(...group.records);
                }
            }
        } else {
            records = result.records || [];
        }

        const templateIds = records.map((record) => record.id);
        if (templateIds.length) {
            const payload = await rpc("/product_card/payload", { template_ids: templateIds });
            for (const record of records) {
                record.productCardData = payload[record.id] || null;
            }
        }
        return result;
    }
}
