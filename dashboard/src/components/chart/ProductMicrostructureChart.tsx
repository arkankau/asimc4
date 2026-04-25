import { useMemo, useRef, type MouseEvent as ReactMouseEvent, type WheelEvent } from "react";
import { ChartContainer } from "./ChartContainer";
import { useDashboard } from "../../state/DashboardProvider";
import { formatPrice, formatQuantity, formatSignedValue, formatTimestamp } from "../../utils/formatters";
import { buildInspectionState, findNearestEventByScreenX } from "../../utils/marketSelectors";
import { getTraderClassColor, TRADER_CLASS_COLOR_ORDER } from "../../utils/traderClassColors";
import type { ChartViewport, IndicatorSeries, MarketEvent } from "../../types/market";

const CHART_WIDTH = 920;
const CHART_HEIGHT = 460;
const PADDING = { top: 20, right: 20, bottom: 36, left: 64 };
const MIN_ZOOM_SPAN_RATIO = 0.04;
const ZOOM_IN_FACTOR = 0.85;
const ZOOM_OUT_FACTOR = 1.2;

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

function createPannedViewport(
  current: ChartViewport,
  fullBounds: ChartViewport,
  deltaTimestamp: number,
  deltaPrice: number,
): ChartViewport | null {
  const timeSpan = current.maxTimestamp - current.minTimestamp;
  const priceSpan = current.maxPrice - current.minPrice;

  if (timeSpan <= 0 || priceSpan <= 0) {
    return null;
  }

  let nextMinTimestamp = current.minTimestamp + deltaTimestamp;
  let nextMaxTimestamp = current.maxTimestamp + deltaTimestamp;
  let nextMinPrice = current.minPrice + deltaPrice;
  let nextMaxPrice = current.maxPrice + deltaPrice;

  if (nextMinTimestamp < fullBounds.minTimestamp) {
    nextMinTimestamp = fullBounds.minTimestamp;
    nextMaxTimestamp = fullBounds.minTimestamp + timeSpan;
  }
  if (nextMaxTimestamp > fullBounds.maxTimestamp) {
    nextMaxTimestamp = fullBounds.maxTimestamp;
    nextMinTimestamp = fullBounds.maxTimestamp - timeSpan;
  }

  if (nextMinPrice < fullBounds.minPrice) {
    nextMinPrice = fullBounds.minPrice;
    nextMaxPrice = fullBounds.minPrice + priceSpan;
  }
  if (nextMaxPrice > fullBounds.maxPrice) {
    nextMaxPrice = fullBounds.maxPrice;
    nextMinPrice = fullBounds.maxPrice - priceSpan;
  }

  const unchanged =
    Math.abs(nextMinTimestamp - current.minTimestamp) < 0.0001 &&
    Math.abs(nextMaxTimestamp - current.maxTimestamp) < 0.0001 &&
    Math.abs(nextMinPrice - current.minPrice) < 0.0001 &&
    Math.abs(nextMaxPrice - current.maxPrice) < 0.0001;

  if (unchanged) {
    return current;
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

function createDiamondPoints(cx: number, cy: number, radius: number) {
  return `${cx},${cy - radius} ${cx + radius},${cy} ${cx},${cy + radius} ${cx - radius},${cy}`;
}

function createTrianglePoints(cx: number, cy: number, radius: number, side: MarketEvent["side"]) {
  if (side === "sell") {
    return `${cx},${cy + radius} ${cx + radius},${cy - radius} ${cx - radius},${cy - radius}`;
  }

  return `${cx},${cy - radius} ${cx + radius},${cy + radius} ${cx - radius},${cy + radius}`;
}

function findNearestIndicatorPoint(series: IndicatorSeries, timestamp: number | null) {
  if (timestamp === null || series.points.length === 0) {
    return null;
  }

  return series.points.reduce<{ timestamp: number; value: number } | null>((closest, point) => {
    if (!closest) {
      return point;
    }

    return Math.abs(point.timestamp - timestamp) < Math.abs(closest.timestamp - timestamp) ? point : closest;
  }, null);
}

function collectDisplayBounds(values: number[], timestamps: number[]) {
  if (values.length === 0 || timestamps.length === 0) {
    return {
      minTimestamp: 0,
      maxTimestamp: 1,
      minPrice: -1,
      maxPrice: 1,
    };
  }

  const minPrice = Math.min(...values);
  const maxPrice = Math.max(...values);
  const padding = Math.max((maxPrice - minPrice) * 0.08, 0.5);

  return {
    minTimestamp: Math.min(...timestamps),
    maxTimestamp: Math.max(...timestamps),
    minPrice: minPrice - padding,
    maxPrice: maxPrice + padding,
  };
}

function buildSeriesPath(
  points: Array<{ timestamp: number; displayValue: number }>,
  xScale: (timestamp: number) => number,
  yScale: (value: number) => number,
) {
  return points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${xScale(point.timestamp)} ${yScale(point.displayValue)}`)
    .join(" ");
}

function formatAxisValue(value: number, normalized: boolean) {
  return normalized ? formatSignedValue(value) : formatPrice(value);
}

export function ProductMicrostructureChart() {
  const { state, selectedProduct, chartSeries, inspection, dispatch } = useDashboard();
  const svgRef = useRef<SVGSVGElement | null>(null);
  const plotWidth = CHART_WIDTH - PADDING.left - PADDING.right;
  const plotHeight = CHART_HEIGHT - PADDING.top - PADDING.bottom;
  const hasBook = chartSeries.visibleBids.length > 0 || chartSeries.visibleAsks.length > 0;
  const normalizationEnabled = state.overlays.normalizationMode === "indicator";

  const xScale = (timestamp: number) => {
    const span = Math.max(chartSeries.viewport.maxTimestamp - chartSeries.viewport.minTimestamp, 1);
    return PADDING.left + ((timestamp - chartSeries.viewport.minTimestamp) / span) * plotWidth;
  };

  const normalizationReferenceSeries = useMemo(() => {
    if (!normalizationEnabled || chartSeries.visibleIndicators.length === 0) {
      return null;
    }

    return (
      chartSeries.visibleIndicators.find((series) => series.id === "mid-price") ??
      chartSeries.visibleIndicators[0] ??
      null
    );
  }, [chartSeries.visibleIndicators, normalizationEnabled]);

  const getDisplayValue = useMemo(() => {
    return (timestamp: number, rawValue: number) => {
      if (!normalizationEnabled || !normalizationReferenceSeries) {
        return rawValue;
      }

      const referencePoint = findNearestIndicatorPoint(normalizationReferenceSeries, timestamp);
      return referencePoint ? rawValue - referencePoint.value : rawValue;
    };
  }, [normalizationEnabled, normalizationReferenceSeries]);

  const midPriceSeries = chartSeries.visibleIndicators.find((series) => series.id === "mid-price") ?? null;
  const overlayIndicators = chartSeries.visibleIndicators.filter((series) => series.id !== "mid-price");

  const quotePaths = useMemo(
    () =>
      (["bid", "ask"] as const).flatMap((kind) =>
        state.overlays.depthLevels.map((level) => ({
          key: `${kind}-${level}`,
          kind,
          level,
          points: buildQuotePath(kind === "bid" ? chartSeries.visibleBids : chartSeries.visibleAsks, level).map(
            ({ event, index }) => ({
              index,
              event,
              displayValue: getDisplayValue(event.timestamp, event.price),
            }),
          ),
        })),
      ),
    [chartSeries.visibleAsks, chartSeries.visibleBids, getDisplayValue, state.overlays.depthLevels],
  );

  const displayedMidPricePoints = useMemo(
    () =>
      (midPriceSeries?.points ?? []).map((point) => ({
        timestamp: point.timestamp,
        value: point.value,
        displayValue: getDisplayValue(point.timestamp, point.value),
      })),
    [getDisplayValue, midPriceSeries],
  );

  const displayedOverlayIndicators = useMemo(
    () =>
      overlayIndicators.map((series) => ({
        ...series,
        displayPoints: series.points.map((point) => ({
          timestamp: point.timestamp,
          value: point.value,
          displayValue: getDisplayValue(point.timestamp, point.value),
        })),
      })),
    [getDisplayValue, overlayIndicators],
  );

  const displayedMarketTrades = useMemo(
    () =>
      chartSeries.visibleTrades.map((event) => ({
        ...event,
        displayValue: getDisplayValue(event.timestamp, event.price),
      })),
    [chartSeries.visibleTrades, getDisplayValue],
  );

  const displayedOwnTrades = useMemo(
    () =>
      chartSeries.visibleOwnTrades.map((event) => ({
        ...event,
        displayValue: getDisplayValue(event.timestamp, event.price),
      })),
    [chartSeries.visibleOwnTrades, getDisplayValue],
  );

  const displayBounds = useMemo(() => {
    const values = [
      ...quotePaths.flatMap(({ points }) => points.map((point) => point.displayValue)),
      ...displayedMidPricePoints.map((point) => point.displayValue),
      ...displayedOverlayIndicators.flatMap((series) => series.displayPoints.map((point) => point.displayValue)),
      ...displayedMarketTrades.map((event) => event.displayValue),
      ...displayedOwnTrades.map((event) => event.displayValue),
    ];
    const timestamps = [
      ...quotePaths.flatMap(({ points }) => points.map((point) => point.event.timestamp)),
      ...displayedMidPricePoints.map((point) => point.timestamp),
      ...displayedOverlayIndicators.flatMap((series) => series.displayPoints.map((point) => point.timestamp)),
      ...displayedMarketTrades.map((event) => event.timestamp),
      ...displayedOwnTrades.map((event) => event.timestamp),
    ];

    return collectDisplayBounds(values, timestamps);
  }, [displayedMarketTrades, displayedMidPricePoints, displayedOverlayIndicators, displayedOwnTrades, quotePaths]);
  const hasRenderableData =
    quotePaths.some(({ points }) => points.length > 0) ||
    displayedMidPricePoints.length > 0 ||
    displayedOverlayIndicators.some((series) => series.displayPoints.length > 0) ||
    displayedMarketTrades.length > 0 ||
    displayedOwnTrades.length > 0;

  const yScale = (value: number) => {
    const span = Math.max(displayBounds.maxPrice - displayBounds.minPrice, 1);
    return PADDING.top + plotHeight - ((value - displayBounds.minPrice) / span) * plotHeight;
  };

  const hoveredX = inspection.hoveredEvent ? xScale(inspection.hoveredEvent.timestamp) : null;
  const hoveredDisplayValue =
    inspection.hoveredTimestamp !== null && inspection.hoveredPrice !== null
      ? getDisplayValue(inspection.hoveredTimestamp, inspection.hoveredPrice)
      : null;
  const hoveredY = hoveredDisplayValue !== null ? yScale(hoveredDisplayValue) : null;
  const indicatorSnapshots = useMemo(
    () =>
      chartSeries.visibleIndicators
        .map((series) => {
          const nearest = findNearestIndicatorPoint(series, inspection.hoveredTimestamp);
          return nearest
            ? {
                id: series.id,
                label: series.label,
                color: series.color,
                value: nearest.value,
                displayValue: getDisplayValue(nearest.timestamp, nearest.value),
                timestamp: nearest.timestamp,
              }
            : null;
        })
        .filter((entry): entry is NonNullable<typeof entry> => entry !== null),
    [chartSeries.visibleIndicators, getDisplayValue, inspection.hoveredTimestamp],
  );

  const handleMove = (event: ReactMouseEvent<SVGSVGElement>) => {
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

    const currentViewport = state.chartViewport ?? chartSeries.fullBounds;
    const isZoomed =
      state.chartViewport !== null &&
      (Math.abs(currentViewport.minTimestamp - chartSeries.fullBounds.minTimestamp) > 0.0001 ||
        Math.abs(currentViewport.maxTimestamp - chartSeries.fullBounds.maxTimestamp) > 0.0001 ||
        Math.abs(currentViewport.minPrice - chartSeries.fullBounds.minPrice) > 0.0001 ||
        Math.abs(currentViewport.maxPrice - chartSeries.fullBounds.maxPrice) > 0.0001);

    if (event.ctrlKey || event.metaKey) {
      event.preventDefault();

      const rect = svgRef.current.getBoundingClientRect();
      const chartX = clamp(event.clientX - rect.left, PADDING.left, CHART_WIDTH - PADDING.right);
      const chartY = clamp(event.clientY - rect.top, PADDING.top, CHART_HEIGHT - PADDING.bottom);
      const zoomFactor = event.deltaY < 0 ? ZOOM_IN_FACTOR : ZOOM_OUT_FACTOR;

      dispatch({
        type: "setChartViewport",
        viewport: createZoomedViewport(
          currentViewport,
          chartSeries.fullBounds,
          chartX,
          chartY,
          plotWidth,
          plotHeight,
          zoomFactor,
        ),
      });
      return;
    }

    if (!isZoomed) {
      return;
    }

    event.preventDefault();

    const timeSpan = Math.max(currentViewport.maxTimestamp - currentViewport.minTimestamp, 1);
    const priceSpan = Math.max(currentViewport.maxPrice - currentViewport.minPrice, 1);
    const deltaTimestamp = (((Math.abs(event.deltaX) > 0 ? event.deltaX : event.deltaY) / plotWidth) * timeSpan);
    const deltaPrice = (event.shiftKey ? event.deltaY / plotHeight : 0) * priceSpan;

    dispatch({
      type: "setChartViewport",
      viewport: createPannedViewport(currentViewport, chartSeries.fullBounds, deltaTimestamp, deltaPrice),
    });
  };

  const handleZoomButton = (zoomFactor: number) => {
    const currentViewport = state.chartViewport ?? chartSeries.fullBounds;
    dispatch({
      type: "setChartViewport",
      viewport: createZoomedViewport(
        currentViewport,
        chartSeries.fullBounds,
        PADDING.left + plotWidth / 2,
        PADDING.top + plotHeight / 2,
        plotWidth,
        plotHeight,
        zoomFactor,
      ),
    });
  };

  return (
    <ChartContainer
      title="Product Microstructure Review"
      subtitle={
        selectedProduct
          ? `${selectedProduct.product.displayName} price, order book, trades, and indicator context`
          : "Select a product to inspect market behavior"
      }
      aside={
        <div className="chart-card__aside-group">
          <span className="chart-card__stat">{chartSeries.visibleEvents.length} visible events</span>
          {hasBook ? <span className="chart-card__stat">Book + trades</span> : <span className="chart-card__stat">Trades only</span>}
          {normalizationEnabled && normalizationReferenceSeries ? (
            <span className="chart-card__stat">Normalized to {normalizationReferenceSeries.label}</span>
          ) : null}
          <button className="chart-card__button" type="button" onClick={() => handleZoomButton(ZOOM_IN_FACTOR)}>
            Zoom In +
          </button>
          <button className="chart-card__button" type="button" onClick={() => handleZoomButton(ZOOM_OUT_FACTOR)}>
            Zoom Out -
          </button>
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
      {selectedProduct === null || !hasRenderableData ? (
        <div className="chart-tooltip chart-tooltip--empty">
          No market microstructure data is available for the selected product under the current filters.
        </div>
      ) : (
        <>
          <div className="chart-class-legend">
            <span className="chart-class-legend__item">
              <span className="chart-class-legend__dot" style={{ backgroundColor: "#f4c95d" }} />
              Mid / anchor
            </span>
            {state.visibility.bids ? (
              <span className="chart-class-legend__item">
                <span className="chart-class-legend__dot" style={{ backgroundColor: "#4ea66e" }} />
                Bid ladder
              </span>
            ) : null}
            {state.visibility.asks ? (
              <span className="chart-class-legend__item">
                <span className="chart-class-legend__dot" style={{ backgroundColor: "#d06464" }} />
                Ask ladder
              </span>
            ) : null}
            {state.visibility.trades ? (
              <span className="chart-class-legend__item">Market trades: triangle / size by qty</span>
            ) : null}
            {state.visibility.ownTrades ? (
              <span className="chart-class-legend__item">Our trades: diamond</span>
            ) : null}
          </div>
          <svg
            ref={svgRef}
            className="market-chart"
            viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
            role="img"
            aria-label="Product microstructure chart"
            onMouseMove={handleMove}
            onMouseLeave={handleLeave}
            onWheel={handleWheel}
            onDoubleClick={() => dispatch({ type: "resetChartViewport" })}
          >
            <rect x="0" y="0" width={CHART_WIDTH} height={CHART_HEIGHT} fill="#10151d" rx="12" />

            {Array.from({ length: 5 }, (_, index) => {
              const y = PADDING.top + (plotHeight / 4) * index;
              const price = displayBounds.maxPrice - ((displayBounds.maxPrice - displayBounds.minPrice) / 4) * index;

              return (
                <g key={`grid-y-${index}`}>
                  <line x1={PADDING.left} y1={y} x2={CHART_WIDTH - PADDING.right} y2={y} className="chart-grid" />
                  <text x={PADDING.left - 10} y={y + 4} className="chart-axis-label">
                    {formatAxisValue(price, normalizationEnabled)}
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

            {normalizationEnabled ? (
              <line
                x1={PADDING.left}
                y1={yScale(0)}
                x2={CHART_WIDTH - PADDING.right}
                y2={yScale(0)}
                className="chart-grid chart-grid--vertical"
              />
            ) : null}

            {displayedMidPricePoints.length > 0 ? (
              <path
                d={buildSeriesPath(displayedMidPricePoints, xScale, yScale)}
                fill="none"
                stroke="#f4c95d"
                strokeWidth="1.3"
                strokeDasharray="6 4"
                opacity="0.82"
              />
            ) : null}

            {displayedOverlayIndicators.map((series) =>
              series.displayPoints.length > 0 ? (
                <path
                  key={series.id}
                  d={buildSeriesPath(series.displayPoints, xScale, yScale)}
                  fill="none"
                  stroke={series.color}
                  strokeWidth="1.5"
                  opacity="0.9"
                />
              ) : null,
            )}

            {quotePaths.map(({ key, kind, level, points }) =>
              points.length > 0 ? (
                <path
                  key={key}
                  d={points
                    .map(({ event, displayValue, index }) =>
                      `${index === 0 ? "M" : "L"} ${xScale(event.timestamp)} ${yScale(displayValue)}`,
                    )
                    .join(" ")}
                  fill="none"
                  stroke={kind === "bid" ? "#4ea66e" : "#d06464"}
                  strokeWidth={Math.max(0.55, 1.15 - (level - 1) * 0.18)}
                  opacity={Math.max(0.22, 0.48 - (level - 1) * 0.08)}
                />
              ) : null,
            )}

            {displayedMarketTrades.map((event) => {
              const radius = 2.3 + Math.min(event.quantity, 10) * 0.24;
              const cx = xScale(event.timestamp);
              const cy = yScale(event.displayValue);

              return (
                <polygon
                  key={event.id}
                  points={createTrianglePoints(cx, cy, radius, event.side)}
                  fill={getTraderClassColor(event.traderClass)}
                  opacity={0.82}
                  stroke="#0d131a"
                  strokeWidth="1.1"
                />
              );
            })}

            {displayedOwnTrades.map((event) => {
              const radius = 4 + Math.min(event.quantity, 12) * 0.12;
              const cx = xScale(event.timestamp);
              const cy = yScale(event.displayValue);

              return (
                <polygon
                  key={event.id}
                  points={createDiamondPoints(cx, cy, radius)}
                  fill={getTraderClassColor(event.traderClass)}
                  opacity={0.96}
                  stroke="#fff4"
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

          <div className="chart-class-legend">
            {TRADER_CLASS_COLOR_ORDER.map((traderClass) => (
              <span className="chart-class-legend__item" key={traderClass}>
                <span className="chart-class-legend__dot" style={{ backgroundColor: getTraderClassColor(traderClass) }} />
                {traderClass}
              </span>
            ))}
          </div>

          {inspection.hoveredTimestamp !== null ? (
            <div className="chart-tooltip">
              <strong>{inspection.hoveredEvent ? inspection.hoveredEvent.label : "Nearest market context"}</strong>
              <span>{formatTimestamp(inspection.hoveredTimestamp)}</span>
              <span>
                Hovered {normalizationEnabled ? "delta" : "price"}{" "}
                {hoveredDisplayValue !== null ? formatAxisValue(hoveredDisplayValue, normalizationEnabled) : "n/a"}
              </span>
              <span>Bid {formatPrice(inspection.nearestVisibleBid?.price ?? null)}</span>
              <span>Ask {formatPrice(inspection.nearestVisibleAsk?.price ?? null)}</span>
              <span>
                Mid{" "}
                {inspection.nearestVisibleBid && inspection.nearestVisibleAsk
                  ? formatPrice((inspection.nearestVisibleBid.price + inspection.nearestVisibleAsk.price) / 2)
                  : formatPrice(midPriceSeries ? findNearestIndicatorPoint(midPriceSeries, inspection.hoveredTimestamp)?.value ?? null : null)}
              </span>
              <span>
                Trade{" "}
                {inspection.nearestVisibleOwnTrade
                  ? `${formatPrice(inspection.nearestVisibleOwnTrade.price)} x ${formatQuantity(inspection.nearestVisibleOwnTrade.quantity)} (ours)`
                  : inspection.nearestVisibleTrade
                    ? `${formatPrice(inspection.nearestVisibleTrade.price)} x ${formatQuantity(inspection.nearestVisibleTrade.quantity)}`
                    : "n/a"}
              </span>
              {inspection.hoveredEvent?.traderClass ? <span>Class {inspection.hoveredEvent.traderClass}</span> : null}
              {inspection.hoveredEvent?.traderGroup ? <span>Group {inspection.hoveredEvent.traderGroup}</span> : null}
              {inspection.hoveredEvent?.traderId ? <span>Trader {inspection.hoveredEvent.traderId}</span> : null}
              {inspection.hoveredEvent?.tradeType ? <span>Flow {inspection.hoveredEvent.tradeType}</span> : null}
              {indicatorSnapshots.map((series) => (
                <span key={series.id}>
                  {series.label} {normalizationEnabled ? formatSignedValue(series.displayValue) : formatPrice(series.value)}
                </span>
              ))}
            </div>
          ) : (
            <div className="chart-tooltip chart-tooltip--empty">
              Hover to inspect timestamp, bid/ask, nearest trade, trader class, quantity, and visible indicator values.
              Use ctrl/cmd+wheel to zoom, scroll to pan through time when zoomed, shift+scroll to pan price, and
              double-click to reset.
            </div>
          )}
        </>
      )}
    </ChartContainer>
  );
}
