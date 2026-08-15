"""
XAU/USD 价格行为分析脚本（市场结构 + 趋势通道 + 关键位）
独立报告：ZigZag 结构识别（HH/HL/LH/LL）+ 通道线 + BOS/CHoCH
"""

import os
import sys
import io
import base64
import pandas as pd
import numpy as np
from datetime import datetime
import webbrowser
import warnings
warnings.filterwarnings("ignore")

# Matplotlib (用于生成嵌入式图表)
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

sys.path.insert(0, os.path.dirname(__file__))
from gold_analysis import fetch_data, atr, REPORT_DIR


# ─────────────────────────────────────────────
# ZigZag 转折点检测
# ─────────────────────────────────────────────

def detect_zigzag(df, atr_mult=2.0, min_bars=3):
    """基于 ATR 阈值的 ZigZag。返回 [(idx, price, type)] 高低交替"""
    if len(df) < 30:
        return []
    high = df["High"].values
    low  = df["Low"].values
    close = df["Close"]
    atr_val = atr(df["High"], df["Low"], close, 14).values
    n = len(df)

    pivots = []
    direction = 0
    last_high = high[0]; last_high_idx = 0
    last_low  = low[0];  last_low_idx  = 0

    for i in range(1, n):
        thr = atr_val[i] * atr_mult if not np.isnan(atr_val[i]) else (high[i] - low[i]) * atr_mult
        if thr <= 0:
            thr = (high[i] - low[i]) + 1e-6
        if direction >= 0:
            if high[i] > last_high:
                last_high = high[i]; last_high_idx = i
            if last_high - low[i] >= thr and (i - last_high_idx) >= min_bars:
                pivots.append((last_high_idx, last_high, "H"))
                direction = -1
                last_low = low[i]; last_low_idx = i
        if direction <= 0:
            if low[i] < last_low:
                last_low = low[i]; last_low_idx = i
            if high[i] - last_low >= thr and (i - last_low_idx) >= min_bars:
                pivots.append((last_low_idx, last_low, "L"))
                direction = 1
                last_high = high[i]; last_high_idx = i

    cleaned = []
    for p in pivots:
        if not cleaned or cleaned[-1][2] != p[2]:
            cleaned.append(p)
        else:
            if p[2] == "H" and p[1] > cleaned[-1][1]:
                cleaned[-1] = p
            elif p[2] == "L" and p[1] < cleaned[-1][1]:
                cleaned[-1] = p
    return cleaned


# ─────────────────────────────────────────────
# 市场结构分析（HH/HL/LH/LL）
# ─────────────────────────────────────────────

def analyze_market_structure(pivots):
    """
    给每个 swing 点打上 HH/HL/LH/LL 标签，并判断整体结构方向。
    
    HH = 比上一个 H 更高（Higher High，多头特征）
    LH = 比上一个 H 更低（Lower High，空头特征）
    HL = 比上一个 L 更高（Higher Low，多头特征）
    LL = 比上一个 L 更低（Lower Low，空头特征）
    
    上升结构 = HH + HL；下降结构 = LH + LL；其它 = 震荡
    """
    if len(pivots) < 4:
        return {"labels": [], "trend": "数据不足", "trend_cls": "neutral",
                "bull_count": 0, "bear_count": 0}
    labels = []
    last_h = None
    last_l = None
    for idx, price, t in pivots:
        if t == "H":
            if last_h is None:
                labels.append("H")
            elif price > last_h:
                labels.append("HH")
            else:
                labels.append("LH")
            last_h = price
        else:
            if last_l is None:
                labels.append("L")
            elif price > last_l:
                labels.append("HL")
            else:
                labels.append("LL")
            last_l = price
    # 看最近 6 个标签里多空各几个
    recent = labels[-6:]
    bull = sum(1 for x in recent if x in ("HH", "HL"))
    bear = sum(1 for x in recent if x in ("LH", "LL"))
    if bull >= 4 and bear <= 1:
        trend = "明确上升结构（HH+HL）"
        trend_cls = "bull"
    elif bear >= 4 and bull <= 1:
        trend = "明确下降结构（LH+LL）"
        trend_cls = "bear"
    elif bull > bear:
        trend = "偏多震荡（多头特征居多）"
        trend_cls = "bull"
    elif bear > bull:
        trend = "偏空震荡（空头特征居多）"
        trend_cls = "bear"
    else:
        trend = "区间震荡（结构不明）"
        trend_cls = "neutral"
    return {
        "labels": labels,
        "trend": trend,
        "trend_cls": trend_cls,
        "bull_count": bull,
        "bear_count": bear,
    }


# ─────────────────────────────────────────────
# BOS / CHoCH 检测
# ─────────────────────────────────────────────

def detect_bos_choch(pivots, current_price, structure):
    """
    检测最近的结构突破事件：
      BOS（Break of Structure）= 顺势突破，趋势延续
      CHoCH（Change of Character）= 逆势突破，趋势反转信号
    
    在上升结构中：
      突破上一个 HH 之上 = BOS up（延续）
      跌破上一个 HL 之下 = CHoCH（转折看空）
    """
    if len(pivots) < 4:
        return []
    events = []
    trend_cls = structure["trend_cls"]
    # 取最近的高点低点
    last_high = next((p for p in reversed(pivots) if p[2] == "H"), None)
    last_low  = next((p for p in reversed(pivots) if p[2] == "L"), None)
    # 倒数第二个同向极值
    prior_highs = [p for p in pivots if p[2] == "H"]
    prior_lows  = [p for p in pivots if p[2] == "L"]
    
    if trend_cls == "bull" and len(prior_highs) >= 2:
        prev_h = prior_highs[-2][1]
        if current_price > prev_h:
            events.append({
                "type": "BOS↑",
                "name": "向上突破前高（趋势延续）",
                "price": round(prev_h, 1),
                "cls": "bull",
                "desc": f"价格突破 {prev_h:.1f}（前高），上升结构有效延续，可顺势找回调入多",
            })
    if trend_cls == "bull" and len(prior_lows) >= 1:
        if last_low and current_price < last_low[1]:
            events.append({
                "type": "CHoCH↓",
                "name": "跌破前低（结构转折）",
                "price": round(last_low[1], 1),
                "cls": "bear",
                "desc": f"价格跌破 {last_low[1]:.1f}（最近HL），上升结构破坏，警惕趋势反转",
            })
    if trend_cls == "bear" and len(prior_lows) >= 2:
        prev_l = prior_lows[-2][1]
        if current_price < prev_l:
            events.append({
                "type": "BOS↓",
                "name": "向下突破前低（趋势延续）",
                "price": round(prev_l, 1),
                "cls": "bear",
                "desc": f"价格跌破 {prev_l:.1f}（前低），下降结构有效延续，可顺势找反弹入空",
            })
    if trend_cls == "bear" and len(prior_highs) >= 1:
        if last_high and current_price > last_high[1]:
            events.append({
                "type": "CHoCH↑",
                "name": "突破前高（结构转折）",
                "price": round(last_high[1], 1),
                "cls": "bull",
                "desc": f"价格突破 {last_high[1]:.1f}（最近LH），下降结构破坏，警惕趋势反转",
            })
    return events


# ─────────────────────────────────────────────
# 趋势通道线检测（线性回归拟合）
# ─────────────────────────────────────────────

def detect_channel(df, pivots, lookback_bars=120):
    """
    用最近的 swing 高低点线性回归拟合通道线。
    返回 dict: {upper_line, lower_line, slope, direction, position_pct}
    
    upper_line / lower_line 形如 (slope, intercept)，y = slope*idx + intercept
    """
    if len(pivots) < 4 or len(df) < 30:
        return None

    n = len(df)
    cutoff = max(0, n - lookback_bars)
    recent_pivots = [p for p in pivots if p[0] >= cutoff]
    highs = [(p[0], p[1]) for p in recent_pivots if p[2] == "H"]
    lows  = [(p[0], p[1]) for p in recent_pivots if p[2] == "L"]
    if len(highs) < 2 or len(lows) < 2:
        return None

    def linear_fit(points):
        xs = np.array([p[0] for p in points], dtype=float)
        ys = np.array([p[1] for p in points], dtype=float)
        slope, intercept = np.polyfit(xs, ys, 1)
        return float(slope), float(intercept)

    h_slope, h_intercept = linear_fit(highs)
    l_slope, l_intercept = linear_fit(lows)
    avg_slope = (h_slope + l_slope) / 2

    # 判断通道方向
    last_idx = n - 1
    upper_now = h_slope * last_idx + h_intercept
    lower_now = l_slope * last_idx + l_intercept
    width = upper_now - lower_now
    if width <= 0:
        return None

    current_price = float(df["Close"].iloc[-1])
    position_pct = (current_price - lower_now) / width * 100  # 0=贴底，100=贴顶

    # 通道方向
    avg_abs_slope = abs(avg_slope)
    price_avg = float(df["Close"].iloc[-min(60, n):].mean())
    slope_pct_per_bar = avg_abs_slope / price_avg * 100
    if slope_pct_per_bar < 0.005:   # 每根K线斜率<0.005% → 接近水平
        direction = "水平区间"
        direction_cls = "neutral"
    elif avg_slope > 0:
        direction = "上升通道"
        direction_cls = "bull"
    else:
        direction = "下降通道"
        direction_cls = "bear"

    # 通道平行度（两条线斜率差异）
    if avg_abs_slope > 0:
        parallelism = 1 - abs(h_slope - l_slope) / (2 * avg_abs_slope + 1e-10)
    else:
        parallelism = 1.0
    parallelism = max(0, min(1, parallelism))

    # 突破检测
    breakout = None
    if current_price > upper_now * 1.001:
        breakout = {"side": "up", "level": round(upper_now, 1),
                    "desc": "已突破通道上轨，趋势加速或形成新结构"}
    elif current_price < lower_now * 0.999:
        breakout = {"side": "down", "level": round(lower_now, 1),
                    "desc": "已跌破通道下轨，趋势加速或形成新结构"}

    return {
        "upper": (h_slope, h_intercept),
        "lower": (l_slope, l_intercept),
        "upper_now": round(upper_now, 1),
        "lower_now": round(lower_now, 1),
        "mid_now":   round((upper_now + lower_now) / 2, 1),
        "width":     round(width, 1),
        "direction": direction,
        "direction_cls": direction_cls,
        "position_pct": round(position_pct, 1),
        "parallelism": round(parallelism * 100, 0),
        "breakout":  breakout,
        "highs_count": len(highs),
        "lows_count":  len(lows),
        "highs_used":  highs,
        "lows_used":   lows,
    }


# ─────────────────────────────────────────────
# 单周期分析
# ─────────────────────────────────────────────

def analyze_pa(df, label, atr_mult=2.0, lookback_bars=120):
    """单周期价格行为分析"""
    if df is None or df.empty or len(df) < 50:
        return {"label": label, "error": "数据不足"}

    pivots = detect_zigzag(df, atr_mult=atr_mult, min_bars=3)
    current_price = float(df["Close"].iloc[-1])
    structure = analyze_market_structure(pivots)
    bos_events = detect_bos_choch(pivots, current_price, structure)
    channel = detect_channel(df, pivots, lookback_bars=lookback_bars)

    return {
        "label":         label,
        "pivots":        pivots[-12:],
        "all_pivots":    pivots,
        "pivot_count":   len(pivots),
        "current_price": round(current_price, 2),
        "structure":     structure,
        "bos_events":    bos_events,
        "channel":       channel,
        "atr_mult":      atr_mult,
    }


# ─────────────────────────────────────────────
# HTML 渲染
# ─────────────────────────────────────────────

def _color(cls):
    return {"bull": "#26a69a", "bear": "#ef5350", "neutral": "#9e9e9e"}.get(cls, "#888")


def render_pivots_table(analysis, df_index):
    """渲染最近转折点 + HH/HL/LH/LL 标签"""
    pivots = analysis["pivots"]
    labels = analysis["structure"]["labels"]
    if not pivots:
        return "<p style='color:#555;font-size:13px'>未识别到转折点</p>"
    label_offset = len(analysis["all_pivots"]) - len(pivots)
    rows = []
    for i, (idx, price, t) in enumerate(pivots):
        try:
            time_str = df_index[idx].strftime("%m-%d %H:%M")
        except Exception:
            time_str = f"#{idx}"
        global_i = label_offset + i
        lbl = labels[global_i] if 0 <= global_i < len(labels) else t
        if lbl in ("HH", "HL"):
            lbl_color = "#26a69a"
        elif lbl in ("LH", "LL"):
            lbl_color = "#ef5350"
        else:
            lbl_color = "#9e9e9e"
        type_color = "#ef5350" if t == "H" else "#26a69a"
        rows.append(
            f"<tr><td style='color:#555;font-size:11px'>{i+1}</td>"
            f"<td style='font-size:11px'>{time_str}</td>"
            f"<td style='color:{type_color}'>{'高点' if t=='H' else '低点'}</td>"
            f"<td><span style='background:{lbl_color}22;color:{lbl_color};"
            f"padding:1px 7px;border-radius:3px;font-weight:bold;font-size:11px'>{lbl}</span></td>"
            f"<td style='text-align:right;color:{type_color};font-family:monospace'>{price:.2f}</td></tr>"
        )
    return f"""<table style='width:100%;font-size:12px'>
<thead><tr style='color:#666'>
  <th>#</th><th>时间</th><th>类型</th><th>结构</th><th style='text-align:right'>价格</th>
</tr></thead>
<tbody>{''.join(rows)}</tbody></table>"""


def render_structure_card(structure):
    color = _color(structure["trend_cls"])
    bull = structure["bull_count"]
    bear = structure["bear_count"]
    bar_total = max(bull + bear, 1)
    bull_w = bull / bar_total * 100
    bear_w = bear / bar_total * 100
    return f"""
    <div style='padding:14px;background:#16162e;border-radius:8px;border-left:4px solid {color}'>
      <div style='font-size:12px;color:#888;margin-bottom:4px'>市场结构判断</div>
      <div style='font-size:18px;font-weight:bold;color:{color};margin-bottom:10px'>{structure['trend']}</div>
      <div style='font-size:12px;color:#aaa;margin-bottom:6px'>近 6 个 swing 点结构特征：</div>
      <div style='display:flex;height:18px;border-radius:9px;overflow:hidden;margin-bottom:8px;background:#0a0a14'>
        <div style='background:#26a69a;width:{bull_w}%;display:flex;align-items:center;justify-content:center;color:#000;font-size:11px;font-weight:bold'>{('多头 '+str(bull)) if bull else ''}</div>
        <div style='background:#ef5350;width:{bear_w}%;display:flex;align-items:center;justify-content:center;color:#000;font-size:11px;font-weight:bold'>{('空头 '+str(bear)) if bear else ''}</div>
      </div>
      <div style='font-size:11px;color:#666;line-height:1.6'>
        <span style='color:#26a69a'>HH/HL</span>=多头结构（更高高点+更高低点）&nbsp;|&nbsp;
        <span style='color:#ef5350'>LH/LL</span>=空头结构（更低高点+更低低点）
      </div>
    </div>"""


def render_channel_card(channel, current_price):
    if not channel:
        return """
        <div style='padding:14px;background:#16162e;border-radius:8px;color:#666;font-size:13px'>
          通道数据不足（需要至少各 2 个高点/低点）
        </div>"""
    color = _color(channel["direction_cls"])
    pos = channel["position_pct"]
    if pos < 25:
        zone = "贴近下轨（接近支撑）"
        zone_color = "#26a69a"
    elif pos > 75:
        zone = "贴近上轨（接近阻力）"
        zone_color = "#ef5350"
    elif 40 <= pos <= 60:
        zone = "通道中枢"
        zone_color = "#f0c040"
    else:
        zone = "通道半道"
        zone_color = "#9e9e9e"

    breakout_html = ""
    if channel["breakout"]:
        b = channel["breakout"]
        bc = "#26a69a" if b["side"] == "up" else "#ef5350"
        breakout_html = f"""
        <div style='margin-top:10px;padding:8px 12px;background:{bc}22;border:1px solid {bc};border-radius:6px'>
          <strong style='color:{bc}'>⚠ 通道突破：</strong>
          <span style='color:#fff;font-size:13px'>{b['desc']}（价位 {b['level']}）</span>
        </div>"""

    return f"""
    <div style='padding:14px;background:#16162e;border-radius:8px;border-left:4px solid {color}'>
      <div style='display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px'>
        <div style='font-size:18px;font-weight:bold;color:{color}'>{channel['direction']}</div>
        <div style='font-size:11px;color:#666'>平行度 {channel['parallelism']:.0f}%</div>
      </div>
      <table style='width:100%;font-size:13px'>
        <tr><td style='color:#888'>通道上轨</td><td style='text-align:right;color:#ef5350;font-family:monospace'>{channel['upper_now']:.1f}</td></tr>
        <tr><td style='color:#888'>通道中线</td><td style='text-align:right;color:#f0c040;font-family:monospace'>{channel['mid_now']:.1f}</td></tr>
        <tr><td style='color:#888'>通道下轨</td><td style='text-align:right;color:#26a69a;font-family:monospace'>{channel['lower_now']:.1f}</td></tr>
        <tr><td style='color:#888'>通道宽度</td><td style='text-align:right;color:#aaa;font-family:monospace'>{channel['width']:.1f}</td></tr>
      </table>
      <div style='margin-top:10px'>
        <div style='font-size:11px;color:#666;margin-bottom:4px'>当前价位置（自下到上 0%-100%）：</div>
        <div style='position:relative;height:24px;background:#0a0a14;border-radius:6px;overflow:hidden'>
          <div style='position:absolute;left:{pos}%;top:0;bottom:0;width:3px;background:#fff;box-shadow:0 0 6px #fff'></div>
          <div style='position:absolute;left:0;right:0;top:0;bottom:0;display:flex;align-items:center;justify-content:center;color:{zone_color};font-size:12px;font-weight:bold'>
            {pos:.0f}% · {zone}
          </div>
        </div>
      </div>
      {breakout_html}
      <div style='margin-top:10px;font-size:11px;color:#666'>
        基于 {channel['highs_count']} 个高点 + {channel['lows_count']} 个低点的线性回归拟合
      </div>
    </div>"""


def render_bos_card(events):
    if not events:
        return """
        <div style='padding:12px;background:#16162e;border-radius:8px;color:#888;font-size:13px'>
          当前未触发 BOS / CHoCH 事件
        </div>"""
    cards = []
    for ev in events:
        c = _color(ev["cls"])
        cards.append(f"""
        <div style='padding:12px;background:#16162e;border-radius:8px;border-left:4px solid {c};margin-bottom:8px'>
          <div style='display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px'>
            <div><span style='background:{c};color:#000;padding:2px 8px;border-radius:4px;font-weight:bold;font-size:12px'>{ev['type']}</span> 
              <span style='color:{c};font-size:14px;font-weight:bold;margin-left:6px'>{ev['name']}</span></div>
            <span style='color:#aaa;font-family:monospace;font-size:13px'>{ev['price']}</span>
          </div>
          <div style='font-size:12px;color:#aaa;line-height:1.6'>{ev['desc']}</div>
        </div>""")
    return "".join(cards)


def generate_trading_plan(analyses):
    """
    综合多周期分析，生成可执行的交易计划。
    返回 dict 包含：主判断、当前指令、多空场景应对、关键触发位、失效条件。
    """
    daily = analyses.get("daily")
    h4    = analyses.get("h4")
    h1    = analyses.get("h1")
    m15   = analyses.get("m15")

    if not (h4 and h1):
        return None

    current_price = h1["current_price"]

    # ── 多周期趋势汇总
    tf_trends = {}
    for k in ("daily", "h4", "h1", "m15"):
        a = analyses.get(k)
        if a and "error" not in a:
            tf_trends[k] = a["structure"]["trend_cls"]

    bull_count = sum(1 for v in tf_trends.values() if v == "bull")
    bear_count = sum(1 for v in tf_trends.values() if v == "bear")
    total = len(tf_trends)

    # ── 主判断
    if bull_count >= 3 and bear_count <= 1:
        main_view = "多周期共振看多"
        main_cls = "bull"
        main_desc = f"{bull_count}/{total} 个周期呈多头结构，趋势向上"
    elif bear_count >= 3 and bull_count <= 1:
        main_view = "多周期共振看空"
        main_cls = "bear"
        main_desc = f"{bear_count}/{total} 个周期呈空头结构，趋势向下"
    elif bull_count > bear_count:
        main_view = "偏多但不共振"
        main_cls = "bull"
        main_desc = f"{bull_count} 多 / {bear_count} 空，多头略占优但需谨慎"
    elif bear_count > bull_count:
        main_view = "偏空但不共振"
        main_cls = "bear"
        main_desc = f"{bear_count} 空 / {bull_count} 多，空头略占优但需谨慎"
    else:
        main_view = "多空争夺"
        main_cls = "neutral"
        main_desc = f"{bull_count} 多 / {bear_count} 空，方向不明，观望"

    # ── 关键触发位（用 H4 + H1 通道边界 + 最近 swing 高低点）
    key_levels = {"resistance": [], "support": []}
    for tf_name, a in [("H4", h4), ("H1", h1)]:
        if not a: continue
        ch = a.get("channel")
        if ch:
            if ch["upper_now"] > current_price:
                key_levels["resistance"].append((ch["upper_now"], f"{tf_name}通道上轨"))
            if ch["lower_now"] < current_price:
                key_levels["support"].append((ch["lower_now"], f"{tf_name}通道下轨"))
        # 最近高低点
        for idx, price, t in a.get("all_pivots", [])[-4:]:
            if t == "H" and price > current_price:
                key_levels["resistance"].append((round(price, 1), f"{tf_name}前高"))
            elif t == "L" and price < current_price:
                key_levels["support"].append((round(price, 1), f"{tf_name}前低"))

    # 排序 + 距离去重（同方向相邻位差距 < 0.3% 当前价时合并，保留更近的那个）
    min_gap = current_price * 0.003   # 大约 14 点 @ $4700
    def _dedup_levels(levels, ascending=True):
        sorted_lv = sorted(set(levels), key=lambda x: x[0] if ascending else -x[0])
        result = []
        for lv in sorted_lv:
            if not result or abs(lv[0] - result[-1][0]) >= min_gap:
                result.append(lv)
        return result
    key_res = _dedup_levels(key_levels["resistance"], ascending=True)[:3]
    key_sup = _dedup_levels(key_levels["support"],    ascending=False)[:3]

    # ── 当前指令（综合判断）
    h1_struct = h1["structure"]["trend_cls"]
    m15_struct = m15["structure"]["trend_cls"] if m15 else "neutral"
    h1_ch = h1.get("channel")
    h1_pos = h1_ch["position_pct"] if h1_ch else 50
    m15_ch = m15.get("channel") if m15 else None
    m15_pos = m15_ch["position_pct"] if m15_ch else 50

    # 收集所有 BOS/CHoCH 事件
    all_events = []
    for tf_name, a in [("日线", daily), ("H4", h4), ("H1", h1), ("M15", m15)]:
        if not a or "error" in a: continue
        for ev in a.get("bos_events", []):
            all_events.append((tf_name, ev))

    has_choch_bull = any("CHoCH↑" in ev["type"] for _, ev in all_events)
    has_choch_bear = any("CHoCH↓" in ev["type"] for _, ev in all_events)
    has_bos_bull   = any("BOS↑" in ev["type"]   for _, ev in all_events)
    has_bos_bear   = any("BOS↓" in ev["type"]   for _, ev in all_events)

    # 决策矩阵
    if has_choch_bull and main_cls == "bear":
        action = "⚠ 立即减仓空单"
        action_cls = "warn"
        action_desc = "下跌结构中出现 CHoCH↑（突破前高），警惕反转，减空单或止盈"
    elif has_choch_bear and main_cls == "bull":
        action = "⚠ 立即减仓多单"
        action_cls = "warn"
        action_desc = "上升结构中出现 CHoCH↓（跌破前低），警惕反转，减多单或止盈"
    elif main_cls == "bull" and h1_struct == "bull" and h1_pos < 35:
        action = "✓ 顺势做多（高胜率）"
        action_cls = "bull"
        action_desc = f"多周期共振 + H1贴近通道下轨（{h1_pos:.0f}%），低吸做多"
    elif main_cls == "bear" and h1_struct == "bear" and h1_pos > 65:
        action = "✓ 顺势做空（高胜率）"
        action_cls = "bear"
        action_desc = f"多周期共振 + H1贴近通道上轨（{h1_pos:.0f}%），高位做空"
    elif main_cls == "bull" and (m15_struct == "bull" or has_bos_bull):
        action = "✓ M15 顺势做多"
        action_cls = "bull"
        action_desc = "大趋势看多，M15 出现多头结构/BOS↑，可日内波段做多"
    elif main_cls == "bear" and (m15_struct == "bear" or has_bos_bear):
        action = "✓ M15 顺势做空"
        action_cls = "bear"
        action_desc = "大趋势看空，M15 出现空头结构/BOS↓，可日内波段做空"
    elif main_cls == "neutral":
        action = "○ 观望等待"
        action_cls = "neutral"
        action_desc = "多空争夺，等待方向明确（H4/H1 出现 BOS 或通道突破）"
    else:
        action = "○ 等待回调"
        action_cls = "neutral"
        action_desc = f"主趋势{main_view}但当前不在最优入场区，等价格到关键位再行动"

    # ── 场景应对剧本
    scenarios = []
    if key_res:
        r1_price, r1_tag = key_res[0]
        scenarios.append({
            "trigger": f"价格上破 {r1_price:.1f}（{r1_tag}）",
            "if_main_bull": f"BOS↑ 顺势加仓多单，目标看到 {key_res[1][0]:.1f}（{key_res[1][1]}）" if len(key_res) > 1 else "BOS↑ 顺势持有多单",
            "if_main_bear": f"突破阻力 = 空头被破坏，立即止损现有空单，等价格回踩 {r1_price:.1f} 后做多",
            "if_neutral":   "突破=方向选择，可顺势做多但仓位减半，止损放在前低下方",
        })
    if key_sup:
        s1_price, s1_tag = key_sup[0]
        scenarios.append({
            "trigger": f"价格下破 {s1_price:.1f}（{s1_tag}）",
            "if_main_bull": f"破支撑 = 多头被破坏，立即止损多单，等反弹至 {s1_price:.1f} 做空",
            "if_main_bear": f"BOS↓ 顺势加仓空单，目标看到 {key_sup[1][0]:.1f}（{key_sup[1][1]}）" if len(key_sup) > 1 else "BOS↓ 顺势持有空单",
            "if_neutral":   "破位=方向选择，可顺势做空但仓位减半，止损放在前高上方",
        })

    # 通道场景
    if h1_ch:
        scenarios.append({
            "trigger": f"价格回到 H1 通道中线（{h1_ch['mid_now']:.1f}）",
            "if_main_bull": "通道内做多机会，等回踩中线企稳后入场",
            "if_main_bear": "反弹至通道中线，是新一轮做空机会",
            "if_neutral":   "中线附近震荡，等待方向选择",
        })

    # 失效条件
    invalidations = []
    if main_cls == "bull" and key_sup:
        invalidations.append(f"H1 收盘跌破 {key_sup[-1][0]:.1f}（最远支撑）→ 多头判断完全失效")
    if main_cls == "bear" and key_res:
        invalidations.append(f"H1 收盘突破 {key_res[-1][0]:.1f}（最远阻力）→ 空头判断完全失效")
    if has_choch_bull or has_choch_bear:
        invalidations.append("已出现 CHoCH 事件 → 当前结构岌岌可危，触发反向 BOS 即翻仓")

    return {
        "main_view":     main_view,
        "main_cls":      main_cls,
        "main_desc":     main_desc,
        "tf_trends":     tf_trends,
        "current_price": current_price,
        "action":        action,
        "action_cls":    action_cls,
        "action_desc":   action_desc,
        "key_resistance": key_res,
        "key_support":    key_sup,
        "events":        all_events,
        "scenarios":     scenarios,
        "invalidations": invalidations,
    }


def render_trading_plan(plan):
    if not plan:
        return ""
    main_color = _color(plan["main_cls"])
    action_color = {"bull": "#26a69a", "bear": "#ef5350",
                    "neutral": "#9e9e9e", "warn": "#ff9800"}.get(plan["action_cls"], "#888")

    # 多周期趋势条
    tf_label_map = {"daily": "日线", "h4": "H4", "h1": "H1", "m15": "M15"}
    tf_html = ""
    for k in ("daily", "h4", "h1", "m15"):
        if k not in plan["tf_trends"]: continue
        cls = plan["tf_trends"][k]
        c = _color(cls)
        ico = "▲" if cls == "bull" else "▼" if cls == "bear" else "■"
        tf_html += (f"<div style='display:inline-block;padding:6px 14px;background:{c}22;"
                    f"border:1px solid {c};border-radius:6px;margin:4px;font-size:13px'>"
                    f"<span style='color:#888;font-size:11px'>{tf_label_map[k]}</span> "
                    f"<span style='color:{c};font-weight:bold;margin-left:6px'>{ico}</span></div>")

    # 关键位条
    res_html = ""
    for price, tag in plan["key_resistance"]:
        diff = price - plan["current_price"]
        res_html += (f"<tr><td style='color:#888;font-size:11px'>{tag}</td>"
                     f"<td style='text-align:right;color:#ef5350;font-family:monospace'>{price:.1f}</td>"
                     f"<td style='text-align:right;color:#666;font-size:11px'>+{diff:.1f}</td></tr>")
    sup_html = ""
    for price, tag in plan["key_support"]:
        diff = plan["current_price"] - price
        sup_html += (f"<tr><td style='color:#888;font-size:11px'>{tag}</td>"
                     f"<td style='text-align:right;color:#26a69a;font-family:monospace'>{price:.1f}</td>"
                     f"<td style='text-align:right;color:#666;font-size:11px'>-{diff:.1f}</td></tr>")

    # 事件
    events_html = ""
    if plan["events"]:
        for tf_name, ev in plan["events"][:5]:
            c = _color(ev["cls"])
            events_html += (f"<div style='padding:6px 10px;background:{c}22;border-left:3px solid {c};"
                            f"border-radius:4px;margin:4px 0;font-size:12px'>"
                            f"<strong style='color:{c}'>[{tf_name}] {ev['type']}</strong> "
                            f"<span style='color:#aaa'>{ev['name']} @ {ev['price']}</span></div>")
    else:
        events_html = "<div style='color:#666;font-size:12px;padding:6px'>暂无 BOS / CHoCH 触发</div>"

    # 场景剧本
    scenarios_html = ""
    for sc in plan["scenarios"]:
        scenarios_html += f"""
        <div style='background:#0e0e1e;padding:10px 14px;border-radius:6px;margin-bottom:10px;border:1px solid #2a2a4a'>
          <div style='font-size:13px;color:#f0c040;font-weight:bold;margin-bottom:8px'>⚡ 触发：{sc['trigger']}</div>
          <table style='font-size:12px;width:100%'>
            <tr><td style='color:#26a69a;width:90px'>主判断看多</td><td style='color:#ddd'>{sc['if_main_bull']}</td></tr>
            <tr><td style='color:#ef5350'>主判断看空</td><td style='color:#ddd'>{sc['if_main_bear']}</td></tr>
            <tr><td style='color:#9e9e9e'>主判断中性</td><td style='color:#ddd'>{sc['if_neutral']}</td></tr>
          </table>
        </div>"""

    # 失效
    inv_html = ""
    for inv in plan["invalidations"]:
        inv_html += f"<li style='color:#ff9800;margin-bottom:4px'>{inv}</li>"
    if not inv_html:
        inv_html = "<li style='color:#666'>暂无明确失效条件</li>"

    return f"""
    <div class='card'>
      <h3>📋 综合交易计划</h3>

      <!-- 多周期趋势条 -->
      <div style='margin-bottom:16px'>
        <div class='sub-h'>多周期趋势</div>
        <div>{tf_html}</div>
      </div>

      <!-- 关键位 + 事件 -->
      <div style='display:grid;grid-template-columns:1fr 1fr 1.2fr;gap:14px;margin-bottom:16px'>
        <div>
          <div class='sub-h'><span class='bear'>↑</span> 关键阻力位</div>
          <table>{res_html if res_html else '<tr><td class="mute">无</td></tr>'}</table>
        </div>
        <div>
          <div class='sub-h'><span class='bull'>↓</span> 关键支撑位</div>
          <table>{sup_html if sup_html else '<tr><td class="mute">无</td></tr>'}</table>
        </div>
        <div>
          <div class='sub-h'>⚡ 已触发事件</div>
          {events_html}
        </div>
      </div>

      <!-- 场景应对 -->
      <div style='margin-bottom:14px'>
        <div class='sub-h gold'>🎯 场景应对剧本（if-then 决策树）</div>
        {scenarios_html}
      </div>

      <!-- 失效条件 -->
      <div style='padding:10px 14px;background:rgba(255,152,0,0.06);border-radius:6px;border-left:3px solid var(--warn)'>
        <div class='sub-h warn' style='margin-bottom:6px'>⚠ 主判断失效条件</div>
        <ul style='margin:0;padding-left:20px;font-size:12px;line-height:1.7'>{inv_html}</ul>
      </div>
    </div>"""


# ─────────────────────────────────────────────
# 图表渲染（嵌入式 base64 PNG）
# ─────────────────────────────────────────────

def render_chart_b64(df, analysis, label, last_n=100):
    """
    渲染带 ZigZag + 通道 + 关键位标注的 K 线图，返回 base64 PNG。
    """
    if not HAS_MPL or df is None or len(df) < 30:
        return None

    df_plot = df.tail(last_n).reset_index()
    n = len(df_plot)
    base_idx = len(df) - last_n

    fig, ax = plt.subplots(figsize=(13, 5.5), facecolor="#0a0a14")
    ax.set_facecolor("#0e0e1e")

    # K 线绘制
    for i, row in df_plot.iterrows():
        color = "#26a69a" if row["Close"] >= row["Open"] else "#ef5350"
        ax.plot([i, i], [row["Low"], row["High"]], color=color, linewidth=0.7, alpha=0.85)
        body_low = min(row["Open"], row["Close"])
        body_high = max(row["Open"], row["Close"])
        height = max(body_high - body_low, (row["High"] - row["Low"]) * 0.001)
        ax.add_patch(plt.Rectangle((i - 0.35, body_low), 0.7, height,
                                   facecolor=color, edgecolor=color, alpha=0.95))

    # ZigZag 折线 + HH/HL/LH/LL 标签
    pivots = analysis.get("all_pivots", [])
    labels = analysis.get("structure", {}).get("labels", [])
    visible_pivots = [(i, (p[0] - base_idx, p[1], p[2])) for i, p in enumerate(pivots) if p[0] >= base_idx]
    if visible_pivots:
        xs = [vp[1][0] for vp in visible_pivots]
        ys = [vp[1][1] for vp in visible_pivots]
        ax.plot(xs, ys, "-", color="#5a8aff", linewidth=1.3, alpha=0.85)
        for global_i, (px, py, pt) in visible_pivots:
            lbl = labels[global_i] if global_i < len(labels) else pt
            lbl_color = "#26a69a" if lbl in ("HH", "HL") else "#ef5350" if lbl in ("LH", "LL") else "#aaa"
            offset_y = (df_plot["High"].max() - df_plot["Low"].min()) * 0.02
            text_y = py + offset_y if pt == "H" else py - offset_y
            va = "bottom" if pt == "H" else "top"
            ax.text(px, text_y, lbl, color=lbl_color, fontsize=8, ha="center", va=va,
                    fontweight="bold", bbox=dict(boxstyle="round,pad=0.2", facecolor="#0a0a14",
                                                  edgecolor=lbl_color, linewidth=0.5, alpha=0.8))
            ax.scatter(px, py, s=25, color=lbl_color, zorder=5,
                       edgecolors="#fff", linewidths=0.5)

    # 通道线
    ch = analysis.get("channel")
    if ch:
        h_slope, h_intercept = ch["upper"]
        l_slope, l_intercept = ch["lower"]
        x_g_start = base_idx
        x_g_end = base_idx + n - 1
        # 延长 20% 到右侧
        x_g_extend = x_g_end + int(n * 0.2)
        x_local_start = 0
        x_local_end_ext = n - 1 + int(n * 0.2)
        upper_y = [h_slope * x_g_start + h_intercept, h_slope * x_g_extend + h_intercept]
        lower_y = [l_slope * x_g_start + l_intercept, l_slope * x_g_extend + l_intercept]
        ax.plot([x_local_start, x_local_end_ext], upper_y,
                "--", color="#ef5350", linewidth=1.2, alpha=0.7, label=f"通道上轨")
        ax.plot([x_local_start, x_local_end_ext], lower_y,
                "--", color="#26a69a", linewidth=1.2, alpha=0.7, label=f"通道下轨")
        # 通道中线
        mid_y = [(u + l) / 2 for u, l in zip(upper_y, lower_y)]
        ax.plot([x_local_start, x_local_end_ext], mid_y,
                ":", color="#f0c040", linewidth=0.8, alpha=0.5, label="通道中线")

    # 当前价水平线
    current_price = float(df_plot["Close"].iloc[-1])
    ax.axhline(y=current_price, color="#fff", linestyle="-", linewidth=0.5, alpha=0.4)
    ax.text(n + 0.5, current_price, f" ${current_price:.1f}", color="#fff",
            fontsize=9, va="center", fontweight="bold")

    # BOS/CHoCH 事件标记
    for ev in analysis.get("bos_events", []):
        ev_color = "#26a69a" if ev["cls"] == "bull" else "#ef5350"
        ax.axhline(y=ev["price"], color=ev_color, linestyle=":", linewidth=1, alpha=0.6)
        ax.text(n - 1, ev["price"], f" {ev['type']} {ev['price']}", color=ev_color,
                fontsize=8, va="center", ha="right",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#0a0a14",
                          edgecolor=ev_color, alpha=0.8))

    # X 轴时间标签
    if "Date" in df_plot.columns or df_plot.columns[0] == "index":
        time_col = df_plot.columns[0]
        try:
            tick_positions = list(range(0, n, max(1, n // 8)))
            tick_labels = [df_plot[time_col].iloc[i].strftime("%m-%d %H:%M") for i in tick_positions]
            ax.set_xticks(tick_positions)
            ax.set_xticklabels(tick_labels, rotation=0, fontsize=8, color="#888")
        except Exception:
            ax.set_xticks([])

    # 样式
    ax.set_xlim(-1, n + int(n * 0.2))
    y_pad = (df_plot["High"].max() - df_plot["Low"].min()) * 0.05
    ax.set_ylim(df_plot["Low"].min() - y_pad, df_plot["High"].max() + y_pad)
    ax.tick_params(colors="#888", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#2a2a4a")
    ax.grid(True, color="#1a1a2e", linewidth=0.4, alpha=0.5)
    ax.set_title(f"{label}  |  {analysis['structure']['trend']}  |  通道：{ch['direction'] if ch else 'N/A'}",
                 color="#f0c040", fontsize=12, pad=10, loc="left")
    if ch:
        ax.legend(loc="upper left", fontsize=8, framealpha=0.7,
                  facecolor="#0a0a14", edgecolor="#2a2a4a", labelcolor="#aaa")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=110, facecolor="#0a0a14", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


# ─────────────────────────────────────────────
# 丰富叙述分析（带具体路径指引）
# ─────────────────────────────────────────────

def _round_to_step(value, step=10):
    """向上/向下取整到指定步长"""
    return round(value / step) * step


def generate_narrative(plan, analyses):
    """
    生成大段散文式行情分析，包括：
      - 当前市场状态描述
      - 核心阻力 / 关键支撑
      - 上行剧本（具体目标位 + 极限目标）
      - 下行剧本（具体支撑 + 深度支撑）
      - 日内操作思路（分水岭+分级应对）
    """
    if not plan:
        return None

    daily = analyses.get("daily")
    h4    = analyses.get("h4")
    h1    = analyses.get("h1")
    m15   = analyses.get("m15")
    price = plan["current_price"]

    # ── 大趋势描述
    daily_struct = daily["structure"]["trend"] if daily and "error" not in daily else "数据不足"
    h4_struct = h4["structure"]["trend"] if h4 and "error" not in h4 else "数据不足"
    h1_struct = h1["structure"]["trend"] if h1 and "error" not in h1 else "数据不足"
    h4_ch = h4.get("channel") if h4 else None
    h1_ch = h1.get("channel") if h1 else None

    main_cls = plan["main_cls"]
    main_view = plan["main_view"]

    # ── 核心阻力 / 关键支撑
    key_res = plan["key_resistance"]
    key_sup = plan["key_support"]
    R1 = key_res[0] if len(key_res) >= 1 else None    # (price, tag)
    R2 = key_res[1] if len(key_res) >= 2 else None
    R3 = key_res[2] if len(key_res) >= 3 else None
    S1 = key_sup[0] if len(key_sup) >= 1 else None
    S2 = key_sup[1] if len(key_sup) >= 2 else None
    S3 = key_sup[2] if len(key_sup) >= 3 else None

    # 计算更远的目标位（基于日线最近极值，但限制距离合理范围内）
    # 极限距离上限：当前价的 4%（黄金 $4700 → 约 188 点），避免取到几年前的离谱 pivot
    max_dist = price * 0.04
    def daily_extreme(direction):
        """从日线 pivots 找合理范围内的最远极值"""
        if not daily or "error" in daily: return None
        pivots = daily.get("all_pivots", [])
        if direction == "up":
            extremes = [p[1] for p in pivots
                        if p[2] == "H" and p[1] > price and (p[1] - price) <= max_dist]
            return max(extremes) if extremes else None
        else:
            extremes = [p[1] for p in pivots
                        if p[2] == "L" and p[1] < price and (price - p[1]) <= max_dist]
            return min(extremes) if extremes else None

    daily_high = daily_extreme("up")
    daily_low  = daily_extreme("down")

    # 上行目标阶梯（必须递增且间隔合理）
    upside_t1 = round(R1[0], 1) if R1 else round(price + 25, 1)
    upside_t2 = round(R2[0], 1) if R2 and R2[0] > upside_t1 + 5 else round(upside_t1 + max(20, price * 0.005), 1)
    # 极限：用 daily_high，但必须大于 t2 + 一定间距；否则用 t2 + ATR×3 估算
    if daily_high and daily_high > upside_t2 + 10:
        upside_extreme = round(daily_high, 1)
    else:
        upside_extreme = round(upside_t2 + max(30, price * 0.008), 1)
    # 整数关：在极限之上的下一个 50 整数关
    next_round_up = _round_to_step(upside_extreme + 25, 50)

    # 下行目标阶梯
    downside_t1 = round(S1[0], 1) if S1 else round(price - 25, 1)
    downside_t2 = round(S2[0], 1) if S2 and S2[0] < downside_t1 - 5 else round(downside_t1 - max(20, price * 0.005), 1)
    if daily_low and daily_low < downside_t2 - 10:
        downside_extreme = round(daily_low, 1)
    else:
        downside_extreme = round(downside_t2 - max(30, price * 0.008), 1)
    next_round_down = _round_to_step(downside_extreme - 25, 50)

    # ── 第一段：市场状态总结
    if main_cls == "bull":
        market_summary = (f"金价当前位于 <b style='color:#f0c040'>${price:.2f}</b>，{main_view}格局，"
                          f"日线呈 <b>{daily_struct}</b>，H4 {h4_struct}，H1 {h1_struct}。"
                          f"多周期共同指向偏多，趋势性结构正在加强中。")
        overall_thinking = "在未跌破关键支撑前，整体采取 <b style='color:#26a69a'>低多为主、高空为辅</b> 的思路，重点把握回调买入机会。"
    elif main_cls == "bear":
        market_summary = (f"金价当前位于 <b style='color:#f0c040'>${price:.2f}</b>，{main_view}格局，"
                          f"日线呈 <b>{daily_struct}</b>，H4 {h4_struct}，H1 {h1_struct}。"
                          f"多周期共同指向偏空，下行结构主导市场。")
        overall_thinking = "在未突破关键阻力前，整体采取 <b style='color:#ef5350'>高空为主、低多为辅</b> 的思路，重点把握反弹做空机会。"
    else:
        market_summary = (f"金价当前位于 <b style='color:#f0c040'>${price:.2f}</b>，{main_view}格局，"
                          f"日线呈 <b>{daily_struct}</b>，H4 {h4_struct}，H1 {h1_struct}。"
                          f"多空双方处于争夺状态，趋势性行情暂时缺失。")
        overall_thinking = "区间未有效破位前，整体采取 <b style='color:#f0c040'>高空低多震荡</b> 思路，等待方向选择后再确立单边方向。"

    # ── 上行剧本
    upside_story = ""
    if R1:
        upside_story = (
            f"若强势上破 <b style='color:#ef5350'>${upside_t1:.1f}</b>（{R1[1]}），后续上行目标先看 "
            f"<b style='color:#ef5350'>${upside_t2:.1f}</b>"
            f"{'（' + R2[1] + '）' if R2 else ''}"
            f"，极限可看向 <b style='color:#ef5350'>${upside_extreme:.1f}</b> 一线。"
            f"该位置突破大概率需要重磅消息面催化，"
            f"再上一阶可关注 <b>${next_round_up:.0f}</b> 整数关口。"
        )
    else:
        upside_story = "上方无明确阻力数据，等价格回测后形成新结构再做判断。"

    # ── 下行剧本
    downside_story = ""
    if S1:
        downside_story = (
            f"若意外下行破位 <b style='color:#26a69a'>${downside_t1:.1f}</b>（{S1[1]}），下方先看 "
            f"<b style='color:#26a69a'>${downside_t2:.1f}</b>"
            f"{'（' + S2[1] + '）' if S2 else ''}"
            f"，深度支撑落在 <b style='color:#26a69a'>${downside_extreme:.1f}</b> 附近，"
            f"低位触及可考虑分批布多。"
            f"再下一阶须警惕跌至 <b>${next_round_down:.0f}</b> 整数关口。"
        )
    else:
        downside_story = "下方无明确支撑数据，等价格回测后形成新结构再做判断。"

    # ── 日内分水岭操作
    if R1 and S1:
        watershed = round((R1[0] + S1[0]) / 2, 1)
        # 多空关键位 = 离当前价最近的强位
        if abs(R1[0] - price) < abs(S1[0] - price):
            watershed = round(R1[0], 1)
            ws_above = True
        else:
            watershed = round(S1[0], 1)
            ws_above = False
    else:
        watershed = round(price, 1)
        ws_above = False

    intraday_plan = []
    if ws_above:
        # 关键位在上方
        intraday_plan.append(
            f"紧盯 <b style='color:#f0c040'>${watershed:.1f}</b> 多空分水岭："
        )
        intraday_plan.append(
            f"① <b>压制 {watershed:.1f} 不破</b>：行情反弹至 ${watershed:.1f} 区间承压，"
            f"反弹乏力即可顺势 <b style='color:#ef5350'>空单介入</b>，下方目标看 ${downside_t1:.1f}；"
        )
        intraday_plan.append(
            f"② <b>有效突破 {watershed:.1f}</b>（H1 收盘站稳上方），多头结构延伸，"
            f"可考虑 <b style='color:#26a69a'>多单介入</b>，上方目标看 ${upside_t2:.1f}；"
        )
        intraday_plan.append(
            f"③ <b>若进一步上破 {upside_t2:.1f}</b>，行情上涨延伸至 "
            f"${upside_extreme:.1f}、${next_round_up:.0f} 附近，高位可分批止盈。"
        )
    else:
        intraday_plan.append(
            f"紧盯 <b style='color:#f0c040'>${watershed:.1f}</b> 多空分水岭："
        )
        intraday_plan.append(
            f"① <b>守住 {watershed:.1f} 不破</b>：行情回踩 ${watershed:.1f} 企稳，"
            f"可顺势 <b style='color:#26a69a'>多单介入</b>，上方目标看 ${upside_t1:.1f}-{upside_t2:.1f} 区间；"
        )
        # 防止与 watershed 重位：若 downside_t1 等于 watershed，则阶梯整体下移一级
        if abs(downside_t1 - watershed) < 0.5:
            d_next, d_deep = downside_t2, downside_extreme
        else:
            d_next, d_deep = downside_t1, downside_t2
        intraday_plan.append(
            f"② <b>有效跌破 {watershed:.1f}</b>（H1 收盘破位），下行先看 ${d_next:.1f} 支撑，"
            f"止跌企稳可博反弹做多；"
        )
        intraday_plan.append(
            f"③ <b>若进一步击穿 {d_next:.1f}</b>，行情下探延伸至 "
            f"${d_deep:.1f}、${downside_extreme:.1f} 附近，低位支撑区域分批接多。"
        )

    # ── M15 日内提示
    m15_tip = ""
    if m15 and "error" not in m15:
        m15_view = m15["structure"]["trend"]
        m15_chan = m15.get("channel")
        if m15_chan:
            m15_pos = m15_chan["position_pct"]
            if m15_pos < 30:
                pos_desc = "贴近通道下轨（短线超卖）"
            elif m15_pos > 70:
                pos_desc = "贴近通道上轨（短线超买）"
            else:
                pos_desc = "通道中段"
            m15_tip = (f"M15 周期：{m15_view}；价格处于 {pos_desc}（{m15_pos:.0f}%），"
                       f"通道方向 <b>{m15_chan['direction']}</b>。")
        else:
            m15_tip = f"M15 周期：{m15_view}（通道数据不足）。"

    return {
        "market_summary":   market_summary,
        "core_resistance":  R1,
        "core_support":     S1,
        "overall_thinking": overall_thinking,
        "upside_story":     upside_story,
        "downside_story":   downside_story,
        "watershed":        watershed,
        "intraday_plan":    intraday_plan,
        "m15_tip":          m15_tip,
        "upside_targets":   {"t1": upside_t1, "t2": upside_t2, "extreme": upside_extreme, "round": next_round_up},
        "downside_targets": {"t1": downside_t1, "t2": downside_t2, "extreme": downside_extreme, "round": next_round_down},
    }


def render_narrative_card(narrative):
    if not narrative:
        return ""
    R = narrative["core_resistance"]
    S = narrative["core_support"]
    R_text = f"<b style='color:#ef5350'>${R[0]:.1f}</b> 一线（{R[1]}）" if R else "暂无明确阻力"
    S_text = f"<b style='color:#26a69a'>${S[0]:.1f}</b> 一线（{S[1]}）" if S else "暂无明确支撑"
    intraday_html = "<br>".join(narrative["intraday_plan"])

    ut = narrative["upside_targets"]
    dt = narrative["downside_targets"]

    return f"""
    <div class='card' style='background:linear-gradient(135deg,#0e0e1e 0%,#16162e 100%);border:1px solid #3a3a5a'>
      <h3>📖 行情综合解读</h3>
      <div style='font-size:14px;line-height:1.95;color:#ddd'>
        <div style='margin-bottom:14px'>{narrative['market_summary']}</div>

        <div style='display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px'>
          <div style='padding:10px 14px;background:#1a0a0a;border-radius:6px;border-left:3px solid #ef5350'>
            <div style='font-size:11px;color:#888;margin-bottom:4px'>核心阻力</div>
            <div style='font-size:15px'>{R_text}</div>
          </div>
          <div style='padding:10px 14px;background:#0a1a14;border-radius:6px;border-left:3px solid #26a69a'>
            <div style='font-size:11px;color:#888;margin-bottom:4px'>关键支撑</div>
            <div style='font-size:15px'>{S_text}</div>
          </div>
        </div>

        <div style='padding:10px 14px;background:#161620;border-radius:6px;margin-bottom:14px;border-left:3px solid #f0c040'>
          <div style='font-size:11px;color:#888;margin-bottom:4px'>整体思路</div>
          <div style='font-size:14px'>{narrative['overall_thinking']}</div>
        </div>

        <div style='display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px'>
          <div style='padding:12px 14px;background:#16100e;border-radius:6px;border:1px solid #ef535055'>
            <div style='font-size:13px;color:#ef5350;font-weight:bold;margin-bottom:8px'>📈 上行剧本</div>
            <div style='font-size:13px;line-height:1.85;color:#ccc'>{narrative['upside_story']}</div>
            <div style='margin-top:10px;font-size:11px;color:#666;border-top:1px dashed #2a2a4a;padding-top:6px'>
              目标阶梯：T1 ${ut['t1']:.1f} → T2 ${ut['t2']:.1f} → 极限 ${ut['extreme']:.1f} → 整数关 ${ut['round']:.0f}
            </div>
          </div>
          <div style='padding:12px 14px;background:#0a1610;border-radius:6px;border:1px solid #26a69a55'>
            <div style='font-size:13px;color:#26a69a;font-weight:bold;margin-bottom:8px'>📉 下行剧本</div>
            <div style='font-size:13px;line-height:1.85;color:#ccc'>{narrative['downside_story']}</div>
            <div style='margin-top:10px;font-size:11px;color:#666;border-top:1px dashed #2a2a4a;padding-top:6px'>
              目标阶梯：T1 ${dt['t1']:.1f} → T2 ${dt['t2']:.1f} → 深度 ${dt['extreme']:.1f} → 整数关 ${dt['round']:.0f}
            </div>
          </div>
        </div>

        <div style='padding:14px 16px;background:#161420;border-radius:6px;border-left:4px solid #f0c040'>
          <div style='font-size:14px;color:#f0c040;font-weight:bold;margin-bottom:10px'>🎯 日内操作思路（分水岭分级应对）</div>
          <div style='font-size:13px;line-height:2;color:#ddd'>{intraday_html}</div>
          {f'<div style="margin-top:10px;font-size:12px;color:#aaa;border-top:1px dashed #2a2a4a;padding-top:8px">💡 {narrative["m15_tip"]}</div>' if narrative['m15_tip'] else ''}
        </div>
      </div>
    </div>"""


# ─────────────────────────────────────────────
# 日内波段专题（纯价格行为，M15 + H1 主导）
# ─────────────────────────────────────────────

def analyze_intraday(analyses, data):
    """
    生成日内波段专题分析：
      - 24小时范围（high/low/中枢）
      - 亚盘 / 欧盘 / 美盘 区间
      - 当前位置 + 即时操作建议（多头/空头各一套，含 Entry/SL/TP1/TP2/RR）
      - 时间窗口提醒
    """
    m15 = analyses.get("m15")
    h1  = analyses.get("h1")
    if not m15 or "error" in m15 or not h1 or "error" in h1:
        return None

    df_m15 = data.get("m15")
    df_h1  = data.get("h1")
    if df_m15 is None or df_m15.empty:
        return None

    price = m15["current_price"]

    # ── 24h 范围（最后 96 根 M15 = 24小时）
    last_96 = df_m15.tail(96)
    today_high = float(last_96["High"].max())
    today_low  = float(last_96["Low"].min())
    today_range = today_high - today_low
    today_mid  = (today_high + today_low) / 2
    pos_in_range = (price - today_low) / today_range * 100 if today_range > 0 else 50

    # ── 各时段区间（基于 UTC 时间）
    sessions = {}
    try:
        idx = df_m15.tail(96).index
        # 转 UTC
        if idx.tz is None:
            utc_idx = pd.DatetimeIndex(idx).tz_localize("UTC")
        else:
            utc_idx = idx.tz_convert("UTC")
        df_session = df_m15.tail(96).copy()
        df_session.index = utc_idx
        # 亚盘 UTC 00:00-08:00 (北京 08:00-16:00)
        # 欧盘 UTC 07:00-16:00 (北京 15:00-00:00)
        # 美盘 UTC 13:00-22:00 (北京 21:00-06:00)
        for name, (s_h, e_h) in [("亚盘", (0, 8)), ("欧盘", (7, 16)), ("美盘", (13, 22))]:
            mask = (df_session.index.hour >= s_h) & (df_session.index.hour < e_h)
            sub = df_session[mask]
            if len(sub) >= 4:
                sessions[name] = {
                    "high": round(float(sub["High"].max()), 1),
                    "low":  round(float(sub["Low"].min()),  1),
                    "bars": len(sub),
                }
    except Exception:
        pass

    # ── M15 通道 + 结构
    m15_struct_cls = m15["structure"]["trend_cls"]
    m15_ch = m15.get("channel")
    m15_pos_pct = m15_ch["position_pct"] if m15_ch else 50

    # H1 趋势
    h1_struct_cls = h1["structure"]["trend_cls"]

    # ── 推荐方向（M15 优先，但需要 H1 不冲突）
    if m15_struct_cls == "bull" and h1_struct_cls != "bear":
        recommend = "long"
        rec_text = "做多优先"
        rec_color = "#26a69a"
        rec_reason = "M15 多头结构 + H1 不冲突"
    elif m15_struct_cls == "bear" and h1_struct_cls != "bull":
        recommend = "short"
        rec_text = "做空优先"
        rec_color = "#ef5350"
        rec_reason = "M15 空头结构 + H1 不冲突"
    elif m15_struct_cls == "bull" and h1_struct_cls == "bear":
        recommend = "wait"
        rec_text = "观望"
        rec_color = "#f0c040"
        rec_reason = "M15 多 vs H1 空，方向冲突，等高周期校准"
    elif m15_struct_cls == "bear" and h1_struct_cls == "bull":
        recommend = "wait"
        rec_text = "观望"
        rec_color = "#f0c040"
        rec_reason = "M15 空 vs H1 多，方向冲突，等高周期校准"
    else:
        recommend = "neutral"
        rec_text = "震荡区间"
        rec_color = "#9e9e9e"
        rec_reason = "M15 区间结构，建议高抛低吸"

    # ── 多头/空头交易方案（基于 24h 范围 + M15 ATR）
    atr_m15 = float(atr(df_m15["High"], df_m15["Low"], df_m15["Close"], 14).iloc[-1])

    # 多头方案
    long_entry_zone = (round(today_low + today_range * 0.05, 1),
                       round(today_low + today_range * 0.20, 1))
    long_sl = round(today_low - atr_m15 * 0.8, 1)
    long_tp1 = round(today_mid, 1)
    long_tp2 = round(today_high, 1)
    long_risk = abs(long_entry_zone[1] - long_sl)
    long_reward1 = abs(long_tp1 - long_entry_zone[1])
    long_reward2 = abs(long_tp2 - long_entry_zone[1])
    long_rr1 = round(long_reward1 / long_risk, 2) if long_risk > 0 else 0
    long_rr2 = round(long_reward2 / long_risk, 2) if long_risk > 0 else 0

    # 空头方案
    short_entry_zone = (round(today_high - today_range * 0.20, 1),
                        round(today_high - today_range * 0.05, 1))
    short_sl = round(today_high + atr_m15 * 0.8, 1)
    short_tp1 = round(today_mid, 1)
    short_tp2 = round(today_low, 1)
    short_risk = abs(short_sl - short_entry_zone[0])
    short_reward1 = abs(short_entry_zone[0] - short_tp1)
    short_reward2 = abs(short_entry_zone[0] - short_tp2)
    short_rr1 = round(short_reward1 / short_risk, 2) if short_risk > 0 else 0
    short_rr2 = round(short_reward2 / short_risk, 2) if short_risk > 0 else 0

    # ── 当前时段
    now = datetime.utcnow()
    h_utc = now.hour
    if 0 <= h_utc < 7:
        current_session = "亚盘活跃期"
        session_note = "亚盘流动性较小，倾向震荡，不宜重仓追单。等欧盘开盘方向。"
    elif 7 <= h_utc < 13:
        current_session = "欧盘启动"
        session_note = "欧盘开盘方向往往决定日内趋势，可顺势入场，仓位可适度。"
    elif 13 <= h_utc < 16:
        current_session = "欧美盘重叠（黄金时段）"
        session_note = "流动性最高，价格波动最剧烈，是日内波段最佳入场窗口。"
    elif 16 <= h_utc < 22:
        current_session = "美盘活跃期"
        session_note = "美元数据公布频繁（21:30 / 22:30），警惕突发行情。"
    else:
        current_session = "美盘尾盘"
        session_note = "流动性下降，避免追单，亚盘开盘前减仓。"

    return {
        "current_price":  price,
        "today_high":     round(today_high, 1),
        "today_low":      round(today_low, 1),
        "today_range":    round(today_range, 1),
        "today_mid":      round(today_mid, 1),
        "pos_in_range":   round(pos_in_range, 1),
        "sessions":       sessions,
        "recommend":      recommend,
        "rec_text":       rec_text,
        "rec_color":      rec_color,
        "rec_reason":     rec_reason,
        "atr_m15":        round(atr_m15, 1),
        "m15_pos":        round(m15_pos_pct, 1),
        "long_plan": {
            "entry_low":  long_entry_zone[0],
            "entry_high": long_entry_zone[1],
            "sl":         long_sl,
            "tp1":        long_tp1,
            "tp2":        long_tp2,
            "risk":       round(long_risk, 1),
            "rr1":        long_rr1,
            "rr2":        long_rr2,
        },
        "short_plan": {
            "entry_low":  short_entry_zone[0],
            "entry_high": short_entry_zone[1],
            "sl":         short_sl,
            "tp1":        short_tp1,
            "tp2":        short_tp2,
            "risk":       round(short_risk, 1),
            "rr1":        short_rr1,
            "rr2":        short_rr2,
        },
        "current_session": current_session,
        "session_note":    session_note,
    }


def render_intraday_card(intraday):
    if not intraday:
        return ""

    # 各时段区间表
    session_html = ""
    for name in ("亚盘", "欧盘", "美盘"):
        s = intraday["sessions"].get(name)
        if s:
            range_val = s["high"] - s["low"]
            session_html += (f"<tr><td style='color:#888'>{name}</td>"
                             f"<td style='text-align:right;color:#ef5350;font-family:monospace'>{s['high']:.1f}</td>"
                             f"<td style='text-align:right;color:#26a69a;font-family:monospace'>{s['low']:.1f}</td>"
                             f"<td style='text-align:right;color:#aaa;font-family:monospace'>{range_val:.1f}</td></tr>")
        else:
            session_html += f"<tr><td style='color:#888'>{name}</td><td colspan='3' style='color:#666;text-align:center'>—</td></tr>"

    # 位置进度条
    pos = intraday["pos_in_range"]
    if pos < 25:
        pos_zone = "贴近日内低点（高赔率做多区）"
        pos_color = "#26a69a"
    elif pos > 75:
        pos_zone = "贴近日内高点（高赔率做空区）"
        pos_color = "#ef5350"
    elif 40 <= pos <= 60:
        pos_zone = "日内中枢（观望或区间交易）"
        pos_color = "#f0c040"
    else:
        pos_zone = "日内中段"
        pos_color = "#9e9e9e"

    # 多头方案
    lp = intraday["long_plan"]
    long_active = intraday["recommend"] == "long"
    long_card = f"""
    <div style='padding:12px 14px;background:{"#0a1610" if long_active else "#0e0e1e"};
                border-radius:6px;border:{"2px solid #26a69a" if long_active else "1px solid #1a3a2a"}'>
      <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>
        <div style='font-size:14px;color:#26a69a;font-weight:bold'>📈 多头方案 {('（推荐）' if long_active else '')}</div>
        <div style='font-size:11px;color:#888'>盈亏比 <strong style='color:#f0c040'>1:{lp['rr1']}</strong> / <strong style='color:#f0c040'>1:{lp['rr2']}</strong></div>
      </div>
      <table style='font-size:13px;width:100%'>
        <tr><td style='color:#888;width:90px'>入场区</td>
            <td style='color:#26a69a;font-family:monospace'>${lp['entry_low']:.1f} - ${lp['entry_high']:.1f}</td></tr>
        <tr><td style='color:#888'>止损</td>
            <td style='color:#ef5350;font-family:monospace'>${lp['sl']:.1f} <span style='color:#666;font-size:11px'>(风险 {lp['risk']:.1f}点)</span></td></tr>
        <tr><td style='color:#888'>目标 1</td>
            <td style='color:#26a69a;font-family:monospace'>${lp['tp1']:.1f} <span style='color:#666;font-size:11px'>(日内中枢)</span></td></tr>
        <tr><td style='color:#888'>目标 2</td>
            <td style='color:#26a69a;font-family:monospace'>${lp['tp2']:.1f} <span style='color:#666;font-size:11px'>(日内高点)</span></td></tr>
      </table>
      <div style='margin-top:8px;padding-top:6px;border-top:1px dashed #2a2a4a;font-size:11px;color:#888;line-height:1.6'>
        💡 触发条件：M15 K线在入场区收阳、出现锤子线/吞没形态、KD底部金叉<br>
        💡 仓位管理：到 TP1 减半 + 移止损至成本；到 TP2 全平
      </div>
    </div>"""

    # 空头方案
    sp = intraday["short_plan"]
    short_active = intraday["recommend"] == "short"
    short_card = f"""
    <div style='padding:12px 14px;background:{"#16100e" if short_active else "#0e0e1e"};
                border-radius:6px;border:{"2px solid #ef5350" if short_active else "1px solid #3a1a1a"}'>
      <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>
        <div style='font-size:14px;color:#ef5350;font-weight:bold'>📉 空头方案 {('（推荐）' if short_active else '')}</div>
        <div style='font-size:11px;color:#888'>盈亏比 <strong style='color:#f0c040'>1:{sp['rr1']}</strong> / <strong style='color:#f0c040'>1:{sp['rr2']}</strong></div>
      </div>
      <table style='font-size:13px;width:100%'>
        <tr><td style='color:#888;width:90px'>入场区</td>
            <td style='color:#ef5350;font-family:monospace'>${sp['entry_low']:.1f} - ${sp['entry_high']:.1f}</td></tr>
        <tr><td style='color:#888'>止损</td>
            <td style='color:#26a69a;font-family:monospace'>${sp['sl']:.1f} <span style='color:#666;font-size:11px'>(风险 {sp['risk']:.1f}点)</span></td></tr>
        <tr><td style='color:#888'>目标 1</td>
            <td style='color:#ef5350;font-family:monospace'>${sp['tp1']:.1f} <span style='color:#666;font-size:11px'>(日内中枢)</span></td></tr>
        <tr><td style='color:#888'>目标 2</td>
            <td style='color:#ef5350;font-family:monospace'>${sp['tp2']:.1f} <span style='color:#666;font-size:11px'>(日内低点)</span></td></tr>
      </table>
      <div style='margin-top:8px;padding-top:6px;border-top:1px dashed #2a2a4a;font-size:11px;color:#888;line-height:1.6'>
        💡 触发条件：M15 K线在入场区收阴、出现射击之星/吞没形态、KD顶部死叉<br>
        💡 仓位管理：到 TP1 减半 + 移止损至成本；到 TP2 全平
      </div>
    </div>"""

    return f"""
    <div class='card' style='border:1px solid #3a3a5a;background:linear-gradient(135deg,#0e0e1e 0%,#10141e 100%)'>
      <h3>⚡ 日内波段专题 · 纯价格行为（M15 + H1）</h3>
      
      <!-- 第一行：日内框架 + 推荐方向 -->
      <div style='display:grid;grid-template-columns:1.4fr 1fr;gap:14px;margin-bottom:14px'>
        <div>
          <div style='font-size:13px;color:#888;margin-bottom:8px'>📊 24小时框架</div>
          <table style='width:100%;font-size:13px;margin-bottom:10px'>
            <tr><td style='color:#888;width:90px'>日内最高</td>
                <td style='color:#ef5350;font-family:monospace;font-weight:bold'>${intraday['today_high']:.1f}</td>
                <td style='color:#666;text-align:right;font-size:11px'>+{intraday['today_high']-intraday['current_price']:.1f}</td></tr>
            <tr><td style='color:#888'>日内中枢</td>
                <td style='color:#f0c040;font-family:monospace'>${intraday['today_mid']:.1f}</td>
                <td style='color:#666;text-align:right;font-size:11px'>{intraday['today_mid']-intraday['current_price']:+.1f}</td></tr>
            <tr><td style='color:#888'>日内最低</td>
                <td style='color:#26a69a;font-family:monospace;font-weight:bold'>${intraday['today_low']:.1f}</td>
                <td style='color:#666;text-align:right;font-size:11px'>-{intraday['current_price']-intraday['today_low']:.1f}</td></tr>
            <tr><td style='color:#888'>日内波幅</td>
                <td colspan='2' style='color:#aaa;font-family:monospace'>{intraday['today_range']:.1f} 点 &nbsp;<span style='color:#666;font-size:11px'>(M15 ATR: {intraday['atr_m15']:.1f})</span></td></tr>
          </table>
          <div style='font-size:11px;color:#666;margin-bottom:4px'>当前位置（日内 0% - 100%）</div>
          <div style='position:relative;height:24px;background:#0a0a14;border-radius:6px;overflow:hidden;margin-bottom:6px'>
            <div style='position:absolute;left:{pos}%;top:0;bottom:0;width:3px;background:#fff;box-shadow:0 0 6px #fff'></div>
            <div style='position:absolute;left:0;right:0;top:0;bottom:0;display:flex;align-items:center;justify-content:center;color:{pos_color};font-size:12px;font-weight:bold'>
              {pos:.0f}% · {pos_zone}
            </div>
          </div>
        </div>
        <div>
          <div style='font-size:13px;color:#888;margin-bottom:8px'>🎯 日内推荐</div>
          <div style='padding:14px;background:#0a0a14;border-radius:8px;border:2px solid {intraday['rec_color']};text-align:center'>
            <div style='font-size:24px;font-weight:bold;color:{intraday['rec_color']};margin-bottom:6px'>{intraday['rec_text']}</div>
            <div style='font-size:12px;color:#aaa;margin-bottom:10px'>{intraday['rec_reason']}</div>
            <div style='font-size:11px;color:#666;border-top:1px dashed #2a2a4a;padding-top:8px;margin-top:8px'>
              <div style='color:#f0c040;font-weight:bold;margin-bottom:4px'>🕐 {intraday['current_session']}</div>
              <div style='color:#aaa;line-height:1.6'>{intraday['session_note']}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 第二行：亚欧美盘区间 -->
      <div style='margin-bottom:14px'>
        <div style='font-size:13px;color:#888;margin-bottom:6px'>🌐 各时段区间（北京时间：亚盘 08-16 / 欧盘 15-00 / 美盘 21-06）</div>
        <table style='width:100%;font-size:13px'>
          <thead><tr style='color:#666;font-size:11px'>
            <th style='text-align:left'>时段</th>
            <th style='text-align:right'>高点</th>
            <th style='text-align:right'>低点</th>
            <th style='text-align:right'>波幅</th>
          </tr></thead>
          <tbody>{session_html}</tbody>
        </table>
      </div>

      <!-- 第三行：多空双方案 -->
      <div style='display:grid;grid-template-columns:1fr 1fr;gap:14px'>
        {long_card}
        {short_card}
      </div>
    </div>"""


def render_hero_bar(plan, intraday, data):
    """顶部 KPI 条：当前价 / 24h变化 / 主判断 / 当前指令 / 日内推荐"""
    if not plan:
        return ""
    price = plan["current_price"]
    main_color = _color(plan["main_cls"])
    action_color_map = {"bull": "var(--bull)", "bear": "var(--bear)",
                         "neutral": "var(--text-dim)", "warn": "var(--warn)"}
    action_color = action_color_map.get(plan["action_cls"], "var(--text-dim)")

    # 24h 变化（基于 H1 数据，用 24 根 H1 = 24 小时）
    chg_pct = chg_abs = 0.0
    has_chg = False
    if data and "h1" in data and data["h1"] is not None and len(data["h1"]) >= 25:
        price_24h_ago = float(data["h1"]["Close"].iloc[-25])
        if price_24h_ago > 0:
            chg_abs = price - price_24h_ago
            chg_pct = chg_abs / price_24h_ago * 100
            has_chg = True

    if has_chg:
        chg_color = "var(--bull)" if chg_abs >= 0 else "var(--bear)"
        chg_arrow = "▲" if chg_abs >= 0 else "▼"
        chg_text = f"{chg_arrow} {chg_abs:+.2f} ({chg_pct:+.2f}%) · 24h"
    else:
        chg_color = "var(--text-mute)"
        chg_text = "数据不足"

    # 日内推荐
    intraday_text = "—"
    intraday_color = "var(--text-dim)"
    intraday_sub = "M15 数据不足"
    if intraday:
        intraday_text = intraday["rec_text"]
        intraday_color = intraday["rec_color"]
        intraday_sub = f"{intraday['current_session']} · 位于日内 {intraday['pos_in_range']:.0f}%"

    return f"""
    <div class='hero'>
      <div class='hero-cell'>
        <div class='hero-label'>XAUUSD · 当前价</div>
        <div class='hero-value gold'>${price:,.2f}</div>
        <div class='hero-sub' style='color:{chg_color}'>{chg_text} · 24h</div>
      </div>
      <div class='hero-cell'>
        <div class='hero-label'>主判断</div>
        <div class='hero-value' style='color:{main_color};font-size:18px'>{plan['main_view']}</div>
        <div class='hero-sub'>{plan['main_desc']}</div>
      </div>
      <div class='hero-cell'>
        <div class='hero-label'>当前指令</div>
        <div class='hero-value' style='color:{action_color};font-size:18px'>{plan['action']}</div>
        <div class='hero-sub'>{plan['action_desc']}</div>
      </div>
      <div class='hero-cell'>
        <div class='hero-label'>日内推荐</div>
        <div class='hero-value' style='color:{intraday_color};font-size:18px'>{intraday_text}</div>
        <div class='hero-sub'>{intraday_sub}</div>
      </div>
    </div>"""


def render_html(analyses, source, data=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    sections = []
    for key, label in [("daily", "日线"), ("h4", "H4"), ("h1", "H1"), ("m15", "M15 (日内波段)")]:
        a = analyses.get(key)
        if not a or "error" in a:
            sections.append(f"""
            <div class='card'>
              <h3>{label} 周期价格行为</h3>
              <p style='color:#666;font-size:13px'>数据不足，无法分析</p>
            </div>""")
            continue
        df = a["_df"]
        pivots_table = render_pivots_table(a, df.index)
        structure_card = render_structure_card(a["structure"])
        channel_card = render_channel_card(a["channel"], a["current_price"])
        bos_card = render_bos_card(a["bos_events"])
        # 渲染图表（不同周期显示不同 K 线数）
        chart_n = {"daily": 80, "h4": 100, "h1": 120, "m15": 150}.get(key, 100)
        chart_b64 = render_chart_b64(df, a, label, last_n=chart_n)
        chart_html = (f'<div style="margin-bottom:14px;text-align:center"><img src="data:image/png;base64,{chart_b64}" '
                       f'style="max-width:100%;border-radius:6px;border:1px solid #2a2a4a"></div>'
                       if chart_b64 else '')
        sections.append(f"""
        <div class='card' id='tf-{key}'>
          <h3>{label} 周期价格行为</h3>
          <div style='font-size:12px;color:#666;margin-bottom:12px'>
            当前价 <strong style='color:#f0c040'>${a['current_price']:.2f}</strong> &nbsp;|&nbsp;
            转折点共 {a['pivot_count']} 个 &nbsp;|&nbsp;
            ZigZag 阈值 {a['atr_mult']}× ATR
          </div>
          {chart_html}
          <div class='three-col'>
            <div>
              <div style='font-size:13px;color:#888;margin-bottom:6px'>① 市场结构</div>
              {structure_card}
              <div style='font-size:13px;color:#888;margin:14px 0 6px'>② BOS / CHoCH 事件</div>
              {bos_card}
            </div>
            <div>
              <div style='font-size:13px;color:#888;margin-bottom:6px'>③ 趋势通道</div>
              {channel_card}
            </div>
            <div>
              <div style='font-size:13px;color:#888;margin-bottom:6px'>④ 转折点序列（最近 12 个）</div>
              {pivots_table}
            </div>
          </div>
        </div>""")
    body = "\n".join(sections)
    # 综合交易计划（放在最上面）
    plan = generate_trading_plan(analyses)
    plan_html = render_trading_plan(plan)
    narrative = generate_narrative(plan, analyses)
    narrative_html = render_narrative_card(narrative)
    intraday = analyze_intraday(analyses, data or {})
    intraday_html = render_intraday_card(intraday)
    hero_html = render_hero_bar(plan, intraday, data)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>XAU/USD 价格行为分析</title>
<style>
  :root{{
    --bg-deep:#08080f; --bg-card:#0e0e1e; --bg-sub:#10101d; --bg-darker:#0a0a14;
    --bull:#26a69a; --bear:#ef5350; --gold:#f0c040; --warn:#ff9800;
    --text:#e0e0e0; --text-dim:#aaa; --text-mute:#666;
    --border:#1a1a2e; --border-strong:#2a2a4a;
    --mono:'JetBrains Mono','Consolas','SF Mono',monospace;
  }}
  *{{box-sizing:border-box}}
  html{{scroll-behavior:smooth}}
  body{{background:var(--bg-deep);color:var(--text);font-family:'Microsoft YaHei','Segoe UI',Tahoma,sans-serif;
       max-width:1400px;margin:0 auto;padding:14px 14px;font-size:13px;padding-top:60px;line-height:1.55}}
  h1{{color:var(--gold);text-align:center;font-size:24px;margin:6px 0 4px;font-weight:300;letter-spacing:3px}}
  h2{{text-align:center;color:var(--text-mute);font-size:12px;font-weight:normal;margin:0 0 16px}}
  h3{{color:var(--gold);font-size:15px;margin:0 0 14px;font-weight:600;display:flex;align-items:center;gap:8px;
      padding-bottom:10px;border-bottom:1px solid var(--border-strong)}}
  .card{{background:var(--bg-card);padding:18px 20px;border-radius:10px;margin-bottom:14px;
        border:1px solid var(--border);scroll-margin-top:60px}}
  div[id^='sec-'],div[id^='tf-']{{scroll-margin-top:60px}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  th,td{{padding:5px 8px;text-align:left}}
  td{{border-bottom:1px solid var(--border)}}
  .three-col{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}}
  @media(max-width:1100px){{.three-col{{grid-template-columns:1fr}}}}
  .footer{{text-align:center;color:#333;font-size:11px;margin-top:20px;padding:10px}}
  .legend{{font-size:12px;color:var(--text-mute);line-height:1.85}}
  /* 顶部导航 */
  .top-nav{{position:fixed;top:0;left:0;right:0;background:rgba(8,8,15,0.92);backdrop-filter:blur(12px);
           padding:9px 20px;border-bottom:1px solid var(--border-strong);z-index:1000;display:flex;
           justify-content:center;gap:6px;flex-wrap:wrap;font-size:12px}}
  .top-nav a{{color:var(--text-dim);text-decoration:none;padding:4px 10px;border-radius:5px;
             transition:all 0.18s;font-weight:500}}
  .top-nav a:hover{{color:var(--gold);background:var(--bg-sub)}}
  /* Hero KPI 条 */
  .hero{{display:grid;grid-template-columns:1.2fr 1fr 1.2fr 1fr;gap:1px;background:var(--border-strong);
        border-radius:10px;overflow:hidden;margin-bottom:14px;border:1px solid var(--border-strong)}}
  .hero-cell{{background:var(--bg-card);padding:14px 18px;display:flex;flex-direction:column;justify-content:center}}
  .hero-label{{font-size:11px;color:var(--text-mute);text-transform:uppercase;letter-spacing:1px;margin-bottom:5px}}
  .hero-value{{font-size:24px;font-weight:600;font-family:var(--mono);line-height:1.2}}
  .hero-sub{{font-size:11px;color:var(--text-dim);margin-top:4px}}
  @media(max-width:1100px){{.hero{{grid-template-columns:1fr 1fr}}}}
  /* 章节标题 */
  .sec-divider{{font-size:13px;color:var(--gold);font-weight:600;margin:22px 0 10px;
                padding:6px 12px;border-left:3px solid var(--gold);letter-spacing:1px;
                background:linear-gradient(90deg,rgba(240,192,64,0.06),transparent)}}
  /* KPI 小条 */
  .kpi-row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:14px}}
  .kpi-box{{background:var(--bg-darker);padding:10px 12px;border-radius:6px;border:1px solid var(--border)}}
  .kpi-box .l{{font-size:10px;color:var(--text-mute);text-transform:uppercase;letter-spacing:0.5px}}
  .kpi-box .v{{font-size:16px;font-weight:600;font-family:var(--mono);margin-top:3px}}
  /* 通用 */
  .mono{{font-family:var(--mono)}}
  .bull{{color:var(--bull)}} .bear{{color:var(--bear)}} .gold{{color:var(--gold)}} .warn{{color:var(--warn)}}
  .dim{{color:var(--text-dim)}} .mute{{color:var(--text-mute)}}
  .pill{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600}}
  .pill.bull{{background:rgba(38,166,154,0.15);color:var(--bull);border:1px solid rgba(38,166,154,0.4)}}
  .pill.bear{{background:rgba(239,83,80,0.15);color:var(--bear);border:1px solid rgba(239,83,80,0.4)}}
  .pill.gold{{background:rgba(240,192,64,0.15);color:var(--gold);border:1px solid rgba(240,192,64,0.4)}}
  .pill.warn{{background:rgba(255,152,0,0.15);color:var(--warn);border:1px solid rgba(255,152,0,0.4)}}
  .sub-h{{font-size:11px;color:var(--text-mute);text-transform:uppercase;letter-spacing:1px;
         margin-bottom:8px;font-weight:600}}
</style>
</head>
<body>
  <!-- 顶部导航 -->
  <div class='top-nav'>
    <a href='#sec-intraday'>⚡ 日内</a>
    <a href='#sec-plan'>📋 计划</a>
    <a href='#sec-narrative'>📖 解读</a>
    <a href='#sec-tf'>📊 多周期</a>
    <a href='#tf-daily'>日线</a>
    <a href='#tf-h4'>H4</a>
    <a href='#tf-h1'>H1</a>
    <a href='#tf-m15'>M15</a>
    <a href='#sec-method'>方法</a>
  </div>

  <h1>XAU/USD 价格行为分析</h1>
  <h2>市场结构 · 趋势通道 · BOS/CHoCH · 日内波段 &nbsp;|&nbsp; {now} &nbsp;|&nbsp; 数据源：{source}</h2>

  {hero_html}

  <div class='sec-divider'>⚡ 日内即时操作</div>
  <div id='sec-intraday'>{intraday_html}</div>

  <div class='sec-divider'>📋 多周期综合判断</div>
  <div id='sec-plan'>{plan_html}</div>

  <div class='sec-divider'>📖 行情背景解读</div>
  <div id='sec-narrative'>{narrative_html}</div>

  <div class='sec-divider' id='sec-tf'>📊 多周期价格行为详解</div>
  {body}

  <div class='card' style='background:#10101d;border-color:#3a3a5a' id='sec-method'>
    <h3>分析方法说明</h3>
    <div class='legend'>
      <strong style='color:#aaa'>① 市场结构</strong>：用 ZigZag 识别每个转折点，再标注 HH/HL（多头）或 LH/LL（空头）。
      <span style='color:#26a69a'>HH=Higher High（更高高点）</span>，
      <span style='color:#26a69a'>HL=Higher Low（更高低点）</span>，
      <span style='color:#ef5350'>LH=Lower High（更低高点）</span>，
      <span style='color:#ef5350'>LL=Lower Low（更低低点）</span>。<br>
      <strong style='color:#aaa'>② BOS（Break of Structure）</strong>：顺势突破前高/前低 → 趋势延续，是 <strong style='color:#26a69a'>顺势加仓</strong>信号。<br>
      <strong style='color:#aaa'>③ CHoCH（Change of Character）</strong>：逆势突破前高/前低 → 趋势反转预警，是 <strong style='color:#ef5350'>减仓/止盈/翻仓</strong>信号。<br>
      <strong style='color:#aaa'>④ 趋势通道</strong>：用最近的高点和低点做线性回归拟合，构成上下轨。<strong>价位贴近上轨=做空机会，贴近下轨=做多机会</strong>，突破通道=趋势加速或反转。<br>
      <strong style='color:#aaa'>⑤ 日内波段</strong>：基于最近 24 小时 M15 数据，划分亚欧美三盘区间，给出多空双方案的入场区/止损/目标位/盈亏比。
    </div>
  </div>

  <div class='card' style='background:#0a150a;border-color:#1a301a'>
    <h3>价格行为交易要点</h3>
    <table style='font-size:13px'>
      <tr><td style='color:#666;width:130px'>识别趋势</td><td style='color:#aaa'>看 HH+HL 或 LH+LL 的连续序列；4个以上同向标签 = 强结构</td></tr>
      <tr><td style='color:#666'>顺势入场</td><td style='color:#aaa'>多头：HH 后等回撤到 HL 上方做多；空头：LH 后等反弹到 LH 下方做空</td></tr>
      <tr><td style='color:#666'>BOS 信号</td><td style='color:#aaa'>顺势 BOS = 加仓信号；可在前高/前低附近找回踩入场</td></tr>
      <tr><td style='color:#666'>CHoCH 信号</td><td style='color:#aaa'>立即减仓或止盈现有持仓；等待新结构形成后再入场（不要立刻反向追单）</td></tr>
      <tr><td style='color:#666'>通道上下轨</td><td style='color:#aaa'>在通道内交易胜率最高；突破后等价格回测通道边界再决定</td></tr>
      <tr><td style='color:#666'>多周期校验</td><td style='color:#aaa'>低周期结构应顺从高周期趋势；不一致时降低仓位或观望</td></tr>
      <tr><td style='color:#666'>日内波段守则</td><td style='color:#aaa'>盈亏比 ≥1:1.5 才入场，单笔风险 ≤ 总资金 1%，重大数据前后 30min 不开仓</td></tr>
    </table>
  </div>

  <div class='footer'>XAU/USD Price Action · 市场结构 + 趋势通道 + 日内波段 · 生成于 {now}</div>
</body>
</html>"""


# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────

def run_analysis(fetch_fn=None, report_prefix="wave_analysis", report_subdir=None,
                 system_label="MT4 系统", open_browser=True):
    """
    通用分析主流程。
    
    参数：
      fetch_fn       : 数据源函数，签名 () -> (data, source_str)。默认用 fetch_data
      report_prefix  : 报告文件名前缀（如 wave_analysis / wave_mt5）
      report_subdir  : 报告子目录（基于 REPORT_DIR），None 表示直接放在 REPORT_DIR
      system_label   : 终端打印用的系统名（"MT4 系统" / "MT5 系统"）
    """
    if fetch_fn is None:
        fetch_fn = fetch_data
    print(f"[PA] 启动价格行为分析 · {system_label}")
    data, source = fetch_fn()
    if not data:
        print("[PA] 错误：无法获取行情数据")
        return None

    analyses = {}
    for key, label, atr_mult, lookback in [
        ("daily", "日线",         2.0, 120),
        ("h4",    "H4",           2.0, 150),
        ("h1",    "H1",           1.5, 200),
        ("m15",   "M15日内波段",  1.2, 200),
    ]:
        df = data.get(key)
        if df is None or df.empty:
            continue
        a = analyze_pa(df, label, atr_mult=atr_mult, lookback_bars=lookback)
        a["_df"] = df
        analyses[key] = a
        if "error" not in a:
            ch = a["channel"]
            print(f"  [PA] {label}: {a['structure']['trend']}; 通道 {ch['direction'] if ch else 'N/A'}; "
                  f"BOS事件 {len(a['bos_events'])} 个")

    # 优先用机构级渲染；失败时回退老版
    try:
        from institutional_render import render_institutional_html, MACRO_CONFIG
        # 注入实时经济日历（金十 → ForexFactory 双源回退，1h 缓存）
        try:
            from economic_calendar import get_calendar
            cal = get_calendar(days_ahead=7, min_impact="medium", verbose=True)
            if cal:
                MACRO_CONFIG["calendar"] = cal
        except Exception as e:
            print(f"  [CAL] 经济日历注入失败，使用占位: {e}")
        plan = generate_trading_plan(analyses)
        narrative = generate_narrative(plan, analyses)
        intraday = analyze_intraday(analyses, data or {})
        # 预渲染所有周期结构图
        charts = {}
        for key, lbl in [("daily", "日线"), ("h4", "H4"), ("h1", "H1"), ("m15", "M15")]:
            a = analyses.get(key)
            if not a or "error" in a: continue
            df = a["_df"]
            chart_n = {"daily": 80, "h4": 100, "h1": 120, "m15": 150}.get(key, 100)
            try:
                charts[key] = render_chart_b64(df, a, lbl, last_n=chart_n)
            except Exception as e:
                print(f"  [PA] 警告: {lbl} 图表渲染失败: {e}")
                charts[key] = ""
        html = render_institutional_html(analyses, plan, narrative, intraday, source, data, charts)
        print("[PA] 使用机构级渲染")
    except Exception as e:
        import traceback
        print(f"[PA] 机构渲染失败 ({e})，回落到旧版")
        traceback.print_exc()
        html = render_html(analyses, source, data=data)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out_dir = os.path.join(REPORT_DIR, report_subdir) if report_subdir else REPORT_DIR
    os.makedirs(out_dir, exist_ok=True)
    report_path = os.path.join(out_dir, f"{report_prefix}_{ts}.html")
    latest_name = report_prefix.replace("wave_analysis", "wave") + "_latest.html"
    latest_path = os.path.join(out_dir, latest_name)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[PA] 报告已生成: {report_path}")
    print(f"[PA] 最新报告: {latest_path}")
    if open_browser:
        try:
            os.startfile(latest_path)
        except Exception:
            webbrowser.open(f"file:///{latest_path.replace(os.sep, '/')}")
    return latest_path


def main():
    """MT4 系统入口（保持原行为不变）"""
    return run_analysis(fetch_fn=fetch_data,
                        report_prefix="wave_analysis",
                        report_subdir=None,
                        system_label="MT4 系统")


if __name__ == "__main__":
    main()
