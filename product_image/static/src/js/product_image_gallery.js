/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { imageUrl } from "@web/core/utils/urls";
import { isBinarySize } from "@web/core/utils/binary";
import { x2ManyCommands } from "@web/core/orm_service";
import { fileTypeMagicWordMap } from "@web/views/fields/image/image_field";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { registry } from "@web/core/registry";

import { Component, useState, useRef, useEffect } from "@odoo/owl";
import { ProductImagePreviewDialog } from "./product_image_preview";
import { useProductImageManage } from "./product_image_manage";

const placeholder = "/web/static/img/placeholder.png";

/**
 * 产品多图图库 widget
 *
 * 替换原生 image_1920 字段的 widget，在同一位置（头像区域）渲染多图浏览：
 * - 主图与图库解耦：产品主图 image_1920 由原生字段独立管理（列表 / 看板 / 报价单展示它），
 *   图库 product.image.gallery 只存补充图，不反向同步 / 不覆盖 / 不清空主图
 * - 展示序列：[原生主图（若有）] + [图库图片按 sequence 升序]，主图永远是第一张；
 *   「第一张即主图」——管理弹窗拖动排序可改变首位，从而更换主图（见 onManageReorder）
 * - 主图放大 2 倍显示（180x180），无上一张/下一张按钮、无序号
 * - 鼠标悬浮主图区：左侧优先（屏幕宽度不足转下方，下方仍不足按比例缩小）显示 540×540 放大窗（内含 1080×1080 图）
 * - 点击主图区弹出全屏预览弹窗（放大/缩小/旋转，见 product_image_preview.js）
 * - 缩略图竖向排列于主图右侧，仅用于选中/切换（编辑态不再放删除按钮）
 * - 缩略图总高超出主图高度时，顶部/底部出现上下滚动按钮
 * - 选中缩略图带一圈蓝色边框（border）
 * - 末端「新增图片」占位符（编辑态）：点击弹出「图片管理」弹窗
 *   （见 product_image_manage.js）——上半部分大图（仅预览）+ 平铺缩略图网格（每张缩略图
 *   含主图右上角 × 可删除：删图库图删记录、删主图自动提升图库首张；
 *   点击缩略图只切换弹窗内大图，不影响页面主图），
 *   下半部分上传 dropzone（点击/拖放/Ctrl+V；上传中即时显示缩略图与动画，
 *   粘贴后不自动关闭弹窗）
 * - 浏览切换为纯前端状态，不写库；管理弹窗内的删除/上传才写库
 *
 * 数据来源（按主记录模型分流，见 galleryField）：
 * - 主图：props.record 的 image_1920 字段（this.props.name）——product.template 为普通字段；
 *   product.product 为原生计算字段（无变体专属主图时回退模板主图），写入走原生 inverse
 * - 图库：product.template → image_gallery_ids；product.product → variant_image_gallery_ids
 *   （均为 One2many → product.image.gallery，两组数据相互独立）
 */
export class ProductImageGallery extends Component {
    static template = "product_image.ProductImageGallery";
    static components = { ProductImagePreviewDialog };
    static props = {
        ...standardFieldProps,
        acceptedFileExtensions: { type: String, optional: true },
        previewImage: { type: String, optional: true },
        convertToWebp: { type: Boolean, optional: true },
        enableZoom: { type: Boolean, optional: true },
        imgClass: { type: String, optional: true },
        zoomDelay: { type: Number, optional: true },
        alt: { type: String, optional: true },
        width: { type: Number, optional: true },
        height: { type: Number, optional: true },
        reload: { type: Boolean, optional: true },
    };
    static defaultProps = {
        acceptedFileExtensions: "image/*",
        alt: _t("Product Image"),
        imgClass: "",
        reload: true,
    };

    setup() {
        this.notification = useService("notification");
        this.orm = useService("orm");
        // 图片管理弹窗走顶层 main_components 注册表（与 gallery 渲染树解耦，避免重渲染闪烁）
        this.manage = useProductImageManage();
        this.state = useState({
            currentIndex: 0,
            hoverZoom: false,
            hoverSide: "left", // "left" | "below"
            hoverLeft: 0,
            hoverTop: 0,
            // 局部放大窗口实际尺寸（540 或按屏幕缩小后的值）与图片尺寸（1080 固定）
            hoverWin: 540,
            hoverImg: 1080,
            // 1080 图片在窗口内的平移量（px），使鼠标点居中
            zoomTx: 0,
            zoomTy: 0,
            previewOpen: false,
            // 缩略图滚动状态
            thumbCanScrollUp: false,
            thumbCanScrollDown: false,
            // 局部放大指示方块（鼠标所在区域，蓝色半透明）
            indLeft: 0,
            indTop: 0,
            indW: 0,
            indH: 0,
        });
        this.mainRef = useRef("main");
        this.mainImgRef = useRef("mainImg");
        this.thumbScrollRef = useRef("thumbScroll");

        // 展示序列变化或选中项变化后重算缩略图溢出与索引边界
        useEffect(() => {
            this._updateThumbOverflow();
            this._clampIndex();
        }, () => [this.displayItems.length, this.state.currentIndex]);
    }

    // ------------------------------------------------------------------
    // 原生主图值
    // ------------------------------------------------------------------

    /** 原生主图字段（image_1920）当前值，为空表示无主图。 */
    get mainFieldValue() {
        return this.props.record.data[this.props.name];
    }

    get hasMainImage() {
        return Boolean(this.mainFieldValue);
    }

    // ------------------------------------------------------------------
    // 图库数据访问
    // ------------------------------------------------------------------

    /**
     * 图库 One2many 字段名（按主记录模型分流）：
     * - product.template → image_gallery_ids（模板共享补充图，模板表单维护）
     * - product.product  → variant_image_gallery_ids（变体专属补充图，在变体编辑表单维护，
     *   与模板共享补充图完全独立；该字段在变体视图 arch 中以不可见 One2many 声明以提供
     *   activeFields 元数据，供本 widget 读取与新建图库记录）
     */
    get galleryField() {
        return this.props.record.resModel === "product.product"
            ? "variant_image_gallery_ids"
            : "image_gallery_ids";
    }

    get galleryList() {
        return this.props.record.data[this.galleryField];
    }

    /**
     * 图库所有图片记录（按 sequence/id 升序，与后端 _order 一致）。
     */
    get galleryRecords() {
        const list = this.galleryList;
        if (!list || !list.records) {
            return [];
        }
        return [...list.records].sort((a, b) => {
            const sa = a.data.sequence ?? 10;
            const sb = b.data.sequence ?? 10;
            if (sa !== sb) return sa - sb;
            return (a.resId || a.id) - (b.resId || b.id);
        });
    }

    // ------------------------------------------------------------------
    // 展示序列：[原生主图] + [图库图片按序]
    // ------------------------------------------------------------------

    /**
     * 展示序列：原生主图（若有值）永远在第一项，其后为图库图片（按 sequence 升序）。
     * 每项结构：{ type: 'main'|'gallery', record, name }
     *   - main: record 为 product.template 主记录，操作写 image_1920 字段
     *   - gallery: record 为 product.image.gallery 记录，操作走 One2many
     */
    get displayItems() {
        const items = [];
        if (this.hasMainImage) {
            items.push({
                type: "main",
                record: this.props.record,
                name: _t("Main image"),
            });
        }
        for (const rec of this.galleryRecords) {
            items.push({
                type: "gallery",
                record: rec,
                name: rec.data.name || "",
            });
        }
        return items;
    }

    get hasItems() {
        return this.displayItems.length > 0;
    }

    get totalCount() {
        return this.displayItems.length;
    }

    get currentItem() {
        const items = this.displayItems;
        if (!items.length) {
            return null;
        }
        const idx = Math.min(this.state.currentIndex, items.length - 1);
        return items[idx] || null;
    }

    // ------------------------------------------------------------------
    // 图片 URL（复用原生 ImageField 的 URL 生成逻辑）
    // ------------------------------------------------------------------

    /**
     * 生成图片 URL。
     *
     * record 既可以是图库记录（product.image.gallery），也可以是主记录
     *（product.template）——后者用于展示原生主图。
     * 对未保存的新记录或相关尺寸字段为空时回退到 image_1920 源数据（base64 data URL），
     * 保证刚上传的图片在保存前也能预览。已保存记录优先用请求字段以节省带宽。
     */
    getUrl(record, fieldName) {
        if (!record) {
            return placeholder;
        }
        let data = record.data[fieldName];
        if (!data && fieldName !== "image_1920") {
            data = record.data.image_1920;
        }
        if (!data) {
            return placeholder;
        }
        if (!record.isNew && isBinarySize(data) && record.resId) {
            const urlField =
                fieldName === "image_1920" || !record.data[fieldName] ? "image_1920" : fieldName;
            return imageUrl(record.resModel || "product.image.gallery", record.resId, urlField, {
                unique: record.data.write_date,
            });
        }
        const magic = fileTypeMagicWordMap[data[0]] || "png";
        return `data:image/${magic};base64,${data}`;
    }

    /** 统一取展示项的图片 URL（主图项与图库项都走同一逻辑）。 */
    getItemUrl(item, fieldName) {
        if (!item) {
            return placeholder;
        }
        // 主图项：始终用主图字段（image_1920），忽略请求的尺寸字段；
        // product.template 继承 image.mixin，image_1024/128 为 related，可正常取
        if (item.type === "main") {
            return this.getUrl(item.record, this.props.name);
        }
        return this.getUrl(item.record, fieldName);
    }

    /** 主图区大图：优先 image_1024（180px 显示足够，比 image_128 清晰），回退 image_1920。 */
    get mainImageUrl() {
        return this.getItemUrl(this.currentItem, "image_1024");
    }

    /** 悬浮放大 / 预览弹窗：用 image_1920 源数据，最大化清晰度。 */
    get fullImageUrl() {
        return this.getItemUrl(this.currentItem, "image_1920");
    }

    /** 缩略图 URL：用 image_128。 */
    getThumbUrl(item) {
        return this.getItemUrl(item, "image_128");
    }

    get currentName() {
        return this.currentItem?.name || "";
    }

    // ------------------------------------------------------------------
    // 选择展示项（纯前端状态，不写库）
    // ------------------------------------------------------------------

    onSelectItem(index) {
        if (index < 0 || index >= this.displayItems.length) {
            return;
        }
        this.state.currentIndex = index;
    }

    _clampIndex() {
        const total = this.displayItems.length;
        if (total === 0) {
            this.state.currentIndex = 0;
        } else if (this.state.currentIndex >= total) {
            this.state.currentIndex = total - 1;
        } else if (this.state.currentIndex < 0) {
            this.state.currentIndex = 0;
        }
    }

    // ------------------------------------------------------------------
    // 悬浮放大
    // ------------------------------------------------------------------

    onHoverEnter(ev) {
        if (!this.hasItems) {
            return;
        }
        const el = this.mainRef.el;
        if (!el) {
            this.state.hoverZoom = true;
            return;
        }
        const rect = el.getBoundingClientRect();
        // 窗口 540（180 的 9 倍面积 / 3 倍边长）；图片 1080（180 的 36 倍面积 / 6 倍边长）
        const DESIRED = 540;
        const IMG = 1080;
        const gap = 8;
        const MIN = 160; // 缩小下限，避免过小失去预览意义
        let side, left, top, win;
        // 1. 左侧：主图左侧屏幕宽度足够 → 在左侧展示
        if (rect.left >= DESIRED + gap) {
            side = "left";
            win = DESIRED;
            left = rect.left - win - gap;
            // 垂直贴齐主图顶，超出屏幕底部则上移夹在屏内
            top = Math.max(0, Math.min(rect.top, window.innerHeight - win - gap));
        } else {
            // 2. 左侧宽度不足 → 在下方展示；下方宽度/高度仍不足 → 按比例缩小悬浮窗以适配屏幕
            side = "below";
            const availW = window.innerWidth - rect.left - gap;
            const availH = window.innerHeight - rect.bottom - gap;
            win = Math.max(MIN, Math.min(DESIRED, availW, availH));
            left = rect.left;
            top = rect.bottom + gap;
        }
        this.state.hoverSide = side;
        this.state.hoverLeft = Math.round(left);
        this.state.hoverTop = Math.round(top);
        this.state.hoverWin = Math.round(win);
        this.state.hoverImg = IMG;
        this.state.hoverZoom = true;
        // 进入时立即按鼠标位置初始化指示方块与放大区域（避免首次移动前方块在 0,0）
        if (ev) {
            this.onHoverMove(ev);
        }
    }

    onHoverLeave() {
        this.state.hoverZoom = false;
    }

    /**
     * 局部放大（放大镜）：
     * - 原图展示区 180×180，放大图 1080×1080，放大窗口 540×540（屏幕不足时按比例缩小）。
     * - 窗口内含 1080×1080 图片，鼠标在原图移动时同比例平移 1080 图片，
     *   使鼠标点居中显示在窗口（1080/win 倍局部放大，win=540 → 2 倍）。
     * - 平移量夹在 [-(1080-win), 0]，使 1080 图片始终填满窗口（图片内容区之外为白色）。
     * - 蓝色指示方块 = 原图上被放大的区域，边长 = 原图宽 × (win/1080)，中心跟随鼠标，夹在原图内；
     *   win 缩小时方块同比例缩小，保持选框与预览内容对应关系准确。
     */
    onHoverMove(ev) {
        const box = this.mainRef.el;
        if (!box) {
            return;
        }
        const rect = box.getBoundingClientRect();
        const boxW = box.clientWidth || rect.width;
        const boxH = box.clientHeight || rect.height;
        // 鼠标相对原图展示区域的位置（0..1），同比例映射到 1080 图片
        let fx = boxW > 0 ? (ev.clientX - rect.left) / boxW : 0.5;
        let fy = boxH > 0 ? (ev.clientY - rect.top) / boxH : 0.5;
        fx = Math.max(0, Math.min(1, fx));
        fy = Math.max(0, Math.min(1, fy));
        const IMG = this.state.hoverImg || 1080;
        const WIN = this.state.hoverWin || 540;
        // 1080 图片在 win 窗口内平移：使鼠标点 (fx*IMG, fy*IMG) 居中于窗口 (WIN/2)
        const tx = Math.max(-(IMG - WIN), Math.min(0, WIN / 2 - fx * IMG));
        const ty = Math.max(-(IMG - WIN), Math.min(0, WIN / 2 - fy * IMG));
        this.state.zoomTx = Math.round(tx);
        this.state.zoomTy = Math.round(ty);
        // 蓝色指示方块（在原图上）：边长 = 原图宽 × (窗口/图片)，按窗口与图片实际比例动态调整，
        // 中心跟随鼠标，夹在原图内
        const indSide = (boxW * WIN) / IMG;
        const indLeft = Math.max(0, Math.min(boxW - indSide, fx * boxW - indSide / 2));
        const indTop = Math.max(0, Math.min(boxH - indSide, fy * boxH - indSide / 2));
        this.state.indLeft = Math.round(indLeft);
        this.state.indTop = Math.round(indTop);
        this.state.indW = Math.round(indSide);
        this.state.indH = Math.round(indSide);
    }

    /** 放大窗口样式：win×win（540 或缩小后），固定定位，溢出隐藏（1080 图片超出部分裁切）。 */
    get hoverStyle() {
        const win = this.state.hoverWin || 540;
        return (
            `position: fixed; left: ${this.state.hoverLeft}px; top: ${this.state.hoverTop}px; ` +
            `width: ${win}px; height: ${win}px; z-index: 1080; pointer-events: none; ` +
            `overflow: hidden; background: #fff;`
        );
    }

    /** 1080×1080 图片样式：绝对定位 + transform 平移，使鼠标点居中于窗口。 */
    get zoomImgStyle() {
        const img = this.state.hoverImg || 1080;
        return (
            `position: absolute; left: 0; top: 0; width: ${img}px; height: ${img}px; ` +
            `object-fit: contain; transform: translate(${this.state.zoomTx}px, ${this.state.zoomTy}px);`
        );
    }

    /** 蓝色半透明指示方块（标示主图上实际被放大的区域）。 */
    get indicatorStyle() {
        return (
            `position: absolute; left: ${this.state.indLeft}px; top: ${this.state.indTop}px; ` +
            `width: ${this.state.indW}px; height: ${this.state.indH}px; ` +
            `background: rgba(13, 110, 253, 0.25); border: 1px solid rgba(13, 110, 253, 0.9); ` +
            `pointer-events: none; z-index: 3;`
        );
    }

    // ------------------------------------------------------------------
    // 点击主图区 → 弹出预览
    // ------------------------------------------------------------------

    onMainClick() {
        if (!this.hasItems) {
            return;
        }
        this.state.hoverZoom = false;
        this.state.previewOpen = true;
    }

    closePreview() {
        this.state.previewOpen = false;
    }

    /** 预览弹窗的图片列表：所有展示项的 image_1920 全图 + 名称。 */
    get previewImages() {
        return this.displayItems.map((item) => ({
            url: this.getItemUrl(item, "image_1920"),
            name: item.name || "",
        }));
    }

    // ------------------------------------------------------------------
    // 图片管理弹窗：点击「新增图片」按钮打开（顶层 overlay，与 gallery 渲染树解耦）
    // 上半部分：大图（仅预览）+ 平铺缩略图（每张缩略图含主图右上角 × 可删）；下半部分：上传 dropzone
    // ------------------------------------------------------------------

    /**
     * 管理弹窗用的展示列表快照：与 displayItems 顺序一致，供弹窗渲染。
     * key 用于弹窗内按项删除（防删除后索引漂移删错图）。
     * 弹窗内的「选中切换」是弹窗自身的展示状态，不回传本 widget；
     * 仅删除 / 上传（写记录）后经 getItems() 重新拉取快照同步。
     */
    get manageItems() {
        return this.displayItems.map((item) => ({
            type: item.type,
            key: this._itemKey(item),
            name: item.name,
            thumbUrl: this.getItemUrl(item, "image_128"),
            bigUrl: this.getItemUrl(item, "image_1024"),
        }));
    }

    /** 展示项稳定 key：主图固定 'main'，图库图为 g<记录 id>（与缩略图展示项一一对应）。 */
    _itemKey(item) {
        return item.type === "main" ? "main" : `g${item.record.resId || item.record.id}`;
    }

    /** 页面当前展示项的稳定 key：上传等写记录操作后按 key 重新锚定，保持页面大图不变。 */
    get currentItemKey() {
        const items = this.displayItems;
        if (!items.length) {
            return null;
        }
        const idx = Math.min(this.state.currentIndex, items.length - 1);
        return this._itemKey(items[idx]);
    }

    openManageModal() {
        if (this.props.readonly) {
            return;
        }
        this.manage.open({
            acceptedFileExtensions: this.props.acceptedFileExtensions,
            initialIndex: this.state.currentIndex,
            getItems: () => this.manageItems,
            // 弹窗内的缩略图切换只影响弹窗自身大图预览，不回传本 widget；
            // 删除 / 上传为记录操作，走下方 onDelete / onUploaded；
            // 拖动排序（写回图库 sequence）走 onReorder
            onDelete: (type, key) => this.onManageDelete(type, key),
            onReorder: (keys) => this.onManageReorder(keys),
            onUploaded: (info) => this.onFileUploaded(info),
        });
    }

    /**
     * 管理弹窗内的删除：按 type/key 定位当前展示项。
     * key 相比索引更稳（删除后列表收缩，索引会漂移）。
     * main 分支：删除主图（图库非空时首张自动提升为新主图，见 onMainRemove）；
     * 其余为图库项：直接删除对应图库记录。
     */
    async onManageDelete(type, key) {
        if (type === "main") {
            await this.onMainRemove();
            return;
        }
        // key 形如 'g<resId>'（见 _itemKey / manageItems），解析出记录 id 再定位，
        // 避免删除列表后索引漂移（此前直接拿数字与 key 比较导致图库删除失效）
        const gid = this._gidFromKey(key);
        const items = this.displayItems;
        const index = items.findIndex(
            (it) =>
                it.type === "gallery" &&
                (it.record.resId || it.record.id) === gid
        );
        if (index < 0) {
            return;
        }
        await this.onGalleryRemove(index);
    }

    /**
     * 统一展示数组的稳定 key 序列（前端唯一的顺序来源，用于排序 diff）：
     * [主图 'main'（若有）] + [图库 'g<id>' 按 sequence 升序]，与 displayItems 一一对应。
     */
    get displayKeys() {
        return this.displayItems.map((item) => this._itemKey(item));
    }

    /**
     * 管理弹窗内拖动排序的写回入口：把「拖动后的统一数组顺序」落到后端。
     *
     * 前端把主图与图库视为**同一个数组**（顺序 = 数组下标），后端却是分开存的
     * （主图 = 产品 image_1920 字段，图库 = One2many 的 sequence），
     * 所以这里做的是「数组 diff → 分别写回」：
     *
     * 1. before = 当前统一数组 key 序列（displayKeys），after = 拖动后的新序列；
     * 2. 首位变化（有主图 且 after[0] !== 'main'）→ 说明换了主图：
     *    after[0] 那张图提升为主图，原主图按它在 after 中的下标落位为图库记录；
     *    仅在此时写 image_1920（见 _writeOrderWithNewMain）；
     * 3. 图库部分按 after 的顺序重排 sequence，且**只写位置真的变了**的记录
     *    （见 _writeGalleryOrder）。
     */
    async onManageReorder(after) {
        if (!Array.isArray(after) || after.length < 2) {
            return;
        }
        const before = this.displayKeys;
        if (before.length !== after.length) {
            return; // 期间发生过增删（并发操作），放弃本次排序避免错位
        }
        if (!this.galleryRecords.length) {
            return;
        }
        // 首位变化 = 更换主图（无主图时不凭空造主图，只重排图库）
        if (this.hasMainImage && after[0] !== "main") {
            await this._writeOrderWithNewMain(after);
            return;
        }
        await this._writeGalleryOrder(this._galleryKeysOf(after));
    }

    /** 从统一数组 key 序列中取出图库部分（去掉主图项 'main'）。 */
    _galleryKeysOf(keys) {
        return keys.filter((key) => key !== "main");
    }

    /**
     * 拖动后首位发生变化 → 更换主图：把 after[0] 那张图设为主图，
     * 原主图按它在新数组中的下标落位为图库记录（**移动**，不复制、不丢图）。
     *
     * 流程（顺序不能颠倒）：
     * 1. 读出「新主图」的 base64（已保存记录可能只持 binary size，需 ORM 读取）；
     * 2. 读出「原主图」的 base64——必须在覆盖主图字段之前，否则读不到原图；
     * 3. 原主图先落位为图库记录，再把新主图数据写入主图字段并删除其图库记录；
     * 4. 新图库顺序 = after 去掉首位、'main' 处换成新建的原主图记录，
     *    交给 _writeGalleryOrder 按 diff 写 sequence。
     */
    async _writeOrderWithNewMain(after) {
        const newMainGid = this._gidFromKey(after[0]);
        const newMainRec = this.galleryRecords.find((rec) => (rec.resId || rec.id) === newMainGid);
        if (!newMainRec) {
            return;
        }
        const newMainData = await this._readGalleryImageBase64(newMainRec);
        if (!newMainData) {
            this.notification.add(
                _t("The image data could not be read, the main image was not changed."),
                { type: "danger" }
            );
            return;
        }
        // 原主图数据必须在覆盖主图字段之前读取
        const oldMainData = await this._readMainImageBase64();
        if (!oldMainData) {
            this.notification.add(
                _t("The previous main image could not be read and was not kept in the gallery."),
                { type: "warning" }
            );
        }
        // 原主图落位为图库记录（先占位，稍后与其余图库项一起按新顺序写 sequence）
        const galleryList = this.galleryList;
        let oldMainRecord = null;
        if (oldMainData && galleryList) {
            oldMainRecord = await galleryList.addNewRecord(false);
            await oldMainRecord.update({ image_1920: oldMainData });
        }
        // 提升新主图：数据写入主图字段 + 删除其图库记录
        const command = newMainRec.isNew
            ? x2ManyCommands.unlink(newMainRec.id)
            : x2ManyCommands.delete(newMainRec.resId);
        await this.props.record.update({
            [this.props.name]: newMainData,
            [this.galleryField]: [command],
        });
        // 拖动后的新图库顺序：去掉已提升为主图的首位，'main' 处换成新建的原主图记录
        const galleryKeys = [];
        for (const key of after.slice(1)) {
            if (key === "main") {
                if (oldMainRecord) {
                    galleryKeys.push(`g${oldMainRecord.id}`);
                }
                continue; // 原主图读取失败时不占位，避免后续顺序错位
            }
            galleryKeys.push(key);
        }
        await this._writeGalleryOrder(galleryKeys);
        // 主图已更换：页面展示回到新的第一张
        this.state.currentIndex = 0;
        this._clampIndex();
        requestAnimationFrame(() => this._updateThumbOverflow());
    }

    /**
     * 按目标图库顺序写 sequence（diff 后最小写回）：
     * 逐项把「目标顺序」与记录当前 sequence 比对，**只有位置真的变了的记录才写**，
     * 未变动的记录不产生任何写操作（避免无谓的 dirty 与重排抖动）。
     * 步长为 10（与后端默认 10、追加末尾时 +10 一致，避免新增图默认 10 插到中间）。
     */
    async _writeGalleryOrder(galleryKeys) {
        // 目标：图库记录标识 → sequence（1..n 的顺序位 × 10）
        const targets = new Map();
        let seq = 0;
        for (const key of galleryKeys) {
            const gid = this._gidFromKey(key);
            if (gid === null) {
                continue;
            }
            seq += 10;
            targets.set(gid, seq);
        }
        if (!targets.size) {
            return;
        }
        // 差异项：当前 sequence 与目标不一致的记录（快照后再逐个写回）
        const changed = [];
        for (const rec of this.galleryRecords) {
            const id = rec.resId || rec.id;
            const next = targets.get(id);
            if (next !== undefined && (rec.data.sequence ?? 10) !== next) {
                changed.push([rec, next]);
            }
        }
        for (const [rec, next] of changed) {
            await rec.update({ sequence: next });
        }
    }

    /** 读取图库记录的图片 base64（已保存记录可能只有 binary size，需 ORM 读取）。 */
    async _readGalleryImageBase64(rec) {
        let data = rec.data.image_1920;
        if ((!data || isBinarySize(data)) && rec.resId && !rec.isNew) {
            try {
                const result = await this.orm.read("product.image.gallery", [rec.resId], [
                    "image_1920",
                ]);
                data = result[0]?.image_1920;
            } catch (_e) {
                data = false;
            }
        }
        return data || false;
    }

    /** 读取产品主图字段的 base64（同样可能只有 binary size，需 ORM 读取）。 */
    async _readMainImageBase64() {
        const record = this.props.record;
        let data = record.data[this.props.name];
        if ((!data || isBinarySize(data)) && record.resId) {
            try {
                const result = await this.orm.read(record.resModel, [record.resId], [
                    this.props.name,
                ]);
                data = result[0]?.[this.props.name];
            } catch (_e) {
                data = false;
            }
        }
        return data || false;
    }

    /**
     * 把弹窗 key（'g<id>'）解析为图库记录标识；非法返回 null。
     * - 已保存记录：数字 resId；
     * - 未保存记录（如原主图落位新建的图库项）：虚拟 id 字符串（如 virtual_1），
     *   原样返回，与 `record.resId || record.id` 严格相等比较即可命中。
     */
    _gidFromKey(key) {
        const s = String(key ?? "");
        if (!s.startsWith("g")) {
            return null;
        }
        const raw = s.slice(1);
        if (!raw) {
            return null;
        }
        const n = Number(raw);
        return Number.isFinite(n) ? n : raw;
    }

    // ------------------------------------------------------------------
    // 主图项删除（弹窗缩略图网格中主图项右上角 × 触发）
    // 删除主图时自动提升图库首张为主图；图库为空则清空主图字段
    // ------------------------------------------------------------------

    /**
     * 删除主图（弹窗主图缩略图右上角 × 触发）：图库非空时自动提升首张图库图为主图。
     *
     * 提升即「移动」：把图库首张图的图片数据写入主图字段（image_1920），
     * 并删除该图库记录——不复制、不重复展示。
     * 已保存图库记录的 image_1920 可能是 binary size（懒加载），需从服务端
     * ORM 读取真实 base64 后再写入主图，避免写入占位字符串。
     * 图库为空时直接清空主图字段。
     */
    async onMainRemove(ev) {
        ev?.stopPropagation?.();
        ev?.preventDefault?.();
        if (this.props.readonly) {
            return;
        }
        const gallery = this.galleryRecords;
        if (gallery.length) {
            const first = gallery[0];
            let imgData = first.data.image_1920;
            // 已保存记录的 image_1920 可能是 binary size（懒加载），读真实 base64
            if ((!imgData || isBinarySize(imgData)) && first.resId && !first.isNew) {
                try {
                    const result = await this.orm.read("product.image.gallery", [first.resId], ["image_1920"]);
                    imgData = result[0]?.image_1920;
                } catch (_e) {
                    imgData = false;
                }
            }
            if (imgData) {
                // 提升：图库首张图数据 → 主图字段，并删除该图库记录（移动，不重复）
                const command = first.isNew
                    ? x2ManyCommands.unlink(first.id)
                    : x2ManyCommands.delete(first.resId);
                await this.props.record.update({
                    [this.props.name]: imgData,
                    [this.galleryField]: [command],
                });
            } else {
                // 取不到图数据，降级为清空主图
                await this.props.record.update({ [this.props.name]: false });
            }
        } else {
            // 图库为空：直接清空主图
            await this.props.record.update({ [this.props.name]: false });
        }
        // 删除后新主图（提升的图库图或空）位于序列首位
        this.state.currentIndex = 0;
        this._clampIndex();
        requestAnimationFrame(() => this._updateThumbOverflow());
    }

    // ------------------------------------------------------------------
    // 图库项编辑：新增 / 删除图库记录
    // ------------------------------------------------------------------

    /**
     * 上传新增图片。
     *
     * 主图为空时，上传的图直接作为主图（写 image_1920 字段，位于序列首位）；
     * 主图已有值时，追加为图库记录（不影响主图）。
     * 即「列表第一位的图片默认为主图」：首张上传的图即主图。
     *
     * 上传只写记录、不切换页面展示（19.0.2.2.15 起，点击 / 拖放 / Ctrl+V 上传均不改变
     * 页面上当前显示的大图）：完成后按上传前展示项的稳定 key 重新锚定当前展示项。
     *
     * @returns {number|undefined} 新增项在展示序列中的索引（供管理弹窗高亮新图）。
     */
    async onFileUploaded(info) {
        const anchor = this.currentItemKey;
        let newIndex;
        if (!this.hasMainImage) {
            // 主图为空：上传图直接作为主图（写 image_1920 字段，位于序列首位）
            await this.props.record.update({ [this.props.name]: info.data });
            newIndex = 0;
        } else {
            const galleryList = this.galleryList;
            if (!galleryList) {
                this.notification.add(
                _t("The gallery is not available, no image can be added."),
                { type: "danger" }
            );
                return;
            }
            // 追加到序列末尾：取当前最大 sequence（默认 10）+10 写入，
            // 保证拖动重排（10/20/…）之后新上传仍排到末尾而非默认 10 插到中间
            let maxSeq = 10;
            for (const rec of this.galleryRecords) {
                maxSeq = Math.max(maxSeq, rec.data.sequence ?? 10);
            }
            const newRecord = await galleryList.addNewRecord(false);
            await newRecord.update({ image_1920: info.data, sequence: maxSeq + 10 });
            // 新增的图库项位于序列末尾
            newIndex = this.displayItems.length - 1;
        }
        this._keepShowing(anchor, newIndex);
        return newIndex;
    }

    /**
     * 上传完成后把页面展示恢复到上传前的那张图：按稳定 key 在最新展示序列中定位
     * （主图为空上传会把新主图前插到首位，原图库项索引后移，用 key 才能找到同一张图）；
     * 锚不存在（如上传前页面无图）时回退为展示新增项。
     */
    _keepShowing(anchor, newIndex) {
        if (anchor) {
            const idx = this.displayItems.findIndex((it) => this._itemKey(it) === anchor);
            if (idx >= 0) {
                this.state.currentIndex = idx;
                this._clampIndex();
                requestAnimationFrame(() => this._updateThumbOverflow());
                return;
            }
        }
        this.state.currentIndex = newIndex;
        this._clampIndex();
        requestAnimationFrame(() => this._updateThumbOverflow());
    }

    async onGalleryRemove(index, ev) {
        ev?.stopPropagation?.();
        ev?.preventDefault?.();
        if (this.props.readonly) {
            return;
        }
        const items = this.displayItems;
        const item = items[index];
        if (!item || item.type !== "gallery") {
            return;
        }
        const rec = item.record;
        const list = this.galleryList;
        if (!list) {
            return;
        }
        // 通过主 record 的 update + x2ManyCommands 删除图库记录
        const command = rec.isNew
            ? x2ManyCommands.unlink(rec.id) // (3, id) 移除关联
            : x2ManyCommands.delete(rec.resId); // (2, id) 删除已保存记录
        await this.props.record.update({
            [this.galleryField]: [command],
        });
        this._clampIndex();
        requestAnimationFrame(() => this._updateThumbOverflow());
    }

    // ------------------------------------------------------------------
    // 缩略图滚动：上下按钮
    // ------------------------------------------------------------------

    get thumbCanScrollUp() {
        return this.state.thumbCanScrollUp;
    }

    get thumbCanScrollDown() {
        return this.state.thumbCanScrollDown;
    }

    onThumbScrollUp() {
        const el = this.thumbScrollRef.el;
        if (!el) {
            return;
        }
        el.scrollBy({ top: -el.clientHeight * 0.8, behavior: "smooth" });
    }

    onThumbScrollDown() {
        const el = this.thumbScrollRef.el;
        if (!el) {
            return;
        }
        el.scrollBy({ top: el.clientHeight * 0.8, behavior: "smooth" });
    }

    onThumbScroll() {
        this._updateThumbOverflow();
    }

    _updateThumbOverflow() {
        const el = this.thumbScrollRef.el;
        if (!el) {
            this.state.thumbCanScrollUp = false;
            this.state.thumbCanScrollDown = false;
            return;
        }
        this.state.thumbCanScrollUp = el.scrollTop > 1;
        this.state.thumbCanScrollDown =
            el.scrollTop + el.clientHeight < el.scrollHeight - 1;
    }

    // ------------------------------------------------------------------
    // 粘贴上传在「图片管理」弹窗（ProductImageManageDialog）下半部 dropzone：
    // 弹窗打开时焦点在弹窗上，Ctrl+V 可靠触发；头像区域不再直接粘贴
    // ------------------------------------------------------------------
}

// ------------------------------------------------------------------
// 注册为字段 widget（registry key 保持 product_image_gallery，视图无需改动）
// ------------------------------------------------------------------

export const productImageGalleryField = {
    component: ProductImageGallery,
    displayName: _t("Product Images"),
    supportedAttributes: [
        { label: _t("Alternative text"), name: "alt", type: "string" },
    ],
    supportedOptions: [
        { label: _t("Reload"), name: "reload", type: "boolean", default: true },
        { label: _t("Enable zoom"), name: "zoom", type: "boolean" },
        { label: _t("Convert to webp"), name: "convert_to_webp", type: "boolean" },
        { label: _t("Zoom delay"), name: "zoom_delay", type: "number" },
        { label: _t("Accepted file extensions"), name: "accepted_file_extensions", type: "string" },
        {
            label: _t("Size"),
            name: "size",
            type: "selection",
            choices: [
                { label: _t("Small"), value: "[0,90]" },
                { label: _t("Medium"), value: "[0,180]" },
                { label: _t("Large"), value: "[0,270]" },
            ],
        },
        { label: _t("Preview image"), name: "preview_image", type: "field", availableTypes: ["binary"] },
    ],
    supportedTypes: ["binary"],
    // 图库 One2many（image_gallery_ids / variant_image_gallery_ids）由产品 / 变体视图 arch 里
    // 声明的 invisible One2many + 内嵌 <list> 提供子字段 activeFields 并加载记录；
    // fieldDependencies 无法携带 one2many 的子字段，因此不在此声明图库字段（避免在
    // product.product 上产生无子字段的冗余依赖），只保留 write_date。
    fieldDependencies: [{ name: "write_date", type: "datetime" }],
    isEmpty: () => false,
    extractProps: ({ attrs, options }) => ({
        alt: attrs.alt,
        enableZoom: options.zoom,
        convertToWebp: options.convert_to_webp,
        imgClass: options.img_class || "",
        zoomDelay: options.zoom_delay,
        previewImage: options.preview_image,
        acceptedFileExtensions: options.accepted_file_extensions,
        width: options.size && Boolean(options.size[0]) ? options.size[0] : undefined,
        height: options.size && Boolean(options.size[1]) ? options.size[1] : undefined,
        reload: "reload" in options ? Boolean(options.reload) : true,
    }),
};

registry.category("fields").add("product_image_gallery", productImageGalleryField);
