#!/usr/bin/env python3
"""仓库自检：把 AGENTS.md 4.6 的自校验固化成一条命令（同时用于 pre-commit）。

平时从仓库根目录调用：task check（或 task check -- --strict）

    python3 .dev/scripts/check_repo.py            # 结构性问题才算失败
    python3 .dev/scripts/check_repo.py --strict   # 连「残留中文界面文本」也算失败

检查项：
 1. i18n/*.po 里重复的 msgid（会导致整份译文导入失败）
 2. 应用列表元数据（shortdesc / summary / description）的 msgid 与 manifest 是否逐字符一致
 3. 源码里残留的中文界面文本（注释不算，需要人工判断的部分用 --strict 卡住）
 4. 所有 XML 是否合法（视图 / QWeb）
 5. JS 语法（需要 node）
 6. TODO.md 结构：条目格式、ID 唯一且待办池递增、模块目录存在、文档链接存在、「检测：」条件语法

退出码：0 通过；1 存在失败项。
"""

from __future__ import annotations

import argparse
import ast
import collections
import glob
import json
import os
import re
import subprocess
import sys
import textwrap
import xml.dom.minidom


def find_repo_root(start: str) -> str:
    """从脚本所在目录往上找 .git，脚本挪位置也不用改这里。"""
    path = start
    while True:
        if os.path.isdir(os.path.join(path, ".git")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            raise SystemExit(f"从 {start} 往上没找到 .git，确定在仓库里跑？")
        path = parent


REPO_ROOT = find_repo_root(os.path.dirname(os.path.abspath(__file__)))

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
MSGID_RE = re.compile(r'^msgid ((?:"(?:[^"\\]|\\.)*"\s*)+)', re.M)
PO_REF_RE = re.compile(r"^#: model:ir\.module\.module,(\w+):base\.module_(\w+)$", re.M)
MODULE_COMMENT_RE = re.compile(r"^#\.\s*module:\s*(\w+)", re.M)
METADATA_KEYS = {"shortdesc": "name", "summary": "summary", "description": "description"}

# ---------------------------------------------------------------------------
# TODO.md（根 AGENTS.md 第 8 节）：结构检查 + 供 .dev/scripts/todo_status.py 复用的解析
# ---------------------------------------------------------------------------

TODO_FILE = os.path.join(REPO_ROOT, "TODO.md")
# 严格区：条目格式由 TODO.md「追加规则 2」定义
TODO_STRICT_SECTIONS = ("进行中", "待办池")
TODO_ARCHIVED_SECTION = "已归档"
TODO_LENIENT_SECTIONS = ("搁置 / 放弃", "已归档")
# - [ ] T-016 ｜ `模块名` ｜ P1 ｜ 一句话描述
TODO_ROW_RE = re.compile(
    r"^- \[(?P<box>[ xX])\] (?P<id>T-\d{3}) ｜ (?P<module>[^｜]+) ｜ "
    r"(?P<priority>P[0-2]) ｜ (?P<desc>\S.*)$"
)
TODO_HEADING_RE = re.compile(r"^## (?P<name>.+?)\s*$")
TODO_ANY_ID_RE = re.compile(r"^- [^\n]*?\b(?P<id>T-\d{3})\b", re.M)
# 条目下缩进的可选检测条件：- 检测：<路径> 含 <正则> / 不含 <正则> / 存在
DETECT_LINE_RE = re.compile(r"^[ \t]+[-*] 检测：\s*(?P<condition>.+?)\s*$")
DETECT_FORMS = (
    "不含",  # 必须先试，否则会被「含」的规则吃掉
    "含",
    "存在",
)
DETECT_CONDITION_RE = {
    "不含": re.compile(r"^(?P<path>\S+) 不含 (?P<pattern>.+)$"),
    "含": re.compile(r"^(?P<path>\S+) 含 (?P<pattern>.+)$"),
    "存在": re.compile(r"^(?P<path>\S+) 存在$"),
}
MODULE_NAME_RE = re.compile(r"`([a-z][a-z0-9_]*)`")
MD_LINK_RE = re.compile(r"\]\((?P<target>[^)\s]+)\)")


def parse_detect_condition(condition: str):
    """解析「<路径> 含 <正则>」这类检测条件。

    :return: ``(kind, {"path": ..., "pattern": ...})``；语法不合法或正则写错时返回 ``None``。
    """
    for kind in DETECT_FORMS:
        match = DETECT_CONDITION_RE[kind].match(condition.strip())
        if not match:
            continue
        groups = match.groupdict()
        pattern = groups.get("pattern")
        if pattern is not None:
            try:
                re.compile(pattern)
            except re.error:
                return None
        return kind, groups
    return None


def parse_todo(content: str | None = None) -> dict[str, list[dict]]:
    """把 TODO.md 解析成 ``{章节名: [条目, ...]}``。

    条目字段：``id`` / ``section`` / ``checked`` / ``modules`` / ``priority`` / ``desc`` /
    ``conditions``（「检测：」条件原文） / ``has_acceptance``（进行中是否写了验收标准）。

    解析刻意保持宽松：只有「严格区」的条目行要求格式正确，检查逻辑放在 ``check_todo()`` 里，
    这样 ``.dev/scripts/todo_status.py`` 能复用同一份解析结果跑看板。
    """
    if content is None:
        if not os.path.isfile(TODO_FILE):
            return {}
        content = open(TODO_FILE, encoding="utf-8").read()

    sections: dict[str, list[dict]] = {}
    section: str | None = None
    item: dict | None = None
    for raw in content.splitlines():
        heading = TODO_HEADING_RE.match(raw)
        if heading:
            section = heading.group("name")
            sections.setdefault(section, [])
            item = None
            continue
        if section is None:
            continue
        row = TODO_ROW_RE.match(raw)
        if row:
            item = {
                "id": row.group("id"),
                "section": section,
                "checked": row.group("box").lower() == "x",
                "modules": MODULE_NAME_RE.findall(row.group("module")),
                "priority": row.group("priority"),
                "desc": row.group("desc").strip(),
                "raw_row": raw,
                "conditions": [],
                "has_acceptance": False,
            }
            sections[section].append(item)
            continue
        if item is None:
            continue
        detect = DETECT_LINE_RE.match(raw)
        if detect:
            item["conditions"].append(detect.group("condition"))
        if "验收标准" in raw:
            item["has_acceptance"] = True
    return sections


def check_todo(report: Report) -> None:
    """TODO.md 的结构检查（根 AGENTS.md 第 8 节）。"""
    if not os.path.isfile(TODO_FILE):
        report.fail("TODO.md 不存在：它是待处理需求的唯一入口（根 AGENTS.md 第 8 节）")
        return
    content = open(TODO_FILE, encoding="utf-8").read()
    sections = parse_todo(content)
    for name in TODO_STRICT_SECTIONS + TODO_LENIENT_SECTIONS:
        if name not in sections:
            report.fail(f"TODO.md 缺少章节「## {name}」（四个章节始终保留，空章节写「（空）」）")

    strict_items = [
        item for name in TODO_STRICT_SECTIONS for item in sections.get(name, [])
    ]

    # 1) 严格区里以 `- [` 开头的行必须是合法条目（能挡住「加了条目但格式写歪」）
    for name in TODO_STRICT_SECTIONS:
        for line in section_lines(content, name):
            if line.startswith("- [") and not TODO_ROW_RE.match(line):
                report.fail(
                    f"TODO.md「{name}」条目格式不对：{line.strip()[:70]}\n"
                    "     期望：- [ ] T-0xx ｜ `模块名` ｜ P0/P1/P2 ｜ 一句话（追加规则 2）"
                )

    # 2) 勾选态：完成应移出本文件并归档（追加规则 4）
    for item in strict_items:
        if item["checked"]:
            report.fail(
                f"TODO.md「{item['section']}」的 {item['id']} 已勾选但没移出："
                "完成后应整条移出并在「已归档」留一行摘要（追加规则 4）"
            )

    # 3) ID 全局唯一（含已归档 / 搁置，挡「开工时复制粘贴忘删」）
    archived_ids = [
        match.group("id")
        for name in TODO_LENIENT_SECTIONS
        for match in TODO_ANY_ID_RE.finditer(section_text(content, name))
    ]
    every_id = [item["id"] for item in strict_items] + archived_ids
    duplicates = sorted(key for key, count in collections.Counter(every_id).items() if count > 1)
    if duplicates:
        report.fail(f"TODO.md 里 ID 重复：{duplicates}（一个需求一个 ID，见追加规则 1）")

    # 4) 待办池 ID 递增：新需求一律追加到末尾，不插队、不重排（追加规则 1）
    pool_ids = [item["id"] for item in sections.get("待办池", [])]
    if pool_ids != sorted(pool_ids):
        report.fail(f"TODO.md「待办池」ID 顺序不是递增：{pool_ids}（新需求追加到末尾，见追加规则 1）")

    # 5) 条目的模块列必须是仓库里真实存在的模块目录
    for item in strict_items:
        if not item["modules"]:
            report.fail(f"TODO.md {item['id']} 的模块列没写模块名：{item['raw_row'][:70]}")
        for module in item["modules"]:
            if not os.path.isdir(os.path.join(REPO_ROOT, module)):
                report.fail(
                    f"TODO.md {item['id']} 指向的模块目录不存在：{module}"
                    "（模块列写仓库里的一级目录名，跨模块用 `a` + `b`）"
                )

    # 6) 文档链接必须指向存在的文件 / 目录（挡住「指针指向已改名或已删除的文档」）
    for target in MD_LINK_RE.findall(content):
        if target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        path = target.split("#", 1)[0]
        if not path:
            continue
        if not os.path.exists(os.path.join(REPO_ROOT, path)):
            report.fail(f"TODO.md 里的链接指向不存在的路径：{target}")

    # 7) 「检测：」条件语法（供 task todo 执行，写错就在门禁这里挡住）
    for item in strict_items:
        for condition in item["conditions"]:
            if not parse_detect_condition(condition):
                report.fail(
                    f"TODO.md {item['id']} 的检测条件看不懂：{condition}\n"
                    "     支持：<路径> 含 <正则> / <路径> 不含 <正则> / <路径> 存在"
                )

    # 8) 进行中的条目要带验收标准（追加规则 3）
    for item in sections.get("进行中", []):
        if not item["has_acceptance"]:
            report.warn(f"TODO.md「进行中」的 {item['id']} 没有「验收标准」清单（追加规则 3）")


def section_text(content: str, name: str) -> str:
    """取某个 ``## 章节`` 的正文（到下一个二级标题为止）。

    公开名（不带下划线）是因为 ``.dev/scripts/todo_status.py`` 会复用同一个解析结果。
    """
    lines = content.splitlines()
    collected: list[str] = []
    inside = False
    for raw in lines:
        heading = TODO_HEADING_RE.match(raw)
        if heading:
            inside = heading.group("name") == name
            continue
        if inside:
            collected.append(raw)
    return "\n".join(collected)


def section_lines(content: str, name: str) -> list[str]:
    return section_text(content, name).splitlines()

ESCAPES = {"n": "\n", "t": "\t", "r": "\r"}


def unescape(raw: str) -> str:
    """把 po 里的 msgid 字面量还原成实际字符串。"""
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', raw)
    joined = "".join(parts)
    return re.sub(r"\\(.)", lambda m: ESCAPES.get(m.group(1), m.group(1)), joined)


class Report:
    def __init__(self, strict: bool) -> None:
        self.strict = strict
        self.failures: list[str] = []
        self.warnings: list[str] = []

    def fail(self, msg: str) -> None:
        self.failures.append(msg)

    def warn(self, msg: str) -> None:
        (self.failures if self.strict else self.warnings).append(msg)


def check_po_duplicates(report: Report) -> None:
    """po 侧的检查：重复 msgid（整份译文导入会失败）+ 每个条目缺 `#. module:`（会被解析崩）。"""
    for po_file in sorted(glob.glob(os.path.join(REPO_ROOT, "*", "i18n", "*.po"))):
        content = open(po_file, encoding="utf-8").read()
        msgids = [unescape(raw) for raw in MSGID_RE.findall(content)]
        duplicates = [key for key, count in collections.Counter(msgids).items() if count > 1]
        if duplicates:
            report.fail(f"{os.path.relpath(po_file, REPO_ROOT)}: 重复 msgid {duplicates}")

        for block in content.split("\n\n"):
            raw = MSGID_RE.search(block)
            if not raw:
                continue  # 纯注释块
            if not unescape(raw.group(1)):
                continue  # 文件头的 metadata 条目（msgid ""）
            if not MODULE_COMMENT_RE.search(block):
                head = block.strip().splitlines()[0][:60]
                report.fail(
                    f"{os.path.relpath(po_file, REPO_ROOT)}: 条目缺 `#. module: xxx`：{head}"
                )


def check_apps_metadata(report: Report) -> None:
    for manifest_file in sorted(glob.glob(os.path.join(REPO_ROOT, "*", "__manifest__.py"))):
        module = os.path.basename(os.path.dirname(manifest_file))
        po_files = glob.glob(os.path.join(REPO_ROOT, module, "i18n", "*.po"))
        if not po_files:
            continue
        try:
            manifest = ast.literal_eval(open(manifest_file, encoding="utf-8").read())
        except Exception as exc:  # noqa: BLE001
            report.fail(f"{module}/__manifest__.py 解析失败：{exc}")
            continue

        found: dict[str, str] = {}
        for po_file in po_files:
            content = open(po_file, encoding="utf-8").read()
            for block in content.split("\n\n"):
                match = PO_REF_RE.search(block)
                if not match:
                    continue
                key, target = match.groups()
                if target != module:
                    continue
                raw = MSGID_RE.search(block)
                if not raw:
                    report.fail(f"{module}: {key} 条目没有 msgid")
                    continue
                got = unescape(raw.group(1))
                want = manifest.get(METADATA_KEYS.get(key, key), "")
                if key == "description":
                    want = textwrap.dedent(want)
                if got != want:
                    report.fail(
                        f"{os.path.relpath(po_file, REPO_ROOT)}: {key} 的 msgid 与 manifest 不一致\n"
                        f"     po  : {got!r}\n"
                        f"    源文本: {want!r}"
                    )
                found[key] = target

        missing = sorted(set(METADATA_KEYS) - set(found))
        if missing:
            report.warn(f"{module}/i18n: 缺少应用列表元数据条目 {missing}（新模块必补，见 AGENTS.md 4.8）")


def docstring_lines(content: str) -> set[int]:
    """返回所有 docstring 覆盖的行号（AGENTS.md 允许注释/docstring 用中文）。"""
    lines: set[int] = set()
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return lines
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", [])
        if not body:
            continue
        first = body[0]
        if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            lines.update(range(first.lineno, getattr(first, "end_lineno", first.lineno) + 1))
    return lines


def strip_comments(text: str, ext: str) -> str:
    """按文件类型去掉注释内容，避免把中文注释误报成「界面文本残留中文」。

    这是启发式处理（不解析 AST），目的是减少噪音；真正犯罪现场仍以人工判断为准。
    """
    def blank_out(match: re.Match) -> str:
        # 换成等量的换行，保证后面的行号和源文件一致
        return "\n" * match.group(0).count("\n")

    if ext == ".xml":
        return re.sub(r"<!--[\s\S]*?-->", blank_out, text)
    if ext == ".js":
        text = re.sub(r"/\*[\s\S]*?\*/", blank_out, text)
        return re.sub(r"//[^\n]*", "", text)
    if ext == ".py":
        # 只去掉行注释；字符串里的 #（颜色值等）会保留，宁可多报不漏报
        return "\n".join(re.sub(r"(^|\s)#.*$", "", line) for line in text.splitlines())
    return text


def check_residual_chinese(report: Report) -> None:
    for path in sorted(glob.glob(os.path.join(REPO_ROOT, "**", "*.*"), recursive=True)):
        ext = os.path.splitext(path)[1]
        if ext not in {".xml", ".csv", ".js", ".py"}:
            continue
        rel = os.path.relpath(path, REPO_ROOT)
        content = open(path, encoding="utf-8").read()
        cleaned = strip_comments(content, ext)
        # 注释被替换成等量空行，行号仍与源文件一致
        skip_lines = docstring_lines(content) if ext == ".py" else set()
        for lineno, line in enumerate(cleaned.splitlines(), start=1):
            if lineno in skip_lines:
                continue  # Python 的模块 / 类 / 方法 docstring 允许中文
            if CJK_RE.search(line):
                report.warn(f"{rel}:{lineno}: 疑似界面文本残留中文 → {line.strip()[:80]}")


def check_xml(report: Report) -> None:
    for path in sorted(glob.glob(os.path.join(REPO_ROOT, "**", "*.xml"), recursive=True)):
        try:
            xml.dom.minidom.parse(path)
        except Exception as exc:  # noqa: BLE001
            report.fail(f"{os.path.relpath(path, REPO_ROOT)}: XML 不合法：{exc}")


def check_js(report: Report) -> None:
    import shutil

    node = shutil.which("node")
    if not node:
        report.warnings.append("未找到 node，跳过 JS 语法检查")
        return
    for path in sorted(glob.glob(os.path.join(REPO_ROOT, "**", "static", "src", "js", "*.js"), recursive=True)):
        result = subprocess.run([node, "--check", path], capture_output=True, text=True)
        if result.returncode != 0:
            report.fail(f"{os.path.relpath(path, REPO_ROOT)}: JS 语法错误：{result.stderr.strip()[:200]}")


def check_json_files(report: Report) -> None:
    for path in sorted(glob.glob(os.path.join(REPO_ROOT, "**", "*.json"), recursive=True)):
        try:
            json.load(open(path, encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            report.fail(f"{os.path.relpath(path, REPO_ROOT)}: JSON 不合法：{exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="仓库自检（AGENTS.md 4.6 固化）")
    parser.add_argument("--strict", action="store_true", help="把警告也当成失败")
    args = parser.parse_args()

    report = Report(args.strict)
    for check in (
        check_po_duplicates,
        check_apps_metadata,
        check_residual_chinese,
        check_xml,
        check_js,
        check_json_files,
        check_todo,
    ):
        check(report)

    print(f"仓库根目录：{REPO_ROOT}")
    if report.warnings:
        print(f"\n[警告] {len(report.warnings)} 项：")
        for item in report.warnings[:50]:
            print("  -", item)
        if len(report.warnings) > 50:
            print(f"  ...（其余 {len(report.warnings) - 50} 项省略）")
    if report.failures:
        print(f"\n[失败] {len(report.failures)} 项：")
        for item in report.failures:
            print("  -", item)
    else:
        print("\n[通过] 未发现结构性问题")
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
