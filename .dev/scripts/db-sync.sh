#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 数据库同步：把服务器现场搬进本地容器，这是「复现问题」的关键
#
# 平时从仓库根目录用统一入口调用：task pull / task db-sync -- <子命令>
# 也可以直接跑本脚本：
#
#   bash .dev/scripts/db-sync.sh pull                  # 服务器 → 本地 dev 库
#   bash .dev/scripts/db-sync.sh load <dump.zip> [库]  # 装载本地备份
#   bash .dev/scripts/db-sync.sh duplicate dev bak     # 复制一份，改坏了再复制回来
#   bash .dev/scripts/db-sync.sh dump [库] [out.zip]   # 备份本地库
#
# pull 需要的环境变量（按需传，不写死）：
#   SSH_HOST=odoo@server SSH_PORT=22 REMOTE_DB=prod \
#   REMOTE_ODOO_DIR=/opt/odoo REMOTE_ODOO_CONF=/etc/odoo.conf
#   （REMOTE_* 是**服务器上**的路径，跟容器无关）
#
# 为什么用 Odoo 的 zip 备份而不是裸 pg_dump：zip 里同时含 filestore，
# 产品图片、附件（product_image / sale_order_no 强依赖）才不会变成空图。
#
# 全部走 `docker compose run --rm`：不依赖 Odoo 服务是否在跑，也不占用 8069。
# ---------------------------------------------------------------------------
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"          # .dev/scripts
DEV_DIR="$(cd "$HERE/.." && pwd)"              # .dev
COMPOSE=(docker compose -f "$DEV_DIR/compose.yml")
BACKUP_DIR="$DEV_DIR/backups"
# 容器里能看到的位置：仓库挂在 /mnt/extra-addons
CT_BACKUP_DIR=/mnt/extra-addons/.dev/backups

DEV_DB="${DEV_DB:-dev}"

info() { echo "[信息] $*"; }
die()  { echo "[错误] $*" >&2; exit 1; }

# 不传 -c：配置由 compose 的 ODOO_RC 提供。
# 注意 Odoo 的 CLI 只看 argv[0]（odoo/cli/command.py:119），子命令必须写在最前面：
#   odoo db dump dev /path       ✅
#   odoo -c conf db dump dev ... ❌ 会被当成 server 命令，报 unrecognized parameters
mkdir -p "$BACKUP_DIR"
odoo_run() { "${COMPOSE[@]}" run --rm -T odoo odoo "$@"; }

case "${1:-}" in

  pull)
    : "${SSH_HOST:?需要 SSH_HOST=用户@服务器}"
    SSH_PORT="${SSH_PORT:-22}"
    REMOTE_DB="${REMOTE_DB:?需要 REMOTE_DB=服务器库名}"
    REMOTE_ODOO_DIR="${REMOTE_ODOO_DIR:-/opt/odoo}"
    REMOTE_ODOO_CONF="${REMOTE_ODOO_CONF:-/etc/odoo.conf}"

    stamp="$(date +%Y%m%d-%H%M)"
    remote_file="/tmp/${REMOTE_DB}-${stamp}.zip"
    local_file="$BACKUP_DIR/${REMOTE_DB}-${stamp}.zip"

    info "在 ${SSH_HOST} 上导出 ${REMOTE_DB}（含 filestore）"
    ssh -p "$SSH_PORT" "$SSH_HOST" \
        "cd ${REMOTE_ODOO_DIR} && ./odoo-bin db -c ${REMOTE_ODOO_CONF} dump ${REMOTE_DB} ${remote_file} --format zip"

    info "下载到 $local_file"
    scp -P "$SSH_PORT" "$SSH_HOST:${remote_file}" "$local_file"
    ssh -p "$SSH_PORT" "$SSH_HOST" "rm -f ${remote_file}"

    info "装载为本地库 ${DEV_DB}（顺带 neutralize：禁邮件 / 禁外部凭据）"
    odoo_run db load -f -n "$DEV_DB" \
        "$CT_BACKUP_DIR/$(basename "$local_file")"
    info "完成：http://localhost:8069 库 ${DEV_DB}"
    ;;

  load)
    dump="${2:?用法：$0 load <dump.zip> [库名]}"
    db="${3:-$DEV_DB}"
    [[ -f "$dump" ]] || die "找不到 $dump"
    # 统一成绝对路径再比较（传进来的可能是相对路径），否则「已在备份目录里」判断会失效
    dump="$(cd "$(dirname "$dump")" && pwd)/$(basename "$dump")"
    # 备份目录里的文件不用再拷：拷贝只是为了让容器能按挂载路径读到它
    if [[ "$dump" != "$BACKUP_DIR"/* ]]; then
        cp -f "$dump" "$BACKUP_DIR/"
    fi
    odoo_run db load -f -n "$db" "$CT_BACKUP_DIR/$(basename "$dump")"
    ;;

  duplicate)
    src="${2:?用法：$0 duplicate <源库> <目标库>}"
    dst="${3:?用法：$0 duplicate <源库> <目标库>}"
    odoo_run db duplicate -f -n "$src" "$dst"
    info "已生成 $dst"
    ;;

  dump)
    db="${2:-$DEV_DB}"
    out="${3:-$BACKUP_DIR/${db}-$(date +%Y%m%d-%H%M).zip}"
    info "导出 ${db} → $out"
    # 走 stdout（dump_path 传 `-`）：少一次容器内落盘，也不受容器用户与宿主机 uid 是否一致的
    # 影响（容器进程身份已按 PUID/PGID 对齐宿主机用户）。
    "${COMPOSE[@]}" run --rm -T odoo odoo db dump "$db" - > "$out"
    info "已备份到 $out"
    ;;

  *)
    cat <<EOF
用法：$0 {pull|load|duplicate|dump} [参数]

  pull                      从服务器拉最新备份并装载为本地 ${DEV_DB}
  load  <dump.zip> [库名]    装载本地备份
  duplicate <源库> <目标库>  本地复制一份，改坏了可以再复制回来
  dump  [库名] [out.zip]     备份本地库

常用组合（复现生产问题）：
  bash .dev/scripts/db-sync.sh pull
  bash .dev/scripts/db-sync.sh duplicate dev dev_clean    # 留一个干净副本再折腾
EOF
    exit 1
    ;;
esac
