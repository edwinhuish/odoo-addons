/** @odoo-module **/

import { onMounted, onPatched, onWillUnmount, useExternalListener } from "@odoo/owl";
import { getPopoverForTarget } from "@web/core/popover/popover";
import { usePopover } from "@web/core/popover/popover_hook";
import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

import { ProductHoverCard } from "./product_hover_card";
import { getLineHoverPayload, prefetchLineHoverPayload } from "./product_hover_cache";

// 只对销售订单行生效：报价单与销售订单共用 sale.order.line 模型与视图，故一并覆盖
const TARGET_MODEL = "sale.order.line";
// 悬停多久后才弹浮层（毫秒）：避免鼠标快速划过时误触
const OPEN_DELAY = 350;
// 鼠标移开后延迟关闭（毫秒）：留出把指针移入浮层的时间
const CLOSE_DELAY = 200;
// 与 __manifest__.py 的 version 保持一致：排查「无浮层」时，先看控制台的 assets 日志确认版本
const MODULE_VERSION = "19.0.1.0.2";

/** 诊断日志：`?debug=1` / `?debug=assets` 下输出（info 级别，控制台默认可见）。 */
function debugInfo(...args) {
    if (typeof odoo !== "undefined" && odoo.debug) {
        console.info(...args);
    }
}

// 资源加载自证（始终输出一条）：确认前端资源已加载，括号内为当前运行版本。
// 若控制台看不到这一行，说明浏览器仍在用旧缓存 / assets 未重建 → `-u` 升级后强刷。
console.info(`[sale_product_hover] assets loaded (${MODULE_VERSION})`);

/**
 * 列表渲染器补丁：订单行悬停展示产品详情浮层。
 *
 * 为什么打补丁而不是继承模板：报价单 / 销售订单表单内的订单行使用 sale 模块
 * 自定义的行模板（`sale.ListRenderer.RecordRow` ← `account.SectionAndNoteListRenderer.RecordRow`），
 * 继承 `web.ListRenderer.RecordRow` 在该处不会生效；补丁作用在 ListRenderer 实例上，
 * 对其所有子类（含自定义渲染器）一致生效，且不必改动任何视图 arch。
 *
 * 事件用 mouseover / mouseout（mouseenter 不冒泡，无法做事件委托），并**双重绑定**：
 * 1) document 级委托：在 setup 阶段注册，与模板结构、挂载时机无关；
 * 2) 渲染器根元素 `this.el` 上再绑一次（onMounted）：兜底不同版本渲染器结构差异。
 * 每个实例用 `this.el.contains(ev.target)` 只处理自己渲染出来的行；同一行重复命中由
 * `_productHoverRowEl` 判重挡住，因此双重绑定不会重复打开浮层。
 *
 * 浮层由 popover 服务渲染在 overlay 容器中，不改变列表 DOM，因此不影响行的
 * 点击、内联编辑、勾选与删除等原有操作。
 */
patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        this._productHoverPopover = usePopover(ProductHoverCard, {
            position: "right-start",
            holdOnHover: true,
            popoverClass: "o_sph_popover",
            // 悬停浮层不得抢占焦点，避免打断正在进行的输入 / 快捷键
            setActiveElement: false,
            onClose: () => this._resetProductHover(),
        });
        this._productHoverRowEl = null;
        this._productHoverBoundEl = null;
        this._productHoverOpenTimer = null;
        this._productHoverCloseTimer = null;
        this._onProductHoverRowOver = this._onProductHoverRowOver.bind(this);
        this._onProductHoverRowOut = this._onProductHoverRowOut.bind(this);
        useExternalListener(document, "mouseover", this._onProductHoverRowOver);
        useExternalListener(document, "mouseout", this._onProductHoverRowOut);
        onMounted(() => {
            this._bindProductHoverToRoot();
            this._prefetchProductHover();
        });
        onPatched(() => this._prefetchProductHover());
        onWillUnmount(() => {
            this._unbindProductHoverFromRoot();
            this._clearProductHoverTimers();
        });
    },

    /** 当前列表渲染的是否为销售订单行。 */
    _isProductHoverList() {
        const list = this.props.list;
        if (!list) {
            return false;
        }
        // 主列表读 list.resModel；x2many 子列表读不到时回退到首条记录
        const resModel = list.resModel || (list.records && list.records[0] && list.records[0].resModel);
        return resModel === TARGET_MODEL;
    },

    /** 兜底监听：document 级委托之外，再绑到渲染器根元素上（见文件头注释）。 */
    _bindProductHoverToRoot() {
        const el = this.el;
        if (!el || this._productHoverBoundEl === el) {
            return;
        }
        this._unbindProductHoverFromRoot();
        el.addEventListener("mouseover", this._onProductHoverRowOver);
        el.addEventListener("mouseout", this._onProductHoverRowOut);
        this._productHoverBoundEl = el;
    },

    _unbindProductHoverFromRoot() {
        if (!this._productHoverBoundEl) {
            return;
        }
        this._productHoverBoundEl.removeEventListener("mouseover", this._onProductHoverRowOver);
        this._productHoverBoundEl.removeEventListener("mouseout", this._onProductHoverRowOut);
        this._productHoverBoundEl = null;
    },

    /**
     * 预取当前页订单行的展示数据：模块级缓存按行 id 去重，翻页 / 筛选后只请求新增行。
     * 悬停时只读缓存，因此不会为每次悬停发请求。
     */
    _prefetchProductHover() {
        if (!this._isProductHoverList()) {
            return;
        }
        const lineIds = [];
        for (const record of this.props.list.records || []) {
            // 尚未保存的新行没有数据库 id，跳过（无浮层数据可展示）
            if (record.resId) {
                lineIds.push(record.resId);
            }
        }
        debugInfo(`[sale_product_hover] prefetch ${TARGET_MODEL}: ${lineIds.length} saved line(s)`);
        if (lineIds.length) {
            prefetchLineHoverPayload(lineIds);
        }
    },

    _onProductHoverRowOver(ev) {
        // 只处理本渲染器渲染出来的行
        if (!this._isProductHoverList() || !this.el || !this.el.contains(ev.target)) {
            return;
        }
        // 编辑态不弹浮层，避免遮挡正在输入的单元格
        if (this.props.list.editedRecord) {
            return;
        }
        const row = ev.target.closest && ev.target.closest("tr.o_data_row");
        if (!row || row === this._productHoverRowEl) {
            return;
        }
        debugInfo("[sale_product_hover] hover row", row.dataset.id);
        this._productHoverRowEl = row;
        this._scheduleProductHoverOpen(row);
    },

    _onProductHoverRowOut(ev) {
        const row = ev.target.closest && ev.target.closest("tr.o_data_row");
        if (!row || row !== this._productHoverRowEl) {
            return;
        }
        const related = ev.relatedTarget;
        // 在同一行内移动、或指针已移入浮层内部时不关闭
        if (related && (row.contains(related) || getPopoverForTarget(row)?.contains(related))) {
            return;
        }
        this._productHoverRowEl = null;
        this._scheduleProductHoverClose();
    },

    _scheduleProductHoverOpen(row) {
        this._clearProductHoverTimers();
        this._productHoverOpenTimer = setTimeout(() => {
            this._productHoverOpenTimer = null;
            this._openProductHover(row);
        }, OPEN_DELAY);
    },

    _scheduleProductHoverClose() {
        this._clearProductHoverTimers();
        this._productHoverCloseTimer = setTimeout(() => {
            this._productHoverCloseTimer = null;
            this._productHoverPopover.close();
        }, CLOSE_DELAY);
    },

    /** 延迟结束且指针仍在行上时，取缓存数据打开浮层；缓存缺失则补一次单行请求。 */
    async _openProductHover(row) {
        if (this._productHoverRowEl !== row) {
            return;
        }
        const record = this._getProductHoverRecord(row);
        if (!record || !record.resId) {
            debugInfo("[sale_product_hover] skip: 行尚无数据库 id（未保存的新行）");
            return;
        }
        let payload = getLineHoverPayload(record.resId);
        if (!payload) {
            await prefetchLineHoverPayload([record.resId]);
            payload = getLineHoverPayload(record.resId);
        }
        // 异步返回后需再次确认指针仍在同一行，且行元素仍在文档中
        if (!payload || this._productHoverRowEl !== row || !row.isConnected) {
            debugInfo("[sale_product_hover] skip: 无数据或指针已移开", record.resId);
            return;
        }
        this._productHoverPopover.open(row, { payload, targetEl: row });
        debugInfo("[sale_product_hover] popover opened for line", record.resId);
    },

    /** 行 DOM（data-id 为 Owl 的 datapoint 内部 id）对应的记录。 */
    _getProductHoverRecord(row) {
        const id = Number(row.dataset.id);
        if (!Number.isFinite(id)) {
            return null;
        }
        return (this.props.list.records || []).find((record) => record.id === id) || null;
    },

    _clearProductHoverTimers() {
        clearTimeout(this._productHoverOpenTimer);
        clearTimeout(this._productHoverCloseTimer);
        this._productHoverOpenTimer = null;
        this._productHoverCloseTimer = null;
    },

    /** 浮层关闭后清空当前行，使指针再次进入该行时能重新计时打开。 */
    _resetProductHover() {
        debugInfo("[sale_product_hover] popover closed");
        this._productHoverRowEl = null;
    },
});
