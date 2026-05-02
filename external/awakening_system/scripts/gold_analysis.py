"""
XAU/USD 黄金自动行情分析脚本
运行后自动生成 HTML 分析报告并在浏览器打开
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import webbrowser
import warnings
warnings.filterwarnings("ignore")

REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")
os.makedirs(REPORT_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# 技术指标计算
# ─────────────────────────────────────────────

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def macd(series, fast=12, slow=26, signal=9):
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def bollinger(series, period=20, std_dev=2):
    mid = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return upper, mid, lower

def atr(high, low, close, period=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean()

def stochastic(high, low, close, k=14, d=3):
    lo = low.rolling(k).min()
    hi = high.rolling(k).max()
    k_line = 100 * (close - lo) / (hi - lo + 1e-10)
    d_line = k_line.rolling(d).mean()
    return k_line, d_line

def adx(high, low, close, period=14):
    up   = high.diff()
    down = -low.diff()
    dm_p = up.where((up > down) & (up > 0), 0.0)
    dm_m = down.where((down > up) & (down > 0), 0.0)
    tr_val = atr(high, low, close, period)
    di_p = 100 * dm_p.ewm(com=period-1, min_periods=period).mean() / (tr_val + 1e-10)
    di_m = 100 * dm_m.ewm(com=period-1, min_periods=period).mean() / (tr_val + 1e-10)
    dx   = 100 * (di_p - di_m).abs() / (di_p + di_m + 1e-10)
    adx_val = dx.ewm(com=period-1, min_periods=period).mean()
    return adx_val, di_p, di_m

def cci(high, low, close, period=20):
    tp = (high + low + close) / 3
    ma = tp.rolling(period).mean()
    md = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    return (tp - ma) / (0.015 * md + 1e-10)

def pivot_points(df):
    """用前一根K线的HLC计算标准枢轴点"""
    if len(df) < 2:
        return {}
    h = float(df["High"].iloc[-2])
    l = float(df["Low"].iloc[-2])
    c = float(df["Close"].iloc[-2])
    p = (h + l + c) / 3
    return {
        "P":  round(p,   1),
        "R1": round(2*p - l,       1),
        "R2": round(p + (h - l),   1),
        "R3": round(h + 2*(p - l), 1),
        "S1": round(2*p - h,       1),
        "S2": round(p - (h - l),   1),
        "S3": round(l - 2*(h - p), 1),
    }

def fibonacci_levels(swing_high, swing_low, direction="up"):
    """
    斐波那契回撤位。direction="up" 表示上涨趋势（回撤做多）；
    direction="down" 表示下跌趋势（反弹做空）。
    标准约定：100% = 起涨/起跌点，0% = 趋势末端。
    """
    diff = swing_high - swing_low
    ratios = [("0.0%", 0), ("23.6%", 0.236), ("38.2%", 0.382),
              ("50.0%", 0.5), ("61.8%", 0.618), ("78.6%", 0.786), ("100%", 1.0)]
    if direction == "up":
        # 起涨点 swing_low = 100%，高点 swing_high = 0%
        return {name: round(swing_high - ratio * diff, 1) for name, ratio in ratios}
    else:
        # 起跌点 swing_high = 100%，低点 swing_low = 0%
        return {name: round(swing_low + ratio * diff, 1) for name, ratio in ratios}

def detect_patterns(df):
    """识别最近一根K线的形态"""
    if len(df) < 3:
        return []
    o = df["Open"].values
    h = df["High"].values
    l = df["Low"].values
    c = df["Close"].values
    i = -1
    body  = abs(c[i] - o[i])
    rng   = h[i] - l[i] + 1e-10
    upper = h[i] - max(c[i], o[i])
    lower = min(c[i], o[i]) - l[i]
    patterns = []
    if body / rng < 0.08:
        patterns.append(("十字星", "neutral"))
    elif body / rng > 0.72:
        patterns.append(("强势阳线" if c[i] > o[i] else "强势阴线",
                         "bull" if c[i] > o[i] else "bear"))
    if lower > 2.2 * body and upper < body and c[i] > o[i]:
        patterns.append(("锤子线", "bull"))
    if upper > 2.2 * body and lower < body and c[i] < o[i]:
        patterns.append(("射击之星", "bear"))
    if (c[i] > o[i] and c[i-1] < o[i-1]
            and c[i] > o[i-1] and o[i] < c[i-1]):
        patterns.append(("阳包阴", "bull"))
    if (c[i] < o[i] and c[i-1] > o[i-1]
            and c[i] < o[i-1] and o[i] > c[i-1]):
        patterns.append(("阴包阳", "bear"))
    if (c[i] < o[i] and abs(c[i-1]-o[i-1])/(h[i-1]-l[i-1]+1e-10) < 0.15
            and c[i-2] > o[i-2]):
        patterns.append(("黄昏十字", "bear"))
    if (c[i] > o[i] and abs(c[i-1]-o[i-1])/(h[i-1]-l[i-1]+1e-10) < 0.15
            and c[i-2] < o[i-2]):
        patterns.append(("晨星十字", "bull"))
    return patterns

def find_swing_levels(df, n=5, count=3):
    """找出近期 swing 高点和低点作为支撑/阻力"""
    highs, lows = [], []
    high = df["High"].values
    low  = df["Low"].values
    for i in range(n, len(df) - n):
        if all(high[i] >= high[i-j] for j in range(1, n+1)) and all(high[i] >= high[i+j] for j in range(1, n+1)):
            highs.append(high[i])
        if all(low[i] <= low[i-j] for j in range(1, n+1)) and all(low[i] <= low[i+j] for j in range(1, n+1)):
            lows.append(low[i])
    highs = sorted(set([round(v, 1) for v in highs]), reverse=True)[:count]
    lows  = sorted(set([round(v, 1) for v in lows]))[:count]
    return highs, lows

def asian_range(df_h1, broker_tz_offset=None):
    """
    计算最近亚洲盘区间（北京时间 08:00-16:00，即 UTC 00:00-08:00）。
    
    时区处理：
    - Yahoo 数据：UTC，无时区信息但已对齐 UTC → 直接当 UTC 用
    - MT4 数据：broker 时区（通常 GMT+2/+3），无时区信息
    - broker_tz_offset：broker 相对 UTC 的小时偏移（如 EXNESS 通常 +2/+3）
    
    返回 {'high', 'low', 'mid', 'date'} 或 None。
    """
    if df_h1 is None or df_h1.empty or len(df_h1) < 4:
        return None
    try:
        idx = df_h1.index
        # 推断时区
        if idx.tz is not None:
            idx_utc = idx.tz_convert("UTC")
        elif broker_tz_offset is not None:
            # 把 broker 时间转 UTC：减去偏移
            idx_utc = idx - pd.Timedelta(hours=broker_tz_offset)
            idx_utc = idx_utc.tz_localize("UTC")
        else:
            # 无时区信息时，自动猜测：检查最后一根K线时间与 UTC now 的差
            now_utc = pd.Timestamp.utcnow().tz_localize(None)
            last_t = idx[-1]
            diff_h = round((last_t - now_utc).total_seconds() / 3600)
            # diff_h ≈ 0 → UTC； diff_h ≈ 2/3 → broker GMT+2/+3
            if -1 <= diff_h <= 1:
                idx_utc = idx.tz_localize("UTC")
            else:
                idx_utc = (idx - pd.Timedelta(hours=diff_h)).tz_localize("UTC")
        now_utc = pd.Timestamp.now(tz="UTC")
        for days_ago in range(0, 5):
            date = (now_utc - pd.Timedelta(days=days_ago)).date()
            s = pd.Timestamp(date, tz="UTC")
            e = s + pd.Timedelta(hours=8)
            mask = (idx_utc >= s) & (idx_utc < e)
            bars = df_h1[mask.values] if hasattr(mask, "values") else df_h1[mask]
            if len(bars) >= 4:
                h = round(float(bars["High"].max()), 1)
                l = round(float(bars["Low"].min()),  1)
                return {"high": h, "low": l,
                        "mid":  round((h + l) / 2, 1),
                        "date": str(date), "bars": len(bars)}
    except Exception:
        pass
    return None

def detect_divergence(close_series, lookback=40, swing_window=3, min_gap=5):
    """
    检测 RSI 价格背离（要求 ±3 根K线的局部极值，且两个极值至少间隔 5 根 K 线）。
    返回 [("RSI看涨背离","bull")] 或 [("RSI看跌背离","bear")] 或 []
    """
    if len(close_series) < lookback + 10:
        return []
    try:
        rsi_s  = rsi(close_series)
        c  = close_series.values[-lookback:]
        rv = rsi_s.values[-lookback:]
        n  = len(c)
        sw = swing_window
        divs = []
        # 找局部低点（±sw 根K线都比它高）
        lo_i = [i for i in range(sw, n-sw)
                if all(c[i] < c[i-j] for j in range(1, sw+1))
                and all(c[i] < c[i+j] for j in range(1, sw+1))]
        if len(lo_i) >= 2:
            i1, i2 = lo_i[-2], lo_i[-1]
            if i2 - i1 >= min_gap and c[i2] < c[i1] and rv[i2] > rv[i1] + 3:
                divs.append(("RSI看涨背离", "bull"))
        hi_i = [i for i in range(sw, n-sw)
                if all(c[i] > c[i-j] for j in range(1, sw+1))
                and all(c[i] > c[i+j] for j in range(1, sw+1))]
        if len(hi_i) >= 2:
            i1, i2 = hi_i[-2], hi_i[-1]
            if i2 - i1 >= min_gap and c[i2] > c[i1] and rv[i2] < rv[i1] - 3:
                divs.append(("RSI看跌背离", "bear"))
        return divs
    except Exception:
        return []

# ─────────────────────────────────────────────
# MT4 CSV 数据源
# ─────────────────────────────────────────────

def find_mt4_files_dir(symbol=None):
    """
    自动搜索 MT4 数据目录下的 Files 文件夹。
    若 symbol=None，自动识别任意 mt4_<symbol>_D1.csv 文件。
    返回 (目录路径, 实际品种名)；找不到返回 (None, None)。
    """
    import glob, re
    candidates = []
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        pattern = os.path.join(appdata, "MetaQuotes", "Terminal", "*", "MQL4", "Files")
        candidates += glob.glob(pattern)
    for drive in ["C:", "D:", "E:", "F:"]:
        for broker_glob in ["Program Files*\\*MT4*", "Program Files*\\*MetaTrader 4*",
                            "Program Files*\\*metatrader*", "*\\MT4", "*\\MetaTrader4"]:
            pattern = os.path.join(drive, broker_glob, "MQL4", "Files")
            candidates += glob.glob(pattern, recursive=False)

    for d in candidates:
        if symbol:
            probe = os.path.join(d, f"mt4_{symbol}_D1.csv")
            if os.path.isfile(probe):
                return d, symbol
        # 自动识别：查找任何 mt4_*_D1.csv（优先黄金 + 最新修改）
        matches = glob.glob(os.path.join(d, "mt4_*_D1.csv"))
        if matches:
            gold = [m for m in matches if re.search(r"(XAU|GOLD)", os.path.basename(m), re.IGNORECASE)]
            pool = gold if gold else matches
            # 按修改时间倒序，最新的优先
            chosen = max(pool, key=lambda p: os.path.getmtime(p))
            sym = re.match(r"mt4_(.+)_D1\.csv", os.path.basename(chosen)).group(1)
            return d, sym
    return None, None


def _merge_sunday_candle(df, tf_name):
    """
    MT4 broker 时区(GMT+2/+3)导致周日22:00-23:59 UTC的1-2小时开盘数据
    被划归"周日 K 线"。对 D1 周期合并到下一根周一K线，避免污染指标。
    （W1 周线 K 线时间戳本就在周日，是 Forex 周开始的设计，不能合并。）
    """
    if df.empty or tf_name != "D1":
        return df
    if not isinstance(df.index, pd.DatetimeIndex):
        return df
    df = df.copy()
    # 计算非周日 K 线的中位波幅作为参考
    non_sun = df[df.index.dayofweek != 6]
    if len(non_sun) < 5:
        return df
    median_range = float((non_sun["High"] - non_sun["Low"]).median())
    drop_idx = []
    for i, t in enumerate(df.index):
        if t.dayofweek != 6:
            continue
        # 周日 K 线波幅 < 中位的 40% 才认为是"被截短的迷你 K 线"
        sun_range = float(df.iloc[i]["High"] - df.iloc[i]["Low"])
        if sun_range > median_range * 0.4:
            continue   # 正常波幅的周日数据，保留
        if i + 1 < len(df):
            nxt = df.index[i + 1]
            df.at[nxt, "Open"] = df.at[t, "Open"]
            df.at[nxt, "High"] = max(df.at[nxt, "High"], df.at[t, "High"])
            df.at[nxt, "Low"]  = min(df.at[nxt, "Low"],  df.at[t, "Low"])
            if "Volume" in df.columns:
                df.at[nxt, "Volume"] = df.at[nxt, "Volume"] + df.at[t, "Volume"]
            drop_idx.append(t)
    if drop_idx:
        df = df.drop(index=drop_idx)
    return df


def read_mt4_csv(files_dir, symbol, tf_name):
    """读取 MT4 导出的单周期 CSV，返回 DataFrame"""
    path = os.path.join(files_dir, f"mt4_{symbol}_{tf_name}.csv")
    if not os.path.isfile(path):
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, parse_dates=["Time"])
        df = df.rename(columns={"Time": "Datetime"})
        df = df.set_index("Datetime")
        df.index = pd.to_datetime(df.index, utc=False)
        df.columns = [c.capitalize() for c in df.columns]
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
        # 合并周日 K 线（MT4 broker 时区问题）
        before = len(df)
        df = _merge_sunday_candle(df, tf_name)
        if len(df) < before:
            print(f"  [MT4] {tf_name} 合并 {before-len(df)} 根周日小K线到周一")
        # 检查数据新鲜度（超过 30 分钟认为 MT4 已关闭）
        age = (datetime.now() - df.index[-1].to_pydatetime().replace(tzinfo=None)).total_seconds()
        if age > 1800:
            print(f"  [MT4] {tf_name} 数据陈旧 ({age/60:.0f}分钟前)，可能MT4未运行")
        return df
    except Exception as e:
        print(f"  [MT4] 读取 {tf_name} 失败: {e}")
        return pd.DataFrame()


def fetch_from_mt4(symbol=None):
    """尝试从 MT4 CSV 文件读取行情，返回 {tf_name: DataFrame} 或空 dict"""
    files_dir, symbol = find_mt4_files_dir(symbol)
    if not files_dir or not symbol:
        return {}, None
    print(f"  [MT4] 找到数据目录: {files_dir}")
    print(f"  [MT4] 识别品种: {symbol}")
    tf_map = {
        "weekly": "W1",
        "daily":  "D1",
        "h4":     "H4",
        "h1":     "H1",
        "m15":    "M15",
    }
    result = {}
    for key, tf in tf_map.items():
        df = read_mt4_csv(files_dir, symbol, tf)
        if not df.empty:
            result[key] = df
            print(f"  [MT4] {key}: {len(df)} 根K线，最新价 {df['Close'].iloc[-1]:.2f}")
    return result, files_dir


# ─────────────────────────────────────────────
# Yahoo Finance 数据源（备用）
# ─────────────────────────────────────────────

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://finance.yahoo.com/",
}


def _fetch_chart(symbol, interval, range_str):
    """直接调用 Yahoo Finance v8 chart API"""
    for host in ["query2", "query1"]:
        try:
            url = f"https://{host}.finance.yahoo.com/v8/finance/chart/{symbol}"
            params = {"interval": interval, "range": range_str, "includePrePost": "false"}
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            payload = resp.json()
            chart = payload["chart"]["result"][0]
            timestamps = chart["timestamp"]
            q = chart["indicators"]["quote"][0]
            ohlcv = {
                "Open":   q.get("open",   [None] * len(timestamps)),
                "High":   q.get("high",   [None] * len(timestamps)),
                "Low":    q.get("low",    [None] * len(timestamps)),
                "Close":  q.get("close",  [None] * len(timestamps)),
                "Volume": q.get("volume", [0]    * len(timestamps)),
            }
            idx = pd.to_datetime(timestamps, unit="s", utc=True)
            df = pd.DataFrame(ohlcv, index=idx).dropna(subset=["Close"])
            return df
        except Exception:
            continue
    return pd.DataFrame()


def fetch_data_yahoo():
    """从 Yahoo Finance 抓取数据（备用）"""
    import time
    configs = [
        ("weekly", "1wk", "2y"),
        ("daily",  "1d",  "6mo"),
        ("h4",     "1h",  "60d"),
        ("h1",     "1h",  "7d"),
        ("m15",    "15m", "5d"),
    ]
    symbols = ["GC=F", "XAUUSD=X"]
    data = {}
    for name, interval, range_str in configs:
        df = pd.DataFrame()
        for sym in symbols:
            df = _fetch_chart(sym, interval, range_str)
            if not df.empty:
                break
            time.sleep(1)
        if df.empty:
            continue
        if name == "h4":
            df = df.resample("4h").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
        data[name] = df
        print(f"  [Yahoo] {name}: {len(df)} 根K线，最新价 {df['Close'].iloc[-1]:.2f}")
        time.sleep(0.5)
    return data


def fetch_data(mt4_symbol="XAUUSD"):
    """优先从 MT4 CSV 读取，如果 MT4 没运行或找不到文件则回退到 Yahoo Finance"""
    print("正在检测数据源...")
    mt4_data, files_dir = fetch_from_mt4(mt4_symbol)
    if mt4_data and len(mt4_data) >= 3:
        print(f"  [OK] 使用 MT4 实时数据（共 {len(mt4_data)} 个周期）")
        return mt4_data, "MT4"
    if mt4_data:
        print(f"  [MT4] 只找到 {len(mt4_data)} 个周期，尝试 Yahoo Finance 补充缺失周期")
    else:
        print("  [MT4] 未找到导出文件，请在 MT4 中加载 MT4_DataExporter 指标")
        print("  [Yahoo] 回退到 Yahoo Finance...")
    yahoo_data = fetch_data_yahoo()
    merged = {**yahoo_data, **mt4_data}  # MT4 数据优先覆盖 Yahoo
    source = "MT4+Yahoo" if (mt4_data and yahoo_data) else ("MT4" if mt4_data else "Yahoo Finance")
    return merged, source


def fetch_data_mt5_first(mt4_symbol="XAUUSD"):
    """
    MT5 系统专用数据源：MT5（Python 包）→ MT4（CSV）→ Yahoo。
    与 fetch_data() 互不干扰，仅供 wave_analysis_mt5.py 调用。
    """
    print("正在检测 MT5 数据源...")
    try:
        from mt5_fetch import fetch_from_mt5
        mt5_data, mt5_src = fetch_from_mt5()
    except ImportError:
        mt5_data, mt5_src = {}, None
        print("  [MT5] MetaTrader5 包未安装")
    except Exception as e:
        mt5_data, mt5_src = {}, None
        print(f"  [MT5] 拉取异常: {e}")

    if mt5_data and len(mt5_data) >= 3:
        print(f"  [OK] 使用 MT5 实时数据（{mt5_src}，共 {len(mt5_data)} 个周期）")
        return mt5_data, mt5_src or "MT5"

    # MT5 不可用 → 借用 MT4
    print("  [MT5] 数据不足，尝试借用 MT4 CSV...")
    mt4_data, _ = fetch_from_mt4(mt4_symbol)
    if mt4_data and len(mt4_data) >= 3:
        print(f"  [OK] MT5 报告借用 MT4 数据（共 {len(mt4_data)} 个周期）")
        return mt4_data, "MT4(借用)"

    # 最后兜底
    print("  [MT4] 也不可用，回退 Yahoo Finance")
    yahoo_data = fetch_data_yahoo()
    return yahoo_data, "Yahoo Finance"

# ─────────────────────────────────────────────
# 单周期分析
# ─────────────────────────────────────────────

def analyze_timeframe(df, label):
    close = df["Close"]
    high  = df["High"]
    low   = df["Low"]
    result = {"label": label}

    # ── OHLC
    result["current_price"] = round(float(close.iloc[-1]), 2)
    result["open"]  = round(float(df["Open"].iloc[-1]), 2)
    result["high"]  = round(float(high.iloc[-1]), 2)
    result["low"]   = round(float(low.iloc[-1]), 2)

    # ── EMA
    result["ema20"]  = round(float(ema(close, 20).iloc[-1]), 2)
    result["ema50"]  = round(float(ema(close, 50).iloc[-1]), 2)
    result["ema200"] = round(float(ema(close, 200).iloc[-1]), 2) if len(close) >= 200 else None

    # ── RSI
    rsi_val = rsi(close)
    result["rsi"] = round(float(rsi_val.iloc[-1]), 1)

    # ── MACD（保留前一根用于"刚交叉"判定）
    macd_line, signal_line, histogram = macd(close)
    result["macd"]        = round(float(macd_line.iloc[-1]), 2)
    result["macd_signal"] = round(float(signal_line.iloc[-1]), 2)
    result["macd_hist"]   = round(float(histogram.iloc[-1]), 2)
    result["_macd_prev"]      = float(macd_line.iloc[-2]) if len(macd_line) > 1 else 0
    result["_macd_sig_prev"]  = float(signal_line.iloc[-2]) if len(signal_line) > 1 else 0
    result["_hist_prev"]      = float(histogram.iloc[-2]) if len(histogram) > 1 else 0

    # ── Bollinger Bands
    bb_upper, bb_mid, bb_lower = bollinger(close)
    result["bb_upper"] = round(float(bb_upper.iloc[-1]), 2)
    result["bb_mid"]   = round(float(bb_mid.iloc[-1]),   2)
    result["bb_lower"] = round(float(bb_lower.iloc[-1]), 2)
    bb_w = (result["bb_upper"] - result["bb_lower"]) / (result["bb_mid"] + 1e-10)
    result["bb_width"] = round(bb_w * 100, 2)   # 带宽%

    # ── ATR & Volatility
    atr_val = atr(high, low, close, 14)
    result["atr"] = round(float(atr_val.iloc[-1]), 2)
    result["atr_pct"] = round(result["atr"] / result["current_price"] * 100, 2)

    # ── Stochastic %K/%D（保留前一根用于"刚交叉"判定）
    k_line, d_line = stochastic(high, low, close)
    result["stoch_k"] = round(float(k_line.iloc[-1]), 1)
    result["stoch_d"] = round(float(d_line.iloc[-1]), 1)
    result["_k_prev"] = float(k_line.iloc[-2]) if len(k_line) > 1 else 50
    result["_d_prev"] = float(d_line.iloc[-2]) if len(d_line) > 1 else 50

    # ── ADX + DI
    adx_val, di_p, di_m = adx(high, low, close)
    result["adx"]  = round(float(adx_val.iloc[-1]), 1)
    result["di_p"] = round(float(di_p.iloc[-1]),    1)
    result["di_m"] = round(float(di_m.iloc[-1]),    1)

    # ── CCI
    cci_val = cci(high, low, close)
    result["cci"] = round(float(cci_val.iloc[-1]), 1)

    # ── Pivot Points
    result["pivots"] = pivot_points(df)

    # ── Fibonacci（用近 60 根K线的最高/最低；方向由高低点先后顺序决定）
    look = min(60, len(df))
    seg_high = high.iloc[-look:]
    seg_low  = low.iloc[-look:]
    fib_h = float(seg_high.max())
    fib_l = float(seg_low.min())
    # 高点位置在低点之后 → 上涨段（回撤做多）；反之下跌段（反弹做空）
    fib_dir = "up" if seg_high.idxmax() >= seg_low.idxmin() else "down"
    result["fib"] = fibonacci_levels(fib_h, fib_l, direction=fib_dir)
    result["fib_direction"] = fib_dir
    result["fib_high"] = round(fib_h, 1)
    result["fib_low"]  = round(fib_l, 1)

    # ── Swing S/R
    result["resistances"], result["supports"] = find_swing_levels(df)

    # ── Candlestick patterns
    result["patterns"] = detect_patterns(df)

    # ── 趋势判断（EMA排列 + EMA200大势 + ADX强度）
    price = result["current_price"]
    e20, e50 = result["ema20"], result["ema50"]
    e200 = result["ema200"]
    adx_v = result["adx"]
    bull_align = price > e20 > e50
    bear_align = price < e20 < e50
    if e200 is not None:
        if bull_align and price > e200:
            trend, trend_cls = "强势多头", "bull"
        elif bear_align and price < e200:
            trend, trend_cls = "强势空头", "bear"
        elif bull_align and price < e200:
            trend, trend_cls = "弱势多头", "bull"
        elif bear_align and price > e200:
            trend, trend_cls = "弱势空头", "bear"
        else:
            trend, trend_cls = "震荡", "neutral"
    else:
        if bull_align: trend, trend_cls = "多头", "bull"
        elif bear_align: trend, trend_cls = "空头", "bear"
        else: trend, trend_cls = "震荡", "neutral"
    result["trend"]     = trend
    result["trend_cls"] = trend_cls

    # 趋势强度
    if adx_v >= 40:
        result["trend_strength"] = "极强趋势"
    elif adx_v >= 25:
        result["trend_strength"] = "趋势明确"
    elif adx_v >= 18:
        result["trend_strength"] = "趋势形成"
    else:
        result["trend_strength"] = "震荡盘整"

    # ── 市场状态
    if adx_v >= 25 and trend_cls != "neutral":
        result["market_state"] = "trending"
    elif result["bb_width"] < 2.0:
        result["market_state"] = "squeeze"
    else:
        result["market_state"] = "ranging"

    # ── 信号列表
    signals = []
    rsi_v = result["rsi"]
    hist  = result["macd_hist"]
    k, d  = result["stoch_k"], result["stoch_d"]
    cci_v = result["cci"]

    if rsi_v > 75:   signals.append(("RSI极度超买", "bear"))
    elif rsi_v > 70: signals.append(("RSI超买",     "bear"))
    elif rsi_v < 25: signals.append(("RSI极度超卖", "bull"))
    elif rsi_v < 30: signals.append(("RSI超卖",     "bull"))

    # MACD 真正的"刚交叉"：前一根在下方，当前根上穿（或反之）
    macd_now, sig_now = result["macd"], result["macd_signal"]
    macd_prev, sig_prev = result["_macd_prev"], result["_macd_sig_prev"]
    if macd_prev <= sig_prev and macd_now > sig_now:
        signals.append(("MACD刚金叉", "bull"))
    elif macd_prev >= sig_prev and macd_now < sig_now:
        signals.append(("MACD刚死叉", "bear"))
    # 柱状图动能（红柱缩短 = 空头转弱，绿柱缩短 = 多头转弱）
    hist_prev = result["_hist_prev"]
    if hist > 0 and hist < hist_prev:
        signals.append(("MACD多头动能减弱", "bear"))
    elif hist < 0 and hist > hist_prev:
        signals.append(("MACD空头动能减弱", "bull"))

    # KD 极值
    if k > 80 and d > 80:   signals.append(("KD超买", "bear"))
    elif k < 20 and d < 20: signals.append(("KD超卖", "bull"))
    # KD 真正的"刚交叉"
    k_prev, d_prev = result["_k_prev"], result["_d_prev"]
    if k_prev <= d_prev and k > d and k < 50:
        signals.append(("KD低位金叉", "bull"))
    elif k_prev >= d_prev and k < d and k > 50:
        signals.append(("KD高位死叉", "bear"))

    if cci_v >  200: signals.append(("CCI极度超买", "bear"))
    elif cci_v > 100: signals.append(("CCI超买",    "bear"))
    elif cci_v < -200: signals.append(("CCI极度超卖","bull"))
    elif cci_v < -100: signals.append(("CCI超卖",   "bull"))

    # 布林带：根据ADX判断是趋势延续还是反转
    if price > result["bb_upper"]:
        if adx_v >= 25:  signals.append(("突破布林上轨(强势延续)", "bull"))
        else:            signals.append(("布林上轨触顶(可能回落)", "bear"))
    elif price < result["bb_lower"]:
        if adx_v >= 25:  signals.append(("跌破布林下轨(强势延续)", "bear"))
        else:            signals.append(("布林下轨触底(可能反弹)", "bull"))

    if result["di_p"] > result["di_m"] and adx_v > 20:
        signals.append(("ADX多头", "bull"))
    elif result["di_m"] > result["di_p"] and adx_v > 20:
        signals.append(("ADX空头", "bear"))

    for pat, cls in result["patterns"]:
        signals.append((pat, cls))

    for div, cls in detect_divergence(close):
        signals.append((div, cls))

    result["signals"] = signals

    # ── 综合评分 (-100 ~ +100，正值偏多，负值偏空)
    score = 0
    for _, cls in signals:
        if cls == "bull":   score += 10
        elif cls == "bear": score -= 10
    if trend_cls == "bull":    score += 15
    elif trend_cls == "bear":  score -= 15
    result["score"] = max(-100, min(100, score))

    return result

# ─────────────────────────────────────────────
# 生成交易机会
# ─────────────────────────────────────────────

def _rr(entry, sl, tp):
    """计算 R:R 比（返回字符串）"""
    try:
        risk   = abs(entry - sl)
        reward = abs(tp - entry)
        if risk == 0: return "—"
        ratio = reward / risk
        return f"1 : {ratio:.1f}"
    except Exception:
        return "—"

def _pivot_levels_near(analyses, price, band):
    """从各周期枢轴点中收集当前价附近的支撑/阻力"""
    extra_sup, extra_res = [], []
    for tf in ["h1", "h4", "daily"]:
        a = analyses.get(tf, {})
        for v in a.get("pivots", {}).values():
            if price - band < v < price:
                extra_sup.append(v)
            elif price < v < price + band:
                extra_res.append(v)
        for v in a.get("fib", {}).values():
            if price - band < v < price:
                extra_sup.append(v)
            elif price < v < price + band:
                extra_res.append(v)
    return extra_sup, extra_res

def generate_setups(analyses, df_h1=None):
    daily = analyses.get("daily")
    h4    = analyses.get("h4")
    h1    = analyses.get("h1")
    if not daily or not h4:
        return []

    price    = h4["current_price"]
    atr_h4   = h4.get("atr", price * 0.01)
    atr_h1   = h1.get("atr", atr_h4 * 0.5) if h1 else atr_h4 * 0.5
    band     = max(price * 0.07, atr_h4 * 10)

    # ── 收集支撑/阻力
    raw_sup, raw_res = [], []
    for tf in [h1, h4, daily]:
        if not tf: continue
        raw_sup += [s for s in tf.get("supports",    []) if price - band < s < price]
        raw_res += [r for r in tf.get("resistances", []) if price < r < price + band]
        for v in list(tf.get("pivots", {}).values()) + list(tf.get("fib", {}).values()):
            (raw_sup if price - band < v < price else raw_res if price < v < price + band else []).append(v)
        for k in ["ema20","ema50","ema200"]:
            v = tf.get(k)
            if v: (raw_sup if price - band < v < price else raw_res if price < v < price + band else []).append(v)

    near_sup = sorted(set([round(s, 1) for s in raw_sup]))[:4]
    near_res = sorted(set([round(r, 1) for r in raw_res]))[:4]
    if not near_sup: near_sup = [round(price - atr_h4*2,1), round(price - atr_h4*4,1)]
    if not near_res: near_res = [round(price + atr_h4*2,1), round(price + atr_h4*4,1)]

    weekly_a     = analyses.get("weekly", {})
    weekly_trend = weekly_a.get("trend_cls", "neutral")
    daily_trend  = daily.get("trend_cls", "neutral")
    h4_trend     = h4.get("trend_cls",   "neutral")
    h4_adx       = h4.get("adx", 0)
    h4_rsi       = h4.get("rsi", 50)
    h4_k         = h4.get("stoch_k", 50)
    h4_d         = h4.get("stoch_d", 50)

    bear_cnt = sum(1 for t in [weekly_trend, daily_trend, h4_trend] if t == "bear")
    bull_cnt = sum(1 for t in [weekly_trend, daily_trend, h4_trend] if t == "bull")

    # 亚盘区间
    ar = asian_range(df_h1) if df_h1 is not None else None

    # H1信号汇总（背离检测已在 analyze_timeframe 中）
    h1_sigs = [s for s,_ in h1.get("signals",[])] if h1 else []
    has_bull_div = any("看涨背离" in s for s in h1_sigs) or any("看涨背离" in s for s,_ in h4.get("signals",[]))
    has_bear_div = any("看跌背离" in s for s in h1_sigs) or any("看跌背离" in s for s,_ in h4.get("signals",[]))

    setups = []

    # ══════════════════════════════════════════════════════
    # 策略一：趋势顺势回调 EMA Pullback（最高胜率日内策略）
    # 核心逻辑：大趋势确认→等价格回调至 EMA20/50→H1出现拒绝信号→入场
    # ══════════════════════════════════════════════════════
    if h4_adx >= 22 and h4_trend != "neutral":
        ema_level = h4.get("ema20") if h4_adx >= 30 else h4.get("ema50", h4.get("ema20"))
        if ema_level:
            is_bull_pb = (h4_trend == "bull" and price > ema_level * 0.995)
            is_bear_pb = (h4_trend == "bear" and price < ema_level * 1.005)
            if is_bull_pb or is_bear_pb:
                if h4_trend == "bull":
                    e_lo = round(ema_level - atr_h1 * 0.3, 1)
                    e_hi = round(ema_level + atr_h1 * 0.5, 1)
                    sl_v = round(ema_level - atr_h1 * 1.8, 1)
                    tp1  = near_res[0] if near_res else round(price + atr_h4*2, 1)
                    tp2  = near_res[1] if len(near_res)>1 else round(price + atr_h4*4, 1)
                    cond = (f"价格回踩 EMA{20 if h4_adx>=30 else 50}（{ema_level:.1f}）附近，"
                            f"H1出现锤子线/阳包阴/长下影支撑K线，"
                            f"RSI≥40 且KD金叉后入场做多")
                    mgmt = ("① EMA附近分批建仓（50%确认+50%回踩加仓）\n"
                            "② 到达TP1移止损至成本价，减仓一半\n"
                            "③ 若H1K线收盘于EMA下方，视为回调加深，等待下一支撑")
                    inv  = (f"H1收盘跌破 {sl_v:.1f}（EMA下方{atr_h1*1.8:.0f}点），"
                            "趋势已被破坏，本次回调演变为反转，立即止损")
                else:
                    e_lo = round(ema_level - atr_h1 * 0.5, 1)
                    e_hi = round(ema_level + atr_h1 * 0.3, 1)
                    sl_v = round(ema_level + atr_h1 * 1.8, 1)
                    tp1  = near_sup[-1] if near_sup else round(price - atr_h4*2, 1)
                    tp2  = near_sup[0]  if len(near_sup)>1 else round(price - atr_h4*4, 1)
                    cond = (f"价格反弹至 EMA{20 if h4_adx>=30 else 50}（{ema_level:.1f}）附近，"
                            f"H1出现射击之星/阴包阳/长上影拒绝K线，"
                            f"RSI≤60 且KD死叉后入场做空")
                    mgmt = ("① EMA区域分批建仓（50%确认+50%反弹加仓）\n"
                            "② 到达TP1移止损至成本价，减仓一半\n"
                            "③ 若H1K线收盘于EMA上方，等待下一阻力区")
                    inv  = (f"H1收盘突破 {sl_v:.1f}（EMA上方{atr_h1*1.8:.0f}点），"
                            "趋势反转信号，本次反弹已演变为突破，立即止损")
                setups.append({
                    "tag": "S1", "type": "做多" if h4_trend=="bull" else "做空",
                    "type_cls": h4_trend,
                    "scenario": f"【策略一】趋势EMA回调入场（ADX={h4_adx:.0f}，趋势{h4.get('trend_strength','')}）",
                    "probability": "高",
                    "condition": cond,
                    "entry": f"{e_lo} – {e_hi}",
                    "sl": f"{sl_v}  (1.8×H1 ATR)",
                    "tp1": f"{tp1:.1f}", "tp2": f"{tp2:.1f}",
                    "rr": _rr((e_lo+e_hi)/2, sl_v, tp1),
                    "management": mgmt, "invalidation": inv,
                    "session": "伦敦盘（15:00-19:00 BJ）或纽约盘（21:00-01:00 BJ）趋势最流畅"
                })

    # ══════════════════════════════════════════════════════
    # 策略二：亚盘区间突破（London/NY开盘方向性策略）
    # 核心逻辑：亚盘横盘蓄力→伦敦/纽约开盘突破→顺势跟进
    # ══════════════════════════════════════════════════════
    if ar:
        ar_h, ar_l, ar_mid = ar["high"], ar["low"], ar["mid"]
        ar_range = ar_h - ar_l
        # 只在价格靠近亚盘区间时给出方案
        if ar_l - atr_h4 < price < ar_h + atr_h4:
            sl_long  = round(ar_l - atr_h1 * 1.2, 1)
            sl_short = round(ar_h + atr_h1 * 1.2, 1)
            tp_long1 = round(ar_h + ar_range * 1.0, 1)
            tp_long2 = round(ar_h + ar_range * 1.8, 1)
            tp_sho1  = round(ar_l - ar_range * 1.0, 1)
            tp_sho2  = round(ar_l - ar_range * 1.8, 1)
            dir_hint = "偏多突破" if (daily_trend=="bull" or h4_trend=="bull") else "偏空突破" if (daily_trend=="bear" or h4_trend=="bear") else "双向观察"
            setups.append({
                "tag": "S2", "type": "突破", "type_cls": "neutral",
                "scenario": f"【策略二】亚盘区间突破（区间 {ar_l}–{ar_h}，幅度 {ar_range:.0f} 点，{dir_hint}）",
                "probability": "较高" if h4_adx < 20 else "中等",
                "condition": (f"亚盘区间 {ar_l} – {ar_h}（{ar['date']}）\n"
                              f"伦敦开盘（15:00 BJ）后若H1收盘突破 {ar_h} → 做多\n"
                              f"若H1收盘跌破 {ar_l} → 做空\n"
                              f"注意：突破后若30分钟内价格回到区间内，视为假突破，不追"),
                "entry": f"突破 {ar_h} 做多 / 跌破 {ar_l} 做空（H1收盘确认）",
                "sl": f"多单止损 {sl_long}（区间低点下方 {ar_l-sl_long:.0f} 点）\n空单止损 {sl_short}（区间高点上方 {sl_short-ar_h:.0f} 点）",
                "tp1": f"多 {tp_long1} / 空 {tp_sho1}（1:1 目标）",
                "tp2": f"多 {tp_long2} / 空 {tp_sho2}（1:1.8 目标）",
                "rr": "1 : 1.5 – 1 : 2",
                "management": ("① 突破后等待价格回踩区间边缘不破（15-30分钟），确认后入场\n"
                                "② TP1减仓50%，止损移至成本\n"
                                "③ 若突破后价格在区间外横盘超过2小时，视为假突破，平仓观望\n"
                                "④ 重叠亚盘高点/低点与枢轴点/Fib位时，可信度更高"),
                "invalidation": (f"突破后价格在1-2根H1K线内回落至区间内（假突破），立即平仓\n"
                                  "区间突破方向与日线/H4趋势相反时，仓位减半，快进快出"),
                "session": "伦敦开盘（15:00-17:00 BJ）为最佳突破时段，纽约开盘（21:00-23:00 BJ）次之"
            })

    # ══════════════════════════════════════════════════════
    # 策略三：关键价位 + RSI背离反转（最强反转信号）
    # 核心逻辑：价格到达强支撑/阻力 + RSI/MACD出现背离 → 高概率反转
    # ══════════════════════════════════════════════════════
    if has_bull_div and near_sup:
        sup0 = near_sup[0]
        e_lo = round(sup0 - atr_h1 * 0.5, 1)
        e_hi = round(sup0 + atr_h1 * 0.8, 1)
        sl_v = round(sup0 - atr_h1 * 2.2, 1)
        tp1  = near_res[0] if near_res else round(price + atr_h4*2, 1)
        tp2  = near_res[1] if len(near_res)>1 else round(price + atr_h4*4, 1)
        setups.append({
            "tag": "S3", "type": "做多", "type_cls": "bull",
            "scenario": "【策略三】支撑位RSI看涨背离反转（价格新低 + RSI更高低点）",
            "probability": "较高",
            "condition": (f"H1/H4出现RSI看涨背离：价格在 {sup0:.1f} 支撑区创新低，"
                          f"但RSI形成更高的低点（不创新低），背离有效\n"
                          f"等待：H1出现阳包阴/锤子线/长下影K线确认后入场"),
            "entry": f"{e_lo} – {e_hi}（支撑区 {sup0:.1f} 附近）",
            "sl": f"{sl_v}  (背离低点下方 {sup0-sl_v:.0f} 点)",
            "tp1": f"{tp1:.1f}", "tp2": f"{tp2:.1f}",
            "rr": _rr((e_lo+e_hi)/2, sl_v, tp1),
            "management": ("① 入场后若H1收盘确认站上 EMA20，可加仓1/3\n"
                            "② TP1减仓50%，移止损至成本\n"
                            "③ 背离反弹目标通常为前高或50%回撤，不要贪"),
            "invalidation": (f"价格跌破 {sl_v:.1f} 并H1收盘确认，背离失效，立即止损\n"
                              "或RSI在支撑区再次创新低（背离信号消失），出场"),
            "session": "背离信号出现后，等下一个流动性窗口（伦敦/纽约开盘）验证"
        })

    if has_bear_div and near_res:
        res0 = near_res[0]
        e_lo = round(res0 - atr_h1 * 0.8, 1)
        e_hi = round(res0 + atr_h1 * 0.5, 1)
        sl_v = round(res0 + atr_h1 * 2.2, 1)
        tp1  = near_sup[-1] if near_sup else round(price - atr_h4*2, 1)
        tp2  = near_sup[0]  if len(near_sup)>1 else round(price - atr_h4*4, 1)
        setups.append({
            "tag": "S3", "type": "做空", "type_cls": "bear",
            "scenario": "【策略三】阻力位RSI看跌背离反转（价格新高 + RSI更低高点）",
            "probability": "较高",
            "condition": (f"H1/H4出现RSI看跌背离：价格在 {res0:.1f} 阻力区创新高，"
                          f"但RSI形成更低的高点（不创新高），背离有效\n"
                          f"等待：H1出现阴包阳/射击之星/长上影K线确认后入场"),
            "entry": f"{e_lo} – {e_hi}（阻力区 {res0:.1f} 附近）",
            "sl": f"{sl_v}  (背离高点上方 {sl_v-res0:.0f} 点)",
            "tp1": f"{tp1:.1f}", "tp2": f"{tp2:.1f}",
            "rr": _rr((e_lo+e_hi)/2, sl_v, tp1),
            "management": ("① 入场后若H1收盘确认跌破 EMA20，可加仓1/3\n"
                            "② TP1减仓50%，移止损至成本\n"
                            "③ 背离回调目标通常为前低或50%支撑，不要贪"),
            "invalidation": (f"价格突破 {sl_v:.1f} 并H1收盘确认，背离失效，立即止损\n"
                              "或RSI在阻力区再次创新高（背离信号消失），出场"),
            "session": "背离信号出现后，等下一个流动性窗口（伦敦/纽约开盘）验证"
        })

    # ══════════════════════════════════════════════════════
    # 策略四：多周期共振顺势（≥2个周期同向时触发）
    # 核心逻辑：周线/日线/H4同向共振 → 分批在回调中入场
    # ══════════════════════════════════════════════════════
    if bear_cnt >= 2:
        res0  = near_res[0]
        e_lo  = round(res0, 1)
        e_hi  = round(res0 + atr_h4 * 0.4, 1)
        sl_v  = round(res0 + atr_h4 * 1.5, 1)
        tp1   = near_sup[-1] if near_sup else round(price - atr_h4*2, 1)
        tp2   = near_sup[0]  if len(near_sup)>1 else round(price - atr_h4*4, 1)
        conf  = "高" if bear_cnt >= 3 else "较高"
        setups.append({
            "tag": "S4", "type": "做空", "type_cls": "bear",
            "scenario": f"【策略四】多周期共振做空（{bear_cnt}/3周期偏空，大势顺势）",
            "probability": conf,
            "condition": (f"周线/日线/H4 {bear_cnt}个周期偏空共振\n"
                          f"价格反弹至 {e_lo}–{e_hi} 阻力区，H1出现拒绝K线（射击之星/阴包阳）\n"
                          f"MACD柱由正转负 + KD死叉后入场"),
            "entry": f"{e_lo} – {e_hi}",
            "sl": f"{sl_v}  (+{sl_v-e_lo:.0f}，约1.5×H4 ATR)",
            "tp1": f"{tp1:.1f}", "tp2": f"{tp2:.1f}",
            "rr": _rr(e_lo, sl_v, tp1),
            "management": ("① 分批建仓：第一笔在入场区低点，第二笔等H1确认信号\n"
                            "② TP1减仓50%，移止损至成本\n"
                            "③ 剩余仓位用H4 ATR跟踪止损，顺势持有\n"
                            "④ 若价格在阻力区横盘3根以上H1K线不破，可小仓先建试探"),
            "invalidation": (f"H1收盘突破 {sl_v:.1f}（阻力上方1.5×ATR），\n"
                              "或ADX骤降至15以下（趋势瓦解），立即全部止损出场"),
            "session": "伦敦开盘（15:00-17:00）或纽约开盘（21:00-23:00）信号质量最高"
        })

    if bull_cnt >= 2:
        sup0  = near_sup[0] if near_sup else round(price - atr_h4*2, 1)
        e_lo  = round(sup0 - atr_h4 * 0.3, 1)
        e_hi  = round(sup0 + atr_h4 * 0.4, 1)
        sl_v  = round(sup0 - atr_h4 * 1.5, 1)
        tp1   = near_res[0] if near_res else round(price + atr_h4*2, 1)
        tp2   = near_res[1] if len(near_res)>1 else round(price + atr_h4*4, 1)
        conf  = "高" if bull_cnt >= 3 else "较高"
        setups.append({
            "tag": "S4", "type": "做多", "type_cls": "bull",
            "scenario": f"【策略四】多周期共振做多（{bull_cnt}/3周期偏多，大势顺势）",
            "probability": conf,
            "condition": (f"周线/日线/H4 {bull_cnt}个周期偏多共振\n"
                          f"价格回调至 {e_lo}–{e_hi} 支撑区，H1出现支撑K线（锤子线/阳包阴）\n"
                          f"MACD柱由负转正 + KD金叉后入场"),
            "entry": f"{e_lo} – {e_hi}",
            "sl": f"{sl_v}  (-{e_lo-sl_v:.0f}，约1.5×H4 ATR)",
            "tp1": f"{tp1:.1f}", "tp2": f"{tp2:.1f}",
            "rr": _rr(e_hi, sl_v, tp1),
            "management": ("① 分批建仓：第一笔在入场区高点，第二笔等H1确认信号\n"
                            "② TP1减仓50%，移止损至成本\n"
                            "③ 剩余仓位用H4 ATR跟踪止损，顺势持有\n"
                            "④ 支撑区出现第二根确认阳线时，可加仓1/3"),
            "invalidation": (f"H1收盘跌破 {sl_v:.1f}（支撑下方1.5×ATR），\n"
                              "或ADX骤降至15以下（趋势瓦解），立即全部止损出场"),
            "session": "亚洲盘（08:00-10:00 BJ）确认支撑，伦敦盘（15:00）方向启动"
        })

    # ══════════════════════════════════════════════════════
    # 策略五：区间震荡 / 无信号等待
    # ══════════════════════════════════════════════════════
    rng_lo = near_sup[0] if near_sup else round(price - atr_h4*3, 1)
    rng_hi = near_res[0] if near_res else round(price + atr_h4*3, 1)
    setups.append({
        "tag": "S5", "type": "观望", "type_cls": "neutral",
        "scenario": "【策略五】区间震荡 / 等待方向确认",
        "probability": "—",
        "condition": (f"当前区间 {rng_lo:.1f} – {rng_hi:.1f}（幅度 {rng_hi-rng_lo:.0f} 点）\n"
                      f"ADX={h4_adx:.0f}（{'趋势弱，震荡为主' if h4_adx<20 else '趋势中等'}）\n"
                      "多空信号尚不明确，不宜盲目入场"),
        "entry": "不操作，等信号",
        "sl": "—", "tp1": "—", "tp2": "—", "rr": "—",
        "management": (f"等待以下任一条件触发策略一/二/三/四：\n"
                       f"① 价格有效突破 {rng_hi:.1f} + H1收盘确认 → 做多（策略二/四）\n"
                       f"② 价格有效跌破 {rng_lo:.1f} + H1收盘确认 → 做空（策略二/四）\n"
                       f"③ 价格回调至 EMA20/50 + 背离信号出现 → 做多/空（策略一/三）\n"
                       "④ 重大经济数据（非农/CPI/FOMC）前后60分钟绝对不开新仓"),
        "invalidation": "N/A",
        "session": "任何时段均可观察，无需守盘；重点关注伦敦/纽约开盘方向"
    })

    key_levels = build_hierarchical_levels(price, near_res, near_sup, atr_h4, analyses)
    return setups, price, near_sup, near_res, key_levels


def build_hierarchical_levels(price, near_res, near_sup, atr_val, analyses):
    """
    构建分级关键价位结构（匹配 TradingView 手画图模式）：
      - 1 个多空关键位（最近的强位）
      - 4 道阻力（第1阻力 / 第2强阻力 / 第3强阻力回调看空 / 第4强阻力不破看空）
      - 4 道支撑（第1支撑 / 第2强支撑 / 第3强支撑回调看多 / 第4支撑不破看多）
    """
    # 收集更多候选位（在 generate_setups 给的 near_* 之外，再加上日线/H4 的远端 swing 与 fib）
    extra_res, extra_sup = [], []
    for key in ["daily", "h4"]:
        a = analyses.get(key, {})
        for r in a.get("resistances", []):
            if r > price:
                extra_res.append(r)
        for s in a.get("supports", []):
            if s < price:
                extra_sup.append(s)
        for v in list(a.get("fib", {}).values()):
            if v > price: extra_res.append(v)
            elif v < price: extra_sup.append(v)
        for v in list(a.get("pivots", {}).values()):
            if v > price: extra_res.append(v)
            elif v < price: extra_sup.append(v)

    all_res = sorted(set([round(r, 1) for r in list(near_res) + extra_res if r > price]))
    all_sup = sorted(set([round(s, 1) for s in list(near_sup) + extra_sup if s < price]), reverse=True)

    # 多空关键位 = 距当前价最近的强位（任一方向），需在 3×ATR 以内
    key_pivot = None
    candidates = []
    if all_res: candidates.append((all_res[0], "res"))
    if all_sup: candidates.append((all_sup[0], "sup"))
    if candidates:
        candidates.sort(key=lambda x: abs(x[0] - price))
        if abs(candidates[0][0] - price) <= atr_val * 3:
            key_pivot = candidates[0][0]

    # 排除已选作 pivot 的价位
    res_list = [r for r in all_res if r != key_pivot]
    sup_list = [s for s in all_sup if s != key_pivot]

    res_labels = ["第1阻力", "第2强阻力", "第3强阻力·回调看空", "第4强阻力·不破看空"]
    sup_labels = ["第1支撑", "第2强支撑", "第3强支撑·回调看多", "第4支撑·不破看多"]

    resistances = []
    for i, r in enumerate(res_list[:4]):
        resistances.append({
            "price": r,
            "label": res_labels[i],
            "rank":  i + 1,
            "dist":  round(r - price, 1),
            "atr_dist": round((r - price) / max(atr_val, 1e-6), 2),
        })
    supports = []
    for i, s in enumerate(sup_list[:4]):
        supports.append({
            "price": s,
            "label": sup_labels[i],
            "rank":  i + 1,
            "dist":  round(price - s, 1),
            "atr_dist": round((price - s) / max(atr_val, 1e-6), 2),
        })

    return {
        "pivot":       key_pivot,
        "pivot_above": key_pivot is not None and key_pivot > price,
        "resistances": resistances,
        "supports":    supports,
        "current":     price,
    }


# ─────────────────────────────────────────────
# 渲染 HTML 报告
# ─────────────────────────────────────────────

def render_html(analyses, setups_data, data_source="Yahoo Finance"):
    setups, price, near_sup, near_res, key_levels = setups_data
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tf_labels = [("weekly","周线"),("daily","日线"),("h4","H4"),("h1","H1")]
    tmap = {"bull":"#26a69a","bear":"#ef5350","neutral":"#9e9e9e"}

    def tag(cls, text):
        c = {"bull":"#26a69a","bear":"#ef5350","neutral":"#9e9e9e"}.get(cls,"#555")
        return f'<span style="background:{c};padding:2px 7px;border-radius:4px;font-size:11px;margin:2px;display:inline-block;white-space:nowrap">{text}</span>'

    def gauge(val, lo, hi, reverse=False):
        pct = max(0, min(100, (val - lo) / (hi - lo + 1e-10) * 100))
        if reverse: pct = 100 - pct
        col = "#ef5350" if pct > 70 else "#26a69a" if pct < 30 else "#f0c040"
        return (f'<div style="background:#222;border-radius:4px;height:6px;width:80px;display:inline-block;vertical-align:middle">'
                f'<div style="background:{col};width:{pct:.0f}%;height:100%;border-radius:4px"></div></div>'
                f' <span style="font-size:11px;color:{col}">{val}</span>')

    # ── 多周期指标表格行
    rows = ""
    for key, label in tf_labels:
        a = analyses.get(key)
        if not a: continue
        tc   = tmap.get(a["trend_cls"],"#9e9e9e")
        e200 = f'{a["ema200"]:.1f}' if a.get("ema200") else "—"
        sigs = " ".join([tag(c,t) for t,c in a.get("signals",[])]) or '<span style="color:#555">—</span>'
        score = a.get("score", 0)
        score_color = "#26a69a" if score > 15 else "#ef5350" if score < -15 else "#f0c040"
        rows += f"""<tr>
          <td style="color:#ccc;font-weight:bold">{label}</td>
          <td style="color:#fff">{a['current_price']:.2f}</td>
          <td style="color:{tc};font-weight:bold">{a['trend']}<br><span style="font-size:10px;color:#666">{a.get('trend_strength','')}</span></td>
          <td style="color:#aaa;font-size:12px">{a['ema20']:.0f}/{a['ema50']:.0f}/{e200}</td>
          <td>{gauge(a['rsi'],0,100)}</td>
          <td>{gauge(a['stoch_k'],0,100)}<br><span style="font-size:10px;color:#555">D:{a['stoch_d']:.0f}</span></td>
          <td style="color:{'#26a69a' if a['adx']>25 else '#888'}">{a['adx']:.0f}<br>
              <span style="font-size:10px;color:#26a69a">+{a['di_p']:.0f}</span>/<span style="font-size:10px;color:#ef5350">-{a['di_m']:.0f}</span></td>
          <td style="color:{'#ef5350' if a['cci']>100 else '#26a69a' if a['cci']<-100 else '#aaa'}">{a['cci']:.0f}</td>
          <td style="color:{'#26a69a' if a['macd_hist']>0 else '#ef5350'}">{a['macd_hist']:.1f}</td>
          <td style="font-size:12px;color:#aaa">{a['atr']:.1f}<br><span style="color:#666">{a['atr_pct']:.2f}%</span></td>
          <td style="color:{score_color};font-weight:bold">{'+' if score>0 else ''}{score}</td>
          <td style="max-width:200px">{sigs}</td>
        </tr>"""

    # ── 分级关键价位（ladder 布局，匹配 TradingView 手画图模式）
    def _ladder_row(label, price_val, role, highlight=False):
        if role == "res":
            color = "#ef5350"
            bg = "linear-gradient(90deg,#1a0a0a 0%,#0e0e1e 100%)"
        elif role == "sup":
            color = "#26a69a"
            bg = "linear-gradient(90deg,#0a1a14 0%,#0e0e1e 100%)"
        elif role == "pivot":
            color = "#f0c040"
            bg = "linear-gradient(90deg,#1a1410 0%,#0e0e1e 100%)"
        else:  # current
            color = "#fff"
            bg = "#1a1a2e"
        marker = "★" if role == "pivot" else ("▼" if role == "current" else "")
        weight = "bold" if highlight or role in ("pivot", "current") else "normal"
        font_size = "15px" if role in ("pivot", "current") else "13px"
        border = "2px solid " + color if role in ("pivot", "current") else f"1px solid {color}33"
        return (f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:8px 12px;background:{bg};border-left:{border};border-radius:4px;'
                f'margin:3px 0;font-size:{font_size};font-weight:{weight}">'
                f'<span style="color:{color}">{marker} {label}</span>'
                f'<span style="color:{color};font-family:monospace">${price_val:.2f}</span>'
                f'</div>')

    ladder_items = []
    # 自上而下：第4阻力 → 第1阻力 → 多空关键位（如果在上方）→ 当前价 → 多空关键位（如果在下方）→ 第1支撑 → 第4支撑
    for r in reversed(key_levels["resistances"]):  # 远 → 近（自顶向下）
        ladder_items.append(_ladder_row(f"{r['label']}（{r['atr_dist']}×ATR）", r["price"], "res"))
    if key_levels["pivot"] is not None and key_levels["pivot_above"]:
        ladder_items.append(_ladder_row("多空关键位", key_levels["pivot"], "pivot"))
    ladder_items.append(_ladder_row("当前价", price, "current"))
    if key_levels["pivot"] is not None and not key_levels["pivot_above"]:
        ladder_items.append(_ladder_row("多空关键位", key_levels["pivot"], "pivot"))
    for s in key_levels["supports"]:  # 近 → 远（自上向下）
        ladder_items.append(_ladder_row(f"{s['label']}（{s['atr_dist']}×ATR）", s["price"], "sup"))

    level_ladder_html = "".join(ladder_items) if ladder_items else "<p style='color:#666'>数据不足</p>"

    # ── 枢轴点（日线）
    pivot_html = ""
    daily_a = analyses.get("daily", {})
    pvts = daily_a.get("pivots", {})
    if pvts:
        p_val = pvts.get("P", price)
        def pc(v):
            c = "#ef5350" if v > p_val else "#26a69a"
            marker = " ◀" if abs(v - price) < (price * 0.005) else ""
            return f'<td style="text-align:center;color:{c};font-weight:bold">{v}{marker}</td>'
        pivot_html = f"""<table style="text-align:center">
          <tr>
            <th style="color:#ef5350">R3</th><th style="color:#ef5350">R2</th><th style="color:#ef5350">R1</th>
            <th style="color:#f0c040">Pivot</th>
            <th style="color:#26a69a">S1</th><th style="color:#26a69a">S2</th><th style="color:#26a69a">S3</th>
          </tr><tr>
            {pc(pvts.get('R3',0))}{pc(pvts.get('R2',0))}{pc(pvts.get('R1',0))}
            <td style="text-align:center;color:#f0c040;font-weight:bold">{pvts.get('P',0)}</td>
            {pc(pvts.get('S1',0))}{pc(pvts.get('S2',0))}{pc(pvts.get('S3',0))}
          </tr></table>"""

    # ── 斐波那契（H4）
    fib_html = ""
    h4_a = analyses.get("h4", {})
    fibs = h4_a.get("fib", {})
    fib_h = h4_a.get("fib_high", 0)
    fib_l = h4_a.get("fib_low", 0)
    if fibs:
        fib_rows = ""
        key_ratios = ["100%","78.6%","61.8%","50.0%","38.2%","23.6%","0.0%"]
        for k in key_ratios:
            v = fibs.get(k, 0)
            is_near = abs(v - price) < (price * 0.008)
            row_style = "background:#1e2a1e" if is_near else ""
            vc = "#ef5350" if v > price else "#26a69a"
            marker = "  ← 当前价附近" if is_near else ""
            fib_rows += f'<tr style="{row_style}"><td style="color:#888">{k}</td><td style="color:{vc};font-weight:bold">{v}{marker}</td></tr>'
        fib_html = f"""<p style="color:#666;font-size:12px;margin-bottom:8px">
            区间高点 {fib_h} → 低点 {fib_l}（H4近60根K线）</p>
            <table style="width:300px">{fib_rows}</table>"""

    # ── 增强版策略卡片
    setup_cards = ""
    for s in setups:
        border   = tmap.get(s["type_cls"],"#555")
        badge_bg = {"bull":"#26a69a","bear":"#ef5350","neutral":"#555"}.get(s["type_cls"],"#555")
        prob     = s.get("probability","—")
        prob_c   = "#26a69a" if prob == "高" else "#f0c040" if prob == "较高" else "#888"
        mgmt     = s.get("management","—").replace("\n","<br>")
        invld    = s.get("invalidation","—")
        session  = s.get("session","—")
        rr_val   = s.get("rr","—")
        setup_cards += f"""
        <div style="border:1px solid {border};border-radius:10px;padding:18px;margin-bottom:16px;background:#0f0f20">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap">
            <span style="background:{badge_bg};padding:4px 14px;border-radius:5px;font-weight:bold;font-size:14px">{s['type']}</span>
            <span style="color:#ddd;font-size:15px;font-weight:500">{s['scenario']}</span>
            <span style="margin-left:auto;background:#1a1a30;padding:3px 10px;border-radius:4px;font-size:12px">
              把握度 <span style="color:{prob_c};font-weight:bold">{prob}</span>
            </span>
          </div>
          <table style="width:100%;font-size:13px;border-collapse:collapse">
            <tr style="border-bottom:1px solid #1a1a2a">
              <td style="width:90px;color:#666;padding:6px 8px">触发条件</td>
              <td style="color:#ccc;padding:6px 8px">{s['condition']}</td>
            </tr>
            <tr style="border-bottom:1px solid #1a1a2a">
              <td style="color:#666;padding:6px 8px">入场区域</td>
              <td style="color:#fff;font-weight:bold;font-size:15px;padding:6px 8px">{s['entry']}</td>
            </tr>
            <tr style="border-bottom:1px solid #1a1a2a">
              <td style="color:#666;padding:6px 8px">止损</td>
              <td style="color:#ef5350;padding:6px 8px">{s['sl']}</td>
            </tr>
            <tr style="border-bottom:1px solid #1a1a2a">
              <td style="color:#666;padding:6px 8px">目标 TP1/2</td>
              <td style="color:#26a69a;font-weight:bold;padding:6px 8px">{s['tp1']} &nbsp;/&nbsp; {s['tp2']}</td>
            </tr>
            <tr style="border-bottom:1px solid #1a1a2a">
              <td style="color:#666;padding:6px 8px">风险回报</td>
              <td style="color:#f0c040;font-weight:bold;padding:6px 8px">{rr_val}</td>
            </tr>
            <tr style="border-bottom:1px solid #1a1a2a">
              <td style="color:#666;padding:6px 8px;vertical-align:top">持仓管理</td>
              <td style="color:#aaa;padding:6px 8px;line-height:1.7">{mgmt}</td>
            </tr>
            <tr style="border-bottom:1px solid #1a1a2a">
              <td style="color:#666;padding:6px 8px;vertical-align:top">失效条件</td>
              <td style="color:#ef5350;padding:6px 8px;font-size:12px">{invld}</td>
            </tr>
            <tr>
              <td style="color:#666;padding:6px 8px">建议时段</td>
              <td style="color:#888;padding:6px 8px;font-size:12px">{session}</td>
            </tr>
          </table>
        </div>"""

    # ── 预计算概览值
    h4_a      = analyses.get("h4", {})
    daily_a   = analyses.get("daily", {})
    weekly_a  = analyses.get("weekly", {})
    h4_cls    = h4_a.get("trend_cls","neutral")
    h4_score  = h4_a.get("score", 0)
    sc        = "#26a69a" if h4_score > 15 else "#ef5350" if h4_score < -15 else "#f0c040"
    atr_disp  = f'{h4_a.get("atr",0):.1f} ({h4_a.get("atr_pct",0):.2f}%)'
    adx_disp  = f'{h4_a.get("adx",0):.0f} — {h4_a.get("trend_strength","")}'
    stoch_disp= f'K:{h4_a.get("stoch_k",0):.0f} D:{h4_a.get("stoch_d",0):.0f}'
    cci_disp  = f'{h4_a.get("cci",0):.0f}'
    near_res_str = f"{near_res[0]:.1f}" if near_res else "—"
    near_sup_str = f"{near_sup[0]:.1f}" if near_sup else "—"
    weekly_trend_val = weekly_a.get("trend","—")
    wtc = tmap.get(weekly_a.get("trend_cls","neutral"),"#9e9e9e")
    daily_trend_val  = daily_a.get("trend","—")
    dtc = tmap.get(daily_a.get("trend_cls","neutral"),"#9e9e9e")
    h4_trend_val     = h4_a.get("trend","—")
    htc = tmap.get(h4_cls,"#9e9e9e")

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>XAU/USD 行情分析</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0a0a18;color:#ddd;font-family:'Segoe UI',Arial,sans-serif;padding:20px;max-width:1400px;margin:0 auto}}
    h1{{color:#f0c040;font-size:20px;margin-bottom:3px}}
    h2{{color:#555;font-size:13px;margin-bottom:20px;font-weight:normal}}
    h3{{color:#e0e0e0;font-size:14px;margin:0 0 12px;border-left:3px solid #f0c040;padding-left:9px}}
    .card{{background:#111125;border-radius:10px;padding:18px;margin-bottom:16px;border:1px solid #1e1e35}}
    table{{width:100%;border-collapse:collapse;font-size:12px}}
    th{{background:#16162a;color:#666;padding:7px 9px;text-align:left;font-weight:normal;border-bottom:1px solid #222}}
    td{{padding:7px 9px;border-bottom:1px solid #141426;vertical-align:middle}}
    tr:last-child td{{border-bottom:none}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px}}
    .box{{background:#16162e;border-radius:8px;padding:12px;text-align:center;border:1px solid #1e1e40}}
    .box .v{{font-size:20px;font-weight:bold;margin-bottom:3px}}
    .box .l{{font-size:10px;color:#555}}
    .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
    @media(max-width:700px){{.two-col{{grid-template-columns:1fr}}}}
    .footer{{text-align:center;color:#333;font-size:11px;margin-top:24px}}
  </style>
</head>
<body>
  <h1>XAU/USD 黄金日内波段分析报告</h1>
  <h2>生成时间：{now}　|　数据来源：{data_source}</h2>

  <!-- ① 价格 + 核心数据 -->
  <div class="card" style="text-align:center;padding:22px 0">
    <div style="font-size:11px;color:#555;letter-spacing:3px">XAU / USD &nbsp;·&nbsp; 黄金现货</div>
    <div style="font-size:52px;font-weight:bold;color:#f0c040;margin:6px 0">${price:.2f}</div>
    <div style="font-size:12px;color:#444">
      ATR(H4): {atr_disp} &nbsp;|&nbsp;
      综合评分: <span style="color:{sc};font-weight:bold">{'+' if h4_score>0 else ''}{h4_score}</span> &nbsp;|&nbsp;
      周线 <span style="color:{wtc}">{weekly_trend_val}</span> &nbsp;/&nbsp;
      日线 <span style="color:{dtc}">{daily_trend_val}</span> &nbsp;/&nbsp;
      H4 <span style="color:{htc}">{h4_trend_val}</span>
    </div>
  </div>

  <!-- ② 多周期共振速览 -->
  <div class="card">
    <h3>多周期趋势共振 &amp; 核心指标</h3>
    <div class="grid">
      <div class="box"><div class="v" style="color:{wtc}">{weekly_trend_val}</div><div class="l">周线趋势</div></div>
      <div class="box"><div class="v" style="color:{dtc}">{daily_trend_val}</div><div class="l">日线趋势</div></div>
      <div class="box"><div class="v" style="color:{htc}">{h4_trend_val}</div><div class="l">H4趋势</div></div>
      <div class="box"><div class="v" style="color:#aaa;font-size:15px">{adx_disp}</div><div class="l">H4 ADX（趋势强度）</div></div>
      <div class="box"><div class="v" style="color:#f0c040">{stoch_disp}</div><div class="l">H4 Stoch K/D</div></div>
      <div class="box"><div class="v" style="color:{'#ef5350' if h4_a.get('cci',0)>100 else '#26a69a' if h4_a.get('cci',0)<-100 else '#aaa'}">{cci_disp}</div><div class="l">H4 CCI</div></div>
      <div class="box"><div class="v" style="color:#ef5350">{near_res_str}</div><div class="l">最近阻力</div></div>
      <div class="box"><div class="v" style="color:#26a69a">{near_sup_str}</div><div class="l">最近支撑</div></div>
    </div>
  </div>

  <!-- ③ 日内波段策略（核心内容，置顶）-->
  <div class="card">
    <h3>日内波段介入策略 &amp; 各情景应对</h3>
    <div style="font-size:12px;color:#555;margin-bottom:14px;line-height:1.8">
      策略优先级：
      <span style="color:#f0c040">S1 趋势EMA回调</span>（最高胜率）&gt;
      <span style="color:#26a69a">S3 RSI背离反转</span>（最强反转）&gt;
      <span style="color:#aaa">S4 多周期共振</span>（大势顺势）&gt;
      <span style="color:#888">S2 亚盘区间突破</span>（开盘方向）&gt;
      <span style="color:#555">S5 等待观望</span>
    </div>
    {setup_cards}
  </div>

  <!-- ④ 关键价位 + 枢轴点 -->
  <div class="two-col">
    <div class="card">
      <h3>分级关键价位（多空梯）</h3>
      <div style="font-size:11px;color:#666;margin-bottom:10px;line-height:1.6">
        ★ <span style="color:#f0c040">多空关键位</span>：当前价附近最强转折，破则趋势翻转
        &nbsp;|&nbsp; <span style="color:#ef5350">回调看空</span>：到位反弹做空
        &nbsp;|&nbsp; <span style="color:#ef5350">不破看空</span>：守位以下看空
        &nbsp;|&nbsp; <span style="color:#26a69a">回调看多</span>：到位回踩做多
        &nbsp;|&nbsp; <span style="color:#26a69a">不破看多</span>：守位以上看多
      </div>
      {level_ladder_html}
    </div>
    <div class="card">
      <h3>日线枢轴点 (Pivot Points)</h3>
      {pivot_html if pivot_html else '<p style="color:#555;font-size:13px">数据不足</p>'}
    </div>
  </div>

  <!-- ⑤ 斐波那契 -->
  <div class="card">
    <h3>斐波那契回撤位（H4）</h3>
    {fib_html if fib_html else '<p style="color:#555;font-size:13px">数据不足</p>'}
  </div>

  <!-- ⑥ 风险控制 -->
  <div class="card" style="background:#0a150a;border-color:#1a301a">
    <h3>风险控制 &amp; 操作纪律</h3>
    <table style="font-size:13px">
      <tr><td style="color:#666;width:140px">单笔最大风险</td><td>账户净值的 <strong style="color:#f0c040">1%</strong>（激进不超过2%）</td></tr>
      <tr><td style="color:#666">仓位公式</td><td style="color:#aaa">手数 = (账户 × 风险%) ÷ (止损点数 × 每点价值)</td></tr>
      <tr><td style="color:#666">入场纪律</td><td style="color:#aaa">必须等 H1 K线收盘确认再入场，不在K线运行中追单</td></tr>
      <tr><td style="color:#666">移动止损</td><td style="color:#aaa">到达TP1后立即将止损移至成本价，锁定无风险持仓</td></tr>
      <tr><td style="color:#666">回避时段</td><td style="color:#aaa">重大数据（非农/CPI/FOMC/美联储讲话）前后 <strong style="color:#f0c040">60分钟</strong> 不开新仓</td></tr>
      <tr><td style="color:#666">连亏处理</td><td style="color:#aaa">连续亏损3次后当日停止交易，复盘后次日再战</td></tr>
      <tr><td style="color:#666">黑天鹅</td><td style="color:#aaa">地缘政治突发事件可导致价格瞬间跳空，务必设置硬止损</td></tr>
    </table>
  </div>

  <!-- ⑦ 技术指标详表（分析根据，置底）-->
  <div class="card">
    <h3>技术指标详表（分析依据）</h3>
    <div style="overflow-x:auto">
    <table>
      <thead><tr>
        <th>周期</th><th>价格</th><th>趋势</th><th>EMA 20/50/200</th>
        <th>RSI(14)</th><th>Stoch K/D</th><th>ADX/DI</th>
        <th>CCI</th><th>MACD柱</th><th>ATR</th><th>评分</th><th>信号</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
    </div>
  </div>

  <div class="footer">XAU/USD Analysis Bot · 自动生成于 {now}</div>
</body>
</html>"""

    return html

# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────

def run_gold_analysis(open_browser=True):
    data, source = fetch_data()
    if not data:
        print("错误：无法获取行情数据，请检查网络连接或 MT4 是否运行")
        return None

    analyses = {}
    label_map = {"weekly":"周线","daily":"日线","h4":"H4","h1":"H1"}
    for key, df in data.items():
        if len(df) < 20:
            print(f"  跳过 {key}（数据不足）")
            continue
        try:
            analyses[key] = analyze_timeframe(df, label_map.get(key, key))
        except Exception as e:
            print(f"  分析 {key} 出错: {e}")

    df_h1 = data.get("h1")
    setups_data = generate_setups(analyses, df_h1=df_h1)
    html_content = render_html(analyses, setups_data, source)

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    report_path = os.path.join(REPORT_DIR, f"gold_analysis_{ts}.html")
    latest_path = os.path.join(REPORT_DIR, "gold_latest.html")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    cleanup_old_reports(keep=10)

    print(f"\n[OK] 报告已生成: {report_path}")
    print(f"[>>] 最新报告: {latest_path}")
    if open_browser:
        try:
            os.startfile(latest_path)
        except Exception:
            webbrowser.open(f"file:///{latest_path.replace(os.sep, '/')}")
    return latest_path


def main():
    return run_gold_analysis(open_browser=True)


# ─────────────────────────────────────────────
# 自动清理旧报告
# ─────────────────────────────────────────────

def cleanup_old_reports(keep=10):
    """
    保留最新 keep 份带时间戳的报告，删除多余的旧文件。
    gold_latest.html 始终保留，不计入 keep 数量。
    """
    import glob
    pattern = os.path.join(REPORT_DIR, "gold_analysis_*.html")
    files = sorted(glob.glob(pattern))          # 按文件名（含时间戳）升序
    to_delete = files[:-keep] if len(files) > keep else []
    for f in to_delete:
        try:
            os.remove(f)
        except OSError:
            pass
    if to_delete:
        print(f"[清理] 删除 {len(to_delete)} 份旧报告，保留最新 {keep} 份")


if __name__ == "__main__":
    main()
