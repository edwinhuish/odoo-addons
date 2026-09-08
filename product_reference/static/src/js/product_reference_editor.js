/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { formatChar } from "@web/views/fields/formatters";
import { CharField } from "@web/views/fields/char/char_field";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { Component } from "@odoo/owl";
import { useProductReferenceManage } from "./product_reference_manage";

// 额外参考号的 One2many（挂在 product.template 上；product.product 通过
// _inherits 委托读取同一组行，因此两种表单共用同一个字段名）
const LINES_FIELD = "reference_code_line_ids";

/**
 * 产品 Reference 编辑器 widget（放在产品名称下方）。
 *
 * 组成（见 static/src/xml/product_reference_editor.xml）：
 * - 原生 Reference 输入框：直接复用 Odoo 原生 `CharField` 组件渲染 `default_code`，
 *   保持原生编辑体验（即时 dirty / 提交 / 校验一致），不自己实现一套输入逻辑
 * - 输入框内右端「+」按钮：打开额外参考号管理弹窗（见 product_reference_manage.js）
 * - 计数徽标：存在额外参考号时显示「+N」，悬停徽标弹出参考号清单 tooltip
 *   （tooltip 走 Odoo 原生 `data-tooltip-template` + `data-tooltip-info`）
 *
 * 只读态：只显示 Reference 文本与徽标 tooltip，不渲染输入框与「+」按钮。
 *
 * 多变体产品（仅 product.template）：模板级 Reference 由各变体各自维护，
 *   此时输入框换成「按变体维护」的提示文本，管理入口保留。
 */
export class ProductReferenceEditor extends Component {
    static template = "product_reference.ProductReferenceEditor";
    static components = { CharField };
    static props = {
        ...standardFieldProps,
        placeholder: { type: String, optional: true },
        linesField: { type: String, optional: true },
    };

    setup() {
        this.manage = useProductReferenceManage();
    }

    // ------------------------------------------------------------------
    // 数据
    // ------------------------------------------------------------------

    get linesField() {
        return this.props.linesField || LINES_FIELD;
    }

    get list() {
        return this.props.record.data[this.linesField] || null;
    }

    /** 额外参考号（按 sequence 升序，与后端 _order 一致）。 */
    get lines() {
        const list = this.list;
        if (!list || !list.records) {
            return [];
        }
        return [...list.records].sort((a, b) => {
            const sa = a.data.sequence ?? 10;
            const sb = b.data.sequence ?? 10;
            if (sa !== sb) {
                return sa - sb;
            }
            return (a.resId || a.id) - (b.resId || b.id);
        });
    }

    /** 徽标 / tooltip 只统计启用中的参考号。 */
    get activeLines() {
        return this.lines.filter((rec) => rec.data.active !== false);
    }

    get count() {
        return this.activeLines.length;
    }

    get codes() {
        return this.activeLines
            .map((rec) => rec.data.reference_code)
            .filter((code) => Boolean(code));
    }

    /** tooltip 数据必须是 JSON 字符串（tooltip 服务每次打开时解析，可随时刷新）。 */
    get tooltipInfo() {
        return JSON.stringify({ codes: this.codes });
    }

    get badgeLabel() {
        return `+${this.count}`;
    }

    get codeValue() {
        return formatChar(this.props.record.data[this.props.name], {}) || "";
    }

    /** 多变体模板：Reference 由各变体维护，模板侧不提供输入。 */
    get isMultiVariant() {
        const record = this.props.record;
        if (record.resModel !== "product.template") {
            return false;
        }
        return (record.data.product_variant_count || 0) > 1;
    }

    get multiVariantHint() {
        return _t("Managed on each variant");
    }

    get addLabel() {
        return _t("Add a reference");
    }

    // ------------------------------------------------------------------
    // 打开管理弹窗（只读态不提供写入口）
    // ------------------------------------------------------------------

    openManage() {
        if (this.props.readonly) {
            return;
        }
        this.manage.open({
            record: this.props.record,
            linesField: this.linesField,
        });
    }
}

export const productReferenceEditorField = {
    component: ProductReferenceEditor,
    displayName: _t("Product Reference"),
    supportedTypes: ["char"],
    // 参考号 One2many 必须声明为依赖：视图 arch 里 invisible="1" 的 x2many
    // 不会进入主记录的加载 spec，子记录与字段便不会随记录读取，
    // 徽标数量与 tooltip 清单会一直为空（与 product_image 图库同理）。
    fieldDependencies: (fieldNode) => [
        {
            name: (fieldNode && fieldNode.options && fieldNode.options.lines_field) || LINES_FIELD,
            type: "one2many",
        },
    ],
    isEmpty: () => false,
    extractProps: ({ options, placeholder }) => ({
        placeholder,
        linesField: (options && options.lines_field) || LINES_FIELD,
    }),
};

registry.category("fields").add("product_reference_editor", productReferenceEditorField);
