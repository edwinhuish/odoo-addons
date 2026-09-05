/** @odoo-module **/

import { Component, onWillDestroy, useRef, useState } from "@odoo/owl";
import { useAutofocus, useService } from "@web/core/utils/hooks";
import { getDataURLFromFile } from "@web/core/utils/urls";
import { checkFileSize } from "@web/core/utils/files";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

// 缩略图排序几何常量（必须与 SCSS 中 tile 68px + gap 8px 一致）
const SORT_CELL = 76; // 单个网格单元：68（图块）+ 8（间距）
const SORT_TILE = 68;
const SORT_GAP = 8;
const DRAG_THRESHOLD = 4; // 判定为「拖动」的最小位移（px），防误触
const SNAP_DELAY = 160; // 松手后“落位”动画时长（ms），之后再提交排序

/**
 * 图片管理弹窗（编辑态点击「新增图片」后弹出）。
 *
 * - 上半部分：左侧大图预览（仅作预览，不提供删除按钮）+ 右侧平铺缩略图网格；
 *   布局固定：大图列宽 250（大图盒 250×250，名称行 / 提示行恒定行高）→ 切换任意
 *   图片（含有无图片）弹窗尺寸不变；缩略图网格占满剩余宽高（超高内部滚动）。
 * - 大图名称行：主图项留空不显示“主图”（行高用占位保持）；图库图显示名称。
 * - 缩略图拖动排序（主图固定首位不参与）：拖动时其余缩略图按位次平滑避让
 *   （transition transform），松手落位动画后写回图库 sequence；上传后仍追加末尾。
 * - 删除：任何删除（缩略图右上角 ×、批量删除）都先弹确认框（带图片缩略图，
 *   主图有自动提升提示）；批量删除在 modal-header 开启勾选模式逐张勾选。
 * - 下半部分：图片 dropzone（点击选择 / 拖放 / Ctrl+V），上传队列逐张显示
 *   本地缩略图 + 转圈动画；Ctrl+V 粘贴上传完成后不自动关闭弹窗
 *
 * 数据同步：
 * - 弹窗不直接持有记录，通过 props 回调与 gallery widget 交互：
 *   · getItems()：取最新展示列表快照（增删后重新拉取，避免快照过期）
 *   · onDelete(type, key)：删除图库记录 / 主图（主图删除自动提升图库首张；按 key 定位）
 *   · onReorder(keys)：拖动排序后的最终展示序列（主图 key 恒为 'main' 且始终首位）
 *   · onUploaded(info)：写入主图或追加图库，返回新增项索引
 * - 以顶层 main_components overlay 挂载（与 gallery 渲染树解耦），
 *   避免 record.update 重渲染 gallery 时弹窗被重建 / 闪烁。
 */
export class ProductImageManageDialog extends Component {
    static template = "product_image.ProductImageManageDialog";
    static props = {
        acceptedFileExtensions: { type: String, optional: true },
        initialIndex: { type: Number, optional: true },
        getItems: Function, // () => [{ type, key, name, thumbUrl, bigUrl }]
        onDelete: Function, // async (type, key) => void 删除图库记录 / 主图（删主图自动提升）
        onReorder: { type: Function, optional: true }, // async (keys) => void 拖动排序持久化
        onUploaded: Function, // async (info) => number 返回新增项索引
        close: Function,
    };

    setup() {
        useAutofocus();
        this.notification = useService("notification");
        this.fileInputRef = useRef("fileInput");
        this.gridRef = useRef("grid");
        this._uploadSeq = 1;
        // 删除/上传防重标记：防止快速连点同一删除按钮造成重复操作
        this._busy = false;
        const items = this.props.getItems() || [];
        this.state = useState({
            items,
            selected: this._clamp(this.props.initialIndex || 0, items.length),
            dragging: false,
            // 上传队列：{ key, name, objectUrl }，本地缩略图预览 + 转圈动画
            queue: [],
            // 缩略图拖动排序：{ key, from, hole, cols, floatX, floatY, spacerH }
            drag: null,
            // 批量删除勾选模式
            selectMode: false,
            checkedKeys: [],
            // 删除确认框：{ title, message, items, confirmLabel, action }
            confirm: null,
            confirmBusy: false,
        });
        // 拖动排序运行时数据（不参与渲染）
        this._sort = null;
        this._sortCleanup = null;
        this._snapTimer = null;
        // 拖动结束后吞掉紧随其后的合成 click（防止落位瞬间误切选中）；事件链结束后复位
        this._suppressClick = false;
        this._clickGuardTimer = null;
    }

    // ------------------------------------------------------------------
    // 数据访问
    // ------------------------------------------------------------------

    /** 展示列表（模板中 items 即指这里；必须提供 getter，否则模板 items.length 读到 undefined）。 */
    get items() {
        return this.state.items;
    }

    get currentItem() {
        return this.state.items[this.state.selected] || null;
    }

    get currentName() {
        return this.currentItem?.name || "";
    }

    /** 大图名称行：仅图库图显示名称；主图项留空（不显示“主图”文字）。 */
    get showName() {
        return Boolean(this.currentItem && this.currentItem.type !== "main");
    }

    get hasMain() {
        return this.state.items[0]?.type === "main";
    }

    /** 批量勾选数量 / 勾选项。 */
    get checkedCount() {
        return this.state.checkedKeys.length;
    }

    get checkedItems() {
        return this.state.checkedKeys
            .map((k) => this.state.items.find((it) => it.key === k))
            .filter(Boolean);
    }

    _clamp(i, len) {
        if (!len) {
            return 0;
        }
        if (i < 0) {
            return 0;
        }
        return Math.min(i, len - 1);
    }

    /** 重新拉取最新列表快照并保持选中项稳定（按 key，其次 prefer 索引）。 */
    _reload({ prefer, key } = {}) {
        const items = this.props.getItems() || [];
        this.state.items = items;
        if (!items.length) {
            this.state.selected = 0;
            this._exitSelectMode();
            return;
        }
        let idx;
        if (key) {
            idx = items.findIndex((it) => it.key === key);
        }
        if (typeof idx !== "number" || idx < 0) {
            idx = typeof prefer === "number" ? prefer : this.state.selected;
        }
        this.state.selected = this._clamp(idx, items.length);
    }

    // ------------------------------------------------------------------
    // 选中：仅更新弹窗内大图预览，不回传 gallery（不影响页面主图）
    // ------------------------------------------------------------------

    /** 点击缩略图：正常模式切大图；勾选模式切换勾选并预览。拖动结束后忽略本次 click。 */
    onTileClick(i, ev) {
        if (!this.state.items[i]) {
            return;
        }
        if (this._suppressClick) {
            this._suppressClick = false;
            return;
        }
        if (this.state.selectMode) {
            this._toggleChecked(i);
        } else {
            this.selectItem(i);
        }
    }

    selectItem(i) {
        const n = this.state.items.length;
        if (i < 0 || i >= n || i === this.state.selected) {
            return;
        }
        this.state.selected = i;
    }

    // ------------------------------------------------------------------
    // 批量删除：header 勾选模式
    // ------------------------------------------------------------------

    enterSelectMode() {
        if (!this.state.items.length || this.state.selectMode) {
            return;
        }
        this.state.selectMode = true;
        this.state.checkedKeys = [];
    }

    _exitSelectMode() {
        this.state.selectMode = false;
        this.state.checkedKeys = [];
    }

    _toggleChecked(i) {
        const item = this.state.items[i];
        if (!item) {
            return;
        }
        this.state.selected = i; // 勾选同时预览该图，便于确认
        const keys = this.state.checkedKeys;
        const pos = keys.indexOf(item.key);
        if (pos >= 0) {
            keys.splice(pos, 1);
        } else {
            keys.push(item.key);
        }
    }

    /** header「批量删除」确认：把勾选项按“先图库、后主图”顺序逐一删除。 */
    requestBatchDelete() {
        const items = this.checkedItems;
        if (!items.length || this._busy) {
            return;
        }
        const hasMain = items.some((it) => it.type === "main");
        let message = _t("确定删除选中的 %s 张图片？操作不可撤销。").replace(
            "%s",
            String(items.length)
        );
        if (hasMain) {
            message += _t("包含主图：图库非空时图库首张将自动提升为新主图；图库为空则主图被清空。");
        }
        this._openConfirm({
            title: _t("批量删除图片"),
            message,
            items: [...items],
            confirmLabel: _t("删除 %s 张").replace("%s", String(items.length)),
            action: () => this._deleteEntries([...items]),
        });
    }

    // ------------------------------------------------------------------
    // 删除：右上角 × / 批量，统一走确认框（含缩略图），确认后调用 onDelete
    // ------------------------------------------------------------------

    /** 点击单张缩略图右上角 ×：先弹确认（含主图自动提升提示）。 */
    requestDelete(i) {
        const item = this.state.items[i];
        if (!item || this._busy || this.state.selectMode) {
            return;
        }
        if (item.type === "main") {
            this._openConfirm({
                title: _t("删除主图"),
                message: _t(
                    "将删除主图。图库非空时首张会自动提升为新主图；图库为空则主图被清空。"
                ),
                items: [item],
                confirmLabel: _t("删除主图"),
                action: () => this._deleteEntries([item]),
            });
        } else {
            this._openConfirm({
                title: _t("删除图片"),
                message: _t("删除后该图片将从产品图库中移除，操作不可撤销。"),
                items: [item],
                confirmLabel: _t("删除"),
                action: () => this._deleteEntries([item]),
            });
        }
    }

    /** 打开删除确认框（confirm 状态承载确认信息，正文含缩略图清单）。 */
    _openConfirm({ title, message, items, confirmLabel, action }) {
        this.state.confirm = {
            title,
            message,
            items: items.map((it) => ({
                type: it.type,
                key: it.key,
                name: it.name || "",
                thumbUrl: it.thumbUrl,
            })),
            confirmLabel,
            action,
        };
    }

    cancelConfirm() {
        if (this.state.confirmBusy) {
            return;
        }
        this.state.confirm = null;
    }

    /** 确认框「确定」：取出 action 执行，执行期间禁止再点。 */
    async confirmDelete() {
        const confirm = this.state.confirm;
        if (!confirm || this.state.confirmBusy) {
            return;
        }
        this.state.confirmBusy = true;
        try {
            const action = confirm.action;
            this.state.confirm = null;
            if (action) {
                await action();
            }
        } finally {
            this.state.confirmBusy = false;
        }
    }

    /**
     * 真正执行删除：entries 按“先图库后主图”顺序删除（主图删除触发提升，
     * 若先删主图会把图库首张提升进主图、打乱后续图库 key 定位，故主图放最后）。
     * 每删一条都重拉快照，全部完成后退出勾选模式。
     */
    async _deleteEntries(entries) {
        if (!entries.length || this._busy) {
            return;
        }
        this._busy = true;
        const anchor = this.currentItem?.key;
        const galleryFirst = [
            ...entries.filter((it) => it.type !== "main"),
            ...entries.filter((it) => it.type === "main"),
        ];
        try {
            for (const it of galleryFirst) {
                try {
                    await this.props.onDelete(it.type, it.key);
                } catch (_e) {
                    this.notification.add(_t("删除“%s”失败，请重试。").replace("%s", it.name), {
                        type: "danger",
                    });
                }
                this._reload({ key: anchor });
            }
            this._exitSelectMode();
            this._reload({ key: anchor });
        } finally {
            this._busy = false;
        }
    }

    // ------------------------------------------------------------------
    // 缩略图拖动排序（主图固定首位不参与）
    // 拖动时把网格切到“绝对定位 + transform”布局：根据指针所在的插入位（hole）
    // 计算其余每张缩略图的目标单元并套 transform → CSS transition 形成避让动画；
    // 松手先把拖拽块 snap 到落位单元，动画结束再提交（写图库 sequence）并还原静态布局。
    // ------------------------------------------------------------------

    /** 是否具备排序条件：至少两张图库图可移动（主图固定、单张图库无意义）。 */
    _dragEnabled() {
        if (this.state.selectMode) {
            return false;
        }
        const galleryCount = this.state.items.filter((it) => it.type === "gallery").length;
        return galleryCount >= 2;
    }

    onSortPointerDown(i, ev) {
        if (!this._dragEnabled() || this.state.confirm) {
            return;
        }
        const item = this.state.items[i];
        if (!item || item.type === "main") {
            return; // 主图固定首位
        }
        if (ev.pointerType === "mouse" && ev.button !== 0) {
            return;
        }
        if (ev.target.closest?.(".o_gallery_manage-del, .o_gallery_manage-check")) {
            return;
        }
        ev.preventDefault();
        this._sort = {
            pointerId: ev.pointerId,
            from: i,
            moved: false,
            lastX: ev.clientX,
            lastY: ev.clientY,
        };
        window.addEventListener("pointermove", this._sortCleanup = (e) => this._onSortMove(e), {
            passive: false,
        });
        window.addEventListener("pointerup", this._onSortUp = (e) => this._onSortEnd(e, false));
        window.addEventListener("pointercancel", this._onSortCancel = (e) => this._onSortEnd(e, true));
    }

    /** 拖动中：更新拖拽块跟随指针、计算插入位并让其余缩略图避让；边缘自动滚动。 */
    _onSortMove(ev) {
        const sort = this._sort;
        if (!sort || ev.pointerId !== sort.pointerId) {
            return;
        }
        ev.preventDefault();
        const dx = ev.clientX - sort.lastX;
        const dy = ev.clientY - sort.lastY;
        sort.lastX = ev.clientX;
        sort.lastY = ev.clientY;
        if (!sort.moved) {
            if (Math.hypot(dx, dy) < DRAG_THRESHOLD) {
                return;
            }
            sort.moved = true;
            this._suppressClick = true; // 松手后合成的 click 由 onTileClick 吞掉，防误切选中
            const geo = this._sortGeo();
            this.state.drag = {
                key: this.state.items[sort.from].key,
                from: sort.from,
                hole: sort.from,
                cols: geo.cols,
                floatX: 0,
                floatY: 0,
                spacerH: geo.spacerH,
            };
        }
        const geo = this._sortGeo();
        // 边缘自动滚动（拖到网格上下边缘附近时）
        this._autoScroll(ev.clientY, geo);
        const rect = geo.grid.getBoundingClientRect();
        const contentX = ev.clientX - rect.left - geo.padL;
        const contentY = ev.clientY - rect.top - geo.padT + geo.grid.scrollTop;
        const n = this.state.items.length;
        let hole = this._holeFromPointer(contentX, contentY, geo.cols, n);
        if (this.hasMain && hole < 1) {
            hole = 1;
        }
        const drag = this.state.drag;
        const changed = drag.hole !== hole;
        drag.hole = hole;
        // 拖拽块跟随指针（中心对齐，夹在网格内容范围内）
        const availX = Math.max(0, geo.grid.clientWidth - geo.padL - geo.padR - SORT_TILE);
        const availY = Math.max(0, geo.spacerH - geo.padT - geo.padB - SORT_TILE);
        drag.floatX = this._clampVal(contentX - SORT_TILE / 2, 0, availX);
        drag.floatY = this._clampVal(contentY - SORT_TILE / 2, 0, availY);
        if (changed) {
            // hole 变化 → 重渲染其余缩略图（transform 过渡 = 避让动画）
            this.state.drag = { ...drag };
        }
    }

    _onSortEnd(ev, canceled) {
        const sort = this._sort;
        if (!sort || ev.pointerId !== sort.pointerId) {
            return;
        }
        this._detachSortListeners();
        if (canceled || !sort.moved) {
            this._suppressClick = false;
            this._sort = null;
            this.state.drag = null;
            return;
        }
        this._sort = null;
        // 合成 click 紧随 pointerup（同一输入事件链）派发，用宏任务复位抑制标志：
        // 同 tile 松手时 click 会先被 onTileClick 吞掉；跨 tile 松手则无 click，下个任务复位
        this._clickGuardTimer = setTimeout(() => {
            this._suppressClick = false;
            this._clickGuardTimer = null;
        }, 0);
        // 松手：先把拖拽块 snap 到落位单元，动画结束后提交
        const drag = this.state.drag;
        const cols = drag.cols;
        const cell = drag.hole;
        drag.floatX = (cell % cols) * SORT_CELL;
        drag.floatY = Math.floor(cell / cols) * SORT_CELL;
        this.state.drag = { ...drag };
        this._snapTimer = setTimeout(() => this._commitReorder(), SNAP_DELAY);
    }

    /** 提交排序：按落位 hole 重排本地列表并回调 onReorder 写图库 sequence。 */
    async _commitReorder() {
        this._snapTimer = null;
        const drag = this.state.drag;
        if (!drag) {
            return;
        }
        const { from, hole, key } = drag;
        this.state.drag = null;
        const anchor = this.currentItem?.key;
        const arr = [...this.state.items];
        const fromIdx = arr.findIndex((it) => it.key === key);
        const [moved] = arr.splice(fromIdx >= 0 ? fromIdx : from, 1);
        arr.splice(hole, 0, moved);
        const keys = arr.map((it) => it.key);
        this.state.items = arr;
        this._reselectByKey(anchor, hole);
        if (this.props.onReorder) {
            try {
                await this.props.onReorder(keys);
                this._reload({ key: anchor });
            } catch (_e) {
                this.notification.add(_t("保存排序失败，请重试。"), { type: "danger" });
                this._reload({ key: anchor });
            }
        }
    }

    _reselectByKey(key, fallback) {
        let idx = key ? this.state.items.findIndex((it) => it.key === key) : -1;
        if (idx < 0) {
            idx = fallback;
        }
        this.state.selected = this._clamp(idx, this.state.items.length);
    }

    /** 计算当前网格几何信息（列数 / 内边距 / 占位高度）。 */
    _sortGeo() {
        const grid = this.gridRef.el;
        const cs = getComputedStyle(grid);
        const padL = parseFloat(cs.paddingLeft) || 0;
        const padR = parseFloat(cs.paddingRight) || 0;
        const padT = parseFloat(cs.paddingTop) || 0;
        const padB = parseFloat(cs.paddingBottom) || 0;
        const cols = Math.max(
            1,
            Math.floor((grid.clientWidth - padL - padR + SORT_GAP) / SORT_CELL)
        );
        const n = this.state.items.length;
        const rows = Math.max(1, Math.ceil(n / cols));
        // 与原 flex 布局等高的内容占位高度（absolute 布局下保证可滚动到底）
        const spacerH = padT + padB + rows * SORT_CELL - SORT_GAP + 2;
        return { grid, cols, padL, padR, padT, padB, spacerH };
    }

    /** 指针所在位置对应的插入位（0..n-1，按行主序、末尾夹取）。 */
    _holeFromPointer(contentX, contentY, cols, n) {
        const maxCell = n - 1;
        const maxRow = Math.floor(maxCell / cols);
        const row = this._clampVal(Math.floor(contentY / SORT_CELL), 0, maxRow);
        const col = this._clampVal(Math.floor(contentX / SORT_CELL), 0, cols - 1);
        return Math.min(maxCell, row * cols + col);
    }

    /** 拖到网格上/下边缘附近时自动滚动，保证可拖到末尾。 */
    _autoScroll(clientY, geo) {
        const rect = geo.grid.getBoundingClientRect();
        const EDGE = 28;
        const STEP = 14;
        if (clientY < rect.top + EDGE && geo.grid.scrollTop > 0) {
            geo.grid.scrollTop = Math.max(0, geo.grid.scrollTop - STEP);
        } else if (clientY > rect.bottom - EDGE) {
            geo.grid.scrollTop = Math.min(
                geo.grid.scrollHeight - geo.grid.clientHeight,
                geo.grid.scrollTop + STEP
            );
        }
    }

    _detachSortListeners() {
        if (this._sortCleanup) {
            window.removeEventListener("pointermove", this._sortCleanup);
        }
        if (this._onSortUp) {
            window.removeEventListener("pointerup", this._onSortUp);
        }
        if (this._onSortCancel) {
            window.removeEventListener("pointercancel", this._onSortCancel);
        }
        this._sortCleanup = this._onSortUp = this._onSortCancel = null;
    }

    _clampVal(v, min, max) {
        return Math.max(min, Math.min(max, v));
    }

    /** 渲染用：缩略图附加 class（选中态 / 勾选态 / 可拖 / 正在拖动）。 */
    tileClasses(i) {
        const it = this.state.items[i];
        if (!it) {
            return "";
        }
        let c = "";
        if (i === this.state.selected) {
            c += " is-selected";
        }
        if (this.state.selectMode) {
            if (this.state.checkedKeys.includes(it.key)) {
                c += " is-checked";
            }
        } else if (this._dragEnabled() && it.type !== "main") {
            c += " o_gm-sortable";
        }
        if (this.state.drag && i === this.state.drag.from) {
            c += " o_gm-drag";
        }
        return c;
    }

    /** 渲染用：拖动排序时每张缩略图的 transform（非拖拽项按 hole 避让布局）。 */
    tileStyle(i) {
        const drag = this.state.drag;
        if (!drag) {
            return "";
        }
        const cols = drag.cols;
        let x, y;
        if (i === drag.from) {
            x = drag.floatX;
            y = drag.floatY;
        } else {
            // 移除拖拽项后按插入位 hole 重排：hole 之前的项原地、之后的项后移一位
            const r = i > drag.from ? i - 1 : i;
            const cell = r < drag.hole ? r : r + 1;
            x = (cell % cols) * SORT_CELL;
            y = Math.floor(cell / cols) * SORT_CELL;
        }
        return `transform: translate(${Math.round(x)}px, ${Math.round(y)}px);`;
    }

    // ------------------------------------------------------------------
    // 上传（下半部分 dropzone，点击选择 / 拖放 / Ctrl+V 汇总到 processFiles）
    // ------------------------------------------------------------------

    /** dropzone 点击 → 打开系统文件选择框。 */
    openPicker() {
        this.fileInputRef.el?.click();
    }

    /** 文件选择框回调：选完立即清空 value，允许再次选择同一文件。 */
    onFileInputChange(ev) {
        const files = [...(ev.target.files || [])];
        ev.target.value = null;
        this.processFiles(files);
    }

    onDragOver(ev) {
        ev.preventDefault();
        this.state.dragging = true;
    }

    onDragLeave(ev) {
        ev.preventDefault();
        this.state.dragging = false;
    }

    async onDrop(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this.state.dragging = false;
        const files = [...(ev.dataTransfer?.files || [])];
        if (files.length) {
            await this.processFiles(files);
        }
    }

    async onPaste(ev) {
        const files = extractImageFiles(ev);
        if (!files.length) {
            return; // 非图片，放行
        }
        ev.preventDefault();
        ev.stopPropagation();
        await this.processFiles(files);
        // 粘贴上传完成后不关闭弹窗（可连续粘贴多张 / 继续管理）
    }

    /**
     * 统一上传入口：过滤图片与大小 → 先全部入队（本地缩略图 + 动画即时可见），
     * 再逐张读 base64 调 onUploaded 写入，完成后出队并入网格高亮。
     */
    async processFiles(files) {
        if (this.state.confirm) {
            return; // 确认框打开时不接收新的上传
        }
        const images = [];
        for (const file of files) {
            if (!file.type.startsWith("image/")) {
                continue;
            }
            if (!checkFileSize(file.size, this.notification)) {
                continue;
            }
            images.push(file);
        }
        if (!images.length) {
            return;
        }
        // 先入队，立即渲染缩略图与上传动画
        const tasks = [];
        for (const file of images) {
            const entry = {
                key: `up${this._uploadSeq++}`,
                name: file.name,
                objectUrl: URL.createObjectURL(file),
            };
            this.state.queue.push(entry);
            tasks.push({ file, entry });
        }
        for (const { file, entry } of tasks) {
            let idx;
            try {
                const data = await getDataURLFromFile(file);
                const base64 = data.split(",")[1];
                if (!base64) {
                    this.notification.add(_t("图片读取失败，已跳过。"), { type: "danger" });
                } else {
                    idx = await this.props.onUploaded({
                        data: base64,
                        type: file.type,
                        name: file.name,
                    });
                }
            } catch (_e) {
                this.notification.add(_t("上传失败，请重试。"), { type: "danger" });
            } finally {
                this._dequeue(entry);
                this._reload({ prefer: typeof idx === "number" ? idx : undefined });
            }
        }
    }

    /** 从上传队列移除一项并撤销其本地 object URL。 */
    _dequeue(entry) {
        const i = this.state.queue.findIndex((q) => q.key === entry.key);
        if (i < 0) {
            return;
        }
        const [removed] = this.state.queue.splice(i, 1);
        if (removed?.objectUrl) {
            URL.revokeObjectURL(removed.objectUrl);
        }
    }

    // ------------------------------------------------------------------
    // 关闭
    // ------------------------------------------------------------------

    onKeydown(ev) {
        if (ev.key !== "Escape") {
            return;
        }
        if (this.state.confirm) {
            this.cancelConfirm();
        } else if (this.state.selectMode) {
            this._exitSelectMode();
        } else {
            this.close();
        }
    }

    close() {
        this.props.close();
    }

    onWillDestroy() {
        this._detachSortListeners();
        this._sort = null;
        if (this._snapTimer) {
            clearTimeout(this._snapTimer);
            this._snapTimer = null;
        }
        if (this._clickGuardTimer) {
            clearTimeout(this._clickGuardTimer);
            this._clickGuardTimer = null;
        }
        // 弹窗关闭时清理仍在队列中的本地预览 URL
        for (const q of this.state.queue) {
            if (q.objectUrl) {
                URL.revokeObjectURL(q.objectUrl);
            }
        }
    }
}

/**
 * 从剪贴板事件提取图片文件列表。
 */
function extractImageFiles(ev) {
    const files = [];
    const items = ev.clipboardData?.items;
    if (!items) {
        return files;
    }
    for (const item of items) {
        if (item.kind === "file" && item.type.startsWith("image/")) {
            const file = item.getAsFile();
            if (file) {
                files.push(file);
            }
        }
    }
    return files;
}

// ------------------------------------------------------------------
// 顶层 overlay 注册：把管理弹窗挂到 main_components（与原生 FileViewer 同模式），
// 与图库 widget 渲染树解耦——record.update 重渲染 gallery 时不再波及弹窗，
// 避免粘贴 / 连续上传处理过程中弹窗重渲染 / 重建导致的闪烁与“重新出现”。
// ------------------------------------------------------------------

let manageSeq = 1;

/**
 * 在 main_components 注册一个图片管理弹窗实例，返回 open/close。
 * open(props) 会先关闭已有实例再注册新的；close 从注册表移除。
 * props 不含 close（由本函数注入，移除自身）。
 */
export function useProductImageManage() {
    const compId = `product_image.manage${manageSeq++}`;
    function close() {
        registry.category("main_components").remove(compId);
    }
    function open(props) {
        close();
        registry.category("main_components").add(compId, {
            Component: ProductImageManageDialog,
            props: { ...props, close },
        });
    }
    onWillDestroy(close);
    return { open, close };
}
