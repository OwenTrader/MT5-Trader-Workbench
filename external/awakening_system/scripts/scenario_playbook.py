# -*- coding: utf-8 -*-
"""
黄金 · 场景化交易剧本（Scenario Playbook）
====================================================================
独立入口，与已有所有报告完全解耦。
专注于：纯行情分析 + 具体场景演练 + 决策树式引导。

报告组成
  · 一、当前态势            — 一句话定位 + 关键参数
  · 二、关键价位地图        — 上下方支撑阻力分级表
  · 三、场景推演决策树      — 上行 / 下行 / 震荡 三大主场景，每个含分叉与失效条件
  · 四、当下操作清单        — 进场前必看的几条规则
  · 五、关键时间窗口        — 盘段切换提示

逻辑一致性原则
  · 所有场景共享同一组关键价位与同一组 ATR
  · 主趋势作为锚定方向，主场景概率最高，反向场景仅作为对冲应对
  · 失效条件必须互斥：场景 A 的失效条件 = 场景 B 的触发条件
"""

import os
import sys
import webbrowser
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(__file__))
from gold_analysis import fetch_data, atr, REPORT_DIR
from wave_analysis import detect_zigzag, analyze_market_structure, detect_bos_choch
from smc_snapshot import (detect_order_blocks, detect_fvgs, detect_liquidity,
                          OrderBlock, FVG, LiquidityZone)


# ════════════════════════════════════════════════════════════════════
# 关键价位地图
# ════════════════════════════════════════════════════════════════════

def build_level_map(htf_obs, htf_fvgs, htf_liq, ltf_obs, ltf_liq, current_price: float) -> Dict:
    """
    汇总上下方关键价位，按距离当前价排序。
    返回结构：
      {
        "above": [{"price": 4720.5, "kind": "空头订单块", "weight": 3, "note": "..."}, ...],
        "below": [{"price": 4660.0, "kind": "多头订单块", "weight": 3, "note": "..."}, ...],
      }
    weight: 权重越大，价位越关键（订单块 3，流动性池 2.5，FVG 2，前高前低 1.5）
    """
    above: List[Dict] = []
    below: List[Dict] = []

    def push(target: List[Dict], price: float, kind: str, weight: float, note: str):
        # 去重：与已有价位差距小于 1 美元的合并
        for x in target:
            if abs(x["price"] - price) < 1.0:
                if weight > x["weight"]:
                    x.update(price=price, kind=kind, weight=weight, note=note)
                return
        target.append({"price": float(price), "kind": kind, "weight": weight, "note": note})

    # 订单块（取大周期未触发的优先）
    for ob in htf_obs + ltf_obs:
        if ob.mitigated:
            continue
        mid = (ob.high + ob.low) / 2
        if ob.side == "demand" and ob.high < current_price:
            push(below, ob.high, "多头订单块上沿",
                 3.0, f"机构买盘吸筹区，区间 ${ob.low:.1f} ~ ${ob.high:.1f}")
        elif ob.side == "supply" and ob.low > current_price:
            push(above, ob.low, "空头订单块下沿",
                 3.0, f"机构卖盘压制区，区间 ${ob.low:.1f} ~ ${ob.high:.1f}")

    # 流动性池
    for z in htf_liq + ltf_liq:
        if z.swept:
            continue
        if z.side == "BSL" and z.price > current_price:
            push(above, z.price, "上方流动性池", 2.5,
                 "前期高点聚集，机构常先扫损此处再做方向选择")
        elif z.side == "SSL" and z.price < current_price:
            push(below, z.price, "下方流动性池", 2.5,
                 "前期低点聚集，机构常先扫损此处再做方向选择")

    # FVG
    for f in htf_fvgs:
        if f.mitigated:
            continue
        mid = (f.top + f.bottom) / 2
        if f.side == "bullish" and f.top < current_price:
            push(below, f.top, "看涨失衡缺口上沿", 2.0,
                 f"未回补区间 ${f.bottom:.1f} ~ ${f.top:.1f}，多头磁吸")
        elif f.side == "bearish" and f.bottom > current_price:
            push(above, f.bottom, "看跌失衡缺口下沿", 2.0,
                 f"未回补区间 ${f.bottom:.1f} ~ ${f.top:.1f}，空头磁吸")

    # 排序：按距离当前价
    above.sort(key=lambda x: x["price"] - current_price)
    below.sort(key=lambda x: current_price - x["price"])
    return {"above": above[:5], "below": below[:5]}


# ════════════════════════════════════════════════════════════════════
# 场景推演引擎
# ════════════════════════════════════════════════════════════════════

def build_scenarios(htf: Dict, ltf: Dict, level_map: Dict, current_price: float) -> List[Dict]:
    """
    依据大周期偏向构造三大主场景：上行 / 下行 / 震荡。
    每个场景含：
      - prob: 概率权重（0~100）
      - trigger: 触发条件
      - first_target / second_target: 两段目标
      - branch_a / branch_b: 到达第一目标后的两种分叉走法
      - entry / stop / size: 进场参考 / 止损 / 仓位建议
      - invalidation: 场景失效条件（同时是反向场景的触发条件）
    """
    htf_cls = htf["structure"]["trend_cls"]
    atr_ltf = ltf.get("atr", 0) or 1.0
    atr_htf = htf.get("atr", 0) or atr_ltf

    above = level_map["above"]
    below = level_map["below"]

    # 概率分配：以大周期偏向为锚，主方向 50%，反方向 25%，震荡 25%
    if htf_cls == "bull":
        prob = {"up": 50, "down": 25, "range": 25}
    elif htf_cls == "bear":
        prob = {"up": 25, "down": 50, "range": 25}
    else:
        prob = {"up": 30, "down": 30, "range": 40}

    scenarios: List[Dict] = []

    # ═══════════ 场景一：上行突破 ═══════════
    if above:
        lvl1 = above[0]                       # 第一阻力
        lvl2 = above[1] if len(above) > 1 else None  # 第二阻力
        trigger = (f"价格站稳并收盘于 <b>{lvl1['kind']} ${lvl1['price']:.1f}</b> 上方"
                   f"（建议以小周期连续两根收盘突破为确认条件）")
        first_tgt = lvl1["price"]
        second_tgt = lvl2["price"] if lvl2 else lvl1["price"] + 2 * atr_htf

        # 分叉
        branch_a = {
            "title": "分叉 A · 受阻回落",
            "condition": f"价格触及第一目标 <b>${first_tgt:.1f}</b> 后出现拒绝信号"
                         f"（如长上影、连续两根反向 K 线、上方流动性被扫损后回落）",
            "action": (f"立即将 50% 仓位止盈离场，剩余仓位上移止损至成本价；"
                       f"若小周期形成结构转换向下信号，则全部止盈，"
                       f"考虑反手轻仓做空回踩 <b>${first_tgt - atr_ltf:.1f}</b>。"),
        }
        branch_b = {
            "title": "分叉 B · 顺势加速",
            "condition": f"价格突破 <b>${first_tgt:.1f}</b> 且回踩不破，"
                         f"小周期出现新的多头订单块或失衡缺口",
            "action": (f"剩余仓位继续持有，加仓 1/3 单位（仓位上限不超过初始 1.5 倍），"
                       f"目标看向第二阻力 <b>${second_tgt:.1f}</b>，止损上移至第一目标下方。"),
        }

        # 进场参考
        entry_zone_low = lvl1["price"]
        entry_zone_high = lvl1["price"] + 0.5 * atr_ltf
        sl = lvl1["price"] - 1.2 * atr_ltf
        invalidation = below[0]["price"] if below else current_price - 2 * atr_htf

        scenarios.append({
            "key": "up",
            "side": "bull",
            "title": "场景一 · 上行突破",
            "prob": prob["up"],
            "summary": f"价格突破上方 <b>{lvl1['kind']}</b> 后向上方流动性池发起进攻",
            "trigger": trigger,
            "first_target": f"${first_tgt:.1f}（{lvl1['kind']}）",
            "second_target": f"${second_tgt:.1f}" + (f"（{lvl2['kind']}）" if lvl2 else "（按 ATR 投影）"),
            "branch_a": branch_a,
            "branch_b": branch_b,
            "entry": f"突破后回踩 <b>${entry_zone_low:.1f} ~ ${entry_zone_high:.1f}</b> 区间不破即进场",
            "stop": f"硬止损 <b>${sl:.1f}</b>（突破价下方 1.2 倍小周期 ATR）",
            "size": "建议总风险敞口 0.5%；若小周期与大周期共振向上，可放大至 1%",
            "invalidation": f"价格收盘于 <b>${invalidation:.1f}</b> 下方 → 上行场景作废，自动进入下行场景",
        })

    # ═══════════ 场景二：下行突破 ═══════════
    if below:
        lvl1 = below[0]
        lvl2 = below[1] if len(below) > 1 else None
        trigger = (f"价格跌破并收盘于 <b>{lvl1['kind']} ${lvl1['price']:.1f}</b> 下方"
                   f"（建议以小周期连续两根收盘破位为确认条件）")
        first_tgt = lvl1["price"]
        second_tgt = lvl2["price"] if lvl2 else lvl1["price"] - 2 * atr_htf

        branch_a = {
            "title": "分叉 A · 受撑反弹",
            "condition": f"价格触及第一目标 <b>${first_tgt:.1f}</b> 后出现拒绝信号"
                         f"（如长下影、连续两根反向 K 线、下方流动性被扫损后反弹）",
            "action": (f"立即将 50% 仓位止盈离场，剩余仓位下移止损至成本价；"
                       f"若小周期形成结构转换向上信号，则全部止盈，"
                       f"考虑反手轻仓做多反弹至 <b>${first_tgt + atr_ltf:.1f}</b>。"),
        }
        branch_b = {
            "title": "分叉 B · 顺势加速",
            "condition": f"价格跌破 <b>${first_tgt:.1f}</b> 且反弹不上，"
                         f"小周期出现新的空头订单块或失衡缺口",
            "action": (f"剩余仓位继续持有，加仓 1/3 单位（仓位上限不超过初始 1.5 倍），"
                       f"目标看向第二支撑 <b>${second_tgt:.1f}</b>，止损下移至第一目标上方。"),
        }

        entry_zone_high = lvl1["price"]
        entry_zone_low = lvl1["price"] - 0.5 * atr_ltf
        sl = lvl1["price"] + 1.2 * atr_ltf
        invalidation = above[0]["price"] if above else current_price + 2 * atr_htf

        scenarios.append({
            "key": "down",
            "side": "bear",
            "title": "场景二 · 下行突破",
            "prob": prob["down"],
            "summary": f"价格跌破下方 <b>{lvl1['kind']}</b> 后向下方流动性池继续扩张",
            "trigger": trigger,
            "first_target": f"${first_tgt:.1f}（{lvl1['kind']}）",
            "second_target": f"${second_tgt:.1f}" + (f"（{lvl2['kind']}）" if lvl2 else "（按 ATR 投影）"),
            "branch_a": branch_a,
            "branch_b": branch_b,
            "entry": f"破位后反抽 <b>${entry_zone_low:.1f} ~ ${entry_zone_high:.1f}</b> 区间不上即进场",
            "stop": f"硬止损 <b>${sl:.1f}</b>（破位价上方 1.2 倍小周期 ATR）",
            "size": "建议总风险敞口 0.5%；若小周期与大周期共振向下，可放大至 1%",
            "invalidation": f"价格收盘于 <b>${invalidation:.1f}</b> 上方 → 下行场景作废，自动进入上行场景",
        })

    # ═══════════ 场景三：区间震荡 ═══════════
    if above and below:
        top = above[0]["price"]
        bot = below[0]["price"]
        scenarios.append({
            "key": "range",
            "side": "warn",
            "title": "场景三 · 区间震荡",
            "prob": prob["range"],
            "summary": f"价格在 <b>${bot:.1f} ~ ${top:.1f}</b> 区间反复试探，等待方向选择",
            "trigger": (f"价格未能突破 <b>${top:.1f}</b>，也未能跌破 <b>${bot:.1f}</b>，"
                        f"小周期形成 4 小时以上的横盘整理"),
            "first_target": f"区间上沿 ${top:.1f}",
            "second_target": f"区间下沿 ${bot:.1f}",
            "branch_a": {
                "title": "分叉 A · 高抛低吸",
                "condition": "价格连续两次在区间边界出现拒绝信号",
                "action": (f"边界做反向，止损放在边界外 0.5 倍 ATR 处，"
                           f"目标看向区间中线 <b>${(top + bot) / 2:.1f}</b>，"
                           f"仓位减半为 0.25%。"),
            },
            "branch_b": {
                "title": "分叉 B · 突破方向",
                "condition": "区间任一边出现强势突破并伴随成交量放大",
                "action": "立即转入场景一或场景二的破位跟随策略，区间内的反向单全部清仓。",
            },
            "entry": "区间边界拒绝信号确认后进场（如锤子线 / 吞没形态 / 流动性扫损反转）",
            "stop": "硬止损：边界外 0.5 ~ 0.8 倍小周期 ATR",
            "size": "震荡行情仓位减半，单笔风险 0.25%，避免被假突破连续止损",
            "invalidation": (f"价格收盘突破 <b>${top:.1f}</b> 或 <b>${bot:.1f}</b> "
                              f"→ 震荡场景作废，自动进入对应方向的破位场景"),
        })

    # ═══════════ 场景四：诱多 / 诱空陷阱（加分项） ═══════════
    # 检查最近是否有流动性扫损（一旦被扫，常常出现假突破后反转）
    swept = [z for z in htf["liquidity"] + ltf["liquidity"] if z.swept]
    if swept:
        z = swept[0]
        if z.side == "BSL":
            scenarios.append({
                "key": "trap",
                "side": "warn",
                "title": "场景四 · 诱多陷阱（已就位）",
                "prob": 35,
                "summary": (f"上方流动性池 <b>${z.price:.1f}</b> 已被扫损，"
                            f"机构很可能完成顶部建仓，价格存在反转下行的概率"),
                "trigger": "扫损后 1 ~ 3 根小周期 K 线出现拒绝形态（长上影、吞没、连续阴线）",
                "first_target": f"扫损起点回撤 50% 的位置 ${z.price - 1.5 * atr_ltf:.1f}",
                "second_target": f"下方最近订单块或流动池 ${below[0]['price']:.1f}" if below else "—",
                "branch_a": {
                    "title": "分叉 A · 反转确认",
                    "condition": "扫损后 1 小时内价格未能再次突破扫损高点",
                    "action": "果断空单介入，止损放在扫损高点上方 0.3 倍 ATR 处，目标第一支撑。",
                },
                "branch_b": {
                    "title": "分叉 B · 真突破",
                    "condition": "扫损后价格再次冲高并站稳扫损高点",
                    "action": "立即放弃做空想法，扫损被证伪，转为关注场景一。",
                },
                "entry": f"建议在 <b>${z.price - 0.3 * atr_ltf:.1f} ~ ${z.price:.1f}</b> 区间挂空单",
                "stop": f"硬止损 <b>${z.price + 0.3 * atr_ltf:.1f}</b>",
                "size": "仓位 0.5%，反转交易盈亏比可达 1:3 以上",
                "invalidation": f"价格站稳 <b>${z.price:.1f}</b> 上方 → 诱多陷阱不成立",
            })
        elif z.side == "SSL":
            scenarios.append({
                "key": "trap",
                "side": "warn",
                "title": "场景四 · 诱空陷阱（已就位）",
                "prob": 35,
                "summary": (f"下方流动性池 <b>${z.price:.1f}</b> 已被扫损，"
                            f"机构很可能完成底部建仓，价格存在反转上行的概率"),
                "trigger": "扫损后 1 ~ 3 根小周期 K 线出现拒绝形态（长下影、吞没、连续阳线）",
                "first_target": f"扫损起点回撤 50% 的位置 ${z.price + 1.5 * atr_ltf:.1f}",
                "second_target": f"上方最近订单块或流动池 ${above[0]['price']:.1f}" if above else "—",
                "branch_a": {
                    "title": "分叉 A · 反转确认",
                    "condition": "扫损后 1 小时内价格未能再次跌破扫损低点",
                    "action": "果断多单介入，止损放在扫损低点下方 0.3 倍 ATR 处，目标第一阻力。",
                },
                "branch_b": {
                    "title": "分叉 B · 真破位",
                    "condition": "扫损后价格再次走低并站稳扫损低点下方",
                    "action": "立即放弃做多想法，扫损被证伪，转为关注场景二。",
                },
                "entry": f"建议在 <b>${z.price:.1f} ~ ${z.price + 0.3 * atr_ltf:.1f}</b> 区间挂多单",
                "stop": f"硬止损 <b>${z.price - 0.3 * atr_ltf:.1f}</b>",
                "size": "仓位 0.5%，反转交易盈亏比可达 1:3 以上",
                "invalidation": f"价格站稳 <b>${z.price:.1f}</b> 下方 → 诱空陷阱不成立",
            })

    return scenarios


# ════════════════════════════════════════════════════════════════════
# 当下操作清单 + 时间窗口
# ════════════════════════════════════════════════════════════════════

def build_action_checklist(htf: Dict, ltf: Dict, level_map: Dict, current_price: float) -> List[str]:
    htf_cls = htf["structure"]["trend_cls"]
    above = level_map["above"]
    below = level_map["below"]
    items = []

    # 第 1 条：当前应监控的关键价位
    watch = []
    if above:
        watch.append(f"上方 <b>${above[0]['price']:.1f}</b>（{above[0]['kind']}）")
    if below:
        watch.append(f"下方 <b>${below[0]['price']:.1f}</b>（{below[0]['kind']}）")
    if watch:
        items.append("立即将 " + "、".join(watch) + " 设为提醒价位，价格触及任一处即进入交易准备状态")

    # 第 2 条：进场前必看的 3 个信号
    items.append("进场前必看的三个确认信号："
                  "①小周期收盘突破或收盘破位；"
                  "②突破后回踩或反抽不再越过关键位；"
                  "③回踩反抽时出现明确的拒绝 K 线形态（长影线、吞没、双针等）")

    # 第 3 条：仓位与盈亏比
    items.append("单笔交易风险敞口控制在账户净值 0.5% 至 1%，"
                  "进场前必须先算清楚硬止损价位与目标位之间的盈亏比，"
                  "<b>不达 1:2 的机会一律放弃</b>")

    # 第 4 条：情绪管理
    items.append("若连续两次止损，立即停止交易并复盘 30 分钟以上；"
                  "若连续盈利情绪高涨，强制减仓 50% 后再进入下一笔")

    # 第 5 条：方向偏好
    if htf_cls == "bull":
        items.append("当前大周期偏多，<b>优先做多</b>；空单仅作为对冲应对，仓位减半，"
                      "盈亏比目标 1:3 以上方可考虑")
    elif htf_cls == "bear":
        items.append("当前大周期偏空，<b>优先做空</b>；多单仅作为对冲应对，仓位减半，"
                      "盈亏比目标 1:3 以上方可考虑")
    else:
        items.append("当前大周期方向不明，建议<b>仅做区间高抛低吸</b>，"
                      "仓位整体减半，等待大周期出现新的结构突破后再调整偏好")

    return items


def build_time_windows() -> List[Dict]:
    """中国时区主要交易时段提示。"""
    return [
        {"name": "亚盘开盘", "time": "09:00 ~ 11:30", "note": "成交清淡，多以延续昨日尾盘方向为主，不建议主动交易"},
        {"name": "欧盘开盘", "time": "15:00 ~ 17:00", "note": "波动放大，常出现日内方向选择，是关键观察窗口"},
        {"name": "美盘开盘", "time": "20:30 ~ 22:30", "note": "黄金最活跃时段，方向选择常在此完成，重点交易窗口"},
        {"name": "美盘尾盘", "time": "次日 02:00 ~ 04:00", "note": "流动性下降，假突破频发，建议避免重仓"},
    ]


# ════════════════════════════════════════════════════════════════════
# HTML 渲染
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
     font-size:13px;line-height:1.8;max-width:1280px;margin:0 auto;padding:24px}
.brand{font-size:11px;color:var(--gold-dim);letter-spacing:3px;margin-bottom:6px}
h1{font-size:26px;font-weight:800;letter-spacing:1px;margin-bottom:6px;
   background:linear-gradient(90deg,#fff,#d9b85c);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.subline{color:var(--text-dim);font-size:12.5px;margin-bottom:24px;font-family:var(--mono)}
.subline b{color:var(--gold)}

.section{margin-top:30px}
.section-title{font-size:14px;font-weight:700;color:var(--gold);
        letter-spacing:1.5px;padding-bottom:8px;margin-bottom:14px;
        border-bottom:1px solid var(--border-gold)}
.section-title small{font-size:11.5px;color:var(--text-mute);font-weight:400;
        letter-spacing:1px;margin-left:8px}

/* 当前态势 */
.stance{padding:20px 24px;background:linear-gradient(135deg,#0a0a14 0%,#101019 100%);
        border:1px solid var(--border-gold);border-radius:10px;margin-bottom:18px;line-height:1.95}
.stance .label{font-size:10.5px;color:var(--gold-dim);letter-spacing:2px;margin-bottom:8px}
.stance .text{font-size:14px;color:var(--text);font-weight:500}
.stance .text b{color:var(--gold)}
.stance .params{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:14px}
@media(max-width:900px){.stance .params{grid-template-columns:repeat(2,1fr)}}
.stance .param{background:var(--bg2);padding:10px 12px;border-radius:6px;border:1px solid var(--border)}
.stance .param .k{font-size:10.5px;color:var(--text-mute);letter-spacing:1px;margin-bottom:4px}
.stance .param .v{font-family:var(--mono);font-size:14px;font-weight:700;color:var(--text)}
.stance .param .v.bull{color:var(--bull)} .stance .param .v.bear{color:var(--bear)} .stance .param .v.gold{color:var(--gold)}

/* 关键价位地图 */
.level-map{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:900px){.level-map{grid-template-columns:1fr}}
.level-col{background:var(--bg1);border:1px solid var(--border);border-radius:8px;padding:14px 16px}
.level-col.above{border-left:3px solid var(--bear)}
.level-col.below{border-left:3px solid var(--bull)}
.level-col h3{font-size:12px;color:var(--gold-dim);letter-spacing:1.5px;margin-bottom:10px;padding-bottom:6px;border-bottom:1px dashed var(--border)}
.level-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px dashed var(--border);font-size:12.5px}
.level-row:last-child{border-bottom:none}
.level-row .lv-info{flex:1}
.level-row .lv-kind{color:var(--text);font-weight:600}
.level-row .lv-note{color:var(--text-mute);font-size:11px;margin-top:2px}
.level-row .lv-price{font-family:var(--mono);font-weight:700;font-size:14px;margin-left:10px;flex-shrink:0}
.level-row .lv-price.bear{color:var(--bear)} .level-row .lv-price.bull{color:var(--bull)}
.level-row .stars{font-size:10px;color:var(--gold);margin-left:6px}
.cur-price-bar{padding:10px 14px;background:rgba(217,184,92,0.08);border:1px dashed var(--gold);
        border-radius:6px;margin:14px 0;text-align:center;font-family:var(--mono);
        color:var(--gold);font-weight:700;font-size:14px}

/* 场景树 */
.scen{background:var(--bg1);border:1px solid var(--border);border-radius:10px;
        padding:20px 22px;margin-bottom:18px;border-left:4px solid var(--gold-dim)}
.scen.bull{border-left-color:var(--bull)}
.scen.bear{border-left-color:var(--bear)}
.scen.warn{border-left-color:var(--warn)}
.scen-head{display:flex;justify-content:space-between;align-items:flex-start;
        margin-bottom:14px;padding-bottom:10px;border-bottom:1px dashed var(--border)}
.scen-head h3{font-size:17px;font-weight:800;letter-spacing:0.5px}
.scen.bull .scen-head h3{color:var(--bull)}
.scen.bear .scen-head h3{color:var(--bear)}
.scen.warn .scen-head h3{color:var(--warn)}
.scen-head .sub{font-size:12px;color:var(--text-dim);margin-top:4px;font-weight:400}
.scen-prob{font-family:var(--mono);font-size:11px;font-weight:700;
        padding:4px 10px;border-radius:4px;flex-shrink:0;margin-left:12px}
.scen.bull .scen-prob{background:rgba(29,223,169,0.15);color:var(--bull);border:1px solid rgba(29,223,169,0.4)}
.scen.bear .scen-prob{background:rgba(255,94,124,0.15);color:var(--bear);border:1px solid rgba(255,94,124,0.4)}
.scen.warn .scen-prob{background:rgba(255,176,102,0.15);color:var(--warn);border:1px solid rgba(255,176,102,0.4)}

.scen-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}
@media(max-width:900px){.scen-grid{grid-template-columns:1fr}}
.scen-block{background:var(--bg2);border:1px solid var(--border);border-radius:7px;padding:12px 14px}
.scen-block h5{font-size:11px;color:var(--text-mute);letter-spacing:1.5px;margin-bottom:8px;font-weight:700}
.scen-block .body{font-size:12.5px;color:var(--text-dim);line-height:1.85}
.scen-block .body b{color:var(--gold)}
.scen-block.target h5{color:var(--gold)}
.scen-block.target .tline{display:flex;justify-content:space-between;padding:5px 0;font-size:12.5px;border-bottom:1px dashed var(--border)}
.scen-block.target .tline:last-child{border-bottom:none}
.scen-block.target .tline .lbl{color:var(--text-mute)}
.scen-block.target .tline .val{font-family:var(--mono);font-weight:700;color:var(--text)}

.branch{padding:12px 14px;margin-top:10px;background:var(--bg2);border:1px solid var(--border);
        border-radius:7px;border-left:3px solid var(--gold-dim)}
.branch h6{font-size:12.5px;color:var(--gold);font-weight:700;margin-bottom:6px;letter-spacing:0.5px}
.branch .b-cond{font-size:12px;color:var(--text-dim);margin-bottom:6px}
.branch .b-cond::before{content:"触发：";color:var(--text-mute);font-weight:600}
.branch .b-act{font-size:12px;color:var(--text)}
.branch .b-act::before{content:"操作：";color:var(--text-mute);font-weight:600}

.exec-row{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px}
@media(max-width:900px){.exec-row{grid-template-columns:1fr}}
.exec-row .e-card{background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:10px 12px;font-size:12px}
.exec-row .e-card .lbl{font-size:10.5px;color:var(--text-mute);letter-spacing:1px;margin-bottom:4px}
.exec-row .e-card .val{color:var(--text);line-height:1.7}
.exec-row .e-card .val b{color:var(--gold)}

.invalid-bar{margin-top:14px;padding:10px 14px;background:rgba(255,94,124,0.07);
        border:1px dashed var(--bear);border-radius:6px;font-size:12px;color:var(--bear);line-height:1.7}
.invalid-bar::before{content:"场景作废条件 ▸ ";font-weight:700;letter-spacing:1px}

/* 操作清单 */
.checklist{counter-reset:cl;display:flex;flex-direction:column;gap:10px}
.cl-item{display:flex;gap:14px;padding:14px 16px;background:var(--bg1);border:1px solid var(--border);
        border-radius:8px;border-left:3px solid var(--gold)}
.cl-item::before{counter-increment:cl;content:counter(cl);
        flex-shrink:0;width:28px;height:28px;border-radius:50%;background:var(--gold);
        color:#0a0a14;font-weight:800;font-size:13px;display:flex;align-items:center;justify-content:center;font-family:var(--mono)}
.cl-item .ct{font-size:13px;line-height:1.85;color:var(--text-dim)}
.cl-item .ct b{color:var(--gold)}

/* 时间窗口 */
.time-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
@media(max-width:900px){.time-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:560px){.time-grid{grid-template-columns:1fr}}
.t-card{background:var(--bg1);border:1px solid var(--border);border-radius:8px;padding:14px 16px}
.t-card .name{font-size:13px;font-weight:700;color:var(--gold);margin-bottom:4px}
.t-card .tm{font-family:var(--mono);font-size:11.5px;color:var(--text);margin-bottom:8px}
.t-card .nt{font-size:11.5px;color:var(--text-mute);line-height:1.7}

.footer{margin-top:36px;padding-top:18px;border-top:1px solid var(--border);
        font-size:11px;color:var(--text-mute);text-align:center;line-height:1.8}
"""


def _stance_text(htf: Dict, ltf: Dict, level_map: Dict, current_price: float) -> str:
    htf_label = htf.get("label", "大周期")
    ltf_label = ltf.get("label", "小周期")
    ht = htf["structure"]["trend"]
    lt = ltf["structure"]["trend"]
    above = level_map["above"]
    below = level_map["below"]

    pieces = [f"当前金价站位 <b>{current_price:.2f}</b>。"]
    pieces.append(f"<b>{htf_label}</b> 周期判断为 <b>{ht}</b>，"
                  f"<b>{ltf_label}</b> 周期判断为 <b>{lt}</b>。")
    if above and below:
        gap_up = above[0]["price"] - current_price
        gap_dn = current_price - below[0]["price"]
        pieces.append(f"上方第一阻力距当前 <b>{gap_up:.1f}</b> 美元，"
                       f"下方第一支撑距当前 <b>{gap_dn:.1f}</b> 美元，"
                       f"价格处于<b>{'上方阻力更近' if gap_up < gap_dn else '下方支撑更近' if gap_dn < gap_up else '上下均衡'}</b>的位置。")
    pieces.append("以下场景推演基于纯价格行为与流动性结构，"
                   "三大主场景互斥且穷尽（任一场景的失效条件等于另一场景的触发条件），"
                   "请按照场景对照实盘走势进行操作选择。")
    return "".join(pieces)


def _render_stance(htf: Dict, ltf: Dict, level_map: Dict, current_price: float) -> str:
    text = _stance_text(htf, ltf, level_map, current_price)
    htf_cls = htf["structure"]["trend_cls"]
    bias_cls = "bull" if htf_cls == "bull" else "bear" if htf_cls == "bear" else "gold"
    bias_text = "偏多" if htf_cls == "bull" else "偏空" if htf_cls == "bear" else "中性"
    atr_ltf = ltf.get("atr", 0) or 0
    above_n = len(level_map["above"]); below_n = len(level_map["below"])

    return f"""<div class="stance">
      <div class="label">当前态势</div>
      <div class="text">{text}</div>
      <div class="params">
        <div class="param"><div class="k">当前价</div><div class="v gold">{current_price:.2f}</div></div>
        <div class="param"><div class="k">大周期偏好</div><div class="v {bias_cls}">{bias_text}</div></div>
        <div class="param"><div class="k">小周期波动率</div><div class="v">${atr_ltf:.2f}</div></div>
        <div class="param"><div class="k">关键价位</div><div class="v">上方 {above_n} · 下方 {below_n}</div></div>
      </div>
    </div>"""


def _render_level_map(level_map: Dict, current_price: float) -> str:
    def render_col(items: List[Dict], side: str) -> str:
        if not items:
            return f'<div class="level-col {side}"><h3>{"上方阻力" if side == "above" else "下方支撑"}</h3><div style="color:var(--text-mute);padding:10px 0">暂无识别到的关键价位</div></div>'
        rows = []
        for i, lv in enumerate(items):
            stars = "★" * int(round(lv["weight"]))
            cls_pri = "bear" if side == "above" else "bull"
            dist = abs(lv["price"] - current_price)
            rows.append(
                f'<div class="level-row">'
                f'<div class="lv-info">'
                f'<div><span class="lv-kind">第 {i+1} 档 · {lv["kind"]}</span><span class="stars">{stars}</span></div>'
                f'<div class="lv-note">{lv["note"]}（距当前价 {dist:.1f} 美元）</div>'
                f'</div>'
                f'<div class="lv-price {cls_pri}">${lv["price"]:.1f}</div>'
                f'</div>'
            )
        title = "上方阻力（按距离排序）" if side == "above" else "下方支撑（按距离排序）"
        return f'<div class="level-col {side}"><h3>{title}</h3>{"".join(rows)}</div>'

    return f"""<div class="level-map">
      {render_col(level_map["above"], "above")}
      {render_col(level_map["below"], "below")}
    </div>
    <div class="cur-price-bar">▼ 当前价 ${current_price:.2f} ▼</div>
    """


def _render_scenario(s: Dict) -> str:
    branches = ""
    for b in (s["branch_a"], s["branch_b"]):
        branches += f"""<div class="branch">
          <h6>{b["title"]}</h6>
          <div class="b-cond">{b["condition"]}</div>
          <div class="b-act">{b["action"]}</div>
        </div>"""

    return f"""<div class="scen {s["side"]}">
      <div class="scen-head">
        <div>
          <h3>{s["title"]}</h3>
          <div class="sub">{s["summary"]}</div>
        </div>
        <div class="scen-prob">概率权重 {s["prob"]}%</div>
      </div>
      <div class="scen-grid">
        <div class="scen-block">
          <h5>触发条件</h5>
          <div class="body">{s["trigger"]}</div>
        </div>
        <div class="scen-block target">
          <h5>目标位</h5>
          <div class="tline"><span class="lbl">第一目标</span><span class="val">{s["first_target"]}</span></div>
          <div class="tline"><span class="lbl">第二目标</span><span class="val">{s["second_target"]}</span></div>
        </div>
      </div>
      <div style="margin-top:14px;font-size:11.5px;color:var(--text-mute);letter-spacing:1.5px;font-weight:700">触及第一目标后的两种分叉</div>
      {branches}
      <div class="exec-row">
        <div class="e-card"><div class="lbl">进场参考</div><div class="val">{s["entry"]}</div></div>
        <div class="e-card"><div class="lbl">止损</div><div class="val">{s["stop"]}</div></div>
        <div class="e-card"><div class="lbl">仓位建议</div><div class="val">{s["size"]}</div></div>
      </div>
      <div class="invalid-bar">{s["invalidation"]}</div>
    </div>"""


def render_playbook_html(htf_label: str, htf: Dict, ltf_label: str, ltf: Dict,
                         level_map: Dict, scenarios: List[Dict],
                         checklist: List[str], time_windows: List[Dict],
                         source: str, current_price: float) -> str:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    stance_html = _render_stance(htf, ltf, level_map, current_price)
    level_html = _render_level_map(level_map, current_price)
    scen_html = "".join(_render_scenario(s) for s in scenarios) or \
                '<div style="color:var(--text-mute);padding:14px">数据不足，未能推演场景。</div>'
    cl_html = "".join(f'<div class="cl-item"><div class="ct">{x}</div></div>' for x in checklist)
    tw_html = "".join(f'<div class="t-card"><div class="name">{t["name"]}</div>'
                       f'<div class="tm">北京时间 {t["time"]}</div>'
                       f'<div class="nt">{t["note"]}</div></div>' for t in time_windows)

    body = f"""
    <div class="brand">黄金 · 场景化交易剧本</div>
    <h1>场景化交易剧本</h1>
    <div class="subline">数据源：<b>{source}</b> &nbsp;|&nbsp; 当前价：<b>{current_price:.2f}</b> &nbsp;|&nbsp; 报告时间：<b>{now_str}</b></div>

    <div class="section">
      <div class="section-title">第一部分 · 当前态势 <small>定位与基础参数</small></div>
      {stance_html}
    </div>

    <div class="section">
      <div class="section-title">第二部分 · 关键价位地图 <small>上下方支撑阻力按距离与权重排序</small></div>
      {level_html}
    </div>

    <div class="section">
      <div class="section-title">第三部分 · 场景推演决策树 <small>三大主场景互斥且穷尽，每个含两条分叉路径</small></div>
      {scen_html}
    </div>

    <div class="section">
      <div class="section-title">第四部分 · 当下操作清单 <small>进场前的强制规则</small></div>
      <div class="checklist">{cl_html}</div>
    </div>

    <div class="section">
      <div class="section-title">第五部分 · 关键时间窗口 <small>北京时间盘段切换提示</small></div>
      <div class="time-grid">{tw_html}</div>
    </div>

    <div class="footer">
      场景化交易剧本 · 基于价格行为与流动性结构 · 决策树式分支推演<br>
      所有场景共享同一组关键价位与同一组波动率，互斥且穷尽，逻辑前后一致<br>
      本报告仅供研究学习，不构成投资建议。市场有风险，决策需谨慎。
    </div>
    """

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>黄金 · 场景化交易剧本 · {now_str}</title>
<style>{CSS}</style></head><body>{body}</body></html>"""


# ════════════════════════════════════════════════════════════════════
# 单周期 SMC 数据收集
# ════════════════════════════════════════════════════════════════════

def collect_tf(df, label: str, atr_mult_zigzag: float = 2.0) -> Dict:
    if df is None or df.empty or len(df) < 50:
        return {"label": label, "error": "数据不足"}
    pivots = detect_zigzag(df, atr_mult=atr_mult_zigzag, min_bars=3)
    structure = analyze_market_structure(pivots)
    cur = float(df["Close"].iloc[-1])
    bos_events = detect_bos_choch(pivots, cur, structure)
    return {
        "label": label,
        "current_price": cur,
        "structure": structure,
        "bos_events": bos_events,
        "order_blocks": detect_order_blocks(df),
        "fvgs": detect_fvgs(df),
        "liquidity": detect_liquidity(df, pivots),
        "atr": float(atr(df["High"], df["Low"], df["Close"], 14).iloc[-1] or 0),
    }


# ════════════════════════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════════════════════════

def run_playbook(fetch_fn=None, report_prefix="playbook", report_subdir="playbook",
                 system_label="MT4 系统",
                 htf_key="h4", htf_label="H4",
                 ltf_key="m15", ltf_label="M15",
                 open_browser=True):
    if fetch_fn is None:
        fetch_fn = fetch_data
    print(f"[剧本] 启动场景化推演 · {system_label}")
    data, source = fetch_fn()
    if not data:
        print("[剧本] 错误：无法获取行情数据")
        return None

    htf_df = data.get(htf_key)
    ltf_df = data.get(ltf_key)

    htf_info = collect_tf(htf_df, htf_label, atr_mult_zigzag=2.0) if htf_df is not None else {"label": htf_label, "error": "数据不足"}
    ltf_info = collect_tf(ltf_df, ltf_label, atr_mult_zigzag=1.2) if ltf_df is not None else {"label": ltf_label, "error": "数据不足"}

    if "error" in htf_info or "error" in ltf_info:
        print("[剧本] 错误：周期数据不足，无法生成剧本")
        return None

    current_price = ltf_info["current_price"]
    level_map = build_level_map(
        htf_info["order_blocks"], htf_info["fvgs"], htf_info["liquidity"],
        ltf_info["order_blocks"], ltf_info["liquidity"],
        current_price,
    )
    scenarios = build_scenarios(htf_info, ltf_info, level_map, current_price)
    checklist = build_action_checklist(htf_info, ltf_info, level_map, current_price)
    time_windows = build_time_windows()

    print(f"  [关键价位] 上方 {len(level_map['above'])} 处 · 下方 {len(level_map['below'])} 处")
    print(f"  [场景] 共生成 {len(scenarios)} 个推演场景")
    for s in scenarios:
        print(f"    - {s['title']}（概率权重 {s['prob']}%）")

    html = render_playbook_html(htf_label, htf_info, ltf_label, ltf_info,
                                  level_map, scenarios, checklist, time_windows,
                                  source, current_price)

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out_dir = os.path.join(REPORT_DIR, report_subdir) if report_subdir else REPORT_DIR
    os.makedirs(out_dir, exist_ok=True)
    report_path = os.path.join(out_dir, f"{report_prefix}_{ts}.html")
    latest_path = os.path.join(out_dir, f"{report_prefix}_latest.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[剧本] 报告已生成：{report_path}")
    print(f"[剧本] 最新报告：{latest_path}")
    if open_browser:
        try:
            os.startfile(latest_path)
        except Exception:
            webbrowser.open(f"file:///{latest_path.replace(os.sep, '/')}")
    return latest_path


def main():
    return run_playbook(fetch_fn=fetch_data,
                        report_prefix="playbook",
                        report_subdir="playbook",
                        system_label="MT4 系统")


if __name__ == "__main__":
    main()
