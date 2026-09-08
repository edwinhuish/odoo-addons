/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { RelationalModel } from "@web/model/relational_model/relational_model";

/**
 * 加载页面内所有产品后，批量请求一次卡片 payload，存到 model 实例的
 * productCardPayload（按 resId 索引）；卡片组件通过 record.model.productCardPayload
 * 读取数据（含变体/图库/在手等）。
 */
export class ProductCardModel extends RelationalModel {
    // 关闭缓存：productCardPayload 是在 _loadData 中赋值到 model 实例的自定义状态，
    // 缓存命中的请求不会重新执行该赋值，会导致卡片数据陈旧。强制每次重新装载以确保正确性。
    static withCache = false;

    async _loadData(params) {
        const result = await super._loadData(...arguments);
        // 单条记录模式（如快速编辑）无卡片网格需求，跳过额外请求
        if (params.isMonoRecord) {
            return result;
        }
        // 收集本页 resId：
        // - 非分组：result.records 是 webSearchRead 返回的原始对象，.id 即数据库 resId；
        // - 分组：group.records 已是 Record 实例，.id 是 datapoint 内部编号、.resId 才是
        //   数据库 id。统一用 resId（原始对象无 resId，回退 .id）。
        let rawRecords;
        if (params.groupBy?.length) {
            rawRecords = [];
            const stackGroups = [...(result.groups || [])];
            while (stackGroups.length) {
                const group = stackGroups.pop();
                if (group.groups?.length) {
                    stackGroups.push(...group.groups);
                }
                if (group.records?.length) {
                    rawRecords.push(...group.records);
                }
            }
        } else {
            rawRecords = result.records || [];
        }
        const templateIds = rawRecords.map((r) => r.resId ?? r.id);
        // payload 存到 model 实例（key 为 resId，JSON 序列化后成字符串），
        // 卡片组件通过 record.model.productCardPayload[record.resId] 取。
        // 不能挂到 record：super._loadData 返回的 result.records 是原始数据对象，
        // 随后 _createRoot 会用它们重建 Record 实例，自定义属性会被丢弃。
        this.productCardPayload = {};
        if (templateIds.length) {
            const payload = await rpc("/product_card/payload", { template_ids: templateIds });
            this.productCardPayload = payload || {};
        }
        return result;
    }
}
