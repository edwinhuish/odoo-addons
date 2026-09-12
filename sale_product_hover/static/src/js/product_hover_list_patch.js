/** @odoo-module **/

import { onMounted, onPatched, onWillUnmount, status } from "@odoo/owl";
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

/**
 * 列表渲染器补丁：订单行悬停展示产品详情浮层。
 *
 * 为什么打补丁而不是继承模板：报价单 / 销售订单表单内的订单行使用 sale 模块
 * 自定义的行模板（`sale.ListRenderer.RecordRow`），继承 `web.ListRenderer.RecordRow`
 * 在该处不会生效；补丁作用在 ListRenderer 实例上，对其所有子类（含自定义渲染器）
 * 一致生效，且不必改动任何视图 arch。
 *
 * 事件用原生 mouseover / mouseout 委托在渲染器根节点上（mouseenter 不冒泡，
 * 无法做事件委托），并通过「同一行内移动不重开」与「移入浮层不关闭」避免抖动。
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
            onClose: () => this._resetProductHover(),
        });
        this._productHoverRowEl = null;
        this._productHoverRootEl = null;
        this._productHoverOpenTimer = null;
        this._productHoverCloseTimer = null;
        this._onProductHoverRowOver = this._onProductHoverRowOver.bind(this);
        this._onProductHoverRowOut = this._onProductHoverRowOut.bind(this);
        onMounted(() => {
            this._bindProductHover();
            this._prefetchProductHover();
        });
        onPatched(() => this._prefetchProductHover());
        onWillUnmount(() => {
            this._unbindProductHover();
            this._clearProductHoverTimers();
        });
    },

    /** 当前列表渲染的是否为销售订单行。 */
    _isProductHoverList() {
        return this.props.list && this.props.list.resModel === TARGET_MODEL;
    },

    /** 在渲染器根节点上委托悬停事件（根节点在卸载前不变，绑定一次即可）。 */
    _bindProductHover() {
        const root = this.rootRef && this.rootRef.el;
        if (!root || this._productHoverRootEl === root) {
            return;
        }
        this._unbindProductHover();
        root.addEventListener("mouseover", this._onProductHoverRowOver);
        root.addEventListener("mouseout", this._onProductHoverRowOut);
        this._productHoverRootEl = root;
    },

    _unbindProductHover() {
        if (!this._productHoverRootEl) {
            return;
        }
        this._productHoverRootEl.removeEventListener("mouseover", this._onProductHoverRowOver);
        this._productHoverRootEl.removeEventListener("mouseout", this._onProductHoverRowOut);
        this._productHoverRootEl = null;
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
        if (lineIds.length) {
            prefetchLineHoverPayload(lineIds);
        }
    },

    _onProductHoverRowOver(ev) {
        // 编辑态不弹浮层，避免遮挡正在输入的单元格
        if (!this._isProductHoverList() || this.props.list.editedRecord) {
            return;
        }
        const row = ev.target.closest && ev.target.closest("tr.o_data_row");
        if (!row || row === this._productHoverRowEl) {
            return;
        }
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
            return;
        }
        let payload = getLineHoverPayload(record.resId);
        if (!payload) {
            await prefetchLineHoverPayload([record.resId]);
            payload = getLineHoverPayload(record.resId);
        }
        // 异步返回后需再次确认指针仍在同一行，且组件未被销毁
        if (!payload || this._productHoverRowEl !== row || status(this) === "destroyed") {
            return;
        }
        this._productHoverPopover.open(row, { payload, targetEl: row });
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
        this._productHoverRowEl = null;
    },
});
