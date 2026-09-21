#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 开发库初始化 / 补齐（幂等）—— 让「重建容器后还要手工装模块、改密码」这件事消失
#
# 目标状态（本仓库本地开发约定）：
#   · 数据库账号     odoo / odoo（compose 里的 POSTGRES_USER / POSTGRES_PASSWORD）
#   · 模块           .dev/init.yaml 的 modules（Odoo 官方 / 第三方）+ addons（本仓库扩展）
#   · 语言           en_US(English US) / zh_CN(Chinese, Simplified)，缺哪个装哪个
#   · 演示数据       随首次安装一起加载（显式 `--with-demo`：Odoo 19 的 CLI 默认不装）
#   · 批次          演示数据自带的 tracking=lot 会被清回 none（见 cleanup_demo_lots）
#
# 平时由 Taskfile 调，也可以直接跑：
#   bash .dev/scripts/init-db.sh                    # 库不在就整套装上；在就只补缺失模块 / 语言
#   bash .dev/scripts/init-db.sh --fresh            # 删库重建（演示数据只有这一次机会，装上才有）
#   DEV_DB=other bash .dev/scripts/init-db.sh       # 换库名
#   DEV_MODULES=mrp bash .dev/scripts/init-db.sh    # 临时覆盖官方 / 第三方模块清单（默认读 init.yaml）
#   DEV_ADDONS=product_image bash .dev/scripts/init-db.sh     # 临时覆盖本仓库扩展清单（默认读 init.yaml；留空 → 自动发现全部）
#   DEV_LANGS=en_US bash .dev/scripts/init-db.sh    # 临时覆盖语言清单（默认读 .dev/init.yaml）
#
# 为什么「演示数据」要 fresh：Odoo 的演示数据是**模块安装时**灌进去的，事后补不了。
# 想连 filestore 一起从零来过，用 `task reset`（清 .dev/data）再 `task up`。
# ---------------------------------------------------------------------------
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"      # .dev/scripts
DEV_DIR="$(cd "$HERE/.." && pwd)"          # .dev
REPO="$(cd "$DEV_DIR/.." && pwd)"          # 仓库根
COMPOSE=(docker compose -f "$DEV_DIR/compose.yml")

DEV_DB="${DEV_DB:-dev}"
# task init 的配置（YAML：顶层 modules / addons / langs 三个 key，见 .dev/init.yaml 头部注释）。
# 环境变量 DEV_MODULES / DEV_ADDONS / DEV_LANGS 只用于临时覆盖；没设时才从这里读。
INIT_YAML="$DEV_DIR/init.yaml"
# 配置缺失 / 没写 langs 时的默认语言：en_US 是 Odoo 默认源语言（一般已激活），
# zh_CN 是自研模块的译文语言（见 AGENTS.md 4.1）。
DEFAULT_LANGS="en_US,zh_CN"

FRESH=0
for arg in "$@"; do
    case "$arg" in
        --fresh) FRESH=1 ;;
        *) echo "[错误] 不认识的参数：$arg（只支持 --fresh）" >&2; exit 2 ;;
    esac
done

info() { echo "[信息] $*"; }
warn() { echo "[警告] $*" >&2; }

# 读 YAML 用哪个 python：宿主机有 PyYAML 就用宿主机（快），否则退回 Odoo 容器里的
# python3（镜像自带 PyYAML，只是每次解析都要起一次容器，慢几秒）。结果缓存进 PY_RUN。
PY_RUN=()
py_run() {
    [[ ${#PY_RUN[@]} -gt 0 ]] && return 0
    if command -v python3 >/dev/null 2>&1 && python3 -c 'import yaml' >/dev/null 2>&1; then
        PY_RUN=(python3)
    else
        warn "宿主机没有 python3 + PyYAML，改用 Odoo 容器里的 python3 解析 $INIT_YAML（稍慢）"
        PY_RUN=("${COMPOSE[@]}" run --rm -T odoo python3)
    fi
}

# 读 YAML：`yaml_get <file> <key>` → 值（每行一个，块列表天然一行一个）。
# 支持 `key: [a, b]` 行内数组、`key:` + `- a` 块列表、单值标量；key 不存在 / 空列表 → 空输出。
# 解析交给 PyYAML（标准 YAML 语义，注释 / 缩进 / 类型都不用自己操心）。
yaml_get() {
    [[ -f "$1" ]] || return 0
    py_run
    "${PY_RUN[@]}" - "$1" "$2" <<'PY'
import sys, yaml

path, key = sys.argv[1], sys.argv[2]
try:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
except FileNotFoundError:
    sys.exit(0)
if not isinstance(data, dict):
    sys.exit(0)
val = data.get(key)
if val is None:
    sys.exit(0)
for item in (val if isinstance(val, list) else [val]):
    if item is not None:
        print(item)
PY
}

# 要装的模块：环境变量 DEV_MODULES > .dev/init.yaml 的 modules。
# 只认模块技术名（写应用显示名如 Sales 是装不上的）。配置缺失只警告 —— 仓库自研模块仍会自动发现。
list_modules() {
    local val=""
    if [[ -n "${DEV_MODULES:-}" ]]; then
        val="$DEV_MODULES"
    elif [[ -f "$INIT_YAML" ]]; then
        val="$(yaml_get "$INIT_YAML" modules || true)"
    else
        warn "找不到配置 $INIT_YAML，也没设 DEV_MODULES —— 只装本仓库模块"
    fi
    [[ -n "$val" ]] || return 0
    tr ', \t' '\n\n\n' <<<"$val" | awk 'NF && !seen[$0]++'
}

# 要装的语言：环境变量 DEV_LANGS > .dev/init.yaml 的 langs > 默认值
list_langs() {
    local val=""
    if [[ -n "${DEV_LANGS:-}" ]]; then
        val="$DEV_LANGS"
    elif [[ -f "$INIT_YAML" ]]; then
        val="$(yaml_get "$INIT_YAML" langs || true)"
    fi
    [[ -n "$val" ]] || val="$DEFAULT_LANGS"
    tr ', \t' '\n\n\n' <<<"$val" | awk 'NF && !seen[$0]++'
}

# 仓库里实际存在的全部扩展（一级目录 + __manifest__.py），自动发现的结果
all_repo_modules() {
    local dir mods=()
    for dir in "$REPO"/*/; do
        [[ -f "$dir/__manifest__.py" ]] || continue
        mods+=("$(basename "$dir")")
    done
    (IFS=,; echo "${mods[*]}")
}

# 要装的**本仓库扩展**：环境变量 DEV_ADDONS > .dev/init.yaml 的 addons > 自动发现全部。
# 名字必须是模块目录名（与该目录下的 __manifest__.py 对应）。
# 指定了清单就逐个校验：Odoo 对认不出的模块名只打 warning、不报错，不提前拦住就会出现
# 「以为装了其实一直缺」的假象。删掉某项不会卸载已装的模块 —— 卸载请用网页「应用」。
repo_modules() {
    local val=""
    if [[ -n "${DEV_ADDONS:-}" ]]; then
        val="$DEV_ADDONS"
    elif [[ -f "$INIT_YAML" ]]; then
        val="$(yaml_get "$INIT_YAML" addons || true)"
    fi
    if [[ -z "$val" ]]; then                       # 没配 → 自动发现，一个不漏
        all_repo_modules
        return 0
    fi
    local mod mods=() bad=()
    while IFS= read -r mod; do
        [[ -n "$mod" ]] || continue
        if [[ -f "$REPO/$mod/__manifest__.py" ]]; then
            mods+=("$mod")
        else
            bad+=("$mod")
        fi
    done < <(tr ', \t' '\n\n\n' <<<"$val" | awk 'NF && !seen[$0]++')
    if [[ ${#bad[@]} -gt 0 ]]; then
        warn "addons 里这些名字在仓库里找不到：$(IFS=,; echo "${bad[*]}")（已跳过）"
        warn "仓库里实际有的扩展：$(all_repo_modules)"
    fi
    (IFS=,; echo "${mods[*]}")
}

# 一次性 odoo 进程：不占用 8069，也不依赖服务是否在跑
odoo_run() { "${COMPOSE[@]}" run --rm -T odoo odoo "$@"; }

# 该装但还没装的模块（库不存在时视为「全都要装」）= 清单 + 仓库自研模块 的差集
missing_modules() {
    local have want=()
    # 这里刻意不用 `|| true` 之外的处理：库不存在 / psql 失败时 have 为空，等价于全新库
    have="$("${COMPOSE[@]}" exec -T db psql -U odoo -d "$DEV_DB" -tAc \
        "select name from ir_module_module where state='installed'" 2>/dev/null || true)"
    while IFS= read -r mod; do
        [[ -n "$mod" ]] || continue
        grep -qx "$mod" <<<"$have" || want+=("$mod")
    done < <({ list_modules; repo_modules | tr ',' '\n'; } | awk 'NF && !seen[$0]++')
    (IFS=,; echo "${want[*]}")
}

# 库里已激活的语言（库不存在 / 查询失败 → 空，等价于「都还没装」）
active_langs() {
    "${COMPOSE[@]}" exec -T db psql -U odoo -d "$DEV_DB" -tAc \
        "select code from res_lang where active" 2>/dev/null || true
}

missing_langs() {
    local have want=()
    have="$(active_langs)"
    while IFS= read -r code; do
        [[ -n "$code" ]] || continue
        grep -qx "$code" <<<"$have" || want+=("$code")
    done < <(list_langs)
    (IFS=,; echo "${want[*]}")
}

# 装语言 = 激活 res.lang + 把各模块 i18n/<lang>.po（与官方 i18n_extra）灌进库。
# 走 Odoo 自己的 load_language（= 网页「设置 → 语言 → 添加语言」那条路径），
# 不能只把 active 置 True：那样译文不进库，界面会中英文混着来。
install_langs() {
    local want="$1" tmp
    tmp="$(mktemp)"
    cat > "$tmp" <<PYEOF
from odoo.tools.translate import load_language

wanted = [c for c in "$want".split(',') if c]
Lang = env['res.lang'].with_context(active_test=False)
for code in wanted:
    lang = Lang.search([('code', '=', code)], limit=1)
    if not lang:
        print("[警告] Odoo 里没有语言 %s，跳过" % code)
        continue
    if lang.active:
        print("[信息] 语言已激活，跳过：%s" % code)
        continue
    print("[信息] 安装语言并加载译文：%s（首次要几分钟，别打断）" % code)
    load_language(env.cr, code)
    env.cr.commit()
    print("[信息] 完成：%s" % code)
PYEOF
    "${COMPOSE[@]}" run --rm -T odoo odoo shell --log-level=warn -d "$DEV_DB" < "$tmp"
    rm -f "$tmp"
}

# --- 演示数据自带的批次（tracking='lot'）-------------------------------------
# stock / product 的演示数据里写死了 <field name="tracking">lot</field>
# （stock/data/stock_demo.xml、stock_demo2.xml），所以 --fresh 重建后一定有几个演示产品
# 带批次，库存里还躺着 stock.lot / stock.quant，看上去像「批次功能被打开了」。
# 演示数据只在模块安装那一刻灌进去、事后补不了，所以只能在装完之后把这几个产品恢复成
# 「按数量」：在库数量归零 → 删批次 → tracking 改回 none。
# 只认**有 ir.model.data 记录的**演示产品（UI 里自己录的产品没有），不碰自录数据；幂等。
#
# 例：库存里有 3 个演示产品带批次（Flipover / Drawer 来自 product 的 demo，
#     Cable Management Box 来自 stock 的 demo），跑完这 3 个都变回 By Quantity。
# 想保留批次（比如要拿演示数据练批次流程）：设 DEV_KEEP_DEMO_LOTS=1。

# 库里「带批次的演示产品」个数（没装 stock / 查不到 → 0）
demo_lot_count() {
    local n
    n="$("${COMPOSE[@]}" exec -T db psql -U odoo -d "$DEV_DB" -tAc \
        "select count(*) from ir_module_module where name='stock' and state='installed'" 2>/dev/null || true)"
    [[ "$n" == "1" ]] || { echo 0; return 0; }
    # 两种残留都算：产品 tracking 还是 lot，或者 tracking 已改但批次记录还在库里
    n="$("${COMPOSE[@]}" exec -T db psql -U odoo -d "$DEV_DB" -tAc \
        "select count(*) from product_template t \
          where exists (select 1 from ir_model_data d where d.res_id = t.id \
                        and d.model = 'product.template') \
            and (t.tracking <> 'none' \
                 or exists (select 1 from stock_lot l \
                            join product_product pp on pp.id = l.product_id \
                            where pp.product_tmpl_id = t.id))" 2>/dev/null || true)"
    echo "${n:-0}"
}

cleanup_demo_lots() {
    local tmp
    tmp="$(mktemp)"
    cat > "$tmp" <<'PYEOF'
Tpl = env['product.template'].with_context(active_test=False)
Quant = env['stock.quant']
Lot = env['stock.lot']
Data = env['ir.model.data'].sudo()

# 演示数据创建的产品都带 ir.model.data 记录；UI 里自己录的产品没有 → 用它区分，避免误动自录数据
demo_ids = {d['res_id'] for d in Data.search_read(
    [('model', '=', 'product.template')], ['res_id'], limit=None)}
# 两种残留都算：tracking 还是 lot，或者 tracking 已改 none 但批次记录还躺在库里
lot_tmpl_ids = Lot.search([]).mapped('product_id.product_tmpl_id').ids
products = Tpl.search([
    ('id', 'in', list(demo_ids)),
    '|', ('tracking', '!=', 'none'), ('id', 'in', lot_tmpl_ids),
])

for t in products:
    print("[信息] 清掉演示产品的批次：%s（%s）" % (t.display_name, t.tracking))
    # 1) 先把 tracking 改回「按数量」，后面的库存调整才不会被要求填批次
    t.tracking = 'none'
    # 2) 在库数量归零（走库存调整，留痕）
    quants = Quant.search([('product_id.product_tmpl_id', '=', t.id), ('quantity', '!=', 0)])
    if quants:
        quants.with_context(inventory_mode=True).write({'inventory_quantity': 0})
        quants.with_context(inventory_mode=True).action_apply_inventory()
    # 3) 删批次记录：stock_quant.lot_id 有外键，得先删掉引用它的 0 库存 quant，再删 lot
    lots = Lot.search([('product_id.product_tmpl_id', '=', t.id)])
    if lots:
        try:
            with env.cr.savepoint():
                # 库存已归零，这些 quant 只是残行，删掉才能解开 lot 的外键
                Quant.search([('lot_id', 'in', lots.ids), ('quantity', '=', 0)]).unlink()
                lots.unlink()
        except Exception as err:
            print("[警告] %s 的批次没删掉（%s）；tracking 已改回 none，不影响使用" % (t.display_name, err))

env.cr.commit()
print("[信息] 演示产品批次清理完成：处理 %d 个产品" % len(products))
PYEOF
    "${COMPOSE[@]}" run --rm -T odoo odoo shell --log-level=warn -d "$DEV_DB" < "$tmp"
    rm -f "$tmp"
}

odoo_running() {
    "${COMPOSE[@]}" ps --status running --services 2>/dev/null | grep -qx odoo
}

# --- 1) 先把 db 拉起来（后面要用 psql 查已装模块） ---------------------------
"${COMPOSE[@]}" up -d db >/dev/null

# --- 2) --fresh：停 odoo → 删库（有连接删不掉，所以必须先停）-----------------
if [[ "$FRESH" == 1 ]]; then
    info "--fresh：删除库 $DEV_DB 并重建（演示数据会重新加载）"
    "${COMPOSE[@]}" stop odoo >/dev/null 2>&1 || true
    odoo_run db drop "$DEV_DB" >/dev/null 2>&1 || true
fi

# --- 3) 装模块（首次安装时连带 base / 依赖 / 演示数据）------------------------
# --with-demo 必须显式给：Odoo 19 起 CLI 默认**不装**演示数据（`--without-demo` 只是
# 保留的取反别名，19.0 的默认值是「不装」）。演示数据只在「模块安装的那一刻」灌进去，
# 所以已装好的库想补演示数据，只能 --fresh 重建。
WANT="$(missing_modules)"
INSTALLED=0
if [[ -n "$WANT" ]]; then
    info "安装模块（含演示数据）：$WANT"
    if ! odoo_run --with-demo -d "$DEV_DB" -i "$WANT" --stop-after-init; then
        warn "模块安装失败：先看上面的报错（依赖缺失 / 迁移脚本报错 / 模块代码本身有问题）"
        exit 1
    fi
    INSTALLED=1
    # 装完复查：Odoo 对**清单里认不出的模块名只打 warning（invalid module names, ignored）、
    # 不会让命令失败**（odoo/modules/loading.py 的 _check_module_names），不复查就会出现
    # 「以为装成功了、其实一直是缺的」这种假象。
    STILL_MISSING="$(missing_modules)"
    if [[ -n "$STILL_MISSING" ]]; then
        warn "这些模块没装上：$STILL_MISSING"
        warn "多半是 $INIT_YAML 的 modules（官方 / 第三方）里名字写错了（要写模块技术名，如 sale_management，不是 Sales）——Odoo 只在日志里打 warning"
    fi
else
    info "模块齐全，跳过安装"
fi

# --- 4) 装语言（放在装模块之后：新模块的译文才会被一并灌进去）------------------
LANGS="$(list_langs | paste -sd, -)"
WANT_LANGS="$(missing_langs)"
if [[ -n "$WANT_LANGS" ]]; then
    info "安装语言（含全部译文，可能要几分钟）：$WANT_LANGS"
    # 语言 code 写错（如写成 English）会在这里失败
    if ! install_langs "$WANT_LANGS"; then
        warn "装语言失败：检查 $INIT_YAML 的 langs（或 DEV_LANGS）里是不是语言 code（en_US / zh_CN 这种），不是语言名字"
        exit 1
    fi
else
    info "语言齐全，跳过（$LANGS）"
fi

# --- 5) 装过模块且 odoo 已在跑 → 重启一次让它加载新模块 -----------------------
# 装语言不用重启：res.lang 激活即时生效，网页刷新一次即可在用户偏好里选语言
if [[ "$INSTALLED" == 1 ]] && odoo_running; then
    info "重启 odoo 让新装的模块生效"
    "${COMPOSE[@]}" restart odoo >/dev/null
fi

# --- 6) 清掉演示数据自带的批次（tracking='lot' → 'none'）----------------------
# 幂等：没有带批次的演示产品就什么都不做，所以每次 task init 都会跑到、但只清理一次。
# 清完再想拿演示数据练批次流程：DEV_KEEP_DEMO_LOTS=1 task init
if [[ -n "${DEV_KEEP_DEMO_LOTS:-}" ]]; then
    info "DEV_KEEP_DEMO_LOTS 已设置，保留演示数据的批次"
else
    DEMO_LOTS="$(demo_lot_count)"
    if [[ "$DEMO_LOTS" =~ ^[0-9]+$ ]] && [[ "$DEMO_LOTS" -gt 0 ]]; then
        info "清掉演示数据自带的批次：$DEMO_LOTS 个演示产品 tracking=lot → none"
        cleanup_demo_lots
    else
        info "没有带批次的演示产品，跳过清理"
    fi
fi

cat <<EOF
[信息] 库 ${DEV_DB} 已就绪：
  · 网页登录    http://localhost:8069 → admin / admin（Odoo 建库默认，本脚本不碰）
  · 数据库账号  odoo / odoo（compose 的 POSTGRES_USER / POSTGRES_PASSWORD）
  · 安装配置    $INIT_YAML（modules / addons / langs，改完跑 task init 即可，不用重启容器）
  · 官方模块    $(list_modules | paste -sd, -)（Odoo 自带 / 第三方，写 modules）
  · 本仓库扩展  $(repo_modules)（写 addons；留空 = 自动发现全部）
  · 语言        ${LANGS}（网页右上角用户偏好里切换界面语言）
  · 演示数据    随首次安装加载（要重新加载就 --fresh，或 task reset 后 task up）
  · 演示批次    已清掉（演示数据写死的 tracking=lot 改回 none；要留着就 DEV_KEEP_DEMO_LOTS=1）
EOF
