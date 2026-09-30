#!/bin/sh
# ---------------------------------------------------------------------------
# 通用容器入口脚本（POSIX sh / busybox，面向 Alpine 基础镜像）：
#   以 root 启动 → 按 PUID/PGID 对齐容器内的用户、组与目录属主 → 降权 → 执行命令。
#
# 用途：让容器里的进程以宿主机的 uid:gid 运行，这样在绑定挂载的目录里读写文件
# 既不会 Permission denied，也不会留下 root 属主的文件。改动只发生在当前容器内
# （/etc/passwd、/etc/group、目录属主），不影响宿主机；容器重建后即从镜像恢复。
#
# 运行时变量（全部可选，改完重启容器即生效，无需重建镜像）：
#   PUID        降权后的目标 uid，默认 1000
#   PGID        降权后的目标 gid，默认 1000
#   USER        目标用户名，默认 app
#   HOME        传给子进程的 HOME，默认 /home/$USER
#   CHOWN_SRC   需要归到 PUID:PGID 的目录，空格分隔可写多个，默认 $HOME
#
# 处理顺序：
#   1. 腾位：PUID 已被别的账号占用时，把占用者挪到空闲 uid（从 2000 起找）；
#      uid 0（root）不挪，只能共用，日志告警。
#   2. 对齐组：PGID 在本容器内已存在 → 直接复用该组，绝不新建；不存在才建同名组。
#   3. 对齐用户：不存在 → 按 PUID:PGID 新建；已存在 → 改写其 uid/gid。
#   4. 目录属主：CHOWN_SRC 里的目录递归归到 PUID:PGID（顶层属主已正确则整段跳过，
#      避免每次启动都递归遍历大目录）。
#   5. 降权：su-exec 切到 PUID:PGID（会重置补充组）后原样执行传入的命令。
#
# 依赖：busybox 提供的 sh / awk / mktemp / stat / chown / adduser / addgroup，
#       以及 su-exec（Alpine 上 `apk add su-exec`）。
# 说明：本脚本只负责降权，不转发任何特定应用的入口；实际要跑的命令由镜像的
#       ENTRYPOINT 与容器 command 共同决定。
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

# --- 账号文件查询 ------------------------------------------------------------
# busybox 没有 getent，直接解析 /etc/passwd、/etc/group（awk 未命中也会返回 0）
pw_uid() { awk -F: -v n="$1" '$1 == n { print $3; exit }' /etc/passwd; }
pw_gid() { awk -F: -v n="$1" '$1 == n { print $4; exit }' /etc/passwd; }
pw_name() { awk -F: -v u="$1" '$3 == u { print $1; exit }' /etc/passwd; }
gr_gid() { awk -F: -v n="$1" '$1 == n { print $3; exit }' /etc/group; }
gr_name() { awk -F: -v g="$1" '$3 == g { print $1; exit }' /etc/group; }

# 就地改写 /etc/passwd、/etc/group：先写临时文件再回灌原路径，
# 保留原文件 inode（这两个文件有时是挂载进来的，直接 mv 会破坏挂载点）
rewrite_file() {
    _src="$1"
    _tmp="$(mktemp)"
    cat > "$_tmp"
    cat "$_tmp" > "$_src"
    rm -f "$_tmp"
}

# 只改某账号的 uid（其余字段不动）
set_uid() {
    awk -F: -v OFS=: -v n="$1" -v u="$2" '$1 == n { $3 = u } { print }' /etc/passwd \
        | rewrite_file /etc/passwd
}

# 只改某个组的 gid（其余字段不动）
set_gid() {
    awk -F: -v OFS=: -v n="$1" -v g="$2" '$1 == n { $3 = g } { print }' /etc/group \
        | rewrite_file /etc/group
}

# 同时改某账号的 uid 与 gid
set_user_ids() {
    awk -F: -v OFS=: -v n="$1" -v u="$2" -v g="$3" \
        '$1 == n { $3 = u; $4 = g } { print }' /etc/passwd \
        | rewrite_file /etc/passwd
}

# 找一个空闲 id：$1 = 查询函数名（pw_name 查用户 / gr_name 查组）。
# 从 2000 起，避开 1-999 系统账号区间
find_free_id() {
    _id=2000
    while [ "$_id" -lt 65000 ]; do
        if [ -z "$("$1" "$_id")" ]; then
            printf '%s\n' "$_id"
            return 0
        fi
        _id=$((_id + 1))
    done
    return 1
}

# --- 1) 腾位：把占用 PUID 的账号挪走，给目标用户让位 -------------------------
free_uid() {
    _occupant="$(pw_name "$PUID")"
    if [ -z "$_occupant" ]; then
        return 0                       # 没人占用
    fi
    if [ "$_occupant" = "$USER" ]; then
        return 0                       # 占用的就是目标用户自己
    fi

    if [ "$PUID" -eq 0 ]; then
        warn "uid 0 属于 root，不能腾位：$USER 将与 root 共用 uid 0（等于以 root 运行，慎用）"
        return 0
    fi

    _free="$(find_free_id pw_name || true)"
    if [ -z "$_free" ]; then
        warn "找不到空闲 uid，$_occupant 保持原样"
        return 0
    fi
    if [ "$PUID" -lt 1000 ]; then
        warn "uid $PUID 落在系统账号区间，改动 $_occupant 可能有副作用"
    fi

    info "uid $PUID 已被 $_occupant 占用 → 把它改到 uid $_free"
    set_uid "$_occupant" "$_free"
}

# --- 2) 对齐组：复用已有 gid，否则新建 ---------------------------------------
# 目标 gid 已被容器内某个组占用时，**不新建组、也不改名**，直接复用该组；
# 只有 gid 空闲时才建（优先复用同名组，没有同名组才新建）
resolve_group() {
    _existing="$(gr_name "$PGID")"
    if [ -n "$_existing" ]; then
        if [ "$PGID" -lt 1000 ]; then
            warn "gid $PGID 落在系统组区间，将直接复用系统组 $_existing"
        fi
        info "gid $PGID 已被组 $_existing 占用 → 直接复用，不新建组"
        GRP="$_existing"
        return 0
    fi

    GRP="$USER"
    if [ -n "$(gr_gid "$USER")" ]; then
        info "把组 $USER 的 gid 改为 $PGID"
        set_gid "$USER" "$PGID"
    else
        info "新建组 $USER（gid $PGID）"
        addgroup -g "$PGID" "$USER"
    fi
}

# --- 3) 对齐用户：不存在则新建，已存在则改写 uid/gid -------------------------
ensure_user() {
    _uid="$(pw_uid "$USER")"
    if [ -z "$_uid" ]; then
        info "用户 $USER 不存在，按 ${PUID}:${PGID} 新建（主组 $GRP）"
        adduser -D -H -u "$PUID" -G "$GRP" -s /bin/sh "$USER"
        return 0
    fi

    _gid="$(pw_gid "$USER")"
    if [ "$_uid" != "$PUID" ] || [ "$_gid" != "$PGID" ]; then
        info "把 $USER 的 uid:gid 从 ${_uid}:${_gid} 改为 ${PUID}:${PGID}"
        set_user_ids "$USER" "$PUID" "$PGID"
    fi
}

# --- 参数校验 ----------------------------------------------------------------
case "$PUID" in
    '' | *[!0-9]*) die "PUID 必须是数字，当前值：$PUID" ;;
esac
case "$PGID" in
    '' | *[!0-9]*) die "PGID 必须是数字，当前值：$PGID" ;;
esac
if [ -z "$USER" ]; then
    die "USER 不能为空"
fi

free_uid
resolve_group
ensure_user

# --- 4) 目录属主：把绑定挂载的源目录归到 PUID:PGID ---------------------------
# 顶层目录属主已经对了就整段跳过：chown -R 会递归遍历整个目录，数据一多每次启动
# 都要白跑一遍。代价是嵌套层里出现异常属主时不会被自动纠正，需要时手动 chown -R 修正。
for _dir in $CHOWN_SRC; do
    if [ ! -e "$_dir" ]; then
        warn "$_dir 不存在，跳过（绑定挂载的源目录需先在宿主机上建好）"
        continue
    fi
    _cur="$(stat -c '%u:%g' "$_dir" 2>/dev/null || printf '未知')"
    if [ "$_cur" = "${PUID}:${PGID}" ]; then
        continue
    fi
    info "把 $_dir 属主从 $_cur 改为 ${PUID}:${PGID}（递归）"
    chown -R "${PUID}:${PGID}" "$_dir"
done

# --- 5) 降权后原样执行传入的命令 ---------------------------------------------
if [ "$#" -eq 0 ]; then
    die "没有要执行的命令：镜像的 ENTRYPOINT / 容器的 command 是空的？"
fi

if ! command -v su-exec >/dev/null 2>&1; then
    die "未找到 su-exec（Alpine 上请先 apk add su-exec），无法降权执行"
fi

exec su-exec "${PUID}:${PGID}" \
    env HOME="$HOME" USER="$USER" LOGNAME="$USER" \
    "$@"
