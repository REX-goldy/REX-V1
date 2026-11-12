export type HandbookCategory =
  | "getting-started"
  | "trading"
  | "technical"
  | "risk"
  | "statistics"
  | "rex"
  | "troubleshooting";

export interface HandbookArticle {
  id: string;
  category: HandbookCategory;
  title: string;
  summary: string;
  definition: string[];
  why: string[];
  example: string[];
  rex: string[];
  mistakes: string[];
  related: string[];
  deepDive?: { heading: string; body: string[] }[];
}

export const CATEGORIES: { id: HandbookCategory; label: string; blurb: string }[] = [
  { id: "getting-started", label: "Getting Started", blurb: "The terminal workflow" },
  { id: "trading", label: "Trading Fundamentals", blurb: "Markets, prices, sessions" },
  { id: "technical", label: "Technical Analysis", blurb: "Structure, trend, breakouts" },
  { id: "risk", label: "Risk Management", blurb: "Risk, R, sizing, drawdown" },
  { id: "statistics", label: "Backtesting & Statistics", blurb: "Evidence and its limits" },
  { id: "rex", label: "REX Research Engine", blurb: "What exists today" },
  { id: "troubleshooting", label: "Troubleshooting", blurb: "Diagnose failed experiments" },
];

const A = (article: HandbookArticle): HandbookArticle => article;

export const ARTICLES: HandbookArticle[] = [
  A({
    id: "what-is-rex",
    category: "getting-started",
    title: "What is REX?",
    summary: "A causal historical-replay and strategy-validation desk — not a signal service or live trading bot.",
    definition: [
      "REX is a quantitative research platform for Forex. It replays completed historical candles, lets a strategy emit signals, simulates a trade lifecycle through the existing execution layer, and measures the result in R-multiples.",
    ],
    why: [
      "A research platform should make assumptions, data, and limitations inspectable. REX is organized around evidence, not around presenting a profitable-looking chart.",
    ],
    example: [
      "You hypothesize that a zone breakout followed by a retest continues in the breakout direction. REX can measure that hypothesis over a selected dataset and period, then show the trade ledger, warnings, and the exact assumptions behind the result.",
    ],
    rex: [
      "The research kernel lives in `historical/`, `strategies/`, `execution/`, and `backtests/`. The terminal is a thin presentation layer. REX does not place broker orders.",
    ],
    mistakes: [
      "Treating a backtest as proof of future profitability.",
      "Assuming every strategy can be trade-simulated. CORE_ZONE_BREAKOUT is currently a signal study only.",
    ],
    related: ["terminal-workflow", "backtesting", "known-limitations"],
  }),
  A({
    id: "terminal-workflow",
    category: "getting-started",
    title: "How the research terminal works",
    summary: "Instrument → timeframe → dataset → range → strategy → run → results → archive.",
    definition: [
      "The terminal is a guided composition of the existing REX kernel: storage and parsing, optional M1-to-higher-timeframe resampling, strategy construction, causal replay, execution simulation, and persisted results.",
    ],
    why: [
      "Separating these steps makes it harder to accidentally compare unlike experiments or interpret a signal study as a trade simulation.",
    ],
    example: [
      "EURUSD → H1 → 2026 dataset → January–June → S002 BreakoutRetest → Run. The result records the dataset, timeframe, dates, parameters, metrics, warnings, and trade ledger.",
    ],
    rex: [
      "Every completed experiment is written to `research/outputs/ui_runs/` and appears in Run Archive. The browser never calculates strategy metrics.",
    ],
    mistakes: [
      "Changing several inputs at once and attributing a result to only one of them.",
      "Comparing runs with different datasets or periods as if they were controlled experiments.",
    ],
    related: ["choose-dataset", "run-backtest", "reproducibility"],
  }),
  A({
    id: "select-instrument-timeframe",
    category: "getting-started",
    title: "Selecting an instrument and timeframe",
    summary: "Instrument and timeframe define the market and the bar size.",
    definition: [
      "The instrument is the symbol being studied, such as EURUSD. The timeframe is the duration represented by each bar, such as M1 or H1.",
    ],
    why: [
      "A setup that works on M1 is a different experiment from the same idea on H1: noise, stop distance, trade frequency, and costs all change.",
    ],
    example: [
      "EURUSD on M1 produces a very large number of bars and signals; EURUSD on H4 produces far fewer, with wider stops.",
    ],
    rex: [
      "REX stores M1 partitions. M5, M15, H1, and H4 are derived on demand with the existing resampler; derived frames are not persisted.",
    ],
    mistakes: [
      "Comparing an M1 run to an H1 run as if only the strategy changed.",
      "Assuming a derived frame uses provider-supplied H1 candles.",
    ],
    related: ["timeframes-resampling", "choose-dataset"],
  }),
  A({
    id: "configure-experiment",
    category: "getting-started",
    title: "Configuring an experiment",
    summary: "Choose dataset, range, strategy, parameters, and risk before running.",
    definition: [
      "An experiment is the complete configuration: instrument, timeframe, dataset, date range, strategy, strategy parameters, R multiple, equity, and risk fraction.",
    ],
    why: [
      "Changing several inputs at once makes the result uninterpretable. Reproducibility requires the exact configuration.",
    ],
    example: [
      "EURUSD · H1 · Jan–Jun 2026 · S008 lookback 10 · 2R · 1% risk is one experiment.",
    ],
    rex: [
      "The Strategy Lab validates the range against actual bars, passes parameters to the strategy constructor, and archives the full configuration with the run.",
    ],
    mistakes: [
      "Tuning parameters on the same range used for the reported conclusion.",
      "Ignoring the distinction between a signal study and a trade simulation.",
    ],
    related: ["run-backtest", "range-too-small", "reproducibility"],
  }),
  A({
    id: "choose-dataset",
    category: "getting-started",
    title: "Selecting a dataset and date range",
    summary: "Use the actual first and last bars — not the year in the filename.",
    definition: [
      "A dataset is a stored M1 partition (`SYMBOL/M1/YEAR.csv`) with optional `.meta.json` provenance. A dataset named 2026 may contain only part of 2026.",
    ],
    why: [
      "The valid research window is bounded by the actual bars. Selecting dates outside them produces empty or misleading results.",
    ],
    example: [
      "If the first bar is 2026-01-02 and the last is 2026-06-30, selecting 2025-12-01 → 2026-07-15 is invalid. REX reports the boundary rather than inventing data.",
    ],
    rex: [
      "The terminal displays actual first/last timestamps, total bars, bars in the selected range, gaps, provider, and provenance. Range validation is server-side against the selected frame (including derived timeframes).",
    ],
    mistakes: [
      "Assuming a yearly filename means twelve full months.",
      "Selecting a short range and then blaming the strategy when there are too few bars.",
    ],
    related: ["timeframes-resampling", "no-data", "range-too-small"],
  }),
  A({
    id: "run-backtest",
    category: "getting-started",
    title: "Running a backtest",
    summary: "Configure, validate, execute, and inspect — without changing strategy logic in the browser.",
    definition: [
      "A backtest replays historical bars in causal order. A strategy produces signals, the execution layer converts supported signals into plans, and the simulator records closed trades and terminations.",
    ],
    why: [
      "The run is a controlled experiment. Its configuration must be visible and reproducible.",
    ],
    example: [
      "An S008 run over the Jan–Jun 2026 EURUSD H1 frame reported 218 signals, 194 closed trades, a 31.4% win rate, PF 0.89, and -0.074R expectancy before costs — a descriptive result, not a promise.",
    ],
    rex: [
      "REX uses `BacktestRunner`, `TradePlanner`, `FixedRiskRewardPolicy`, `FixedRiskSizer`, and the strategy-specific setup factory. Parameters are passed to the strategy constructor; the UI does not tune them.",
    ],
    mistakes: [
      "Reading expectancy without sample size and warnings.",
      "Assuming the target R multiple accounts for spread or slippage.",
    ],
    related: ["read-results", "execution-assumptions", "costs-slippage"],
  }),
  A({
    id: "read-results",
    category: "getting-started",
    title: "Reading a result",
    summary: "Separate signals from trades; read metrics with assumptions and sample size.",
    definition: [
      "Signal-study statistics count detections. Trade-simulation statistics describe closed simulated trades. They answer different questions and must not be mixed casually.",
    ],
    why: [
      "A high signal count is not a strategy. A trade result without costs or sample size is not evidence of an edge.",
    ],
    example: [
      "A signal study may emit thousands of detections while lifecycle constraints reduce the simulated trade count. Signal count, win rate, expectancy, and ambiguous exits describe different things.",
    ],
    rex: [
      "The result panel labels signal-only runs, shows closed trades, expectancy, profit factor, drawdown in R, ambiguous exits, and explicit warnings for costs, static zones, and small samples.",
    ],
    mistakes: [
      "Calling win rate 'accuracy'.",
      "Ignoring that drawdown is measured in cumulative R, not rupees or account percentage.",
    ],
    related: ["win-rate", "expectancy", "max-drawdown", "ambiguous-exits"],
  }),
  A({
    id: "run-archive",
    category: "getting-started",
    title: "Finding previous runs",
    summary: "Run Archive stores the exact configuration and ledger for every completed experiment.",
    definition: [
      "Each run is a JSON artifact under `research/outputs/ui_runs/`, containing the dataset summary, timeframe, parameters, request, metrics, warnings, reconciliation, and trades.",
    ],
    why: [
      "Reproducibility requires more than a screenshot. The archive preserves the context needed to inspect or rerun an experiment.",
    ],
    example: [
      "A run archived at 14:32 can be compared with one at 15:10. If the dataset or parameters differ, the comparison panel explicitly warns that the comparison may be invalid.",
    ],
    rex: [
      "Runs are local artifacts; there is no database. The archive starts empty and is populated by the Strategy Lab.",
    ],
    mistakes: [
      "Comparing two runs without checking dataset and timeframe.",
      "Assuming an archived result is validated out-of-sample.",
    ],
    related: ["reproducibility", "in-sample-oos"],
  }),

  A({
    id: "currency-pairs",
    category: "trading",
    title: "Currency pairs",
    summary: "A pair states how much of the quote currency one unit of the base currency costs.",
    definition: [
      "EUR/USD = 1.0850 means one euro costs 1.0850 US dollars. EUR is the base currency; USD is the quote currency.",
    ],
    why: [
      "Direction, pip value, and quote conventions all follow from which currency is base and which is quote.",
    ],
    example: ["A rise from 1.0850 to 1.0860 is a 10-pip move in EUR/USD."],
    rex: [
      "REX instruments are canonicalized as `EURUSD`; provider symbols such as `EUR/USD` are mapped at the adapter boundary.",
    ],
    mistakes: ["Confusing a long EUR/USD position with a long USD position."],
    related: ["pips", "bid-ask-spread"],
  }),
  A({
    id: "bid-ask-spread",
    category: "trading",
    title: "Bid, ask and spread",
    summary: "Bid is what a buyer is offered; ask is what a seller pays. Spread is the gap.",
    definition: [
      "Bid is the price at which the market buys from you. Ask is the price at which it sells to you. Ask minus bid is the spread.",
    ],
    why: [
      "A strategy that looks profitable at mid prices can lose after crossing the spread on entry and exit.",
    ],
    example: [
      "Bid 1.10000, ask 1.10012 = 1.2 pips spread. On a 1-pip stop, the spread is a very large fraction of the risk.",
    ],
    rex: [
      "The current fill model uses OHLC prices and does not apply spread, commission, or slippage. The terminal warns about this explicitly.",
    ],
    mistakes: [
      "Testing a scalping idea without transaction costs.",
      "Assuming a provider's bid-only candles include the spread.",
    ],
    related: ["costs-slippage", "execution-assumptions"],
  }),
  A({
    id: "pips",
    category: "trading",
    title: "Pips and pipettes",
    summary: "A pip is a standard price increment; a pipette is one tenth of a pip.",
    definition: [
      "For most USD-quoted pairs, one pip is 0.0001; a pipette is 0.00001. JPY pairs typically use 0.01 and 0.001.",
    ],
    why: [
      "Stop distances, spreads, and cost assumptions are naturally expressed in pips, but REX computes risk in price units and R.",
    ],
    example: [
      "A EUR/USD stop distance of 0.0020 is 20 pips. A 1-pip spread is 5% of that stop distance.",
    ],
    rex: [
      "Instrument metadata determines pip size. REX results are in R-multiples, not pips or currency.",
    ],
    mistakes: ["Using 0.0001 for JPY pairs.", "Confusing pip distance with position size."],
    related: ["risk-per-trade", "r-multiple"],
  }),
  A({
    id: "candlesticks",
    category: "trading",
    title: "Candlesticks and OHLC",
    summary: "A candle summarizes open, high, low, and close for a fixed interval.",
    definition: [
      "The body spans open and close; the wicks span the high and low. A completed candle is information available only after its interval closes.",
    ],
    why: [
      "Using a candle's high or close before the candle is complete is look-ahead bias.",
    ],
    example: [
      "An H1 candle that opens at 09:00 cannot be treated as known until 10:00.",
    ],
    rex: [
      "REX bars carry naive UTC timestamps and are replayed chronologically. The resampler only emits completed higher-timeframe buckets.",
    ],
    mistakes: ["Using the current unfinished candle as if it were closed."],
    related: ["timeframes-resampling", "lookahead"],
  }),
  A({
    id: "sessions",
    category: "trading",
    title: "Market sessions",
    summary: "Forex trades nearly 24 hours on weekdays, with regional liquidity windows.",
    definition: [
      "Sydney, Tokyo, London, and New York sessions overlap in different combinations. Liquidity and volatility are not uniform across the day.",
    ],
    why: [
      "A strategy tested across all hours may be driven by one session. Session slicing is a robustness check.",
    ],
    example: [
      "The London–New York overlap often has higher activity than the late Sydney window.",
    ],
    rex: [
      "`SessionManager` contains fixed UTC session windows and does not model daylight-saving shifts. Session labels are available for research, but the current UI does not slice results by session.",
    ],
    mistakes: ["Assuming fixed UTC windows are correct year-round.", "Ignoring session effects when comparing periods."],
    related: ["volatility-liquidity", "overfitting"],
  }),
  A({
    id: "volatility-liquidity",
    category: "trading",
    title: "Volatility and liquidity",
    summary: "Volatility is the size of price movement; liquidity is the ease of transacting without moving price.",
    definition: [
      "Volatility is often measured by range or ATR. Liquidity describes available market depth and is typically higher during major session overlaps.",
    ],
    why: [
      "Stops that are tight relative to volatility get hit by noise. Thin liquidity can make fills and spreads worse.",
    ],
    example: [
      "A 2-pip stop in a market moving 15 pips per hour is noise; a 30-pip stop is a different experiment.",
    ],
    rex: [
      "REX includes ATR and range-expansion features in the feature pipeline. The current UI does not overlay them; the simulator does not model liquidity depth.",
    ],
    mistakes: ["Comparing strategies with very different stop distances as if they were equivalent."],
    related: ["pips", "costs-slippage"],
  }),
  A({
    id: "support-resistance",
    category: "trading",
    title: "Support and resistance",
    summary: "Price areas where prior buying or selling interest was visible.",
    definition: [
      "Support is a region below price where demand previously appeared; resistance is a region above where supply appeared. They are zones, not exact lines.",
    ],
    why: [
      "Zones provide a structural reference for breakouts, retests, stops, and targets.",
    ],
    example: ["A daily demand zone from 1.1500 to 1.1530 can act as a reference for a retest."],
    rex: [
      "REX supports manual zones from `config/zones.json` and automatic zone research generators. Manual zones have no confirmation timestamp; the terminal warns about this.",
    ],
    mistakes: ["Drawing zones after seeing the test period and then claiming a causal edge."],
    related: ["breakouts", "breakout-retests", "data-providers"],
  }),
  A({
    id: "trend-range",
    category: "trading",
    title: "Trend and range-bound markets",
    summary: "Trend means persistent direction; range means oscillation inside boundaries.",
    definition: [
      "A trend makes higher highs and higher lows (up) or lower highs and lower lows (down). A range repeatedly tests boundaries without sustained direction.",
    ],
    why: [
      "Breakout logic behaves differently in trends and ranges. Regime stability matters for robustness.",
    ],
    example: ["A breakout system may perform well in a trending quarter and poorly in a range-bound one."],
    rex: [
      "REX exposes trend/phase views through the feature pipeline, but strategies currently do not consume them. Regime slicing is not yet part of the terminal.",
    ],
    mistakes: ["Evaluating a strategy in only one regime and generalizing."],
    related: ["market-structure", "overfitting"],
  }),

  A({
    id: "moving-averages",
    category: "technical",
    title: "Moving averages (MA)",
    summary: "A moving average smooths price over a window.",
    definition: [
      "An SMA averages the last N closes equally. An EMA weights recent closes more heavily, so it reacts faster.",
    ],
    why: [
      "MAs can summarize trend direction and provide dynamic support/resistance; they are also easy to overfit.",
    ],
    example: ["SMA(20) on H1 averages the last 20 hourly closes; EMA(20) responds faster to the newest close."],
    rex: [
      "`IndicatorEngine` exposes SMA/EMA through the existing pandas-ta-classic adapter. The current Strategy Lab does not expose indicator overlays.",
    ],
    mistakes: ["Optimizing the MA period on the same data used to report results."],
    related: ["ma-crossovers", "overfitting"],
  }),
  A({
    id: "ma-crossovers",
    category: "technical",
    title: "MA crossovers and trend confirmation",
    summary: "A fast/slow MA crossover is a trend-following signal, not a guarantee.",
    definition: [
      "A bullish crossover occurs when a faster MA crosses above a slower MA; bearish is the reverse. Confirmation waits for additional evidence such as structure or a close beyond a level.",
    ],
    why: [
      "Crossovers lag by construction and whipsaw in ranges. Confirmation changes the trade-off between delay and noise.",
    ],
    example: ["EMA(20) crossing above EMA(50) may confirm an uptrend, but in a range it can produce repeated false signals."],
    rex: ["The MA Confluence Zone V1 research generator uses EMA20/EMA50 convergence as a zone hypothesis. It is research, not a live strategy."],
    mistakes: ["Calling every crossover a trend.", "Using a crossover on an unfinished candle."],
    related: ["moving-averages", "false-breakouts", "lookahead"],
  }),
  A({
    id: "breakouts",
    category: "technical",
    title: "Breakouts",
    summary: "A breakout is a close or move beyond a defined boundary.",
    definition: [
      "Breakouts can be defined by a close beyond a zone, a prior swing, or a range boundary. The definition must specify whether intrabar touches count.",
    ],
    why: [
      "Small definition changes create very different signal populations and results.",
    ],
    example: ["Close above a zone high is a close-based breakout; a wick above it is an intrabar touch."],
    rex: [
      "`CORE_ZONE_BREAKOUT` detects zone interactions and is a signal study only. S002 uses a close beyond a manual zone, then waits for a retest.",
    ],
    mistakes: ["Mixing close-based and intrabar definitions.", "Ignoring the retest or false-breakout rate."],
    related: ["breakout-retests", "false-breakouts", "support-resistance"],
  }),
  A({
    id: "breakout-retests",
    category: "technical",
    title: "Breakout retests",
    summary: "A retest checks whether a broken level now acts as support/resistance in the new direction.",
    definition: [
      "After a breakout, price returns to the broken boundary and rejects. A bullish retest touches the broken level from above and closes back above it.",
    ],
    why: [
      "Retests can offer a more defined invalidation level than chasing the breakout candle, at the cost of missing runs that never return.",
    ],
    example: ["Break above 1.1500, retest to 1.1498, close at 1.1510. S002 may emit RETEST_ABOVE."],
    rex: [
      "`S002_BreakoutRetest` keeps per-zone state, enforces a `max_wait` window, and uses static manual zones. Entry is modeled at the next candle open; the stop comes from the retest bar.",
    ],
    mistakes: ["Assuming a retest always occurs.", "Using hindsight zone levels.", "Ignoring the spread relative to the retest stop."],
    related: ["breakouts", "false-breakouts", "execution-assumptions"],
  }),
  A({
    id: "false-breakouts",
    category: "technical",
    title: "False breakouts",
    summary: "A breakout that fails and reverses back through the boundary.",
    definition: [
      "False breakouts are the complement of successful breakouts. They are common in ranges and around thin liquidity.",
    ],
    why: [
      "A breakout strategy's edge depends on the ratio of continuation to failure, not only on how many breakouts occur.",
    ],
    example: ["Close above 1.1500, then close back below 1.1490 within a few bars."],
    rex: [
      "CORE and S002 detect interactions but do not classify false breakouts as a separate outcome in the UI. This is a research gap.",
    ],
    mistakes: ["Filtering false breakouts using future bars.", "Reporting breakout frequency as profitability."],
    related: ["breakouts", "trend-range"],
  }),
  A({
    id: "market-structure",
    category: "technical",
    title: "Market structure",
    summary: "The sequence of swing highs and lows and breaks of those points.",
    definition: [
      "Structural analysis asks whether price is making higher highs/lows, lower highs/lows, or breaking a prior swing. BOS (break of structure) is one formalization.",
    ],
    why: [
      "Structure provides a causal context for entries and invalidation rather than an arbitrary indicator value.",
    ],
    example: ["A break above the last confirmed swing high can be treated as bullish structure, but only after the swing is confirmed."],
    rex: [
      "`core.features.generators.bos` implements swing-based structural BOS with confirmation times. `LookbackBreakoutRule` is a separate legacy lookback rule and is not structural BOS.",
    ],
    mistakes: ["Using unconfirmed swings.", "Confusing a lookback maximum with a structural break."],
    related: ["swings", "multi-timeframe", "lookahead"],
  }),
  A({
    id: "swings",
    category: "technical",
    title: "Swing highs and lows",
    summary: "Local extrema confirmed by bars on both sides.",
    definition: [
      "A swing high has a higher high than the bars to its left and right within a window. A swing low is the mirror.",
    ],
    why: [
      "The confirmation delay is the causal cost of knowing a swing exists. Ignoring it creates look-ahead bias.",
    ],
    example: ["With two right bars, a swing high at index i is only known at index i+2."],
    rex: [
      "`SwingEvent` records source and confirmation timestamps. The feature repository only admits confirmed swings as of the requested time.",
    ],
    mistakes: ["Marking a swing at its source time without waiting for right-side confirmation."],
    related: ["market-structure", "lookahead", "candlesticks"],
  }),
  A({
    id: "multi-timeframe",
    category: "technical",
    title: "Multiple-timeframe analysis",
    summary: "Using higher-timeframe context while trading a lower timeframe.",
    definition: [
      "HTF context might be daily trend or H4 zones; LTF execution might be M15. The HTF candle must be complete before it is usable.",
    ],
    why: [
      "Mixing timeframes can improve context, but it is a common source of look-ahead and alignment errors.",
    ],
    example: ["An H1 bar is only complete at the next hour boundary; it cannot be used to trade inside that hour."],
    rex: [
      "The terminal can derive M5/M15/H1/H4 from stored M1 using the existing resampler. Incomplete buckets are skipped and derived data is not persisted.",
    ],
    mistakes: ["Using an unfinished HTF bar.", "Aligning buckets in local time instead of UTC."],
    related: ["timeframes-resampling", "lookahead", "candlesticks"],
  }),

  A({
    id: "risk-per-trade",
    category: "risk",
    title: "Risk per trade and risk fraction",
    summary: "Risk is the amount lost if the stop is hit; the fraction is that amount divided by equity.",
    definition: [
      "With 100,000 equity and 1% risk, the planned loss at the stop is 1,000 before costs. REX's sizer uses equity × risk_fraction divided by stop distance.",
    ],
    why: [
      "Consistent risk makes R-multiples comparable across trades and prevents one trade from dominating the sample.",
    ],
    example: ["100,000 × 0.01 = 1,000 risk. A 20-pip stop implies a position sized so 20 pips equals 1,000."],
    rex: [
      "`FixedRiskSizer` computes size and risk amount. The simulator currently records R-multiples rather than currency P&L.",
    ],
    mistakes: ["Confusing risk fraction with position size.", "Assuming sizing is applied to currency equity in results."],
    related: ["position-sizing", "r-multiple"],
  }),
  A({
    id: "position-sizing",
    category: "risk",
    title: "Position sizing",
    summary: "Converting a risk amount and stop distance into a position size.",
    definition: [
      "Size = risk amount ÷ stop distance in price units, adjusted for contract conventions. REX's default sizer uses this simple relationship.",
    ],
    why: [
      "Oversizing turns a good strategy into an unsurvivable one; undersizing hides the effect of risk.",
    ],
    example: ["Risk 1,000, stop distance 0.0020 → 500,000 units under the simple model."],
    rex: [
      "The sizer is implemented, but position size does not affect the R-multiple metrics in the current simulator. This is a documented limitation.",
    ],
    mistakes: ["Assuming REX applies lot sizes, margin, or leverage.", "Ignoring currency conversion for non-USD quote pairs."],
    related: ["risk-per-trade", "known-limitations"],
  }),
  A({
    id: "stop-take",
    category: "risk",
    title: "Stop-loss and take-profit",
    summary: "Exit levels that bound loss and define the target.",
    definition: [
      "A stop-loss closes a losing position at a defined level; a take-profit closes a winner. REX's default policy places the stop from the setup hint and the target at a fixed R multiple.",
    ],
    why: [
      "Stops and targets determine both the risk unit and the distribution of outcomes.",
    ],
    example: ["Entry 1.1000, stop 1.0980 (20 pips), 2R target 1.1040."],
    rex: [
      "`FixedRiskRewardPolicy` uses structural stop hints and a configurable R multiple. The simulator recomputes the target from the actual fill and the stop.",
    ],
    mistakes: ["Assuming the target is always honored before the stop when both are inside one candle; REX conservatively marks that ambiguous."],
    related: ["risk-reward", "ambiguous-exits"],
  }),
  A({
    id: "risk-reward",
    category: "risk",
    title: "Risk-to-reward ratio",
    summary: "Target distance divided by stop distance.",
    definition: [
      "A 2R target risks one unit to make two. The ratio is a design choice, not an edge by itself.",
    ],
    why: [
      "A high R target can have a low hit rate and still break even or profit; a low target can have a high hit rate and still lose after costs.",
    ],
    example: ["At 2R, break-even win rate before costs is 33.3% if outcomes are exactly +2R or -1R."],
    rex: ["The Strategy Lab lets you set the R multiple; the policy builds the target from it."],
    mistakes: ["Equating a high R multiple with a better strategy.", "Ignoring the hit rate and costs."],
    related: ["r-multiple", "win-rate-trap", "expectancy"],
  }),
  A({
    id: "r-multiple",
    category: "risk",
    title: "R-multiple",
    summary: "Profit or loss measured in units of the initial risk.",
    definition: [
      "R is the amount risked on the trade. +1R is a gain equal to that risk; -1R is a loss equal to it. REX computes R from entry, stop, and exit prices.",
    ],
    why: [
      "R normalizes results across instruments and position sizes, making expectancy and drawdown comparable across trades.",
    ],
    example: [
      "If a trade risks ₹1,000: +1R = +₹1,000, +2R = +₹2,000, -1R = -₹1,000, before costs. R is relative to initial risk, not account balance or percentage return.",
    ],
    rex: [
      "Closed trades store `pnl_r`. Ambiguous exits are forced to -1R. The equity curve is cumulative R, not currency equity.",
    ],
    mistakes: ["Treating +2R as +2% of the account.", "Forgetting that the risk denominator is the actual entry-to-stop distance."],
    related: ["risk-reward", "expectancy", "max-drawdown"],
  }),
  A({
    id: "drawdown",
    category: "risk",
    title: "Drawdown",
    summary: "The decline from a peak in cumulative performance.",
    definition: [
      "Drawdown is measured from a running peak. REX's max drawdown is the largest peak-to-trough decline in cumulative R.",
    ],
    why: [
      "Two strategies with the same expectancy can have very different survival characteristics.",
    ],
    example: ["Cumulative R goes 0 → +5 → -8 → +3. The peak is +5; the trough is -8; drawdown is 13R."],
    rex: ["The backend computes the cumulative-R curve and drawdown from closed trades. It is not currency equity or a percentage."],
    mistakes: ["Comparing R drawdown to account drawdown.", "Ignoring drawdown when comparing strategies."],
    related: ["max-drawdown", "equity-curve", "risk-of-ruin"],
  }),
  A({
    id: "consecutive-losses",
    category: "risk",
    title: "Consecutive losses",
    summary: "The longest losing streak in the sample.",
    definition: ["A run of losing closed trades. It is a sample statistic, not a guarantee of the next outcome."],
    why: ["Long losing streaks are psychologically and financially demanding even when expectancy is positive."],
    example: ["A 45% win-rate system will produce long losing streaks over a large sample."],
    rex: ["Metrics include consecutive wins/losses in the performance model; the terminal currently surfaces trade-level data and drawdown rather than a dedicated streak widget."],
    mistakes: ["Abandoning a strategy after a streak without checking sample size."],
    related: ["risk-of-ruin", "drawdown"],
  }),
  A({
    id: "risk-of-ruin",
    category: "risk",
    title: "Risk of ruin",
    summary: "The probability of losing enough capital to be unable to continue.",
    definition: [
      "Ruin depends on risk per trade, edge, and the sequence of outcomes. It is not captured by expectancy alone.",
    ],
    why: [
      "A positive expectancy can still be unsurvivable at high risk per trade or under fat-tailed losses.",
    ],
    example: ["Risking 20% per trade makes a short losing streak catastrophic."],
    rex: [
      "REX does not currently compute risk of ruin or currency path simulations. The UI warns that results are R-only and do not model portfolio ruin.",
    ],
    mistakes: ["Assuming positive expectancy removes ruin risk."],
    related: ["risk-per-trade", "drawdown", "known-limitations"],
  }),
  A({
    id: "win-rate-trap",
    category: "risk",
    title: "Why a high win rate is not enough",
    summary: "Win rate ignores the size of winners and losers.",
    definition: ["Win rate = wins ÷ decided outcomes. A 90% win rate can still lose money if the losing tail is large."],
    why: ["Expectancy and profit factor combine frequency and magnitude."],
    example: ["Nine +1R wins and one -10R loss: win rate 90%, net -1R."],
    rex: ["REX reports win rate alongside expectancy, profit factor, and drawdown; it warns when the sample is small."],
    mistakes: ["Selecting strategies by win rate alone."],
    related: ["win-rate", "expectancy", "profit-factor"],
  }),

  A({
    id: "backtesting",
    category: "statistics",
    title: "What backtesting means",
    summary: "A controlled historical replay under explicit assumptions.",
    definition: [
      "Backtesting applies a strategy to historical bars in causal order and measures outcomes. It is a simulation, not a forecast.",
    ],
    why: ["It makes hypotheses testable and assumptions inspectable — if the data and execution model are honest."],
    example: ["Replay EURUSD H1 Jan–Jun 2026 with S002, then inspect the trade ledger and warnings."],
    rex: ["`BacktestRunner` replays bars causally. Strategy detection is separate from execution planning and simulation."],
    mistakes: ["Treating one backtest as validation.", "Changing rules after seeing results."],
    related: ["read-results", "overfitting", "dataset"],
  }),
  A({
    id: "dataset",
    category: "statistics",
    title: "What a historical dataset represents",
    summary: "A finite, provider-specific record with gaps and provenance.",
    definition: [
      "A dataset is a set of bars for a symbol, timeframe, and period, produced by a provider and stored with optional provenance metadata.",
    ],
    why: ["Provider, timestamp convention, gaps, and coverage determine what can honestly be tested."],
    example: ["A 2026 partition may begin in April; the year label does not imply January data."],
    rex: ["Metadata records provider, requested/actual coverage, retrieval time, counts, and quality notes when available."],
    mistakes: ["Assuming two providers produce identical candles.", "Ignoring timezone and gap conventions."],
    related: ["data-providers", "storage-provenance", "gaps"],
  }),
  A({
    id: "timeframes-resampling",
    category: "statistics",
    title: "Timeframes and resampling",
    summary: "Higher timeframes are aggregations of lower-timeframe bars.",
    definition: [
      "M5/M15/H1/H4 bars aggregate M1 open, high, low, close over aligned UTC buckets. A bucket is complete only when all expected open minutes exist.",
    ],
    why: ["Incomplete buckets or misaligned buckets create artificial candles and look-ahead risk."],
    example: ["An H1 bar at 09:00 uses M1 bars from 09:00 through 09:59."],
    rex: ["`research/free_ohlc/resampler.py` implements `fx_open_minutes_v1`; derived frames are computed on demand, incomplete buckets are skipped, and derived data is not persisted."],
    mistakes: ["Using a partial bucket as if complete.", "Resampling in local time."],
    related: ["multi-timeframe", "gaps", "lookahead"],
  }),
  A({
    id: "sample-size",
    category: "statistics",
    title: "Sample size",
    summary: "How many independent-ish observations support the result.",
    definition: ["The number of closed trades or signals. More observations reduce noise but do not remove bias."],
    why: ["A 20-trade sample is fragile; a large biased sample is still biased."],
    example: ["30 trades with +0.2R average could easily be noise; 1,000 overlapping trades in one month can still be one regime."],
    rex: ["The terminal warns when a run has fewer than 100 closed trades. It does not compute statistical significance."],
    mistakes: ["Assuming many signals equals many independent trades.", "Ignoring regime concentration."],
    related: ["overfitting", "expectancy", "misleading-results"],
  }),
  A({
    id: "win-rate",
    category: "statistics",
    title: "Win rate",
    summary: "Share of decided outcomes that are positive.",
    definition: ["REX computes wins ÷ (wins + losses) × 100. Zero outcomes are excluded from the denominator."],
    why: ["It is intuitive but incomplete without average win/loss and sample size."],
    example: ["393 wins, 938 losses → 393/1331 = 29.5%."],
    rex: ["Displayed with expectancy, profit factor, and warnings."],
    mistakes: ["Calling it accuracy.", "Ignoring breakeven trades."],
    related: ["win-rate-trap", "expectancy"],
  }),
  A({
    id: "expectancy",
    category: "statistics",
    title: "Expectancy",
    summary: "Average R per closed trade.",
    definition: ["Expectancy = sum of realized R outcomes ÷ number of outcomes. REX reports it for trade simulation from closed trades."],
    why: ["It combines win rate and payoff into one per-trade unit, still dependent on sample and costs."],
    example: ["+2R, -1R, -1R, +2R → average +0.5R."],
    rex: ["The result is descriptive. The UI warns about costs, sample size, and ambiguity."],
    mistakes: ["Reading +0.02R as a reliable edge.", "Comparing expectancy across different cost assumptions."],
    related: ["r-multiple", "profit-factor", "costs-slippage"],
  }),
  A({
    id: "profit-factor",
    category: "statistics",
    title: "Profit factor",
    summary: "Gross profit divided by gross loss.",
    definition: ["PF = sum of positive R ÷ absolute sum of negative R. If there are no losses, REX reports no value rather than infinity."],
    why: ["It shows payoff balance, but can be distorted by one large winner or a short sample."],
    example: ["+60R gross profit and -50R gross loss → PF 1.2."],
    rex: ["Computed from closed trades; displayed as — when undefined."],
    mistakes: ["Comparing PF across different instruments/periods without context."],
    related: ["expectancy", "max-drawdown"],
  }),
  A({
    id: "max-drawdown",
    category: "statistics",
    title: "Maximum drawdown",
    summary: "Largest peak-to-trough decline in cumulative R.",
    definition: ["REX computes the running cumulative R, its peak, and the largest subsequent decline."],
    why: ["It captures path pain that expectancy hides."],
    example: ["Cumulative R peaks at 40 then falls to -20 → 60R drawdown."],
    rex: ["Backend-computed; shown with a drawdown curve. Not currency or percentage."],
    mistakes: ["Treating R drawdown as account drawdown."],
    related: ["drawdown", "equity-curve"],
  }),
  A({
    id: "equity-curve",
    category: "statistics",
    title: "Equity curve",
    summary: "Cumulative performance over the sequence of trades.",
    definition: ["In REX, the curve is cumulative R at trade exits. It assumes a fixed risk unit and no compounding."],
    why: ["The shape reveals clusters of losses, regime dependence, and whether performance is path-dependent."],
    example: ["A smooth rise and a jagged flat line can share the same final R but imply different risk."],
    rex: ["The terminal plots cumulative R and drawdown from closed trades; it labels them as not currency equity."],
    mistakes: ["Assuming the curve includes spread, commission, or compounding."],
    related: ["max-drawdown", "costs-slippage"],
  }),
  A({
    id: "trade-distribution",
    category: "statistics",
    title: "Trade distribution over time",
    summary: "When trades occurred, not just how many.",
    definition: ["A distribution can show clustering by day, session, or regime. REX's archive preserves entry/exit timestamps."],
    why: ["Clustering can make a large sample look more independent than it is."],
    example: ["1,000 trades in 20 days is not the same evidence as 1,000 trades across two years."],
    rex: ["The trade ledger shows timestamps; the UI does not yet provide a dedicated time-histogram or session breakdown."],
    mistakes: ["Treating clustered trades as independent observations."],
    related: ["sample-size", "overfitting"],
  }),
  A({
    id: "ambiguous-exits",
    category: "statistics",
    title: "Ambiguous exits",
    summary: "When one candle contains both stop and target, the order is unknown.",
    definition: ["OHLC data cannot establish which level was hit first. REX conservatively records these as -1R."],
    why: ["Choosing the favorable order would invent information."],
    example: ["A bar with low below stop and high above target is ambiguous."],
    rex: ["`ConservativeOHLCFillModel` returns `AMBIGUITY`; the simulator scores -1R and increments the ambiguous count."],
    mistakes: ["Assuming the target hit first.", "Ignoring ambiguity rate when comparing strategies."],
    related: ["gaps", "execution-assumptions"],
  }),
  A({
    id: "gaps",
    category: "statistics",
    title: "Missing candles and timestamp gaps",
    summary: "Absent intervals can be closures, provider gaps, or data errors.",
    definition: ["A gap is a difference between consecutive timestamps larger than the expected step. Weekends and maintenance create normal gaps."],
    why: ["Gaps affect resampling completeness, signal generation, and what period was actually tested."],
    example: ["Friday 21:59 → Sunday 22:00 is a normal FX weekend gap."],
    rex: ["Quality reports count raw timestamp gaps and label them as not session-aware. The resampler skips incomplete buckets. The UI shows gap counts with warnings."],
    mistakes: ["Treating every weekend as missing data.", "Resampling across gaps as if complete."],
    related: ["missing-timestamps", "timeframes-resampling"],
  }),
  A({
    id: "lookahead",
    category: "statistics",
    title: "Look-ahead bias",
    summary: "Using information before it was available.",
    definition: ["Peeking at future bars, unconfirmed swings, unfinished HTF candles, or post-hoc zones changes the experiment's causal meaning."],
    why: ["Look-ahead produces fictional edge that disappears live."],
    example: ["A swing high confirmed two bars later cannot be used at the source bar."],
    rex: ["REX replays completed bars chronologically; swing events carry confirmation times; the resampler admits completed HTF buckets. Manual zones remain a known causality limitation."],
    mistakes: ["Assuming the existence of a test proves causality.", "Using future data to select the test period."],
    related: ["candlesticks", "swings", "multi-timeframe"],
  }),
  A({
    id: "overfitting",
    category: "statistics",
    title: "Overfitting",
    summary: "Fitting noise in a specific sample.",
    definition: ["Overfitting is excessive tuning to one dataset/period so the rules do not generalize."],
    why: ["More parameters and repeated evaluation increase the chance of a spurious result."],
    example: ["Testing dozens of lookback values on one quarter and reporting the best one."],
    rex: ["The terminal exposes parameters but does not enforce a validation protocol. Treat parameter sweeps as exploratory until tested out-of-sample."],
    mistakes: ["Reporting the best in-sample run as the strategy.", "Ignoring multiple-testing effects."],
    related: ["in-sample-oos", "walk-forward", "sample-size"],
  }),
  A({
    id: "in-sample-oos",
    category: "statistics",
    title: "In-sample and out-of-sample testing",
    summary: "Development data versus held-back evidence.",
    definition: ["In-sample data is used to form/tune the idea. Out-of-sample data is not used for tuning and tests whether the idea survives."],
    why: ["Without a held-out period, reported performance is a selection artifact."],
    example: ["Tune on 2020–2023; evaluate unchanged on 2024–2025."],
    rex: ["REX can run any selected period, but no automatic split or OOS protocol is enforced. This is a documented research-integrity gap."],
    mistakes: ["Tuning again after seeing OOS results."],
    related: ["walk-forward", "overfitting", "known-limitations"],
  }),
  A({
    id: "walk-forward",
    category: "statistics",
    title: "Walk-forward testing",
    summary: "Roll the train/test window forward through time.",
    definition: ["Walk-forward analysis repeatedly trains on a past window and tests on the next, then advances."],
    why: ["It approximates how a process would be updated and used over time."],
    example: ["Train 12 months, test 3, roll 3 months, repeat."],
    rex: ["Not implemented as an automated REX workflow. The terminal can run separate periods manually, but does not claim walk-forward validation."],
    mistakes: ["Calling rolling separate backtests 'walk-forward' without a fixed protocol."],
    related: ["in-sample-oos", "overfitting"],
  }),
  A({
    id: "costs-slippage",
    category: "statistics",
    title: "Transaction costs and slippage",
    summary: "Real trading pays spread, commission, and adverse fills.",
    definition: ["Costs reduce each trade's net result; slippage is the difference between intended and actual fill prices."],
    why: ["Short-horizon strategies can be entirely consumed by costs."],
    example: ["A 1-pip spread on a 1-pip stop is 1R of cost per round trip."],
    rex: ["The current fill model does not apply costs. Results are gross and must not be described as net. Spread calibration is a planned improvement."],
    mistakes: ["Comparing gross results to a live account.", "Assuming costs are negligible because they are not modeled."],
    related: ["bid-ask-spread", "execution-assumptions", "known-limitations"],
  }),
  A({
    id: "misleading-results",
    category: "statistics",
    title: "Why historical results can mislead",
    summary: "A backtest is conditional on data, assumptions, and selection.",
    definition: ["Results depend on provider data, gaps, costs, execution assumptions, parameter choices, period, and how many ideas were tried."],
    why: ["The same code can produce a flattering result under optimistic assumptions and a negative one under honest ones."],
    example: ["1,331 trades in one month with no costs is one regime and one assumption set, not a durable edge."],
    rex: ["Warnings are shown with every run. The terminal never claims future performance or that a strategy is profitable."],
    mistakes: ["Reading a positive expectancy as a guarantee.", "Ignoring warnings because the chart is attractive."],
    related: ["overfitting", "costs-slippage", "sample-size"],
  }),

  A({
    id: "data-providers",
    category: "rex",
    title: "Data providers and provenance",
    summary: "Twelve Data is the primary M1 source; Dukascopy remains a legacy adapter.",
    definition: ["Providers differ in history, timestamps, bid/ask availability, licensing, and rate limits. Provenance records which source produced a partition."],
    why: ["Results are only meaningful for the data actually stored."],
    example: ["A partition can be provider `twelve_data` or `dukascopy`; unknown means no metadata."],
    rex: ["Twelve Data free tier: 8 requests/min, 800/day, M1 history for this key from 2020-04-07. Dukascopy is retained but its terms restrict automated/commercial use. The terminal refuses to merge a new provider into a legacy unmetadata'd partition."],
    mistakes: ["Assuming all providers agree.", "Redistributing free-tier data commercially."],
    related: ["dataset", "storage-provenance", "provider-mismatch"],
  }),
  A({
    id: "storage-provenance",
    category: "rex",
    title: "Dataset storage and provenance",
    summary: "Yearly CSV partitions plus metadata.",
    definition: ["Bars are stored under `SYMBOL/TIMEFRAME/YEAR.csv`; `.meta.json` records provider, requested/actual coverage, retrieval time, counts, and quality notes when available."],
    why: ["Without provenance, a dataset cannot be attributed or safely combined."],
    example: ["A legacy CSV with no metadata is labeled unattributed and blocked from UI provider merges."],
    rex: ["`HistoricalStorage` writes atomically. Downloads are idempotent; reruns skip covered partitions."],
    mistakes: ["Copying CSVs without metadata and assuming they are production data."],
    related: ["data-providers", "dataset"],
  }),
  A({
    id: "canonical-bar",
    category: "rex",
    title: "Canonical bar representation",
    summary: "One validated OHLCV shape for the research kernel.",
    definition: ["`Bar(symbol, timestamp, open, high, low, close, volume)` with naive UTC timestamps and validated OHLC relationships."],
    why: ["A single representation prevents format-specific logic from leaking into strategies."],
    example: ["Twelve Data JSON rows are mapped to `Bar` at the adapter boundary; strategies never see provider JSON."],
    rex: ["`historical/bar_contract.py` validates and normalizes; volume is `None` when the provider does not supply it."],
    mistakes: ["Using local time.", "Fabricating volume when absent."],
    related: ["storage-provenance", "timeframes-resampling"],
  }),
  A({
    id: "feature-pipeline",
    category: "rex",
    title: "Feature generation",
    summary: "Typed feature packs and pure views; currently disconnected from strategies.",
    definition: ["`FeatureRepository` materializes immutable context packs (price, structure, volatility, indicators, zones, session); Views project them with a required method id."],
    why: ["It provides one canonical implementation per concept and causal HTF handling."],
    example: ["Trend is a view using `market_structure_v1`; swings carry confirmation times."],
    rex: ["The feature pipeline exists and is tested, but strategies still consume raw bars in the current phase. The terminal does not expose feature views."],
    mistakes: ["Assuming the UI uses the feature pipeline for strategy decisions."],
    related: ["known-limitations", "market-structure"],
  }),
  A({
    id: "strategies",
    category: "rex",
    title: "Strategies in REX",
    summary: "Three implemented strategies; CORE is signal-only.",
    definition: [
      "CORE_ZONE_BREAKOUT detects zone interactions. S002_BreakoutRetest trades a manual-zone breakout followed by a retest. S008_LiquiditySweep trades sweep signals.",
    ],
    why: ["Strategy behavior, parameters, and simulation support must be understood before interpreting a run."],
    example: ["S008 has lookback, wick ratio, tolerance, and close-inside parameters. S002 has retest tolerance and max wait."],
    rex: ["Strategies emit signals; the execution layer translates them. CORE has no trade setup factory in the current UI, so it is a signal study."],
    mistakes: ["Assuming every strategy has a trade simulator.", "Changing parameters without recording the experiment."],
    related: ["signals", "trade-simulation", "known-limitations"],
  }),
  A({
    id: "signals",
    category: "rex",
    title: "Signal generation",
    summary: "Detection only; signals are not trades.",
    definition: ["A strategy returns `Signal` objects with symbol, type, price, timestamp, reason, and zone metadata."],
    why: ["Separating signals from execution keeps detection measurable and lets the kernel decide whether a strategy can be simulated."],
    example: ["2,702 retest signals may become 1,331 closed trades after lifecycle filtering."],
    rex: ["`Signal` is zone-oriented; non-zone strategies use zone id 0. The runner counts signals and rejected setups separately."],
    mistakes: ["Reporting signal count as trade count.", "Ignoring rejected setups."],
    related: ["trade-simulation", "read-results"],
  }),
  A({
    id: "trade-simulation",
    category: "rex",
    title: "Trade simulation",
    summary: "Turn supported setups into plans, fills, and closed trades.",
    definition: ["The execution pipeline is signal → factory → setup → validator → planner → plan → simulator → position/closed trade/terminated setup."],
    why: ["It makes assumptions explicit: entry model, stop, target, sizing, expiration, and ambiguity."],
    example: ["S002 retest signal → setup → next-open plan → SL/TP/ambiguity → closed trade in R."],
    rex: ["`BacktestRunner` wires the pipeline. One active lifecycle per strategy+symbol is allowed; additional signals are ignored and counted."],
    mistakes: ["Assuming pending plans fill at the signal price.", "Ignoring timeouts and end-of-data closures."],
    related: ["signals", "execution-assumptions"],
  }),
  A({
    id: "execution-assumptions",
    category: "rex",
    title: "Execution assumptions",
    summary: "What the simulator actually does — and does not do.",
    definition: [
      "Entry is next candle open for supported strategies. The stop comes from the setup; the target is recomputed from the actual fill and R multiple. Ambiguous intrabar exits are -1R. Costs are not applied.",
    ],
    why: ["A result is only interpretable with its execution assumptions attached."],
    example: ["A plan with a 2R target does not guarantee a 2R outcome if the entry fills at a different price."],
    rex: ["`ConservativeOHLCFillModel`, `TradeSimulator`, `FixedRiskRewardPolicy`, and `FixedRiskSizer` implement these rules."],
    mistakes: ["Assuming LIMIT/STOP entries are implemented (they are not).", "Assuming commission/spread are included."],
    related: ["costs-slippage", "ambiguous-exits", "known-limitations"],
  }),
  A({
    id: "metrics",
    category: "rex",
    title: "Research metrics",
    summary: "What each number means and what it omits.",
    definition: [
      "REX reports total signals, closed trades, win rate, expectancy in R, profit factor, max drawdown in R, largest win/loss, ambiguous exits, and average holding duration.",
    ],
    why: ["Each metric answers a different question; none is a complete strategy verdict."],
    example: ["S008 on the current dataset: 1,507 signals, 1,416 trades, 34.0% win rate, PF 1.03, +0.019R expectancy before costs."],
    rex: ["Metrics are backend-calculated from the run. The UI labels signal-only vs simulated results."],
    mistakes: ["Treating PF 1.03 as a validated edge.", "Comparing drawdown in R to account percentage."],
    related: ["read-results", "expectancy", "profit-factor"],
  }),
  A({
    id: "reproducibility",
    category: "rex",
    title: "Experiment reproducibility",
    summary: "Same data, timeframe, parameters, and code should reproduce the run.",
    definition: ["Reproducibility requires recording dataset identity, provider provenance, dates, timeframe, strategy parameters, execution assumptions, and warnings."],
    why: ["Without it, a result is an anecdote."],
    example: ["A run artifact includes the dataset summary, request, parameters, metrics, warnings, and trade ledger."],
    rex: ["Run artifacts are JSON under `research/outputs/ui_runs/`. Dataset hashes and a formal code-version manifest are not yet embedded."],
    mistakes: ["Sharing only a screenshot.", "Assuming a rerun used the same data when the partition changed."],
    related: ["run-archive", "dataset"],
  }),
  A({
    id: "known-limitations",
    category: "rex",
    title: "Known limitations",
    summary: "The current honest boundary of REX.",
    definition: [
      "No costs, spread, slippage, fees, financing, currency equity, compounding, live trading, portfolio management, auth, database, background jobs, OOS protocol, or walk-forward automation.",
    ],
    why: ["Knowing what is absent prevents overclaiming."],
    example: ["A positive gross R result may be negative after realistic costs."],
    rex: [
      "CORE is signal-only; S002/S008 are simulated. Zones are static. Manual zones lack confirmation timestamps. The feature pipeline is not yet consumed by strategies. Historical sessions are DST-unaware.",
    ],
    mistakes: ["Filling gaps with assumptions instead of reporting them.", "Presenting the terminal as a production trading system."],
    related: ["costs-slippage", "in-sample-oos", "execution-assumptions"],
  }),

  A({
    id: "no-data",
    category: "troubleshooting",
    title: "No data available for selected dates",
    summary: "The requested range falls outside the actual dataset.",
    definition: ["The provider or dataset has no bars inside the requested dates."],
    why: ["REX does not invent bars or clamp dates silently."],
    example: ["Selecting 2025 for a partition whose first bar is 2026-01-02."],
    rex: ["Check the dataset panel for actual first/last timestamps; choose a range inside them or download the missing period."],
    mistakes: ["Assuming a year label means full-year coverage."],
    related: ["choose-dataset", "data-providers"],
  }),
  A({
    id: "range-too-small",
    category: "troubleshooting",
    title: "Selected range contains too few bars",
    summary: "The range is too short for the frame or strategy lookback.",
    definition: ["REX requires at least two bars, and S008 needs lookback + 2 bars with the current parameters."],
    why: ["A strategy cannot form a valid signal/history with insufficient data."],
    example: ["S008 lookback 10 on 6 H1 bars is insufficient."],
    rex: ["The API rejects the run with the actual bar count and required minimum. Select a longer range or lower the lookback."],
    mistakes: ["Blaming the strategy when the range is too short."],
    related: ["choose-dataset", "strategies"],
  }),
  A({
    id: "missing-timestamps",
    category: "troubleshooting",
    title: "Missing timestamps / gaps",
    summary: "The dataset is not a perfectly continuous minute series.",
    definition: ["Weekends, maintenance, holidays, and provider outages create gaps. Raw gap counts include normal closures."],
    why: ["Gaps affect completeness and can hide missing periods."],
    example: ["Friday 21:59 → Sunday 22:00 is expected; a missing Tuesday afternoon is not."],
    rex: ["The dataset panel shows raw gap counts; derived timeframes skip incomplete buckets."],
    mistakes: ["Assuming every gap is an error.", "Ignoring an unexpected intraday gap."],
    related: ["gaps", "timeframes-resampling"],
  }),
  A({
    id: "provider-mismatch",
    category: "troubleshooting",
    title: "Dataset and provider mismatch",
    summary: "REX refuses to merge providers into one partition.",
    definition: ["A partition may be written by one provider. Mixing another provider's bars into it would destroy provenance."],
    why: ["Different providers can disagree on prices and timestamps."],
    example: ["An existing unmetadata'd 2026 partition blocks a Twelve Data UI download for 2026."],
    rex: ["Use a separate `REX_DATA_DIR` for a provider-pure dataset, or deliberately overwrite via the CLI."],
    mistakes: ["Assuming a successful merge means the data is compatible."],
    related: ["data-providers", "storage-provenance"],
  }),
  A({
    id: "unsupported-timeframe",
    category: "troubleshooting",
    title: "Unsupported timeframe",
    summary: "Only M1 is stored; M5/M15/H1/H4 are derived.",
    definition: ["The UI offers M1, M5, M15, H1, and H4. Derived frames require an M1 source partition."],
    why: ["Storing every timeframe separately would duplicate data and create provenance conflicts."],
    example: ["A non-M1 stored partition cannot produce H1 through the current derivation path."],
    rex: ["The resampler emits only complete buckets. The terminal labels derived frames and does not persist them."],
    mistakes: ["Expecting provider-supplied H1 files to be used automatically."],
    related: ["timeframes-resampling"],
  }),
  A({
    id: "signals-no-trades",
    category: "troubleshooting",
    title: "Strategy produces signals but no trades",
    summary: "The execution layer may not support that strategy's signals.",
    definition: ["Signal detection and trade simulation are separate. A strategy without a setup factory is a signal study."],
    why: ["The kernel must not pretend an unsupported signal became a trade."],
    example: ["CORE_ZONE_BREAKOUT produces zone signals but is not trade-simulated in the current UI."],
    rex: ["The run panel labels signal-only results and shows zero trades; the setup-factory boundary counts rejected signals."],
    mistakes: ["Assuming zero trades means zero signals.", "Adding a generic factory that ignores signal semantics."],
    related: ["signals", "trade-simulation", "known-limitations"],
  }),
  A({
    id: "no-equity-curve",
    category: "troubleshooting",
    title: "No equity curve available",
    summary: "The run has no closed trades or is a signal study.",
    definition: ["The cumulative-R curve is built from closed trades. No closed trades means no curve."],
    why: ["Plotting an empty curve as performance would be misleading."],
    example: ["A signal study with 500 signals but no execution factory has no equity curve."],
    rex: ["The UI shows an empty-state explanation instead of a flat/fabricated line."],
    mistakes: ["Treating a missing curve as a bug.", "Plotting signals as if they were trades."],
    related: ["signals-no-trades", "equity-curve"],
  }),
  A({
    id: "invalid-config",
    category: "troubleshooting",
    title: "Invalid experiment configuration",
    summary: "A parameter or risk value is outside the accepted range.",
    definition: ["Parameters are validated against the strategy specification; R multiple, equity, and risk fraction have explicit bounds."],
    why: ["Silent coercion would change the experiment."],
    example: ["Risk fraction 0.5 is rejected because the UI accepts at most 0.1."],
    rex: ["The API returns an actionable 400 message; the Strategy Lab renders it near the form."],
    mistakes: ["Assuming a rejected value was used anyway.", "Tuning risk to make a curve look better."],
    related: ["run-backtest", "risk-per-trade"],
  }),
  A({
    id: "execution-errors",
    category: "troubleshooting",
    title: "Backtest execution errors",
    summary: "Unexpected engine or data errors are surfaced, not hidden.",
    definition: ["Errors can come from missing datasets, invalid bars, unsupported signals, missing zones, or provider failures."],
    why: ["A failed run must not be presented as a successful empty result."],
    example: ["A missing EURUSD zone book prevents S002 from running."],
    rex: ["The API returns an error detail; the terminal preserves the form and shows the message. Check the System page and dataset warnings for context."],
    mistakes: ["Retrying identical invalid configuration.", "Ignoring the distinction between zero trades and a failed run."],
    related: ["invalid-config", "no-data"],
  }),
];

export const GLOSSARY: { term: string; definition: string; article: string }[] = [
  { term: "Ask", definition: "The price at which the market sells a base currency to you.", article: "bid-ask-spread" },
  { term: "ATR", definition: "Average True Range; a volatility measure based on recent ranges.", article: "volatility-liquidity" },
  { term: "Bid", definition: "The price at which the market buys a base currency from you.", article: "bid-ask-spread" },
  { term: "BOS", definition: "Break of structure; a break of a confirmed swing point.", article: "market-structure" },
  { term: "Candle", definition: "OHLC summary for one interval.", article: "candlesticks" },
  { term: "Drawdown", definition: "Decline from a running peak in cumulative performance.", article: "drawdown" },
  { term: "EMA", definition: "Exponential moving average; weights recent closes more.", article: "moving-averages" },
  { term: "Expectancy", definition: "Average R per closed trade.", article: "expectancy" },
  { term: "Gap", definition: "A missing interval between consecutive bars.", article: "gaps" },
  { term: "HTF", definition: "Higher timeframe; an aggregated frame such as H1 or H4.", article: "multi-timeframe" },
  { term: "Look-ahead", definition: "Using information before it was available.", article: "lookahead" },
  { term: "OHLC", definition: "Open, high, low, close.", article: "candlesticks" },
  { term: "Pip", definition: "Standard price increment, usually 0.0001 for USD pairs.", article: "pips" },
  { term: "Profit factor", definition: "Gross profit divided by gross loss.", article: "profit-factor" },
  { term: "R", definition: "Initial risk on a trade; results are measured in R-multiples.", article: "r-multiple" },
  { term: "Resampling", definition: "Aggregating lower-timeframe bars into a higher timeframe.", article: "timeframes-resampling" },
  { term: "SMA", definition: "Simple moving average; equal-weighted mean of closes.", article: "moving-averages" },
  { term: "Spread", definition: "Ask minus bid.", article: "bid-ask-spread" },
  { term: "Swing", definition: "A local high or low confirmed by bars on both sides.", article: "swings" },
  { term: "Win rate", definition: "Wins divided by decided outcomes.", article: "win-rate" },
];

export function searchHandbook(query: string): HandbookArticle[] {
  const q = query.trim().toLowerCase();
  if (!q) return ARTICLES;
  return ARTICLES.filter((article) => {
    const haystack = [
      article.title,
      article.summary,
      ...article.definition,
      ...article.why,
      ...article.example,
      ...article.rex,
      ...article.mistakes,
      ...(article.deepDive ?? []).flatMap((section) => [section.heading, ...section.body]),
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(q);
  });
}

export function articleById(id: string): HandbookArticle | undefined {
  return ARTICLES.find((article) => article.id === id);
}
