#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 容器入口（odoo 与 postgres 共用）：以 root 起 → 按 PUID/PGID 调好「用户 + 数据目录」
# → 降权 → 直接执行传进来的命令
#
# 变量（都是运行时的，改完 `task up` 即生效，不需要 `task rebuild`）：
#   PUID        目标 uid，默认 1000
#   PGID        目标 gid，默认 1000
#   USER        目标用户名，默认为当前容器里的值（odoo 服务是 odoo，pg 服务是 postgres）
#   HOME        传给孩子进程的 HOME，默认 /home/$USER
#   CHOWN_SRC   需要归到 PUID:PGID 的目录（就是绑定挂载进来的宿主机源目录），
#               空格分隔可写多个，默认 $HOME（odoo = /var/lib/odoo，pg = /var/lib/postgresql）
#
# 处理顺序：
#   1. 腾位置：PUID / PGID 已被别的账号占用时，把占用者挪到空闲 id（从 2000 起找），让位给 USER。
#      uid/gid 0（root）除外——root 不动，只能共用（会告警）。
#   2. 对齐用户：USER 不存在 → 按 PUID:PGID 新建；已存在 → 把它的 uid/gid 改成 PUID:PGID。
#   3. 目录属主：CHOWN_SRC 里每个目录归到 PUID:PGID —— 属主已经对了就跳过（避免每次启动递归 chown）。
#   4. setpriv 降权到 PUID:PGID，然后直接 exec 传进来的命令。
#
# 这里**不认识**官方 entrypoint：镜像的 ENTRYPOINT 已经把「要跑的官方 entrypoint」排在命令最前面
# （见 Dockerfile.odoo / Dockerfile.pg），本脚本只负责降权，之后原样执行，不做任何转发。
#
# 改 /etc/passwd 只影响**当前容器**（每次 `task up` 都从镜像重建），不会动宿主机。
#
# 注意：这里的 USER 就是容器环境里的 USER，odoo 镜像的官方 entrypoint 也拿它当**数据库用户名**，
# 所以两者天生同名。要换名字在 .dev/.env 里设 ODOO_USER（compose 负责映射成 USER）——
# **不要**在 .env 里直接写 USER：宿主机 shell 一般已导出 USER（如 edwin），compose 会把你的
# 登录名带进来，导致这里建出多余用户、数据库用户名也一起变。
# ---------------------------------------------------------------------------
set -euo pipefail

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
USER="${USER:-odoo}"
HOME="${HOME:-/home/$USER}"
CHOWN_SRC="${CHOWN_SRC:-$HOME}"

info() { echo "[entrypoint] $*"; }
warn() { echo "[entrypoint][警告] $*" >&2; }

# 找一个空闲 id：$1 = passwd | group。从 2000 起，避开 1-999 系统账号区间
find_free_id() {
    local id=2000
    while [ "$id" -lt 65000 ]; do
        getent "$1" "$id" >/dev/null || { echo "$id"; return 0; }
        id=$((id + 1))
    done
    return 1
}

# 把「占用 PUID 的账号」挪走，给 USER 让位
free_uid() {
    local occupant free
    # 注意：getent 查不到时返回 2，而这里开了 pipefail —— 必须 `|| true` 兜住，
    # 否则「目标 uid 空闲」这条路会直接把脚本杀掉（exit 2、且一行日志都没有）。
    occupant="$(getent passwd "$PUID" 2>/dev/null | cut -d: -f1)" || true
    [ -z "$occupant" ] && return 0          # 没人占用
    [ "$occupant" = "$USER" ] && return 0   # 占用的就是 USER 自己

    if [ "$PUID" -eq 0 ]; then
        warn "uid 0 属于 root，不能腾位：$USER 将与 root 共用 uid 0（等于以 root 跑，慎用）"
        return 0
    fi

    free="$(find_free_id passwd)" || { warn "找不到空闲 uid，$occupant 保持原样"; return 0; }
    [ "$PUID" -lt 1000 ] && warn "uid $PUID 落在系统账号区间，挪动 $occupant 可能有副作用"
    info "uid $PUID 被 $occupant 占用 → 把 $occupant 挪到 uid $free"
    usermod --uid "$free" "$occupant" >/dev/null 2>&1 \
        || warn "挪动 $occupant 失败，稍后用 --non-unique 兜底"
}

# 把「占用 PGID 的组」挪走，给 USER 的同名组让位
free_gid() {
    local occupant free
    occupant="$(getent group "$PGID" 2>/dev/null | cut -d: -f1)" || true   # 同上，getent 未命中是 2
    [ -z "$occupant" ] && return 0
    [ "$occupant" = "$USER" ] && return 0

    if [ "$PGID" -eq 0 ]; then
        warn "gid 0 属于 root 组，不能腾位：$USER 的主组将与 root 共用 gid 0（慎用）"
        return 0
    fi

    free="$(find_free_id group)" || { warn "找不到空闲 gid，$occupant 保持原样"; return 0; }
    [ "$PGID" -lt 1000 ] && warn "gid $PGID 落在系统账号区间，挪动组 $occupant 可能有副作用"
    info "gid $PGID 被组 $occupant 占用 → 把它挪到 gid $free"
    groupmod --gid "$free" "$occupant" >/dev/null 2>&1 \
        || warn "挪动组 $occupant 失败，稍后用 --non-unique 兜底"
}

# --- 1) 腾位置 --------------------------------------------------------------
free_uid
free_gid

# --- 2) 对齐 USER 的 uid/gid ------------------------------------------------
if ! getent passwd "$USER" >/dev/null; then
    info "用户 $USER 不存在，按 ${PUID}:${PGID} 新建"
    getent group "$PGID" >/dev/null || groupadd --gid "$PGID" "$USER"
    useradd --non-unique --uid "$PUID" --gid "$PGID" \
        --no-create-home --shell /bin/bash "$USER"
fi

if [ "$(id -u "$USER")" != "$PUID" ] || [ "$(id -g "$USER")" != "$PGID" ]; then
    # 先记原值——改组会改掉 id -g 的结果，日志要显示改动前的状态
    old_uid="$(id -u "$USER")"
    old_gid="$(id -g "$USER")"

    # USER 的同名组对齐到 PGID（没有同名组就建；--non-unique 兜住 gid 0 这类腾不开的情况）
    if getent group "$USER" >/dev/null; then
        groupmod --non-unique --gid "$PGID" "$USER"
    else
        groupadd --gid "$PGID" "$USER"
    fi

    info "把 $USER 的 uid:gid 从 ${old_uid}:${old_gid} 改为 ${PUID}:${PGID}"
    usermod --non-unique --uid "$PUID" --gid "$PGID" "$USER"
fi

# --- 3) 目录属主：把绑定挂载的宿主机源目录归到 PUID:PGID ---------------------
# 顶层目录属主已经对了就整段跳过：chown -R 会递归遍历 filestore / PGDATA，
# 数据一大每次启动都要白跑一遍。代价是嵌套层里出现异常属主时不会被自动纠正，
# 真遇到就手动 `sudo chown -R $(id -u):$(id -g) .dev/data/<x>`，或 `task reset` 重来。
for dir in $CHOWN_SRC; do
    if [ ! -e "$dir" ]; then
        warn "$dir 不存在（宿主机上的绑定源目录要先建好：task up 会先建 data/）"
        continue
    fi
    cur="$(stat -c '%u:%g' "$dir")"
    if [ "$cur" = "${PUID}:${PGID}" ]; then
        continue
    fi
    info "把 $dir 属主从 $cur 改为 ${PUID}:${PGID}（递归）"
    chown -R "$PUID:$PGID" "$dir"
done

# --- 4) 降权后直接执行命令（官方 entrypoint 已在命令最前面，见 Dockerfile） ----
if [ "$#" -eq 0 ]; then
    warn "没有要执行的命令：compose 里这个服务的 command 是空的？"
    exit 1
fi

exec setpriv --reuid "$PUID" --regid "$PGID" --clear-groups \
    env HOME="$HOME" USER="$USER" LOGNAME="$USER" USERNAME="$USER" \
    "$@"
