# -*- coding: utf-8 -*-
"""
XAU/USD 市场深度分析简报 · Snapshot Report (SMC 风格)
====================================================================
独立于现有所有入口，专注 Smart Money Concept 简化版本：

  · 1. 核心叙事 (Executive Summary)         — 一句话主导驱动
  · 2. 多周期结构 (Structural Integrity)    — HTF 导航 / LTF 狙击
  · 3. 流动性与订单流 (Liquidity & Order Flow)
        ─ Order Block (OB)
        ─ Fair Value Gap (FVG / Imbalance)
        ─ Buy-side / Sell-side Liquidity (BSL / SSL) Sweep
  · 4. 战术应对方案 (Action Plan, IF-THEN)
        ─ 看涨情景 / 看跌情景 / ATR 风控

报告输出： reports/snapshot/snapshot_<时间戳>.html  +  snapshot_latest.html
"""

import os
import sys
import webbrowser
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple

import numpy as np
import pandas as pd

import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(__file__))
from gold_analysis import fetch_data, atr, REPORT_DIR
from wave_analysis import detect_zigzag, detect_bos_choch, analyze_market_structure


# ════════════════════════════════════════════════════════════════════
# 数据结构
# ════════════════════════════════════════════════════════════════════

@dataclass
class OrderBlock:
    idx: int
    side: str           # "demand" / "supply"
    high: float
    low: float
    time_str: str
    mitigated: bool = False

@dataclass
class FVG:
    idx: int            # 中间 K 线索引
    side: str           # "bullish" / "bearish"
    top: float
    bottom: float
    time_str: str
    mitigated: bool = False  # 是否已被价格回补

@dataclass
class LiquidityZone:
    side: str           # "BSL" / "SSL"
    price: float
    time_str: str
    swept: bool = False
    swept_time: str = ""


# ════════════════════════════════════════════════════════════════════
# 检测核心：Order Block / FVG / Liquidity
# ════════════════════════════════════════════════════════════════════

def detect_order_blocks(df: pd.DataFrame, lookback: int = 200,
                        displacement_mult: float = 1.5,
                        max_blocks: int = 6) -> List[OrderBlock]:
    """
    Order Block 识别：
      · Bullish OB (Demand)：在一个强势上行位移之前的最后一根空头 K 线
      · Bearish OB (Supply)：在一个强势下行位移之前的最后一根多头 K 线

    位移定义：单根 K 线实体 ≥ displacement_mult × ATR(14)
    Mitigation：随后价格回到 OB 的 high/low 区间内即视为已触碰
    """
    if len(df) < 30:
        return []
    sub = df.tail(lookback).copy()
    sub_atr = atr(sub["High"], sub["Low"], sub["Close"], 14).bfill().fillna(0).values
    o = sub["Open"].values; h = sub["High"].values
    l = sub["Low"].values;  c = sub["Close"].values
    n = len(sub)
    base = len(df) - n

    blocks: List[OrderBlock] = []
    cur_price = c[-1]

    for i in range(2, n - 1):
        body = abs(c[i] - o[i])
        if body < displacement_mult * sub_atr[i]:
            continue
        # Bullish displacement: 该根大阳线，前面找最后一根阴线作为 demand OB
        if c[i] > o[i]:
            for j in range(i - 1, max(i - 6, 0), -1):
                if c[j] < o[j]:  # 阴线
                    ob = OrderBlock(
                        idx=base + j, side="demand",
                        high=float(max(o[j], c[j])),
                        low=float(min(l[j], o[j], c[j])),
                        time_str=sub.index[j].strftime("%m-%d %H:%M"),
                    )
                    # 检查是否已被破坏（之后是否价格跌破 OB low）
                    after_low = sub["Low"].iloc[j + 1:].min()
                    ob.mitigated = bool(after_low < ob.low - 0.5 * sub_atr[i])
                    blocks.append(ob)
                    break
        # Bearish displacement: 大阴线，前面找最后一根阳线作为 supply OB
        elif c[i] < o[i]:
            for j in range(i - 1, max(i - 6, 0), -1):
                if c[j] > o[j]:
                    ob = OrderBlock(
                        idx=base + j, side="supply",
                        high=float(max(h[j], o[j], c[j])),
                        low=float(min(o[j], c[j])),
                        time_str=sub.index[j].strftime("%m-%d %H:%M"),
                    )
                    after_high = sub["High"].iloc[j + 1:].max()
                    ob.mitigated = bool(after_high > ob.high + 0.5 * sub_atr[i])
                    blocks.append(ob)
                    break

    # 去重（同一 K 线只保留一次） + 仅保留未触发或部分有效的，且距离当前价合理范围内
    seen = set()
    unique: List[OrderBlock] = []
    for ob in blocks:
        if ob.idx in seen:
            continue
        seen.add(ob.idx)
        unique.append(ob)

    # 排序：按距当前价远近，取最近的多个
    unique.sort(key=lambda b: abs((b.high + b.low) / 2 - cur_price))
    # 优先未消耗的
    fresh = [b for b in unique if not b.mitigated][:max_blocks]
    if len(fresh) < max_blocks:
        used = [b for b in unique if b.mitigated][: max_blocks - len(fresh)]
        fresh.extend(used)
    # 按时间倒序（最近的在前）
    fresh.sort(key=lambda b: b.idx, reverse=True)
    return fresh


def detect_fvgs(df: pd.DataFrame, lookback: int = 200, min_size_atr_mult: float = 0.3,
                max_count: int = 8) -> List[FVG]:
    """
    Fair Value Gap：经典三 K 线模式
      · Bullish FVG：candle[i-1].high < candle[i+1].low（中间 K 线留下向上缺口）
      · Bearish FVG：candle[i-1].low  > candle[i+1].high
    Mitigation：之后价格回到 FVG 区间内即视为部分回补
    """
    if len(df) < 30:
        return []
    sub = df.tail(lookback).copy()
    sub_atr = atr(sub["High"], sub["Low"], sub["Close"], 14).bfill().fillna(0).values
    h = sub["High"].values; l = sub["Low"].values
    n = len(sub); base = len(df) - n

    fvgs: List[FVG] = []
    for i in range(1, n - 1):
        # Bullish
        if h[i - 1] < l[i + 1]:
            top, bot = float(l[i + 1]), float(h[i - 1])
            if (top - bot) >= min_size_atr_mult * sub_atr[i]:
                fvg = FVG(idx=base + i, side="bullish", top=top, bottom=bot,
                          time_str=sub.index[i].strftime("%m-%d %H:%M"))
                # mitigation: 之后任意 K 线 low 进入区间
                later_low = sub["Low"].iloc[i + 2:].min() if i + 2 < n else top + 1
                fvg.mitigated = bool(later_low <= top)
                fvgs.append(fvg)
        # Bearish
        if l[i - 1] > h[i + 1]:
            top, bot = float(l[i - 1]), float(h[i + 1])
            if (top - bot) >= min_size_atr_mult * sub_atr[i]:
                fvg = FVG(idx=base + i, side="bearish", top=top, bottom=bot,
                          time_str=sub.index[i].strftime("%m-%d %H:%M"))
                later_high = sub["High"].iloc[i + 2:].max() if i + 2 < n else bot - 1
                fvg.mitigated = bool(later_high >= bot)
                fvgs.append(fvg)
    # 优先未回补
    fresh = [f for f in fvgs if not f.mitigated]
    fresh.sort(key=lambda f: f.idx, reverse=True)
    return fresh[:max_count]


def detect_liquidity(df: pd.DataFrame, pivots: List[Tuple],
                     tolerance_atr: float = 0.4, max_zones: int = 6) -> List[LiquidityZone]:
    """
    流动性识别：
      · BSL Pool：相近的 swing high（差距 < tolerance × ATR）→ 上方流动性
      · SSL Pool：相近的 swing low → 下方流动性
      · Sweep：当前 high/low 是否曾突破后又收回（最近 5 根 K 线内）
    """
    if not pivots or len(df) < 30:
        return []
    atr_val = atr(df["High"], df["Low"], df["Close"], 14).iloc[-1]
    if pd.isna(atr_val) or atr_val == 0:
        return []
    tol = tolerance_atr * atr_val

    highs = [p for p in pivots if p[2] == "H"][-8:]
    lows = [p for p in pivots if p[2] == "L"][-8:]

    zones: List[LiquidityZone] = []
    # BSL: 相近高点聚集
    for i in range(len(highs)):
        for j in range(i + 1, len(highs)):
            if abs(highs[i][1] - highs[j][1]) <= tol:
                price = (highs[i][1] + highs[j][1]) / 2
                # 看是否被 sweep
                last5_high = df["High"].iloc[-5:].max()
                last5_close = df["Close"].iloc[-1]
                swept = (last5_high > price + 0.1 * atr_val) and (last5_close < price)
                try:
                    ts = df.index[highs[j][0]].strftime("%m-%d %H:%M")
                except Exception:
                    ts = ""
                zones.append(LiquidityZone(side="BSL", price=float(price),
                                           time_str=ts, swept=swept,
                                           swept_time=df.index[-1].strftime("%m-%d %H:%M") if swept else ""))
                break
    # SSL: 相近低点聚集
    for i in range(len(lows)):
        for j in range(i + 1, len(lows)):
            if abs(lows[i][1] - lows[j][1]) <= tol:
                price = (lows[i][1] + lows[j][1]) / 2
                last5_low = df["Low"].iloc[-5:].min()
                last5_close = df["Close"].iloc[-1]
                swept = (last5_low < price - 0.1 * atr_val) and (last5_close > price)
                try:
                    ts = df.index[lows[j][0]].strftime("%m-%d %H:%M")
                except Exception:
                    ts = ""
                zones.append(LiquidityZone(side="SSL", price=float(price),
                                           time_str=ts, swept=swept,
                                           swept_time=df.index[-1].strftime("%m-%d %H:%M") if swept else ""))
                break

    # 去重（按价格 ± tol）
    cur = float(df["Close"].iloc[-1])
    zones.sort(key=lambda z: abs(z.price - cur))
    return zones[:max_zones]


# ════════════════════════════════════════════════════════════════════
# 单周期 SMC 分析
# ════════════════════════════════════════════════════════════════════

def analyze_smc_tf(df: pd.DataFrame, label: str, atr_mult_zigzag: float = 2.0) -> Dict:
    if df is None or df.empty or len(df) < 50:
        return {"label": label, "error": "数据不足"}
    pivots = detect_zigzag(df, atr_mult=atr_mult_zigzag, min_bars=3)
    structure = analyze_market_structure(pivots)
    bos_events = detect_bos_choch(pivots, float(df["Close"].iloc[-1]), structure)
    obs = detect_order_blocks(df)
    fvgs = detect_fvgs(df)
    liqs = detect_liquidity(df, pivots)
    atr_now = float(atr(df["High"], df["Low"], df["Close"], 14).iloc[-1] or 0)
    return {
        "label": label,
        "current_price": float(df["Close"].iloc[-1]),
        "structure": structure,
        "bos_events": bos_events,
        "order_blocks": obs,
        "fvgs": fvgs,
        "liquidity": liqs,
        "atr": atr_now,
        "df": df,
    }


# ════════════════════════════════════════════════════════════════════
# 战术 Action Plan 生成
# ════════════════════════════════════════════════════════════════════

def build_action_plan(htf: Dict, ltf: Dict) -> Dict:
    """
    根据 HTF (H4/D1) + LTF (M15) 数据生成 IF-THEN 战术。
    """
    if "error" in htf or "error" in ltf:
        return {"executive": "数据不足，无法生成完整战术。", "scenarios": [], "risk": ""}

    cur = ltf["current_price"]
    htf_label = htf.get("label", "大周期")
    ltf_label = ltf.get("label", "小周期")
    htf_trend = htf["structure"]["trend"]
    htf_cls = htf["structure"]["trend_cls"]
    ltf_trend = ltf["structure"]["trend"]
    ltf_cls = ltf["structure"]["trend_cls"]
    atr_htf = htf.get("atr", 0)
    atr_ltf = ltf.get("atr", 0)

    # 多头订单块（价格下方·机构吸筹区）
    demand_obs = sorted(
        [b for b in htf["order_blocks"] + ltf["order_blocks"]
         if b.side == "demand" and b.high < cur and not b.mitigated],
        key=lambda b: cur - b.high)
    supply_obs = sorted(
        [b for b in htf["order_blocks"] + ltf["order_blocks"]
         if b.side == "supply" and b.low > cur and not b.mitigated],
        key=lambda b: b.low - cur)

    # 流动性目标：上方流动池=多头目标 / 下方流动池=空头目标
    bsl_targets = sorted([z for z in htf["liquidity"] if z.side == "BSL" and z.price > cur],
                         key=lambda z: z.price - cur)
    ssl_targets = sorted([z for z in htf["liquidity"] if z.side == "SSL" and z.price < cur],
                         key=lambda z: cur - z.price)

    # 未回补的失衡缺口
    bull_fvgs = [f for f in htf["fvgs"] + ltf["fvgs"] if f.side == "bullish" and not f.mitigated]
    bear_fvgs = [f for f in htf["fvgs"] + ltf["fvgs"] if f.side == "bearish" and not f.mitigated]
    bull_fvgs.sort(key=lambda f: abs((f.top + f.bottom) / 2 - cur))
    bear_fvgs.sort(key=lambda f: abs((f.top + f.bottom) / 2 - cur))

    # ── 多段细致叙述 ────────────────────────────────────────
    paras = []

    # 段一：宏观情绪（技术解读层面，避免预测宏观）
    paras.append(
        "<b>一、宏观情绪与定位。</b>当前金价站位 "
        f"<b>{cur:.2f}</b>，全球宏观背景以美元利率预期与地缘风险溢价的相对强弱为核心驱动。"
        "在缺乏明确催化剂的窗口期，价格倾向于由订单流（机构挂单堆积区）与流动性主导，"
        "本简报的判断完全基于价格行为与流动性结构，剔除一切滞后指标。"
    )

    # 段二：大级别结构
    if htf_cls == "bull":
        big_struct = (f"<b>{htf_label} 周期维持上升结构</b>，连续形成更高高点（HH）与更高低点（HL），"
                       "机构资金的趋势性买入仍未结束。回调即买入仍是主基调。")
    elif htf_cls == "bear":
        big_struct = (f"<b>{htf_label} 周期维持下降结构</b>，连续形成更低高点（LH）与更低低点（LL），"
                       "机构资金的趋势性卖出仍在延续。反弹即卖出仍是主基调。")
    else:
        big_struct = (f"<b>{htf_label} 周期处于结构转换或震荡区间</b>，多空双方未形成单边压制，"
                       "应等待明确的结构突破（BOS）或结构转换（CHoCH）信号再做方向假设。")
    htf_bos_str = ""
    if htf["bos_events"]:
        ev = htf["bos_events"][0]
        htf_bos_str = f"该周期最近触发 <b>{ev['name']}</b>（价位 {ev['price']}），是当前结构判断的关键依据。"
    paras.append("<b>二、大级别结构。</b>" + big_struct + htf_bos_str)

    # 段三：小级别状态
    if ltf_cls == "bull":
        small_struct = (f"<b>{ltf_label} 周期内部多头驱动</b>，短线动能偏向买方。"
                         "建议优先在大级别多头订单块或失衡缺口附近寻找做多触发。")
    elif ltf_cls == "bear":
        small_struct = (f"<b>{ltf_label} 周期内部空头驱动</b>，短线动能偏向卖方。"
                         "建议优先在大级别空头订单块或失衡缺口附近寻找做空触发。")
    else:
        small_struct = (f"<b>{ltf_label} 周期内部多空摆动剧烈</b>，缺乏方向选择。"
                         "建议等待小级别出现明确的内部结构转换后再行动，避免被反复震荡止损。")
    paras.append("<b>三、小级别状态。</b>" + small_struct)

    # 段四：关键订单块阵列
    ob_lines = []
    if demand_obs:
        ob = demand_obs[0]
        dist = (cur - ob.high) / max(atr_ltf, 1e-6)
        ob_lines.append(
            f"下方最近的<b>多头订单块（机构买盘吸筹区）</b>位于 <b>${ob.low:.1f} – ${ob.high:.1f}</b>，"
            f"距离当前价约 <b>{dist:.1f} 倍小级别波动率</b>，是多头反击的首要防线。"
        )
    if supply_obs:
        ob = supply_obs[0]
        dist = (ob.low - cur) / max(atr_ltf, 1e-6)
        ob_lines.append(
            f"上方最近的<b>空头订单块（机构卖盘压制区）</b>位于 <b>${ob.low:.1f} – ${ob.high:.1f}</b>，"
            f"距离当前价约 <b>{dist:.1f} 倍小级别波动率</b>，是空头反击的首要防线。"
        )
    if not ob_lines:
        ob_lines.append("暂未识别到价格附近的有效订单块，价格可能继续在区间内试探。")
    paras.append("<b>四、订单块阵列。</b>" + "".join(ob_lines))

    # 段五：流动性扫损评估
    swept_now = [z for z in htf["liquidity"] + ltf["liquidity"] if z.swept]
    liq_lines = []
    if swept_now:
        z = swept_now[0]
        side_zh = "上方流动性池（前期高点聚集）" if z.side == "BSL" else "下方流动性池（前期低点聚集）"
        rev_dir = "反转向下" if z.side == "BSL" else "反转向上"
        liq_lines.append(
            f"近期已发生 <b>{side_zh}</b> 的扫损动作（价位 <b>{z.price:.1f}</b>），"
            f"机构资金完成了对散户挂单的收割，价格存在 <b>{rev_dir}</b> 的概率。"
        )
    else:
        liq_lines.append("近期未识别到明显的流动性扫损，价格仍在主动寻找下一处可被收割的挂单堆积。")
    if bsl_targets:
        liq_lines.append(
            f"未被触及的上方流动性池仍有 <b>{len(bsl_targets)}</b> 处，最近一处位于 <b>{bsl_targets[0].price:.1f}</b>，"
            "是多头反击时的天然磁吸目标。"
        )
    if ssl_targets:
        liq_lines.append(
            f"未被触及的下方流动性池仍有 <b>{len(ssl_targets)}</b> 处，最近一处位于 <b>{ssl_targets[0].price:.1f}</b>，"
            "是空头扩展时的天然磁吸目标。"
        )
    paras.append("<b>五、流动性扫损评估。</b>" + "".join(liq_lines))

    # 段六：失衡缺口（FVG）磁吸方向
    fvg_lines = []
    if bull_fvgs:
        f = bull_fvgs[0]
        fvg_lines.append(
            f"未回补的<b>看涨失衡缺口</b>位于 <b>${f.bottom:.1f} – ${f.top:.1f}</b>，"
            "价格回踩此区是潜在的多头进场触发点。"
        )
    if bear_fvgs:
        f = bear_fvgs[0]
        fvg_lines.append(
            f"未回补的<b>看跌失衡缺口</b>位于 <b>${f.bottom:.1f} – ${f.top:.1f}</b>，"
            "价格反弹至此区是潜在的空头进场触发点。"
        )
    if not fvg_lines:
        fvg_lines.append("暂无显著未回补失衡缺口，价格短期缺乏强磁吸。")
    paras.append("<b>六、失衡缺口磁吸。</b>" + "".join(fvg_lines))

    # 段七：综合判断与演化路径
    if htf_cls == "bull":
        path = ("主路径：价格回踩多头订单块或失衡缺口企稳后，向上方流动性池发起进攻。"
                "备选路径：若价格直接跌破多头订单块下沿，则结构作废，需重新评估为转空。")
    elif htf_cls == "bear":
        path = ("主路径：价格反弹至空头订单块或失衡缺口受阻后，向下方流动性池继续扩张。"
                "备选路径：若价格直接突破空头订单块上沿，则结构作废，需重新评估为转多。")
    else:
        path = ("主路径：在订单块上下沿之间高抛低吸，等待区间打破方向后顺势跟进。"
                "备选路径：以中线 BOS/CHoCH 信号为准，避免在震荡中过度交易。")
    paras.append("<b>七、综合判断与演化路径。</b>" + path +
                  f" 当前小级别波动率 ATR 约 <b>${atr_ltf:.2f}</b>，"
                  "短线止损建议参考此值的 1.0 ~ 1.5 倍。")

    executive = "<br><br>".join(paras)

    # IF-THEN 情景
    scenarios = []
    # 看涨情景
    if demand_obs:
        ob = demand_obs[0]
        target = bsl_targets[0].price if bsl_targets else cur + 3 * atr_ltf
        sl = ob.low - 0.5 * atr_ltf
        scenarios.append({
            "side": "bull",
            "title": "情景一 · 看涨布局",
            "trigger": f"价格回踩至多头订单块 <b>${ob.low:.1f} – ${ob.high:.1f}</b>，"
                       f"且小周期出现拒绝信号（反转 K 线、下方流动池被扫损后反转、看涨失衡缺口被回补后反转）",
            "entry": f"在订单块上沿 <b>${ob.high:.1f}</b> 附近触发多单",
            "stop": f"硬止损：订单块下沿之外 <b>${sl:.1f}</b>（订单块下沿 − 0.5 倍小周期波动率）",
            "target": f"目标位：上方流动性池 <b>${target:.1f}</b>",
            "rr": _rr_str(ob.high, sl, target),
        })
    # 看跌情景
    if supply_obs:
        ob = supply_obs[0]
        target = ssl_targets[0].price if ssl_targets else cur - 3 * atr_ltf
        sl = ob.high + 0.5 * atr_ltf
        scenarios.append({
            "side": "bear",
            "title": "情景二 · 看跌布局",
            "trigger": f"价格反弹至空头订单块 <b>${ob.low:.1f} – ${ob.high:.1f}</b>，"
                       f"且小周期出现拒绝信号（上方流动池被扫损后失败摆动、看跌失衡缺口被回补后反转）",
            "entry": f"在订单块下沿 <b>${ob.low:.1f}</b> 附近触发空单",
            "stop": f"硬止损：订单块上沿之外 <b>${sl:.1f}</b>（订单块上沿 + 0.5 倍小周期波动率）",
            "target": f"目标位：下方流动性池 <b>${target:.1f}</b>",
            "rr": _rr_str(ob.low, sl, target),
        })

    # 趋势反转情景
    if htf["bos_events"]:
        ev = htf["bos_events"][0]
        scenarios.append({
            "side": "warn",
            "title": "情景三 · 趋势反转预警",
            "trigger": f"大周期已触发 <b>{ev['name']}</b>（价位 {ev['price']}）",
            "entry": "若价格在反转后形成小级别内部结构翻转加上失败摆动，可顺新趋势布局",
            "stop": "止损放在反转关键转折点之外",
            "target": "下一处关键流动性池或反向订单块",
            "rr": "—",
        })

    risk = (f"当前小周期波动率约 <b>${atr_ltf:.2f}</b>，大周期波动率约 <b>${atr_htf:.2f}</b>。"
            "建议每笔风险敞口控制在账户净值的 0.5% 至 1%；"
            "最小盈亏比目标 1 比 2，盈亏比不达标的机会一律放弃；"
            "重要经济数据公布前 30 分钟内禁止开仓，避免被异常波动击穿；"
            "若小周期方向与大周期方向矛盾，应优先以大周期偏好为准，等待小周期同步后再行动。")

    return {
        "executive": executive,
        "scenarios": scenarios,
        "risk": risk,
        "near_demand_ob": demand_obs[0] if demand_obs else None,
        "near_supply_ob": supply_obs[0] if supply_obs else None,
        "bsl_target": bsl_targets[0] if bsl_targets else None,
        "ssl_target": ssl_targets[0] if ssl_targets else None,
    }


def _rr_str(entry: float, sl: float, tp: float) -> str:
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    if risk <= 0:
        return "—"
    return f"R:R ≈ 1:{reward/risk:.2f}"


# ════════════════════════════════════════════════════════════════════
# HTML 渲染（简洁机构风）
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
     font-size:13px;line-height:1.75;max-width:1280px;margin:0 auto;padding:24px}
.brand{font-size:11px;color:var(--gold-dim);letter-spacing:3px;text-transform:uppercase;margin-bottom:6px}
h1{font-size:26px;font-weight:800;letter-spacing:1px;margin-bottom:6px;
   background:linear-gradient(90deg,#fff,#d9b85c);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.subline{color:var(--text-dim);font-size:12.5px;margin-bottom:24px;font-family:var(--mono)}
.subline b{color:var(--gold)}

.exec-summary{padding:20px 24px;background:linear-gradient(135deg,#0a0a14 0%,#101019 100%);
        border:1px solid var(--border-gold);border-radius:10px;margin-bottom:22px;
        position:relative;overflow:hidden}
.exec-summary::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;
        background:linear-gradient(90deg,#1ddfa9,#d9b85c,#ff5e7c)}
.exec-summary .label{font-size:10.5px;color:var(--gold-dim);letter-spacing:2px;text-transform:uppercase;margin-bottom:8px}
.exec-summary .text{font-size:14.5px;color:var(--text);line-height:1.85;font-weight:500}
.exec-summary .text b{color:var(--gold)}

.section{margin-top:28px}
.section-title{font-size:13.5px;font-weight:700;color:var(--gold);
        letter-spacing:1.5px;padding-bottom:8px;margin-bottom:14px;
        border-bottom:1px solid var(--border-gold);text-transform:uppercase}
.section-title small{font-size:11px;color:var(--text-mute);font-weight:400;
        letter-spacing:1px;margin-left:8px}

.tf-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:900px){.tf-grid{grid-template-columns:1fr}}
.tf-card{background:var(--bg1);border:1px solid var(--border);border-radius:8px;padding:16px 18px;border-left:3px solid var(--gold-dim)}
.tf-card.htf{border-left-color:var(--gold)}
.tf-card.ltf{border-left-color:var(--bull)}
.tf-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;
        padding-bottom:8px;border-bottom:1px dashed var(--border)}
.tf-role{font-size:10px;color:var(--text-mute);letter-spacing:2px;text-transform:uppercase}
.tf-name{font-size:18px;font-weight:800;color:var(--gold);letter-spacing:1px}
.tf-state{font-size:12.5px;color:var(--text-dim)}

.kv{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px dashed var(--border);font-size:12.5px}
.kv:last-child{border-bottom:none}
.kv .k{color:var(--text-mute)}
.kv .v{font-family:var(--mono);color:var(--text);font-weight:600}
.kv .v.bull{color:var(--bull)} .kv .v.bear{color:var(--bear)} .kv .v.gold{color:var(--gold)} .kv .v.warn{color:var(--warn)}

.zone-list{display:flex;flex-direction:column;gap:8px;margin-top:8px}
.zone-item{display:flex;justify-content:space-between;align-items:center;
        padding:8px 12px;background:var(--bg2);border:1px solid var(--border);border-radius:6px;
        font-size:12px}
.zone-item.demand{border-left:3px solid var(--bull)}
.zone-item.supply{border-left:3px solid var(--bear)}
.zone-item.bsl{border-left:3px solid var(--warn)}
.zone-item.ssl{border-left:3px solid var(--bull-dim,#00a07a)}
.zone-item .lbl{color:var(--text-dim);font-size:11.5px}
.zone-item .pri{font-family:var(--mono);font-weight:700}
.zone-item .pri.bull{color:var(--bull)} .zone-item .pri.bear{color:var(--bear)} .zone-item .pri.warn{color:var(--warn)}
.zone-item .tag{font-family:var(--mono);font-size:10px;padding:2px 7px;border-radius:3px;
        background:rgba(122,130,144,0.2);color:var(--text-mute);margin-left:8px}
.zone-item .tag.fresh{background:rgba(217,184,92,0.18);color:var(--gold)}
.zone-item .tag.swept{background:rgba(255,176,102,0.18);color:var(--warn)}
.zone-item .tag.mitigated{background:rgba(122,130,144,0.18);color:var(--text-mute)}

.scenario{padding:16px 18px;background:var(--bg1);border:1px solid var(--border);border-radius:8px;
        margin-bottom:12px;border-left:4px solid var(--gold-dim)}
.scenario.bull{border-left-color:var(--bull)}
.scenario.bear{border-left-color:var(--bear)}
.scenario.warn{border-left-color:var(--warn)}
.scenario h4{font-size:14px;font-weight:700;margin-bottom:10px;letter-spacing:0.5px}
.scenario.bull h4{color:var(--bull)} .scenario.bear h4{color:var(--bear)} .scenario.warn h4{color:var(--warn)}
.scenario .row{display:flex;gap:10px;padding:5px 0;font-size:12.5px;line-height:1.7}
.scenario .row .lbl{flex-shrink:0;width:64px;color:var(--text-mute);font-size:11.5px;letter-spacing:0.5px;font-weight:600}
.scenario .row .val{flex:1;color:var(--text-dim)}
.scenario .row .val b{color:var(--gold)}
.scenario .rr{display:inline-block;margin-top:8px;font-family:var(--mono);font-size:11px;
        padding:3px 9px;background:rgba(217,184,92,0.13);color:var(--gold);border-radius:4px;font-weight:700}

.risk-box{padding:16px 20px;background:var(--bg1);border:1px solid var(--border);border-radius:8px;
        border-left:4px solid var(--warn);font-size:12.5px;color:var(--text-dim);line-height:1.85}
.risk-box .rl{font-size:11px;color:var(--warn);font-weight:700;letter-spacing:1.5px;
        text-transform:uppercase;margin-bottom:6px}
.risk-box b{color:var(--warn)}

.footer{margin-top:36px;padding-top:18px;border-top:1px solid var(--border);
        font-size:11px;color:var(--text-mute);text-align:center;line-height:1.8}
"""


def _zone_item(label: str, price: str, klass: str, tag: Optional[Tuple[str, str]] = None) -> str:
    tag_html = f'<span class="tag {tag[0]}">{tag[1]}</span>' if tag else ""
    return f'<div class="zone-item {klass}"><div><span class="lbl">{label}</span>{tag_html}</div><div class="pri {klass.split()[0] if klass else ""}">{price}</div></div>'


def _render_tf_card(role: str, label: str, info: Dict) -> str:
    """role: 'HTF' / 'LTF'"""
    if "error" in info:
        return f"""<div class="tf-card {role.lower()}">
          <div class="tf-head">
            <div><div class="tf-role">{'大周期 · 导航定位' if role == 'HTF' else '小周期 · 狙击触发'}</div>
                 <div class="tf-name">{label}</div></div>
          </div>
          <div style="color:var(--text-mute)">数据不足。</div>
        </div>"""

    structure = info["structure"]
    s_color = {"bull": "bull", "bear": "bear", "neutral": "warn"}.get(structure["trend_cls"], "warn")
    bos_html = ""
    if info["bos_events"]:
        for ev in info["bos_events"][:2]:
            cls = "bull" if ev["cls"] == "bull" else "bear" if ev["cls"] == "bear" else "warn"
            bos_html += f'<div class="kv"><span class="k">{ev["type"]} {ev["name"]}</span><span class="v {cls}">{ev["price"]}</span></div>'
    else:
        bos_html = '<div class="kv"><span class="k">结构突破 / 结构转换</span><span class="v">尚未触发</span></div>'

    # OB list
    ob_items = []
    for ob in info["order_blocks"][:4]:
        klass = "demand" if ob.side == "demand" else "supply"
        zh = "多头订单块（机构买盘吸筹区）" if ob.side == "demand" else "空头订单块（机构卖盘压制区）"
        tag = ("mitigated", "已被触碰") if ob.mitigated else ("fresh", "仍然有效")
        cls_pri = "bull" if ob.side == "demand" else "bear"
        ob_items.append(
            f'<div class="zone-item {klass}">'
            f'<div><span class="lbl">{zh} · {ob.time_str}</span>'
            f'<span class="tag {tag[0]}">{tag[1]}</span></div>'
            f'<div class="pri {cls_pri}">${ob.low:.1f} – ${ob.high:.1f}</div></div>'
        )
    obs_html = "".join(ob_items) or '<div style="color:var(--text-mute);font-size:12px;padding:6px 0">未识别有效订单块</div>'

    # FVG
    fvg_items = []
    for fv in info["fvgs"][:4]:
        klass = "demand" if fv.side == "bullish" else "supply"
        zh = "看涨失衡缺口（多头磁吸区）" if fv.side == "bullish" else "看跌失衡缺口（空头磁吸区）"
        cls_pri = "bull" if fv.side == "bullish" else "bear"
        fvg_items.append(
            f'<div class="zone-item {klass}">'
            f'<div><span class="lbl">{zh} · {fv.time_str}</span></div>'
            f'<div class="pri {cls_pri}">${fv.bottom:.1f} – ${fv.top:.1f}</div></div>'
        )
    fvg_html = "".join(fvg_items) or '<div style="color:var(--text-mute);font-size:12px;padding:6px 0">未识别到未回补的失衡缺口</div>'

    # Liquidity
    liq_items = []
    for z in info["liquidity"][:5]:
        klass = "bsl" if z.side == "BSL" else "ssl"
        zh = "上方流动性池（前期高点聚集）" if z.side == "BSL" else "下方流动性池（前期低点聚集）"
        if z.swept:
            tag = ("swept", "已被扫损")
        else:
            tag = ("fresh", "待被获取")
        cls_pri = "warn" if z.side == "BSL" else "bull"
        liq_items.append(
            f'<div class="zone-item {klass}">'
            f'<div><span class="lbl">{zh}</span><span class="tag {tag[0]}">{tag[1]}</span></div>'
            f'<div class="pri {cls_pri}">${z.price:.1f}</div></div>'
        )
    liq_html = "".join(liq_items) or '<div style="color:var(--text-mute);font-size:12px;padding:6px 0">未识别到明显流动性聚集</div>'

    role_zh = "大周期 · 导航 · 定义趋势" if role == "HTF" else "小周期 · 狙击 · 触发进场"

    return f"""<div class="tf-card {role.lower()}">
      <div class="tf-head">
        <div>
          <div class="tf-role">{role_zh}</div>
          <div class="tf-name">{label}</div>
        </div>
        <div class="tf-state">
          <span class="v {s_color}" style="font-weight:700">{structure["trend"]}</span>
          <small style="color:var(--text-mute);margin-left:6px">波动率约 ${info['atr']:.2f}</small>
        </div>
      </div>
      <div style="font-size:11px;color:var(--text-mute);letter-spacing:1.5px;margin-bottom:6px;font-weight:600">结构状态 · 结构突破与转换</div>
      {bos_html}
      <div style="font-size:11px;color:var(--text-mute);letter-spacing:1.5px;margin:14px 0 6px;font-weight:600">订单块阵列</div>
      <div class="zone-list">{obs_html}</div>
      <div style="font-size:11px;color:var(--text-mute);letter-spacing:1.5px;margin:14px 0 6px;font-weight:600">失衡缺口</div>
      <div class="zone-list">{fvg_html}</div>
      <div style="font-size:11px;color:var(--text-mute);letter-spacing:1.5px;margin:14px 0 6px;font-weight:600">流动性聚集池</div>
      <div class="zone-list">{liq_html}</div>
    </div>"""


def _render_scenarios(plan: Dict) -> str:
    if not plan["scenarios"]:
        return '<div style="color:var(--text-mute);padding:14px">数据不足，未生成战术情景。</div>'
    blocks = []
    for s in plan["scenarios"]:
        rr = f'<div class="rr">{s["rr"]}</div>' if s["rr"] != "—" else ""
        blocks.append(f"""<div class="scenario {s["side"]}">
          <h4>{s["title"]}</h4>
          <div class="row"><div class="lbl">触发</div><div class="val">{s["trigger"]}</div></div>
          <div class="row"><div class="lbl">入场</div><div class="val">{s["entry"]}</div></div>
          <div class="row"><div class="lbl">止损</div><div class="val">{s["stop"]}</div></div>
          <div class="row"><div class="lbl">目标</div><div class="val">{s["target"]}</div></div>
          {rr}
        </div>""")
    return "".join(blocks)


def render_snapshot_html(htf_label: str, htf_info: Dict,
                         ltf_label: str, ltf_info: Dict,
                         plan: Dict, source: str, current_price: float) -> str:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    htf_html = _render_tf_card("HTF", htf_label, htf_info)
    ltf_html = _render_tf_card("LTF", ltf_label, ltf_info)
    scen_html = _render_scenarios(plan)

    body = f"""
    <div class="brand">黄金 · 市场深度分析简报</div>
    <h1>市场深度分析简报</h1>
    <div class="subline">数据源：<b>{source}</b> &nbsp;|&nbsp; 当前价：<b>{current_price:.2f}</b> &nbsp;|&nbsp; 报告时间：<b>{now_str}</b></div>

    <div class="exec-summary">
      <div class="label">第一部分 · 核心叙事</div>
      <div class="text">{plan["executive"]}</div>
    </div>

    <div class="section">
      <div class="section-title">第二部分 · 多周期结构 <small>仅价格行为，剔除一切滞后指标</small></div>
      <div class="tf-grid">
        {htf_html}
        {ltf_html}
      </div>
    </div>

    <div class="section">
      <div class="section-title">第三部分 · 流动性与订单流 <small>核心要素已包含于上方周期卡片中</small></div>
      <div style="font-size:12.5px;color:var(--text-dim);padding:14px 18px;background:var(--bg1);border:1px solid var(--border);border-radius:8px;line-height:1.95">
        <b style="color:var(--gold)">阅读指南：</b><br>
        <b>多头订单块</b>＝机构买盘吸筹区，是多头潜在的入场区；
        <b>空头订单块</b>＝机构卖盘压制区，是空头潜在的入场区；
        <b>失衡缺口</b>＝未回补的价格失衡区间，是价格回归的"磁铁"，常作为反转或顺势加仓的触发点；
        <b>流动性聚集池</b>＝多个相近的前期高点或低点形成的挂单堆积，价格倾向于先扫损止损盘再做方向选择。<br>
        标签 <b style="color:var(--gold)">"仍然有效"</b> 代表订单块尚未被价格触碰，仍具备机构挂单效力；
        <b style="color:var(--warn)">"已被扫损"</b> 代表流动性已被收割，常常预示反转的来临。
      </div>
    </div>

    <div class="section">
      <div class="section-title">第四部分 · 战术应对方案 <small>条件触发式情景分析</small></div>
      {scen_html}
      <div style="margin-top:14px"></div>
      <div class="risk-box">
        <div class="rl">风控提示</div>
        {plan["risk"]}
      </div>
    </div>

    <div class="footer">
      市场深度分析简报 · 基于价格行为与流动性结构 · 涵盖订单块、失衡缺口、流动性池、结构突破与转换<br>
      底层算法：ZigZag 转折点检测 + 14 周期波动率位移识别<br>
      本报告仅供研究学习，不构成投资建议。市场有风险，决策需谨慎。
    </div>
    """

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>XAU/USD · 市场深度分析简报 · {now_str}</title>
<style>{CSS}</style></head><body>{body}</body></html>"""


# ════════════════════════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════════════════════════

def run_snapshot(fetch_fn=None, report_prefix="snapshot", report_subdir="snapshot",
                 system_label="MT4 系统",
                 htf_key="h4", htf_label="H4",
                 ltf_key="m15", ltf_label="M15",
                 open_browser=True):
    if fetch_fn is None:
        fetch_fn = fetch_data
    print(f"[SNAP] 启动 SMC 简报 · {system_label}")
    data, source = fetch_fn()
    if not data:
        print("[SNAP] 错误：无法获取行情数据")
        return None

    htf_df = data.get(htf_key)
    ltf_df = data.get(ltf_key)

    htf_info = analyze_smc_tf(htf_df, htf_label, atr_mult_zigzag=2.0) if htf_df is not None else {"label": htf_label, "error": "数据不足"}
    ltf_info = analyze_smc_tf(ltf_df, ltf_label, atr_mult_zigzag=1.2) if ltf_df is not None else {"label": ltf_label, "error": "数据不足"}

    current_price = ltf_info.get("current_price") or htf_info.get("current_price") or 0.0

    plan = build_action_plan(htf_info, ltf_info)

    if "error" not in htf_info:
        print(f"  [HTF] {htf_label}: {htf_info['structure']['trend']}; OBs={len(htf_info['order_blocks'])}; FVGs={len(htf_info['fvgs'])}; Liquidity={len(htf_info['liquidity'])}")
    if "error" not in ltf_info:
        print(f"  [LTF] {ltf_label}: {ltf_info['structure']['trend']}; OBs={len(ltf_info['order_blocks'])}; FVGs={len(ltf_info['fvgs'])}; Liquidity={len(ltf_info['liquidity'])}")
    print(f"  [PLAN] 情景数: {len(plan['scenarios'])}")

    html = render_snapshot_html(htf_label, htf_info, ltf_label, ltf_info, plan, source, current_price)

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out_dir = os.path.join(REPORT_DIR, report_subdir) if report_subdir else REPORT_DIR
    os.makedirs(out_dir, exist_ok=True)
    report_path = os.path.join(out_dir, f"{report_prefix}_{ts}.html")
    latest_path = os.path.join(out_dir, f"{report_prefix}_latest.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[SNAP] 报告已生成: {report_path}")
    print(f"[SNAP] 最新报告: {latest_path}")
    if open_browser:
        try:
            os.startfile(latest_path)
        except Exception:
            webbrowser.open(f"file:///{latest_path.replace(os.sep, '/')}")
    return latest_path


def main():
    """MT4 系统入口（数据回退链：MT4 CSV → Yahoo）"""
    return run_snapshot(fetch_fn=fetch_data,
                        report_prefix="snapshot",
                        report_subdir="snapshot",
                        system_label="MT4 系统")


if __name__ == "__main__":
    main()
