# -*- coding: utf-8 -*-
"""
PA × Elliott Wave 融合机构报告（独立入口）
====================================================================
不影响现有任何入口（gold_analysis / wave_analysis(_mt5) / elliott_wave(_mt5)）。

本入口的定位：纯粹的"价格行为 + 艾略特波浪"双引擎机构级分析报告。

  · 左路：价格行为引擎  ─ ZigZag 转折 + 市场结构 (HH/HL/LH/LL) + 趋势通道 + BOS/CHoCH
  · 右路：波浪理论引擎  ─ 5 浪推动 + ABC 调整 + 三大铁律 + 斐波那契目标投影
  · 顶部：跨引擎共振结论 + 综合行动建议

报告输出： reports/fusion/fusion_<时间戳>.html  +  fusion_latest.html
"""

import os
import sys
import webbrowser
from datetime import datetime
from typing import Dict, Tuple, Optional

sys.path.insert(0, os.path.dirname(__file__))

from gold_analysis import fetch_data, REPORT_DIR
from wave_analysis import (
    analyze_pa,
    render_chart_b64 as render_pa_chart_b64,
    render_pivots_table,
    render_structure_card,
    render_channel_card,
    render_bos_card,
    detect_zigzag,
)
from elliott_wave import (
    detect_wave_pattern,
    render_wave_chart_b64,
    _render_pattern_block as render_elliott_block,
    _build_narrative as build_elliott_narrative,
    CSS as ELLIOTT_CSS,
    WavePattern,
)


# ════════════════════════════════════════════════════════════════════
# 跨引擎共振 / 综合判断
# ════════════════════════════════════════════════════════════════════

def cross_engine_summary(pa_results: Dict, ew_results: Dict, current_price: float) -> Dict:
    """
    汇总两个引擎的方向判断，给出共振强度。

    PA 方向取自 structure["trend_cls"] (bull/bear/neutral)
    EW 方向取自 pattern.direction (bull/bear)
    """
    rows = []
    pa_score = 0
    ew_score = 0
    total = 0
    for key, label in [("daily", "日线"), ("h4", "H4"), ("h1", "H1"), ("m15", "M15")]:
        pa = pa_results.get(key)
        ew = ew_results.get(key)
        if not pa or "error" in pa:
            pa_dir = "—"; pa_cls = "neutral"
        else:
            pa_cls = pa["structure"]["trend_cls"]
            pa_dir = pa["structure"]["trend"]
        if not ew or ew[1] is None:
            ew_dir = "—"; ew_cls = "neutral"
        else:
            ew_cls = ew[1].direction
            ew_dir = ("看涨推动 W%d" % ew[1].completeness) if ew_cls == "bull" else ("看跌推动 W%d" % ew[1].completeness)

        # 一致性
        if pa_cls == ew_cls and pa_cls in ("bull", "bear"):
            consistency = "强共振"
            cclass = pa_cls
        elif pa_cls in ("bull", "bear") and ew_cls in ("bull", "bear") and pa_cls != ew_cls:
            consistency = "矛盾"
            cclass = "neutral"
        else:
            consistency = "弱信号"
            cclass = "neutral"

        rows.append({
            "key": key, "label": label,
            "pa_dir": pa_dir, "pa_cls": pa_cls,
            "ew_dir": ew_dir, "ew_cls": ew_cls,
            "consistency": consistency, "cclass": cclass,
        })
        if pa_cls == "bull": pa_score += 1
        elif pa_cls == "bear": pa_score -= 1
        if ew_cls == "bull": ew_score += 1
        elif ew_cls == "bear": ew_score -= 1
        total += 1

    combined = pa_score + ew_score
    if combined >= 3:
        verdict = "多头主导（双引擎强共振）"; verdict_cls = "bull"
    elif combined <= -3:
        verdict = "空头主导（双引擎强共振）"; verdict_cls = "bear"
    elif combined > 0:
        verdict = "偏多（共振不充分，等待大级别确认）"; verdict_cls = "bull"
    elif combined < 0:
        verdict = "偏空（共振不充分，等待大级别确认）"; verdict_cls = "bear"
    else:
        verdict = "震荡 / 多空分歧（暂不操作或仅做日内）"; verdict_cls = "neutral"

    return {
        "rows": rows,
        "pa_score": pa_score,
        "ew_score": ew_score,
        "combined": combined,
        "verdict": verdict,
        "verdict_cls": verdict_cls,
        "current_price": current_price,
    }


# ════════════════════════════════════════════════════════════════════
# 渲染：附加 CSS + 双栏布局
# ════════════════════════════════════════════════════════════════════

EXTRA_CSS = """
.fusion-hero{margin:6px 0 22px;padding:22px 26px;background:linear-gradient(135deg,#0d0d18 0%,#15151f 100%);
        border:1px solid var(--border-gold);border-radius:12px;position:relative;overflow:hidden}
.fusion-hero::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;
        background:linear-gradient(90deg,#1ddfa9,#d9b85c,#ff5e7c)}
.verdict{font-size:24px;font-weight:800;letter-spacing:1px;margin:6px 0 10px}
.verdict.bull{color:var(--bull)}
.verdict.bear{color:var(--bear)}
.verdict.neutral{color:var(--text-dim)}
.score-bar{display:flex;gap:18px;margin-top:14px;flex-wrap:wrap}
.score-card{flex:1;min-width:180px;background:var(--bg2);border:1px solid var(--border);
        border-radius:8px;padding:12px 14px}
.score-label{font-size:11px;color:var(--text-mute);text-transform:uppercase;letter-spacing:1px}
.score-val{font-size:22px;font-weight:800;margin-top:4px;font-family:var(--mono)}
.score-val.bull{color:var(--bull)} .score-val.bear{color:var(--bear)} .score-val.neutral{color:var(--text-dim)}
.matrix{width:100%;border-collapse:collapse;margin-top:14px;font-size:12.5px}
.matrix th,.matrix td{padding:9px 10px;border-bottom:1px solid var(--border);text-align:left}
.matrix th{color:var(--text-mute);font-size:11px;letter-spacing:1px;text-transform:uppercase}
.matrix .pill{display:inline-block;padding:2px 9px;border-radius:11px;font-size:11px;font-weight:700;font-family:var(--mono)}
.pill.bull{background:rgba(29,223,169,0.15);color:var(--bull);border:1px solid rgba(29,223,169,0.4)}
.pill.bear{background:rgba(255,94,124,0.15);color:var(--bear);border:1px solid rgba(255,94,124,0.4)}
.pill.neutral{background:rgba(122,130,144,0.15);color:var(--text-mute);border:1px solid rgba(122,130,144,0.3)}

.dual-block{background:var(--bg1);border:1px solid var(--border);border-radius:10px;
        padding:20px 22px;margin-bottom:24px;border-left:3px solid var(--gold)}
.dual-head{display:flex;justify-content:space-between;align-items:center;
        padding-bottom:10px;border-bottom:1px dashed var(--border);margin-bottom:16px}
.dual-title{font-size:18px;font-weight:700;color:var(--gold);letter-spacing:1.5px}
.tf-tags{display:flex;gap:8px;flex-wrap:wrap}
.charts-row{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px}
@media (max-width:1100px){.charts-row{grid-template-columns:1fr}}
.chart-pane{background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:12px}
.chart-pane h4{font-size:12px;color:var(--gold-dim);text-transform:uppercase;
        letter-spacing:1.5px;margin-bottom:8px;padding-bottom:6px;
        border-bottom:1px solid var(--border)}
.chart-pane h4 small{font-size:10.5px;color:var(--text-mute);font-weight:400;
        letter-spacing:0;margin-left:6px}
.chart-pane .chart-wrap{margin:0;border:none}
.chart-pane .chart-wrap img{width:100%;display:block;border-radius:5px}
.detail-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
@media (max-width:1300px){.detail-grid{grid-template-columns:repeat(2,1fr)}}
@media (max-width:700px){.detail-grid{grid-template-columns:1fr}}
.detail-card{background:var(--bg2);border:1px solid var(--border);border-radius:7px;
        padding:12px 14px;min-height:90px}
.detail-card h5{font-size:11px;color:var(--text-mute);text-transform:uppercase;
        letter-spacing:1px;margin-bottom:8px;padding-bottom:4px;
        border-bottom:1px solid var(--border)}
.detail-card h5 .src{float:right;font-size:9px;color:var(--gold-dim);font-weight:600}
.tables-row{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}
@media (max-width:1100px){.tables-row{grid-template-columns:1fr}}
.alerts-row{display:flex;flex-direction:column;gap:10px;margin-top:14px}

/* 顶部综合行情分析 */
.market-overview{margin:8px 0 24px;padding:24px 28px;background:linear-gradient(135deg,#0a0a14 0%,#101019 100%);
        border:1px solid var(--border-gold);border-radius:12px;line-height:1.95;
        font-size:13.5px;color:var(--text-dim)}
.market-overview h2{font-size:18px;font-weight:800;color:var(--gold);
        letter-spacing:1.5px;margin-bottom:14px;display:flex;align-items:center;gap:10px}
.market-overview h2::before{content:"❖";color:var(--gold-dim);font-size:20px}
.market-overview p{margin-bottom:11px}
.market-overview b{color:var(--gold)}
.market-overview .bullish{color:var(--bull);font-weight:700}
.market-overview .bearish{color:var(--bear);font-weight:700}
.market-overview .warn{color:var(--warn);font-weight:700}
.mo-keypoints{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:14px}
@media (max-width:900px){.mo-keypoints{grid-template-columns:1fr}}
.mo-kp{background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:12px 14px}
.mo-kp .lbl{font-size:10.5px;color:var(--text-mute);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px}
.mo-kp .val{font-family:var(--mono);font-size:15px;font-weight:700;color:var(--text)}
.mo-kp .val.bull{color:var(--bull)} .mo-kp .val.bear{color:var(--bear)} .mo-kp .val.gold{color:var(--gold)}
"""


def _verdict_card(summary: Dict) -> str:
    rows_html = []
    for r in summary["rows"]:
        rows_html.append(f"""
        <tr>
          <td><b>{r['label']}</b></td>
          <td><span class="pill {r['pa_cls']}">{r['pa_dir']}</span></td>
          <td><span class="pill {r['ew_cls']}">{r['ew_dir']}</span></td>
          <td><span class="pill {r['cclass']}">{r['consistency']}</span></td>
        </tr>""")
    pa_cls = "bull" if summary["pa_score"] > 0 else "bear" if summary["pa_score"] < 0 else "neutral"
    ew_cls = "bull" if summary["ew_score"] > 0 else "bear" if summary["ew_score"] < 0 else "neutral"
    cb_cls = summary["verdict_cls"]
    return f"""
    <div class="fusion-hero">
      <div style="font-size:11px;color:var(--text-mute);letter-spacing:2px;text-transform:uppercase">
        Cross-Engine Verdict · 双引擎综合判断
      </div>
      <div class="verdict {summary['verdict_cls']}">{summary['verdict']}</div>
      <div style="color:var(--text-dim);font-size:13px">
        当前价 <b style="color:var(--gold);font-family:var(--mono)">{summary['current_price']:.2f}</b>
        &nbsp;|&nbsp; 共振分数（多+ / 空-）：<b class="mono">{summary['combined']:+d}</b>
      </div>
      <div class="score-bar">
        <div class="score-card">
          <div class="score-label">价格行为引擎得分</div>
          <div class="score-val {pa_cls}">{summary['pa_score']:+d}</div>
        </div>
        <div class="score-card">
          <div class="score-label">艾略特波浪引擎得分</div>
          <div class="score-val {ew_cls}">{summary['ew_score']:+d}</div>
        </div>
        <div class="score-card">
          <div class="score-label">综合方向</div>
          <div class="score-val {cb_cls}">{summary['combined']:+d}</div>
        </div>
      </div>
      <table class="matrix">
        <thead><tr><th>周期</th><th>价格行为方向</th><th>艾略特方向</th><th>跨引擎一致性</th></tr></thead>
        <tbody>{''.join(rows_html)}</tbody>
      </table>
    </div>"""


def _render_dual_tf(label: str,
                    pa_result: Optional[Dict],
                    ew_tuple: Optional[Tuple],
                    pa_chart: str,
                    ew_chart: str,
                    df) -> str:
    # ── 顶部标签行 ──
    tags = []
    if pa_result and "error" not in pa_result:
        tcls = pa_result["structure"]["trend_cls"]
        tags.append(f'<span class="pill {tcls}">PA · {pa_result["structure"]["trend"]}</span>')
    if ew_tuple and ew_tuple[1] is not None:
        pat = ew_tuple[1]
        ecls = pat.direction
        ew_dir_zh = "看涨推动" if ecls == "bull" else "看跌推动"
        tags.append(f'<span class="pill {ecls}">EW · {ew_dir_zh} W{pat.completeness}/5</span>')
    tags_html = "".join(tags) or '<span class="pill neutral">数据不足</span>'

    # ── 双图表行 ──
    pa_chart_html = (f'<div class="chart-wrap"><img src="data:image/png;base64,{pa_chart}"/></div>'
                     if pa_chart else
                     '<div style="color:var(--text-mute);padding:30px;text-align:center">PA 图表不可用</div>')
    ew_chart_html = (f'<div class="chart-wrap"><img src="data:image/png;base64,{ew_chart}"/></div>'
                     if ew_chart else
                     '<div style="color:var(--text-mute);padding:30px;text-align:center">EW 图表不可用</div>')
    charts_row = f"""
    <div class="charts-row">
      <div class="chart-pane">
        <h4>价格行为引擎 <small>ZigZag · 通道 · BOS / CHoCH</small></h4>
        {pa_chart_html}
      </div>
      <div class="chart-pane">
        <h4>艾略特波浪引擎 <small>5 浪 · ABC · 斐波那契目标</small></h4>
        {ew_chart_html}
      </div>
    </div>"""

    # ── 4 列详情卡片（PA 结构 / PA 通道 / EW 规则 / EW 比率+目标） ──
    if pa_result and "error" not in pa_result:
        struct_card = render_structure_card(pa_result["structure"])
        ch_card = render_channel_card(pa_result["channel"], pa_result["current_price"])
    else:
        struct_card = '<div style="color:var(--text-mute);font-size:12px">数据不足</div>'
        ch_card = '<div style="color:var(--text-mute);font-size:12px">数据不足</div>'

    # EW 规则 / 比率 / 目标 — 直接构造小卡片内容
    if ew_tuple and ew_tuple[1] is not None:
        pat = ew_tuple[1]
        rule_text = {
            "W2_holds":         "W2 不破 W1 起点",
            "W3_extends":       "W3 突破 W1 终点",
            "W4_no_overlap":    "W4 不进入 W1 价格区",
            "W3_not_shortest":  "W3 非最短浪",
        }
        rules_html = ""
        for k, txt in rule_text.items():
            if k in pat.rules_passed:
                ok = pat.rules_passed[k]
                cls = "rule-pass" if ok else "rule-fail"
                ic = "✓" if ok else "✗"
                rules_html += (f'<div class="rule"><div class="rule-icon {cls}">{ic}</div>'
                               f'<div class="rule-text">{txt}</div></div>')
        fib_ideal = {
            "W2/W1": "理想 0.5~0.618",
            "W3/W1": "理想 1.618",
            "W4/W3": "理想 0.382",
            "W5/W1": "理想 1.0/1.618",
        }
        fib_html = ""
        for k, ideal in fib_ideal.items():
            if k in pat.fibs:
                v = pat.fibs[k]
                fib_html += (f"<div class='kv'><span class='k'>{k}<br><small style='color:var(--text-mute)'>{ideal}</small></span>"
                             f"<span class='v gold'>{v:.3f}</span></div>")
        tgt_html = ""
        ecls = pat.direction
        for k, v in pat.next_target.items():
            tgt_html += f"<div class='kv'><span class='k'>{k}</span><span class='v {ecls}'>{v:.2f}</span></div>"
        if pat.invalidation is not None:
            verb = "跌破" if ecls == "bull" else "升破"
            tgt_html += (f"<div class='kv' style='border-top:1px dashed var(--border);margin-top:6px;padding-top:8px'>"
                         f"<span class='k'>⚠ 作废价（{verb}）</span>"
                         f"<span class='v bear'>{pat.invalidation:.2f}</span></div>")
    else:
        rules_html = '<div style="color:var(--text-mute);font-size:12px">未识别有效形态</div>'
        fib_html = '<div style="color:var(--text-mute);font-size:12px">—</div>'
        tgt_html = '<div style="color:var(--text-mute);font-size:12px">—</div>'

    detail_grid = f"""
    <div class="detail-grid">
      <div class="detail-card">
        <h5>市场结构 <span class="src">PA</span></h5>{struct_card}
      </div>
      <div class="detail-card">
        <h5>趋势通道 <span class="src">PA</span></h5>{ch_card}
      </div>
      <div class="detail-card">
        <h5>艾略特三铁律 <span class="src">EW</span></h5>{rules_html}
      </div>
      <div class="detail-card">
        <h5>下一浪目标 <span class="src">EW</span></h5>{tgt_html}
      </div>
    </div>"""

    # ── 表格行（左：PA 转折点；右：EW 浪点 + 比率） ──
    if pa_result and "error" not in pa_result:
        pivots_tbl = render_pivots_table(pa_result, df.index)
    else:
        pivots_tbl = '<div style="color:var(--text-mute);font-size:12px">无</div>'

    if ew_tuple and ew_tuple[1] is not None:
        pat = ew_tuple[1]
        from elliott_wave import CIRCLED
        rows = []
        for p in pat.impulse + pat.correction:
            try:
                t = df.index[p.idx].strftime("%m-%d %H:%M") if p.idx < len(df) else f"#{p.idx}"
            except Exception:
                t = f"#{p.idx}"
            rows.append(
                f"<tr><td class='mono'>{CIRCLED.get(p.label, p.label)}</td>"
                f"<td>{t}</td><td>{'高' if p.pivot_type == 'H' else '低'}</td>"
                f"<td class='right mono'>{p.price:.2f}</td></tr>"
            )
        wave_pts_tbl = (f"<table><thead><tr><th>浪</th><th>时间</th><th>类型</th>"
                        f"<th class='right'>价格</th></tr></thead>"
                        f"<tbody>{''.join(rows)}</tbody></table>")
        wave_extra = f"<div style='margin-top:10px;padding-top:10px;border-top:1px dashed var(--border)'>{fib_html}</div>"
    else:
        wave_pts_tbl = '<div style="color:var(--text-mute);font-size:12px">未识别</div>'
        wave_extra = ""

    tables_row = f"""
    <div class="tables-row">
      <div class="detail-card">
        <h5>近 12 转折点 <span class="src">PA</span></h5>{pivots_tbl}
      </div>
      <div class="detail-card">
        <h5>艾略特浪点序列 + 实测比率 <span class="src">EW</span></h5>
        {wave_pts_tbl}{wave_extra}
      </div>
    </div>"""

    # ── 警示行（BOS / 作废告警） ──
    alerts = []
    if pa_result and "error" not in pa_result:
        bos = render_bos_card(pa_result["bos_events"])
        alerts.append(f'<div class="detail-card"><h5>BOS / CHoCH 事件 <span class="src">PA</span></h5>{bos}</div>')
    alerts_row = f'<div class="alerts-row">{"".join(alerts)}</div>' if alerts else ""

    return f"""
    <div class="dual-block" id="tf-{label}">
      <div class="dual-head">
        <div class="dual-title">{label} · 双引擎对照</div>
        <div class="tf-tags">{tags_html}</div>
      </div>
      {charts_row}
      {detail_grid}
      {tables_row}
      {alerts_row}
    </div>"""


def _build_market_overview(pa_results: Dict, ew_results: Dict, summary: Dict,
                           current_price: float) -> str:
    """生成顶部综合行情分析叙述（融合 PA + EW 双引擎结论）。"""
    paragraphs = []

    # 第 1 段：当前定位
    verdict = summary["verdict"]
    vc = summary["verdict_cls"]
    cls_zh = "看涨" if vc == "bull" else "看跌" if vc == "bear" else "中性"
    paragraphs.append(
        f"<p><b>当前定位：</b>价格 <b>{current_price:.2f}</b>，"
        f"双引擎综合判断为 <span class='{('bullish' if vc == 'bull' else 'bearish' if vc == 'bear' else 'warn')}'>"
        f"{verdict}</span>。"
        f"价格行为引擎打分 <b>{summary['pa_score']:+d}</b>，艾略特波浪引擎打分 <b>{summary['ew_score']:+d}</b>，"
        f"合计 <b>{summary['combined']:+d}</b>。</p>"
    )

    # 第 2 段：大级别结构（日线 + H4）
    big_pa = []
    big_ew = []
    for key, lbl in [("daily", "日线"), ("h4", "H4")]:
        pa = pa_results.get(key)
        ew = ew_results.get(key)
        if pa and "error" not in pa:
            ch = pa["channel"]
            ch_str = f"{ch['direction']}（中线 {ch['mid_now']:.1f}）" if ch else "通道未成型"
            big_pa.append(f"{lbl}结构 <b>{pa['structure']['trend']}</b>，{ch_str}")
        if ew and ew[1] is not None:
            big_ew.append(f"{lbl} 浪型 <b>{('看涨' if ew[1].direction == 'bull' else '看跌')}推动</b>"
                          f"（{ew[1].state}）")
    if big_pa or big_ew:
        line2 = "<p><b>大级别格局：</b>"
        if big_pa:
            line2 += "价格行为视角下，" + "；".join(big_pa) + "。"
        if big_ew:
            line2 += "艾略特视角下，" + "；".join(big_ew) + "。"
        line2 += "</p>"
        paragraphs.append(line2)

    # 第 3 段：日内驱动（H1 + M15）
    sm_pa = []
    sm_ew = []
    for key, lbl in [("h1", "H1"), ("m15", "M15")]:
        pa = pa_results.get(key)
        ew = ew_results.get(key)
        if pa and "error" not in pa:
            bos_n = len(pa["bos_events"])
            sm_pa.append(f"{lbl} {pa['structure']['trend']}，BOS 事件 {bos_n} 个")
        if ew and ew[1] is not None:
            pat = ew[1]
            tgts = list(pat.next_target.items())
            tgt_brief = f"目标位 {tgts[0][1]:.1f}" if tgts else ""
            sm_ew.append(f"{lbl} {('多头' if pat.direction == 'bull' else '空头')}浪 W{pat.completeness}{tgt_brief}")
    if sm_pa or sm_ew:
        line3 = "<p><b>短线驱动：</b>"
        if sm_pa:
            line3 += "结构上 " + "；".join(sm_pa) + "。"
        if sm_ew:
            line3 += "浪型上 " + "；".join(sm_ew) + "。"
        line3 += "</p>"
        paragraphs.append(line3)

    # 第 4 段：关键价位（汇总通道边界 + 艾略特目标 + 作废价）
    key_levels = []
    # 通道：取 H4 / H1 的上下轨
    for key, lbl in [("h4", "H4"), ("h1", "H1")]:
        pa = pa_results.get(key)
        if pa and "error" not in pa and pa.get("channel"):
            ch = pa["channel"]
            key_levels.append(f"{lbl} 通道上轨 <b>{ch['upper_now']:.1f}</b> / 下轨 <b>{ch['lower_now']:.1f}</b>")
    # EW 目标：取主导级别（取 ew_score 偏向方）
    main_key = None
    for key in ("daily", "h4", "h1"):
        if key in ew_results and ew_results[key][1] is not None:
            main_key = key; break
    if main_key:
        pat = ew_results[main_key][1]
        if pat.next_target:
            tgt_brief = "、".join([f"{k} {v:.1f}" for k, v in list(pat.next_target.items())[:3]])
            key_levels.append(f"{('日线' if main_key == 'daily' else main_key.upper())} 艾略特目标位 {tgt_brief}")
        if pat.invalidation is not None:
            verb = "跌破" if pat.direction == "bull" else "升破"
            key_levels.append(f"<span class='warn'>主计数作废价</span> ({verb}) <b>{pat.invalidation:.1f}</b>")
    if key_levels:
        paragraphs.append("<p><b>关键价位：</b>" + "；".join(key_levels) + "。</p>")

    # 第 5 段：执行建议
    if vc == "bull" and summary["combined"] >= 3:
        advice = ("策略倾向：<span class='bullish'>顺势做多</span>。等待价格回踩 H1/H4 通道下轨或 EW 调整浪低点企稳后入场，"
                  "止损放在主计数作废价之外，目标参照艾略特 W3/W5 投影位。")
    elif vc == "bear" and summary["combined"] <= -3:
        advice = ("策略倾向：<span class='bearish'>顺势做空</span>。等待价格反弹至 H1/H4 通道上轨或 EW 反弹浪高点出现见顶信号后入场，"
                  "止损放在主计数作废价之外，目标参照艾略特 W3/W5 投影位。")
    elif vc == "bull":
        advice = ("策略倾向：<span class='warn'>谨慎偏多</span>。共振强度不足，建议等待大级别（日线/H4）方向确认后再行动，"
                  "或仅做日内小级别波段，严格控制仓位。")
    elif vc == "bear":
        advice = ("策略倾向：<span class='warn'>谨慎偏空</span>。共振强度不足，建议等待大级别（日线/H4）方向确认后再行动，"
                  "或仅做日内小级别波段，严格控制仓位。")
    else:
        advice = ("策略倾向：<span class='warn'>观望为主</span>。多空力量分歧，趋势缺乏，"
                  "可在通道上下轨之间做高抛低吸的区间操作，或暂时空仓等待方向选择。")
    paragraphs.append(f"<p><b>执行建议：</b>{advice}</p>")

    paragraphs.append(
        "<p style='color:var(--text-mute);font-size:12px;margin-top:14px;border-top:1px dashed var(--border);padding-top:10px'>"
        "声明：本节由价格行为引擎与艾略特波浪引擎双重判断自动综合生成，仅供研究参考，不构成投资建议。"
        "实战需结合宏观背景、成交量、动量背离及风控规则。</p>"
    )

    # 关键数据卡
    keypoints = []
    keypoints.append(f"<div class='mo-kp'><div class='lbl'>当前价</div><div class='val gold'>{current_price:.2f}</div></div>")
    keypoints.append(f"<div class='mo-kp'><div class='lbl'>综合方向</div>"
                     f"<div class='val {vc}'>{cls_zh} ({summary['combined']:+d})</div></div>")
    # 主计数作废价
    if main_key and ew_results[main_key][1] and ew_results[main_key][1].invalidation is not None:
        inv = ew_results[main_key][1].invalidation
        keypoints.append(f"<div class='mo-kp'><div class='lbl'>主计数作废价</div>"
                         f"<div class='val bear'>{inv:.2f}</div></div>")
    else:
        keypoints.append(f"<div class='mo-kp'><div class='lbl'>主计数作废价</div><div class='val'>—</div></div>")

    return f"""
    <div class="market-overview">
      <h2>综合行情分析 · Market Overview</h2>
      {''.join(paragraphs)}
      <div class="mo-keypoints">{''.join(keypoints)}</div>
    </div>"""


def render_fusion_html(pa_results: Dict, ew_results: Dict, pa_charts: Dict, ew_charts: Dict,
                       data: Dict, source: str) -> str:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    current_price = 0.0
    for k in ("m15", "h1", "h4", "daily"):
        if k in data and data[k] is not None and not data[k].empty:
            current_price = float(data[k]["Close"].iloc[-1])
            break

    summary = cross_engine_summary(pa_results, ew_results, current_price)
    verdict_html = _verdict_card(summary)
    overview_html = _build_market_overview(pa_results, ew_results, summary, current_price)

    # 各周期双栏
    tf_blocks = []
    for key, label in [("daily", "日线"), ("h4", "H4"), ("h1", "H1"), ("m15", "M15")]:
        df = data.get(key)
        if df is None or df.empty:
            continue
        tf_blocks.append(_render_dual_tf(
            label,
            pa_results.get(key),
            ew_results.get(key),
            pa_charts.get(key, ""),
            ew_charts.get(key, ""),
            df,
        ))

    # 艾略特总体叙述（沿用 elliott_wave 的 narrative）
    ew_for_narr = {k: (v[0], v[1], v[2]) for k, v in ew_results.items() if v is not None}
    narrative = build_elliott_narrative(ew_for_narr, current_price) if ew_for_narr else \
                "<p>暂无足够数据进行艾略特解读。</p>"

    nav = f"""
    <div class="topbar">
      <div class="brand">PA × ELLIOTT <span>· XAU/USD 双引擎机构融合报告</span></div>
      <div class="topbar-nav">
        <a href="#overview">综合分析</a>
        <a href="#verdict">双引擎判断</a>
        <a href="#tf-日线">日线</a>
        <a href="#tf-H4">H4</a>
        <a href="#tf-H1">H1</a>
        <a href="#tf-M15">M15</a>
        <a href="#narrative">波浪解读</a>
      </div>
      <div class="ts">{now_str}</div>
    </div>
    """

    body = f"""
    {nav}
    <h1 class="hero">XAU/USD · 价格行为 × 艾略特波浪 · 机构融合报告</h1>
    <div class="hero-sub">
      数据源：<b>{source}</b> &nbsp;|&nbsp; 当前价：<b>{current_price:.2f}</b>
      &nbsp;|&nbsp; 报告时间：<b>{now_str}</b>
    </div>

    <div class="section" id="overview">
      <div class="section-title">I · 综合行情分析</div>
      {overview_html}
    </div>

    <div class="section" id="verdict">
      <div class="section-title">II · 双引擎共振矩阵</div>
      {verdict_html}
    </div>

    <div class="section">
      <div class="section-title">III · 多周期双引擎对照</div>
      {''.join(tf_blocks) or '<div style="color:var(--text-mute);padding:20px">暂无周期数据。</div>'}
    </div>

    <div class="section" id="narrative">
      <div class="section-title">IV · 艾略特波浪综合解读</div>
      <div class="narrative">{narrative}</div>
    </div>

    <div class="footer">
      Fusion Report · Price Action Engine + Elliott Wave Engine<br>
      ZigZag 转折 · 市场结构 · 趋势通道 · BOS / CHoCH · 5 浪 · ABC · 三大铁律 · 斐波那契目标<br>
      仅供研究学习，非投资建议。市场有风险，决策需谨慎。
    </div>
    """

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>XAU/USD · PA × Elliott 融合报告 · {now_str}</title>
<style>{ELLIOTT_CSS}{EXTRA_CSS}</style></head><body>{body}</body></html>"""


# ════════════════════════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════════════════════════

def run_fusion_analysis(fetch_fn=None, report_prefix="fusion", report_subdir="fusion",
                        system_label="MT4 系统", open_browser=True):
    if fetch_fn is None:
        fetch_fn = fetch_data
    print(f"[FUSION] 启动 PA × Elliott 融合分析 · {system_label}")
    data, source = fetch_fn()
    if not data:
        print("[FUSION] 错误：无法获取行情数据")
        return None

    tf_settings = [
        ("daily", "日线", 2.0, 120,  80),
        ("h4",    "H4",   2.0, 150, 100),
        ("h1",    "H1",   1.5, 200, 140),
        ("m15",   "M15",  1.2, 200, 180),
    ]

    pa_results: Dict[str, Dict] = {}
    pa_charts: Dict[str, str] = {}
    ew_results: Dict[str, Tuple[str, Optional[WavePattern], object]] = {}
    ew_charts: Dict[str, str] = {}

    for key, label, atr_mult, lookback, last_n in tf_settings:
        df = data.get(key)
        if df is None or df.empty or len(df) < 30:
            continue
        # PA 引擎
        try:
            pa = analyze_pa(df, label, atr_mult=atr_mult, lookback_bars=lookback)
            pa_results[key] = pa
            if "error" not in pa:
                pa_charts[key] = render_pa_chart_b64(df, pa, label, last_n=last_n) or ""
                ch = pa["channel"]
                print(f"  [PA] {label}: {pa['structure']['trend']}; 通道 {ch['direction'] if ch else 'N/A'}")
        except Exception as e:
            print(f"  [PA] {label} 失败: {e}")

        # Elliott 引擎
        try:
            pivots = detect_zigzag(df, atr_mult=atr_mult, min_bars=3)
            pat = detect_wave_pattern(pivots, df)
            ew_results[key] = (label, pat, df)
            ew_charts[key] = render_wave_chart_b64(df, pat, label, last_n=last_n) or ""
            if pat:
                print(f"  [EW] {label}: {pat.direction} W{pat.completeness}/5 · {pat.state}")
            else:
                print(f"  [EW] {label}: 未识别有效形态")
        except Exception as e:
            print(f"  [EW] {label} 失败: {e}")

    html = render_fusion_html(pa_results, ew_results, pa_charts, ew_charts, data, source)

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out_dir = os.path.join(REPORT_DIR, report_subdir) if report_subdir else REPORT_DIR
    os.makedirs(out_dir, exist_ok=True)
    report_path = os.path.join(out_dir, f"{report_prefix}_{ts}.html")
    latest_path = os.path.join(out_dir, f"{report_prefix}_latest.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[FUSION] 报告已生成: {report_path}")
    print(f"[FUSION] 最新报告: {latest_path}")
    if open_browser:
        try:
            os.startfile(latest_path)
        except Exception:
            webbrowser.open(f"file:///{latest_path.replace(os.sep, '/')}")
    return latest_path


def main():
    """MT4 系统入口（数据回退链：MT4 CSV → Yahoo）"""
    return run_fusion_analysis(fetch_fn=fetch_data,
                               report_prefix="fusion",
                               report_subdir="fusion",
                               system_label="MT4 系统")


if __name__ == "__main__":
    main()
