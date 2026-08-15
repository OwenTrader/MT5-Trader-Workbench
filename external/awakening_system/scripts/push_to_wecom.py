# -*- coding: utf-8 -*-
"""
把已生成的 HTML 报告推送到企业微信群。
====================================================================
用法：
  · 推送指定文件：
        python push_to_wecom.py <html_file_path>
  · 自动找到最新一份报告（按修改时间）：
        python push_to_wecom.py --latest
  · 自动找到指定类型的最新报告：
        python push_to_wecom.py --type playbook
        python push_to_wecom.py --type snapshot
        python push_to_wecom.py --type fusion
        python push_to_wecom.py --type elliott
        python push_to_wecom.py --type wave
        python push_to_wecom.py --type gold
  · 交互式选择：
        python push_to_wecom.py    （不带参数，列出最新报告供选择）

可选参数：
  --no-summary      只发文件，不发 Markdown 摘要
  --no-file         只发摘要，不发文件
  --key <KEY>       指定 webhook key（覆盖环境变量与配置文件）
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Optional, List

sys.path.insert(0, os.path.dirname(__file__))
from wecom_push import push_report, load_webhook_key

REPORT_ROOT = Path(__file__).resolve().parent.parent / "reports"

TYPE_PATTERNS = {
    "playbook": "playbook/playbook*latest.html",
    "snapshot": "snapshot/snapshot*latest.html",
    "fusion":   "fusion/fusion*latest.html",
    "elliott":  "elliott/elliott*latest.html",
    "wave":     "mt5/wave*latest.html",
    "gold":     "gold_analysis_latest.html",
}

TYPE_ZH = {
    "playbook": "场景化交易剧本",
    "snapshot": "市场深度分析简报",
    "fusion":   "PA × 艾略特双引擎融合",
    "elliott":  "艾略特波浪",
    "wave":     "价格行为",
    "gold":     "黄金综合分析",
}


def find_latest(pattern: str) -> Optional[Path]:
    """在 reports 目录下按 glob 查找最新文件。"""
    matches = list(REPORT_ROOT.glob(pattern))
    # 也兼容根目录
    matches += list(REPORT_ROOT.glob("**/" + Path(pattern).name))
    matches = list({p.resolve() for p in matches if p.is_file()})
    if not matches:
        return None
    return max(matches, key=lambda p: p.stat().st_mtime)


def list_all_latest() -> List[tuple]:
    """返回 [(type_key, type_zh, path), ...]，仅含存在的。"""
    out = []
    for k, pat in TYPE_PATTERNS.items():
        p = find_latest(pat)
        if p:
            out.append((k, TYPE_ZH[k], p))
    return out


def interactive_pick() -> Optional[Path]:
    items = list_all_latest()
    if not items:
        print("[push] 在 reports/ 下未找到任何 *_latest.html 报告")
        return None
    print("\n可推送的最新报告：")
    print("─" * 70)
    for i, (k, zh, p) in enumerate(items, 1):
        size_kb = p.stat().st_size / 1024
        print(f"  [{i}] {zh:<24}  {p.name:<32}  ({size_kb:>6.1f} KB)")
    print("─" * 70)
    while True:
        choice = input("请选择编号（回车=最新一份；q=退出）：").strip()
        if choice in ("q", "Q"):
            return None
        if choice == "":
            # 选择最新修改的那份
            return max((p for _, _, p in items), key=lambda p: p.stat().st_mtime)
        if choice.isdigit() and 1 <= int(choice) <= len(items):
            return items[int(choice) - 1][2]
        print("[push] 输入无效，请重试。")


def main():
    ap = argparse.ArgumentParser(description="把 HTML 报告推送到企业微信群")
    ap.add_argument("path", nargs="?", help="HTML 文件路径")
    ap.add_argument("--latest", action="store_true", help="自动选择最新一份报告")
    ap.add_argument("--type", choices=list(TYPE_PATTERNS.keys()), help="按类型选择最新")
    ap.add_argument("--no-summary", action="store_true", help="不发送 Markdown 摘要")
    ap.add_argument("--no-file", action="store_true", help="不发送文件附件")
    ap.add_argument("--key", help="覆盖 Webhook Key")
    args = ap.parse_args()

    # 提前校验 key
    try:
        load_webhook_key(args.key)
    except RuntimeError as e:
        print(f"\n[push] 配置错误：\n{e}\n")
        sys.exit(1)

    target: Optional[Path] = None
    if args.path:
        target = Path(args.path).resolve()
        if not target.exists():
            print(f"[push] 文件不存在：{target}")
            sys.exit(1)
    elif args.type:
        target = find_latest(TYPE_PATTERNS[args.type])
        if not target:
            print(f"[push] 未找到类型为 '{args.type}' 的报告")
            sys.exit(1)
    elif args.latest:
        items = list_all_latest()
        if not items:
            print("[push] 未找到任何报告")
            sys.exit(1)
        target = max((p for _, _, p in items), key=lambda p: p.stat().st_mtime)
    else:
        target = interactive_pick()
        if target is None:
            sys.exit(0)

    print(f"\n[push] 目标报告：{target}")
    push_report(
        str(target),
        webhook_key=args.key,
        send_summary=not args.no_summary,
        send_attachment=not args.no_file,
    )
    print("[push] 全部完成 ✓")


if __name__ == "__main__":
    main()
