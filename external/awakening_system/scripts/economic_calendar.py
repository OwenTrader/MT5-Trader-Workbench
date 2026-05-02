# -*- coding: utf-8 -*-
"""
经济日历抓取器 · 黄金交易相关
================================
双源策略（按以下顺序尝试，任何一个成功即返回）：
  1. 金十数据 jin10.com   ─ 中文事件名优先，国内访问快
  2. ForexFactory faireconomy JSON ─ 英文兜底，最稳定

输出格式（与 institutional_render.MACRO_CONFIG.calendar 一致）：
    [{"time": "MM-DD HH:MM", "name": "中文事件名", "impact": "high|medium|low"}, ...]

特性：
  - 1 小时本地缓存（reports/.cache/calendar.json），避免每次跑都打外网
  - 自动按重要度过滤（默认 high + medium）
  - 自动按国家过滤（默认 US + EU + CN，对黄金影响最大）
  - 自动翻译 FF 英文事件名到中文（覆盖 60+ 高频事件）
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

try:
    import requests
except ImportError:
    requests = None

# ─────────────────────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────────────────────
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "reports", ".cache")
CACHE_FILE = os.path.join(CACHE_DIR, "calendar.json")
CACHE_TTL_SEC = 60 * 60  # 1 小时

# 只保留美国（对黄金影响最直接，数据/新闻最权威）
GOLD_RELEVANT_CCY = {"USD"}
# 金十的 country_id → 货币代码
JIN10_COUNTRY_MAP = {
    "美国": "USD", "欧元区": "EUR", "中国": "CNY", "英国": "GBP", "日本": "JPY",
    "德国": "EUR", "法国": "EUR", "意大利": "EUR", "西班牙": "EUR",
    "加拿大": "CAD", "澳大利亚": "AUD", "新西兰": "NZD", "瑞士": "CHF",
}

# FF 英文事件名 → 中文翻译表（黄金相关高频事件，130+）
FF_CN_MAP = {
    # ─── 美国：就业 ───
    "Non-Farm Employment Change": "非农就业人数",
    "Nonfarm Payrolls": "非农就业人数",
    "Unemployment Rate": "失业率",
    "Average Hourly Earnings m/m": "平均时薪月率",
    "Average Hourly Earnings": "平均时薪",
    "Labor Force Participation Rate": "劳动参与率",
    "Unemployment Claims": "初请失业金人数",
    "Continuing Jobless Claims": "续请失业金人数",
    "ADP Non-Farm Employment Change": "ADP 就业人数",
    "JOLTS Job Openings": "JOLTS 职位空缺",
    "Challenger Job Cuts y/y": "挑战者裁员人数",
    "Employment Cost Index q/q": "雇佣成本指数季率",
    # ─── 美国：通胀 ───
    "CPI m/m": "CPI 月率",
    "CPI y/y": "CPI 年率",
    "Core CPI m/m": "核心 CPI 月率",
    "Core CPI y/y": "核心 CPI 年率",
    "PPI m/m": "PPI 月率",
    "PPI y/y": "PPI 年率",
    "Core PPI m/m": "核心 PPI 月率",
    "Core PPI y/y": "核心 PPI 年率",
    "PCE Price Index m/m": "PCE 物价指数月率",
    "PCE Price Index y/y": "PCE 物价指数年率",
    "Core PCE Price Index m/m": "核心 PCE 物价指数月率",
    "Core PCE Price Index y/y": "核心 PCE 物价指数年率",
    "Import Prices m/m": "进口物价月率",
    "Inflation Expectations": "通胀预期",
    # ─── 美国：增长 ───
    "GDP q/q": "GDP 季率",
    "Advance GDP q/q": "GDP 初值季率",
    "Prelim GDP q/q": "GDP 修正值季率",
    "Final GDP q/q": "GDP 终值季率",
    "GDP Price Index q/q": "GDP 价格指数季率",
    "Advance GDP Price Index q/q": "GDP 价格指数初值",
    "ISM Manufacturing PMI": "ISM 制造业 PMI",
    "ISM Services PMI": "ISM 服务业 PMI",
    "ISM Manufacturing Prices": "ISM 制造业物价",
    "ISM Services Prices": "ISM 服务业物价",
    "Manufacturing PMI": "制造业 PMI",
    "Services PMI": "服务业 PMI",
    "Flash Manufacturing PMI": "Markit 制造业 PMI 初值",
    "Flash Services PMI": "Markit 服务业 PMI 初值",
    "Final Manufacturing PMI": "Markit 制造业 PMI 终值",
    "Final Services PMI": "Markit 服务业 PMI 终值",
    "Chicago PMI": "芝加哥 PMI",
    "Philly Fed Manufacturing Index": "费城联储制造业指数",
    "Empire State Manufacturing Index": "纽约联储制造业指数",
    "Industrial Production m/m": "工业产出月率",
    "Capacity Utilization Rate": "产能利用率",
    "Factory Orders m/m": "工厂订单月率",
    # ─── 美国：消费 / 房地产 ───
    "Retail Sales m/m": "零售销售月率",
    "Core Retail Sales m/m": "核心零售销售月率",
    "CB Consumer Confidence": "谘商会消费者信心",
    "UoM Consumer Sentiment": "密歇根消费者信心",
    "Prelim UoM Consumer Sentiment": "密歇根消费者信心初值",
    "Revised UoM Consumer Sentiment": "密歇根消费者信心终值",
    "Prelim UoM Inflation Expectations": "密歇根通胀预期初值",
    "Building Permits": "营建许可",
    "Housing Starts": "新屋开工",
    "Existing Home Sales": "成屋销售",
    "New Home Sales": "新屋销售",
    "Pending Home Sales m/m": "成屋签约销售月率",
    "S&P/CS Composite-20 HPI y/y": "S&P/CS 20 城房价指数年率",
    "HPI m/m": "FHFA 房价指数月率",
    "Durable Goods Orders m/m": "耐用品订单月率",
    "Core Durable Goods Orders m/m": "核心耐用品订单月率",
    # ─── 美国：联储 / 政策 ───
    "Federal Funds Rate": "美联储利率决议",
    "FOMC Statement": "FOMC 声明",
    "FOMC Press Conference": "FOMC 新闻发布会",
    "FOMC Meeting Minutes": "FOMC 会议纪要",
    "FOMC Economic Projections": "FOMC 经济预测",
    "Fed Chair Powell Speaks": "鲍威尔讲话",
    "Fed Chair Powell Testifies": "鲍威尔国会作证",
    "Treasury Sec Yellen Speaks": "耶伦讲话",
    "President Trump Speaks": "特朗普讲话",
    "President Biden Speaks": "拜登讲话",
    "10-y Bond Auction": "10 年期国债拍卖",
    "30-y Bond Auction": "30 年期国债拍卖",
    "Beige Book": "美联储褐皮书",
    # ─── 美国：贸易 / 其他 ───
    "Trade Balance": "贸易帐",
    "Crude Oil Inventories": "EIA 原油库存",
    "Natural Gas Storage": "天然气库存",
    "Personal Income m/m": "个人收入月率",
    "Personal Spending m/m": "个人支出月率",
    "Wholesale Inventories m/m": "批发库存月率",
    "Business Inventories m/m": "商业库存月率",
    "Consumer Credit m/m": "消费信贷月率",

    # ─── 欧元区 ───
    "Main Refinancing Rate": "欧央行利率决议",
    "ECB Press Conference": "欧央行新闻发布会",
    "ECB Monetary Policy Statement": "欧央行货币政策声明",
    "ECB President Lagarde Speaks": "拉加德讲话",
    "Deposit Facility Rate": "欧央行存款利率",
    "CPI Flash Estimate y/y": "CPI 年率初值",
    "Core CPI Flash Estimate y/y": "核心 CPI 年率初值",
    "German Prelim CPI m/m": "德国 CPI 月率初值",
    "German Final CPI m/m": "德国 CPI 月率终值",
    "German ZEW Economic Sentiment": "德国 ZEW 经济景气",
    "German Ifo Business Climate": "德国 Ifo 商业景气",
    "German Prelim GDP q/q": "德国 GDP 季率初值",
    "German Final GDP q/q": "德国 GDP 季率终值",
    "German Manufacturing PMI": "德国制造业 PMI",
    "German Services PMI": "德国服务业 PMI",
    "German Flash Manufacturing PMI": "德国制造业 PMI 初值",
    "German Flash Services PMI": "德国服务业 PMI 初值",
    "German Retail Sales m/m": "德国零售销售月率",
    "German Unemployment Change": "德国失业人数变化",
    "French Flash Manufacturing PMI": "法国制造业 PMI 初值",
    "French Flash Services PMI": "法国服务业 PMI 初值",
    "Spanish Flash CPI y/y": "西班牙 CPI 年率初值",
    "Italian Prelim CPI m/m": "意大利 CPI 月率初值",
    "Prelim Flash GDP q/q": "GDP 季率初值",

    # ─── 英国 ───
    "Official Bank Rate": "英央行利率决议",
    "BOE Monetary Policy Report": "英央行货币政策报告",
    "Monetary Policy Summary": "英央行货币政策摘要",
    "Monetary Policy Statement": "货币政策声明",
    "MPC Official Bank Rate Votes": "MPC 利率投票",
    "MPC Meeting Minutes": "MPC 会议纪要",
    "BOE Gov Bailey Speaks": "贝利讲话",

    # ─── 日本 ───
    "BOJ Policy Rate": "日本央行利率决议",
    "BOJ Press Conference": "日本央行新闻发布会",
    "BOJ Outlook Report": "日本央行展望报告",
    "BOJ Core CPI y/y": "日本央行核心 CPI 年率",
    "Tokyo Core CPI y/y": "东京核心 CPI 年率",
    "BOJ Gov Ueda Speaks": "植田和男讲话",

    # ─── 中国 ───
    "Manufacturing PMI": "中国制造业 PMI",
    "Non-Manufacturing PMI": "中国非制造业 PMI",
    "Caixin Manufacturing PMI": "财新制造业 PMI",
    "Caixin Services PMI": "财新服务业 PMI",
    "CNY CPI y/y": "中国 CPI 年率",
    "CNY PPI y/y": "中国 PPI 年率",
    "Trade Balance (USD)": "中国贸易帐（美元计）",
}


# ─────────────────────────────────────────────────────────────
# 缓存
# ─────────────────────────────────────────────────────────────
def _load_cache() -> Optional[List[Dict]]:
    try:
        if not os.path.isfile(CACHE_FILE):
            return None
        if time.time() - os.path.getmtime(CACHE_FILE) > CACHE_TTL_SEC:
            return None
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_cache(events: List[Dict]) -> None:
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# 数据源 1：金十 (中文优先)
# ─────────────────────────────────────────────────────────────
def fetch_jin10(days_ahead: int = 7, timeout: int = 8) -> Optional[List[Dict]]:
    """金十经济日历。返回标准格式或 None（失败）。"""
    if requests is None:
        return None
    try:
        # 金十的 calendar 接口（公开），按日期范围批量取
        beijing = timezone(timedelta(hours=8))
        start = datetime.now(beijing).date()
        end = start + timedelta(days=days_ahead)
        url = "https://cdn-rili.jin10.com/web_data/{y}/daily/{m:02d}/{d:02d}/economics.json"

        events_out = []
        d = start
        while d <= end:
            try:
                u = url.format(y=d.year, m=d.month, d=d.day)
                r = requests.get(u, timeout=timeout, headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://rili.jin10.com/",
                })
                if r.status_code != 200:
                    d += timedelta(days=1)
                    continue
                data = r.json()
                for ev in (data.get("economics") or data or []):
                    if not isinstance(ev, dict):
                        continue
                    country = (ev.get("country") or "").strip()
                    ccy = JIN10_COUNTRY_MAP.get(country, "")
                    if ccy and ccy not in GOLD_RELEVANT_CCY:
                        continue
                    star = int(ev.get("star") or 0)
                    impact = "high" if star >= 3 else ("medium" if star == 2 else "low")
                    name = (ev.get("event") or ev.get("name") or "").strip()
                    pub_time = ev.get("pub_time") or ev.get("time_period") or ""
                    # pub_time 格式: "2026-05-02 20:30:00"
                    try:
                        dt = datetime.strptime(pub_time[:16], "%Y-%m-%d %H:%M")
                        time_str = dt.strftime("%m-%d %H:%M")
                    except Exception:
                        time_str = (pub_time[5:16] if len(pub_time) >= 16 else "待定")
                    if not name:
                        continue
                    cn_tag = {"USD": "[美]", "EUR": "[欧]", "CNY": "[中]",
                              "GBP": "[英]", "JPY": "[日]"}.get(ccy, "")
                    events_out.append({
                        "time": time_str,
                        "name": f"{cn_tag} {name}".strip(),
                        "impact": impact,
                        "_ccy": ccy, "_star": star,
                    })
            except Exception:
                pass
            d += timedelta(days=1)

        if not events_out:
            return None
        return events_out
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# 数据源 2：ForexFactory faireconomy JSON (英文兜底)
# ─────────────────────────────────────────────────────────────
def fetch_faireconomy(timeout: int = 8) -> Optional[List[Dict]]:
    """ForexFactory 本周日历（faireconomy 官方镜像）。"""
    if requests is None:
        return None
    try:
        urls = [
            "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
            "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
        ]
        events_out = []
        for url in urls:
            try:
                r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code != 200:
                    continue
                data = r.json()
            except Exception:
                continue
            for ev in data:
                ccy = (ev.get("country") or "").upper()
                if ccy not in GOLD_RELEVANT_CCY:
                    continue
                impact_raw = (ev.get("impact") or "").lower()
                impact = {"high": "high", "medium": "medium",
                          "low": "low", "holiday": "low"}.get(impact_raw, "low")
                title_en = (ev.get("title") or "").strip()
                title_cn = FF_CN_MAP.get(title_en, title_en)
                # 国家中文方括号标签
                cn_tag = {"USD": "[美]", "EUR": "[欧]", "GBP": "[英]",
                          "JPY": "[日]", "CNY": "[中]"}.get(ccy, f"[{ccy}]")
                # 时间解析（ISO 带时区 → 北京时间）
                date_iso = ev.get("date") or ""
                try:
                    dt = datetime.fromisoformat(date_iso.replace("Z", "+00:00"))
                    dt_bj = dt.astimezone(timezone(timedelta(hours=8)))
                    time_str = dt_bj.strftime("%m-%d %H:%M")
                except Exception:
                    time_str = "待定"
                events_out.append({
                    "time": time_str,
                    "name": f"{cn_tag} {title_cn}".strip(),
                    "impact": impact,
                    "_ccy": ccy,
                })
        return events_out or None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────────────────────
def get_calendar(days_ahead: int = 7, min_impact: str = "medium",
                 use_cache: bool = True, verbose: bool = True) -> List[Dict]:
    """
    获取经济日历。返回 institutional_render.MACRO_CONFIG.calendar 格式。

    参数：
      days_ahead   : 向后取多少天事件（金十源生效）
      min_impact   : 最低重要度过滤 ("low" / "medium" / "high")
      use_cache    : 是否使用本地 1 小时缓存
      verbose      : 是否打印日志
    """
    if use_cache:
        cached = _load_cache()
        if cached:
            if verbose:
                print(f"  [CAL] 使用本地缓存（{len(cached)} 条事件）")
            return _post_filter(cached, min_impact)

    events = None
    src = ""
    # 优先级：金十（中文）→ FF（英文兜底）
    if verbose:
        print("  [CAL] 尝试金十数据 ...", end=" ")
    events = fetch_jin10(days_ahead=days_ahead)
    if events:
        src = "jin10"
        if verbose:
            print(f"OK ({len(events)} 条)")
    else:
        if verbose:
            print("失败，回退 ForexFactory ...", end=" ")
        events = fetch_faireconomy()
        if events:
            src = "faireconomy"
            if verbose:
                print(f"OK ({len(events)} 条)")
        else:
            if verbose:
                print("也失败")

    if not events:
        if verbose:
            print("  [CAL] 所有数据源不可用，返回占位")
        return [{"time": "数据源不可达",
                 "name": "⚠ 经济日历抓取失败，请检查网络或手工编辑",
                 "impact": "low"}]

    # 排序：按时间字符串排序（MM-DD HH:MM 字典序与时间序一致）
    events.sort(key=lambda x: x.get("time", "9"))

    if use_cache:
        _save_cache(events)
    if verbose:
        print(f"  [CAL] 数据源：{src}，已缓存到 {CACHE_FILE}")

    return _post_filter(events, min_impact)


def _post_filter(events: List[Dict], min_impact: str) -> List[Dict]:
    rank = {"low": 0, "medium": 1, "high": 2}
    floor = rank.get(min_impact, 1)
    out = []
    for ev in events:
        if rank.get(ev.get("impact", "low"), 0) < floor:
            continue
        # 移除内部字段
        out.append({k: v for k, v in ev.items() if not k.startswith("_")})
    # 截断防止页面过长
    return out[:30]


if __name__ == "__main__":
    # 命令行测试
    cal = get_calendar(use_cache=False, verbose=True)
    print(f"\n共 {len(cal)} 条事件：\n")
    for ev in cal:
        print(f"  [{ev['impact'].upper():6}] {ev['time']}  {ev['name']}")
