import { useMemo, useRef, useState } from "react";
import { ChartContainer } from "./ChartContainer";
import { useDashboard } from "../../state/DashboardProvider";
import { buildVisualizationPoints, collectChartBounds } from "../../utils/marketSelectors";
import { formatPrice, formatQuantity, formatTimestamp } from "../../utils/formatters";
import type { VisualizationPoint } from "../../types/market";

const CHART_WIDTH = 920;
const CHART_HEIGHT = 460;
const PADDING = { top: 20, right: 20, bottom: 36, left: 64 };

const colorBySide: Record<VisualizationPoint["side"], string> = {
  bid: "#4ea66e",
  ask: "#d06464",
  buy: "#58a6ff",
  sell: "#f0883e",
};

export function MarketChart() {
  const { state, selectedProduct, dispatch } = useDashboard();
  const points = useMemo(() => buildVisualizationPoints(selectedProduct, state), [selectedProduct, state]);
  const bounds = useMemo(() => collectChartBounds(points), [points]);
  const midPriceSeries = selectedProduct?.indicators.find((series) => series.id === "mid-price")?.points ?? [];
  const [tooltip, setTooltip] = useState<{ x: number; y: number; point: VisualizationPoint } | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  const plotWidth = CHART_WIDTH - PADDING.left - PADDING.right;
  const plotHeight = CHART_HEIGHT - PADDING.top - PADDING.bottom;

  const xScale = (timestamp: number) => {
    const span = Math.max(bounds.maxTimestamp - bounds.minTimestamp, 1);
    return PADDING.left + ((timestamp - bounds.minTimestamp) / span) * plotWidth;
  };

  const yScale = (price: number) => {
    const span = Math.max(bounds.maxPrice - bounds.minPrice, 1);
    return PADDING.top + plotHeight - ((price - bounds.minPrice) / span) * plotHeight;
  };

  const handleMove = (event: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current || points.length === 0) {
      return;
    }

    const rect = svgRef.current.getBoundingClientRect();
    const relativeX = event.clientX - rect.left;
    const hovered = points.reduce<VisualizationPoint | null>((closest, point) => {
      const pointX = xScale(point.timestamp);
      if (!closest) {
        return point;
      }

      return Math.abs(pointX - relativeX) < Math.abs(xScale(closest.timestamp) - relativeX) ? point : closest;
    }, null);

    if (!hovered) {
      return;
    }

    dispatch({ type: "setHoveredTimestamp", timestamp: hovered.timestamp });
    setTooltip({
      x: xScale(hovered.timestamp),
      y: yScale(hovered.price),
      point: hovered,
    });
  };

  const handleLeave = () => {
    dispatch({ type: "setHoveredTimestamp", timestamp: null });
    setTooltip(null);
  };

  const quotePaths = (["bid", "ask"] as const).flatMap((side) =>
    state.overlays.depthLevels.map((level) => {
      const path = points
        .filter((point) => point.kind === "quote" && point.side === side && point.level === level)
        .map((point, index) => `${index === 0 ? "M" : "L"} ${xScale(point.timestamp)} ${yScale(point.price)}`)
        .join(" ");

      return {
        key: `${side}-${level}`,
        side,
        level,
        path,
      };
    }),
  );

  const midPricePath = midPriceSeries
    .map((point, index) => `${index === 0 ? "M" : "L"} ${xScale(point.timestamp)} ${yScale(point.value)}`)
    .join(" ");

  return (
    <ChartContainer
      title="Market View"
      subtitle={selectedProduct ? `${selectedProduct.product.displayName} order book and trades` : "Load a dataset"}
      aside={<span className="chart-card__stat">{points.length} rendered points</span>}
    >
      <svg
        ref={svgRef}
        className="market-chart"
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        role="img"
        aria-label="Market chart"
        onMouseMove={handleMove}
        onMouseLeave={handleLeave}
      >
        <rect x="0" y="0" width={CHART_WIDTH} height={CHART_HEIGHT} fill="#10151d" rx="12" />

        {Array.from({ length: 5 }, (_, index) => {
          const y = PADDING.top + (plotHeight / 4) * index;
          const price = bounds.maxPrice - ((bounds.maxPrice - bounds.minPrice) / 4) * index;

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
          const timestamp = bounds.minTimestamp + ((bounds.maxTimestamp - bounds.minTimestamp) / 5) * index;

          return (
            <g key={`grid-x-${index}`}>
              <line x1={x} y1={PADDING.top} x2={x} y2={CHART_HEIGHT - PADDING.bottom} className="chart-grid chart-grid--vertical" />
              <text x={x} y={CHART_HEIGHT - 12} textAnchor="middle" className="chart-axis-label">
                {formatTimestamp(timestamp)}
              </text>
            </g>
          );
        })}

        {midPricePath ? (
          <path d={midPricePath} fill="none" stroke="#f4c95d" strokeWidth="1.5" strokeDasharray="6 5" opacity="0.7" />
        ) : null}

        {quotePaths.map(({ key, side, level, path }) =>
          path ? (
            <path
              key={key}
              d={path}
              fill="none"
              stroke={side === "bid" ? "#4ea66e" : "#d06464"}
              strokeWidth={Math.max(1, 2.6 - (level - 1) * 0.6)}
              opacity={Math.max(0.4, 0.95 - (level - 1) * 0.2)}
            />
          ) : null,
        )}

        {points
          .filter((point) => point.kind === "trade")
          .map((point) => (
            <circle
              key={`${point.kind}-${point.timestamp}-${point.price}-${point.side}`}
              cx={xScale(point.timestamp)}
              cy={yScale(point.price)}
              r={4 + Math.min(point.quantity, 5)}
              fill={colorBySide[point.side]}
              opacity={0.85}
              stroke="#0d1117"
              strokeWidth="1.5"
            />
          ))}

        {tooltip ? (
          <>
            <line
              x1={tooltip.x}
              y1={PADDING.top}
              x2={tooltip.x}
              y2={CHART_HEIGHT - PADDING.bottom}
              className="chart-crosshair"
            />
            <circle cx={tooltip.x} cy={tooltip.y} r={6} fill="#f4c95d" stroke="#fff1" />
          </>
        ) : null}
      </svg>

      {tooltip ? (
        <div className="chart-tooltip">
          <strong>{tooltip.point.label}</strong>
          <span>{formatTimestamp(tooltip.point.timestamp)}</span>
          <span>Price {formatPrice(tooltip.point.price)}</span>
          <span>Qty {formatQuantity(tooltip.point.quantity)}</span>
        </div>
      ) : (
        <div className="chart-tooltip chart-tooltip--empty">Hover the chart to inspect the nearest market event.</div>
      )}
    </ChartContainer>
  );
}
