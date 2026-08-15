#!/usr/bin/env python3
"""Generic Project GUIDE.md Tree Verification Script.

Parses tree codeblocks in GUIDE.md and compares against actual disk / git state.
Works for ANY programming language, framework, or project structure (CLI, Web, Mobile, Library, Monorepo).

Usage:
    python .agents/skills/project-guide/scripts/check_guide_tree.py [project_root]
"""

from __future__ import annotations

import os
import re
import sys
import subprocess

def find_project_root(start_dir: str) -> str:
    curr = os.path.abspath(start_dir)
    while True:
        if os.path.exists(os.path.join(curr, "GUIDE.md")) or os.path.exists(os.path.join(curr, ".git")):
            return curr
        parent = os.path.dirname(curr)
        if parent == curr:
            return os.path.abspath(start_dir)
        curr = parent

ROOT = find_project_root(sys.argv[1] if len(sys.argv) > 1 else os.getcwd())
GUIDE_PATH = os.path.join(ROOT, "GUIDE.md")

# Comprehensive noise directories across ecosystems (Python, Node, Rust, Go, Java, Flutter, C++, C#)
NOISE_DIR_PARTS = {
    ".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules",
    ".next", ".idea", ".vscode", "build", "dist", "out", "target", ".cargo",
    ".coverage", ".dart_tool", "vendor", ".gradle", "bin", "obj", ".freebuff",
}
NOISE_FILE_NAMES = {"__init__.py", ".gitignore", ".DS_Store", "py.typed", ".metadata"}
COLLAPSED_KEYWORDS = ("image", "镜像", "mirror", "pruned", "剪枝", "vendor", "dependencies")
CONDITIONAL_KEYWORDS = ("test build", "测试包", "便携", "optional", "conditional")

def run_git(*args: str) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", ROOT, *args], capture_output=True, text=True
    )
    if proc.returncode != 0:
        return []
    return [line for line in proc.stdout.splitlines() if line.strip()]

def norm(p: str) -> str:
    return p.replace("\\", "/").strip("/")

def contains_any(comment: str, keywords: tuple[str, ...]) -> bool:
    low = comment.lower()
    return any(k.lower() in low for k in keywords)

def parse_entry(line: str) -> str:
    s = re.sub(r"^[│├└─\s]+", "", line)
    return s.split("#", 1)[0].strip()

def extract_trees(md: str) -> list[tuple[str, list[tuple[int, str, str]]]]:
    trees = []
    for block in re.findall(r"```[a-zA-Z]*\n(.*?)```", md, re.S):
        if "├" not in block and "└" not in block:
            continue
        # Avoid ASCII diagrams or UI tables using box-drawing characters
        if "┌─" in block or "═" in block or "╔" in block:
            continue
        lines = block.splitlines()
        root = lines[0].split("#", 1)[0].strip() if lines else ""
        entries = []
        for line in lines[1:]:
            if "├" not in line and "└" not in line:
                continue
            branch_idx = min(i for i, ch in enumerate(line) if ch in "├└")
            prefix = line[:branch_idx]
            # Use max of bar count and char-width/4 to handle both explicit '|' and space-only indentations
            bar_count = prefix.count("│")
            char_depth = (len(prefix) // 4) + 1
            depth = max(bar_count + 1, char_depth)
            name = parse_entry(line)
            if name:
                entries.append((depth, name, line))
        if entries:
            trees.append((root, entries))
    return trees

def main() -> int:
    if not os.path.exists(GUIDE_PATH):
        print(f"Error: {GUIDE_PATH} does not exist.")
        return 1

    with open(GUIDE_PATH, encoding="utf-8") as fh:
        md = fh.read()

    doc_entries: dict[str, dict] = {}
    conditional: set[str] = set()
    annotated_ignored: set[str] = set()
    collapsed: set[str] = set()

    repo_name = os.path.basename(ROOT).lower()

    for root_raw, entries in extract_trees(md):
        root = norm(root_raw)
        root_clean = re.sub(r"[\[\]/]", "", root).lower()
        # Set base empty if tree root represents the project root directory
        base = "" if root_clean in ("", ".", repo_name, "project-root", "root", "repository-root") else root
        stack: list[str] = []
        for depth, name, line in entries:
            while len(stack) >= depth:
                stack.pop()
            comment = line.split("#", 1)[1].strip() if "#" in line else ""
            path = norm(os.path.join(base, *stack, name))
            doc_entries[path] = {"comment": comment}
            if contains_any(comment, CONDITIONAL_KEYWORDS):
                conditional.add(path)
            if "git-ignored" in comment or "excluded from git" in comment.lower():
                annotated_ignored.add(path)
            if contains_any(comment, COLLAPSED_KEYWORDS):
                collapsed.add(path)
            stack.append(name)

    enumerated = {p for p in doc_entries if any(o.startswith(p + "/") for o in doc_entries)}

    stale: list[str] = []
    stale_conditional: list[str] = []
    for path in sorted(doc_entries):
        exists = os.path.exists(os.path.join(ROOT, *path.split("/")))
        if exists:
            continue
        (stale_conditional if path in conditional else stale).append(path)

    tracked = set(norm(p) for p in run_git("ls-files"))
    untracked = set(norm(p) for p in run_git("ls-files", "--others", "--exclude-standard"))
    repo_items = tracked | untracked

    def is_noise(path: str) -> bool:
        parts = path.split("/")
        if any(p in NOISE_DIR_PARTS for p in parts):
            return True
        return parts[-1] in NOISE_FILE_NAMES

    def inside_collapsed(path: str) -> bool:
        parts = path.split("/")
        return any("/".join(parts[:i]) in collapsed for i in range(1, len(parts)))

    missing_root: list[str] = []
    missing_children: dict[str, list[str]] = {}

    for path in sorted(repo_items):
        if is_noise(path) or inside_collapsed(path):
            continue
        if path in doc_entries:
            continue
        parts = path.split("/")
        if len(parts) == 1:
            missing_root.append(path)
            continue
        parent = "/".join(parts[:-1])
        if parent not in doc_entries:
            continue
        if parent in enumerated:
            missing_children.setdefault(parent, []).append(path)

    conflicts: list[str] = []
    for path in sorted(annotated_ignored):
        is_tracked = path in tracked or any(t.startswith(path + "/") for t in tracked)
        if is_tracked:
            conflicts.append(path)

    issues = bool(stale or missing_root or missing_children or conflicts)

    print("=" * 64)
    print(f"GUIDE.md Tree Verification ({ROOT})")
    print("=" * 64)

    print(f"\n[1] Stale items - in GUIDE.md but missing on disk ({len(stale)})")
    for path in stale:
        print(f"    ✗ {path}")
    if not stale:
        print("    (None)")

    print(f"\n[2] Conditional items - missing on disk but conditional build ({len(stale_conditional)})")
    for path in stale_conditional:
        print(f"    ? {path} ({doc_entries[path]['comment']})")
    if not stale_conditional:
        print("    (None)")

    print(f"\n[3] Missing items - in repository but omitted from GUIDE.md")
    print(f"    Root level ({len(missing_root)}):")
    for path in missing_root:
        print(f"    + {path}")
    if not missing_root:
        print("    (None)")

    total_children = sum(len(v) for v in missing_children.values())
    print(f"    Expanded directory children ({total_children}):")
    for parent in sorted(missing_children):
        print(f"    [{parent}/]")
        for child in missing_children[parent]:
            print(f"    + {child}")
    if total_children == 0:
        print("    (None)")

    print(f"\n[4] Annotation conflicts - marked (git-ignored) but tracked by git ({len(conflicts)})")
    for path in conflicts:
        print(f"    ! {path} ({doc_entries[path]['comment']})")
    if not conflicts:
        print("    (None)")

    print("\n" + "-" * 64)
    if issues:
        print("Result: Discrepancies detected. Update GUIDE.md accordingly.")
    else:
        print("Result: GUIDE.md tree matches repository structure.")
    return 1 if issues else 0

if __name__ == "__main__":
    raise SystemExit(main())
