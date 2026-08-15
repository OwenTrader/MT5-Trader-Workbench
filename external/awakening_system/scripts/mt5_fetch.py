# -*- coding: utf-8 -*-
"""
MT5 数据源（官方 Python 包）
================================
通过 MetaTrader5 IPC 直连运行中的 MT5 终端拉取 K 线，与 MT4 CSV 路径并列。

返回格式与 fetch_from_mt4 完全一致：{key: DataFrame(Open/High/Low/Close/Volume, index=Datetime)}

调用方约定：
  fetch_from_mt5(symbol_hint=None) → (data_dict, source_label)
"""

from datetime import datetime
import pandas as pd

try:
    import MetaTrader5 as mt5
    HAS_MT5 = True
except ImportError:
    HAS_MT5 = False


# 周期映射
def _tf_map():
    if not HAS_MT5: return {}
    return {
        "weekly": mt5.TIMEFRAME_W1,
        "daily":  mt5.TIMEFRAME_D1,
        "h4":     mt5.TIMEFRAME_H4,
        "h1":     mt5.TIMEFRAME_H1,
        "m15":    mt5.TIMEFRAME_M15,
    }


# 默认要拉的 K 线数量
BARS = {
    "weekly": 500,
    "daily":  500,
    "h4":     500,
    "h1":     500,
    "m15":    500,
}


def _resolve_symbol(symbol_hint=None):
    """
    解析实际可用的黄金品种名。MT5 不同 broker 使用不同后缀（XAUUSD/XAUUSDc/XAUUSDm 等）。
    优先级：用户指定 → 包含 XAU/GOLD 的品种 → None
    """
    if symbol_hint:
        info = mt5.symbol_info(symbol_hint)
        if info and info.visible:
            return symbol_hint
        if info and not info.visible:
            mt5.symbol_select(symbol_hint, True)
            return symbol_hint

    syms = mt5.symbols_get() or []
    # 优先匹配
    candidates = [s.name for s in syms if any(k in s.name.upper() for k in ("XAU", "GOLD"))]
    if not candidates:
        return None
    # 优先选择 XAUUSD（带后缀），排除 XAUEUR 等其他计价
    usd_quoted = [c for c in candidates if "USD" in c.upper()]
    pool = usd_quoted or candidates
    # 优先无后缀（XAUUSD）→ 然后任意带后缀
    pool.sort(key=lambda x: (len(x), x))
    chosen = pool[0]
    # 确保可见
    info = mt5.symbol_info(chosen)
    if info and not info.visible:
        mt5.symbol_select(chosen, True)
    return chosen


def fetch_from_mt5(symbol_hint=None):
    """
    主入口。返回 (data_dict, files_dir_label) 与 fetch_from_mt4 同形。
    files_dir_label 这里用 "MT5:<symbol>" 作为来源标识。
    """
    if not HAS_MT5:
        print("  [MT5] MetaTrader5 包未安装，跳过 MT5 数据源")
        return {}, None

    if not mt5.initialize():
        err = mt5.last_error()
        print(f"  [MT5] 初始化失败: {err}（MT5 终端可能未运行）")
        return {}, None

    try:
        ti = mt5.terminal_info()
        ai = mt5.account_info()
        if ti:
            print(f"  [MT5] 终端: {ti.name}")
        if ai:
            print(f"  [MT5] 账户: {ai.login} @ {ai.server}")

        symbol = _resolve_symbol(symbol_hint)
        if not symbol:
            print("  [MT5] 未找到黄金品种（XAU/GOLD），请在 MT5 市场报价中右键启用")
            return {}, None
        print(f"  [MT5] 使用品种: {symbol}")

        result = {}
        for key, tf in _tf_map().items():
            n = BARS.get(key, 500)
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, n)
            if rates is None or len(rates) == 0:
                print(f"  [MT5] {key}: 无数据 (last_error={mt5.last_error()})")
                continue
            df = pd.DataFrame(rates)
            # MT5 时间字段是 broker 时区秒级时间戳，统一当 UTC 处理（与 MT4 CSV 路径一致）
            df["Datetime"] = pd.to_datetime(df["time"], unit="s", utc=False)
            df = df.set_index("Datetime")
            df = df.rename(columns={
                "open": "Open", "high": "High", "low": "Low", "close": "Close",
                "tick_volume": "Volume",
            })
            df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])

            # 检查数据新鲜度
            age = (datetime.now() - df.index[-1].to_pydatetime().replace(tzinfo=None)).total_seconds()
            if age > 1800:
                print(f"  [MT5] {key}: 数据陈旧 ({age/60:.0f}分钟前)")

            result[key] = df
            print(f"  [MT5] {key}: {len(df)} 根K线，最新价 {df['Close'].iloc[-1]:.2f}")
        return result, f"MT5:{symbol}"
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    data, src = fetch_from_mt5()
    print(f"\n来源: {src}")
    for k, df in data.items():
        print(f"  {k}: {len(df)} bars, last={df['Close'].iloc[-1]:.2f} @ {df.index[-1]}")
