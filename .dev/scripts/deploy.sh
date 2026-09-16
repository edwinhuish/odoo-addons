#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 发布到服务器（本地验收通过之后的最后一步）
#
# 平时从仓库根目录调用：DEPLOY_HOST=... task deploy
# 也可以直接跑本脚本：
#
#   bash .dev/scripts/deploy.sh
#   MODULES=product_image bash .dev/scripts/deploy.sh     # 同步后顺带升级模块
#   DRY_RUN=1 bash .dev/scripts/deploy.sh                 # 只看会传什么
#
# 需要：DEPLOY_HOST（用户@服务器）、DEPLOY_PATH、DEPLOY_SERVICE（可选）
# 建议先 db-sync.sh pull 把服务器数据拉进来验证，通过后再发布。
# 这个脚本全程在宿主机跑，不依赖容器。
# ---------------------------------------------------------------------------
set -euo pipefail

: "${DEPLOY_HOST:?需要 DEPLOY_HOST=用户@服务器}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/odoo-addons}"
DEPLOY_SERVICE="${DEPLOY_SERVICE:-odoo}"

REPO="$(cd "$(dirname "$0")/../.." && pwd)"    # .dev/scripts → 仓库根
cd "$REPO"

info() { echo "[信息] $*"; }
warn() { echo "[警告] $*" >&2; }

if [[ -n "$(git status --porcelain)" ]]; then
    warn "工作区不干净，未提交的内容也会同步上去："
    git status --short
    read -r -p "继续？(y/N) " ans
    [[ "$ans" =~ ^[Yy]$ ]] || exit 1
fi

RSYNC_ARGS=(-a --info=stats2 --human-readable --delete
            --exclude '.git/' --exclude '__pycache__/' --exclude '*.pyc'
            --exclude '.claude/' --exclude '.codebuddy/'
            --exclude '.dev/backups/' --exclude '.dev/data/')

if [[ "${DRY_RUN:-0}" == "1" ]]; then
    RSYNC_ARGS+=(--dry-run)
fi

info "同步 $REPO → $DEPLOY_HOST:$DEPLOY_PATH"
rsync "${RSYNC_ARGS[@]}" "$REPO/" "$DEPLOY_HOST:$DEPLOY_PATH/"

if [[ "${DRY_RUN:-0}" == "1" ]]; then
    info "DRY_RUN：未做任何实际改动"
    exit 0
fi

if [[ -n "${MODULES:-}" ]]; then
    info "升级模块 $MODULES"
    ssh "$DEPLOY_HOST" "cd $DEPLOY_PATH && odoo -c /etc/odoo.conf -d ${DEPLOY_DB:-prod} -u ${MODULES} --stop-after-init"
fi

info "重启 ${DEPLOY_SERVICE}"
ssh "$DEPLOY_HOST" "sudo systemctl restart ${DEPLOY_SERVICE}"

info "服务器日志：ssh $DEPLOY_HOST 'journalctl -u ${DEPLOY_SERVICE} -f'"
