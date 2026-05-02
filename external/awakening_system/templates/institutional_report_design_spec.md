---
title: XAU/USD 日内波段机构版报告 — 板块设计规格
version: v1.0-DRAFT
audience: Forex / Gold Intraday Swing Desk
benchmark: GS FX Strategy · JPM Cross-Asset · Citi FX Daily · SocGen Multi-Asset
status: 待审定（确认后据此生成 institutional_report_template.html）
last_updated: 2026-04-27
---

# 设计总则

## 1. 顶级机构报告的共性
- **结论先行 (Lead with the call)**：首屏必给 *Bias / Catalyst / Action*，其余皆为论据。
- **数据契约 (Data Contract)**：每个数字都要有 *来源 · 时效戳 · 计算口径*，不允许"裸数字"。
- **可证伪 (Falsifiability)**：每个观点必有 *Invalidation Trigger*（价格/事件级别都要写出）。
- **可执行 (Actionable)**：策略段必须给出 *Entry / SL / TP / Size / R · Kelly 上限 / Kill Criteria*。
- **可审计 (Auditable)**：报告底部必有 *REF 编号 / 模型版本 / 数据源 / 利益冲突披露 / 免责声明*。
- **节奏化 (Cadenced)**：日内报告以 *Killzone* 为时序主轴，而不是简单按周期排序。

## 2. 视觉与排版约束
- 暗金主题保留（沿用现有 `--gold #C9A84C`、`--bull #00C896`、`--bear #FF4D6D`）。
- 字体：`'Inter','Microsoft YaHei'` 正文 / `'JetBrains Mono','Menlo'` 数字 / `'Playfair Display'` 标题点缀。
- **A4 横向打印宽度 1280px**；移动端不优先；屏幕 + PDF 一致。
- 任何数字字段右对齐、等宽字体、保留固定小数位（金价 2 位、R:R 2 位、% 2 位、Z-score 2 位）。
- 颜色不承担信息单一性：每条着色条目同时附带 ▲/▼/● 形状（色盲合规）。

## 3. 全局命名与编号
- 报告编号：`GLD-INTRADAY-YYYYMMDD-HHmm-{seq}`，例：`GLD-INTRADAY-20260427-1320-001`。
- 板块编号：罗马 I–XII（替代现 A–G）。
- 信号 ID：`SIG-{TF}-{TYPE}-{n}`，例：`SIG-H1-OB-03`。

---

# 板块清单（共 12 节 + 头尾）

| # | 板块 | 锚点 | 一句话定位 |
|---|---|---|---|
| 00 | **Cover · 封面与签发** | `#cover` | 机构身份 / 报告编号 / 签发时间 / 责任人 |
| 01 | **Executive Summary · TL;DR** | `#tldr` | 3 行 desk note：偏置 / 催化 / 操作 |
| 02 | **Market Snapshot · 行情快照** | `#snap` | 报价 / 24H 变动 / Bias Gauge / Session 钟 |
| 03 | **Macro Anchors · 宏观锚定** | `#macro` | DXY / 实际利率 / BEI / VIX / Oil / BTC / COT / ETF |
| 04 | **Event Risk · 事件日历** | `#calendar` | 未来 24H 高影响事件 + 禁交易窗口 |
| 05 | **Multi-TF Bias Matrix · 多周期偏置矩阵** | `#bias` | D1 / H4 / H1 / M15 × 8 维结构指标 |
| 06 | **Volatility & Session Profile · 波动与节奏** | `#vol` | EDR / RV-IV / ATR / Killzone 时序 |
| 07 | **SMC / ICT Structure Map · 结构图** | `#smc` | OB / FVG / BB / MSS / Premium-Discount |
| 08 | **Liquidity Map · 流动性地图** | `#liq` | SSL / BSL / Equal H-L / Asia Range / Judas |
| 09 | **Price Ladder · 阶梯关键位** | `#ladder` | 上下 ±1% 内带置信度的合流位 |
| 10 | **Trade Plans · 执行单** | `#plan` | A 多 / B 空 / C 区间，含头寸计算 + EV |
| 11 | **Scenario Tree · 概率树** | `#scenario` | 3 路径 × 触发 / 失效 / 跟进 / EV |
| 12 | **Risk Protocol & Checklist · 风控** | `#risk` | Pre / In / Post Trade 三段勾选清单 |
| 99 | **Audit & Disclosures · 审计披露** | `#audit` | 数据源 / 模型版本 / 利益冲突 / 免责 |

---

# 00 · Cover · 封面与签发

**目的**：让任何审计员在 5 秒内识别是谁、何时、为何发布。

**字段**

| 字段 | 类型 | 来源 | 示例 |
|---|---|---|---|
| `desk_name` | str | config | "GoldDesk · Intraday Swing" |
| `report_ref` | str | autogen | `GLD-INTRADAY-20260427-1320-001` |
| `instrument` | str | const | `XAU/USD (Spot Gold)` |
| `issued_at` | datetime (UTC+8) | system | `2026-04-27 13:20:00` |
| `valid_until` | datetime | issued_at + 24h | `2026-04-28 13:20:00` |
| `analyst` | str | config | "Quant Desk · Model v3.4.1" |
| `data_freshness` | dict | feeds | `{MT4: 2s ago, DXY: 11s, Reuters: 28s}` |
| `classification` | enum | const | `INTERNAL · NOT FOR REDISTRIBUTION` |

**视觉草图**

```
┌─────────────────────────────────────────────────────────────────┐
│ GOLD■DESK     XAU/USD INTRADAY SWING REPORT                     │
│ ─────────────                                                   │
│ REF  GLD-INTRADAY-20260427-1320-001    ISSUED  Mon 13:20 UTC+8 │
│ DESK Quant Model v3.4.1                VALID   24H              │
│ FEED MT4 ●2s   Reuters ●28s   FRED ●1m  ←color=fresh/stale     │
│                                                                 │
│ CLASSIFICATION  ▌INTERNAL · NOT FOR REDISTRIBUTION▐             │
└─────────────────────────────────────────────────────────────────┘
```

---

# 01 · Executive Summary (TL;DR)

**目的**：替代当前的 hero 文案，让交易员在屏幕滚动前就拿到结论。

**字段（严格 3 段）**

| 段 | 字段 | 约束 |
|---|---|---|
| `bias` | `direction ∈ {long, short, neutral}` + `score ∈ [-10, +10]` + `regime ∈ {trending, ranging, breakout, distribution}` | 必填 |
| `catalyst` | 自然语言 ≤ 30 字 + 关联事件 ID 列表 | 必填 |
| `action` | `recommended ∈ {execute, stalk, stand-aside}` + `primary_plan_ref` | 必填 |

**视觉草图**

```
╔═══ I · EXECUTIVE SUMMARY ════════════════════════════════════╗
║                                                               ║
║  BIAS       ▼ CAUTIOUSLY BEARISH    Score  -1.2 / 10          ║
║             Regime: RANGING (post-impulse digestion)          ║
║                                                               ║
║  CATALYST   H4 BOS down + DXY soft,  US 10Y real ↑ caps gold ║
║             linked: EVT-FOMC-MIN, EVT-US-CPI-PRELIM           ║
║                                                               ║
║  ACTION     ◇ STAND-ASIDE  until price reclaims $4727.8       ║
║             or sweeps $4668-$4672 SSL.                        ║
║             Primary plan → SIG-H1-OB-03 (short)               ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

---

# 02 · Market Snapshot · 行情快照

替代现有 hero-grid，但**信息密度提升**。

**4 列 × 2 行 网格**

| 列 | 行 1 | 行 2 |
|---|---|---|
| **Price** | 报价 + 24H 变动 + 闪烁 LIVE | OHLC (D1) `O / H / L / C` |
| **Bias Gauge** | -10/+10 滑针 + 数值 | 4 周期一致性条 (D/H4/H1/M15) |
| **Volatility** | 当前 ATR(14, M15) + 24H Range | EDR 消耗 % + Realized Vol 5D |
| **Session** | 三段 Killzone 钟（亚/伦/纽，高亮当前） | 距下一个 Killzone Open 倒计时 |

**关键计算**

- `bias_score = w_d·sign_D + w_h4·sign_H4 + w_h1·sign_H1 + w_m15·sign_M15`，权重 `(0.4, 0.3, 0.2, 0.1)`，sign 取 `{-1, 0, +1}` × 强度系数 `[0,1]`。
- `EDR_used_pct = (today_high - today_low) / EDR_20d × 100`。EDR_20d = 过去 20 个交易日日内极差均值。
- `RV_5D = std(log_returns_M15) × sqrt(96 × 5) × 100%`。

**视觉草图**

```
┌────────────┬────────────┬────────────┬────────────┐
│ XAU/USD    │ BIAS       │ VOLATILITY │ SESSION    │
│ $4,717.85  │ ─●─┼────   │ ATR  7.0   │ [ASIA] EU  │
│ ▲ +43.60   │ -1.2 /10   │ EDR  73%   │ NY         │
│ +0.93% 24H │ ◐CONFLICT  │ RV5D 14.2% │ →London    │
├────────────┼────────────┼────────────┼────────────┤
│ O 4674.25  │ D ▲ H4 ▼   │ 24H Rng    │ open in    │
│ H 4731.20  │ H1 ◐ M15 ◐ │ 82.6 pt    │  01h 40m   │
│ L 4664.00  │            │            │            │
└────────────┴────────────┴────────────┴────────────┘
```

---

# 03 · Macro Anchors · 宏观锚定

**目的**：把"金价 ≈ -DXY -RealYield +VIX +ETF 持仓"这一框架完整落到表上，每个驱动给 **当前值 / Δ / Z-score(60D) / 与金价 60D 滚动 β / 影响方向**。

**字段表（每个驱动一行）**

| 字段 | 类型 | 备注 |
|---|---|---|
| `name` | str | DXY / US10Y Real / BEI 10Y / VIX / WTI / BTC / GLD AUM Δ / CFTC Net Long |
| `value` | float | 当前 |
| `delta_24h` | float | 绝对 Δ |
| `delta_pct_24h` | float | %Δ |
| `zscore_60d` | float | 偏离度 |
| `beta_to_xau_60d` | float | OLS 滚动 β |
| `impact` | enum | `bullish_gold / bearish_gold / neutral` |
| `weight` | float | 综合 bias 时的权重 |
| `source` | str | Reuters / FRED / CFTC / WGC |
| `staleness_sec` | int | 秒 |

**新增（机构必备，现报告缺）**

- **TIPS 5y5y 远期实际利率**：黄金最强解释变量之一。
- **ETF 持仓 24H Δ (GLD + IAU + 中国 ETF)**：买盘真金白银。
- **CFTC 非商业净多 (Managed Money)**：周更，但放进周对比。
- **央行购金月度速读**：WGC 数据，影响中长期 floor。
- **跨资产相关性热力图 (60D)**：XAU vs DXY / SPX / WTI / BTC / UST。

**视觉草图**

```
III · MACRO ANCHORS ─────────────────────────────────────
┌──────────────┬─────────┬────────┬────────┬──────┬─────────┐
│ DRIVER       │ VALUE   │ Δ24H   │ Z-60D  │ β→XAU│ IMPACT  │
├──────────────┼─────────┼────────┼────────┼──────┼─────────┤
│ DXY          │ 99.20   │ -0.35% │ -1.8 ◀ │ -0.78│ ▲ BULL  │
│ US10Y Real   │ +1.85%  │ +4 bp  │ +0.6   │ -0.62│ ▼ BEAR  │
│ BEI 10Y      │ 2.42%   │ +1 bp  │ +0.2   │ +0.31│ ● NEU   │
│ TIPS 5y5y    │ +1.92%  │ +2 bp  │ +0.4   │ -0.55│ ▼ BEAR  │
│ VIX          │ 18.4    │ +1.2   │ +0.9   │ +0.28│ ▲ BULL  │
│ WTI          │ 71.8    │ -0.6%  │ -0.3   │ +0.18│ ● NEU   │
│ BTC          │ 68,420  │ +1.1%  │ +0.7   │ +0.41│ ● NEU   │
│ GLD ETF AUM  │ 911.2 t │ +2.8 t │ +1.2   │  —   │ ▲ BULL  │
│ CFTC Net Long│ 248k    │ +12k W │ +1.4 ▶ │  —   │ ▲ BULL  │
└──────────────┴─────────┴────────┴────────┴──────┴─────────┘

CORRELATION HEATMAP (60D rolling)         AGGREGATE
       DXY  SPX  WTI  BTC  10Y          ┌──────────────┐
XAU   -.78 +.12 +.18 +.41 -.62          │ Macro Bias    │
                                         │  +2.1 / 10    │
                                         │  ▲ MILD BULL  │
                                         └──────────────┘
```

---

# 04 · Event Risk · 事件日历

**字段表**

| 字段 | 类型 |
|---|---|
| `time_local` | datetime UTC+8 |
| `time_to_event` | duration |
| `country` | iso |
| `event_name` | str |
| `impact` | `{HIGH, MED, LOW}` |
| `forecast / previous / actual` | float / null |
| `embargo_window` | `(t-15min, t+30min)` 内禁开新仓 |
| `historical_xau_avg_move` | float (pt) |

**视觉**：彩色左边条（HIGH=red, MED=amber, LOW=grey），并在 timeline 上标出当前价格距事件的"窗口"。

```
┌─ 14:30 (UTC+8) ──── 01h 10m ──┐ HIGH  US Core PCE   ┌ Fcst 0.3%  Prev 0.3%
│  ⛔ EMBARGO 14:15-15:00       │       Hist avg ±18pt
└──────────────────────────────┘
```

**新增**：
- **央行讲话**：Powell / Lagarde / 鲍威尔半年报告。
- **拍卖**：US 10Y / 30Y 拍卖结果。
- **地缘** Headline Risk：自然语言 + 来源链接（Reuters / BBG）。

---

# 05 · Multi-TF Bias Matrix

**核心创新**：把现在零散的 pill 改成 **4 周期 × 8 维**矩阵，一眼看出共识与冲突。

**矩阵列**

| 维度 | 取值 | 计算 |
|---|---|---|
| `Trend` | ▲▼● | EMA(20/50/200) stack |
| `BOS` | last side / time | 最近一次 break of structure |
| `CHoCH` | last side / time | 最近一次 change of character |
| `Premium/Discount` | 0–100% | 当前价格在 last range 中的位置 |
| `VWAP Dev` | σ | 距日内 VWAP 偏离 |
| `RSI(14) Regime` | OB/OS/Mid | |
| `ATR Regime` | H/M/L vs 20D | |
| `Volume / OI` | ▲▼● | tick volume proxy |

**视觉**

```
V · MULTI-TF BIAS MATRIX
            │ Trend │ BOS    │ CHoCH  │ P/D    │ VWAP σ │ RSI    │ ATR  │ Vol │
────────────┼───────┼────────┼────────┼────────┼────────┼────────┼──────┼─────┤
D1          │  ▲    │ ▲ 04/22│  —     │ 71% PRE│ +0.6   │ 58 Mid │ HIGH │  ▲  │
H4          │  ▼    │ ▼ 04/26│ ▼04/26 │ 38% DIS│ -0.4   │ 44 Mid │ HIGH │  ▲  │
H1          │  ●    │ ▲ 04/27│ ▼04/27 │ 52% MID│ +0.1   │ 51 Mid │ MED  │  ●  │
M15         │  ●    │ ▼ 13:05│  —     │ 48% MID│ -0.2   │ 49 Mid │ LOW  │  ●  │
────────────┴───────┴────────┴────────┴────────┴────────┴────────┴──────┴─────┘
CONSENSUS: 25% BULL · 50% BEAR · 25% NEU   →  ◐ CONFLICTED · stand-aside default
```

---

# 06 · Volatility & Session Profile

**目的**：日内波段成败的一半是节奏。本节解决"今天还剩多少波动 / 哪个 Killzone 是肉 / 现在该不该开仓"。

**字段**

- `EDR_20d`、`EDR_used_pct`、`EDR_remaining_pt`
- `RV_intraday`（M15 已实现波动 annualized）
- `IV_1w` (CME GLD options ATM IV，可选)
- `ATR_M15 / H1 / H4 / D1`
- **Killzone 表**：Asia (08:00-12:00) / London Open (15:00-17:00) / NY Open (21:30-23:30) / NY PM (01:00-03:00)，每段给 **历史均幅 / 命中率 / Sweep 概率**。

**视觉**

```
VI · VOLATILITY & SESSION CADENCE

EDR (20D)  ████████████████████░░░░░░░  73% used  · 30.7 pt left
                                          ▲ caution: late-day mean-reversion bias

          08:00      15:00      21:30      03:00 (next)
ASIA      ████░░░░░░░░░░░░░░░░░░░░░░░  current ●
LONDON    ░░░░░░░░░██████░░░░░░░░░░░░  hist avg 38pt · sweep prob 62%
NY OPEN   ░░░░░░░░░░░░░░░░░░░██████░░  hist avg 45pt · sweep prob 71% ★
NY PM     ░░░░░░░░░░░░░░░░░░░░░░░░░██  hist avg 18pt

ATR     M15  7.0   H1  18.4   H4  46.2   D1  82.6
RV(5D)  14.2%       IV(1W) 16.8%        Skew  -2.1 (put-rich)
```

---

# 07 · SMC / ICT Structure Map

**目的**：把现有 SMC 卡片做成专业图谱，每个元素带置信度与失效条件。

**实体类型**

| 类型 | 字段 |
|---|---|
| **Order Block (OB)** | `id, side(bull/bear), tf, top, bot, created_at, mitigated_pct, strength(1-5), invalidation` |
| **Fair Value Gap (FVG)** | `id, side, tf, top, bot, filled_pct, age_bars` |
| **Breaker Block (BB)** | `id, side, tf, range, polarity_flip_at` |
| **Mitigation Block** | 同 OB，但已被部分回测 |
| **Market Structure Shift (MSS)** | `id, tf, direction, level, time, confirmed_by` |
| **Equilibrium / Premium / Discount** | `range_top, range_bot, eq, current_zone` |

**新增**：
- **Multi-TF 嵌套高亮**：H4 OB 嵌入 D1 Premium 区时强度 +1。
- **Mitigation 状态条**：进度条显示 OB 被吃掉百分比。
- **Polarity Flip 提示**：BB 标注由 OB 翻转时间。

**视觉草图**

```
VII · STRUCTURE MAP                                   tf-filter [D1 H4 H1 M15]

   $4,800  ─────────────────── D1 PREMIUM ▲ ─────────────────
   $4,757  ░░░░ Bull OB (H4) [SIG-H4-OB-01] ★★★★☆ mitig 0%
   $4,740  ─── BSL pool (H1, ×2) ──────────────────────────
   $4,727  ▓▓▓▓ Bear OB (H1) [SIG-H1-OB-03] ★★★★★ mitig 12%
   $4,724  ▒▒▒▒ Bull OB (H1) [SIG-H1-OB-02] ★★★★☆ mitig 40%   ↘ confluence
   $4,718  ●  current  4,717.85
   $4,708  ▒▒▒▒ Bull OB (H1) [SIG-H1-OB-01] ★★★★☆ mitig 0%
   $4,684  ▓▓▓▓ FVG (H4) unfilled ★★★★★
   $4,672  ─── SSL pool (H1/H4, ×3) ─── prior H4 low
   $4,650  ─── SSL pool ─── prior H4 low + $4650 round
   $4,600  ─── EQ / round                              D1 DISCOUNT ▼
```

---

# 08 · Liquidity Map

**目的**：列出**所有止损池 / 等高等低 / Asia Range / Judas Swing 痕迹**。

**字段**

| 字段 | 取值 |
|---|---|
| `pool_type` | `SSL / BSL / Equal-H / Equal-L / Round / Asia-H / Asia-L / Prior-Day-H/L / Prior-Week-H/L` |
| `price` | float |
| `strength` | 1-5（基于触及次数 + 距离 + tf 嵌套） |
| `est_volume_proxy` | int (tick volume) |
| `swept` | bool |
| `swept_at` | datetime |
| `target_probability` | % (基于历史相同 setup 命中) |

**视觉**：双侧条形图（上方 BSL 红、下方 SSL 绿），柱长 = 强度。

```
        BSL ABOVE
$4,757  ████████ ★★★★☆ Bull OB H4
$4,740  ████ ★★★☆ BSL ×2  (Asia-H + prior-day-H)
$4,733  ██ ★★ Equal-H (3x)
─── 4,717.85 ●
$4,708  ██ ★★ Bull OB H1
$4,684  ████████ ★★★★★ FVG H4 (unfilled, magnet)
$4,672  ██████ ★★★★ SSL ×3 (prior H4-L + cluster stops)
$4,650  ████████ ★★★★★ SSL + round (HIGH MAGNET ★)
        SSL BELOW
```

---

# 09 · Price Ladder · 阶梯关键位

合并现"上下方阶梯"和"流动性"。每行带 **Confluence Score = Σ(权重)**，按距当前价排序。

**列**

| 列 | 说明 |
|---|---|
| `price` | float |
| `dist_pt` | 距当前价（带正负） |
| `dist_pct` | % |
| `tags` | 多个：OB / FVG / SSL / BSL / Round / EMA / VWAP / Pivot |
| `confluence` | 0–10 |
| `action_hint` | "Re-enter long if reclaim" / "Sell on tag + rejection" |

**视觉**：阶梯式，颜色随置信度从透明→深金渐变。

---

# 10 · Trade Plans · 执行单

**最重要也最缺的一节**。每个 plan 一张卡。

**字段**

| 区段 | 字段 |
|---|---|
| **Setup** | `id, type ∈ {OB-tap, FVG-fill, Sweep-reversal, Breakout-retest, Range-fade}, tf, thesis ≤ 30字, linked SMC ids` |
| **Entry** | `entry_top, entry_bot, trigger ∈ {limit, stop-on-rejection, market-on-confirm}` |
| **Stop** | `sl_price, sl_pt, sl_logic` |
| **Targets** | `tp1, tp2, tp3 + 各自 R:R + 触发逻辑 + 部分平仓 %` |
| **Filter** | `min_rr_T1=1.5, min_rr_T2=2.0, embargo_pass(bool), tf_alignment_pass(bool)` |
| **Sizing** | `account_equity, risk_pct=0.5%, sl_pt → lots, notional, max_lots_correlation_capped` |
| **Expected Value** | `EV = Σ p_i × R_i` 基于历史 setup 命中率 |
| **Kill Criteria** | "若 H1 收盘破 X 取消" / "若 EVT-CPI 超预期取消" |
| **Audit** | `signal source ids, generated_by_model_version, confidence` |

**头寸计算公式**

```
risk_usd          = equity × risk_pct
pip_value_per_lot = 100  (XAU/USD: 1 lot = 100 oz, $1/0.01 ≈ $1/pt → $100/$1pt for 1 std lot, broker-dependent)
sl_pt             = |entry - sl|
lots              = risk_usd / (sl_pt × pip_value_per_lot)
notional          = lots × 100 × entry
margin            = notional × leverage⁻¹
correlation_adj   = lots × (1 - max_corr_with_open_pos)
final_lots        = min(lots, correlation_adj, broker_max_lots)
```

**EV 计算**

```
p_T1 = base_hit_rate(setup_type) × tf_alignment_factor × embargo_factor
p_SL = 1 - p_T1 - p_partial
EV   = p_T1 × R_T1 + p_T2 × R_T2 + p_T3 × R_T3 - p_SL × 1
显示： EV = +0.42R · 历史样本 n=84 · 命中率 58%
```

**视觉草图（单卡）**

```
╔═══ PLAN A · LONG  [SIG-H1-OB-01]  ★★★★☆  ┃  STATUS: STALK ════════════╗
║ THESIS  H1 bull OB 4708.7-4716.9 untouched, sits above H4 FVG magnet      ║
║ ENTRY   limit 4716.9   trigger: M15 bullish FVG inside zone               ║
║ STOP    4698.2  (-18.7 pt · below H1 OB low + 5pt buffer)                 ║
║ TARGETS T1 4727.8  ★ part 50%   R:R 0.58   ❌ filter fail                  ║
║         T2 4740.2  ★ part 30%   R:R 1.25   ❌ filter fail                  ║
║         T3 4757.9  ★ part 20%   R:R 2.19   ✅ pass                         ║
║ EV      +0.18R   p(T3 reach)=22%  hist n=46  win-rate 51%                 ║
║ SIZE    eq $50,000 × 0.5% = $250 risk → 0.13 lots  notional $61k          ║
║ KILL    cancel if H1 closes < 4698.2   OR  US-CPI surprise > +0.2%        ║
║ FILTER  ❌ T1/T2 R:R < 1.5  ─→ DOWNGRADE to scout 25% size only           ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

---

# 11 · Scenario Tree · 概率树

**目的**：替换当前的"情景"列表，做成 3 分支概率树，每分支带 trigger / invalidation / follow-through / EV。

**结构**

```
ROOT (current 4717.85)
├─ BULL  P=28%   trigger: H1 close > 4727.8
│        ├─ ▲ T1 4740 (BSL sweep)        P|bull = 65%
│        └─ ▲ T2 4757.9 (H4 OB tap)      P|bull = 35%
│        invalidation: H1 close < 4708
│        EV (R-units) = +0.46
│
├─ BEAR  P=47%   trigger: M15 sweep 4724-4727 + rejection wick
│        ├─ ▼ T1 4684 (H4 FVG fill)      P|bear = 70%
│        └─ ▼ T2 4668-4672 (SSL ×3 sweep) P|bear = 30%
│        invalidation: H1 close > 4731
│        EV = +0.71  ★ best path
│
└─ RANGE P=25%   trigger: 4708-4727 hold for 2× H1 closes
         fade extremes inside box
         EV = +0.22
```

---

# 12 · Risk Protocol & Checklist

**三段勾选清单（HTML `<input type=checkbox>`）**

**Pre-Trade**
- [ ] 账户日累计回撤 < 1.5%（DDL 未触发）
- [ ] 该仓位 risk_pct ≤ 0.5%
- [ ] 与现有持仓相关性 |ρ| ≤ 0.6
- [ ] 距下一个 HIGH 事件 ≥ 30 分钟（embargo 通过）
- [ ] R:R T1 ≥ 1.5 或已下调至 scout 25%
- [ ] TF Alignment ≥ 2 个周期同向

**In-Trade**
- [ ] 入场后 1× ATR(M15) 内未止损 → 移动 SL 到入场 -0.3R
- [ ] 触及 T1 → 平 50% + SL 移至成本
- [ ] 触及 T2 → 平 30% + SL 移至 T1
- [ ] 跨 Killzone 仍持仓 → 主动减仓 30%

**Post-Trade**
- [ ] `decision_log.md` 已写入 setup / entry / exit / 反思
- [ ] PnL 落入预期区间 (±1σ)，否则触发**例外审计**
- [ ] 当日累计仓位数 ≤ 4，否则**强制冷静期 4h**

**全局风控参数**

| 参数 | 值 |
|---|---|
| Max risk per trade | 0.5% |
| Daily Drawdown Limit | 1.5% → halt |
| Weekly Drawdown Limit | 3.0% → halt week |
| Max concurrent positions | 2 (correlated) / 4 (uncorrelated) |
| Max lots (Gold) | 1.0 |
| Kelly cap | 25% of full Kelly |
| News embargo | High: ±30min · Med: ±10min |

---

# 99 · Audit & Disclosures

```
╔══ AUDIT TRAIL ════════════════════════════════════════════╗
║ Report REF      GLD-INTRADAY-20260427-1320-001           ║
║ Model Version   gold_analysis.py @ git:a3f9c1e            ║
║ Data Sources    MT4 (price, volume) · FRED (yields, DXY)  ║
║                 CFTC COT · WGC ETF · Reuters Calendar     ║
║ Freshness       price 2s · macro 11s · calendar 5min      ║
║ Conflicts       Desk holds 0 lots XAU @ issue time        ║
║ Distribution    Internal only · Do not redistribute       ║
║                                                            ║
║ DISCLAIMER  本报告仅供内部参考，不构成投资建议。模型输出  ║
║   存在误差与延迟，最终决策由交易员承担全部责任。           ║
╚════════════════════════════════════════════════════════════╝
```

---

# 数据契约总表（供 `gold_analysis.py` 实现参考）

```jsonc
{
  "meta": { "ref":"...", "issued_at":"...", "model_version":"...", "feeds":{...} },
  "snapshot": { "price":..., "ohlc_d1":{...}, "bias_score":..., "regime":"..." },
  "macro": [ { "name":"DXY","value":99.20,"delta":..., "z":..., "beta":..., "impact":"bull" }, ... ],
  "events": [ { "time":"...","impact":"HIGH","name":"...","fcst":...,"prev":...,"hist_avg_pt":18 }, ... ],
  "bias_matrix": { "D1":{...}, "H4":{...}, "H1":{...}, "M15":{...} },
  "vol": { "edr_20d":..., "edr_used_pct":..., "atr":{...}, "rv_5d":..., "iv_1w":..., "killzones":[...] },
  "smc": { "ob":[...], "fvg":[...], "bb":[...], "mss":[...], "pd":{...} },
  "liquidity": [ { "type":"SSL","price":4672,"strength":4,"swept":false }, ... ],
  "ladder": [ { "price":..., "tags":[...], "confluence":7, "hint":"..." }, ... ],
  "plans": [ { "id":"...", "side":"long", "entry":..., "sl":..., "tp":[...], "rr":[...], "size":{...}, "ev":..., "kill":[...] }, ... ],
  "scenarios": [ { "branch":"bull","prob":0.28,"trigger":"...","invalidation":"...","ev":0.46,"children":[...] }, ... ],
  "risk": { "params":{...}, "checklist_state":{ "pre":[...], "in":[...], "post":[...] } },
  "audit": { "sources":[...], "git_sha":"...", "conflicts":"...", "disclaimer":"..." }
}
```

---

# 待你决定的开放项

| # | 议题 | 选项 |
|---|---|---|
| Q1 | **板块顺序**：是否同意 12 节顺序？或要把 Trade Plans 提前到第 03 节（"结论先行"再加强）？ | A. 同意 / B. Plans 提前 |
| Q2 | **配色**：保留现有暗金 / 切换到更克制的"BBG Terminal 黑橙" / 双主题切换？ | A / B / C |
| Q3 | **打印/PDF**：是否需要 A4 横向 print stylesheet？ | 是 / 否 |
| Q4 | **数据缺失态**：宏观字段无数据时显示 `n/a` 还是隐藏行？ | 显示 / 隐藏 |
| Q5 | **Trade Plans 数量**：固定 A 多 / B 空 / C 区间 三张？还是动态 1–4 张？ | 固定 3 / 动态 |
| Q6 | **EV 历史样本来源**：是否已有交易日志可用做 base hit rate？没有则先用先验值（写明 prior）。 | 有 / 无 → 先验 |
| Q7 | **多语言**：纯中文 / 中英混排（标题 EN + 内容 CN）/ 双语切换？ | 选其一 |
| Q8 | **签发人头像/签名**：是否需要在 Cover 放电子签？ | 是 / 否 |

请逐条标注（`Q1=B, Q2=A` 这样回我即可），或对任意板块直接写"删 / 改 / 加"指令。审定后我即开始生成 `institutional_report_template.html`（含真实 4/27 样本数据），以及在你需要时同步改 `gold_analysis.py`。
