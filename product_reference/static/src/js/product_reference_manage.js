/** @odoo-module **/

import { Component, onWillDestroy, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useAutofocus, useService } from "@web/core/utils/hooks";
import { x2ManyCommands } from "@web/core/orm_service";
import { _t } from "@web/core/l10n/translation";

// 参考号类型选项，与 product.reference.code.reference_type 的 selection 一一对应；
// 文案沿用 selection 标签的 msgid，中文由 i18n/zh_CN.po 提供（同一 msgid 多引用）。
const REFERENCE_TYPES = [
    ["customer", _t("Customer Reference")],
    ["factory", _t("Factory Reference")],
    ["alias", _t("Alias")],
];

// 排序步长，与后端 sequence 默认 10 保持一致
const SEQUENCE_STEP = 10;

/**
 * 额外参考号管理弹窗（点击 Reference 输入框右侧「+」按钮打开）。
 *
 * 设计要点：
 * - **保存语义与产品表单一致**：弹窗内的增删改直接作用在产品表单 record 的
 *   One2many 上（`record.update` / 子记录 `update` / x2many 命令），
 *   点产品表单「保存」才真正入库；未保存的新产品也能先加参考号。
 * - **顶层 overlay（main_components）**：与产品表单渲染树解耦，record 更新重渲染
 *   表单时弹窗不会被重建 / 闪烁（与 product_image 管理弹窗同一模式）。
 * - 弹窗不持有 Record 对象本身（避免响应式代理包裹 Odoo 的 Record），
 *   只保存行快照（key + 字段值），写操作前按 key 回查 List 里的子记录。
 * - 行 key：已保存记录 `id:<resId>`，未保存记录 `new:<virtual id>`，
 *   避免删除 / 新增后索引漂移导致改错行、删错行。
 */
export class ProductReferenceManageDialog extends Component {
    static template = "product_reference.ProductReferenceManageDialog";
    static props = {
        record: Object,
        linesField: { type: String, optional: true },
        close: Function,
    };

    setup() {
        useAutofocus();
        this.notification = useService("notification");
        this.state = useState({
            items: this._snapshot(),
            busy: false,
        });
    }

    // ------------------------------------------------------------------
    // 数据访问
    // ------------------------------------------------------------------

    get linesField() {
        return this.props.linesField || "reference_code_line_ids";
    }

    /** 产品表单 record 上的参考号 One2many 列表（未声明 / 未加载时为空）。 */
    get list() {
        return this.props.record.data[this.linesField] || null;
    }

    get records() {
        const list = this.list;
        if (!list || !list.records) {
            return [];
        }
        // 与后端 _order（sequence, product_tmpl_id, id）保持一致
        return [...list.records].sort((a, b) => {
            const sa = a.data.sequence ?? SEQUENCE_STEP;
            const sb = b.data.sequence ?? SEQUENCE_STEP;
            if (sa !== sb) {
                return sa - sb;
            }
            return (a.resId || a.id) - (b.resId || b.id);
        });
    }

    get typeOptions() {
        return REFERENCE_TYPES;
    }

    /** 行快照（不含 Record 实例，避免被响应式代理包裹）。 */
    _snapshot() {
        return this.records.map((rec) => ({
            key: rec.isNew ? `new:${rec.id}` : `id:${rec.resId}`,
            code: rec.data.reference_code || "",
            type: rec.data.reference_type || "customer",
            active: rec.data.active !== false,
            note: rec.data.note || "",
            sequence: rec.data.sequence ?? SEQUENCE_STEP,
        }));
    }

    refresh() {
        this.state.items = this._snapshot();
    }

    /** 按 key 回查子记录：优先已保存记录，其次未保存（虚拟 id）记录。 */
    _findRecord(key) {
        const [kind, raw] = String(key || "").split(":");
        return this.records.find((rec) => {
            if (kind === "new") {
                return rec.isNew && String(rec.id) === raw;
            }
            return !rec.isNew && String(rec.resId) === raw;
        });
    }

    // ------------------------------------------------------------------
    // 行操作（全部作用在产品表单 record 上，随产品保存）
    // ------------------------------------------------------------------

    /** 新增一行：在 One2many 末尾追加一条未保存记录并带上默认 sequence。 */
    async onAddLine() {
        const list = this.list;
        if (!list || this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            const rec = await list.addNewRecord({ position: "bottom" });
            if (!rec) {
                return;
            }
            let maxSeq = SEQUENCE_STEP;
            for (const line of this.records) {
                maxSeq = Math.max(maxSeq, line.data.sequence ?? SEQUENCE_STEP);
            }
            await rec.update({
                sequence: maxSeq + SEQUENCE_STEP,
                reference_code: "",
                reference_type: "customer",
                active: true,
            });
            this.refresh();
        } catch (_e) {
            this.notification.add(_t("The reference could not be added."), {
                type: "danger",
            });
        } finally {
            this.state.busy = false;
        }
    }

    /** 行字段修改（失焦 / 选择后提交，不逐字符写记录）。 */
    async onFieldChange(item, fieldName, value) {
        const rec = this._findRecord(item.key);
        if (!rec || this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            await rec.update({ [fieldName]: value });
            this.refresh();
        } catch (_e) {
            this.notification.add(_t("The reference could not be updated."), {
                type: "danger",
            });
        } finally {
            this.state.busy = false;
        }
    }

    /** 删除一行：未保存行用 unlink（移除关联），已保存行用 delete（删除记录）。 */
    async onDelete(item) {
        const rec = this._findRecord(item.key);
        if (!rec || this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            const command = rec.isNew
                ? x2ManyCommands.unlink(rec.id)
                : x2ManyCommands.delete(rec.resId);
            await this.props.record.update({ [this.linesField]: [command] });
            this.refresh();
        } catch (_e) {
            this.notification.add(_t("The reference could not be deleted."), {
                type: "danger",
            });
        } finally {
            this.state.busy = false;
        }
    }

    /**
     * 上下移动一行：按快照顺序重排 sequence（10 递增），只写位置真的变了的记录。
     * 与后端 _order 一致，保存后列表 / 弹窗顺序即最终顺序。
     */
    async onMove(index, offset) {
        const items = this.state.items;
        const target = index + offset;
        if (this.state.busy || index < 0 || target < 0 || target >= items.length) {
            return;
        }
        const reordered = [...items];
        const [moved] = reordered.splice(index, 1);
        reordered.splice(target, 0, moved);
        this.state.busy = true;
        try {
            let seq = 0;
            for (const item of reordered) {
                seq += SEQUENCE_STEP;
                const rec = this._findRecord(item.key);
                if (rec && (rec.data.sequence ?? SEQUENCE_STEP) !== seq) {
                    await rec.update({ sequence: seq });
                }
            }
            this.refresh();
        } catch (_e) {
            this.notification.add(_t("The references could not be reordered."), {
                type: "danger",
            });
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------------
    // 关闭（Esc / 遮罩 / 关闭按钮 / 完成按钮）
    // ------------------------------------------------------------------

    onKeydown(ev) {
        if (ev.key === "Escape") {
            ev.stopPropagation();
            this.props.close();
        }
    }

    close() {
        this.props.close();
    }
}

// ------------------------------------------------------------------
// 顶层 overlay 注册：与 product_image 管理弹窗同一模式，把弹窗挂到
// main_components，避免 record.update 重渲染表单时波及弹窗。
// ------------------------------------------------------------------

let manageSeq = 1;

export function useProductReferenceManage() {
    const compId = `product_reference.manage${manageSeq++}`;
    function close() {
        registry.category("main_components").remove(compId);
    }
    function open(props) {
        close();
        registry.category("main_components").add(compId, {
            Component: ProductReferenceManageDialog,
            props: { ...props, close },
        });
    }
    onWillDestroy(close);
    return { open, close };
}
