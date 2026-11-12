import { useEffect, useRef } from "react";
import {
  ColorType,
  CrosshairMode,
  LineStyle,
  createChart,
  type IChartApi,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import type { BarPoint, CurvePoint, TradeRow } from "../types";
import { EmptyState } from "./Primitives";

const CHART_LAYOUT = {
  background: { type: ColorType.Solid as const, color: "transparent" },
  textColor: "#8f9bac",
  fontFamily: "Inter, Segoe UI, sans-serif",
  fontSize: 10,
  attributionLogo: false,
};

const GRID = {
  vertLines: { color: "rgba(165, 179, 199, 0.055)" },
  horzLines: { color: "rgba(165, 179, 199, 0.055)" },
};

const RIGHT_SCALE = {
  borderColor: "rgba(165, 179, 199, 0.14)",
  entireTextOnly: true,
};

const TIME_SCALE = {
  borderColor: "rgba(165, 179, 199, 0.14)",
  timeVisible: true,
  secondsVisible: false,
  rightOffset: 4,
  barSpacing: 6,
};

const CROSSHAIR = {
  mode: CrosshairMode.Normal,
  vertLine: {
    color: "rgba(79, 140, 255, 0.42)",
    width: 1 as const,
    style: LineStyle.Dashed,
    labelBackgroundColor: "#111927",
  },
  horzLine: {
    color: "rgba(79, 140, 255, 0.34)",
    width: 1 as const,
    style: LineStyle.Dashed,
    labelBackgroundColor: "#111927",
  },
};

function useChart(
  ref: React.RefObject<HTMLDivElement>,
  build: (chart: IChartApi) => void,
  dependencies: unknown[],
) {
  useEffect(() => {
    const container = ref.current;
    if (!container) return;
    const chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight,
      layout: CHART_LAYOUT,
      localization: { locale: "en-US" },
      grid: GRID,
      rightPriceScale: RIGHT_SCALE,
      timeScale: TIME_SCALE,
      crosshair: CROSSHAIR,
    });
    build(chart);
    const observer = new ResizeObserver(() => {
      chart.applyOptions({
        width: container.clientWidth,
        height: container.clientHeight,
      });
    });
    observer.observe(container);
    return () => {
      observer.disconnect();
      chart.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies);
}

function precisionFor(symbol: string): { precision: number; minMove: number } {
  if (symbol.includes("JPY")) return { precision: 3, minMove: 0.001 };
  if (symbol === "XAUUSD") return { precision: 2, minMove: 0.01 };
  return { precision: 5, minMove: 0.00001 };
}

export function PriceChart({
  bars,
  symbol,
  trades,
  tall = false,
}: {
  bars: BarPoint[];
  symbol: string;
  trades?: TradeRow[];
  tall?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useChart(
    ref,
    (chart) => {
      if (!bars.length) return;
      const series = chart.addCandlestickSeries({
        upColor: "#43cf9a",
        downColor: "#df6a6a",
        borderVisible: false,
        wickUpColor: "#43cf9a",
        wickDownColor: "#df6a6a",
        priceFormat: { type: "price", ...precisionFor(symbol) },
      });
      series.setData(
        bars.map((bar) => ({
          time: bar.time as UTCTimestamp,
          open: bar.open,
          high: bar.high,
          low: bar.low,
          close: bar.close,
        })),
      );

      if (trades?.length) {
        const first = bars[0].time;
        const last = bars[bars.length - 1].time;
        const markers: SeriesMarker<Time>[] = [];
        const inRange = trades.filter((trade) => {
          const entry = Math.floor(new Date(trade.entry_time).getTime() / 1000);
          return entry >= first && entry <= last;
        });
        const step = Math.max(1, Math.ceil(inRange.length / 80));
        const sampled = inRange.filter((_, index) => index % step === 0);
        for (const trade of sampled) {
          const entry = Math.floor(new Date(trade.entry_time).getTime() / 1000);
          const exit = Math.floor(new Date(trade.exit_time).getTime() / 1000);
          if (entry >= first && entry <= last) {
            markers.push({
              time: entry as UTCTimestamp,
              position: trade.direction === "LONG" ? "belowBar" : "aboveBar",
              color: "#4f8cff",
              shape: trade.direction === "LONG" ? "arrowUp" : "arrowDown",
              text: trade.direction === "LONG" ? "L" : "S",
            });
          }
          if (exit >= first && exit <= last) {
            markers.push({
              time: exit as UTCTimestamp,
              position: trade.pnl_r >= 0 ? "aboveBar" : "belowBar",
              color: trade.pnl_r >= 0 ? "#43cf9a" : "#df6a6a",
              shape: "circle",
              text: `${trade.pnl_r > 0 ? "+" : ""}${trade.pnl_r.toFixed(1)}R`,
            });
          }
        }
        markers.sort((a, b) => Number(a.time) - Number(b.time));
        series.setMarkers(markers);
      }

      chart.timeScale().fitContent();
    },
    [bars, symbol, trades],
  );

  if (!bars.length) {
    return (
      <div className={`chart-frame ${tall ? "tall" : ""}`.trim()}>
        <EmptyState
          title="No price series"
          copy="Select a dataset with stored M1 bars to render a candlestick view."
        />
      </div>
    );
  }

  return (
    <div className={`chart-frame ${tall ? "tall" : ""}`.trim()}>
      <div className="chart-canvas" ref={ref} />
    </div>
  );
}

export function EquityCharts({
  equity,
  drawdown,
}: {
  equity: CurvePoint[];
  drawdown: CurvePoint[];
}) {
  const equityRef = useRef<HTMLDivElement>(null);
  const drawdownRef = useRef<HTMLDivElement>(null);

  useChart(
    equityRef,
    (chart) => {
      const series = chart.addAreaSeries({
        lineColor: "#4f8cff",
        topColor: "rgba(79, 140, 255, 0.2)",
        bottomColor: "rgba(79, 140, 255, 0.01)",
        lineWidth: 1,
        priceFormat: { type: "price", precision: 2, minMove: 0.01 },
      });
      series.setData(
        equity.map((point) => ({
          time: point.time as UTCTimestamp,
          value: point.value,
        })),
      );
      chart.timeScale().fitContent();
    },
    [equity],
  );

  useChart(
    drawdownRef,
    (chart) => {
      const series = chart.addAreaSeries({
        lineColor: "#df6a6a",
        topColor: "rgba(223, 106, 106, 0.18)",
        bottomColor: "rgba(223, 106, 106, 0.01)",
        lineWidth: 1,
        priceFormat: { type: "price", precision: 2, minMove: 0.01 },
      });
      series.setData(
        drawdown.map((point) => ({
          time: point.time as UTCTimestamp,
          value: point.value,
        })),
      );
      chart.timeScale().fitContent();
    },
    [drawdown],
  );

  if (!equity.length) {
    return (
      <EmptyState
        title="No simulated lifecycle"
        copy="This run produced no closed trades, so there is no cumulative R curve to plot."
      />
    );
  }

  return (
    <div className="stack">
      <div>
        <div className="chart-legend">
          <span className="legend-item">
            <span className="legend-swatch" /> Cumulative R
          </span>
          <span>R-multiples · not currency equity</span>
        </div>
        <div className="chart-frame short">
          <div className="chart-canvas" ref={equityRef} />
        </div>
      </div>
      <div>
        <div className="chart-legend">
          <span className="legend-item">
            <span className="legend-swatch crimson" /> Drawdown (R)
          </span>
          <span>Peak-to-trough of cumulative R</span>
        </div>
        <div className="chart-frame short">
          <div className="chart-canvas" ref={drawdownRef} />
        </div>
      </div>
    </div>
  );
}
