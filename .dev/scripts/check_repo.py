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
