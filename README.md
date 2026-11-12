# REX

REX is a quantitative trading **research** platform. It helps you form hypotheses, replay historical data causally, and measure results under explicit assumptions.

It does **not** place live broker orders, manage portfolios, or connect to exchanges today.

For why REX exists, engineering rules, current architecture, and roadmap, use the documentation system below—not this README.

---

## Documentation

| Document | Responsibility |
|----------|----------------|
| [VISION.md](VISION.md) | Why REX exists |
| [PRINCIPLES.md](PRINCIPLES.md) | Engineering constitution |
| [ROADMAP.md](ROADMAP.md) | Phases, focus, deferred work |
| [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) | Current architecture and capabilities |
| [Strategy Workspace](docs/strategy-workspace/ARCHITECTURE.md) | Research strategy, variation, note and experiment management |
| [P0 Execution Integrity](docs/p0-execution-integrity/README.md) | Sizing, gap execution, CORE signal and duplicate-timestamp fixes |
| [P1 Realistic Backtesting](docs/p1-realistic-backtesting/README.md) | Cost profiles, gross/net, validation, dataset quality and preflight |
| [P2 Research Management](docs/p2-research-management/README.md) | Strategy variations, experiments, zones, comparison and dashboard |
| [P3 Assessment](docs/p3-assessment/README.md) | Feature intelligence, analytics, regime and robustness roadmap |
| [P3.1 Indicator Foundation](docs/p3-indicator-foundation/README.md) | Versioned causal indicator series foundation |
| [research/README.md](research/README.md) | Research process howto |

---

## Quick overview

- **Strategies** implement `generate_signals(candles)` and are discovered by the registry (detection only).
- **Execution layer** (`execution/`): `Signal` → `TradeSetup` → `TradePlan` via factory, validator, policy, and sizer.
- Directions use `TradeDirection` (`LONG` / `SHORT`). Plans carry `planned_at` (when produced).
- Pending-plan `timeout_candles` is enforced (`EXPIRED` after that many unfilled wait bars).
- **BacktestRunner** replays bars causally; trade mode feeds `TradePlan` into `TradeSimulator`.
- **Historical data** comes from a configurable source via `historical/` (M1): Dukascopy or Twelve Data. Higher timeframes are derived with the existing resampler.
- **Two research modes:** signal studies, or trade simulation (`simulate_trades=True`).
- **Current strategies:** zone breakout (`CORE_ZONE_BREAKOUT`), breakout → retest (`S002`), liquidity sweep (`S008`). See [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).

---

## Installation

```bash
python -m pip install -r requirements.txt
```

---

## Quality checks

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
make lint     # compileall + pyflakes on production packages
make test     # full unittest suite
make build    # frontend npm ci + typecheck + production build
make check    # all three
```

A minimal GitHub Actions workflow (`.github/workflows/ci.yml`) runs the Python
suite and frontend build. It requires no secrets; tests use mocked provider
responses and never consume Twelve Data credits.

## Research terminal (UI)

A local React/Vite terminal sits over a thin FastAPI service. The browser never
holds provider keys; the service reads `TWELVE_DATA_API_KEY` from its environment.

```bash
# backend (port 8000)
python -m pip install -r requirements.txt
export TWELVE_DATA_API_KEY=...
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000

# frontend (port 5173, proxies /api to :8000)
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

Open `http://localhost:5173`. For a single-process deployment, run
`cd frontend && npm run build`; the API serves `frontend/dist` at `/`.

The terminal provides:

- **Overview** — real datasets, strategy catalog, warnings, recent archived runs.
- **Market Data** — dataset provenance/quality, actual first/last timestamps,
  candlestick preview, bounded synchronous downloads (max 31 days per UI request;
  use the CLI for bulk history).
- **Strategy Lab** — instrument → timeframe → dataset → date-range workflow with
  1/3/6/12-month presets and custom dates; server-side range validation against
  actual bars; M5/M15/H1/H4 derived from M1; real `BacktestRunner` runs with
  parameters, R-multiple metrics, trade ledger, cadence, cumulative-R/drawdown
  plots, assumptions and sample-size warnings.
- **Run Archive** — persisted JSON results and side-by-side comparison.
- **Help & Handbook** — searchable, category-organized articles on trading,
  technical analysis, risk, statistics, the REX engine, troubleshooting, and a
  glossary, plus contextual links/tooltips from the lab.
- **System** — setup, credential handling, and the platform's explicit limits.

The UI can apply optional estimated/proxy cost profiles and separates gross from
net results; it does not add currency equity, out-of-sample validation, or live
trading. Every run writes an artifact under `research/outputs/ui_runs/` (ignored
by git). If a partition has no provenance metadata, downloads are refused for
that year to prevent silently mixing providers; choose a separate `REX_DATA_DIR`.

---

## Historical data setup

Provider selection is configuration-driven. Existing Dukascopy configs continue
to work unchanged.

### Twelve Data (M1, free tier)

```bash
export TWELVE_DATA_API_KEY=...        # never commit the key
cp config/historical_data_twelve_data.json config/historical_data.json
python -m historical.downloader
```

Or load a named profile directly:

```python
from pathlib import Path
from historical import HistoricalDownloader, load_historical_config

config = load_historical_config(Path("config/historical_data_twelve_data.json"))
HistoricalDownloader(config).download()
```

Notes:

- Free Basic: 8 requests/minute, 800/day, 5,000 points/request.
- 1-minute coverage for this key begins **2020-04-07**; earlier requests fail
  with a coverage error instead of silently writing partial data.
- Free tier is for internal/personal research. Commercial use requires a
  Twelve Data business plan; do not redistribute the data.
- `max_points_per_request`, `requests_per_minute`, and `api_key_env` are
  configurable; the key is read from the environment only.
- Providers can return bars during the FX weekly closure. Ingest filters them
  with the shared `fx_open_minutes_v1` rule and records the excluded count in
  `closure_filtered_count`; market closures remain distinguishable from gaps.

### Verified datasets in this workspace

| Pair | Requested | Actual | M1 bars | Trading days | Raw gaps | Quality |
|---|---:|---:|---:|---:|---:|---|
| EURUSD | 2026-01-01 → 2026-06-30 | 2026-01-01 13:00 → 2026-06-30 23:59 | 184,963 | 155 | 35 | valid; 10 unexpected gaps |
| GBPUSD | 2026-04-01 → 2026-06-30 | 2026-04-01 00:00 → 2026-06-30 23:59 | 93,600 | 78 | 13 | valid; closures only |
| USDJPY | 2026-04-01 → 2026-06-30 | 2026-04-01 00:00 → 2026-06-30 23:59 | 93,600 | 78 | 13 | valid; closures only |
| AUDUSD | 2026-04-01 → 2026-06-30 | 2026-04-01 00:00 → 2026-06-30 23:59 | 93,600 | 78 | 13 | valid; closures only |
| USDCAD | 2026-04-01 → 2026-06-30 | 2026-04-01 00:00 → 2026-06-30 23:59 | 93,600 | 78 | 13 | valid; closures only |

All five meet the one-week and one-month targets; EURUSD meets six months and
the other four meet three months. M5/M15/H1/H4 derivation was verified for all
five (0 invalid OHLC, aligned UTC buckets).

### Dukascopy

Configure `config/historical_data.json`, then download:

```bash
python -m historical.downloader
```

Data is stored under `data/historical/{SYMBOL}/M1/{YEAR}.csv` with a
`.meta.json` containing provider, requested/actual coverage, retrieval time,
record counts, and data-quality findings.

If a partition already names a different provider in its metadata, the
downloader refuses to merge it; use a separate `data_directory` (for example
`data/historical_twelve_data`) or enable `overwrite_existing_files`. Legacy
files without metadata cannot be attributed, so prefer a fresh directory when
switching providers.

Load bars in research code:

```python
from datetime import date
from historical import HistoricalDataProvider

bars = HistoricalDataProvider().get_bars(
    "EURUSD",
    "M1",
    date(2024, 1, 1),
    date(2024, 12, 31),
)
```

---

## Running a backtest

Signal study (counts signals; outcomes only if you supply an outcome provider):

```python
from backtests.backtest_runner import BacktestRunner
from strategies.liquidity_sweep import LiquiditySweepStrategy

strategy = LiquiditySweepStrategy(lookback=10)
result = BacktestRunner().run(strategy, bars)
result.export_json(output_path)
```

Trade simulation (factory → validator → planner → simulator):

```python
from execution import FixedRiskRewardPolicy, FixedRiskSizer, TradePlanner

planner = TradePlanner(
    policy=FixedRiskRewardPolicy(r_multiple=2.0),
    sizer=FixedRiskSizer(),
)
result = BacktestRunner().run(
    strategy,
    bars,
    simulate_trades=True,
    trade_planner=planner,  # optional; defaults are created if omitted
)
```

**Note:** The default `SweepTradeSetupFactory` handles liquidity-sweep signals only. Other signal types are rejected at the opportunity boundary. Pipeline details: [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).

Registry usage:

```python
from strategies.registry import build_default_registry

registry = build_default_registry()
strategy = registry.create("S008", lookback=10)
```

---

## Testing

```bash
python -m unittest discover -s tests -v
```

---

## Adding a strategy

1. Follow [research/README.md](research/README.md) (hypothesis first).
2. Add a `BaseStrategy` subclass under `strategies/` with `strategy_id`, `strategy_name`, `description`.
3. Implement `generate_signals(self, candles: Sequence[Bar]) -> list[Signal]`.
4. Add tests; run the suite above.

Engineering expectations: [PRINCIPLES.md](PRINCIPLES.md).  
What exists today: [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).
