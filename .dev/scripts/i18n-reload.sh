#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 强制刷新译文（改了 .po 里**已有**的译文之后要跑，`-u` 不会覆盖旧值）
#
# 平时从仓库根目录调用：task i18n -- zh_CN <模块...>
# 也可以直接跑本脚本：
#
#   bash .dev/scripts/i18n-reload.sh zh_CN product_image product_packing
#   bash .dev/scripts/i18n-reload.sh zh_CN              # 不传模块 = 全部（慢）
#
# 背景见 AGENTS.md 4.8 第 9 条：这些记录 noupdate=True，只有 force_overwrite 才会更新；
# 前端术语（JS _t / QWeb 文本）刷完还要强刷浏览器（AGENTS.md 4.7）。
#
# 走 `docker compose run --rm` + odoo shell，不依赖服务是否在跑。
# ---------------------------------------------------------------------------
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"          # .dev/scripts
DEV_DIR="$(cd "$HERE/.." && pwd)"              # .dev
COMPOSE=(docker compose -f "$DEV_DIR/compose.yml")
# 不传 -c：配置由 compose 里的 ODOO_RC 指定（子命令必须写在最前面，见 compose 注释）
DEV_DB="${DEV_DB:-dev}"

LANG_CODE="${1:-zh_CN}"
shift || true
MODULES="$*"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

cat > "$TMP" <<PYEOF
import os, glob
from odoo.tools import config
from odoo.tools.translate import TranslationImporter

lang = "${LANG_CODE}"
modules = [m.strip() for m in "${MODULES}".split(',') if m.strip()]

# Odoo 19 里 config['addons_path'] 已经是 list（老版本是逗号分隔字符串），两种都兜住
addons = config['addons_path']
if isinstance(addons, str):
    addons = addons.split(',')

po_files, seen = [], set()
for root in addons:
    root = root.strip()
    if not root:
        continue
    for po in sorted(glob.glob(os.path.join(root, '*/i18n', lang + '.po'))):
        module_name = po[len(root):].strip(os.sep).split(os.sep)[0]
        if modules and module_name not in modules:
            continue
        if po not in seen:
            seen.add(po)
            po_files.append(po)

if not po_files:
    print("没找到任何 %s.po：检查模块名是否写错" % lang)

for po in po_files:
    importer = TranslationImporter(env.cr)
    importer.load_file(po, lang)
    importer.save(force_overwrite=True)
    print("已强制刷新：", po)

env.cr.commit()
print("完成，共处理 %d 个 po 文件" % len(po_files))
PYEOF

echo "[信息] 强制刷新 ${LANG_CODE} 译文（库 ${DEV_DB}）"
"${COMPOSE[@]}" run --rm -T odoo \
    odoo shell --log-level=warn -d "$DEV_DB" < "$TMP"
