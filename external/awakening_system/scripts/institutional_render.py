# -*- coding: utf-8 -*-
"""
GOLDDESK · 机构级 XAU/USD 报告渲染层
================================================
在 wave_analysis.py 现有分析数据之上叠加：
  · 多周期共振评分（TF权重 D=2/H4=3/H1=2/M15=1）
  · SMC/ICT 框架：Order Block / FVG / SSL / BSL
  · 场景概率决策树（启发式）
  · 盈亏比硬性过滤（≥1:1.5 警示, ≥1:2.0 入场）
  · 宏观面板 + 经济日历（可在 MACRO_CONFIG 手动维护）

设计原则：
  · 所有数据从 analyses / plan / intraday 派生，不重复计算结构
  · 渲染纯字符串模板，零依赖
  · 宏观数据无 API 时回落为占位（用户可编辑下方 MACRO_CONFIG）
"""

from datetime import datetime, timedelta
import pandas as pd

# ════════════════════════════════════════════════════════════
# MACRO_CONFIG · 用户手动维护的宏观数据
# 没有实时 API 接入时，请按需编辑此区域，每日盘前更新 1 次即可
# ════════════════════════════════════════════════════════════
MACRO_CONFIG = {
    "dxy":         {"value": "99.20", "delta": "▼ -0.35%", "desc": "美元指数（请手动更新）", "impact": "bull"},   # 美元跌=金涨
    "real_yield":  {"value": "+1.85%", "delta": "",        "desc": "10年期 TIPS 实际收益率",  "impact": "bear"},   # 实利率高=金跌
    "vix":         {"value": "—",      "delta": "",        "desc": "市场恐慌指数（CBOE VIX）", "impact": "neutral"},
    "fed_policy":  {"value": "降息预期", "delta": "",      "desc": "CME FedWatch 6月降息概率 (请更新)", "impact": "bull"},
    "calendar": [
        # 编辑示例（北京时间）：
        # {"time": "MM-DD HH:MM", "name": "事件名称", "impact": "high"},
        {"time": "本周", "name": "请在 institutional_render.py 顶部 MACRO_CONFIG.calendar 编辑实际日历", "impact": "low"},
    ],
    "macro_summary": (
        "<strong style='color:var(--gold)'>宏观面板为可编辑占位</strong>。"
        "实盘前请在 <code>institutional_render.py</code> 顶部 <code>MACRO_CONFIG</code> 更新："
        "DXY、实际利率、VIX、美联储政策预期、本周日历。"
        "黄金对宏观面（美元/利率/避险）高度敏感，纯技术分析无法替代基本面校准。"
    ),
}

# ════════════════════════════════════════════════════════════
# 多周期共振评分
# ════════════════════════════════════════════════════════════

TF_WEIGHTS = {"daily": 2, "h4": 3, "h1": 2, "m15": 1}
TF_LABELS  = {"daily": "日线", "h4": "H4", "h1": "H1", "m15": "M15"}


def compute_confluence(analyses):
    """
    计算多周期共振评分 (-10..+10) 与每个TF的细化指标。
    返回 dict: {score, score_pct, level, level_cls, bias, rows[], notes[]}
    """
    rows = []
    raw_score = 0.0
    notes = []
    has_choch_against_trend = False

    for key in ("daily", "h4", "h1", "m15"):
        a = analyses.get(key)
        w = TF_WEIGHTS[key]
        if not a or "error" in a:
            rows.append({
                "tf": key, "label": TF_LABELS[key], "weight": w,
                "structure": "—", "trend_cls": "neutral",
                "bos": "数据不足", "channel": "—", "score": 0,
                "structure_label": "数据不足",
            })
            continue

        s = a["structure"]
        ch = a.get("channel")
        bos_events = a.get("bos_events", [])
        cls = s["trend_cls"]
        struct_label = s.get("trend", "—")

        # 基础打分
        base = w if cls == "bull" else (-w if cls == "bear" else 0)

        # CHoCH 反向惩罚 / BOS 同向加成（每TF最多追加一次警示标签）
        bos_str_parts = []
        warning_appended = False
        for ev in bos_events[-2:]:
            t = ev.get("type", "")
            bos_str_parts.append(t)
            if "CHoCH↓" in t and cls == "bull":
                base -= 0.5 * w
                has_choch_against_trend = True
                if not warning_appended:
                    struct_label = struct_label + " ⚠待确认"
                    warning_appended = True
            elif "CHoCH↑" in t and cls == "bear":
                base += 0.5 * w
                has_choch_against_trend = True
                if not warning_appended:
                    struct_label = struct_label + " ⚠待确认"
                    warning_appended = True
            elif "BOS↑" in t and cls == "bull":
                base += 0.3 * w
            elif "BOS↓" in t and cls == "bear":
                base -= 0.3 * w
        bos_str = " / ".join(bos_str_parts) if bos_str_parts else "无近期事件"

        # 通道方向辅助说明
        if ch:
            ch_str = f"{ch.get('direction','—')} · 价位 {ch.get('position_pct',50):.0f}%"
        else:
            ch_str = "通道数据不足"

        rows.append({
            "tf": key, "label": TF_LABELS[key], "weight": w,
            "structure": struct_label, "trend_cls": cls,
            "bos": bos_str, "channel": ch_str,
            "score": round(base, 1),
            "structure_label": struct_label,
        })
        raw_score += base

    # 归一化到 ±10
    max_possible = sum(TF_WEIGHTS.values())  # 8
    score_10 = max(-10, min(10, raw_score * 10 / max_possible))

    # 等级
    if score_10 >= 7:
        level = "高确信做多"; level_cls = "bull"; bias = "strong_bull"
        action_line = "可全仓入场，顺势加仓"
    elif score_10 >= 3:
        level = "做多偏向"; level_cls = "bull"; bias = "lean_bull"
        action_line = "半仓做多，寻找最优入场区"
    elif score_10 <= -7:
        level = "高确信做空"; level_cls = "bear"; bias = "strong_bear"
        action_line = "可全仓做空，顺势加仓"
    elif score_10 <= -3:
        level = "做空偏向"; level_cls = "bear"; bias = "lean_bear"
        action_line = "半仓做空，寻找回调高点"
    else:
        level = "震荡观望"; level_cls = "neutral"; bias = "range"
        action_line = "等方向选择，仓位减半或不动"

    # 记录提示
    if has_choch_against_trend:
        notes.append("⚠ 检测到 CHoCH 与高周期趋势冲突，结构稳定性降级")
    bull_tfs = [r["label"] for r in rows if r["trend_cls"] == "bull"]
    bear_tfs = [r["label"] for r in rows if r["trend_cls"] == "bear"]
    if bull_tfs and bear_tfs:
        notes.append(f"多周期方向冲突：{','.join(bull_tfs)} 偏多 vs {','.join(bear_tfs)} 偏空 → 不可重仓")
    if -3 < score_10 < 3:
        notes.append("共振评分处于震荡区，禁止追单，等方向明确")

    # 仪表盘指针位置 0..100%
    needle_pct = (score_10 + 10) / 20 * 100

    return {
        "score":       round(score_10, 1),
        "raw_score":   round(raw_score, 2),
        "score_pct":   round(needle_pct, 1),
        "level":       level,
        "level_cls":   level_cls,
        "bias":        bias,
        "action_line": action_line,
        "rows":        rows,
        "notes":       notes,
        "bull_tfs":    bull_tfs,
        "bear_tfs":    bear_tfs,
    }


# ════════════════════════════════════════════════════════════
# SMC / ICT · Order Block / FVG / 流动性池 检测
# ════════════════════════════════════════════════════════════

def detect_order_blocks(df, pivots, current_price, max_n=4):
    """
    基于 pivot 序列识别 OB：
      · 牛OB（Demand）= 价格在 HL→HH 推动前的最后一根阴 K（HL 之后到 HH 之前）
      · 熊OB（Supply）= 价格在 LH→LL 推动前的最后一根阳 K（LH 之后到 LL 之前）

    pivots 格式：[(idx, price, 'H'|'L'), ...]，idx 是 K 线整数索引。
    返回 [{kind, low, high, idx, fresh}]，距当前价由近到远。
    """
    if df is None or df.empty or len(df) < 20 or not pivots:
        return []
    closes = df["Close"].values
    opens  = df["Open"].values
    highs  = df["High"].values
    lows   = df["Low"].values
    n = len(df)

    obs = []
    # 取最近的 ~12 个 pivot 来扫描 OB
    recent = pivots[-12:]
    for i in range(1, len(recent)):
        prev_idx, _, prev_t = recent[i - 1]
        cur_idx,  _, cur_t  = recent[i]
        if prev_idx is None or cur_idx is None:
            continue
        if cur_idx >= n or prev_idx >= n:
            continue
        # HL → HH（HL 之后到 HH 之前的最后一根阴 K = 牛OB）
        if prev_t == "L" and cur_t == "H":
            for j in range(cur_idx - 1, prev_idx, -1):
                if j < 0 or j >= n: continue
                if closes[j] < opens[j]:
                    obs.append({
                        "kind": "bull",
                        "low":  round(float(lows[j]), 1),
                        "high": round(float(highs[j]), 1),
                        "idx":  j,
                        "fresh": current_price > highs[j],
                    })
                    break
        # LH → LL（LH 之后到 LL 之前的最后一根阳 K = 熊OB）
        elif prev_t == "H" and cur_t == "L":
            for j in range(cur_idx - 1, prev_idx, -1):
                if j < 0 or j >= n: continue
                if closes[j] > opens[j]:
                    obs.append({
                        "kind": "bear",
                        "low":  round(float(lows[j]), 1),
                        "high": round(float(highs[j]), 1),
                        "idx":  j,
                        "fresh": current_price < lows[j],
                    })
                    break
    # 去重（同向且价格区中点接近 0.2% 内合并）
    deduped = []
    for o in obs:
        merged = False
        for d in deduped:
            same_kind = d["kind"] == o["kind"]
            close_price = abs((d["low"]+d["high"])/2 - (o["low"]+o["high"])/2) < current_price * 0.002
            if same_kind and close_price:
                d["low"]  = min(d["low"],  o["low"])
                d["high"] = max(d["high"], o["high"])
                merged = True
                break
        if not merged:
            deduped.append(o)
    # 按距当前价由近到远，最多 max_n 个
    deduped.sort(key=lambda o: abs((o["low"]+o["high"])/2 - current_price))
    return deduped[:max_n]


def detect_fvg(df, lookback=80, current_price=None, max_n=4):
    """
    公允价值缺口（3K线模式）：
      · 看多 FVG（缺口在下，吸引价格回测后做多）：bar[i-1].high < bar[i+1].low
        gap = (bar[i-1].high, bar[i+1].low)
      · 看空 FVG（缺口在上）：bar[i-1].low > bar[i+1].high
        gap = (bar[i+1].high, bar[i-1].low)
    返回未被填补且距当前价合理的最近 max_n 个
    """
    if df is None or df.empty or len(df) < 5:
        return []
    n = len(df)
    start = max(1, n - lookback)
    highs = df["High"].values
    lows  = df["Low"].values
    if current_price is None:
        current_price = float(df["Close"].iloc[-1])
    fvgs = []
    for i in range(start, n - 1):
        h_prev = highs[i-1]; l_prev = lows[i-1]
        h_next = highs[i+1]; l_next = lows[i+1]
        # 看多缺口
        if h_prev < l_next:
            gap_low, gap_high = float(h_prev), float(l_next)
            # 检查是否已被回补
            filled = False
            for k in range(i+2, n):
                if lows[k] <= gap_high and highs[k] >= gap_low:
                    if lows[k] <= gap_low:  # 完全回补
                        filled = True
                        break
            if not filled and gap_high - gap_low >= current_price * 0.0005:
                fvgs.append({
                    "kind":   "bull",
                    "low":    round(gap_low, 1),
                    "high":   round(gap_high, 1),
                    "idx":    i,
                })
        # 看空缺口
        elif l_prev > h_next:
            gap_low, gap_high = float(h_next), float(l_prev)
            filled = False
            for k in range(i+2, n):
                if lows[k] <= gap_high and highs[k] >= gap_low:
                    if highs[k] >= gap_high:
                        filled = True
                        break
            if not filled and gap_high - gap_low >= current_price * 0.0005:
                fvgs.append({
                    "kind":   "bear",
                    "low":    round(gap_low, 1),
                    "high":   round(gap_high, 1),
                    "idx":    i,
                })
    # 取距当前价最近的 max_n 个
    fvgs.sort(key=lambda x: abs((x["low"]+x["high"])/2 - current_price))
    return fvgs[:max_n]


def detect_liquidity_pools(analyses, current_price):
    """
    流动性池识别：
      · BSL（买方流动性，价格上方）= H4/H1 最近的显著高点（多个相近高点更强）
      · SSL（卖方流动性，价格下方）= 最近的显著低点
    """
    bsl_candidates = []  # 高点
    ssl_candidates = []  # 低点
    for tf in ("h4", "h1"):
        a = analyses.get(tf)
        if not a or "error" in a:
            continue
        for idx, price, t in a.get("all_pivots", [])[-10:]:
            if t == "H" and price > current_price:
                bsl_candidates.append((round(price, 1), TF_LABELS[tf]))
            elif t == "L" and price < current_price:
                ssl_candidates.append((round(price, 1), TF_LABELS[tf]))

    # 聚类（相近价位强度叠加）
    def _cluster(items, ascending=True):
        if not items: return []
        items = sorted(items, key=lambda x: x[0] if ascending else -x[0])
        clusters = []
        for price, tag in items:
            merged = False
            for c in clusters:
                if abs(c["price"] - price) < current_price * 0.003:
                    c["count"] += 1
                    c["tags"].add(tag)
                    merged = True
                    break
            if not merged:
                clusters.append({"price": price, "count": 1, "tags": {tag}})
        for c in clusters:
            c["tags"] = "/".join(sorted(c["tags"]))
        return clusters

    bsl = _cluster(bsl_candidates, ascending=True)[:3]
    ssl = _cluster(ssl_candidates, ascending=False)[:3]
    return {"bsl": bsl, "ssl": ssl}


def build_smc_ladder(analyses, data, current_price, plan, intraday):
    """
    汇总 SMC 价格梯度：上方阻力 + 下方支撑，附带 OB / FVG / 流动性 标签。
    返回 [{price, dist, badges, kind('above'/'below'/'current'), strength}]
    """
    levels = []  # 每个: {price_low, price_high, kind, badges:[badge], strength}

    # H4 + H1 OB / FVG
    for tf in ("h4", "h1"):
        a = analyses.get(tf)
        df = data.get(tf) if data else None
        if not a or "error" in a or df is None:
            continue
        obs = detect_order_blocks(df, a.get("all_pivots", []), current_price)
        for ob in obs:
            mid = (ob["low"] + ob["high"]) / 2
            kind = "above" if mid > current_price else "below"
            badge = "OB-S" if ob["kind"] == "bear" else "OB-B"
            label = ("熊OB " if ob["kind"]=="bear" else "牛OB ") + f"({TF_LABELS[tf]})"
            levels.append({
                "low": ob["low"], "high": ob["high"], "mid": round(mid, 1),
                "kind": kind, "badges": [(badge, label)], "strength": 4,
                "src": f"{TF_LABELS[tf]}-OB",
            })
        fvgs = detect_fvg(df, lookback=80, current_price=current_price)
        for fv in fvgs:
            mid = (fv["low"] + fv["high"]) / 2
            kind = "above" if mid > current_price else "below"
            badge = "FVG-S" if fv["kind"] == "bear" else "FVG-B"
            label = f"FVG({TF_LABELS[tf]}) 未回补"
            levels.append({
                "low": fv["low"], "high": fv["high"], "mid": round(mid, 1),
                "kind": kind, "badges": [(badge, label)], "strength": 3,
                "src": f"{TF_LABELS[tf]}-FVG",
            })

    # 流动性池
    pools = detect_liquidity_pools(analyses, current_price)
    for c in pools["bsl"]:
        levels.append({
            "low": c["price"], "high": c["price"], "mid": c["price"],
            "kind": "above", "badges": [("LIQ", f"BSL 买方流动性({c['tags']}, 强度×{c['count']})")],
            "strength": 3 + c["count"],
            "src": "BSL",
        })
    for c in pools["ssl"]:
        levels.append({
            "low": c["price"], "high": c["price"], "mid": c["price"],
            "kind": "below", "badges": [("LIQ", f"SSL 卖方流动性({c['tags']}, 强度×{c['count']})")],
            "strength": 3 + c["count"],
            "src": "SSL",
        })

    # 关键支阻：H4 前高 / 前低
    h4 = analyses.get("h4")
    if h4 and "error" not in h4:
        for idx, price, t in h4.get("all_pivots", [])[-6:]:
            kind = "above" if price > current_price else "below"
            label = f"H4{'前高' if t=='H' else '前低'}"
            if t == "H" and price > current_price * 1.001:
                levels.append({"low": price, "high": price, "mid": round(price, 1),
                               "kind": kind, "badges": [("KEY", label)], "strength": 4, "src": "H4-key"})
            elif t == "L" and price < current_price * 0.999:
                levels.append({"low": price, "high": price, "mid": round(price, 1),
                               "kind": kind, "badges": [("KEY", label)], "strength": 4, "src": "H4-key"})

    # 整数关口（包含当前所在 50 整数倍 base_round 自身）
    base_round = int(current_price // 50) * 50
    for delta in (-100, -50, 0, 50, 100):
        rp = base_round + delta
        # 距当前价 < 3pt 视为已在当前价附近，避免与 NOW 标记重复
        if abs(rp - current_price) < 3:
            continue
        kind = "above" if rp > current_price else "below"
        levels.append({"low": rp, "high": rp, "mid": rp,
                       "kind": kind, "badges": [("KEY", f"整数关口 ${rp}")], "strength": 3, "src": "round"})

    # 去重合并 (mid 相近 < 0.2%)
    merge_gap = current_price * 0.002
    deduped = []
    for lv in levels:
        merged = False
        for d in deduped:
            if abs(d["mid"] - lv["mid"]) < merge_gap and d["kind"] == lv["kind"]:
                d["low"]  = min(d["low"],  lv["low"])
                d["high"] = max(d["high"], lv["high"])
                d["mid"]  = round((d["low"]+d["high"])/2, 1)
                d["badges"].extend(lv["badges"])
                d["strength"] = min(5, d["strength"] + 1)
                d["src"] = d["src"] + "+" + lv["src"]
                merged = True
                break
        if not merged:
            deduped.append(dict(lv))

    # 按距离当前价排序
    above = sorted([l for l in deduped if l["kind"]=="above"], key=lambda x: x["mid"])
    below = sorted([l for l in deduped if l["kind"]=="below"], key=lambda x: -x["mid"])

    # 限制数量
    above = above[:6]
    below = below[:6]
    return {"above": above, "below": below}


# ════════════════════════════════════════════════════════════
# 场景概率与策略筛选
# ════════════════════════════════════════════════════════════

def build_scenarios(plan, intraday, confluence, ladder, current_price):
    """
    基于共振评分 + 关键位置生成 4 个场景及概率。
    返回 [{title, prob, prob_cls, trigger, structure, action, target, note, color_cls}]
    """
    score = confluence["score"]
    scenarios = []

    above = ladder.get("above", [])
    below = ladder.get("below", [])
    R1 = above[0] if above else None
    R2 = above[1] if len(above) > 1 else None
    S1 = below[0] if below else None
    S2 = below[1] if len(below) > 1 else None

    # 概率分配（基于评分；总和不强制 100%，因为场景可叠加触发）
    if score <= -3:
        p_break_down, p_hold_bounce, p_reach_R, p_breakout_up = 45, 25, 55, 10
    elif score >= 3:
        p_break_down, p_hold_bounce, p_reach_R, p_breakout_up = 15, 50, 30, 35
    else:
        p_break_down, p_hold_bounce, p_reach_R, p_breakout_up = 30, 35, 40, 20

    if S1:
        target_str = f"目标 ${S2['mid']:.1f}" if S2 else f"目标继续下移约 -{intraday['atr_m15']*4:.1f}pt"
        scenarios.append({
            "title":     f"🔴 场景1 · 价格跌破 ${S1['mid']:.1f} 后空头延伸",
            "prob":      p_break_down,
            "prob_cls":  "mid" if p_break_down < 50 else "hi",
            "color":     "bear",
            "structure": f"跌破关键支撑（{S1['badges'][0][1] if S1['badges'] else '前低'}），原支撑转阻力，空头加速",
            "action":    f"等 M15/H1 收盘确认跌破，<strong>反抽 ${S1['mid']:.1f}（破后转阻）受阻收阴</strong>时做空，{target_str}",
            "holder":    "多单立即止损，不抱侥幸",
            "invalid":   f"反抽 ${S1['mid']:.1f} 反而强势收阳并站稳上方 → 放弃做空（假突破）",
        })
    if S1:
        scenarios.append({
            "title":     f"🟢 场景2 · 价格在 ${S1['mid']:.1f} 区域企稳反弹",
            "prob":      p_hold_bounce,
            "prob_cls":  "mid" if p_hold_bounce < 50 else "hi",
            "color":     "bull",
            "structure": "支撑/牛OB 有效，超卖反弹（但高周期偏空时仅短多）",
            "action":    f"M15 收阳 / 锤子线确认后做多，目标 ${R1['mid']:.1f}" if R1 else "M15 收阳后短多",
            "holder":    f"已多单：T1 看 {R1['mid']:.1f}，进入阻力区减仓" if R1 else "已多单：阻力区减仓",
            "invalid":   "M15 跌破支撑下沿 + 收盘破位 → 立即止损",
        })
    if R1:
        if S1 and S2:
            tgt = f"T1 看回落至当前价 ${current_price:.1f}，T2 延伸至 ${S1['mid']:.1f}"
        elif S1:
            tgt = f"T1 看回落至当前价 ${current_price:.1f}，T2 延伸至 ${S1['mid']:.1f}"
        else:
            tgt = "目标看回到当前价位附近"
        scenarios.append({
            "title":     f"🟡 场景3 · 价格反弹至 ${R1['mid']:.1f} 阻力区受阻回落",
            "prob":      p_reach_R,
            "prob_cls":  "hi" if p_reach_R >= 50 else "mid",
            "color":     "warn",
            "structure": "阻力/熊OB 有效，价格在阻力区被拒绝（符合高周期空头逻辑）",
            "action":    f"在 ${R1['mid']:.1f} 区域出现 M15 收阴/吞没/上影线时做空，{tgt}" if S1 else "等阻力区做空信号",
            "holder":    "短多减仓离场",
            "invalid":   f"M15 收盘强势站稳 ${R1['mid']:.1f} 上方（非影线刺穿） → 升级到场景4",
        })
    if R2 or R1:
        target_break = (R2 or R1)
        retest_level = target_break['mid']     # 突破谁就回踩谁
        scenarios.append({
            "title":     f"🟠 场景4 · 价格强势突破 ${target_break['mid']:.1f}（结构反转）",
            "prob":      p_breakout_up,
            "prob_cls":  "lo" if p_breakout_up < 25 else "mid",
            "color":     "gold",
            "structure": "H4 收盘 CHoCH↑ 确认，空头逻辑作废，转入多头框架",
            "action":    f"等 H4 收盘确认突破，<strong>回踩 ${retest_level:.1f}（破后转支撑）不破做多</strong>",
            "holder":    "持空单立即止损，不抗单",
            "invalid":   "通常需要重大消息面催化（NFP / CPI / FOMC / 地缘事件）",
        })
    return scenarios


def normalize_entry_zone(e_low, e_high, current_price, side, buffer=1.0):
    """
    将入场区截断到「相对于当前价的合理一侧」。
      · long  入场必须全部位于当前价 *下方*（等回踩才能买）
      · short 入场必须全部位于当前价 *上方*（等反弹才能卖）
    返回 (low, high) 或 None（整个区域无效，方案应被拒绝）。
    """
    e_low, e_high = float(e_low), float(e_high)
    if side == "long":
        new_high = min(e_high, current_price - buffer)
        new_low  = e_low
    else:  # short
        new_high = e_high
        new_low  = max(e_low, current_price + buffer)
    if new_low >= new_high:
        return None
    return (round(new_low, 1), round(new_high, 1))


def filter_setup(label, entry, sl, tp1, tp2, tp3=None, side="long"):
    """
    计算盈亏比 + 是否达标。
    保守原则：始终用「最差入场价」算 risk 和 reward，避免 R:R 虚高。
      · long  最差入场 = 区间上沿 (entry_high)：风险最大、收益最小
      · short 最差入场 = 区间下沿 (entry_low) ：风险最大、收益最小

    方向校验（防止"反向 TP"虚假 R:R）：
      · long :  TP 必须 > e_worst, SL 必须 < e_worst
      · short:  TP 必须 < e_worst, SL 必须 > e_worst
    校验失败的 TP 会被设为 None；若 TP1 为 None，方案被标记失效。
    """
    if isinstance(entry, (int, float)):
        e_worst = float(entry)
    else:
        e_worst = float(entry[1]) if side == "long" else float(entry[0])

    # SL 方向校验
    if side == "long" and sl >= e_worst:
        return None
    if side == "short" and sl <= e_worst:
        return None

    risk = abs(e_worst - sl)
    if risk <= 0:
        return None

    # 单个 TP 方向校验：错向直接置空
    def _validate_tp(tp):
        if tp is None: return None
        tp = float(tp)
        if side == "long"  and tp <= e_worst: return None
        if side == "short" and tp >= e_worst: return None
        return tp
    tp1 = _validate_tp(tp1)
    tp2 = _validate_tp(tp2)
    tp3 = _validate_tp(tp3)

    # 若 T1 错向 → 方案根本不该开
    if tp1 is None:
        rr1 = 0.0
        status = "❌ 方向无效"; status_cls = "bear"
        status_note = "T1 在错误方向（不在 entry 与目标的合理一侧），<strong>方案作废</strong>"
        return {
            "label": label, "side": side,
            "entry": entry, "sl": sl,
            "tp1": tp1, "tp2": tp2, "tp3": tp3,
            "rr1": 0.0, "rr2": 0.0, "rr3": None,
            "risk": round(risk, 1),
            "ok_t1": False, "ok_strict": False,
            "status": status, "status_cls": status_cls, "status_note": status_note,
        }

    rr1 = (tp1 - e_worst) / risk if side == "long" else (e_worst - tp1) / risk
    rr2 = ((tp2 - e_worst) / risk if side == "long" else (e_worst - tp2) / risk) if tp2 is not None else 0.0
    rr3 = ((tp3 - e_worst) / risk if side == "long" else (e_worst - tp3) / risk) if tp3 is not None else None

    # 判定等级
    if rr1 >= 2.0:
        status = "✅ 高确信"; status_cls = "bull"; status_note = f"T1 R:R 1:{rr1:.1f} 达标，标准仓位"
    elif rr1 >= 1.5:
        status = "⚠ 边界达标"; status_cls = "warn"; status_note = f"T1 R:R 1:{rr1:.1f}（最低门槛 1:1.5），半仓"
    else:
        status = "❌ 不达标"; status_cls = "bear"; status_note = f"T1 R:R 1:{rr1:.2f} 低于规则 1:1.5，<strong>不应开仓</strong>"

    return {
        "label":      label, "side": side,
        "entry":      entry, "sl": sl,
        "tp1": tp1, "tp2": tp2, "tp3": tp3,
        "rr1": round(rr1, 2), "rr2": round(rr2, 2),
        "rr3": round(rr3, 2) if rr3 is not None else None,
        "risk": round(risk, 1),
        "ok_t1":  rr1 >= 1.5,
        "ok_strict": rr1 >= 2.0,
        "status": status, "status_cls": status_cls, "status_note": status_note,
    }


# ════════════════════════════════════════════════════════════
# 渲染层
# ════════════════════════════════════════════════════════════

CSS = """
:root{
  /* 暗金机构调 v2：底色仍深沉，但前景全面提亮，长时间阅读更清晰 */
  --bg0:#0c0c14;--bg1:#10101a;--bg2:#15151f;--bg3:#1a1a26;--bg4:#22222e;
  --gold:#e0b770;--gold-dim:#b89554;--gold-glow:rgba(224,183,112,0.16);
  --bull:#5dd4a8;--bull-dim:#3aa57d;--bull-bg:rgba(93,212,168,0.09);
  --bear:#f08597;--bear-dim:#bd5a6e;--bear-bg:rgba(240,133,151,0.09);
  --warn:#f0b675;--warn-bg:rgba(240,182,117,0.09);
  --info:#7fd0e8;--info-bg:rgba(127,208,232,0.08);
  --neutral:#9aa3b6;--text:#e8ecf4;--text-dim:#bfc6d6;--text-mute:#7a8294;
  --border:rgba(255,255,255,0.08);--border-gold:rgba(224,183,112,0.28);
  --mono:'JetBrains Mono','IBM Plex Mono','Consolas',monospace;
  --display:'Segoe UI','Microsoft YaHei',sans-serif;
  --body:'Microsoft YaHei','Segoe UI',sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--bg0);color:var(--text);font-family:var(--body);font-size:13px;
     line-height:1.6;max-width:1600px;margin:0 auto;padding:70px 20px 40px}
body::before{content:'';position:fixed;inset:0;
     background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.03'/%3E%3C/svg%3E");
     pointer-events:none;z-index:0;opacity:0.4}
.topbar{position:fixed;top:0;left:0;right:0;background:rgba(12,12,20,0.92);
     backdrop-filter:blur(20px);border-bottom:1px solid var(--border-gold);
     z-index:100;display:flex;align-items:center;padding:0 24px;height:52px}
.topbar-logo{font-family:var(--display);font-size:16px;font-weight:800;color:var(--gold);
     letter-spacing:2px;margin-right:32px;white-space:nowrap}
.topbar-logo span{color:var(--text-dim);font-weight:400}
.topbar-nav{display:flex;gap:2px;flex:1;flex-wrap:wrap}
.topbar-nav a{font-family:var(--mono);font-size:10.5px;font-weight:600;color:var(--text-dim);
     text-decoration:none;padding:4px 8px;border-radius:4px;letter-spacing:0.4px;
     transition:all 0.15s;text-transform:uppercase;white-space:nowrap}
.topbar-nav a:hover{color:var(--gold);background:var(--gold-glow)}
.topbar-ts{font-family:var(--mono);font-size:11px;color:var(--text-dim);white-space:nowrap;margin-left:12px}
.topbar-ts .live{color:var(--bull);animation:blink 2s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:0.3}}
.card{background:var(--bg2);border:1px solid var(--border);border-radius:8px;
     padding:20px 22px;margin-bottom:12px;scroll-margin-top:60px}
.card.highlight{border-color:var(--border-gold);background:linear-gradient(135deg,var(--bg2) 0%,rgba(224,183,112,0.04) 100%)}
.sec-label{font-family:var(--display);font-size:12px;font-weight:700;letter-spacing:3px;
     text-transform:uppercase;color:var(--text);padding:18px 0 8px;
     display:flex;align-items:center;gap:10px}
.sec-label::after{content:'';flex:1;height:1px;background:var(--border-gold)}
.sec-label.gold{color:var(--gold)}
.card-title{font-family:var(--display);font-size:14px;font-weight:700;color:var(--gold);
     letter-spacing:1px;text-transform:uppercase;margin-bottom:16px;
     display:flex;align-items:center;gap:10px}
.card-title::before{content:'';display:inline-block;width:3px;height:14px;background:var(--gold);border-radius:2px}
.hero-grid{display:grid;grid-template-columns:2fr 1.2fr 1.2fr 1fr;gap:1px;
     background:var(--border-gold);border-radius:10px;overflow:hidden;
     border:1px solid var(--border-gold);margin-bottom:12px}
.hero-cell{background:var(--bg1);padding:18px 22px}
.hero-label{font-family:var(--mono);font-size:9px;font-weight:500;color:var(--text-mute);
     text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px}
.hero-price{font-family:var(--mono);font-size:38px;font-weight:600;color:var(--gold);
     line-height:1;letter-spacing:-1px;margin-bottom:6px}
.hero-change{font-family:var(--mono);font-size:13px}
.hero-value{font-family:var(--mono);font-size:24px;font-weight:500;line-height:1.2;margin-bottom:4px}
.hero-sub{font-size:11px;color:var(--text-dim);line-height:1.5}
.bias-gauge{display:flex;align-items:center;gap:10px;margin-top:10px}
.gauge-track{flex:1;height:6px;background:linear-gradient(90deg,var(--bear) 0%,#555 50%,var(--bull) 100%);
     border-radius:3px;position:relative}
.gauge-needle{position:absolute;top:-4px;width:14px;height:14px;background:var(--gold);
     border-radius:50%;box-shadow:0 0 4px var(--gold-glow);transform:translateX(-50%);transition:left 0.5s ease}
.gauge-label{font-family:var(--mono);font-size:10px;color:var(--text-mute)}
.pill{display:inline-flex;align-items:center;justify-content:center;padding:2px 8px;border-radius:4px;
     font-family:var(--mono);font-size:10px;font-weight:600;letter-spacing:0.5px}
.pill.bull{background:var(--bull-bg);color:var(--bull);border:1px solid rgba(93,212,168,0.32)}
.pill.bear{background:var(--bear-bg);color:var(--bear);border:1px solid rgba(240,133,151,0.32)}
.pill.neutral{background:rgba(154,163,182,0.10);color:var(--neutral);border:1px solid rgba(154,163,182,0.24)}
.pill.gold{background:var(--gold-glow);color:var(--gold);border:1px solid var(--border-gold)}
.pill.warn{background:var(--warn-bg);color:var(--warn);border:1px solid rgba(240,182,117,0.32)}
.pill.sm{padding:1px 6px;font-size:9px}
table{width:100%;border-collapse:collapse}
th{font-family:var(--mono);font-size:9px;font-weight:600;color:var(--text-mute);
     text-transform:uppercase;letter-spacing:1px;padding:6px 10px;text-align:left;
     border-bottom:1px solid var(--border)}
td{padding:7px 10px;border-bottom:1px solid var(--border);font-size:12px;color:var(--text-dim)}
tr:last-child td{border-bottom:none}
tr:hover td{background:rgba(255,255,255,0.035)}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
.g4{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px}
@media(max-width:1200px){.g4{grid-template-columns:1fr 1fr}.g3{grid-template-columns:1fr 1fr}}
@media(max-width:900px){.g2,.g3,.g4{grid-template-columns:1fr}}
.kpi{background:var(--bg3);border:1px solid var(--border);border-radius:6px;padding:10px 14px}
.kpi .l{font-family:var(--mono);font-size:9px;color:var(--text-mute);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px}
.kpi .v{font-family:var(--mono);font-size:18px;font-weight:600;line-height:1}
.kpi .s{font-size:10px;color:var(--text-mute);margin-top:3px}
.macro-item{display:flex;flex-direction:column;background:var(--bg3);border:1px solid var(--border);
     border-radius:6px;padding:12px 14px}
.macro-item .name{font-family:var(--mono);font-size:9px;color:var(--text-mute);text-transform:uppercase;letter-spacing:1px;margin-bottom:6px}
.macro-item .val{font-family:var(--mono);font-size:16px;font-weight:600;margin-bottom:3px}
.macro-item .desc{font-size:10px;color:var(--text-mute);line-height:1.4}
.macro-item .impact{font-size:10px;margin-top:5px;padding:2px 6px;border-radius:3px;display:inline-block;font-family:var(--mono);align-self:flex-start}
.impact-bull{background:var(--bull-bg);color:var(--bull)}
.impact-bear{background:var(--bear-bg);color:var(--bear)}
.impact-neutral{background:rgba(154,163,182,0.12);color:var(--neutral)}
.cal-item{display:flex;gap:12px;align-items:flex-start;padding:8px 12px;border-radius:5px;
     margin-bottom:4px;border-left:3px solid var(--border);background:var(--bg3)}
.cal-item.high{border-left-color:var(--bear)}
.cal-item.medium{border-left-color:var(--warn)}
.cal-item.low{border-left-color:var(--neutral)}
.cal-time{font-family:var(--mono);font-size:10px;color:var(--text-mute);white-space:nowrap;min-width:90px}
.cal-name{font-size:12px;color:var(--text);flex:1}
.cal-impact{font-family:var(--mono);font-size:9px;font-weight:700;padding:1px 5px;border-radius:3px;white-space:nowrap}
.consensus-bar{display:flex;height:10px;border-radius:5px;overflow:hidden;margin:8px 0;gap:1px}
.cb-bull{background:var(--bull)}.cb-bear{background:var(--bear)}.cb-neu{background:var(--neutral)}
.session-bar{display:flex;gap:4px;margin:8px 0}
.session-seg{flex:1;height:28px;border-radius:4px;display:flex;align-items:center;justify-content:center;
     font-family:var(--mono);font-size:9px;font-weight:600;letter-spacing:0.5px}
.session-asia{background:rgba(93,212,168,0.12);color:var(--bull);border:1px solid rgba(93,212,168,0.24)}
.session-eu{background:rgba(224,183,112,0.12);color:var(--gold);border:1px solid var(--border-gold)}
.session-us{background:rgba(240,133,151,0.12);color:var(--bear);border:1px solid rgba(240,133,151,0.24)}
.session-active{box-shadow:0 0 0 1px currentColor inset}
.smc-map{background:var(--bg1);border:1px solid var(--border);border-radius:8px;padding:16px;font-family:var(--mono);font-size:11px}
.price-ladder{display:flex;flex-direction:column;gap:2px;position:relative}
.ladder-row{display:flex;align-items:center;gap:10px;padding:5px 8px;border-radius:4px}
.ladder-row.current{background:rgba(224,183,112,0.12);border:1px solid var(--border-gold)}
.ladder-row.above,.ladder-row.below{opacity:0.92}
.ladder-price{min-width:90px;font-weight:600}
.ladder-dist{min-width:55px;font-size:10px;color:var(--text-mute)}
.ladder-tag{flex:1;font-size:10px}
.ladder-strength{display:flex;gap:2px}
.str-dot{width:5px;height:5px;border-radius:50%;background:var(--border)}
.str-dot.on{background:var(--gold)}
.badge{font-family:var(--mono);font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;white-space:nowrap;display:inline-block}
.badge-OB-B{background:var(--bull-bg);color:var(--bull)}
.badge-OB-S{background:var(--bear-bg);color:var(--bear)}
.badge-FVG-B{background:var(--info-bg);color:var(--info)}
.badge-FVG-S{background:var(--warn-bg);color:var(--warn)}
.badge-LIQ{background:var(--gold-glow);color:var(--gold)}
.badge-KEY{background:rgba(154,163,182,0.12);color:var(--neutral)}
.plan-box{border-radius:8px;padding:16px 18px;border-width:2px;border-style:solid}
.plan-box.primary-bull{border-color:var(--bull-dim);background:linear-gradient(135deg,#0e1814,#11201a)}
.plan-box.primary-bear{border-color:var(--bear-dim);background:linear-gradient(135deg,#181014,#22141a)}
.plan-box.suppressed{border-color:var(--text-mute);background:var(--bg3);border-style:dashed;opacity:0.6}
.plan-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px}
.plan-title{font-family:var(--display);font-size:15px;font-weight:700}
.plan-rr{font-family:var(--mono);font-size:20px;font-weight:600;color:var(--gold)}
.plan-rr .rr-label{font-size:9px;color:var(--text-mute);text-transform:uppercase;letter-spacing:1px;display:block;text-align:right}
.plan-table td:first-child{width:80px;color:var(--text-mute)}
.plan-table td:last-child{font-family:var(--mono);font-weight:500}
.confidence-row{display:flex;align-items:center;gap:8px;margin-top:12px;padding-top:12px;border-top:1px solid var(--border)}
.conf-stars{color:var(--gold);font-size:14px}
.conf-text{font-size:11px;color:var(--text-dim)}
.scenario{background:var(--bg3);border:1px solid var(--border);border-radius:6px;padding:14px 16px;margin-bottom:8px}
.scenario-header{display:flex;align-items:center;gap:10px;margin-bottom:10px;justify-content:space-between}
.scenario-trigger{font-family:var(--mono);font-size:12px;font-weight:600}
.scenario-prob{font-family:var(--mono);font-size:11px;padding:3px 10px;border-radius:10px}
.prob-hi{background:rgba(93,212,168,0.14);color:var(--bull)}
.prob-mid{background:rgba(240,182,117,0.14);color:var(--warn)}
.prob-lo{background:rgba(154,163,182,0.12);color:var(--neutral)}
.prob-bar{height:4px;border-radius:2px;margin-bottom:10px}
.prob-bar.bull-bar{background:linear-gradient(90deg,var(--bull-dim),var(--bull))}
.prob-bar.bear-bar{background:linear-gradient(90deg,var(--bear-dim),var(--bear))}
.prob-bar.warn-bar{background:linear-gradient(90deg,#7a4d28,var(--warn))}
.prob-bar.gold-bar{background:linear-gradient(90deg,var(--gold-dim),var(--gold))}
.inv-box{background:rgba(240,133,151,0.06);border:1px solid rgba(240,133,151,0.22);border-radius:6px;padding:12px 14px;margin-top:12px}
.tf-block{background:var(--bg3);border:1px solid var(--border);border-radius:6px;overflow:hidden}
.tf-header{display:flex;align-items:center;justify-content:space-between;padding:8px 12px;
     border-bottom:1px solid var(--border);background:var(--bg4)}
.tf-name{font-family:var(--display);font-size:12px;font-weight:700;color:var(--text)}
.tf-body{padding:10px 12px}
.tf-row{display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid var(--border);font-size:11px}
.tf-row:last-child{border-bottom:none}
.tf-row .k{color:var(--text-mute)}
.tf-row .v{font-family:var(--mono);font-weight:500}
.tf-chart{padding:8px 10px;background:var(--bg2);border-bottom:1px solid var(--border)}
.tf-chart img{width:100%;border-radius:4px;display:block}
.rule-row{display:flex;gap:12px;align-items:flex-start;padding:8px 0;border-bottom:1px solid var(--border)}
.rule-row:last-child{border-bottom:none}
.rule-num{font-family:var(--mono);font-size:10px;font-weight:700;color:var(--gold);min-width:20px;margin-top:1px}
.rule-text{font-size:12px;color:var(--text-dim);line-height:1.6}
.rule-text strong{color:var(--text)}
.calc-box{background:var(--bg1);border:1px solid var(--border-gold);border-radius:6px;padding:14px 16px}
.footer{text-align:center;font-family:var(--mono);font-size:10px;color:var(--text-mute);padding:30px 0 10px;letter-spacing:1px}
.footer span{color:var(--gold-dim)}
.mono{font-family:var(--mono)}
.bull{color:var(--bull)}.bear{color:var(--bear)}.gold{color:var(--gold)}.warn{color:var(--warn)}
.dim{color:var(--text-dim)}.mute{color:var(--text-mute)}
.sm{font-size:10px}.xs{font-size:9px}.fw6{font-weight:600}
.mt8{margin-top:8px}.mt12{margin-top:12px}.mb8{margin-bottom:8px}.mb12{margin-bottom:12px}
.hr{height:1px;background:var(--border);margin:16px 0}
.card{animation:fadeUp 0.4s ease both}
@keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}

/* ── 导读语：每节开篇一句话，告诉读者「为什么读这一节」 ── */
.sec-intro{font-size:11.5px;color:var(--text-dim);font-style:italic;line-height:1.7;
     margin:-4px 0 14px;padding:9px 13px;background:rgba(224,183,112,0.05);
     border-left:2px solid var(--gold-dim);border-radius:0 4px 4px 0}
.sec-intro strong{color:var(--text);font-style:normal;font-weight:600}

/* ── II · TL;DR ── */
.tldr-grid{display:grid;grid-template-columns:1.1fr 1.5fr 1.3fr;gap:14px}
@media(max-width:900px){.tldr-grid{grid-template-columns:1fr}}
.tldr-cell{background:var(--bg1);border:1px solid var(--border);border-left:3px solid var(--gold-dim);
     border-radius:6px;padding:14px 16px}
.tldr-cell.bull{border-left-color:var(--bull)}
.tldr-cell.bear{border-left-color:var(--bear)}
.tldr-cell.warn{border-left-color:var(--warn)}
.tldr-k{font-family:var(--mono);font-size:9px;color:var(--text-mute);letter-spacing:2px;
     text-transform:uppercase;margin-bottom:10px}
.tldr-v{font-family:var(--display);font-size:18px;font-weight:600;line-height:1.35;margin-bottom:8px;color:var(--text)}
.tldr-v.bull{color:var(--bull)}.tldr-v.bear{color:var(--bear)}.tldr-v.warn{color:var(--warn)}.tldr-v.gold{color:var(--gold)}
.tldr-d{font-size:11.5px;color:var(--text-mute);line-height:1.7}
.tldr-d strong{color:var(--text-dim)}

/* ── V · 波动与节奏 ── */
.vol-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px;
     padding-bottom:6px;border-bottom:1px solid var(--border)}
.vol-k{font-family:var(--mono);font-size:10px;color:var(--text-mute);text-transform:uppercase;letter-spacing:1.2px}
.edr-track{height:10px;background:var(--bg3);border-radius:5px;overflow:hidden;margin-bottom:12px;
     border:1px solid var(--border)}
.edr-fill{height:100%;border-radius:5px;transition:width 0.5s ease}
.kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:12px}
.kpi-mini{background:var(--bg3);border:1px solid var(--border);border-radius:4px;padding:8px 10px}
.kpi-mini .l{font-family:var(--mono);font-size:8.5px;color:var(--text-mute);letter-spacing:1px;
     text-transform:uppercase;margin-bottom:4px}
.kpi-mini .v{font-family:var(--mono);font-size:14px;font-weight:600;line-height:1;color:var(--text)}
.cadence-note{font-size:11.5px;color:var(--text-dim);line-height:1.75;padding:10px 12px;
     background:rgba(224,183,112,0.05);border-left:2px solid var(--gold);border-radius:0 4px 4px 0}
.atr-tab{width:100%}
.atr-tab td{padding:7px 8px;font-size:11.5px;border-bottom:1px solid var(--border)}
.atr-tab tr:last-child td{border-bottom:none}
.atr-tab td:first-child{color:var(--text-mute);width:90px;font-family:var(--mono);font-size:10px;letter-spacing:0.5px}
.kz-bar{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:6px}
.kz-seg{padding:9px 8px;border-radius:5px;border:1px solid var(--border);background:var(--bg3);text-align:center}
.kz-seg.kz-asia{border-color:rgba(93,212,168,0.28)}
.kz-seg.kz-london{border-color:var(--border-gold)}
.kz-seg.kz-ny{border-color:rgba(240,133,151,0.28)}
.kz-seg.kz-post{border-color:rgba(154,163,182,0.18)}
.kz-name{font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:0.5px;color:var(--text-dim)}
.kz-hint{font-size:9.5px;color:var(--text-mute);margin-top:4px;line-height:1.3}
.kz-seg.kz-active{background:rgba(224,183,112,0.14);border-color:var(--gold);box-shadow:0 0 0 1px var(--gold-glow) inset}
.kz-seg.kz-active .kz-name{color:var(--gold)}
.kz-seg.kz-active .kz-hint{color:var(--text-dim)}

/* ── X · 风控三段勾选 ── */
.ck-card{background:var(--bg3);border:1px solid var(--border);border-radius:6px;padding:14px 16px}
.ck-card.ck-pre{border-top:3px solid var(--bull-dim)}
.ck-card.ck-in{border-top:3px solid var(--gold-dim)}
.ck-card.ck-post{border-top:3px solid var(--bear-dim)}
.ck-title{font-family:var(--display);font-size:11px;font-weight:700;letter-spacing:1.5px;
     text-transform:uppercase;color:var(--text);margin-bottom:10px;padding-bottom:6px;
     border-bottom:1px solid var(--border)}
.ck-title.bull{color:var(--bull)}.ck-title.gold{color:var(--gold)}.ck-title.bear{color:var(--bear)}
.ck-row{display:flex;align-items:flex-start;gap:8px;padding:5px 0;font-size:11.5px;
     color:var(--text-dim);line-height:1.55;cursor:pointer}
.ck-row:hover{color:var(--text)}
.ck-row input{margin-top:3px;accent-color:var(--gold);cursor:pointer;width:13px;height:13px;flex-shrink:0}
.ck-row input:checked + span{color:var(--text-mute);text-decoration:line-through}
.calc-box .calc-h{font-family:var(--mono);font-size:10px;color:var(--gold-dim);letter-spacing:1px;
     text-transform:uppercase;margin-bottom:8px}
.calc-box .calc-f{font-family:var(--mono);font-size:13px;color:var(--text);margin-bottom:6px}
.calc-box .calc-eg{font-family:var(--mono);font-size:11px;color:var(--text-mute)}
.rlimit{width:100%}
.rlimit td{padding:6px 8px;font-size:11.5px;border-bottom:1px solid var(--border)}
.rlimit tr:last-child td{border-bottom:none}
.rlimit td:first-child{color:var(--text-mute);width:90px}

/* ── 99 · 审计页脚 ── */
.audit-tab{width:100%}
.audit-tab td{padding:8px 12px;font-size:11.5px;border-bottom:1px solid var(--border);vertical-align:top}
.audit-tab td.k{color:var(--text-mute);font-family:var(--mono);font-size:9.5px;letter-spacing:1.2px;
     text-transform:uppercase;width:110px;font-weight:600}
.audit-tab tr:last-child td{border-bottom:none}
.disclaimer{margin-top:14px;padding:12px 14px;background:rgba(240,133,151,0.05);
     border-left:3px solid var(--bear-dim);border-radius:0 4px 4px 0;
     font-size:11.5px;color:var(--text-dim);line-height:1.75}
.disclaimer strong{color:var(--bear)}
"""


# ════════════════════════════════════════════════════════════
# 渲染函数
# ════════════════════════════════════════════════════════════

def render_tldr(plan, confluence, intraday):
    """II · 执行摘要 TL;DR：偏向 / 催化 / 操作 三栏先行结论。"""
    if not plan or not confluence:
        return ""
    score = confluence.get("score", 0)
    if score >= 6:
        bias_arrow, bias_text, bias_cls = "▲▲", "强偏多 STRONG LONG", "bull"
    elif score >= 3:
        bias_arrow, bias_text, bias_cls = "▲", "偏多 LONG", "bull"
    elif score <= -6:
        bias_arrow, bias_text, bias_cls = "▼▼", "强偏空 STRONG SHORT", "bear"
    elif score <= -3:
        bias_arrow, bias_text, bias_cls = "▼", "偏空 SHORT", "bear"
    else:
        bias_arrow, bias_text, bias_cls = "■", "震荡 RANGE", "warn"

    if confluence.get("bull_tfs") and confluence.get("bear_tfs"):
        regime = "周期冲突 · 节奏不同步"
    elif abs(score) >= 6:
        regime = "高确信定向 · 顺势加仓窗口"
    elif abs(score) >= 3:
        regime = "弱定向 · 寻最优入场区"
    else:
        regime = "震荡消化 · 等方向选择"

    notes = confluence.get("notes", [])
    catalyst = notes[0] if notes else "H4 / H1 结构权重决定方向，关注关键位反应"

    action_text = plan.get("action", "等待")
    action_desc = plan.get("action_desc", "—")
    action_cls = plan.get("action_cls", "neutral")
    if confluence.get("bull_tfs") and confluence.get("bear_tfs") and "做多" in action_text and score < 0:
        action_text = "⚡ 条件观望"
        action_cls = "warn"
        action_desc = "高周期偏空 + 低周期偏多，<strong class='bear'>禁止追多</strong>，等待明确触发"
    action_cls_map = {"bull": "bull", "bear": "bear", "warn": "warn", "neutral": "gold"}
    action_color_cls = action_cls_map.get(action_cls, "gold")

    return f"""
<div class="sec-label gold" id="tldr">II &nbsp;·&nbsp; 执行摘要 · TL;DR</div>
<div class="card highlight">
  <div class="sec-intro"><strong>一页结论先行。</strong>在向下展开论据前，先确认偏向、催化与今日是否动手；
  下方 III 宏观、IV 偏置矩阵、V 节奏 是这三行的论据，VII 策略、VIII 场景 是这三行的执行路径。</div>
  <div class="tldr-grid">
    <div class="tldr-cell {bias_cls}">
      <div class="tldr-k">BIAS · 偏向</div>
      <div class="tldr-v {bias_cls}">{bias_arrow} {bias_text}</div>
      <div class="tldr-d">共振得分 <span class="mono fw6">{score:+.1f}/10</span><br>REGIME · {regime}</div>
    </div>
    <div class="tldr-cell">
      <div class="tldr-k">CATALYST · 催化</div>
      <div class="tldr-v" style="font-size:14px;line-height:1.55">{catalyst}</div>
      <div class="tldr-d">联动事件请见 <strong>III 宏观</strong> 面板；价格触发位见 <strong>VI SMC</strong>。</div>
    </div>
    <div class="tldr-cell{(' ' + action_color_cls) if action_color_cls in ('bull','bear','warn') else ''}">
      <div class="tldr-k">ACTION · 操作</div>
      <div class="tldr-v {action_color_cls}">{action_text}</div>
      <div class="tldr-d">{action_desc}</div>
    </div>
  </div>
</div>"""


def render_vol_section(intraday, data):
    """V · 波动与节奏：EDR 消耗 / ATR 多周期 / Killzone 时序。"""
    df_d1 = (data or {}).get("daily")
    df_h1 = (data or {}).get("h1")
    today_range = float((intraday or {}).get("today_range", 0) or 0)
    atr_m15 = (intraday or {}).get("atr_m15", "—")
    pos = float((intraday or {}).get("pos_in_range", 0) or 0)
    cur_session = (intraday or {}).get("current_session", "—")

    # EDR (20D)：过去 20 个交易日 (H-L) 均值
    edr = None
    try:
        if df_d1 is not None and len(df_d1) >= 21:
            recent = df_d1.iloc[-21:-1]
            edr = float((recent["High"] - recent["Low"]).mean())
    except Exception:
        edr = None
    edr_used_pct = (today_range / edr * 100) if (edr and edr > 0 and today_range > 0) else 0.0
    edr_remaining = max(0.0, edr - today_range) if edr else 0.0

    # H1 ATR(14)
    atr_h1 = "—"
    try:
        if df_h1 is not None and len(df_h1) >= 15:
            h_, l_, c_ = df_h1["High"], df_h1["Low"], df_h1["Close"]
            tr = pd.concat([(h_ - l_), (h_ - c_.shift()).abs(), (l_ - c_.shift()).abs()], axis=1).max(axis=1)
            atr_h1 = f"{tr.iloc[-14:].mean():.1f}"
    except Exception:
        pass

    # Killzone 时段（北京时间 UTC+8）
    h_now = datetime.now().hour
    if 8 <= h_now < 15:
        active = "asia"
    elif 15 <= h_now < 21:
        active = "london"
    elif h_now >= 21 or h_now < 3:
        active = "ny"
    else:
        active = "post"

    seg_html = ""
    for code, name, hint in [
        ("asia",   "亚盘 08-15",   "区间窄 · 埋伏点"),
        ("london", "伦敦 15-21",   "流动性放量 · 主行情"),
        ("ny",     "纽约 21-03",   "数据驱动 · 扩波"),
        ("post",   "盘后 03-08",   "收敛回归"),
    ]:
        ac = " kz-active" if code == active else ""
        seg_html += (f'<div class="kz-seg kz-{code}{ac}">'
                     f'<div class="kz-name">{name}</div>'
                     f'<div class="kz-hint">{hint}</div></div>')

    edr_bar_w = min(100.0, edr_used_pct)
    if edr_used_pct >= 80:
        edr_color = "var(--bear)"
        cadence_note = "今日波动消耗已 ≥80%，<strong class='bear'>晚段倾向均值回归</strong>，慎追突破。"
    elif edr_used_pct >= 60:
        edr_color = "var(--warn)"
        cadence_note = "波动消耗过半，<strong class='warn'>新仓需要更高确信</strong>，T1 优先短目标。"
    elif edr_used_pct >= 25:
        edr_color = "var(--gold)"
        cadence_note = "波动尚未释放，<strong class='gold'>主行情可能在伦敦/纽约时段</strong>。"
    else:
        edr_color = "var(--bull-dim)"
        cadence_note = "极低波动，<strong class='dim'>等待 Killzone 启动再动手</strong>。"

    edr_str = f"{edr:.1f}" if edr else "—"

    return f"""
<div class="sec-label gold" id="vol">V &nbsp;·&nbsp; 波动与节奏 · EDR / ATR / Killzone</div>
<div class="card highlight">
  <div class="sec-intro"><strong>日内波段成败的一半是节奏。</strong>这一节解决三个问题：
  今日还剩多少波动空间？现在该不该出手？哪个时段才是肉？</div>
  <div class="g2 mb12">
    <div>
      <div class="vol-head"><span class="vol-k">今日波动消耗 · EDR(20D)</span>
           <span class="mono fw6" style="color:{edr_color}">{edr_used_pct:.0f}%</span></div>
      <div class="edr-track"><div class="edr-fill" style="width:{edr_bar_w:.1f}%;background:{edr_color}"></div></div>
      <div class="kpi-row">
        <div class="kpi-mini"><div class="l">EDR (20D)</div><div class="v">{edr_str}</div></div>
        <div class="kpi-mini"><div class="l">今日振幅</div><div class="v gold">{today_range:.1f}</div></div>
        <div class="kpi-mini"><div class="l">剩余空间</div><div class="v">{edr_remaining:.1f}</div></div>
        <div class="kpi-mini"><div class="l">日内位置</div><div class="v warn">{pos:.0f}%</div></div>
      </div>
      <div class="cadence-note">{cadence_note}</div>
    </div>
    <div>
      <div class="vol-head"><span class="vol-k">ATR · 多周期波动尺度</span>
           <span class="mono dim sm">即时</span></div>
      <table class="atr-tab">
        <tr><td>M15 ATR</td><td class="mono fw6">{atr_m15}</td><td class="dim sm">单根 K 平均波幅 · 止损/T1 单位</td></tr>
        <tr><td>H1 ATR(14)</td><td class="mono fw6">{atr_h1}</td><td class="dim sm">小时级波动 · 波段目标尺度</td></tr>
      </table>
      <div class="vol-head" style="margin-top:14px"><span class="vol-k">Killzone · 当前时段 (UTC+8)</span>
           <span class="mono dim sm">{cur_session}</span></div>
      <div class="kz-bar">{seg_html}</div>
      <div class="dim sm" style="margin-top:8px;line-height:1.6">
        机构原则：<strong class="gold">伦敦/纽约开盘前 30 分钟</strong> 是 Sweep 与 Judas 高发窗口，
        亚盘埋伏 + 伦敦验证 + 纽约兑现 是日内波段的标准节奏。
      </div>
    </div>
  </div>
</div>"""


def render_risk_section_v2():
    """X · 风控协议 v2：Pre / In / Post 三段交易勾选清单 + 仓位公式 + 阈值表。"""
    return """
<div class="sec-label gold" id="risk">X &nbsp;·&nbsp; 风控协议 · 三段交易守则</div>
<div class="card highlight">
  <div class="sec-intro"><strong>所有信号都可错。</strong>让你长期活下来的不是模型，是这张可勾选清单。
  开仓前过 PRE，持仓中按 IN，平仓后写 POST，每一项都不可跳。</div>
  <div class="g3">
    <div class="ck-card ck-pre">
      <div class="ck-title bull">PRE-TRADE · 开仓前</div>
      <label class="ck-row"><input type="checkbox"><span>账户日累计回撤 &lt; 1.5%（DDL 未触发）</span></label>
      <label class="ck-row"><input type="checkbox"><span>该笔风险 ≤ 净值 1%（高确信 ≤ 1.5%）</span></label>
      <label class="ck-row"><input type="checkbox"><span>距下一个 HIGH 事件 ≥ 30 分钟（embargo 通过）</span></label>
      <label class="ck-row"><input type="checkbox"><span>R:R T1 ≥ 1:1.5（边界），≥ 1:2.0（标准）</span></label>
      <label class="ck-row"><input type="checkbox"><span>多周期共振 ≥ 2 个 TF 同向</span></label>
      <label class="ck-row"><input type="checkbox"><span>EDR 消耗 &lt; 80%（晚段不追突破）</span></label>
      <label class="ck-row"><input type="checkbox"><span>入场区距当前价合理（不挂远不挂近）</span></label>
    </div>
    <div class="ck-card ck-in">
      <div class="ck-title gold">IN-TRADE · 持仓中</div>
      <label class="ck-row"><input type="checkbox"><span>1× ATR(M15) 内未止损 → 移 SL 到 -0.3R</span></label>
      <label class="ck-row"><input type="checkbox"><span>触及 T1 → 平 50% + SL 移到成本</span></label>
      <label class="ck-row"><input type="checkbox"><span>触及 T2 → 平 30% + SL 移到 T1</span></label>
      <label class="ck-row"><input type="checkbox"><span>跨 Killzone 仍持仓 → 主动减 30%</span></label>
      <label class="ck-row"><input type="checkbox"><span>异常 K（&gt;3×ATR）出现 → 暂停加仓</span></label>
      <label class="ck-row"><input type="checkbox"><span>CHoCH 反向 → 不立即翻向，等 2 根 H1 收盘</span></label>
      <label class="ck-row"><input type="checkbox"><span>禁绝拉止损、禁绝逆势加仓摊成本</span></label>
    </div>
    <div class="ck-card ck-post">
      <div class="ck-title bear">POST-TRADE · 平仓后</div>
      <label class="ck-row"><input type="checkbox"><span>记录 setup / 入场 / 出场 / 反思（30 分钟内）</span></label>
      <label class="ck-row"><input type="checkbox"><span>PnL 落入预期（±1σ），否则触发例外审计</span></label>
      <label class="ck-row"><input type="checkbox"><span>当日累计仓位 ≤ 4，否则强制冷静期 4h</span></label>
      <label class="ck-row"><input type="checkbox"><span>连亏 2 笔 → 当日停止交易</span></label>
      <label class="ck-row"><input type="checkbox"><span>结构准确率 / 执行率 / 盈亏归因 三件套</span></label>
      <label class="ck-row"><input type="checkbox"><span>记入 decision_log.md / daily_audit.md</span></label>
      <label class="ck-row"><input type="checkbox"><span>下一笔不在情绪温度 ≥ 7/10 时开</span></label>
    </div>
  </div>
  <div class="g2 mt12">
    <div class="calc-box">
      <div class="calc-h">仓位规模公式 · Position Sizing</div>
      <div class="calc-f">手数 = (账户净值 × 风险%) ÷ (止损pt × 每点价值)</div>
      <div class="calc-eg">示例：$10,000 × 1% ÷ (12pt × $1) = <span class="gold fw6">0.83 手</span></div>
      <div class="dim sm" style="margin-top:6px;line-height:1.55">
        Kelly 上限：<strong class="gold">25% × Full Kelly</strong>，过度乐观时启动相关性折减
        <span class="mono">final_lots = lots × (1 − max_corr_with_open_pos)</span>。
      </div>
    </div>
    <div class="calc-box">
      <div class="calc-h">关键阈值 · Risk Limits</div>
      <table class="rlimit">
        <tr><td>单笔风险</td><td class="mono fw6">≤ 1.0%</td><td class="dim sm">高确信可至 1.5%</td></tr>
        <tr><td>日累计</td><td class="mono fw6 bear">≤ 2.0%</td><td class="dim sm">触及强制停止当日</td></tr>
        <tr><td>周累计</td><td class="mono fw6 bear">≤ 3.0%</td><td class="dim sm">触及停周</td></tr>
        <tr><td>同时持仓</td><td class="mono fw6">≤ 3 单</td><td class="dim sm">总敞口 ≤ 3%</td></tr>
        <tr><td>R:R 门槛</td><td class="mono fw6">T1 ≥ 1:1.5</td><td class="dim sm">标准 ≥ 1:2.0</td></tr>
        <tr><td>新闻禁交易</td><td class="mono fw6 warn">±30 分钟</td><td class="dim sm">High 事件全程 / Med ±10 分钟</td></tr>
      </table>
    </div>
  </div>
</div>"""


def render_audit_footer(now_str, source, plan, confluence):
    """99 · 审计与披露：报告编号 / 数据源 / 模型版本 / 免责声明。"""
    score = confluence.get("score", 0) if confluence else 0
    bias = confluence.get("bias", "range") if confluence else "range"
    ref = f"GLD-INTRADAY-{datetime.now().strftime('%Y%m%d-%H%M')}-001"
    return f"""
<div class="sec-label gold" id="audit">99 &nbsp;·&nbsp; 审计与披露 · Audit &amp; Disclosures</div>
<div class="card" style="border-color:var(--border-gold);background:var(--bg1)">
  <div class="sec-intro" style="margin-bottom:10px"><strong>每一份机构报告必须可被审计。</strong>
  以下编号、数据源、模型版本与免责声明，是这份报告唯一的"出生证"。</div>
  <table class="audit-tab">
    <tr><td class="k">报告编号</td><td class="mono">{ref}</td>
        <td class="k">签发时间</td><td class="mono">{now_str} <span class="dim sm">UTC+8</span></td></tr>
    <tr><td class="k">分析品种</td><td class="mono">XAU/USD · Spot Gold (Intraday Swing)</td>
        <td class="k">数据源</td><td class="mono">{source}</td></tr>
    <tr><td class="k">模型版本</td><td class="mono">institutional_render · v1.1 (2026-04)</td>
        <td class="k">综合得分</td><td class="mono gold">{score:+.1f}/10 · {bias}</td></tr>
    <tr><td class="k">分发范围</td><td class="mono warn">INTERNAL · NOT FOR REDISTRIBUTION</td>
        <td class="k">有效期</td><td class="mono">24H 或下一次重大事件前</td></tr>
    <tr><td class="k">利益披露</td><td class="mono dim">本桌台 / 模型不持有 XAU 头寸</td>
        <td class="k">复盘记录</td><td class="mono">decision_log.md / daily_audit.md</td></tr>
  </table>
  <div class="disclaimer">
    <strong>免责声明：</strong>本报告由量化模型自动生成，所有数据存在延迟与误差。报告中的偏向、目标位、概率均为
    基于历史规律的<strong>启发式估算</strong>，不构成任何投资建议。最终交易决策由交易员承担全部责任。
    机构纪律 &gt; 模型信号 &gt; 直觉冲动。
  </div>
</div>
<div class="footer">
  GOLDDESK &nbsp;·&nbsp; <span>XAU/USD Institutional Intraday Swing Framework</span><br>
  执行摘要 · 宏观锚点 · 偏置矩阵 · 波动节奏 · SMC/ICT · 策略执行 · 场景树 · 周期详解 · 风控协议<br>
  <span>Generated {now_str}　|　Source {source}</span>
</div>"""


def _impact_pill(impact):
    cls_map = {"bull": ("impact-bull", "📈 利多黄金"),
               "bear": ("impact-bear", "📉 利空黄金"),
               "neutral": ("impact-neutral", "■ 中性")}
    cls, txt = cls_map.get(impact, cls_map["neutral"])
    return f'<div class="impact {cls}">{txt}</div>'


def render_topbar(now_str, source):
    return f"""
<div class="topbar">
  <div class="topbar-logo">GOLD<span>DESK</span></div>
  <nav class="topbar-nav">
    <a href="#cmd">I 指挥</a>
    <a href="#tldr">II 摘要</a>
    <a href="#macro">III 宏观</a>
    <a href="#bias">IV 偏置</a>
    <a href="#vol">V 节奏</a>
    <a href="#smc">VI SMC</a>
    <a href="#plan">VII 策略</a>
    <a href="#scenario">VIII 场景</a>
    <a href="#tf-detail">IX 周期</a>
    <a href="#risk">X 风控</a>
    <a href="#audit">99 审计</a>
  </nav>
  <div class="topbar-ts"><span class="live">●</span>&nbsp;{now_str}&nbsp;|&nbsp;{source}</div>
</div>"""


def render_hero(plan, intraday, confluence, data):
    """顶部命令中心：当前价 / 共振 / 核心指令 / 今日盘感"""
    if not plan:
        return ""
    price = plan["current_price"]

    # 24h 涨跌：优先 H1[-25]；不足则降级用 daily 昨日收盘
    df_h1 = (data or {}).get("h1")
    df_d1 = (data or {}).get("daily")
    change_html = '<span class="dim">—</span>'
    prev, label_24h = None, "24H"
    if df_h1 is not None and len(df_h1) >= 25:
        prev = float(df_h1["Close"].iloc[-25]); label_24h = "24H"
    elif df_d1 is not None and len(df_d1) >= 2:
        prev = float(df_d1["Close"].iloc[-2]);  label_24h = "较昨日"
    if prev is not None and prev > 0:
        diff = price - prev
        pct = diff / prev * 100
        if diff >= 0:
            change_html = f'<span class="bull">▲ +{diff:.2f}&nbsp;(+{pct:.2f}%)&nbsp;{label_24h}</span>'
        else:
            change_html = f'<span class="bear">▼ {diff:.2f}&nbsp;({pct:.2f}%)&nbsp;{label_24h}</span>'

    # 共振条
    consensus_segs = ""
    pill_segs = ""
    for r in confluence["rows"]:
        cls = r["trend_cls"]
        if cls == "bull":
            consensus_segs += f'<div class="cb-bull" style="flex:{r["weight"]}" title="{r["label"]}:多"></div>'
        elif cls == "bear":
            consensus_segs += f'<div class="cb-bear" style="flex:{r["weight"]}" title="{r["label"]}:空"></div>'
        else:
            consensus_segs += f'<div class="cb-neu" style="flex:{r["weight"]}" title="{r["label"]}:中"></div>'
        pill_cls = {"bull": "bull", "bear": "bear", "neutral": "neutral"}[cls]
        pill_arrow = {"bull": "▲", "bear": "▼", "neutral": "■"}[cls]
        pill_segs += f'<span class="pill {pill_cls} sm">{r["label"]} {pill_arrow}</span>'

    # 警示
    if confluence["bull_tfs"] and confluence["bear_tfs"]:
        warn_line = "⚠ 多周期方向冲突 · 共振不足 · 降仓应对"
    elif abs(confluence["score"]) < 3:
        warn_line = "⚠ 共振得分震荡区 · 等待方向选择"
    else:
        warn_line = f"✓ 共振方向一致 · {confluence['action_line']}"

    # 核心指令（来自 plan）
    action_text = plan.get("action", "等待")
    action_desc = plan.get("action_desc", "")
    action_cls  = plan.get("action_cls", "neutral")
    if confluence["bull_tfs"] and confluence["bear_tfs"]:
        if "做多" in action_text and confluence["score"] < 0:
            action_text = "⚡ 条件观望"
            action_cls = "warn"
            action_desc = "高周期偏空 + 低周期偏多 → <strong class='bear'>禁止追多</strong>，等待明确触发条件"

    cmd_color_map = {"bull": "var(--bull)", "bear": "var(--bear)", "warn": "var(--warn)", "neutral": "var(--gold)"}
    cmd_color = cmd_color_map.get(action_cls, "var(--gold)")

    # 今日盘感
    intraday_html = ""
    if intraday:
        cur_session = intraday.get("current_session", "—")
        atr_m15 = intraday.get("atr_m15", "—")
        pos = intraday.get("pos_in_range", 0)
        rng = intraday.get("today_range", 0)
        # 时段高亮
        active_seg = ""
        if "亚盘" in cur_session: active_seg = "asia"
        elif "欧盘" in cur_session: active_seg = "eu"
        elif "美盘" in cur_session: active_seg = "us"
        seg_html = ""
        for code, name in [("asia", "亚盘"), ("eu", "欧盘"), ("us", "美盘")]:
            active_cls = " session-active" if code == active_seg else ""
            seg_html += f'<div class="session-seg session-{code}{active_cls}">{name}</div>'

        intraday_html = f"""
        <div class="session-bar" style="margin-top:8px">{seg_html}</div>
        <div class="hero-sub" style="margin-top:8px">
          24H 振幅 <span class="mono gold">{rng:.1f} pt</span><br>
          M15 ATR <span class="mono">{atr_m15}</span> &nbsp;|&nbsp; 日内位 <span class="mono warn">{pos:.0f}%</span><br>
          <span class="sm dim">{cur_session}</span>
        </div>"""

    return f"""
<div class="hero-grid" id="cmd">
  <div class="hero-cell">
    <div class="hero-label">XAU/USD · 当前价</div>
    <div class="hero-price">${price:,.2f}</div>
    <div class="hero-change">{change_html}</div>
    <div class="bias-gauge" style="margin-top:14px">
      <span class="gauge-label mute">BEAR</span>
      <div class="gauge-track">
        <div class="gauge-needle" style="left:{confluence['score_pct']:.1f}%"></div>
      </div>
      <span class="gauge-label mute">BULL</span>
    </div>
    <div class="sm mute" style="margin-top:6px;font-family:var(--mono)">综合偏向得分 {confluence['score']:+.1f}/10 · {confluence['level']}</div>
  </div>
  <div class="hero-cell">
    <div class="hero-label">多周期共振</div>
    <div class="consensus-bar" style="margin-top:6px">{consensus_segs}</div>
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px">{pill_segs}</div>
    <div class="hero-sub" style="margin-top:10px">{warn_line}</div>
  </div>
  <div class="hero-cell">
    <div class="hero-label">核心指令</div>
    <div class="hero-value" style="font-size:20px;margin-top:4px;color:{cmd_color}">{action_text}</div>
    <div class="hero-sub" style="margin-top:8px">{action_desc}</div>
  </div>
  <div class="hero-cell">
    <div class="hero-label">今日盘感</div>
    {intraday_html}
  </div>
</div>"""


def render_macro_section():
    cfg = MACRO_CONFIG
    items_html = ""
    for key, label in [("dxy", "美元指数 DXY"), ("real_yield", "美债10Y 实际收益率"),
                       ("vix", "避险情绪 VIX"), ("fed_policy", "美联储政策预期")]:
        m = cfg.get(key, {})
        # 带方向着色：bull→绿（利多黄金）bear→红（利空黄金）neutral→灰
        val_color = {"bull": "bull", "bear": "bear", "neutral": "dim"}.get(m.get("impact", "neutral"), "dim")
        items_html += f"""
        <div class="macro-item">
          <div class="name">{label}</div>
          <div class="val {val_color}">{m.get('value', '—')} {m.get('delta','')}</div>
          <div class="desc">{m.get('desc', '—')}</div>
          {_impact_pill(m.get('impact', 'neutral'))}
        </div>"""

    cal_html = ""
    for ev in cfg.get("calendar", []):
        impact = ev.get("impact", "low")
        impact_label = {"high": "高", "medium": "中", "low": "低"}.get(impact, "低")
        impact_bg = {"high": "var(--bear-bg);color:var(--bear)",
                     "medium": "var(--warn-bg);color:var(--warn)",
                     "low": "rgba(154,163,182,0.12);color:var(--neutral)"}[impact]
        cal_html += f"""
        <div class="cal-item {impact}">
          <div class="cal-time">{ev.get('time', '—')}</div>
          <div class="cal-name">{ev.get('name', '')}</div>
          <div class="cal-impact" style="background:{impact_bg}">{impact_label}</div>
        </div>"""

    return f"""
<div class="sec-label gold" id="macro">III &nbsp;·&nbsp; 宏观环境锚点 · Macro Anchors</div>
<div class="card highlight">
  <div class="sec-intro"><strong>价格只是结果，宏观才是因。</strong>美元、利率、避险、政策预期，是决定金价中线方向的四根锚；
  日内交易必须知道宏观风往哪吹，否则只是在和算法对赌。</div>
  <div class="card-title">宏观驱动矩阵 · 黄金核心影响因子</div>
  <div class="g4 mb12">{items_html}</div>
  <div style="background:var(--bg1);border-radius:6px;padding:14px 16px;border:1px solid var(--border-gold)">
    <div style="font-family:var(--mono);font-size:10px;color:var(--gold-dim);letter-spacing:1px;margin-bottom:10px;text-transform:uppercase">宏观综合结论</div>
    <div style="font-size:13px;color:var(--text-dim);line-height:1.85">{cfg.get('macro_summary', '')}</div>
  </div>
  <div style="margin-top:14px">
    <div class="sub-label mb8" style="font-family:var(--mono);font-size:9px;color:var(--text-mute);text-transform:uppercase;letter-spacing:1.5px">⚡ 本周重大经济日历</div>
    {cal_html if cal_html else '<div class="dim sm">日历为空，请在 MACRO_CONFIG.calendar 添加事件</div>'}
    <div style="font-size:10px;color:var(--text-mute);margin-top:6px;padding:6px 10px;background:rgba(240,133,151,0.06);border-radius:4px;border-left:2px solid var(--bear)">
      ⚠ 重大数据前后 <strong style="color:var(--bear)">30分钟内禁止开仓</strong>，持仓在数据前需决策是否减半避险
    </div>
  </div>
</div>"""


def render_confluence_section(confluence):
    rows_html = ""
    for r in confluence["rows"]:
        cls = r["trend_cls"]
        pill_cls = {"bull": "bull", "bear": "bear", "neutral": "neutral"}[cls]
        arrow = {"bull": "▲", "bear": "▼", "neutral": "■"}[cls]
        score = r["score"]
        score_color = "var(--bull)" if score > 0 else ("var(--bear)" if score < 0 else "var(--neutral)")
        rows_html += f"""
        <tr>
          <td><strong style="font-family:var(--display);color:var(--text)">{r['label']}</strong></td>
          <td><span class="pill {pill_cls} sm">{r['structure']}</span></td>
          <td class="dim">{r['bos']}</td>
          <td class="dim">{r['channel']}</td>
          <td style="text-align:center"><span class="pill {pill_cls}">偏{('多' if cls=='bull' else ('空' if cls=='bear' else '中'))} {arrow}</span></td>
          <td style="text-align:center;font-family:var(--mono);color:{score_color};font-weight:600">{score:+.1f}</td>
        </tr>"""

    notes_html = "".join(f"<div>{n}</div>" for n in confluence["notes"]) or "<div class='dim'>—</div>"

    return f"""
<div class="sec-label gold" id="bias">IV &nbsp;·&nbsp; 多周期偏置矩阵 · Bias Matrix</div>
<div class="card highlight">
  <div class="sec-intro"><strong>把宏观结论翻译成价格行为。</strong>D1 决定方向、H4 决定结构、H1 决定时机、M15 决定扳机；
  四个周期同向才是顺势，分裂时只能小仓位摸鱼。</div>
  <div class="card-title">多周期价格行为共振矩阵 (TF 权重 D=2 / H4=3 / H1=2 / M15=1)</div>
  <div style="overflow-x:auto">
  <table style="min-width:700px">
    <thead>
      <tr><th style="width:70px">周期</th><th>市场结构</th><th>BOS/CHoCH</th><th>趋势通道</th>
          <th style="width:110px">偏向信号</th><th style="width:60px;text-align:center">得分</th></tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
  </div>

  <div class="g2 mt12">
    <div style="background:var(--bg1);border-radius:6px;padding:14px 16px;border:1px solid var(--border)">
      <div style="font-family:var(--mono);font-size:9px;color:var(--text-mute);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">共振评分 · 综合</div>
      <div style="font-family:var(--mono);font-size:32px;font-weight:600;color:var(--{confluence['level_cls']})">{confluence['score']:+.1f} / 10</div>
      <div style="font-size:11px;color:var(--text-mute);margin-top:4px">{confluence['level']} · {confluence['action_line']}</div>
      <div class="mt8" style="font-size:12px;color:var(--text-dim);line-height:1.85">{notes_html}</div>
    </div>
    <div style="background:var(--bg1);border-radius:6px;padding:14px 16px;border:1px solid var(--border)">
      <div style="font-family:var(--mono);font-size:9px;color:var(--text-mute);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">操作分级阈值</div>
      <table style="font-size:11px">
        <tr><td style="color:var(--text-mute);padding:5px 8px;width:80px">+7 ~ +10</td><td><span class="pill bull sm">高确信做多</span> 全仓可用</td></tr>
        <tr><td style="color:var(--text-mute);padding:5px 8px">+3 ~ +6</td><td><span class="pill bull sm" style="background:rgba(93,212,168,0.06)">做多偏向</span> 半仓介入</td></tr>
        <tr><td style="color:var(--text-mute);padding:5px 8px">−2 ~ +2</td><td><span class="pill warn sm">震荡观望</span> 等待明确</td></tr>
        <tr><td style="color:var(--text-mute);padding:5px 8px">−3 ~ −6</td><td><span class="pill bear sm" style="background:rgba(240,133,151,0.06)">做空偏向</span> 半仓介入</td></tr>
        <tr><td style="color:var(--text-mute);padding:5px 8px">−7 ~ −10</td><td><span class="pill bear sm">高确信做空</span> 全仓可用</td></tr>
      </table>
      <div style="margin-top:10px;padding:8px 10px;background:var(--{confluence['level_cls']}-bg, var(--warn-bg));border-radius:4px;font-size:11px;color:var(--{confluence['level_cls']})">
        当前得分 {confluence['score']:+.1f} → <strong>{confluence['level']}</strong>
      </div>
    </div>
  </div>
</div>"""


def render_smc_section(ladder, current_price):
    rows = []
    # 上方（远 → 近）
    for lv in reversed(ladder["above"]):
        rows.append(("above", lv))
    # 当前
    rows.append(("current", None))
    # 下方（近 → 远）
    for lv in ladder["below"]:
        rows.append(("below", lv))

    rows_html = ""
    for kind, lv in rows:
        if kind == "current":
            rows_html += f"""
            <div class="ladder-row current">
              <div class="ladder-price gold" style="font-size:15px">▶ {current_price:,.2f}</div>
              <div class="ladder-dist" style="color:var(--gold)">NOW</div>
              <div class="ladder-tag gold fw6">当前价格</div>
              <div class="ladder-strength"><div class="str-dot on" style="background:var(--gold)"></div></div>
            </div>"""
            continue
        price_str = f"{lv['low']:.1f}" if lv["low"] == lv["high"] else f"{lv['low']:.1f}–{lv['high']:.1f}"
        dist = lv["mid"] - current_price
        dist_str = f"{dist:+.1f}"
        price_color = "bear" if kind == "above" else "bull"
        badges_html = ""
        for code, label in lv["badges"][:3]:
            badges_html += f'<span class="badge badge-{code}">{label}</span>&nbsp;'
        # strength
        st = max(1, min(5, lv["strength"]))
        dots_html = ""
        for i in range(5):
            dots_html += f'<div class="str-dot{" on" if i < st else ""}"></div>'
        rows_html += f"""
        <div class="ladder-row {kind}">
          <div class="ladder-price {price_color}">{price_str}</div>
          <div class="ladder-dist mute">{dist_str}</div>
          <div class="ladder-tag">{badges_html}</div>
          <div class="ladder-strength">{dots_html}</div>
        </div>"""

    # 关键结论
    above0 = ladder["above"][0] if ladder["above"] else None
    below0 = ladder["below"][0] if ladder["below"] else None
    conclusion = []
    if below0:
        bn = "/".join([b[1] for b in below0["badges"][:2]])
        conclusion.append(f"① 下方最强防线：<strong class='bull'>${below0['mid']:.1f}</strong>（{bn}）距 {abs(below0['mid']-current_price):.1f} pt")
    if above0:
        an = "/".join([b[1] for b in above0["badges"][:2]])
        conclusion.append(f"② 上方最近阻力：<strong class='bear'>${above0['mid']:.1f}</strong>（{an}）距 {abs(above0['mid']-current_price):.1f} pt")
    has_liq_above = any("LIQ" in [b[0] for b in lv["badges"]] for lv in ladder["above"])
    has_liq_below = any("LIQ" in [b[0] for b in lv["badges"]] for lv in ladder["below"])
    if has_liq_above and has_liq_below:
        conclusion.append("③ 上下均存在 <strong class='gold'>流动性池</strong>，机构倾向先扫单再走方向")
    elif has_liq_above:
        conclusion.append("③ 上方有 <strong class='gold'>BSL 买方流动性</strong>，警惕假突破后做空机会")
    elif has_liq_below:
        conclusion.append("③ 下方有 <strong class='gold'>SSL 卖方流动性</strong>，警惕扫单后反弹机会")
    conclusion_html = "<br>".join(conclusion) if conclusion else "—"

    return f"""
<div class="sec-label gold" id="smc">VI &nbsp;·&nbsp; SMC / ICT 机构行为地图 · Liquidity &amp; OB</div>
<div class="card highlight">
  <div class="sec-intro"><strong>这一节告诉你「机构在哪等」。</strong>OB 是它们留下的脚印、FVG 是它们错过的回头票、
  SSL/BSL 是它们准备打劫的止损池；下一节 VII 的入场区，就建在这张地图上。</div>
  <div class="card-title">流动性 · Order Block · FVG 综合地图</div>
  <div class="g2">
    <div class="smc-map">
      <div style="font-family:var(--mono);font-size:9px;color:var(--text-mute);letter-spacing:1px;margin-bottom:10px;text-transform:uppercase">价格结构梯度 · 当前价 ${current_price:,.2f}</div>
      <div class="price-ladder">{rows_html}</div>
    </div>
    <div>
      <div style="background:var(--bg3);border-radius:6px;padding:14px 16px;border:1px solid var(--border);margin-bottom:10px">
        <div style="font-family:var(--mono);font-size:9px;color:var(--text-mute);letter-spacing:1px;text-transform:uppercase;margin-bottom:10px">SMC/ICT 要素说明</div>
        <div class="tf-row"><div class="k"><span class="badge badge-OB-S">熊OB</span></div><div class="v dim">机构卖单原始区 · 回测=最优做空点</div></div>
        <div class="tf-row"><div class="k"><span class="badge badge-OB-B">牛OB</span></div><div class="v dim">机构买单原始区 · 回测=最优做多点</div></div>
        <div class="tf-row"><div class="k"><span class="badge badge-FVG-S">FVG↓</span></div><div class="v dim">看空缺口 · 回补后做空</div></div>
        <div class="tf-row"><div class="k"><span class="badge badge-FVG-B">FVG↑</span></div><div class="v dim">看多缺口 · 回补后支撑做多</div></div>
        <div class="tf-row"><div class="k"><span class="badge badge-LIQ">SSL/BSL</span></div><div class="v dim">流动性池 · 止损单聚集，机构惯用扫单位置</div></div>
        <div class="tf-row" style="border-bottom:none"><div class="k"><span class="badge badge-KEY">KEY</span></div><div class="v dim">关键支阻 / 整数关口 / 前高前低</div></div>
      </div>
      <div style="background:var(--bg3);border-radius:6px;padding:14px 16px;border:1px solid var(--border-gold)">
        <div style="font-family:var(--mono);font-size:9px;color:var(--gold-dim);letter-spacing:1px;text-transform:uppercase;margin-bottom:10px">当前 SMC 核心结论</div>
        <div style="font-size:12px;line-height:1.85;color:var(--text-dim)">{conclusion_html}</div>
      </div>
    </div>
  </div>
</div>"""


def render_plans_section(plan, intraday, confluence, ladder):
    """
    渲染策略执行单。基于现有 intraday 的 long_plan / short_plan，
    叠加 OB 入场区作为升级方案，并执行 R:R 过滤。

    关键约束（防方向错误）：
      · 做多入场区必须全部 < 当前价；做空入场区必须全部 > 当前价
      · 跨越当前价的 OB 自动截断；截断后无效则该 OB 不可用，回落到日内通道
    """
    if not intraday or not plan:
        return ""

    current_price = plan["current_price"]
    score = confluence["score"]
    above = ladder.get("above", [])
    below = ladder.get("below", [])

    # 优先级：根据共振评分决定主次方案
    if score >= 3:
        long_status = "✅ 首选·顺势"; long_status_cls = "bull"
        short_status = "⚠ 次选·逆势"; short_status_cls = "warn"
    elif score <= -3:
        long_status = "⚠ 次选·逆势"; long_status_cls = "warn"
        short_status = "✅ 首选·顺势"; short_status_cls = "bull"
    else:
        long_status = "○ 备选"; long_status_cls = "neutral"
        short_status = "○ 备选"; short_status_cls = "neutral"

    long_plan_data = intraday["long_plan"]
    short_plan_data = intraday["short_plan"]

    # 寻找最近的 OB 作为入场区（仅在合理一侧）
    bull_ob = next((lv for lv in below if any(b[0]=="OB-B" for b in lv["badges"])), None)
    bear_ob = next((lv for lv in above if any(b[0]=="OB-S" for b in lv["badges"])), None)

    # ── 做多方案
    long_filtered = None
    used_ob_long = False
    if bull_ob:
        clipped = normalize_entry_zone(bull_ob["low"], bull_ob["high"], current_price, "long")
        if clipped:
            e_low, e_high = clipped
            sl = round(e_low - intraday["atr_m15"] * 1.5, 1)
            tp1 = above[0]["mid"] if above else round(e_high + intraday["atr_m15"] * 4, 1)
            tp2 = above[1]["mid"] if len(above) > 1 else round(tp1 + intraday["atr_m15"] * 3, 1)
            tp3 = above[2]["mid"] if len(above) > 2 else None
            long_filtered = filter_setup("做多方案 A", (e_low, e_high), sl, tp1, tp2, tp3, side="long")
            if long_filtered:
                used_ob_long = True
                clip_note = "（已截断到当前价下方）" if (bull_ob["high"] != e_high) else ""
                long_filtered["entry_label"] = f"${e_low:.1f} – ${e_high:.1f}"
                long_filtered["entry_note"]  = "/".join([b[1] for b in bull_ob["badges"][:2]]) + clip_note
                long_filtered["tp_notes"] = [
                    (above[0]["badges"][0][1] if above else "ATR延伸位"),
                    (above[1]["badges"][0][1] if len(above)>1 else "ATR×3"),
                    (above[2]["badges"][0][1] if len(above)>2 else None),
                ]
    if not long_filtered:
        # 回落到日内通道入场
        e_low, e_high = long_plan_data["entry_low"], long_plan_data["entry_high"]
        clipped = normalize_entry_zone(e_low, e_high, current_price, "long")
        if clipped:
            e_low, e_high = clipped
            long_filtered = filter_setup("做多方案 A", (e_low, e_high),
                                         long_plan_data["sl"], long_plan_data["tp1"],
                                         long_plan_data["tp2"], side="long")
            if long_filtered:
                long_filtered["entry_label"] = f"${e_low:.1f} – ${e_high:.1f}"
                long_filtered["entry_note"]  = "日内低点+5~20%"
                long_filtered["tp_notes"] = ["日内中枢", "日内高点", None]
        if not long_filtered:
            # 整个做多入场区都在错误位置 → 显式拒绝
            long_filtered = {
                "label": "做多方案 A", "side": "long",
                "entry": (current_price, current_price), "sl": 0,
                "tp1": None, "tp2": None, "tp3": None,
                "rr1": 0, "rr2": 0, "rr3": None, "risk": 0,
                "ok_t1": False, "ok_strict": False,
                "status": "❌ 入场区错位", "status_cls": "bear",
                "status_note": "可用入场区均在当前价上方（价格已超过 OB/通道）→ <strong>等价格回调到合理位再评估</strong>",
                "entry_label": "—", "entry_note": "无可用入场区",
                "tp_notes": [None, None, None],
            }

    # ── 做空方案
    short_filtered = None
    used_ob_short = False
    if bear_ob:
        clipped = normalize_entry_zone(bear_ob["low"], bear_ob["high"], current_price, "short")
        if clipped:
            e_low, e_high = clipped
            sl = round(e_high + intraday["atr_m15"] * 1.5, 1)
            tp1 = below[0]["mid"] if below else round(e_low - intraday["atr_m15"] * 4, 1)
            tp2 = below[1]["mid"] if len(below) > 1 else round(tp1 - intraday["atr_m15"] * 3, 1)
            tp3 = below[2]["mid"] if len(below) > 2 else None
            short_filtered = filter_setup("做空方案 B", (e_low, e_high), sl, tp1, tp2, tp3, side="short")
            if short_filtered:
                used_ob_short = True
                clip_note = "（已截断到当前价上方）" if (bear_ob["low"] != e_low) else ""
                short_filtered["entry_label"] = f"${e_low:.1f} – ${e_high:.1f}"
                short_filtered["entry_note"]  = "/".join([b[1] for b in bear_ob["badges"][:2]]) + clip_note
                short_filtered["tp_notes"] = [
                    (below[0]["badges"][0][1] if below else "ATR延伸位"),
                    (below[1]["badges"][0][1] if len(below)>1 else "ATR×3"),
                    (below[2]["badges"][0][1] if len(below)>2 else None),
                ]
    if not short_filtered:
        e_low, e_high = short_plan_data["entry_low"], short_plan_data["entry_high"]
        clipped = normalize_entry_zone(e_low, e_high, current_price, "short")
        if clipped:
            e_low, e_high = clipped
            short_filtered = filter_setup("做空方案 B", (e_low, e_high),
                                          short_plan_data["sl"], short_plan_data["tp1"],
                                          short_plan_data["tp2"], side="short")
            if short_filtered:
                short_filtered["entry_label"] = f"${e_low:.1f} – ${e_high:.1f}"
                short_filtered["entry_note"]  = "日内高点-5~20%"
                short_filtered["tp_notes"] = ["日内中枢", "日内低点", None]
        if not short_filtered:
            short_filtered = {
                "label": "做空方案 B", "side": "short",
                "entry": (current_price, current_price), "sl": 0,
                "tp1": None, "tp2": None, "tp3": None,
                "rr1": 0, "rr2": 0, "rr3": None, "risk": 0,
                "ok_t1": False, "ok_strict": False,
                "status": "❌ 入场区错位", "status_cls": "bear",
                "status_note": "可用入场区均在当前价下方（价格已跌破 OB/通道）→ <strong>等价格反弹到合理位再评估</strong>",
                "entry_label": "—", "entry_note": "无可用入场区",
                "tp_notes": [None, None, None],
            }

    def _plan_box(plan_d, kind, status, status_cls):
        if plan_d is None:
            return ""
        title_color = "bull" if kind == "long" else "bear"
        title_emoji = "📈 做多" if kind == "long" else "📉 做空"

        # 入场区错位：显示极简警示卡，不显示数字
        if "错位" in plan_d["status"]:
            return f"""
<div class="plan-box suppressed">
  <div class="plan-header">
    <div>
      <div class="plan-title {title_color}">{title_emoji} {plan_d['label']} &nbsp;<span class="pill bear" style="font-size:10px;vertical-align:middle">❌ 暂无方案</span></div>
      <div style="font-size:11px;color:var(--text-mute);margin-top:4px">{plan_d['status']}</div>
    </div>
  </div>
  <div style="background:rgba(240,133,151,0.08);border-radius:6px;padding:14px 16px;margin-top:8px;font-size:12px;color:var(--text-dim);line-height:1.85">
    {plan_d['status_note']}
  </div>
</div>"""

        # 卡片色彩
        card_cls = "primary-bull" if kind == "long" else "primary-bear"
        if not plan_d["ok_t1"]:
            card_cls = "suppressed"
        target_color = "bull" if kind == "long" else "bear"
        sl_color = "bear" if kind == "long" else "bull"

        # 置信度星
        if plan_d["ok_strict"] and status_cls == "bull":
            stars = "★★★★☆"; conf = "70%"; conf_note = "顺势 + 盈亏比达标，<strong class='bull'>可用标准仓位的80%</strong>"
        elif plan_d["ok_strict"] and status_cls == "warn":
            stars = "★★☆☆☆"; conf = "40%"; conf_note = "盈亏比达标但逆势，<strong class='warn'>仅用标准仓位的50%</strong>"
        elif plan_d["ok_t1"]:
            stars = "★★☆☆☆"; conf = "35%"; conf_note = "盈亏比边界达标，<strong class='warn'>仓位减半</strong>"
        else:
            stars = "★☆☆☆☆"; conf = "<20%"; conf_note = "<strong class='bear'>盈亏比不达标，按规则不应开仓</strong>"

        tp_rows = ""
        for i, (tp, rr, note) in enumerate([
            (plan_d["tp1"], plan_d["rr1"], plan_d["tp_notes"][0]),
            (plan_d["tp2"], plan_d["rr2"], plan_d["tp_notes"][1]),
            (plan_d["tp3"], plan_d["rr3"], plan_d["tp_notes"][2]),
        ]):
            if tp is None: continue
            ok = "✓" if rr >= 1.5 else "✗"
            ok_color = "bull" if rr >= 2.0 else ("warn" if rr >= 1.5 else "bear")
            tp_rows += f"""
            <tr>
              <td>目标 T{i+1}</td>
              <td class="{target_color}">${tp:.1f}</td>
              <td class="xs mute">{note or '—'} &nbsp;<span class="{ok_color}">R:R 1:{rr:.2f} {ok}</span></td>
            </tr>"""

        return f"""
<div class="plan-box {card_cls}">
  <div class="plan-header">
    <div>
      <div class="plan-title {title_color}">{title_emoji} {plan_d['label']} &nbsp;<span class="pill {status_cls}" style="font-size:10px;vertical-align:middle">{status}</span></div>
      <div style="font-size:11px;color:var(--text-mute);margin-top:4px">{plan_d['status']} · {plan_d['status_note']}</div>
    </div>
    <div>
      <div class="rr-label">盈亏比 T2</div>
      <div class="plan-rr">1 : {plan_d['rr2']:.1f}</div>
    </div>
  </div>
  <table class="plan-table">
    <tr><td>入场区</td><td class="{target_color}">{plan_d['entry_label']}</td><td class="xs mute">{plan_d['entry_note']}</td></tr>
    <tr><td>止损</td><td class="{sl_color}">${plan_d['sl']:.1f}</td><td class="xs mute">风险 {plan_d['risk']:.1f} pt</td></tr>
    {tp_rows}
  </table>
  <div class="confidence-row">
    <div class="conf-stars">{stars}</div>
    <div class="conf-text">置信度 {conf} · {conf_note}</div>
  </div>
</div>"""

    long_html  = _plan_box(long_filtered,  "long",  long_status,  long_status_cls)
    short_html = _plan_box(short_filtered, "short", short_status, short_status_cls)

    # 顶部统一状态提示：双方案都不达标 → 强制观望
    if long_filtered and short_filtered and not long_filtered["ok_t1"] and not short_filtered["ok_t1"]:
        banner = ("<div class='card' style='border-color:var(--bear);background:rgba(240,133,151,0.07);margin-bottom:8px'>"
                  "<div style='font-size:13px;color:var(--bear);font-weight:600;margin-bottom:4px'>⛔ 今日观望</div>"
                  "<div style='font-size:12px;color:var(--text-dim);line-height:1.7'>"
                  "双方案 R:R 均 &lt; 1:1.5，均未达到 R3 门槛（价格距关键位过近/过远，赋赔不划算）。"
                  "<strong style='color:var(--bear)'>今日不应开仓</strong>，等价格接近 OB / 点位后重新评估。"
                  "</div></div>")
    elif long_filtered and not long_filtered["ok_t1"] and short_filtered and short_filtered["ok_t1"]:
        banner = ("<div class='card' style='border-color:var(--warn);background:var(--warn-bg);margin-bottom:8px'>"
                  "<div style='font-size:12px;color:var(--warn)'>⚠ 只有做空方案达标，做多方案被拒：仅考虑做空。</div></div>")
    elif short_filtered and not short_filtered["ok_t1"] and long_filtered and long_filtered["ok_t1"]:
        banner = ("<div class='card' style='border-color:var(--warn);background:var(--warn-bg);margin-bottom:8px'>"
                  "<div style='font-size:12px;color:var(--warn)'>⚠ 只有做多方案达标，做空方案被拒：仅考虑做多。</div></div>")
    else:
        banner = ""

    return f"""
<div class="sec-label gold" id="plan">VII &nbsp;·&nbsp; 策略执行单 · Trade Plans (OB 入场 + R:R 过滤)</div>
<div class="sec-intro"><strong>从地图到扳机。</strong>每张卡 = 一个完整 setup（入场 / 止损 / 三段目标 / R:R 等级 / 失效条件）；
R:R T1 不达 1:1.5 自动降级为「不应开仓」，以防情绪追单。</div>
{banner}
<div class="g2">
  {long_html}
  {short_html}
</div>
<div class="card" style="margin-top:8px;border-style:dashed;border-color:var(--border-gold)">
  <div style="font-size:11px;color:var(--text-mute);line-height:1.8">
    💡 <strong style="color:var(--gold)">入场区优先策略</strong>：当存在牛OB/熊OB 时，入场区自动收紧到 OB 范围；若无 OB 数据则回落到日内通道。
    <strong style="color:var(--warn)">所有方案严格遵守 R3 规则</strong>：T1 R:R &lt; 1:1.5 时方案被压制（虚线灰色框）。
  </div>
</div>"""


def render_scenarios_section(scenarios):
    if not scenarios:
        return ""
    items = ""
    for sc in scenarios:
        prob = sc["prob"]
        prob_cls = "prob-" + sc["prob_cls"]
        bar_cls = {"bull": "bull-bar", "bear": "bear-bar", "warn": "warn-bar", "gold": "gold-bar"}.get(sc["color"], "warn-bar")
        items += f"""
        <div class="scenario" style="border-color:rgba(154,163,182,0.22)">
          <div class="scenario-header">
            <div class="scenario-trigger {sc['color']}">{sc['title']}</div>
            <div class="scenario-prob {prob_cls}">概率 {prob}%</div>
          </div>
          <div class="prob-bar {bar_cls}" style="width:{prob}%"></div>
          <table style="font-size:12px">
            <tr><td style="width:110px;color:var(--text-mute)">结构含义</td><td>{sc['structure']}</td></tr>
            <tr><td style="color:var(--text-mute)">执行动作</td><td class="{sc['color']} fw6">{sc['action']}</td></tr>
            <tr><td style="color:var(--text-mute)">持仓者</td><td>{sc['holder']}</td></tr>
            <tr><td style="color:var(--text-mute);border-bottom:none">失效条件</td><td style="border-bottom:none">{sc['invalid']}</td></tr>
          </table>
        </div>"""

    return f"""
<div class="sec-label gold" id="scenario">VIII &nbsp;·&nbsp; 场景概率决策树 · Scenario Tree</div>
<div class="card highlight">
  <div class="sec-intro"><strong>市场只走三种路：上、下、横。</strong>提前为每条路写好「触发条件 / 失效条件 / 应对动作」，
  比临盘拍脑袋决定快一个量级；这是日内波段的「if-then」程序化大脑。</div>
  <div class="card-title">If-Then 场景应对 · 概率加权（启发式估算）</div>
  {items}
  <div class="inv-box">
    <div style="font-family:var(--mono);font-size:9px;color:var(--bear);letter-spacing:1.5px;text-transform:uppercase;margin-bottom:8px">⚠ 所有方案通用失效条件</div>
    <div style="font-size:12px;color:var(--text-dim);line-height:1.85">
      · 非农/CPI/FOMC 等重大数据发布前后 30分钟：<strong class="bear">关闭所有仓位</strong><br>
      · 连续亏损2笔后：<strong class="bear">当日停止交易，复盘归因</strong><br>
      · 单日最大亏损达账户 2%：<strong class="bear">强制停止</strong><br>
      · M15/H1 突然出现异常大K线（&gt;3×ATR）：<strong class="warn">暂停判断，等待结构稳定</strong>
    </div>
  </div>
</div>"""


def render_tf_detail_section(analyses, charts, confluence):
    """周期详解：每周期一个块，嵌入结构图。"""
    blocks = []
    score_by_tf = {r["tf"]: r["score"] for r in confluence["rows"]}
    for key in ("daily", "h4", "h1", "m15"):
        a = analyses.get(key)
        label_full = {"daily": "日线 DAILY", "h4": "H4 · 4小时", "h1": "H1 · 1小时", "m15": "M15 · 15分钟"}[key]
        if not a or "error" in a:
            blocks.append(f"""
<div class="tf-block card" style="padding:0;margin-bottom:0">
  <div class="tf-header"><div class="tf-name">{label_full}</div><span class="pill neutral sm">数据不足</span></div>
  <div class="tf-body"><div class="dim sm">无数据</div></div>
</div>""")
            continue
        s = a["structure"]
        ch = a.get("channel")
        cls = s["trend_cls"]
        pill_cls = {"bull": "bull", "bear": "bear", "neutral": "neutral"}[cls]
        arrow = {"bull": "▲", "bear": "▼", "neutral": "■"}[cls]
        score = score_by_tf.get(key, 0)

        bos_str = "近期无新事件"
        bos_cls = "mute"
        if a.get("bos_events"):
            ev = a["bos_events"][-1]
            bos_str = f"{ev.get('type','')} @ {ev.get('price','—')}"
            bos_cls = "bear" if "↓" in ev.get("type","") else "bull"

        ch_str = "—"
        if ch:
            ch_str = f"{ch.get('direction','—')} · 价位 {ch.get('position_pct',50):.0f}%"

        chart_b64 = charts.get(key, "")
        chart_html = ""
        if chart_b64:
            chart_html = f'<div class="tf-chart"><img src="data:image/png;base64,{chart_b64}"/></div>'

        # 关键位
        all_pivots = a.get("all_pivots", [])
        latest_h = next((p for p in reversed(all_pivots) if p[2]=="H"), None)
        latest_l = next((p for p in reversed(all_pivots) if p[2]=="L"), None)
        h_str = f"${latest_h[1]:.1f}" if latest_h else "—"
        l_str = f"${latest_l[1]:.1f}" if latest_l else "—"

        action_advice = {
            "bull": "顺势找回踩入场",
            "bear": "顺势找反弹做空",
            "neutral": "等结构明确再操作",
        }[cls]

        blocks.append(f"""
<div class="tf-block card" style="padding:0;margin-bottom:0">
  <div class="tf-header">
    <div class="tf-name">{label_full}</div>
    <div style="display:flex;gap:6px;align-items:center">
      <span class="pill {pill_cls} sm">{s.get('trend','—')} {arrow}</span>
      <span class="mono sm dim">得分 {score:+.1f}</span>
    </div>
  </div>
  {chart_html}
  <div class="tf-body">
    <div class="tf-row"><div class="k">市场结构</div><div class="v {pill_cls}">{s.get('trend','—')}</div></div>
    <div class="tf-row"><div class="k">已触发事件</div><div class="v {bos_cls}">{bos_str}</div></div>
    <div class="tf-row"><div class="k">趋势通道</div><div class="v">{ch_str}</div></div>
    <div class="tf-row"><div class="k">最近高/低点</div><div class="v"><span class="bear">{h_str}</span> / <span class="bull">{l_str}</span></div></div>
    <div class="tf-row"><div class="k">操作建议</div><div class="v {pill_cls}">{action_advice}</div></div>
  </div>
</div>""")

    # 2x2 布局
    return f"""
<div class="sec-label gold" id="tf-detail">IX &nbsp;·&nbsp; 多周期结构详解 · Per-TF Deep Dive</div>
<div class="sec-intro"><strong>把 IV 矩阵的每一行展开。</strong>每个周期一张结构图 + 关键事件 + 通道位置，
用来回答「为什么这个周期是这个分」「下一根 K 线我看哪里」。</div>
<div class="g2">
  {blocks[0]}
  {blocks[1]}
</div>
<div class="g2 mt12">
  {blocks[2]}
  {blocks[3]}
</div>"""


def render_institutional_html(analyses, plan, narrative, intraday, source, data, charts):
    """主入口：拼装机构级 HTML 报告。
    页面顺序（前后逻辑链）：
      I  指挥中心 (hero)        ─ 当前价 / 共振仪表 / 时段
      II  执行摘要 TL;DR          ─ 偏向 / 催化 / 操作 三行先行结论
      III 宏观锚点                ─ 解释「为什么是这个偏向」
      IV  多周期偏置矩阵          ─ 偏向落到价格行为
      V   波动与节奏              ─ 今日还有多少肉、什么时段动手
      VI  SMC/ICT 机构地图        ─ 机构在哪埋单、在哪扫单
      VII 策略执行单              ─ 从地图到扳机：入场 / SL / 三段 TP / R:R
      VIII 场景概率树             ─ 不可控时的 if-then 程序
      IX  周期详解（含结构图）    ─ 把 IV 每一行展开成图
      X   风控协议（PRE/IN/POST） ─ 真正决定生死的清单
      99  审计与披露              ─ 编号、数据源、模型版本、免责
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    confluence = compute_confluence(analyses)

    current_price = plan["current_price"] if plan else (
        next((a["current_price"] for a in analyses.values() if a and "error" not in a), 0)
    )

    ladder = build_smc_ladder(analyses, data, current_price, plan, intraday)
    scenarios = build_scenarios(plan, intraday, confluence, ladder, current_price) if plan else []

    topbar_html     = render_topbar(now_str, source)
    hero_html       = render_hero(plan, intraday, confluence, data) if plan else ""
    tldr_html       = render_tldr(plan, confluence, intraday)
    macro_html      = render_macro_section()
    confluence_html = render_confluence_section(confluence)
    vol_html        = render_vol_section(intraday, data)
    smc_html        = render_smc_section(ladder, current_price)
    plans_html      = render_plans_section(plan, intraday, confluence, ladder)
    scenarios_html  = render_scenarios_section(scenarios)
    tf_detail_html  = render_tf_detail_section(analyses, charts, confluence)
    risk_html       = render_risk_section_v2()
    audit_html      = render_audit_footer(now_str, source, plan, confluence)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>XAU/USD · GOLDDESK 机构日内波段 · {now_str}</title>
<style>{CSS}</style>
</head>
<body>
{topbar_html}
{hero_html}
{tldr_html}
{macro_html}
{confluence_html}
{vol_html}
{smc_html}
{plans_html}
{scenarios_html}
{tf_detail_html}
{risk_html}
{audit_html}
</body>
</html>"""
