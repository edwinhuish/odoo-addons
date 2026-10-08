#!/bin/sh
# ---------------------------------------------------------------------------
# 通用容器入口（POSIX sh / Alpine）：
#   以 root 启动 → 按 PUID/PGID 对齐账号与目录属主 → 降权后执行传入的命令。
#   目的是让容器内进程以宿主机的 uid:gid 运行，绑定挂载目录读写不会 Permission
#   denied，也不会留下 root 属主的文件；改动只落在当前容器内，重建即还原。
#
# 变量（均可选，改完重启容器即生效）：
#   PUID      目标 uid，默认 1000
#   PGID      目标 gid，默认 1000
#   USER      目标用户名，默认 app
#   HOME      传给子进程的 HOME，默认 /home/$USER
#   CHOWN_SRC 需要归到 PUID:PGID 的目录，空格分隔可写多个，默认 $HOME
#
# 账号对齐一律带 -o（--non-unique）：目标 uid/gid 已被别的账号占用时直接共用同一
# 数字 id，不报错，也无需事先检查占用情况。代价是按数字反查用户名只会命中先出现的
# 条目（如 `id 1000` 显示的是基础镜像自带账号名）；进程身份与文件属主只认数字 id。
#
# 依赖：shadow 的 useradd/usermod/groupadd/groupmod 与 su-exec
#       Alpine 上：apk add --no-cache shadow su-exec
# ---------------------------------------------------------------------------
set -eu

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
USER="${USER:-app}"
HOME="${HOME:-/home/$USER}"
CHOWN_SRC="${CHOWN_SRC:-$HOME}"

info() { printf '[INFO] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
die() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

case "$PUID" in
    '' | *[!0-9]*) die "PUID 必须是数字，当前值：$PUID" ;;
esac
case "$PGID" in
    '' | *[!0-9]*) die "PGID 必须是数字，当前值：$PGID" ;;
esac
if [ -z "$USER" ]; then
    die "USER 不能为空"
fi

for _tool in useradd usermod groupadd groupmod su-exec; do
    if ! command -v "$_tool" >/dev/null 2>&1; then
        die "未找到 $_tool（Alpine 上执行：apk add --no-cache shadow su-exec）"
    fi
done

# 组 / 用户：已存在就改 id，不存在就新建；-o 保证 id 被占用时也不报错。
# 先试改后试建，失败信息交给后一条命令暴露（usermod 的 "no changes" 提示走 stdout，也要吞掉）
groupmod -o -g "$PGID" "$USER" >/dev/null 2>&1 \
    || groupadd -o -g "$PGID" "$USER"
usermod -o -u "$PUID" -g "$PGID" "$USER" >/dev/null 2>&1 \
    || useradd -o -u "$PUID" -g "$PGID" -M -s /bin/sh "$USER"
info "目标身份：$USER（${PUID}:${PGID}）"

# 目录属主：顶层属主已正确就跳过，避免每次启动都递归 chown 大目录
for _dir in $CHOWN_SRC; do
    if [ ! -e "$_dir" ]; then
        warn "$_dir 不存在，跳过"
        continue
    fi
    _cur="$(stat -c '%u:%g' "$_dir" 2>/dev/null || printf '未知')"
    if [ "$_cur" = "${PUID}:${PGID}" ]; then
        continue
    fi
    info "把 $_dir 属主从 $_cur 改为 ${PUID}:${PGID}（递归）"
    chown -R "${PUID}:${PGID}" "$_dir"
done

if [ "$#" -eq 0 ]; then
    die "没有要执行的命令"
fi

exec su-exec "${PUID}:${PGID}" \
    env HOME="$HOME" USER="$USER" LOGNAME="$USER" \
    "$@"
