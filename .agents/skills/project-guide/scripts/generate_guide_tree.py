#!/usr/bin/env python3
"""Generic Project GUIDE.md Tree Generator Script.

Scans the repository structure, filters out noise/ignored files, and prints a formatted
markdown text tree codeblock ready to insert into GUIDE.md Section 3.

Usage:
    python .agents/skills/project-guide/scripts/generate_guide_tree.py [project_root]
"""

from __future__ import annotations

import os
import sys
import subprocess

NOISE_DIR_PARTS = {
    ".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules",
    ".next", ".idea", ".vscode", "build", "dist", "out", "target", ".cargo",
    ".coverage", ".dart_tool", "vendor", ".gradle", "bin", "obj", ".freebuff",
}
NOISE_FILE_NAMES = {"__init__.py", ".gitignore", ".DS_Store", "py.typed", ".metadata"}

KNOWN_COMMENTS = {
    "GUIDE.md": "System architecture & directory guide (this file)",
    "README.md": "Primary product documentation & user guide",
    "LICENSE": "License terms and legal agreement",
    "pyproject.toml": "Project metadata, dependencies, and configuration (PEP 621)",
    "package.json": "Node.js dependencies and script manifests",
    "Cargo.toml": "Rust package manifest and workspace configuration",
    "go.mod": "Go module definition and dependency specifications",
    ".python-version": "Pinned runtime language version",
    "uv.lock": "Dependency lockfile for reproducible resolution",
    "package-lock.json": "npm dependency lockfile",
    "pnpm-lock.yaml": "pnpm dependency lockfile",
    "build.bat": "Windows build & execution helper script",
    "build.py": "PyInstaller packaging automation script",
    "AndroidAutoOCR.spec": "PyInstaller build specification file",
}

def find_project_root(start_dir: str) -> str:
    curr = os.path.abspath(start_dir)
    while True:
        if os.path.exists(os.path.join(curr, "GUIDE.md")) or os.path.exists(os.path.join(curr, ".git")):
            return curr
        parent = os.path.dirname(curr)
        if parent == curr:
            return os.path.abspath(start_dir)
        curr = parent

def norm(p: str) -> str:
    return p.replace("\\", "/").strip("/")

def is_noise(path: str) -> bool:
    parts = path.split("/")
    if any(p in NOISE_DIR_PARTS for p in parts):
        return True
    return parts[-1] in NOISE_FILE_NAMES

def run_git(root: str, *args: str) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", root, *args], capture_output=True, text=True
    )
    if proc.returncode != 0:
        return []
    return [line for line in proc.stdout.splitlines() if line.strip()]

def scan_repository(root: str) -> set[str]:
    tracked = set(norm(p) for p in run_git(root, "ls-files"))
    untracked = set(norm(p) for p in run_git(root, "ls-files", "--others", "--exclude-standard"))
    repo_items = tracked | untracked
    if not repo_items:
        # Fallback to os.walk if git is not initialized or unavailable
        repo_items = set()
        for r, dirs, files in os.walk(root):
            rel_dir = norm(os.path.relpath(r, root))
            if rel_dir == ".":
                rel_dir = ""
            for d in dirs:
                repo_items.add(norm(os.path.join(rel_dir, d)))
            for f in files:
                repo_items.add(norm(os.path.join(rel_dir, f)))
    return repo_items

def build_tree_node(paths: set[str]) -> dict:
    tree: dict = {}
    for p in sorted(paths):
        if is_noise(p):
            continue
        parts = p.split("/")
        curr = tree
        for part in parts:
            curr = curr.setdefault(part, {})
    return tree

def render_tree(tree: dict, prefix: str = "") -> list[str]:
    lines = []
    items = sorted(tree.keys(), key=lambda k: (len(tree[k]) == 0, k.lower()))
    for idx, key in enumerate(items):
        is_last = (idx == len(items) - 1)
        branch = "└── " if is_last else "├── "
        children = tree[key]
        is_dir = bool(children)
        display_name = f"{key}/" if is_dir else key
        
        comment = KNOWN_COMMENTS.get(key, "# [Insert module description]" if is_dir else "# [Insert file description]")
        line = f"{prefix}{branch}{display_name:<35} # {comment}" if "#" not in comment else f"{prefix}{branch}{display_name:<35} {comment}"
        lines.append(line)
        
        if is_dir:
            next_prefix = prefix + ("    " if is_last else "│   ")
            lines.extend(render_tree(children, next_prefix))
    return lines

def main() -> int:
    root = find_project_root(sys.argv[1] if len(sys.argv) > 1 else os.getcwd())
    repo_name = os.path.basename(root)
    paths = scan_repository(root)
    tree_struct = build_tree_node(paths)

    print(f"```text\n{repo_name}/")
    for line in render_tree(tree_struct):
        print(line)
    print("```")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
