import { useMemo, useRef, type WheelEvent } from "react";
import { ChartContainer } from "./ChartContainer";
import { useDashboard } from "../../state/DashboardProvider";
import { formatPrice, formatQuantity, formatTimestamp } from "../../utils/formatters";
import { buildInspectionState, findNearestEventByScreenX } from "../../utils/marketSelectors";
import type { ChartViewport, MarketEvent } from "../../types/market";

const CHART_WIDTH = 920;
const CHART_HEIGHT = 460;
const PADDING = { top: 20, right: 20, bottom: 36, left: 64 };
const MIN_ZOOM_SPAN_RATIO = 0.04;

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function createZoomedViewport(
  current: ChartViewport,
  fullBounds: ChartViewport,
  chartX: number,
  chartY: number,
  plotWidth: number,
  plotHeight: number,
  zoomFactor: number,
): ChartViewport | null {
  const timeSpan = Math.max(current.maxTimestamp - current.minTimestamp, 1);
  const priceSpan = Math.max(current.maxPrice - current.minPrice, 1);
  const fullTimeSpan = Math.max(fullBounds.maxTimestamp - fullBounds.minTimestamp, 1);
  const fullPriceSpan = Math.max(fullBounds.maxPrice - fullBounds.minPrice, 1);
  const minTimeSpan = Math.max(fullTimeSpan * MIN_ZOOM_SPAN_RATIO, 10);
  const minPriceSpan = Math.max(fullPriceSpan * MIN_ZOOM_SPAN_RATIO, 1);

  const targetTimeSpan = clamp(timeSpan * zoomFactor, minTimeSpan, fullTimeSpan);
  const targetPriceSpan = clamp(priceSpan * zoomFactor, minPriceSpan, fullPriceSpan);

  const cursorTimeRatio = (chartX - PADDING.left) / plotWidth;
  const cursorPriceRatio = 1 - (chartY - PADDING.top) / plotHeight;

  let nextMinTimestamp = current.minTimestamp + (timeSpan - targetTimeSpan) * cursorTimeRatio;
  let nextMaxTimestamp = nextMinTimestamp + targetTimeSpan;

  if (nextMinTimestamp < fullBounds.minTimestamp) {
    nextMinTimestamp = fullBounds.minTimestamp;
    nextMaxTimestamp = nextMinTimestamp + targetTimeSpan;
  }

  if (nextMaxTimestamp > fullBounds.maxTimestamp) {
    nextMaxTimestamp = fullBounds.maxTimestamp;
    nextMinTimestamp = nextMaxTimestamp - targetTimeSpan;
  }

  let nextMinPrice = current.minPrice + (priceSpan - targetPriceSpan) * cursorPriceRatio;
  let nextMaxPrice = nextMinPrice + targetPriceSpan;

  if (nextMinPrice < fullBounds.minPrice) {
    nextMinPrice = fullBounds.minPrice;
    nextMaxPrice = nextMinPrice + targetPriceSpan;
  }

  if (nextMaxPrice > fullBounds.maxPrice) {
    nextMaxPrice = fullBounds.maxPrice;
    nextMinPrice = nextMaxPrice - targetPriceSpan;
  }

  const isFullDomain =
    Math.abs(nextMinTimestamp - fullBounds.minTimestamp) < 1 &&
    Math.abs(nextMaxTimestamp - fullBounds.maxTimestamp) < 1 &&
    Math.abs(nextMinPrice - fullBounds.minPrice) < 0.0001 &&
    Math.abs(nextMaxPrice - fullBounds.maxPrice) < 0.0001;

  if (isFullDomain) {
    return null;
  }

  return {
    minTimestamp: nextMinTimestamp,
    maxTimestamp: nextMaxTimestamp,
    minPrice: nextMinPrice,
    maxPrice: nextMaxPrice,
  };
}

function buildQuotePath(events: MarketEvent[], level: number) {
  return events
    .filter((event) => event.level === level)
    .sort((left, right) => left.timestamp - right.timestamp)
    .map((event, index) => ({ index, event }));
}

function renderOwnTradeDiamond(cx: number, cy: number, radius: number) {
  return `${cx},${cy - radius} ${cx + radius},${cy} ${cx},${cy + radius} ${cx - radius},${cy}`;
}

export function MarketChart() {
  const { state, selectedProduct, chartSeries, inspection, dispatch } = useDashboard();
  const svgRef = useRef<SVGSVGElement | null>(null);
  const plotWidth = CHART_WIDTH - PADDING.left - PADDING.right;
  const plotHeight = CHART_HEIGHT - PADDING.top - PADDING.bottom;

  const xScale = (timestamp: number) => {
    const span = Math.max(chartSeries.viewport.maxTimestamp - chartSeries.viewport.minTimestamp, 1);
    return PADDING.left + ((timestamp - chartSeries.viewport.minTimestamp) / span) * plotWidth;
  };

  const yScale = (price: number) => {
    const span = Math.max(chartSeries.viewport.maxPrice - chartSeries.viewport.minPrice, 1);
    return PADDING.top + plotHeight - ((price - chartSeries.viewport.minPrice) / span) * plotHeight;
  };

  const midPriceSeries = chartSeries.visibleIndicators.find((series) => series.id === "mid-price");

  const quotePaths = useMemo(
    () =>
      (["bid", "ask"] as const).flatMap((kind) =>
        state.overlays.depthLevels.map((level) => ({
          key: `${kind}-${level}`,
          kind,
          level,
          points: buildQuotePath(kind === "bid" ? chartSeries.visibleBids : chartSeries.visibleAsks, level),
        })),
      ),
    [chartSeries.visibleAsks, chartSeries.visibleBids, state.overlays.depthLevels],
  );

  const hoveredX = inspection.hoveredEvent ? xScale(inspection.hoveredEvent.timestamp) : null;
  const hoveredY = inspection.hoveredEvent ? yScale(inspection.hoveredEvent.price) : null;

  const handleMove = (event: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current || chartSeries.visibleEvents.length === 0) {
      return;
    }

    const rect = svgRef.current.getBoundingClientRect();
    const relativeX = clamp(event.clientX - rect.left, PADDING.left, CHART_WIDTH - PADDING.right);
    const hoveredEvent = findNearestEventByScreenX(chartSeries.visibleEvents, relativeX, xScale);
    dispatch({
      type: "setInspection",
      inspection: buildInspectionState(selectedProduct, hoveredEvent, chartSeries),
    });
  };

  const handleLeave = () => {
    dispatch({ type: "clearInspection" });
  };

  const handleWheel = (event: WheelEvent<SVGSVGElement>) => {
    if (!svgRef.current || chartSeries.visibleEvents.length === 0) {
      return;
    }

    event.preventDefault();

    const rect = svgRef.current.getBoundingClientRect();
    const chartX = clamp(event.clientX - rect.left, PADDING.left, CHART_WIDTH - PADDING.right);
    const chartY = clamp(event.clientY - rect.top, PADDING.top, CHART_HEIGHT - PADDING.bottom);
    const zoomFactor = event.deltaY < 0 ? 0.82 : 1.22;

    dispatch({
      type: "setChartViewport",
      viewport: createZoomedViewport(
        state.chartViewport ?? chartSeries.fullBounds,
        chartSeries.fullBounds,
        chartX,
        chartY,
        plotWidth,
        plotHeight,
        zoomFactor,
      ),
    });
  };

  return (
    <ChartContainer
      title="Market View"
      subtitle={selectedProduct ? `${selectedProduct.product.displayName} market microstructure view` : "Load a dataset"}
      aside={
        <div className="chart-card__aside-group">
          <span className="chart-card__stat">{chartSeries.visibleEvents.length} visible events</span>
          {chartSeries.filterSummary.length > 0 ? <span className="chart-card__stat">{chartSeries.filterSummary[0]}</span> : null}
          <button
            className="chart-card__button"
            type="button"
            onClick={() => dispatch({ type: "resetChartViewport" })}
            disabled={!state.chartViewport}
          >
            Reset Zoom
          </button>
        </div>
      }
    >
      <svg
        ref={svgRef}
        className="market-chart"
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        role="img"
        aria-label="Market chart"
        onMouseMove={handleMove}
        onMouseLeave={handleLeave}
        onWheel={handleWheel}
        onDoubleClick={() => dispatch({ type: "resetChartViewport" })}
      >
        <rect x="0" y="0" width={CHART_WIDTH} height={CHART_HEIGHT} fill="#10151d" rx="12" />

        {Array.from({ length: 5 }, (_, index) => {
          const y = PADDING.top + (plotHeight / 4) * index;
          const price =
            chartSeries.viewport.maxPrice -
            ((chartSeries.viewport.maxPrice - chartSeries.viewport.minPrice) / 4) * index;

          return (
            <g key={`grid-y-${index}`}>
              <line x1={PADDING.left} y1={y} x2={CHART_WIDTH - PADDING.right} y2={y} className="chart-grid" />
              <text x={PADDING.left - 10} y={y + 4} className="chart-axis-label">
                {formatPrice(price)}
              </text>
            </g>
          );
        })}

        {Array.from({ length: 6 }, (_, index) => {
          const x = PADDING.left + (plotWidth / 5) * index;
          const timestamp =
            chartSeries.viewport.minTimestamp +
            ((chartSeries.viewport.maxTimestamp - chartSeries.viewport.minTimestamp) / 5) * index;

          return (
            <g key={`grid-x-${index}`}>
              <line x1={x} y1={PADDING.top} x2={x} y2={CHART_HEIGHT - PADDING.bottom} className="chart-grid chart-grid--vertical" />
              <text x={x} y={CHART_HEIGHT - 12} textAnchor="middle" className="chart-axis-label">
                {formatTimestamp(timestamp)}
              </text>
            </g>
          );
        })}

        {midPriceSeries ? (
          <path
            d={midPriceSeries.points
              .map((point, index) => `${index === 0 ? "M" : "L"} ${xScale(point.timestamp)} ${yScale(point.value)}`)
              .join(" ")}
            fill="none"
            stroke="#f4c95d"
            strokeWidth="1.2"
            strokeDasharray="6 4"
            opacity="0.7"
          />
        ) : null}

        {quotePaths.map(({ key, kind, level, points }) =>
          points.length > 0 ? (
            <path
              key={key}
              d={points.map(({ event, index }) => `${index === 0 ? "M" : "L"} ${xScale(event.timestamp)} ${yScale(event.price)}`).join(" ")}
              fill="none"
              stroke={kind === "bid" ? "#4ea66e" : "#d06464"}
              strokeWidth={Math.max(1, 2.6 - (level - 1) * 0.55)}
              opacity={Math.max(0.35, 0.95 - (level - 1) * 0.2)}
            />
          ) : null,
        )}

        {chartSeries.visibleTrades.map((event) => (
          <circle
            key={event.id}
            cx={xScale(event.timestamp)}
            cy={yScale(event.price)}
            r={1.2 + Math.min(event.quantity, 6) * 0.22}
            fill={event.side === "buy" ? "#58a6ff" : "#f0883e"}
            opacity={0.75}
            stroke="#0d1117"
            strokeWidth="0.8"
          />
        ))}

        {chartSeries.visibleOwnTrades.map((event) => {
          const cx = xScale(event.timestamp);
          const cy = yScale(event.price);
          const radius = 4.2;
          return (
            <polygon
              key={event.id}
              points={renderOwnTradeDiamond(cx, cy, radius)}
              fill="#f4c95d"
              opacity={0.95}
              stroke="#0d1117"
              strokeWidth="1"
            />
          );
        })}

        {hoveredX !== null ? (
          <line
            x1={hoveredX}
            y1={PADDING.top}
            x2={hoveredX}
            y2={CHART_HEIGHT - PADDING.bottom}
            className="chart-crosshair"
          />
        ) : null}

        {hoveredX !== null && hoveredY !== null ? (
          <circle cx={hoveredX} cy={hoveredY} r={5.5} fill="#f4c95d" stroke="#fff1" />
        ) : null}
      </svg>

      {inspection.hoveredEvent ? (
        <div className="chart-tooltip">
          <strong>{inspection.hoveredEvent.label}</strong>
          <span>{formatTimestamp(inspection.hoveredTimestamp)}</span>
          <span>Price {formatPrice(inspection.hoveredPrice)}</span>
          <span>Qty {formatQuantity(inspection.hoveredQuantity)}</span>
          <span>Type {inspection.hoveredEventType}</span>
          {inspection.hoveredEvent?.tradeType ? <span>Flow {inspection.hoveredEvent.tradeType}</span> : null}
        </div>
      ) : (
        <div className="chart-tooltip chart-tooltip--empty">
          Hover the chart to inspect the nearest event. Scroll to zoom and double-click to reset.
        </div>
      )}
    </ChartContainer>
  );
}
