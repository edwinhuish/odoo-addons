/** @odoo-module **/

import { Component, onPatched, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { useRecordObserver } from "@web/model/relational_model/utils";
import { Record } from "@web/model/relational_model/record";
import { X2ManyField } from "@web/views/fields/x2many/x2many_field";
import { ListX2ManyField } from "@web/views/fields/x2many/list_x2many_field";

/**
 * 「属性 ↔ 变体」映射表 —— **以组合为行，选由哪条既有变体保留**。
 *
 * 用户在产品表单「属性与变体」页照常改属性；属性行下方这张表把「这次改动之后会存在的组合」
 * 逐行列出来（每个属性一列），每行的 **Variant** 下拉用来指定「这个组合由哪条既有变体继续保留」：
 *
 * - 留空 = 这个组合新建一条变体；
 * - 选一条既有变体 = 那条变体继续承载这个组合（它的库存、单据、价格都跟着走）；
 * - 选**「不生成变体」** = 这个组合不产出变体（本次不建）。它与「由既有变体保留」互斥：
 *   这一行上还挂着既有变体时选不了 —— 那等于要删掉一条带着库存与单据的变体
 *   （服务端还会再判一次，见 AGENTS.md → L1 约束 1）；
 * - 每条既有变体必须**恰好出现在一行**里：没有出现在任何一行的，会在上方提示「还有 N 条没被分配」，
 *   并且**阻止保存** —— 本模块绝不静默丢掉既有变体；
 * - 同一行不会有两条变体（组合是行，天然不重复）；选中的变体若原本在别的行，会自动从那一行让出来，
 *   所以「两条变体互换组合」只需点两下（先把 A 选到 B 的行，A 原来的行自动空出）。
 *
 * 「按需生成」（``dynamic``）的属性：它的列是**可改的下拉**（默认取本行原本那条变体带着的取值，
 * 没有就取第一个），用户改了就等于把这一行的组合改成那个取值 —— 这样**不会预建**它的其它取值
 * （``T-039``），既有的组合数也不会因为多一个按需属性而爆炸。
 *
 * 编辑期间**不问服务端**（见 AGENTS.md → L2 P4 陷阱 13）：挂载时取一次快照
 * （既有变体各自带的取值 + 已保存的属性行基线 + 各属性 / 取值的名称与生成方式），
 * 之后一切变化都用 ``readLocalChanges()``（本地 ``_getChanges()``，不走 mutex）+ 纯函数算；
 * 保存时才把映射随表单提交。
 */

/** 纯函数：还没被分配到任何组合的既有变体数（> 0 就不许保存）。 */
export function countUnassigned(rows) {
    return rows.filter((row) => row.unassigned).length;
}

/** 纯函数：many2one 的 id（``[id, label]``、record、数字都认）。 */
export function readMany2oneId(value) {
    if (Array.isArray(value)) {
        return value[0] || false;
    }
    if (typeof value === "number") {
        return value;
    }
    if (value && typeof value === "object") {
        return value.resId || value.id || false;
    }
    return false;
}

/**
 * 纯函数：把一个 m2m 字段的命令集应用到它当前的值上。
 *
 * ``[6, 0, ids]``（set）是替换；其余（``[4, id]`` 关联 / ``[3, id]`` 取消关联 / ``[5]`` 清空）
 * 是增量 —— 表单里勾一个取值时发的就是增量命令，直接当替换会把别的取值丢掉。
 */
export function applyValueCommands(current, commands) {
    const list = commands || [];
    if (list.some((command) => Array.isArray(command) && command[0] === 6)) {
        const set = list.find((command) => Array.isArray(command) && command[0] === 6);
        return [...(set[2] || [])];
    }
    const ids = [...(current || [])];
    for (const command of list) {
        if (!Array.isArray(command) || !command.length) {
            continue;
        }
        const [operation, first] = command;
        if (operation === 4 && !ids.includes(first)) {
            ids.push(first);
        } else if (operation === 3) {
            const index = ids.indexOf(first);
            if (index >= 0) {
                ids.splice(index, 1);
            }
        } else if (operation === 5) {
            ids.length = 0;
        }
    }
    return ids;
}

/**
 * 纯函数：把 ``record.getChanges()`` 的属性行命令合并到快照给的**已保存基线**上，
 * 得到表单「当前编辑态」的属性行：``[{id, attribute_id, value_ids}]``。
 *
 * 关键：新建行必须用 **Odoo 给的虚拟 id 原样记下来** —— 用户点 Add a line 之后，
 * 「选属性」「勾取值」是**后续命令**（``[1, 虚拟id, {...}]``），Odoo 用那个虚拟 id 定位这一行；
 * 自己另造一个 id 会让那些更新全部落空（见模块 AGENTS.md → L2 P4 陷阱 15）。
 */
export function mergeAttributeLines(baseline, commands) {
    const lines = (baseline || []).map((line) => ({
        id: line.id,
        attribute_id: line.attribute_id,
        value_ids: [...(line.value_ids || [])],
    }));
    for (const command of commands || []) {
        if (!Array.isArray(command) || !command.length) {
            continue;
        }
        const [operation, first, second] = command;
        if (operation === 0) {
            const vals = second || {};
            lines.push({
                id: first,
                attribute_id: readMany2oneId(vals.attribute_id),
                value_ids: applyValueCommands([], vals.value_ids),
            });
        } else if (operation === 1 && second) {
            let line = lines.find((item) => item.id === first);
            if (!line) {
                // 基线里没有这一行 → 它是本次新建的虚拟行，这条命令给的就是它的全部值
                line = { id: first, attribute_id: false, value_ids: [] };
                lines.push(line);
            }
            if ("attribute_id" in second) {
                line.attribute_id = readMany2oneId(second.attribute_id);
            }
            if ("value_ids" in second) {
                line.value_ids = applyValueCommands(line.value_ids, second.value_ids);
            }
        } else if (operation === 2 || operation === 3) {
            const index = lines.findIndex((item) => item.id === first);
            if (index >= 0) {
                lines.splice(index, 1);
            }
        } else if (operation === 5) {
            lines.length = 0;
        } else if (operation === 6) {
            const kept = new Set(second || []);
            for (let index = lines.length - 1; index >= 0; index -= 1) {
                if (!kept.has(lines[index].id)) {
                    lines.splice(index, 1);
                }
            }
        }
    }
    return lines;
}

/** 纯函数：一组取值的「组合签名」（与顺序无关）。 */
export function combinationKey(valueIds) {
    return [...valueIds].sort((left, right) => left - right).join("-");
}

/** 纯函数：属性行内容的签名（用来感知「属性配置有没有变」）。 */
export function attributeLineSignature(record) {
    const value = record?.data?.attribute_line_ids;
    const records = value?.records || [];
    try {
        return records
            .map((line) =>
                [
                    line.resId || line.id || "new",
                    readMany2oneId(line.data?.attribute_id),
                    (line.data?.value_ids?.records || []).length,
                ].join(":")
            )
            .join("|");
    } catch {
        return "";
    }
}

/**
 * 纯函数：把属性行整理成「轴」——每个属性一项，带着它的取值与生成方式。
 *
 * 不是轴的行会被跳过：「不生成变体」（``no_variant``）的属性不参与组合；还没勾取值的行也不算。
 */
export function buildAxes(lines, snapshot) {
    const attributes = snapshot?.attributes || {};
    const values = snapshot?.values || {};
    const axes = [];
    for (const line of lines || []) {
        const info = attributes[line.attribute_id];
        if (!line.attribute_id || !info || info.create_variant === "no_variant") {
            continue;
        }
        const options = (line.value_ids || [])
            .filter((id) => values[id] && values[id].attribute_id === line.attribute_id)
            .map((id) => ({ id, name: values[id].name }));
        if (!options.length) {
            continue;
        }
        axes.push({
            attribute_id: line.attribute_id,
            attribute_label: info.name,
            values: options,
            // 「按需生成」属性：预建时不会展开它的其它取值（前端仍然全部列出来供分配）
            onDemand: info.create_variant === "dynamic",
        });
    }
    return axes;
}

/**
 * 纯函数：列出「这次改动之后会存在的组合」——**每行一个组合**。
 *
 * 行的身份（``key``）只由**「立即」属性**（``always``）的取值决定：
 *
 * - 有「立即」属性 → 按它们的取值做笛卡尔积（这是 Odoo 一定会预建的组合空间）；
 * - 全是「按需生成」属性（``dynamic``）→ 不展开取值空间（``T-039``：那种属性由 Odoo 在订单里
 *   创建变体），改用「既有变体现在带着的取值组合」作为行，用户可以在行内改这些取值；
 * - 没有任何有效轴 → 空表（产品还没加属性行）。
 *
 * 「按需生成」属性的取值是**行上的一个可改值**（不是行身份），优先级：
 * 用户在这一行选过的 → 该行匹配到的既有变体带着的 → 该轴第一个取值。所以它既不会预建
 * 其它取值，也不会因为取值变化把用户已经做好的分配弄丢。
 */
/**
 * 纯函数：列出「这次改动之后会存在的组合」——**每行一个组合，属性列全部穷举**。
 *
 * 所有属性一视同仁（含「按需生成」的）：各属性有效取值做笛卡尔积，每行一个组合。
 * 用户要求「充分列举所有可能的组合」，所以早期那套「按需轴只钉住既有变体的取值、
 * 列可改」的特例（``T-039``）已取消。
 *
 * 一个有效轴都没有时（例如把唯一属性删掉），不代表「没有组合」：产品本身就是一个
 * 空组合，要给一行让既有变体挂靠 —— 否则删除唯一属性后既有变体会变成「未分配」，
 * 保存被拦（见 AGENTS.md → L2 P4 陷阱 21）。
 */
export function buildCombinationRows(axes) {
    if (!axes.length) {
        // 没有属性：产品本身就是一个组合（空组合），给一行让既有变体挂靠
        return [
            {
                key: combinationKey([]),
                cells: [],
                variant_id: false,
                on_hand: null,
                is_new: true,
            },
        ];
    }
    const rows = [];
    const walk = (index, cells) => {
        if (index === axes.length) {
            rows.push({
                key: combinationKey(cells.map((cell) => cell.value_id)),
                cells,
                variant_id: false,
                on_hand: null,
                is_new: true,
            });
            return;
        }
        const axis = axes[index];
        for (const value of axis.values) {
            walk(index + 1, [
                ...cells,
                {
                    attribute_id: axis.attribute_id,
                    attribute_label: axis.attribute_label,
                    value_id: value.id,
                    value_name: value.name,
                    on_demand: Boolean(axis.onDemand),
                },
            ]);
        }
    };
    walk(0, []);
    return rows;
}

/** 纯函数：某条既有变体是不是「本来就属于这一行的组合」（每个属性取值全等）。 */
export function rowMatchesVariant(row, variant) {
    return row.cells.every((cell) => variant.values[cell.attribute_id] === cell.value_id);
}

/**
 * 纯函数：把「本来就属于这一行」的既有变体自动放回它的行。
 *
 * 用户没有显式分配、也没有显式清空过的行，如果某条既有变体的取值组合正好等于这一行，
 * 就把它挂上去（默认复用）。空组合行会匹配所有变体；多条变体抢一个空组合时只取第一条，
 * 其余留在「未分配」里等用户决定。
 *
 * :param list rows: ``computeVariantMapping()`` 算出的组合行。
 * :param list variants: 快照里的既有变体。
 * :param dict assignment: 当前分配（会被修改）。
 * :param dict cleared: 用户显式清空过的行 key（跳过）。
 * :param dict skipped: 用户标了「不生成变体」的行 key（跳过）。
 * :return: 更新后的 ``assignment``。
 */
export function applyDefaultAssignment(rows, variants, assignment, cleared, skipped) {
    const taken = new Set(Object.values(assignment || {}).filter(Boolean));
    for (const row of rows || []) {
        // 标了「不生成变体」的行不参与默认分配：给它挂上一条既有变体，又等于要生成一条
        if (assignment[row.key] || (cleared && cleared[row.key]) || (skipped && skipped[row.key])) {
            continue;
        }
        const match = (variants || []).find(
            (variant) => !taken.has(variant.id) && rowMatchesVariant(row, variant)
        );
        if (match) {
            assignment[row.key] = match.id;
            taken.add(match.id);
        }
    }
    return assignment;
}

/**
 * 纯函数：按「表单当前编辑态 + 快照」算出面板要显示的内容。
 *
 * :param list lines: ``mergeAttributeLines()`` 的结果（只带 id）。
 * :param list variants: 快照里的既有变体。
 * :param dict snapshot: 快照（``attributes`` / ``values``）。
 * :param dict assignment: 用户分配好的 ``{组合 key: 既有变体 id 或 false}``。
 * :param dict skipped: 用户标了「不生成变体」的组合 ``{组合 key: true}`` —— 这些行
 *   不挂变体、也不新建变体（保存时服务端把刚建出来的那一条丢掉）。
 * :return: ``{rows, axes, unassigned, unassigned_count, new_count, pending_count, skipped_count}``：
 *   ``rows`` 每行一个组合（``cells`` 各属性取值 + ``variant_id`` + ``skipped``；
 *   ``will_create`` 表示这一行会不会真的产出变体）；
 *   ``unassigned`` 没被任何组合认领的既有变体（**保存会被拦**）。
 */
export function computeVariantMapping({ lines, variants, snapshot, assignment, skipped }) {
    const axes = buildAxes(lines, snapshot);
    const rows = buildCombinationRows(axes);
    const skippedRows = skipped || {};
    const byId = new Map((variants || []).map((variant) => [variant.id, variant]));
    const taken = new Set();
    for (const row of rows) {
        // 「不生成变体」与「由某条既有变体保留」互斥：标了就不挂变体（挂上等于要生成一条）
        row.skipped = Boolean(skippedRows[row.key]);
        const wanted = row.skipped ? false : (assignment || {})[row.key];
        const variant = wanted ? byId.get(wanted) : false;
        if (variant && !taken.has(variant.id)) {
            row.variant_id = variant.id;
            row.on_hand = variant.on_hand;
            taken.add(variant.id);
        } else {
            row.variant_id = false;
            row.on_hand = null;
        }
        row.is_new = !row.variant_id && !row.skipped;
    }
    const unassigned = (variants || [])
        .filter((variant) => !taken.has(variant.id))
        .map((variant) => ({
            variant_id: variant.id,
            label: variant.label,
            on_hand: variant.on_hand,
        }));
    // 「按需生成」属性上，被某条既有变体认领的取值（含变体原本带着的、用户在按需轴上改的）。
    // 只有这些取值才会现在创建 —— 其余的留给 Odoo 在订单里创建（T-039 的口径），
    // 前端把它们**列出来**是为了让人看清全貌、能提前分配（见 AGENTS.md → L2 P4 陷阱 18）。
    const claimed = new Set();
    for (const row of rows) {
        if (!row.variant_id) {
            continue;
        }
        for (const cell of row.cells) {
            if (cell.on_demand) {
                claimed.add(cell.value_id);
            }
        }
    }
    for (const row of rows) {
        const onDemandCells = row.cells.filter((cell) => cell.on_demand);
        row.will_create =
            !row.skipped &&
            (Boolean(row.variant_id) || onDemandCells.every((cell) => claimed.has(cell.value_id)));
    }
    return {
        rows,
        axes,
        unassigned,
        unassigned_count: unassigned.length,
        new_count: rows.filter((row) => row.is_new && row.will_create).length,
        // 「等订单创建」不含用户标了「不生成变体」的行：那是明确不要，不是还没轮到
        pending_count: rows.filter((row) => !row.skipped && !row.will_create).length,
        skipped_count: rows.filter((row) => row.skipped).length,
    };
}

/**
 * 纯函数：Variant 下拉的选项 —— 每条既有变体 + 它当前被**哪一行**占着（``taken_by``）。
 *
 * 一条变体只能承载一个组合，所以已经被别行占着的变体在那一行里要禁用（灰显、选不了）：
 * 要换位置只能先把占着它的那一行改回「(new variant)」把它让出来，再给另一行选 ——
 * 否则两个下拉互相抢，用户改哪一行都像是从另一行「抢走」了变体，看不出到底谁让给谁
 * （见 AGENTS.md → L2 P4 陷阱 19）。
 *
 * :param list variants: 快照里的既有变体。
 * :param list rows: ``computeVariantMapping()`` 算出的组合行（带 ``key`` / ``variant_id``）。
 */
export function buildVariantOptions(variants, rows) {
    const takenBy = new Map();
    for (const row of rows || []) {
        if (row.variant_id) {
            takenBy.set(row.variant_id, row.key);
        }
    }
    return (variants || []).map((variant) => ({
        id: variant.id,
        label: variant.label,
        on_hand: variant.on_hand,
        taken_by: takenBy.get(variant.id) || false,
    }));
}

/** 纯函数：分配关系的稳定签名（与键的插入顺序无关，只认「哪一行占哪条变体」）。 */
function assignmentSignature(assignment) {
    return Object.keys(assignment || {})
        .filter((key) => assignment[key])
        .sort()
        .map((key) => `${key}:${assignment[key]}`)
        .join("|");
}

/** 纯函数：字典里「值为真的键」的稳定签名（与插入顺序无关）。 */
function truthyKeysSignature(dict) {
    return Object.keys(dict || {})
        .filter((key) => dict[key])
        .sort()
        .join("|");
}

/**
 * 纯函数：映射相对「未修改前」（``store.baseline``）有没有改动。
 *
 * 这是「要不要显示 Save manually / Discard all changes」的判据：只有用户真的改了分配
 * （改了变体归属、标了 / 取消「不生成变体」，或改了「共享供应商价格」），
 * 才认为有未保存的映射改动。面板第一次算完时会先建立基线
 * （``snapshotMappingBaseline()``），所以默认分配不算改动。
 */
export function mappingDiffersFromBaseline(store) {
    const baseline = store.baseline;
    if (!baseline) {
        return false;
    }
    return (
        assignmentSignature(store.assignment) !== assignmentSignature(baseline.assignment) ||
        truthyKeysSignature(store.skipped) !== truthyKeysSignature(baseline.skipped) ||
        Boolean(store.shareVendorPrices) !== Boolean(baseline.shareVendorPrices)
    );
}

/** 纯函数：把当前映射记为新基线（面板首次算完 / 保存成功后调用）。 */
export function snapshotMappingBaseline(store) {
    store.baseline = {
        assignment: { ...(store.assignment || {}) },
        skipped: { ...(store.skipped || {}) },
        shareVendorPrices: Boolean(store.shareVendorPrices),
    };
}

/**
 * 纯函数：把映射表整理成服务端认的归属载荷（``mapping`` 里每条就是一个组合）。
 *
 * ``skip`` 为真的组合服务端**不建变体**（本次刚建出来的那一条会被丢掉）；
 * 它与 ``origin_variant_id`` 互斥：既有变体带着库存与单据，一条都不能因为
 * 「这个组合不生成变体」而被删掉（服务端还会再判一次）。
 */
export function buildMappingPayload(rows, shareVendorPrices) {
    return {
        mapping: rows.map((row) => ({
            values: row.cells.filter((cell) => cell.value_id).map((cell) => cell.value_id),
            origin_variant_id: row.variant_id || false,
            skip: !!row.skipped,
        })),
        share_vendor_prices: !!shareVendorPrices,
    };
}

/** 纯函数：空的映射表状态（``resId`` 用来识别「换了产品记录」）。 */
export function emptyMappingStore(resId) {
    return {
        resId: resId || false,
        rows: [],
        unassigned: [],
        assignment: {},
        cleared: {},
        skipped: {},        // 用户标了「不生成变体」的组合：{组合 key: true}
        shareVendorPrices: false,
        signature: undefined,
        snapshot: null,
        baseline: null,       // 「未修改前」的分配（Discard all changes 恢复到这里）
        dirty: false,         // 映射相对基线改过没有（决定 Save manually / Discard all changes 的出现）
    };
}

/**
 * 纯函数：把一份映射状态**原地**清空成「刚换到 ``resId`` 这条记录」的样子。
 *
 * 必须**原地**改：``this.store`` 是 ``useState()`` 给的响应式代理，换一个新对象上去
 * ① 组件与保存钩子（都握着旧对象）会各说各话，② 不经过代理的 set 陷阱，界面根本不重画
 * （见模块 AGENTS.md → L2 P4 陷阱 24）。
 *
 * :param dict store: 映射状态（通常就是面板的 ``this.store``）。
 * :param resId: 当前记录的 id（新建还没保存时为 ``false``）。
 * :return: 同一个 ``store`` 对象（身份不变）。
 */
export function resetMappingStore(store, resId) {
    const fresh = emptyMappingStore(resId);
    for (const key of Object.keys(store)) {
        delete store[key];
    }
    Object.assign(store, fresh);
    return store;
}

/**
 * 映射表状态存在 ``model`` 上（不是组件里）：
 *
 * 面板挂在「属性与变体」页里，用户切到别的页签它就卸载了。把状态放在 model 上，
 * 保存钩子（``FormController.onWillSaveRecord``）与面板共享同一份数据 —— 无论面板
 * 当前有没有挂载，「用户怎么分配的」都不会丢；快照也只取一次。
 */
export function getMappingStore(model) {
    if (!model.variantMapping) {
        model.variantMapping = emptyMappingStore(model.root?.resId);
    }
    return model.variantMapping;
}

/**
 * 读「表单当前编辑态」的字段改动 —— **不走** ``model.mutex``。
 *
 * ``Record.getChanges()`` 是 ``mutex.exec(() => this._getChanges(...))``，而 ``Record.save()``
 * 已经把 ``_save()`` 丢进了同一把 mutex（``mutex.exec(() => this._save(options))``）。
 * 于是保存钩子（``FormController.onWillSaveRecord``）里再调 ``getChanges()``，就是
 * **等自己正占着的那把锁** —— 死锁：``await`` 永远不返回，表现为「点了 Save manually
 * 按钮变灰、一个请求都没发、然后一直灰着」（见模块 AGENTS.md → L2 P4 陷阱 21）。
 *
 * ``Record._getChanges()`` 与它调的 x2many ``_getCommands()`` 都是同步的，直接读即可。
 */
export function readLocalChanges(record) {
    return record._getChanges(record._changes, { withReadonly: true });
}

/**
 * 把「映射有没有未保存改动」同步给表单状态指示器。
 *
 * Odoo 的 ``FormStatusIndicator`` 监听 ``model.bus`` 上的 ``FIELD_IS_DIRTY`` 事件
 * （``web/static/src/views/form/form_status_indicator/form_status_indicator.js``），
 * 收到 true 就显示 **Save manually** / **Discard all changes** 两个按钮。
 * 映射改动只存在于本模块的 store 里（不是 record 的字段改动），所以必须主动广播 ——
 * 这也是「不让 Odoo 自动保存悄悄提交映射」的前提：record 不脏，自动保存路径就不会带它
 * （见 AGENTS.md → L2 P4 陷阱 20）。
 */
export function setMappingDirty(model, dirty) {
    const store = getMappingStore(model);
    if (store.dirty === dirty) {
        return;
    }
    store.dirty = dirty;
    model.bus?.trigger("FIELD_IS_DIRTY", dirty);
}

/** 丢掉尚未保存的映射改动，回到基线（原生 Discard all changes 会调用它）。 */
export function discardMappingChanges(model) {
    const store = getMappingStore(model);
    const baseline = store.baseline;
    store.assignment = { ...((baseline && baseline.assignment) || {}) };
    store.cleared = {};
    store.skipped = { ...((baseline && baseline.skipped) || {}) };
    store.shareVendorPrices = Boolean(baseline && baseline.shareVendorPrices);
    store.dirty = false;
    model.bus?.trigger("FIELD_IS_DIRTY", false);
    // 属性行也回到基线了：要**重算**（不是只刷行），否则面板还停在丢弃前的属性配置上
    model.variantMappingPanel?.scheduleRefresh();
}

/** 「属性 ↔ 变体」映射表：产品表单「属性与变体」页、属性行下方的常驻面板。 */
export class VariantMappingPanel extends Component {
    static template = "product_variant.VariantMappingPanel";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.store = useState(getMappingStore(this.props.record.model));
        // 保存钩子要用同一个实例重算（用户可能在本页改完就走保存）
        this.props.record.model.variantMappingPanel = this;
        // 切换产品记录时 model 是复用的：先把上一份映射（含基线）清掉，免得串记录
        this.resetForRecord();
        // 属性行增删、勾取值都会让 record 变化：统一防抖后重算（重算里再按签名去重）
        useRecordObserver(() => this.scheduleRefresh());
        // 兜底自检：Odoo 的 observer 触发条件依赖内部实现（见 AGENTS.md → L2 P4 陷阱 16），
        // 面板挂载期间每秒本地比较一次签名；没变化时 recompute() 直接返回，没有开销。
        this.pollTimer = setInterval(() => this.scheduleRefresh(), 1000);
    }

    /**
     * 换到另一条产品记录（点 **New** / 翻页 / 新建的产品保存后拿到真实 id）：
     * 上一份映射（行、分配、基线、脏标记）**整个作废**，再按新记录重取快照。
     *
     * 点 New 与翻页走的都是 ``model.load({resId})``：model 与面板组件实例都被复用
     * （``setup()`` 不会再跑一次），所以「记录换了」这件事只能在 ``recompute()`` /
     * 挂载时自己认出来（见模块 AGENTS.md → L2 P4 陷阱 24）。
     */
    async resetForRecord() {
        const resId = this.props.record?.resId || false;
        resetMappingStore(this.store, resId);
        // 上一份「未保存」标记要跟着一起撤掉，否则新记录上还挂着 Save manually
        this.props.record.model.bus?.trigger("FIELD_IS_DIRTY", false);
        await this.load();
    }

    willUnmount() {
        clearTimeout(this.refreshTimer);
        clearInterval(this.pollTimer);
    }

    // ------------------------------------------------------------------
    // 数据：一次快照 + 纯前端重算
    // ------------------------------------------------------------------

    /** 取一次快照（有缓存就不重复取），然后重算映射。 */
    async load() {
        const record = this.props.record;
        if (!record || !record.resId) {
            return;
        }
        // 新建的产品保存之后才有 id：记下来，免得又被当成「换了记录」反复作废
        this.store.resId = record.resId;
        if (!this.store.snapshot) {
            this.store.snapshot = await this.orm.call(
                "product.template",
                "get_variant_mapping_snapshot",
                [[record.resId]]
            );
        }
        this.store.signature = undefined;
        await this.recompute();
    }

    /** 变化很密（加一行 / 勾一个取值都会触发），防抖后只算一次。 */
    scheduleRefresh() {
        clearTimeout(this.refreshTimer);
        this.refreshTimer = setTimeout(() => this.recompute(), 150);
    }

    /**
     * 纯前端重算：``readLocalChanges()``（本地、不走 mutex）拿属性行命令 → 合并到快照基线 → 算组合表。
     *
     * 属性配置没真的变（例如只是改了产品名）就直接返回，省掉重算与重渲染；
     * 但**分配关系**变了要走 ``refreshRows()``（那里不做签名去重）。
     */
    async recompute() {
        const record = this.props.record;
        if (!record) {
            return;
        }
        // 换了记录（New / 翻页 / 新建保存后拿到 id）：旧快照与旧分配都不再属于这条记录
        const resId = record.resId || false;
        if (this.store.resId !== resId) {
            await this.resetForRecord();
            return;
        }
        const snapshot = this.store.snapshot;
        if (!resId || !snapshot) {
            return;
        }
        // 不走 ``record.getChanges()``：保存钩子是在 mutex 里调它的，会死锁（陷阱 21）
        const changes = readLocalChanges(record);
        const lines = mergeAttributeLines(snapshot.lines, changes.attribute_line_ids);
        const signature = JSON.stringify(lines);
        if (signature === this.store.signature) {
            return;
        }
        this.store.signature = signature;
        this.store.lines = lines;
        this.refreshRows();
    }

    /** 用当前属性行 + 快照 + 用户已做的分配，重算组合表（纯本地，不同步去重）。 */
    refreshRows() {
        const snapshot = this.store.snapshot;
        if (!snapshot) {
            return;
        }
        const variants = snapshot.variants || [];
        const lines = this.store.lines || [];
        // 属性行变了：把已经失效的分配丢掉，其余（行还在的）保留
        const preview = computeVariantMapping({
            lines,
            variants,
            snapshot,
            assignment: this.store.assignment,
            skipped: this.store.skipped,
        });
        const liveKeys = new Set(preview.rows.map((row) => row.key));
        for (const key of Object.keys(this.store.assignment)) {
            if (!liveKeys.has(key)) {
                delete this.store.assignment[key];
                delete this.store.cleared[key];
            }
        }
        // 组合已经不存在的「不生成变体」标记跟着一起丢（属性行改了，那一行已经不在了）
        for (const key of Object.keys(this.store.skipped)) {
            if (!liveKeys.has(key)) {
                delete this.store.skipped[key];
            }
        }
        // 默认分配：把「本来就属于这一行」的既有变体放回它的行
        // （用户显式清空过、或标了「不生成变体」的行不碰）
        applyDefaultAssignment(
            preview.rows, variants, this.store.assignment, this.store.cleared, this.store.skipped
        );
        const result = computeVariantMapping({
            lines,
            variants,
            snapshot,
            assignment: this.store.assignment,
            skipped: this.store.skipped,
        });
        this.store.rows = result.rows;
        this.store.unassigned = result.unassigned;
        this.store.axes = result.axes;
        this.store.newCount = result.new_count;
        this.store.pendingCount = result.pending_count || 0;
        this.store.skippedCount = result.skipped_count || 0;
        this.syncDirty();
    }

    /**
     * 重算「映射有没有未保存的改动」并广播给表单状态指示器。
     *
     * 第一次算完先建立基线（默认分配不算改动），之后分配一变就变成「有改动」，
     * 于是右上角（以及面板下方）出现 Save manually / Discard all changes。
     */
    syncDirty() {
        if (!this.store.baseline) {
            snapshotMappingBaseline(this.store);
        }
        this.store.dirty = mappingDiffersFromBaseline(this.store);
        setMappingDirty(this.props.record.model, this.store.dirty);
    }

    /** 交给服务端落库的归属载荷（保存钩子把它塞进本次保存的 ``changes``）。 */
    mappingPayload() {
        return buildMappingPayload(this.store.rows, this.store.shareVendorPrices);
    }

    // ------------------------------------------------------------------
    // 展示
    // ------------------------------------------------------------------

    get isEditable() {
        return this.props.record.isInEdition;
    }

    /**
     * 面板要不要显示：**已保存的产品**、且快照确实属于**当前这条记录**时才显示。
     *
     * 新建（还没有 id）时没有既有变体可映射；换到另一条记录后，重算与取快照都是异步的
     * （防抖 150ms / 兜底 1s + 一次 RPC），这段时间里**先藏起来** —— 否则界面上挂着的
     * 是上一条产品的映射，用户会当成这一条的（见模块 AGENTS.md → L2 P4 陷阱 24）。
     */
    get showPanel() {
        const resId = this.props.record?.resId || false;
        return Boolean(resId) && this.store.resId === resId;
    }

    /** 面板标题（原来只有一句说明，看不出这一块是干什么的）。 */
    get panelTitle() {
        return _t("Variants Mapping");
    }

    get mappingDirty() {
        return Boolean(this.store.dirty);
    }

    get unsavedLabel() {
        return _t("Unsaved mapping changes");
    }

    get dirtyHint() {
        return _t(
            "Use the Save / Discard buttons next to the product title to store the mapping, or to roll the attribute lines and the mapping back to the last saved state."
        );
    }

    get axisLabels() {
        return (this.store.axes || []).map((axis) => axis.attribute_label);
    }

    /** Variant 下拉的选项：所有既有变体 + 它被哪一行占着（被别行占着的会在那一行禁用）。 */
    get variantOptions() {
        return buildVariantOptions(
            this.store.snapshot?.variants || [],
            this.store.rows || []
        ).map((option) => ({
            ...option,
            label: option.on_hand === null || option.on_hand === undefined
                ? option.label
                : _t("%(label)s — %(count)s on hand", { label: option.label, count: option.on_hand }),
        }));
    }

    /** 某一行里这个选项是不是「已被别的组合占着」（要禁用）。 */
    isOptionTaken(option, row) {
        return Boolean(option.taken_by) && option.taken_by !== row.key;
    }

    get takenElsewhereLabel() {
        return _t(
            "Already kept by another combination — set that one back to (new variant) first if you want to move it here"
        );
    }

    get unassignedCount() {
        return (this.store.unassigned || []).length;
    }

    get introLabel() {
        return _t(
            "Every combination that will exist, and which existing variant keeps it. Leave the variant empty to create a new one, or pick Do not create a variant to leave that combination out; a variant that is not assigned to any combination would be dropped, so the save is blocked until each of them is assigned."
        );
    }

    get newVariantLabel() {
        return _t("(new variant)");
    }

    get chooseVariantLabel() {
        return _t("Choose a variant");
    }

    /** Variant 下拉里「不生成变体」这个选项的值（既不是变体 id，也不是空值）。 */
    get skipValue() {
        return "skip";
    }

    get skipLabel() {
        return _t("Do not create a variant");
    }

    /** 这一行还挂着既有变体时，「不生成变体」选不了 —— 得先把它让出来。 */
    get skipBlockedLabel() {
        return _t(
            "An existing variant keeps this combination, so it cannot be marked as not created: set that row back to (new variant) to release the variant first — an existing variant is never dropped."
        );
    }

    get skippedCount() {
        return this.store.skippedCount || 0;
    }

    get skippedHint() {
        return _t(
            "%(count)s combinations are marked as not created: no variant is created for them. It applies to this save only, so the next attribute change lists them again.",
            { count: this.skippedCount }
        );
    }

    get unassignedHint() {
        return _t(
            "%(count)s existing variants are not assigned to any combination yet: assign each of them in the Variant column (the combination itself is never dropped, it would just create a new variant).",
            { count: this.unassignedCount }
        );
    }

    get pendingCount() {
        return this.store.pendingCount || 0;
    }

    get pendingHint() {
        return _t(
            "%(count)s combinations are not created now: they only sit on attributes that create their variants on demand, and no existing variant keeps them yet — Odoo creates those variants when they are ordered. Assign a variant here to create one right away.",
            { count: this.pendingCount }
        );
    }

    get newVariantsLabel() {

        return _t(
            "%(count)s combinations have no existing variant and will be created as new variants",
            { count: this.store.newCount || 0 }
        );
    }

    get shareVendorPricesLabel() {
        return _t("Apply the vendor prices of these variants to all variants");
    }

    /** 未分配变体的简短清单（提示里点名，用户知道还差哪几条）。 */
    get unassignedLabel() {
        return (this.store.unassigned || []).map((variant) => variant.label).join(", ");
    }

    // ------------------------------------------------------------------
    // 交互
    // ------------------------------------------------------------------

    /**
     * 给某一行指定「这个组合怎么办」—— 下拉有三种取值：
     *
     * - 一条既有变体：那条变体接着承载这个组合（库存、单据、价格都跟着走）；
     * - 空：这个组合**新建**一条变体；
     * - ``skip``（**不生成变体**）：这个组合**不产出变体**，本次不建、也不许有既有变体挂在上面。
     */
    onSelectVariant(row, ev) {
        const raw = ev.target.value;
        if (raw === this.skipValue) {
            // 「不生成变体」与「由既有变体保留」互斥：这一行上还挂着既有变体时不能标 ——
            // 标了等于要删掉它，而既有变体带着库存与单据，一条都不能动
            // （下拉里已禁用，这里是防御；服务端还会再判一次，见 AGENTS.md → L1 约束 1）
            if (!row.variant_id) {
                this.store.skipped[row.key] = true;
                delete this.store.assignment[row.key];
                delete this.store.cleared[row.key];
            }
            this.refreshRows();
            return;
        }
        const variantId = Number(raw) || false;
        if (variantId) {
            // 已经被别行占着的变体在下拉里是禁用的（浏览器不会触发它），这里只是防御：
            // 想把它换到这一行，得先把占着它的那一行改回「(new variant)」让出来
            // （见 AGENTS.md → L2 P4 陷阱 19）
            const takenElsewhere = this.store.rows.some(
                (other) => other !== row && other.variant_id === variantId
            );
            if (takenElsewhere) {
                this.refreshRows();
                return;
            }
            this.store.assignment[row.key] = variantId;
            delete this.store.cleared[row.key];
            delete this.store.skipped[row.key];
        } else {
            // 留空 = 这一行新建变体；记下来，别在下次重算时又自动分配回去
            delete this.store.assignment[row.key];
            delete this.store.skipped[row.key];
            this.store.cleared[row.key] = true;
        }
        this.refreshRows();
    }

    onToggleShareVendorPrices(ev) {
        this.store.shareVendorPrices = ev.target.checked;
        this.syncDirty();
    }
}

/**
 * 让映射表跟着「属性与变体」页的那个 o2m 动起来。
 *
 * ``useRecordObserver`` 的依赖是 ``[props.record]``（record 对象本身不变），子行里改字段
 * 不一定触发它；o2m 组件自己会随列表变化重渲染，所以在它每次 patch 之后通知面板重算
 * （见模块 AGENTS.md → L2 P4 陷阱 16）。外层与真正渲染行的 ``ListX2ManyField`` 都挂，
 * 包装原 ``setup`` 时不依赖 ``super.setup`` 是否存在。
 */
function notifyMappingPanel(component) {
    const model = component?.props?.record?.model || component?.props?.list?.model;
    if (model?.variantMappingPanel) {
        onPatched(() => model.variantMappingPanel.scheduleRefresh());
    }
}

for (const X2Many of [X2ManyField, ListX2ManyField]) {
    const originalSetup = X2Many.prototype.setup;
    patch(X2Many.prototype, {
        setup() {
            if (originalSetup) {
                originalSetup.call(this);
            }
            notifyMappingPanel(this);
        },
    });
}

/**
 * 改属性行时**不再**打一次 ``product.template`` 的 onchange
 * （见模块 AGENTS.md → L2 P4 陷阱 21）。
 *
 * Odoo 的 ``ir.ui.view._postprocess_on_change()`` 会给「视图里某个 compute 字段的依赖」
 * 自动补 ``on_change="1"``：``attribute_line_ids`` 是 ``valid_product_template_attribute_line_ids``
 * 这类 compute 字段的依赖，于是表单里一改属性行就发一次
 * ``/web/dataset/call_kw/product.template/onchange``。本模块的属性改动**全部在前端算**
 * （挂载时一次快照 + 本地 ``_getChanges()``），这次调用既没有用，又会把 model 的 mutex 占住
 * （保存要排在它后面），所以直接跳掉 —— 只跳「改动里只有属性行」的那一次，
 * ``standard_price`` / ``type`` / ``uom_id`` 这些真有 onchange 的字段照旧。
 */
const NO_ONCHANGE_MODEL = "product.template";
const NO_ONCHANGE_FIELDS = new Set(["attribute_line_ids"]);

patch(Record.prototype, {
    async _getOnchangeValues(changes) {
        const fieldNames = Object.keys(changes || {});
        if (
            this.resModel === NO_ONCHANGE_MODEL &&
            fieldNames.length &&
            fieldNames.every((fieldName) => NO_ONCHANGE_FIELDS.has(fieldName))
        ) {
            return {};
        }
        return super._getOnchangeValues(...arguments);
    },
});

/**
 * 字段注册表的描述对象。
 *
 * **必须**是 ``{ component, displayName, supportedTypes }`` 这种对象，不能把组件类
 * 直接丢进去：``web.Field`` 模板渲染的是 ``field.component``，注册裸类时它是
 * ``undefined``，渲染会崩在 ``Component.name``（见模块 AGENTS.md → L2 P4 陷阱 8）。
 */
export const variantMappingPanelField = {
    component: VariantMappingPanel,
    displayName: _t("Attribute / Variant Mapping"),
    supportedTypes: ["text"],
};

registry.category("fields").add("variant_mapping_panel", variantMappingPanelField);
