# -*- coding: utf-8 -*-
"""
Elliott Wave Theory · 专项分析入口
====================================================================
独立于 wave_analysis.py（价格行为/结构通道）与 gold_analysis.py（指标）。

聚焦内容：
  - 5 浪推动结构（1-2-3-4-5）+ ABC 调整结构识别
  - 三大铁律校验（W2 不重叠 W1 起点 / W3 非最短 / W4 不进入 W1 价格区）
  - 斐波那契比率（W2 = 0.5/0.618 W1，W3 = 1.618 W1，W4 = 0.382 W3，W5 = W1 或 1.618 W1）
  - 当前所处浪位推断 + 下一浪目标位投影
  - 多周期（D / H4 / H1 / M15）独立扫描
  - 机构级 HTML 报告 + 详细标注图表

报告输出： reports/elliott/elliott_<timestamp>.html  +  elliott_latest.html
"""

import os
import sys
import io
import base64
import webbrowser
import warnings
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

sys.path.insert(0, os.path.dirname(__file__))
from gold_analysis import fetch_data, REPORT_DIR
from wave_analysis import detect_zigzag


# ════════════════════════════════════════════════════════════════════
# 数据结构
# ════════════════════════════════════════════════════════════════════

@dataclass
class WavePoint:
    idx: int          # 全局 K 线索引
    price: float
    label: str        # "0","1","2","3","4","5","A","B","C"
    pivot_type: str   # "H" or "L"


@dataclass
class WavePattern:
    direction: str                    # "bull" / "bear"
    impulse: List[WavePoint] = field(default_factory=list)   # 0..5（最多 6 个点）
    correction: List[WavePoint] = field(default_factory=list) # A,B,C
    rules_passed: Dict[str, bool] = field(default_factory=dict)
    fibs: Dict[str, float] = field(default_factory=dict)     # 实测各浪占比
    score: float = 0.0
    state: str = ""                   # 当前所处状态描述
    next_target: Dict[str, float] = field(default_factory=dict)  # 下一浪目标 {label: price}
    completeness: int = 0             # 已识别多少个推动浪点
    invalidation: Optional[float] = None  # 形态作废价位


# ════════════════════════════════════════════════════════════════════
# Elliott Wave 检测核心
# ════════════════════════════════════════════════════════════════════

def _ratio(a, b):
    if b == 0:
        return 0.0
    return abs(a) / abs(b)


def _check_impulse_rules(p0, p1, p2, p3, p4, p5, direction):
    """三大铁律 + 比率检验。返回 (rules_passed_dict, fibs_dict, score)"""
    rules = {}
    fibs = {}
    # 价格序列
    if direction == "bull":
        # 期望 0<1, 1>2, 2<3, 3>4, 4<5；3 是最高
        rules["W2_holds"]  = (p2 is None) or (p2.price > p0.price)
        rules["W3_extends"] = (p3 is None) or (p3.price > p1.price)
        rules["W4_no_overlap"] = (p4 is None) or (p4.price > p1.price)
        # W3 not shortest（在 1/3/5 全部已知时）
        if p5 is not None and p3 is not None and p4 is not None:
            w1 = p1.price - p0.price
            w3 = p3.price - p2.price
            w5 = p5.price - p4.price
            rules["W3_not_shortest"] = (w3 >= w1) and (w3 >= w5)
        else:
            rules["W3_not_shortest"] = True
    else:  # bear
        rules["W2_holds"]  = (p2 is None) or (p2.price < p0.price)
        rules["W3_extends"] = (p3 is None) or (p3.price < p1.price)
        rules["W4_no_overlap"] = (p4 is None) or (p4.price < p1.price)
        if p5 is not None and p3 is not None and p4 is not None:
            w1 = p0.price - p1.price
            w3 = p2.price - p3.price
            w5 = p4.price - p5.price
            rules["W3_not_shortest"] = (w3 >= w1) and (w3 >= w5)
        else:
            rules["W3_not_shortest"] = True

    # 斐波那契比率
    try:
        if direction == "bull":
            w1 = p1.price - p0.price
            if p2 is not None:
                w2 = p1.price - p2.price
                fibs["W2/W1"] = _ratio(w2, w1)
            if p3 is not None and p2 is not None:
                w3 = p3.price - p2.price
                fibs["W3/W1"] = _ratio(w3, w1)
            if p4 is not None and p3 is not None:
                w4 = p3.price - p4.price
                fibs["W4/W3"] = _ratio(w4, p3.price - p2.price)
            if p5 is not None and p4 is not None:
                w5 = p5.price - p4.price
                fibs["W5/W1"] = _ratio(w5, w1)
        else:
            w1 = p0.price - p1.price
            if p2 is not None:
                w2 = p2.price - p1.price
                fibs["W2/W1"] = _ratio(w2, w1)
            if p3 is not None and p2 is not None:
                w3 = p2.price - p3.price
                fibs["W3/W1"] = _ratio(w3, w1)
            if p4 is not None and p3 is not None:
                w4 = p4.price - p3.price
                fibs["W4/W3"] = _ratio(w4, p2.price - p3.price)
            if p5 is not None and p4 is not None:
                w5 = p4.price - p5.price
                fibs["W5/W1"] = _ratio(w5, w1)
    except Exception:
        pass

    # 评分：硬规则各 25 分；比率落入合理区间各 +5
    score = 0
    score += 25 if rules.get("W2_holds", False) else 0
    score += 25 if rules.get("W3_extends", False) else 0
    score += 25 if rules.get("W4_no_overlap", False) else 0
    score += 25 if rules.get("W3_not_shortest", False) else 0
    if 0.236 <= fibs.get("W2/W1", -1) <= 0.886:
        score += 5
    if 1.0 <= fibs.get("W3/W1", -1) <= 3.236:
        score += 8
    if 0.118 <= fibs.get("W4/W3", -1) <= 0.5:
        score += 5
    if 0.382 <= fibs.get("W5/W1", -1) <= 1.618:
        score += 4

    return rules, fibs, score


def detect_wave_pattern(pivots, df) -> Optional[WavePattern]:
    """
    在最近转折点中扫描最佳的 5 浪推动 / ABC 调整形态。

    思路：
      - 取最近 8 个 pivots（覆盖 5 浪 + ABC）
      - 对每个起始点（必须类型与方向匹配）尝试构造形态
      - 选择评分最高且最近完成的形态
    """
    if len(pivots) < 4:
        return None

    candidates = []
    recent = pivots[-12:]
    n = len(recent)

    for direction in ("bull", "bear"):
        first_type = "L" if direction == "bull" else "H"
        for start in range(n):
            if recent[start][2] != first_type:
                continue
            # 期望交替类型
            seq = [recent[start]]
            for k in range(start + 1, n):
                expect = "H" if seq[-1][2] == "L" else "L"
                if recent[k][2] == expect:
                    seq.append(recent[k])
                if len(seq) >= 6:
                    break

            if len(seq) < 3:
                continue

            # 构造 WavePoint
            wave_labels = ["0", "1", "2", "3", "4", "5"]
            wpts = [WavePoint(idx=p[0], price=p[1], label=wave_labels[i], pivot_type=p[2])
                    for i, p in enumerate(seq[:6])]
            p_arr = wpts + [None] * (6 - len(wpts))

            rules, fibs, score = _check_impulse_rules(
                p_arr[0], p_arr[1], p_arr[2], p_arr[3], p_arr[4], p_arr[5], direction)
            # 至少要 W2_holds 通过才考虑
            if not rules.get("W2_holds", False):
                continue

            pattern = WavePattern(
                direction=direction,
                impulse=wpts,
                rules_passed=rules,
                fibs=fibs,
                score=score,
                completeness=len(wpts) - 1,
            )

            # 尝试附加 ABC（如果有 5 浪完成且后面还有 pivots）
            if len(wpts) >= 6:
                last_idx_in_recent = start + 5
                abc_seq = []
                for k in range(last_idx_in_recent + 1, n):
                    expect = "H" if (abc_seq[-1][2] if abc_seq else seq[5][2]) == "L" else "L"
                    if recent[k][2] == expect:
                        abc_seq.append(recent[k])
                    if len(abc_seq) >= 3:
                        break
                abc_labels = ["A", "B", "C"]
                pattern.correction = [
                    WavePoint(idx=p[0], price=p[1], label=abc_labels[i], pivot_type=p[2])
                    for i, p in enumerate(abc_seq[:3])
                ]

            # 倾向最近形态：起点越近加分
            recency_bonus = (start / max(n - 1, 1)) * 10
            pattern.score += recency_bonus
            candidates.append(pattern)

    if not candidates:
        return None

    best = max(candidates, key=lambda p: (p.score, p.completeness))
    _annotate_state(best, df)
    return best


def _annotate_state(pat: WavePattern, df):
    """根据已识别浪点，推断当前形态阶段、下一目标位与作废价。"""
    if not pat.impulse:
        return
    completeness = pat.completeness  # 已确认的浪 = 已完成的最大序号
    direction = pat.direction
    last_close = float(df["Close"].iloc[-1])
    targets: Dict[str, float] = {}

    pts = pat.impulse
    p0 = pts[0]
    p1 = pts[1] if len(pts) > 1 else None
    p2 = pts[2] if len(pts) > 2 else None
    p3 = pts[3] if len(pts) > 3 else None
    p4 = pts[4] if len(pts) > 4 else None
    p5 = pts[5] if len(pts) > 5 else None

    sign = 1 if direction == "bull" else -1

    # 推断状态
    if completeness == 1:
        pat.state = f"第 1 浪已成立（{p1.price:.2f}），目前正在第 2 浪回调"
        # 下一目标 = W2 的回撤区间（0.5~0.618 W1）
        w1 = abs(p1.price - p0.price)
        targets["W2 目标 0.5"] = p1.price - sign * w1 * 0.5
        targets["W2 目标 0.618"] = p1.price - sign * w1 * 0.618
        pat.invalidation = p0.price  # W2 不能跌破 W1 起点
    elif completeness == 2:
        pat.state = f"第 2 浪已结束（{p2.price:.2f}），目前应在第 3 浪发动"
        w1 = abs(p1.price - p0.price)
        targets["W3 目标 1.0×W1"] = p2.price + sign * w1
        targets["W3 目标 1.618×W1"] = p2.price + sign * w1 * 1.618
        targets["W3 目标 2.618×W1"] = p2.price + sign * w1 * 2.618
        pat.invalidation = p0.price
    elif completeness == 3:
        pat.state = f"第 3 浪已结束（{p3.price:.2f}），目前应在第 4 浪调整"
        w3 = abs(p3.price - p2.price)
        targets["W4 目标 0.382×W3"] = p3.price - sign * w3 * 0.382
        targets["W4 目标 0.5×W3"]   = p3.price - sign * w3 * 0.5
        # 不允许进入 W1 范围（铁律）
        pat.invalidation = p1.price
    elif completeness == 4:
        pat.state = f"第 4 浪已结束（{p4.price:.2f}），目前应在第 5 浪冲顶"
        w1 = abs(p1.price - p0.price)
        w0_3 = abs(p3.price - p0.price)
        targets["W5 目标 = W1"] = p4.price + sign * w1
        targets["W5 目标 1.618×W1"] = p4.price + sign * w1 * 1.618
        targets["W5 目标 0.618×(W0→W3)"] = p4.price + sign * w0_3 * 0.618
        pat.invalidation = p1.price
    elif completeness >= 5:
        pat.state = f"第 5 浪已完成（{p5.price:.2f}），警惕 ABC 反向调整启动"
        w1_5 = abs(p5.price - p0.price)
        targets["A 浪目标 0.382"] = p5.price - sign * w1_5 * 0.382
        targets["A 浪目标 0.5"]   = p5.price - sign * w1_5 * 0.5
        targets["A 浪目标 0.618"] = p5.price - sign * w1_5 * 0.618
        pat.invalidation = p5.price  # 突破 5 浪高/低 = 仍在推动延伸
    else:
        pat.state = "形态发展不足，无法明确浪位"

    pat.next_target = targets


# ════════════════════════════════════════════════════════════════════
# 图表渲染
# ════════════════════════════════════════════════════════════════════

CIRCLED = {"0": "⓪", "1": "①", "2": "②", "3": "③", "4": "④", "5": "⑤",
           "A": "Ⓐ", "B": "Ⓑ", "C": "Ⓒ"}


def render_wave_chart_b64(df, pattern: WavePattern, label: str, last_n=160) -> Optional[str]:
    if not HAS_MPL or df is None or len(df) < 30:
        return None

    df_plot = df.tail(last_n).reset_index(drop=False)
    n = len(df_plot)
    base_idx = len(df) - last_n

    fig, ax = plt.subplots(figsize=(14, 6.2), facecolor="#050508")
    ax.set_facecolor("#0a0a14")

    # 提前计算 ylim，便于后续裁剪越界目标
    y_pad = (df_plot["High"].max() - df_plot["Low"].min()) * 0.05
    y_min_lim = df_plot["Low"].min() - y_pad
    y_max_lim = df_plot["High"].max() + y_pad

    # K 线
    for i, row in df_plot.iterrows():
        c = "#1ddfa9" if row["Close"] >= row["Open"] else "#ff5e7c"
        ax.plot([i, i], [row["Low"], row["High"]], color=c, linewidth=0.7, alpha=0.85)
        bl = min(row["Open"], row["Close"]); bh = max(row["Open"], row["Close"])
        h = max(bh - bl, (row["High"] - row["Low"]) * 0.001)
        ax.add_patch(plt.Rectangle((i - 0.35, bl), 0.7, h, facecolor=c, edgecolor=c, alpha=0.9))

    # 全局 → 局部 索引转换
    def to_local(g):
        return g - base_idx

    # 浪段连线 + 标签
    if pattern is not None:
        all_pts = list(pattern.impulse) + list(pattern.correction)
        visible = [p for p in all_pts if p.idx >= base_idx and to_local(p.idx) < n]
        if len(visible) >= 2:
            xs = [to_local(p.idx) for p in visible]
            ys = [p.price for p in visible]
            ax.plot(xs, ys, "-", color="#d9b85c", linewidth=2.0, alpha=0.95, zorder=4)

        for p in visible:
            x = to_local(p.idx)
            color = "#1ddfa9" if pattern.direction == "bull" else "#ff5e7c"
            if p.label in ("A", "B", "C"):
                color = "#ffb066"
            offset = (df_plot["High"].max() - df_plot["Low"].min()) * 0.025
            text_y = p.price + offset if p.pivot_type == "H" else p.price - offset
            va = "bottom" if p.pivot_type == "H" else "top"
            txt = CIRCLED.get(p.label, p.label)
            ax.scatter(x, p.price, s=80, color=color, edgecolors="#fff", linewidths=1.2, zorder=6)
            ax.text(x, text_y, txt, color=color, fontsize=14, ha="center", va=va,
                    fontweight="bold", zorder=7,
                    bbox=dict(boxstyle="circle,pad=0.25", facecolor="#050508",
                              edgecolor=color, linewidth=1.2, alpha=0.9))

        # 投影下一浪目标线（仅绘制位于可见 ylim 范围内的目标，越界目标只在右侧表格中展示）
        if pattern.next_target:
            last_pt = pattern.impulse[-1] if not pattern.correction else pattern.correction[-1]
            x_proj_start = to_local(last_pt.idx)
            x_proj_end = n - 1 + int(n * 0.22)
            in_range = [(k, v) for k, v in pattern.next_target.items()
                        if y_min_lim <= v <= y_max_lim]
            for k, v in in_range:
                ax.plot([x_proj_start, x_proj_end], [last_pt.price, v],
                        ":", color="#d9b85c", linewidth=0.9, alpha=0.55, clip_on=True)
                ax.text(x_proj_end, v, f" {k}: {v:.1f}", color="#d9b85c",
                        fontsize=8, va="center", fontweight="bold", clip_on=True)
            # 标记越界目标数量（角落小字）
            out_count = len(pattern.next_target) - len(in_range)
            if out_count > 0:
                ax.text(0.99, 0.02, f"⤓ 另有 {out_count} 个目标位超出图表范围（详见右侧表格）",
                        transform=ax.transAxes, ha="right", va="bottom",
                        fontsize=8, color="#d9b85c", alpha=0.75)

        # 作废线
        if pattern.invalidation is not None and y_min_lim <= pattern.invalidation <= y_max_lim:
            ax.axhline(y=pattern.invalidation, color="#ff5e7c", linestyle="--",
                       linewidth=1.0, alpha=0.7)
            ax.text(n - 1, pattern.invalidation, f" ⚠ 作废 {pattern.invalidation:.1f}",
                    color="#ff5e7c", fontsize=9, va="center", ha="right",
                    fontweight="bold", clip_on=True,
                    bbox=dict(boxstyle="round,pad=0.25", facecolor="#050508",
                              edgecolor="#ff5e7c", alpha=0.85))

    # 当前价
    cur = float(df_plot["Close"].iloc[-1])
    ax.axhline(y=cur, color="#fff", linestyle="-", linewidth=0.5, alpha=0.45)
    ax.text(n + 0.5, cur, f" ${cur:.1f}", color="#fff", fontsize=10, va="center", fontweight="bold")

    # X 轴时间标签
    time_col = df_plot.columns[0]
    try:
        tick_pos = list(range(0, n, max(1, n // 8)))
        tick_lbl = [df_plot[time_col].iloc[i].strftime("%m-%d %H:%M") for i in tick_pos]
        ax.set_xticks(tick_pos)
        ax.set_xticklabels(tick_lbl, rotation=0, fontsize=8, color="#888")
    except Exception:
        ax.set_xticks([])

    ax.set_ylim(y_min_lim, y_max_lim)
    ax.tick_params(colors="#888", labelsize=8)
    for sp in ax.spines.values():
        sp.set_color("#1f1f2e")
    ax.grid(True, color="#12121e", linewidth=0.4, alpha=0.6)

    title_dir = "看涨推动" if pattern and pattern.direction == "bull" else \
                "看跌推动" if pattern and pattern.direction == "bear" else "形态不明"
    state = pattern.state if pattern else "未识别到有效艾略特浪形态"
    ax.set_title(f"{label}  ·  Elliott Wave  ·  {title_dir}  ·  {state}",
                 color="#d9b85c", fontsize=12, pad=10, loc="left")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=110, facecolor="#050508")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


# ════════════════════════════════════════════════════════════════════
# HTML 渲染（机构级风格）
# ════════════════════════════════════════════════════════════════════

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg0:#050508;--bg1:#0a0a14;--bg2:#0f0f1a;--bg3:#15151f;
      --gold:#d9b85c;--gold-dim:#a88a3e;--bull:#1ddfa9;--bear:#ff5e7c;
      --warn:#ffb066;--text:#e6e9f0;--text-dim:#b4bcca;--text-mute:#7a8290;
      --border:rgba(255,255,255,0.06);--border-gold:rgba(217,184,92,0.28);
      --mono:'JetBrains Mono','Consolas',monospace;
      --body:'Microsoft YaHei','Segoe UI',sans-serif;}
body{background:var(--bg0);color:var(--text);font-family:var(--body);
     font-size:13px;line-height:1.7;max-width:1600px;margin:0 auto;padding:70px 22px 44px}
.topbar{position:fixed;top:0;left:0;right:0;background:rgba(5,5,8,0.92);
        backdrop-filter:blur(18px);border-bottom:1px solid var(--border-gold);
        z-index:100;display:flex;align-items:center;padding:0 26px;height:54px}
.brand{font-size:16px;font-weight:800;color:var(--gold);letter-spacing:2px;margin-right:24px}
.brand span{color:var(--text-dim);font-weight:400;letter-spacing:0}
.topbar-nav{display:flex;gap:4px;flex:1;flex-wrap:wrap}
.topbar-nav a{font-family:var(--mono);font-size:11px;font-weight:600;color:var(--text-dim);
        text-decoration:none;padding:6px 11px;border-radius:5px;letter-spacing:0.5px;
        transition:all 0.15s;text-transform:uppercase}
.topbar-nav a:hover{color:var(--gold);background:rgba(217,184,92,0.13)}
.ts{font-family:var(--mono);font-size:11px;color:var(--text-mute)}
h1.hero{font-size:30px;font-weight:800;letter-spacing:1px;margin:8px 0 6px;
        background:linear-gradient(90deg,#fff,#d9b85c);-webkit-background-clip:text;
        -webkit-text-fill-color:transparent}
.hero-sub{color:var(--text-dim);font-size:13px;margin-bottom:22px}
.hero-sub b{color:var(--gold)}
.section{margin:34px 0 14px}
.section-title{font-size:16px;font-weight:700;color:var(--gold);
        letter-spacing:1.5px;padding-bottom:8px;margin-bottom:14px;
        border-bottom:1px solid var(--border-gold);text-transform:uppercase}
.tf-block{background:var(--bg1);border:1px solid var(--border);border-radius:10px;
        padding:18px 20px;margin-bottom:22px;border-left:3px solid var(--gold-dim)}
.tf-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:12px;
        padding-bottom:10px;border-bottom:1px dashed var(--border)}
.tf-name{font-size:18px;font-weight:700;color:var(--gold);letter-spacing:1px}
.tf-state{font-size:13px;color:var(--text-dim)}
.tf-tag{font-family:var(--mono);font-size:11px;padding:3px 10px;border-radius:4px;
        font-weight:700;letter-spacing:0.5px;margin-left:8px}
.tag-bull{background:rgba(29,223,169,0.13);color:var(--bull);border:1px solid rgba(29,223,169,0.4)}
.tag-bear{background:rgba(255,94,124,0.13);color:var(--bear);border:1px solid rgba(255,94,124,0.4)}
.tag-warn{background:rgba(255,176,102,0.13);color:var(--warn);border:1px solid rgba(255,176,102,0.4)}
.tag-mute{background:rgba(122,130,144,0.13);color:var(--text-mute);border:1px solid rgba(122,130,144,0.3)}
.chart-wrap{margin:14px 0;border-radius:8px;overflow:hidden;border:1px solid var(--border)}
.chart-wrap img{width:100%;display:block}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}
@media (max-width: 920px){.grid2{grid-template-columns:1fr}}
.card{background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:14px 16px}
.card h4{font-size:12px;color:var(--text-mute);font-weight:600;letter-spacing:1px;
        margin-bottom:10px;text-transform:uppercase}
table{width:100%;font-size:12.5px;border-collapse:collapse}
table th,table td{padding:6px 8px;border-bottom:1px solid var(--border)}
table th{color:var(--text-mute);font-weight:600;text-align:left;font-size:11px;letter-spacing:0.5px}
.mono{font-family:var(--mono)}
.right{text-align:right}
.rule{display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid var(--border)}
.rule:last-child{border-bottom:none}
.rule-icon{width:18px;height:18px;border-radius:50%;display:flex;align-items:center;
        justify-content:center;font-size:11px;font-weight:700;flex-shrink:0}
.rule-pass{background:rgba(29,223,169,0.18);color:var(--bull)}
.rule-fail{background:rgba(255,94,124,0.18);color:var(--bear)}
.rule-text{flex:1;color:var(--text-dim);font-size:12.5px}
.kv{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px dashed var(--border);font-size:12.5px}
.kv:last-child{border-bottom:none}
.kv .k{color:var(--text-mute)}
.kv .v{font-family:var(--mono);color:var(--text)}
.kv .v.bull{color:var(--bull)}
.kv .v.bear{color:var(--bear)}
.kv .v.gold{color:var(--gold)}
.warn-box{margin-top:12px;padding:10px 14px;background:rgba(255,94,124,0.08);
        border:1px solid rgba(255,94,124,0.4);border-radius:6px;color:var(--bear);
        font-size:12.5px}
.warn-box b{color:#ff8fa3}
.narrative{background:var(--bg1);border:1px solid var(--border);border-left:3px solid var(--gold);
        border-radius:8px;padding:18px 22px;font-size:13px;line-height:1.85;color:var(--text-dim)}
.narrative p{margin-bottom:10px}
.narrative b{color:var(--gold)}
.footer{margin-top:40px;padding-top:18px;border-top:1px solid var(--border);
        font-size:11px;color:var(--text-mute);text-align:center;line-height:1.8}
.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:11.5px;color:var(--text-dim);
        background:var(--bg2);padding:10px 14px;border-radius:6px;margin-bottom:18px;
        border:1px solid var(--border)}
.legend span{display:flex;align-items:center;gap:6px}
.legend i{display:inline-block;width:18px;height:18px;border-radius:50%;text-align:center;
        line-height:18px;font-style:normal;font-weight:700;font-size:11px;
        background:#050508;border:1.5px solid;}
"""


def _rule_row(passed, text):
    icon_cls = "rule-pass" if passed else "rule-fail"
    icon = "✓" if passed else "✗"
    return f'<div class="rule"><div class="rule-icon {icon_cls}">{icon}</div><div class="rule-text">{text}</div></div>'


def _render_pattern_block(label: str, pattern: Optional[WavePattern], chart_b64: Optional[str], df) -> str:
    if pattern is None:
        return f"""
        <div class="tf-block">
          <div class="tf-head">
            <div class="tf-name">{label}</div>
            <div><span class="tf-tag tag-mute">无明确浪形</span></div>
          </div>
          <div style="color:var(--text-mute);padding:12px 0">
            当前周期 ZigZag 数据不足以识别有效艾略特浪形态。请等待更多结构形成或换大级别周期观察。
          </div>
        </div>"""

    dir_tag = '<span class="tf-tag tag-bull">看涨推动</span>' if pattern.direction == "bull" \
        else '<span class="tf-tag tag-bear">看跌推动</span>'
    completeness_tag = f'<span class="tf-tag tag-warn">已识别 {pattern.completeness}/5 浪</span>'

    # 浪点表
    rows = []
    for p in pattern.impulse + pattern.correction:
        try:
            t = df.index[p.idx].strftime("%m-%d %H:%M") if p.idx < len(df) else f"#{p.idx}"
        except Exception:
            t = f"#{p.idx}"
        rows.append(
            f"<tr><td class='mono'>{CIRCLED.get(p.label, p.label)}</td>"
            f"<td>{t}</td><td>{'高' if p.pivot_type == 'H' else '低'}</td>"
            f"<td class='right mono'>{p.price:.2f}</td></tr>"
        )
    points_table = f"""<table>
        <thead><tr><th>浪</th><th>时间</th><th>类型</th><th class='right'>价格</th></tr></thead>
        <tbody>{''.join(rows)}</tbody></table>"""

    # 规则核查
    rules_html = ""
    rule_text = {
        "W2_holds":         "铁律 1 · 第 2 浪不得超越第 1 浪起点",
        "W3_extends":       "铁律 2 · 第 3 浪须突破第 1 浪终点",
        "W4_no_overlap":    "铁律 3 · 第 4 浪不得进入第 1 浪价格区",
        "W3_not_shortest":  "守则 · 第 3 浪通常非 1/3/5 中最短的浪",
    }
    for k, txt in rule_text.items():
        if k in pattern.rules_passed:
            rules_html += _rule_row(pattern.rules_passed[k], txt)

    # 比率
    fib_rows = ""
    fib_ideal = {
        "W2/W1": "理想 0.5 ~ 0.618",
        "W3/W1": "理想 1.618（强势可达 2.618）",
        "W4/W3": "理想 0.382（最多 0.5）",
        "W5/W1": "理想 1.0 或 1.618",
    }
    for k, ideal in fib_ideal.items():
        if k in pattern.fibs:
            v = pattern.fibs[k]
            cls = "gold"
            fib_rows += f"<div class='kv'><span class='k'>{k} <small style='color:var(--text-mute)'>{ideal}</small></span><span class='v {cls}'>{v:.3f}</span></div>"

    # 下一浪目标
    target_rows = ""
    for k, v in pattern.next_target.items():
        cls = "bull" if pattern.direction == "bull" else "bear"
        target_rows += f"<div class='kv'><span class='k'>{k}</span><span class='v {cls}'>{v:.2f}</span></div>"

    invalid_html = ""
    if pattern.invalidation is not None:
        invalid_html = f"""<div class='warn-box'>
            <b>形态作废价位：</b>价格{'跌破' if pattern.direction == 'bull' else '突破'}
            <b>{pattern.invalidation:.2f}</b>，则当前波浪计数失效，需重新识别。
        </div>"""

    chart_html = f'<div class="chart-wrap"><img src="data:image/png;base64,{chart_b64}" alt="elliott chart {label}"/></div>' if chart_b64 else ""

    return f"""
    <div class="tf-block">
      <div class="tf-head">
        <div>
          <span class="tf-name">{label}</span>
          {dir_tag}{completeness_tag}
        </div>
        <div class="tf-state">{pattern.state}</div>
      </div>
      {chart_html}
      <div class="grid2">
        <div class="card">
          <h4>浪点序列</h4>
          {points_table}
        </div>
        <div class="card">
          <h4>艾略特规则核查</h4>
          {rules_html}
        </div>
        <div class="card">
          <h4>实测斐波那契比率</h4>
          {fib_rows or "<div style='color:var(--text-mute);font-size:12px'>数据不足</div>"}
        </div>
        <div class="card">
          <h4>下一浪目标投影</h4>
          {target_rows or "<div style='color:var(--text-mute);font-size:12px'>暂无投影</div>"}
        </div>
      </div>
      {invalid_html}
    </div>"""


def _build_narrative(analyses: Dict[str, Tuple[str, Optional[WavePattern]]], current_price: float) -> str:
    """生成总体解读文字。"""
    paragraphs = []

    # 主导周期：取 H4 / 日线 中识别度最高
    main = None
    for key in ("daily", "h4", "h1", "m15"):
        if key in analyses and analyses[key][1] is not None:
            cand = analyses[key][1]
            if main is None or cand.completeness > main[1].completeness or \
               (cand.completeness == main[1].completeness and cand.score > main[1].score):
                main = (key, cand)

    if main is None:
        paragraphs.append("<p>当前各周期 ZigZag 转折点不足以构造完整艾略特浪形态。建议先观察大级别（日线/H4）累积更多结构后再做计数。</p>")
    else:
        key, pat = main
        tf_label = {"daily": "日线", "h4": "H4", "h1": "H1", "m15": "M15"}[key]
        dir_zh = "看涨推动浪" if pat.direction == "bull" else "看跌推动浪"
        paragraphs.append(
            f"<p>主导级别落在 <b>{tf_label}</b>，正在演化一组 <b>{dir_zh}</b>。"
            f"当前阶段：<b>{pat.state}</b>。已识别 {pat.completeness} 个推动浪点，规则评分 "
            f"<b>{pat.score:.0f}/100</b>。</p>"
        )

        # 规则失败提示
        failed = [k for k, v in pat.rules_passed.items() if not v]
        if failed:
            paragraphs.append(
                f"<p style='color:var(--bear)'>⚠ 规则告警：{', '.join(failed)} 未通过校验，"
                f"该浪计数存在重新分解风险，请将其视为<b>备选方案</b>而非主计数。</p>"
            )

        # 目标位
        if pat.next_target:
            tgt_str = "；".join([f"{k} ≈ {v:.2f}" for k, v in pat.next_target.items()])
            paragraphs.append(f"<p>关键目标位：{tgt_str}。当前价 <b>{current_price:.2f}</b>。</p>")

        if pat.invalidation is not None:
            verb = "跌破" if pat.direction == "bull" else "升破"
            paragraphs.append(
                f"<p>风险控制：一旦价格 {verb} <b>{pat.invalidation:.2f}</b>，"
                f"主计数即作废，应立即停止按此计数布局并切换为反向假设。</p>"
            )

    # 多周期共振
    bulls = sum(1 for v in analyses.values() if v[1] and v[1].direction == "bull")
    bears = sum(1 for v in analyses.values() if v[1] and v[1].direction == "bear")
    if bulls > bears:
        paragraphs.append(f"<p>多周期共振统计：<b>{bulls}</b> 个周期识别为多头推动，<b>{bears}</b> 个为空头，整体偏多。</p>")
    elif bears > bulls:
        paragraphs.append(f"<p>多周期共振统计：<b>{bears}</b> 个周期识别为空头推动，<b>{bulls}</b> 个为多头，整体偏空。</p>")
    elif bulls > 0:
        paragraphs.append(f"<p>多周期共振统计：多空各 <b>{bulls}</b> 个周期，方向分歧，建议等待大级别明朗后再行动。</p>")

    paragraphs.append(
        "<p style='color:var(--text-mute);font-size:12px'>"
        "声明：艾略特波浪存在主观性，本报告基于 ZigZag 自动识别，仅供研究参考。"
        "实战中请结合关键支撑阻力、成交量、动量背离等多重证据。"
        "</p>"
    )
    return "\n".join(paragraphs)


def render_html(analyses: Dict[str, Tuple[str, Optional[WavePattern]]],
                charts: Dict[str, str],
                source: str,
                current_price: float) -> str:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    blocks = []
    for key, tup in analyses.items():
        label = tup[0]
        pat = tup[1]
        df = tup[2] if len(tup) > 2 else None
        blocks.append(_render_pattern_block(label, pat, charts.get(key), df))

    # 上方：图例
    legend = """
    <div class="legend">
      <span><i style="border-color:#1ddfa9;color:#1ddfa9">①</i>推动浪点（多）</span>
      <span><i style="border-color:#ff5e7c;color:#ff5e7c">①</i>推动浪点（空）</span>
      <span><i style="border-color:#ffb066;color:#ffb066">Ⓐ</i>调整浪 ABC</span>
      <span style="color:var(--gold)">━━━ 浪段连线</span>
      <span style="color:var(--gold)">┄┄┄ 下一浪目标投影</span>
      <span style="color:var(--bear)">┅┅┅ 形态作废线</span>
    </div>
    """

    nav = """
    <div class="topbar">
      <div class="brand">ELLIOTT WAVE <span>· XAU/USD 艾略特波浪专项</span></div>
      <div class="topbar-nav">
        <a href="#overview">总体解读</a>
        <a href="#daily">日线</a>
        <a href="#h4">H4</a>
        <a href="#h1">H1</a>
        <a href="#m15">M15</a>
      </div>
      <div class="ts">""" + now_str + """</div>
    </div>
    """

    narrative = _build_narrative(analyses, current_price)

    body = f"""
    {nav}
    <h1 class="hero">XAU/USD · 艾略特波浪专项分析</h1>
    <div class="hero-sub">
      数据源：<b>{source}</b> &nbsp;|&nbsp; 当前价：<b>{current_price:.2f}</b>
      &nbsp;|&nbsp; 报告时间：<b>{now_str}</b>
    </div>

    <div class="section" id="overview">
      <div class="section-title">总体解读 · 主计数与风险</div>
      <div class="narrative">{narrative}</div>
    </div>

    <div class="section">
      <div class="section-title">图例</div>
      {legend}
    </div>

    <div class="section">
      <div class="section-title">多周期艾略特波浪计数</div>
      {''.join(blocks)}
    </div>

    <div class="footer">
      Elliott Wave Analyzer · 基于 ZigZag + 三铁律 + 斐波那契比率自动识别<br>
      仅供研究学习，非投资建议。市场有风险，决策需谨慎。
    </div>
    """

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>XAU/USD · 艾略特波浪专项 · {now_str}</title>
<style>{CSS}</style></head><body>{body}</body></html>"""


# ════════════════════════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════════════════════════

def run_elliott_analysis(fetch_fn=None, report_prefix="elliott", report_subdir="elliott",
                         system_label="MT4 系统", open_browser=True):
    if fetch_fn is None:
        fetch_fn = fetch_data
    print(f"[EW] 启动艾略特波浪分析 · {system_label}")
    data, source = fetch_fn()
    if not data:
        print("[EW] 错误：无法获取行情数据")
        return None

    tf_settings = [
        ("daily", "日线",  2.0, 80),
        ("h4",    "H4",    2.0, 100),
        ("h1",    "H1",    1.5, 140),
        ("m15",   "M15",   1.2, 180),
    ]

    analyses: Dict[str, Tuple[str, Optional[WavePattern], pd.DataFrame]] = {}
    charts: Dict[str, str] = {}
    current_price = 0.0

    for key, label, atr_mult, last_n in tf_settings:
        df = data.get(key)
        if df is None or df.empty or len(df) < 30:
            continue
        pivots = detect_zigzag(df, atr_mult=atr_mult, min_bars=3)
        pat = detect_wave_pattern(pivots, df)
        analyses[key] = (label, pat, df)
        try:
            charts[key] = render_wave_chart_b64(df, pat, label, last_n=last_n) or ""
        except Exception as e:
            print(f"  [EW] {label} 图表渲染失败: {e}")
            charts[key] = ""
        current_price = float(df["Close"].iloc[-1])
        if pat:
            print(f"  [EW] {label}: {pat.direction} 完整度 {pat.completeness}/5 评分 {pat.score:.0f} · {pat.state}")
        else:
            print(f"  [EW] {label}: 未识别有效形态")

    html = render_html(analyses, charts, source, current_price)

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out_dir = os.path.join(REPORT_DIR, report_subdir) if report_subdir else REPORT_DIR
    os.makedirs(out_dir, exist_ok=True)
    report_path = os.path.join(out_dir, f"{report_prefix}_{ts}.html")
    latest_path = os.path.join(out_dir, f"{report_prefix}_latest.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[EW] 报告已生成: {report_path}")
    print(f"[EW] 最新报告: {latest_path}")
    if open_browser:
        try:
            os.startfile(latest_path)
        except Exception:
            webbrowser.open(f"file:///{latest_path.replace(os.sep, '/')}")
    return latest_path


def main():
    """MT4 系统入口（通过 MT4 CSV → Yahoo 数据回退链）"""
    return run_elliott_analysis(fetch_fn=fetch_data,
                                report_prefix="elliott",
                                report_subdir="elliott",
                                system_label="MT4 系统")


if __name__ == "__main__":
    main()
