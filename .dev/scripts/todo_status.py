#!/usr/bin/env python3
"""待办池看板：跑 TODO.md 里每条需求自带的「检测：」条件，报告当前状态。

用法（仓库根目录）：

    task todo                # 看板：进行中 + 待办池
    task todo -- --all       # 连「搁置 / 放弃」「已归档」一起列
    task todo -- T-017       # 只看某一条（可给多个 ID）

**这是特征探测，不是验收**：条件满足只说明代码里出现了该特征（必要条件），不代表业务正确。
验收永远以模块 `README.md` 的「验证清单」与人工复核为准。看板回答的是两个日常问题：

1. 这条需求是不是已经悄悄做完了（该去验收归档了）？
2. 我的改动有没有把某个条目的检测条件悄悄变成「已满足」？

条件语法（写错会被 `task check` 拦住）：
    <路径> 含 <正则>     路径（文件 / 目录 / glob，仓库根相对）里有匹配 → 满足
    <路径> 不含 <正则>   路径里没有匹配 → 满足
    <路径> 存在          路径存在 → 满足

一个条目写多行 → 全部满足才算「可能已实现」。条目从待办池移出（归档）时，
那些「检测：」行跟着一起走，不需要在脚本里维护任何清单。
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_repo  # noqa: E402  复用 TODO.md 解析与「检测：」条件语法

# 探测时跳过的目录 / 只扫这些后缀，避免把 .dev/.cache 里的核心源码副本翻一遍
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".cache", ".venv", "dist"}
TEXT_EXT = {".py", ".xml", ".js", ".csv", ".md", ".yml", ".yaml", ".json", ".po", ".html"}
MAX_HITS = 3

STATUS_LABEL = {
    "done": "✓ 检测条件全部满足 → 可能已实现：请验收并按 TODO.md 追加规则 4 归档",
    "todo": "✗ 未实现",
    "unknown": "— 没写「检测：」条件，只能人工判断（建议补一行，见 TODO.md 追加规则 8）",
}


def iter_files(root: str, target: str) -> list[str]:
    """把检测条件里的「路径」展开成待搜索的文件列表（支持文件 / 目录 / glob）。"""
    path = os.path.join(root, target)
    if os.path.isfile(path):
        return [path]
    if os.path.isdir(path):
        found: list[str] = []
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            found.extend(
                os.path.join(dirpath, name)
                for name in sorted(filenames)
                if os.path.splitext(name)[1] in TEXT_EXT
            )
        return found
    if "*" in target or "?" in target:
        import glob

        return sorted(item for item in glob.glob(path, recursive=True) if os.path.isfile(item))
    return []


def grep(root: str, target: str, pattern: str) -> list[tuple[str, int, str]]:
    """在目标路径里按行正则搜索，返回前 MAX_HITS 个命中 ``(相对路径, 行号, 行内容)``。"""
    regex = re.compile(pattern)
    hits: list[tuple[str, int, str]] = []
    for path in iter_files(root, target):
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                for lineno, line in enumerate(handle, start=1):
                    if regex.search(line):
                        hits.append((os.path.relpath(path, root), lineno, line.strip()[:100]))
                        if len(hits) >= MAX_HITS:
                            return hits
        except OSError:
            continue
    return hits


def evaluate(condition: str, root: str) -> tuple[bool | None, str]:
    """执行一条检测条件。返回 ``(是否满足, 说明)``，语法不合法时第一个元素是 ``None``。"""
    parsed = check_repo.parse_detect_condition(condition)
    if not parsed:
        return None, "条件语法不合法（task check 会报）"
    kind, groups = parsed
    target = groups["path"]

    if kind == "存在":
        exists = os.path.exists(os.path.join(root, target))
        return exists, "%s %s" % (target, "存在" if exists else "不存在")

    hits = grep(root, target, groups["pattern"])
    if kind == "含":
        if hits:
            rel, lineno, line = hits[0]
            return True, "%s 命中 %s:%s → %s" % (target, rel, lineno, line)
        return False, "%s 里没有匹配 /%s/" % (target, groups["pattern"])
    # 不含
    if hits:
        rel, lineno, line = hits[0]
        return False, "%s 里仍有 %s:%s → %s" % (target, rel, lineno, line)
    return True, "%s 里没有匹配 /%s/" % (target, groups["pattern"])


def item_status(item: dict, root: str) -> tuple[str, list[tuple[bool | None, str, str]]]:
    """给一个条目跑完所有条件，返回 ``(status, [(满足?, 条件原文, 说明), ...])``。"""
    if not item["conditions"]:
        return "unknown", []
    results = []
    for condition in item["conditions"]:
        satisfied, detail = evaluate(condition, root)
        results.append((satisfied, condition, detail))
    status = "done" if all(satisfied for satisfied, _, _ in results) else "todo"
    return status, results


def main() -> int:
    argv = sys.argv[1:]
    show_all = "--all" in argv
    wanted = [arg.upper() for arg in argv if not arg.startswith("-")]

    sections = check_repo.parse_todo()
    if not sections:
        print("没读到 TODO.md，先确认在仓库根目录跑")
        return 0

    root = check_repo.REPO_ROOT
    # 指定了 ID 就全章节找；否则默认只看「进行中 + 待办池」，--all 时连归档一起列
    order = [name for name in ("进行中", "待办池", "搁置 / 放弃", "已归档") if name in sections]
    if not (show_all or wanted):
        order = [name for name in order if name in ("进行中", "待办池")]

    counter = {"done": 0, "todo": 0, "unknown": 0}
    print("待办池看板（仓库根：%s）" % root)
    print("TODO.md：%s" % os.path.relpath(check_repo.TODO_FILE, root))
    print()

    for name in order:
        items = [item for item in sections.get(name, []) if not wanted or item["id"] in wanted]
        if not items:
            continue
        print("## %s（%d 条）" % (name, len(items)))
        for item in items:
            status, results = item_status(item, root)
            counter[status] += 1
            print("  %s  %s  %s" % (item["id"], item["priority"], "`%s`" % "` + `".join(item["modules"])))
            print("        %s" % item["desc"][:110])
            print("        %s" % STATUS_LABEL[status])
            for satisfied, condition, detail in results:
                mark = "✓" if satisfied else "✗"
                print("          %s %s" % (mark, condition))
                print("              %s" % detail)
        print()

    # 已归档条目的行格式是历史遗留（不统一），这里不解析字段，只在需要时列出 ID
    if show_all or wanted:
        content = open(check_repo.TODO_FILE, encoding="utf-8").read()
        archived = [
            match.group("id")
            for match in check_repo.TODO_ANY_ID_RE.finditer(
                check_repo.section_text(content, check_repo.TODO_ARCHIVED_SECTION)
            )
        ]
        listed = {item["id"] for name in order for item in sections.get(name, [])}
        if show_all and archived:
            print("## 已归档（%d 条，只列 ID，不跑检测）" % len(archived))
            print("  " + " · ".join(archived))
            print()
        for key in [key for key in wanted if key not in listed and key in archived]:
            print("%s 已归档：完成信息见 TODO.md 文末「已归档」与对应模块 CHANGELOG / README" % key)
            print()

    print(
        "可能已实现 %(done)s 条 · 未实现 %(todo)s 条 · 无检测条件 %(unknown)s 条"
        % counter
    )
    print("提示：条件语法合法性由 task check 兜住；检测条件只是必要条件，验收仍以模块 README 的「验证清单」为准。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
