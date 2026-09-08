/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { RelationalModel } from "@web/model/relational_model/relational_model";

/**
 * 视图加载（root 就绪）后批量请求一次卡片 payload，按 resId 挂到各 Record
 * 实例的 productCardData；卡片组件从 record.productCardData 读取
 * （变体 / 图库 / 在手等）。
 *
 * 必须重写 load 而非 _loadData：
 * - _loadData 在 root 创建前执行，挂到 result.records 的属性会被 _createRoot
 *   重建 Record 实例时丢弃；
 * - 在 _loadData 里给 reactive model 赋值会触发 reload 循环（keepLast 竞争 +
 *   第二次空响应 + 页面卡死）。
 * ViewController await load，故渲染时 payload 已就绪，无闪烁。
 */
export class ProductCardModel extends RelationalModel {
    // 关闭缓存：productCardData 是在 load 后挂到 Record 实例的自定义属性，
    // 缓存命中的请求不会重新执行该挂载，会导致卡片数据陈旧。
    static withCache = false;

    async load(params = {}) {
        await super.load(params);
        const records = this._collectCardRecords();
        const templateIds = records
            .map((record) => record.resId)
            .filter((id) => id != null);
        if (!templateIds.length) {
            return;
        }
        const payload = await rpc("/product_card/payload", { template_ids: templateIds });
        for (const record of records) {
            record.productCardData = (payload && payload[record.resId]) || null;
        }
    }

    /**
     * 从 root 收集当前展示的 Record 实例：
     * - 非分组：DynamicRecordList.records（数组）；
     * - 分组：DynamicGroupList.records（getter，含所有非折叠组的记录）。
     * mono record（表单 / 快速编辑）无 records，返回空数组跳过。
     */
    _collectCardRecords() {
        const root = this.root;
        if (!root) {
            return [];
        }
        return root.records || [];
    }
}
