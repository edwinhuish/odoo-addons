/**
 * 映射表「纯函数」的离线自测（不需要 Odoo、不需要浏览器）。
 *
 * 面板的映射计算全在前端，Odoo 的 Python 测试跑不到它；这里把
 * `static/src/js/variant_mapping_panel.js` 头部那段纯函数抽出来，喂真实形状的
 * 「基线 + getChanges 命令」跑断言 —— 这几条正是反复踩过的坑与交互约定
 * （见 AGENTS.md → L2 P4 陷阱 11~18）。
 *
 * 跑法（宿主机有 node 即可）：
 *
 *     node product_variant/tests/js/variant_mapping_pure.mjs
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const panelPath = join(here, "..", "..", "static", "src", "js", "variant_mapping_panel.js");
const source = readFileSync(panelPath, "utf-8");

// 纯函数段：从文件头第一个纯函数到 getMappingStore（之后的代码依赖 @odoo/owl，抽不出来）
const start = source.indexOf("/** 纯函数：还没被分配到任何组合的既有变体数");
const end = source.indexOf("/**\n * 映射表状态存在");
assert.ok(start > 0 && end > start, "面板文件结构变了，自测的抽取位置要跟着改");

const pure = source.slice(start, end).replace(/export function/g, "function");
const {
    applyDefaultAssignment,
    applyValueCommands,
    buildMappingPayload,
    buildCombinationRows,
    buildVariantOptions,
    computeVariantMapping,
    mappingDiffersFromBaseline,
    mergeAttributeLines,
    rowMatchesVariant,
    snapshotMappingBaseline,
} = new Function(
    `${pure}; return { applyDefaultAssignment, applyValueCommands, buildMappingPayload, buildCombinationRows, ` +
        `buildVariantOptions, computeVariantMapping, mappingDiffersFromBaseline, mergeAttributeLines, ` +
        `rowMatchesVariant, snapshotMappingBaseline };`
)();

const check = (label, fn) => {
    fn();
    console.log("  ok -", label);
};

// ------------------------------------------------------------------
// 场景：Legs(2) × Color(3) × Length(2)，既有变体 2 条
// ------------------------------------------------------------------
const snapshot = {
    attributes: {
        5: { name: "Legs", create_variant: "always" },
        6: { name: "Color", create_variant: "always" },
        7: { name: "Length", create_variant: "dynamic" },
    },
    values: {
        51: { name: "Steel", attribute_id: 5 },
        52: { name: "Aluminium", attribute_id: 5 },
        61: { name: "White", attribute_id: 6 },
        62: { name: "Gray", attribute_id: 6 },
        63: { name: "Beige", attribute_id: 6 },
        71: { name: "120", attribute_id: 7 },
        72: { name: "140", attribute_id: 7 },
    },
};
const lines = [
    { id: 1, attribute_id: 5, value_ids: [51, 52] },
    { id: 2, attribute_id: 6, value_ids: [61, 62, 63] },
    { id: 3, attribute_id: 7, value_ids: [71, 72] },
];
const variants = [
    { id: 900, label: "[E-COM12] Chair (Steel, White, 140)", on_hand: 26, values: { 5: 51, 6: 61, 7: 72 } },
    { id: 901, label: "[E-COM13] Chair (Aluminium, White, 140)", on_hand: 30, values: { 5: 52, 6: 61, 7: 72 } },
];
const base = (extra = {}) =>
    computeVariantMapping({ lines, variants, snapshot, assignment: {}, ...extra });

console.log("variant_mapping_pure");

check("行 = 属性组合：所有属性（含「按需生成」）一律穷举", () => {
    const result = base();
    assert.equal(result.rows.length, 12, "2 × 3 × 2 = 12 个组合，一个不少");
    assert.deepEqual(
        result.rows[0].cells.map((cell) => cell.value_name),
        ["Steel", "White", "120"]
    );
    assert.equal(result.unassigned_count, 2, "两条既有变体还没被分配");
    // 「按需生成」属性的取值要有人认领才会现在创建：一条都没认领时全部等订单
    assert.equal(result.new_count, 0);
    assert.equal(result.pending_count, 12);
});

check("组合不重复：同一组取值只出现一行", () => {
    const keys = base().rows.map((row) => row.key);
    assert.equal(new Set(keys).size, keys.length);
});

check("默认分配：本来就属于这一行的变体放回它的行", () => {
    const assignment = {};
    for (const row of base().rows) {
        const match = variants.find((variant) => rowMatchesVariant(row, variant));
        if (match) {
            assignment[row.key] = match.id;
        }
    }
    const result = base({ assignment });
    assert.equal(result.unassigned_count, 0);
    // 两条既有变体都把 Length 钉在 140 → 「立即」轴那 6 个 140 组合会创建（减去两条既有变体）
    assert.equal(result.new_count, 4);
    // Length=120 的 6 个组合没人认领 → 不预建，等 Odoo 在订单里创建
    assert.equal(result.pending_count, 6);
    assert.ok(
        result.rows.filter((row) => !row.will_create).every((row) =>
            row.cells.some((cell) => cell.on_demand && cell.value_name === "120")
        )
    );
    assert.equal(result.rows.find((row) => row.variant_id === 900).cells[2].value_name, "140");
});

check("同一条变体只能占一行：重复的分配只认第一行，另一行算新建", () => {
    const rows = base().rows;
    const result = base({ assignment: { [rows[0].key]: 900, [rows[1].key]: 900 } });
    assert.equal(result.rows[0].variant_id, 900);
    assert.equal(result.rows[1].variant_id, false);
    assert.equal(result.rows[1].is_new, true);
    assert.equal(result.unassigned_count, 1, "V2 仍然待分配");
});

check("交换位置：A 让出后可以选到别的行，原行变空（可再放 B）", () => {
    const rows = base().rows;
    const swapped = { [rows[3].key]: 900 };
    let result = base({ assignment: swapped });
    assert.equal(result.rows[3].variant_id, 900);
    assert.equal(result.rows[0].is_new, true, "原行空出来 → 新建变体");
    assert.equal(result.unassigned_count, 1, "V2 待分配");
    result = base({ assignment: { ...swapped, [rows[0].key]: 901 } });
    assert.equal(result.rows[0].variant_id, 901);
    assert.equal(result.unassigned_count, 0);
});

check("Variant 下拉可以清空：那一行变回「新建变体」", () => {
    const rows = base().rows;
    assert.equal(base({ assignment: { [rows[0].key]: 900 } }).rows[0].variant_id, 900);
    const cleared = base({ assignment: {} });
    assert.equal(cleared.rows[0].is_new, true);
    assert.equal(cleared.unassigned_count, 2, "清空后那条变体需要重新分配");
});

check("提交给服务端的 mapping 就是「组合 → 归属变体」，覆盖全部组合", () => {
    const rows = base().rows;
    const payload = buildMappingPayload(rows, false);
    assert.equal(payload.mapping.length, 12);
    assert.deepEqual(Object.keys(payload.mapping[0]).sort(), ["origin_variant_id", "values"]);
    assert.equal(payload.mapping[0].origin_variant_id, false);
    assert.equal(payload.share_vendor_prices, false);
});

check("全是「按需生成」属性时，同样按取值穷举组合", () => {
    const onlyDynamic = {
        attributes: { 7: snapshot.attributes[7] },
        values: snapshot.values,
    };
    const result = computeVariantMapping({
        lines: [{ id: 3, attribute_id: 7, value_ids: [71, 72] }],
        variants: [{ id: 900, label: "V1", on_hand: null, values: { 7: 71 } }],
        snapshot: onlyDynamic,
        assignment: {},
    });
    assert.equal(result.rows.length, 2, "组合照样穷举");
    assert.deepEqual(result.rows.map((row) => row.cells[0].value_name), ["120", "140"]);
    assert.equal(result.pending_count, 2, "既有变体没认领时都不预建");
});

check("Add a line → 选属性 → 勾取值：那一行要成为轴（虚拟 id 不能自己造）", () => {
    const merged = mergeAttributeLines([], [
        [0, 0, {}],
        [1, 0, { attribute_id: 5, value_ids: [[6, 0, [51, 52]]] }],
    ]);
    assert.deepEqual(merged, [{ id: 0, attribute_id: 5, value_ids: [51, 52] }]);
    const single = {
        attributes: { 5: snapshot.attributes[5] },
        values: snapshot.values,
    };
    const result = computeVariantMapping({
        lines: merged,
        variants: [{ id: 1000, label: "Cable Box", on_hand: null, values: {} }],
        snapshot: single,
        assignment: {},
    });
    assert.equal(result.rows.length, 2, "Color 的两个取值各一行");
    assert.equal(result.unassigned_count, 1, "既有变体等着被分配");
});

check("逐条勾取值走增量命令，不能把已勾的丢掉", () => {
    assert.deepEqual(applyValueCommands([51], [[4, 52]]), [51, 52]);
    assert.deepEqual(applyValueCommands([51, 52], [[3, 51]]), [52]);
    assert.deepEqual(applyValueCommands([51], [[6, 0, [52]]]), [52]);
});

check("把某一行的取值删空 / 删整行都不炸", () => {
    const baseline = [{ id: 2, attribute_id: 6, value_ids: [61, 62] }];
    assert.deepEqual(mergeAttributeLines(baseline, [[1, 2, { value_ids: [[5]] }]]), [
        { id: 2, attribute_id: 6, value_ids: [] },
    ]);
    assert.deepEqual(mergeAttributeLines(baseline, [[2, 2]]), []);
    const result = computeVariantMapping({
        lines: mergeAttributeLines(baseline, [[2, 2]]),
        variants,
        snapshot,
        assignment: {},
    });
    assert.equal(result.rows.length, 1, "没有属性时产品本身是一个空组合，也要给一行");
    assert.equal(result.rows[0].cells.length, 0);
    // 模拟 refreshRows 里的默认分配：空组合匹配所有变体，只会挂第一条
    const assignment = applyDefaultAssignment(result.rows, variants, {}, {});
    const final = computeVariantMapping({
        lines: mergeAttributeLines(baseline, [[2, 2]]),
        variants,
        snapshot,
        assignment,
    });
    assert.equal(final.unassigned_count, 1, "两条既有变体里只有一条能挂到空组合上");
});

check("删除唯一属性后，唯一既有变体自动复用", () => {
    const singleVariant = [{ id: 900, label: "[HW017] Bracket", on_hand: 10, values: {} }];
    const result = computeVariantMapping({
        lines: [],
        variants: singleVariant,
        snapshot: { attributes: {}, values: {} },
        assignment: {},
    });
    assert.equal(result.rows.length, 1, "空组合给一行");
    const assignment = applyDefaultAssignment(result.rows, singleVariant, {}, {});
    const final = computeVariantMapping({
        lines: [],
        variants: singleVariant,
        snapshot: { attributes: {}, values: {} },
        assignment,
    });
    assert.equal(final.rows[0].variant_id, 900, "唯一既有变体自动挂到空组合");
    assert.equal(final.unassigned_count, 0, "没有未分配的变体");
});

check("组合行的 key 唯一，且顺序无关", () => {
    const rows = buildCombinationRows([
        { attribute_id: 5, attribute_label: "Legs", values: [{ id: 51, name: "Steel" }, { id: 52, name: "Aluminium" }] },
        { attribute_id: 6, attribute_label: "Color", values: [{ id: 61, name: "White" }] },
    ]);
    assert.equal(rows.length, 2);
    assert.equal(new Set(rows.map((row) => row.key)).size, rows.length);
});

check("有人认领之后，认领所在这条按需取值上的组合才会现在创建", () => {
    const rows = base().rows;
    // 只认领「Steel + White + 120」这一行
    const target = rows.find((row) =>
        row.cells.every((cell) => ["Steel", "White", "120"].includes(cell.value_name))
    );
    const result = base({ assignment: { [target.key]: 900 } });
    assert.equal(result.unassigned_count, 1, "另一条既有变体还没分配");
    // 立即轴展开出的 Length=120 那 6 个组合会创建（减去被认领的这条）
    assert.equal(result.new_count, 5);
    assert.equal(result.pending_count, 6, "Length=140 没人认领 → 等订单");
    assert.equal(result.rows.find((row) => row.key === target.key).will_create, true);
});

check("已被别的行选走的变体在那一行禁用：只能先让出来再换", () => {
    const rows = base().rows;
    const rowA = rows.find((row) => rowMatchesVariant(row, variants[0]));   // Steel / White / 140
    const rowB = rows.find((row) => rowMatchesVariant(row, variants[1]));   // Aluminium / White / 140
    const result = computeVariantMapping({
        lines,
        variants,
        snapshot,
        assignment: { [rowA.key]: 900, [rowB.key]: 901 },
    });
    const options = buildVariantOptions(variants, result.rows);

    assert.equal(options.find((option) => option.id === 900).taken_by, rowA.key);
    assert.equal(options.find((option) => option.id === 901).taken_by, rowB.key);
    // A 那一行里 901 被别人占着 → 禁用；自己的 900 不禁用
    assert.equal(options.find((option) => option.id === 901).taken_by === rowA.key, false);
    assert.equal(options.find((option) => option.id === 900).taken_by === rowA.key, true);

    // A 先让出来（改回新建）→ 900 在 B 那一行就能选了
    const freed = computeVariantMapping({
        lines,
        variants,
        snapshot,
        assignment: { [rowB.key]: 901 },
    });
    assert.equal(buildVariantOptions(variants, freed.rows).find((o) => o.id === 900).taken_by, false);
});

check("映射改过才显示保存/丢弃：默认分配不算改动，动过才显示", () => {
    const store = { assignment: {}, shareVendorPrices: false };
    assert.equal(mappingDiffersFromBaseline(store), false, "还没建立基线时不算改动");
    snapshotMappingBaseline(store);
    assert.equal(mappingDiffersFromBaseline(store), false, "刚记完基线：没有改动");

    const rowA = base().rows.find((row) => rowMatchesVariant(row, variants[0]));
    store.assignment[rowA.key] = 900;
    assert.equal(mappingDiffersFromBaseline(store), true, "挑了一条变体 → 有未保存改动");

    delete store.assignment[rowA.key];
    assert.equal(mappingDiffersFromBaseline(store), false, "清回基线 → 又没有改动了");

    store.shareVendorPrices = true;
    assert.equal(mappingDiffersFromBaseline(store), true, "勾选框也属于映射状态");
});

console.log("all good");
