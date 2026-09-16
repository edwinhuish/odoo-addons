#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 开发库初始化 / 补齐（幂等）—— 让「重建容器后还要手工装模块、改密码」这件事消失
#
# 目标状态（本仓库本地开发约定）：
#   · 数据库账号     odoo / odoo（compose 里的 POSTGRES_USER / POSTGRES_PASSWORD）
#   · 业务模块       sale_management(Sales) / purchase / stock(Inventory)
#   · 本仓库所有模块 自动发现（根目录下有 __manifest__.py 的一级目录，一个都不漏）
#   · 演示数据       随首次安装一起加载（显式 `--with-demo`：Odoo 19 的 CLI 默认不装）
#
# 平时由 Taskfile 调，也可以直接跑：
#   bash .dev/scripts/init-db.sh               # 库不在就整套装上；在就只补缺失模块
#   bash .dev/scripts/init-db.sh --fresh       # 删库重建（演示数据只有这一次机会，装上才有）
#   DEV_DB=other bash .dev/scripts/init-db.sh  # 换库名
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
# 业务模块用**技术名**：Sales 是 sale_management（sale + sales_team 会自动带上），
# Inventory 是 stock。写中文/应用名是装不上的。
BUSINESS_MODULES="sale_management,purchase,stock"

FRESH=0
for arg in "$@"; do
    case "$arg" in
        --fresh) FRESH=1 ;;
        *) echo "[错误] 不认识的参数：$arg（只支持 --fresh）" >&2; exit 2 ;;
    esac
done

info() { echo "[信息] $*"; }
warn() { echo "[警告] $*" >&2; }

# 本仓库的模块：一级目录 + __manifest__.py
repo_modules() {
    local dir mods=()
    for dir in "$REPO"/*/; do
        [[ -f "$dir/__manifest__.py" ]] || continue
        mods+=("$(basename "$dir")")
    done
    (IFS=,; echo "${mods[*]}")
}

# 一次性 odoo 进程：不占用 8069，也不依赖服务是否在跑
odoo_run() { "${COMPOSE[@]}" run --rm -T odoo odoo "$@"; }

# 该装但还没装的模块（库不存在时视为「全都要装」）
missing_modules() {
    local have want=()
    # 这里刻意不用 `|| true` 之外的处理：库不存在 / psql 失败时 have 为空，等价于全新库
    have="$("${COMPOSE[@]}" exec -T db psql -U odoo -d "$DEV_DB" -tAc \
        "select name from ir_module_module where state='installed'" 2>/dev/null || true)"
    while IFS= read -r mod; do
        [[ -n "$mod" ]] || continue
        grep -qx "$mod" <<<"$have" || want+=("$mod")
    done < <(tr ',' '\n' <<<"$BUSINESS_MODULES"; tr ',' '\n' <<<"$(repo_modules)")
    (IFS=,; echo "${want[*]}")
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
    odoo_run --with-demo -d "$DEV_DB" -i "$WANT" --stop-after-init
    INSTALLED=1
else
    info "模块齐全，跳过安装"
fi

# --- 4) 装过模块且 odoo 已在跑 → 重启一次让它加载新模块 -----------------------
if [[ "$INSTALLED" == 1 ]] && odoo_running; then
    info "重启 odoo 让新装的模块生效"
    "${COMPOSE[@]}" restart odoo >/dev/null
fi

cat <<EOF
[信息] 库 ${DEV_DB} 已就绪：
  · 网页登录    http://localhost:8069 → admin / admin（Odoo 建库默认，本脚本不碰）
  · 数据库账号  odoo / odoo（compose 的 POSTGRES_USER / POSTGRES_PASSWORD）
  · 业务模块    sale_management(Sales) / purchase / stock(Inventory)
  · 仓库模块    $(repo_modules)
  · 演示数据    随首次安装加载（要重新加载就 --fresh，或 task reset 后 task up）
EOF
