import { useMemo, useState } from "react";
import { ChartContainer } from "./ChartContainer";
import { useDashboard } from "../../state/DashboardProvider";
import { aggregateDatasetPnlSeries } from "../../utils/marketSelectors";
import { formatSignedValue, formatTimestamp } from "../../utils/formatters";

const CHART_WIDTH = 920;
const CHART_HEIGHT = 420;
const PADDING = { top: 18, right: 18, bottom: 34, left: 72 };

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function findNearestPoint<T extends { timestamp: number }>(points: T[], timestamp: number | null) {
  if (timestamp === null || points.length === 0) {
    return null;
  }

  return points.reduce<T | null>((closest, current) => {
    if (!closest) {
      return current;
    }

    return Math.abs(current.timestamp - timestamp) < Math.abs(closest.timestamp - timestamp) ? current : closest;
  }, null);
}

export function BacktestChart() {
  const { selectedDataset, selectedProduct } = useDashboard();
  const [hoveredTimestamp, setHoveredTimestamp] = useState<number | null>(null);

  const datasetSeries = useMemo(() => aggregateDatasetPnlSeries(selectedDataset), [selectedDataset]);
  const productSeries = selectedProduct?.pnlSeries ?? [];
  const chartPoints = [...datasetSeries, ...productSeries];

  const minTimestamp = chartPoints.length ? Math.min(...chartPoints.map((point) => point.timestamp)) : 0;
  const maxTimestamp = chartPoints.length ? Math.max(...chartPoints.map((point) => point.timestamp)) : 1;
  const minValue = chartPoints.length ? Math.min(...chartPoints.map((point) => point.value)) : 0;
  const maxValue = chartPoints.length ? Math.max(...chartPoints.map((point) => point.value)) : 1;
  const xSpan = Math.max(maxTimestamp - minTimestamp, 1);
  const valuePadding = Math.max((maxValue - minValue) * 0.08, 1);
  const paddedMinValue = minValue - valuePadding;
  const paddedMaxValue = maxValue + valuePadding;
  const ySpan = Math.max(paddedMaxValue - paddedMinValue, 1);
  const plotWidth = CHART_WIDTH - PADDING.left - PADDING.right;
  const plotHeight = CHART_HEIGHT - PADDING.top - PADDING.bottom;

  const scaleX = (timestamp: number) => PADDING.left + ((timestamp - minTimestamp) / xSpan) * plotWidth;
  const scaleY = (value: number) => PADDING.top + plotHeight - ((value - paddedMinValue) / ySpan) * plotHeight;

  const datasetPath = datasetSeries
    .map((point, index) => `${index === 0 ? "M" : "L"} ${scaleX(point.timestamp)} ${scaleY(point.value)}`)
    .join(" ");
  const productPath = productSeries
    .map((point, index) => `${index === 0 ? "M" : "L"} ${scaleX(point.timestamp)} ${scaleY(point.value)}`)
    .join(" ");

  const hoveredDatasetPoint = findNearestPoint(datasetSeries, hoveredTimestamp);
  const hoveredProductPoint = findNearestPoint(productSeries, hoveredTimestamp);
  const activeTimestamp = hoveredProductPoint?.timestamp ?? hoveredDatasetPoint?.timestamp ?? null;
  const hoveredX = activeTimestamp !== null ? scaleX(activeTimestamp) : null;

  return (
    <ChartContainer
      title="Backtest Equity"
      subtitle={
        selectedProduct
          ? `${selectedProduct.product.displayName} contribution against total dataset PnL`
          : "Select a product to compare against total PnL"
      }
      aside={
        <div className="chart-card__aside-group">
          <span className="chart-card__stat">Submission mode</span>
          <span className="chart-card__stat">{datasetSeries.length} pnl points</span>
        </div>
      }
    >
      {chartPoints.length === 0 ? (
        <div className="chart-tooltip chart-tooltip--empty">No PnL series available for this dataset.</div>
      ) : (
        <>
          <div className="pnl-preview__legend">
            <span className="pnl-preview__key pnl-preview__key--dataset">Dataset total</span>
            <span className="pnl-preview__key pnl-preview__key--product">Selected product</span>
          </div>
          <svg
            className="market-chart"
            viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
            role="img"
            aria-label="Backtest equity chart"
            onMouseMove={(event) => {
              const rect = event.currentTarget.getBoundingClientRect();
              const relativeX = clamp(event.clientX - rect.left, PADDING.left, CHART_WIDTH - PADDING.right);
              const estimatedTimestamp = minTimestamp + ((relativeX - PADDING.left) / plotWidth) * xSpan;
              setHoveredTimestamp(estimatedTimestamp);
            }}
            onMouseLeave={() => setHoveredTimestamp(null)}
          >
            <rect x="0" y="0" width={CHART_WIDTH} height={CHART_HEIGHT} fill="#10151d" rx="12" />

            {Array.from({ length: 5 }, (_, index) => {
              const y = PADDING.top + (plotHeight / 4) * index;
              const value = paddedMaxValue - ((paddedMaxValue - paddedMinValue) / 4) * index;

              return (
                <g key={`equity-grid-y-${index}`}>
                  <line x1={PADDING.left} y1={y} x2={CHART_WIDTH - PADDING.right} y2={y} className="chart-grid" />
                  <text x={PADDING.left - 10} y={y + 4} className="chart-axis-label">
                    {value.toFixed(0)}
                  </text>
                </g>
              );
            })}

            {Array.from({ length: 6 }, (_, index) => {
              const x = PADDING.left + (plotWidth / 5) * index;
              const timestamp = minTimestamp + ((maxTimestamp - minTimestamp) / 5) * index;

              return (
                <g key={`equity-grid-x-${index}`}>
                  <line x1={x} y1={PADDING.top} x2={x} y2={CHART_HEIGHT - PADDING.bottom} className="chart-grid chart-grid--vertical" />
                  <text x={x} y={CHART_HEIGHT - 12} textAnchor="middle" className="chart-axis-label">
                    {formatTimestamp(timestamp)}
                  </text>
                </g>
              );
            })}

            {datasetPath ? <path d={datasetPath} fill="none" stroke="#58a6ff" strokeWidth="2.4" /> : null}
            {productPath ? <path d={productPath} fill="none" stroke="#f4c95d" strokeWidth="2.1" /> : null}

            {hoveredX !== null ? (
              <line
                x1={hoveredX}
                y1={PADDING.top}
                x2={hoveredX}
                y2={CHART_HEIGHT - PADDING.bottom}
                className="chart-crosshair"
              />
            ) : null}

            {hoveredDatasetPoint ? (
              <circle cx={scaleX(hoveredDatasetPoint.timestamp)} cy={scaleY(hoveredDatasetPoint.value)} r="4" fill="#58a6ff" />
            ) : null}
            {hoveredProductPoint ? (
              <circle cx={scaleX(hoveredProductPoint.timestamp)} cy={scaleY(hoveredProductPoint.value)} r="4" fill="#f4c95d" />
            ) : null}
          </svg>

          <div className="chart-tooltip">
            <span>{activeTimestamp !== null ? formatTimestamp(activeTimestamp) : "Hover the equity curve"}</span>
            <strong>Total {formatSignedValue(hoveredDatasetPoint?.value ?? datasetSeries[datasetSeries.length - 1]?.value ?? null)}</strong>
            <strong>
              Product {formatSignedValue(hoveredProductPoint?.value ?? productSeries[productSeries.length - 1]?.value ?? null)}
            </strong>
          </div>
        </>
      )}
    </ChartContainer>
  );
}
