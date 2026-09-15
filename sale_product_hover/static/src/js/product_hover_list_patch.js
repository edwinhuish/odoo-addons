/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { onMounted, onPatched, onWillUnmount, useExternalListener } from "@odoo/owl";
import { getPopoverForTarget } from "@web/core/popover/popover";
import { usePopover } from "@web/core/popover/popover_hook";
import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

import { ProductHoverCard } from "./product_hover_card";
import {
    getLineHoverPayload,
    prefetchDraftHoverPayload,
    prefetchLineHoverPayload,
    setClientVersion,
} from "./product_hover_cache";

// 只对销售订单行生效：报价单与销售订单共用 sale.order.line 模型与视图，故一并覆盖
const TARGET_MODEL = "sale.order.line";
// 数据行 DOM：web.ListRenderer 与 sale 的自定义行模板都会渲染 tr.o_data_row[data-id]
const ROW_SELECTOR = "tr.o_data_row";
// 悬停多久后才弹浮层（毫秒）：避免鼠标快速划过时误触
const OPEN_DELAY = 300;
// 鼠标移开后延迟关闭（毫秒）：留出把指针移入浮层的时间
const CLOSE_DELAY = 200;
// 触屏长按多久后弹浮层（毫秒）：触屏没有 hover，用长按代替
const TOUCH_OPEN_DELAY = 500;
// 触屏手势结束后忽略浏览器补发的 mouse 事件的时间窗（毫秒），避免"点一下弹两次"
const TOUCH_MOUSE_GRACE = 800;
// 长按过程中位移超过该阈值（像素）即视为滚动，取消长按
const TOUCH_MOVE_TOLERANCE = 10;
// 浮层相对光标的偏移（像素）：贴在光标右下，不遮住光标本身
const POINTER_OFFSET_X = 16;
const POINTER_OFFSET_Y = 12;
// 与视口边缘的最小间距（像素）：跟随鼠标时也不让浮层被屏幕裁切
const VIEWPORT_MARGIN = 8;
// 与 __manifest__.py 的 version 保持一致（**三处同步**：manifest / 本文件 /
// controllers/product_hover_controller.py 的 MODULE_VERSION）。
// 排查「无浮层」时先看控制台的 assets 日志确认版本；接口还会回显服务端版本，
// 两者不一致时缓存层会直接告警（见 product_hover_cache.js 的 checkServerVersion）。
const MODULE_VERSION = "19.0.1.3.2";

// document 级监听一律用捕获阶段：行内可能有业务自己的 `stopPropagation`
// （如列表在触屏选择模式下会拦截 mouseover），捕获阶段先于它们触发，不受影响。
const CAPTURE = { capture: true };

/** 诊断日志：`?debug=1` / `?debug=assets` 下输出（info 级别，控制台默认可见）。 */
function debugInfo(...args) {
    if (typeof odoo !== "undefined" && odoo.debug) {
        console.info(...args);
    }
}

// 资源加载自证（始终输出一条）：确认前端资源已加载，括号内为当前运行版本。
// 若控制台看不到这一行，说明浏览器仍在用旧缓存 / assets 未重建 → `-u` 升级后强刷。
// 加载期自检：命名导入在「源码漏改 / 资源与代码不同步」时可能拿到 undefined，那样只会
// 等到悬停时才抛 `xxx is not a function`，排查代价很高——`19.0.1.3.1` 就真踩过：
// 整份重写缓存模块时漏掉了 `getLineHoverPayload` 的导出，表现是悬停时
// `Uncaught TypeError: getLineHoverPayload is not a function`。这里在加载时就一次性查明并报出来。
const hoverHelpers = {
    getLineHoverPayload,
    prefetchDraftHoverPayload,
    prefetchLineHoverPayload,
    setClientVersion,
};
const missingHoverHelpers = Object.keys(hoverHelpers).filter(
    (name) => typeof hoverHelpers[name] !== "function"
);
if (missingHoverHelpers.length) {
    console.error(
        `[sale_product_hover] assets are inconsistent: ${missingHoverHelpers.join(", ")} ` +
            "missing from product_hover_cache.js exports — the hover card will not work. " +
            "Hard refresh (Ctrl+Shift+R) and run `-u sale_product_hover`; if it persists, " +
            "compare the named imports with the cache module's exports."
    );
}

setClientVersion(MODULE_VERSION);
console.info(`[sale_product_hover] assets loaded (${MODULE_VERSION})`);

/**
 * 列表渲染器补丁：订单行悬停（触屏为长按）展示产品详情浮层。
 *
 * 为什么打补丁而不是继承模板：报价单 / 销售订单表单内的订单行使用 sale 模块
 * 自定义的行模板（`sale.ListRenderer.RecordRow` ← `account.SectionAndNoteListRenderer.RecordRow`
 * ← `web.ListRenderer.RecordRow`），继承 `web.ListRenderer.RecordRow` 在该处不会生效；
 * 补丁作用在 `ListRenderer` 实例上，对其所有子类（含自定义渲染器）一致生效，
 * 且不必改动任何视图 arch。
 *
 * 事件用 document 级**捕获阶段**委托（mouseover / mouseout / touchstart / …）：
 * - `mouseenter` / `mouseleave` 不冒泡，无法做事件委托，故用 mouseover / mouseout；
 * - 捕获阶段注册，先于行内业务监听触发，不会被 `stopPropagation` 吃掉；
 * - 与渲染器 DOM 结构、挂载时机、根节点 ref 均无关（自定义渲染器的 `t-ref="root"`
 *   不一定存在，这是本模块 19.0.1.0.1 之前「悬停完全没反应」的根因）。
 *
 * 「这一行是否属于本渲染器」不靠 `this.el.contains()` 判断，而是用行的 `data-id`
 * （Owl datapoint id）反查 `props.list.records`：查得到就是本渲染器的行。这样既不依赖
 * 根元素结构，也天然排除其他模型的列表。
 *
 * 已保存行与**尚未保存的新行**（刚新增的产品行）都能预览：
 * - 缓存键 `_getProductHoverKey()`：已保存行用数据库 id，新行用 datapoint id；
 * - 新行由 `_getProductHoverDraft()` 把表单里正在编辑的值交给后端格式化，
 *   取值一变签名就变、`onPatched` 会重新预取，所以数量 / 单价改完立刻反映到浮层；
 * - 编辑态避让只针对「正在被内联编辑的**已保存**行」（`_isProductHoverBlockedByEdit()`）——
 *   Odoo 里 `Record.isInEdition` 对 `!resId` 恒为真，新行一加进来就是 `editedRecord`，
 *   旧版一刀切导致新增产品永远没有预览。
 *
 * 浮层由 popover 服务渲染在 overlay 容器，不改变列表 DOM，因此不影响行的
 * 点击、内联编辑、勾选与删除等原有操作。
 *
 * 位置：popover 以**行**为目标（`target` 用行元素，`getPopoverForTarget(row)` 才能查到浮层），
 * 但落点由 `_positionProductHover()` 自己算——贴着光标右下、空间不足时翻到左上。
 * Odoo 的 `reposition()` 会把浮层设成 `position: fixed` 并写 `left/top`（视口坐标），
 * 所以后续可以直接改 `left/top` 来跟随鼠标，不会与 Odoo 的定位打架
 * （每次 Odoo 重定位后都会回调 `onPositioned`，我们在那里再套用一次光标位置）。
 */
patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        this._productHoverPopover = usePopover(ProductHoverCard, {
            position: "right-start",
            // 关闭开合动画：浮层跟随鼠标，动画的位移/锁位只会造成抖动
            animation: false,
            arrow: false,
            // 指针移入浮层后锁定位置（`holdOnHover`），方便阅读
            holdOnHover: true,
            popoverClass: "o_sph_popover",
            // 悬停浮层不得抢占焦点，避免打断正在进行的输入 / 快捷键
            setActiveElement: false,
            onClose: () => this._onProductHoverClosed(),
            // Odoo 每次重新定位后（挂载 / 滚动 / 缩放）都会回调，用来把浮层拉回光标处
            onPositioned: (el) => this._positionProductHover(this._productHoverPointer, el),
        });
        this._productHoverRowEl = null;
        this._productHoverPointer = null;
        this._productHoverFollowFrame = null;
        this._productHoverOpenTimer = null;
        this._productHoverCloseTimer = null;
        this._productHoverTouchTimer = null;
        this._productHoverTouchOrigin = null;
        this._productHoverTouchActive = false;
        this._productHoverTouchGraceTimer = null;

        this._onProductHoverMouseOver = this._onProductHoverMouseOver.bind(this);
        this._onProductHoverMouseOut = this._onProductHoverMouseOut.bind(this);
        this._onProductHoverMouseEnter = this._onProductHoverMouseEnter.bind(this);
        this._onProductHoverMouseMove = this._onProductHoverMouseMove.bind(this);
        this._onProductHoverTouchStart = this._onProductHoverTouchStart.bind(this);
        this._onProductHoverTouchMove = this._onProductHoverTouchMove.bind(this);
        this._onProductHoverTouchEnd = this._onProductHoverTouchEnd.bind(this);

        useExternalListener(document, "mouseover", this._onProductHoverMouseOver, CAPTURE);
        useExternalListener(document, "mouseout", this._onProductHoverMouseOut, CAPTURE);
        useExternalListener(document, "mousemove", this._onProductHoverMouseMove, {
            capture: true,
            passive: true,
        });
        useExternalListener(document, "mouseenter", this._onProductHoverMouseEnter, CAPTURE);
        useExternalListener(document, "touchstart", this._onProductHoverTouchStart, CAPTURE);
        useExternalListener(document, "touchmove", this._onProductHoverTouchMove, CAPTURE);
        useExternalListener(document, "touchend", this._onProductHoverTouchEnd, CAPTURE);
        useExternalListener(document, "touchcancel", this._onProductHoverTouchEnd, CAPTURE);

        onMounted(() => this._prefetchProductHover());
        onPatched(() => {
            // 行被重渲染替换后，旧元素已脱离文档：清掉引用与浮层，避免卡在"已悬停"状态
            if (this._productHoverRowEl && !this._productHoverRowEl.isConnected) {
                this._resetProductHover();
                this._productHoverPopover.close();
            }
            this._prefetchProductHover();
        });
        onWillUnmount(() => this._cancelProductHoverFollow());
    },

    /** 当前列表渲染的是否为销售订单行。 */
    _isProductHoverList() {
        const list = this.props.list;
        if (!list) {
            return false;
        }
        // 主列表读 list.resModel；x2many 子列表取不到时回退到首条记录
        const resModel = list.resModel || (list.records && list.records[0] && list.records[0].resModel);
        return resModel === TARGET_MODEL;
    },

    /**
     * 预取当前页订单行的展示数据：模块级缓存按键去重，翻页 / 筛选后只请求新增行。
     * 悬停时只读缓存，因此不会为每次悬停发请求。
     *
     * 已保存行按数据库 id 批量取；**尚未保存的新行**（刚新增的产品行）改送「草稿规格」，
     * 让它在落库之前也能预览——新行数量 / 单价一变，签名就变，`onPatched` 会重新预取，
     * 所以浮层内容始终跟着表单里的输入走。
     */
    _prefetchProductHover() {
        if (!this._isProductHoverList()) {
            return;
        }
        const lineIds = [];
        const drafts = [];
        for (const record of this.props.list.records || []) {
            if (record.resId) {
                lineIds.push(record.resId);
                continue;
            }
            const draft = this._getProductHoverDraft(record);
            if (draft) {
                drafts.push(draft);
            }
        }
        debugInfo(
            `[sale_product_hover] prefetch ${TARGET_MODEL}: ` +
                `${lineIds.length} saved / ${drafts.length} draft line(s)`
        );
        if (lineIds.length) {
            prefetchLineHoverPayload(lineIds);
        }
        if (drafts.length) {
            prefetchDraftHoverPayload(drafts);
        }
    },

    /**
     * 行 DOM 对应的记录；查不到（不是本列表的行）返回 null。
     *
     * 行的 `data-id` 是 Owl 的 **datapoint id，字符串**（`getId()` 返回
     * `"datapoint_<n>"`，见 `model/relational_model/utils.js`），必须**按字符串比较**：
     * 旧实现写成 `Number(row.dataset.id)` → `NaN` → 反查永远失败、悬停完全没反应
     * （这是本模块 `19.0.1.0.0`~`19.0.1.1.0` 「悬停无浮层」的真正根因）。
     * Odoo 官方同样直接比字符串，如 `kanban_renderer.js`：
     * `records.find((e) => e.id === target.dataset.id)`。
     * 这里两侧都做一次字符串化，兼容日后 id 类型变化。
     */
    _getProductHoverRecord(row) {
        const datapointId = row.dataset.id;
        if (!datapointId) {
            return null;
        }
        return (
            (this.props.list.records || []).find(
                (record) => String(record.id) === datapointId
            ) || null
        );
    },

    /**
     * 缓存 / payload 的键：**已保存行用数据库 id（数字）**，**未保存的新行用 Owl datapoint id**
     * （字符串，形如 `"datapoint_42"`）。两者不会冲突，而且新行从加入列表那一刻起就有键，
     * 不必等落库才能预览。
     */
    _getProductHoverKey(record) {
        return record.resId || record.id;
    },

    /**
     * 未保存新行交给后端的「草稿规格」；还没选产品（或分节 / 备注行）时返回 null。
     *
     * 新行没有数据库 id，展示数据只能由前端把表单里正在编辑的值传上去，后端按同样口径
     * 读产品并格式化——所以新行与已保存行的浮层内容完全一致。
     * 取值的形态见 `model/relational_model/record.js`：many2one 是 `{id, display_name}`
     * 对象（不是 `[id, name]` 数组）。
     */
    _getProductHoverDraft(record) {
        const data = record.data || {};
        const product = data.product_id;
        if (!product || !product.id || data.display_type) {
            return null;
        }
        const uom = data.product_uom_id;
        // 新行的 currency_id 可能还没从 onchange 回来，退回订单（父记录）的币种。
        // 两种来源的形态不同：`record.data` 里是 `{id, display_name}` 对象，
        // 而 `evalContext` 里（`record.js._computeDataContext()`）many2one 已经被压成 id 数字。
        const currency = data.currency_id || record.evalContext?.parent?.currency_id;
        const currencyId = typeof currency === "number" ? currency : currency?.id;
        return {
            key: record.id,
            product_id: product.id,
            quantity: data.product_uom_qty,
            uom_name: uom ? uom.display_name : "",
            price_unit: data.price_unit,
            currency_id: currencyId || null,
        };
    },

    /**
     * 编辑态是否需要避让浮层。
     *
     * 已保存的行在内联编辑时不弹（避免遮住正在改的字段）；**未保存的新行例外**：
     * Odoo 的 `Record.isInEdition` 对 `!resId` 恒为真
     * （`model/relational_model/record.js`：`this.config.mode === "edit" || !this.resId`），
     * 新行一加进列表就已经是 `editedRecord`——照旧一刀切的话，新增的产品行永远没有预览；
     * 而且只要列表里存在一条新行，其它**已保存行**也会被一起挡掉。
     */
    _isProductHoverBlockedByEdit(record) {
        const editedRecord = this.props.list.editedRecord;
        return Boolean(editedRecord && editedRecord === record && record.resId);
    },

    /**
     * 事件命中的订单行；不属于本渲染器时返回 null。
     *
     * 用「行的 data-id 能查到本列表的记录」判定归属，等价于（且比）`this.el.contains()`
     * 更稳：不依赖渲染器根元素，也不会误判其他模型列表的行。
     */
    _getProductHoverRowFromEvent(ev) {
        if (!this._isProductHoverList()) {
            return null;
        }
        const row = ev.target?.closest?.(ROW_SELECTOR);
        // 分节 / 备注行也在 o_data_row 里，但后端不会为它们生成 payload，
        // 因此统一交给 `_openProductHover` 的「无数据则跳过」处理，这里不特判。
        return row && this._getProductHoverRecord(row) ? row : null;
    },

    _onProductHoverMouseOver(ev) {
        // 触屏刚结束时浏览器会补发 mouse 事件，忽略以免重复弹出
        if (this._productHoverTouchActive) {
            return;
        }
        const row = this._getProductHoverRowFromEvent(ev);
        if (!row) {
            return;
        }
        // 记录光标位置：浮层就落在光标右下（见 `_positionProductHover`）
        this._productHoverPointer = { x: ev.clientX, y: ev.clientY };
        if (row === this._productHoverRowEl) {
            return;
        }
        // 该行已挂着浮层（例如刚由浮层内部移回）：只校准状态，不重新计时打开
        if (getPopoverForTarget(row)) {
            this._productHoverRowEl = row;
            return;
        }
        // 编辑态避让：正在内联编辑的**已保存行**不弹（未保存的新行不受限，见该方法注释）
        if (this._isProductHoverBlockedByEdit(this._getProductHoverRecord(row))) {
            return;
        }
        debugInfo("[sale_product_hover] hover row", row.dataset.id);
        this._productHoverRowEl = row;
        this._scheduleProductHoverOpen(row);
    },

    _onProductHoverMouseOut(ev) {
        if (this._productHoverTouchActive) {
            return;
        }
        const row = ev.target?.closest?.(ROW_SELECTOR);
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

    /**
     * 拦掉行内元素的原生 tooltip。
     *
     * Odoo 的 tooltip 服务同样挂在**捕获阶段**（`document.body` 上的 `mouseenter`），
     * 元素上的 `data-tooltip`（单元格里常见，延迟 1000ms 弹出）会和我们的浮层同时出现。
     * 在更外层的 `document` 捕获阶段先收下这个事件：只要当前行确实有我们自己的浮层数据，
     * 就 `stopPropagation()`，tooltip 服务便收不到 `mouseenter`，那层黑色小提示不会再弹。
     * 只在"我们自己会弹浮层"的行上拦截，其余元素 / 行不受影响。
     */
    _onProductHoverMouseEnter(ev) {
        if (this._productHoverTouchActive) {
            return;
        }
        const row = this._getProductHoverRowFromEvent(ev);
        if (!row || !this._isProductHoverCardReady(row)) {
            return;
        }
        ev.stopPropagation();
    },

    /** 该行是否确实有可展示的浮层数据（无产品 / 分节行 / 尚未预取到为假）。 */
    _isProductHoverCardReady(row) {
        const record = this._getProductHoverRecord(row);
        if (!record || this._isProductHoverBlockedByEdit(record)) {
            return false;
        }
        return Boolean(getLineHoverPayload(this._getProductHoverKey(record)));
    },

    // ------------------------------------------------------------------
    // 跟随鼠标：浮层贴在光标右下，越界时翻到左上 / 贴边
    // ------------------------------------------------------------------
    _onProductHoverMouseMove(ev) {
        if (this._productHoverTouchActive || !this._productHoverRowEl) {
            return;
        }
        if (!this._productHoverPopover.isOpen) {
            return;
        }
        const el = getPopoverForTarget(this._productHoverRowEl);
        // 指针已进入浮层内部：停止跟随，让它停在原地方便阅读
        if (el && el.contains(ev.target)) {
            return;
        }
        this._productHoverPointer = { x: ev.clientX, y: ev.clientY };
        this._scheduleProductHoverFollow();
    },

    _scheduleProductHoverFollow() {
        if (this._productHoverFollowFrame) {
            return;
        }
        // 用 rAF 合帧：mousemove 频率远高于屏幕刷新率，且定位里要读 getBoundingClientRect
        this._productHoverFollowFrame = browser.requestAnimationFrame(() => {
            this._productHoverFollowFrame = null;
            this._positionProductHover(this._productHoverPointer);
        });
    },

    /**
     * 把浮层摆到光标附近（`position: fixed`，故 `left/top` 即视口坐标）。
     *
     * `el` 可传入已知的浮层元素；不传则按当前行反查。空间不足时依次退让：
     * 先翻到光标左侧，再贴下边界；浮层比视口还高时自己收紧 `maxHeight`。
     */
    _positionProductHover(pointer, el) {
        if (!pointer) {
            return;
        }
        const popoverEl = el || (this._productHoverRowEl && getPopoverForTarget(this._productHoverRowEl));
        if (!popoverEl) {
            return;
        }
        // Odoo 在空间不足时会写 maxHeight / overflowY（而且是 min() 叠加），
        // 浮层位置既然由我们接管，就清掉这两项，避免尺寸被历史值压住
        popoverEl.style.maxHeight = "";
        popoverEl.style.overflowY = "";
        const { width, height } = popoverEl.getBoundingClientRect();
        const maxX = window.innerWidth - VIEWPORT_MARGIN;
        const maxY = window.innerHeight - VIEWPORT_MARGIN;
        let left = pointer.x + POINTER_OFFSET_X;
        let top = pointer.y + POINTER_OFFSET_Y;
        if (left + width > maxX) {
            // 右侧放不下：翻到光标左侧（仍放不下则贴左边）
            left = Math.max(VIEWPORT_MARGIN, pointer.x - POINTER_OFFSET_X - width);
        }
        if (top + height > maxY) {
            // 下方放不下：上移贴住下边界；连视口都装不下时收紧自身高度并允许内部滚动
            top = Math.max(VIEWPORT_MARGIN, maxY - height);
            const available = window.innerHeight - 2 * VIEWPORT_MARGIN;
            if (height > available) {
                popoverEl.style.maxHeight = `${available}px`;
                popoverEl.style.overflowY = "auto";
                top = VIEWPORT_MARGIN;
            }
        }
        popoverEl.style.left = `${left}px`;
        popoverEl.style.top = `${top}px`;
    },

    _cancelProductHoverFollow() {
        if (this._productHoverFollowFrame) {
            browser.cancelAnimationFrame(this._productHoverFollowFrame);
            this._productHoverFollowFrame = null;
        }
        this._clearProductHoverTimers();
    },

    // ------------------------------------------------------------------
    // 触屏：没有 hover，用长按代替（不阻止默认行为，不影响滚动与原有点击）
    // ------------------------------------------------------------------
    _onProductHoverTouchStart(ev) {
        this._productHoverTouchActive = true;
        clearTimeout(this._productHoverTouchGraceTimer);
        this._clearProductHoverTouchTimer();
        const row = this._getProductHoverRowFromEvent(ev);
        if (!row || this._isProductHoverBlockedByEdit(this._getProductHoverRecord(row))) {
            return;
        }
        if (this._productHoverRowEl === row && this._productHoverPopover.isOpen) {
            return;
        }
        const touch = ev.touches?.[0];
        this._productHoverTouchOrigin = touch
            ? { x: touch.clientX, y: touch.clientY }
            : null;
        // 触屏没有 mousemove，浮层就停在手指位置（越界时由 _positionProductHover 收敛）
        if (touch) {
            this._productHoverPointer = { x: touch.clientX, y: touch.clientY };
        }
        this._productHoverTouchTimer = setTimeout(() => {
            this._productHoverTouchTimer = null;
            // 该点按会紧接着触发一次 click（打开记录），这里把它吃掉
            this._suppressNextProductHoverClick();
            this._productHoverRowEl = row;
            this._openProductHover(row);
        }, TOUCH_OPEN_DELAY);
    },

    _onProductHoverTouchMove(ev) {
        if (!this._productHoverTouchTimer) {
            return;
        }
        const touch = ev.touches?.[0];
        const origin = this._productHoverTouchOrigin;
        if (
            touch &&
            origin &&
            (Math.abs(touch.clientX - origin.x) > TOUCH_MOVE_TOLERANCE ||
                Math.abs(touch.clientY - origin.y) > TOUCH_MOVE_TOLERANCE)
        ) {
            // 用户在滚动列表，不是长按
            this._clearProductHoverTouchTimer();
        }
    },

    _onProductHoverTouchEnd() {
        this._clearProductHoverTouchTimer();
        // 手势刚结束时浏览器会补发 mouseover / mouseout，短时间内忽略它们；
        // 浮层本身留给 popover 的「点击别处关闭」逻辑处理，便于阅读。
        clearTimeout(this._productHoverTouchGraceTimer);
        this._productHoverTouchGraceTimer = setTimeout(() => {
            this._productHoverTouchGraceTimer = null;
            this._productHoverTouchActive = false;
        }, TOUCH_MOUSE_GRACE);
    },

    /** 吃掉紧随长按之后的那次 click，避免"弹出浮层"的同时又打开记录。 */
    _suppressNextProductHoverClick() {
        const suppressor = (ev) => {
            document.removeEventListener("click", suppressor, CAPTURE);
            ev.stopPropagation();
            ev.preventDefault();
        };
        document.addEventListener("click", suppressor, CAPTURE);
        // 兜底：某些浏览器长按后不派发 click，超时自行移除
        setTimeout(
            () => document.removeEventListener("click", suppressor, CAPTURE),
            TOUCH_OPEN_DELAY + 200
        );
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

    /** 延迟结束且指针仍在行上时，取缓存数据打开浮层；缓存缺失则补一次请求。 */
    async _openProductHover(row) {
        if (this._productHoverRowEl !== row) {
            return;
        }
        const record = this._getProductHoverRecord(row);
        if (!record) {
            return;
        }
        const key = this._getProductHoverKey(record);
        if (record.resId) {
            // 已保存行：按行 id 补一次（缓存里已有则完全不发请求）
            if (!getLineHoverPayload(key)) {
                await prefetchLineHoverPayload([record.resId]);
            }
        } else {
            // 未保存的新行：按当前取值重算签名——取值没变就是空操作（不发请求），
            // 变了才补一次，保证浮层里的数量 / 单价跟着刚输入的内容走
            const draft = this._getProductHoverDraft(record);
            if (!draft) {
                debugInfo("[sale_product_hover] skip: 新行还没选产品（或为分节 / 备注行）");
                return;
            }
            await prefetchDraftHoverPayload([draft]);
        }
        const payload = getLineHoverPayload(key);
        // 异步返回后需再次确认指针仍在同一行，且行元素仍在文档中
        if (!payload || this._productHoverRowEl !== row || !row.isConnected) {
            debugInfo(
                "[sale_product_hover] skip:",
                payload
                    ? "指针已移开"
                    : "接口没有返回这一行的数据（无产品 / 分节行 / 无权限 / 服务端未升级）",
                key
            );
            return;
        }
        const pointer = this._productHoverPointer;
        // 用 popover 服务展示（`open` 内部会先关掉上一个浮层，不会叠加实例）
        this._productHoverPopover.open(row, { payload, targetEl: row });
        // `open` 内部关闭旧浮层时会同步触发 onClose → `_resetProductHover`（会清掉当前行与光标），
        // 故这两项必须在 open 之后补回：
        // - 行状态丢失会让指针在同一行内移动时重新计时、浮层反复刷新；
        // - 光标丢失会让浮层挂载时的 `onPositioned` 无从定位，先闪在行旁边才跳到光标处。
        this._productHoverRowEl = row;
        this._productHoverPointer = pointer;
        debugInfo("[sale_product_hover] popover opened for line", key);
    },

    _clearProductHoverTouchTimer() {
        clearTimeout(this._productHoverTouchTimer);
        this._productHoverTouchTimer = null;
        this._productHoverTouchOrigin = null;
    },

    _clearProductHoverTimers() {
        clearTimeout(this._productHoverOpenTimer);
        clearTimeout(this._productHoverCloseTimer);
        this._productHoverOpenTimer = null;
        this._productHoverCloseTimer = null;
        this._clearProductHoverTouchTimer();
        // 注意：不清 `_productHoverTouchActive`。它表示"刚发生过触摸"，由 touchend 的
        // 宽限定时器复位；在这里复位会让触屏抬手后补发的 mouse 事件被当成悬停。
        clearTimeout(this._productHoverTouchGraceTimer);
        this._productHoverTouchGraceTimer = null;
    },

    /** 浮层关闭后清空当前行，使指针再次进入该行时能重新计时打开。 */
    _onProductHoverClosed() {
        debugInfo("[sale_product_hover] popover closed");
        this._resetProductHover();
    },

    _resetProductHover() {
        this._productHoverRowEl = null;
        this._productHoverPointer = null;
        if (this._productHoverFollowFrame) {
            browser.cancelAnimationFrame(this._productHoverFollowFrame);
            this._productHoverFollowFrame = null;
        }
    },
});
