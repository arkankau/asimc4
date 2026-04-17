import { Panel } from "./Panel";
import { useDashboard } from "../../state/DashboardProvider";
import { aggregateDatasetPnlSeries, derivePnlSummary } from "../../utils/marketSelectors";
import { formatPercent, formatSignedValue, formatTimestamp } from "../../utils/formatters";

const CHART_WIDTH = 420;
const CHART_HEIGHT = 180;
const CHART_PADDING = { top: 14, right: 12, bottom: 20, left: 10 };

function buildPath(
  points: Array<{ timestamp: number; value: number }>,
  minTimestamp: number,
  maxTimestamp: number,
  minValue: number,
  maxValue: number,
) {
  const plotWidth = CHART_WIDTH - CHART_PADDING.left - CHART_PADDING.right;
  const plotHeight = CHART_HEIGHT - CHART_PADDING.top - CHART_PADDING.bottom;
  const timeSpan = Math.max(maxTimestamp - minTimestamp, 1);
  const valueSpan = Math.max(maxValue - minValue, 1);

  return points
    .map((point, index) => {
      const x = CHART_PADDING.left + ((point.timestamp - minTimestamp) / timeSpan) * plotWidth;
      const y =
        CHART_PADDING.top + plotHeight - ((point.value - minValue) / valueSpan) * plotHeight;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

export function PnlPanel() {
  const { selectedProduct, selectedDataset, inspection } = useDashboard();
  const summary = derivePnlSummary(selectedProduct, inspection, selectedDataset);
  const datasetSeries = aggregateDatasetPnlSeries(selectedDataset ?? null);
  const productSeries = selectedProduct?.pnlSeries ?? [];
  const chartPoints = [...datasetSeries, ...productSeries];
  const minTimestamp = chartPoints.length ? Math.min(...chartPoints.map((point) => point.timestamp)) : 0;
  const maxTimestamp = chartPoints.length ? Math.max(...chartPoints.map((point) => point.timestamp)) : 1;
  const minValue = chartPoints.length ? Math.min(...chartPoints.map((point) => point.value)) : 0;
  const maxValue = chartPoints.length ? Math.max(...chartPoints.map((point) => point.value)) : 1;
  const datasetPath = datasetSeries.length
    ? buildPath(datasetSeries, minTimestamp, maxTimestamp, minValue, maxValue)
    : null;
  const productPath = productSeries.length
    ? buildPath(productSeries, minTimestamp, maxTimestamp, minValue, maxValue)
    : null;

    return (
    <Panel title="PnL & Risk">
      <div className="metric-grid metric-grid--four">
        <div className="metric-card">
          <span className="inspection-label">Selected Product</span>
          <strong>{summary.latest ? summary.latest.value.toFixed(2) : "n/a"}</strong>
        </div>
        <div className="metric-card">
          <span className="inspection-label">Dataset Total</span>
          <strong>{summary.datasetLatest ? summary.datasetLatest.value.toFixed(2) : "n/a"}</strong>
        </div>
        <div className="metric-card">
          <span className="inspection-label">Selected Sharpe-like</span>
          <strong>{summary.productPerformance.sharpeLike?.toFixed(2) ?? "n/a"}</strong>
        </div>
        <div className="metric-card">
          <span className="inspection-label">Selected Max DD</span>
          <strong>{summary.productPerformance.maxDrawdown?.toFixed(2) ?? "n/a"}</strong>
        </div>
      </div>

      <div className="pnl-preview">
        <div className="pnl-preview__legend">
          <span className="pnl-preview__key pnl-preview__key--dataset">Dataset total</span>
          <span className="pnl-preview__key pnl-preview__key--product">Selected product</span>
        </div>
        <svg viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} className="pnl-preview__chart" role="img" aria-label="PnL preview">
          <rect x="0" y="0" width={CHART_WIDTH} height={CHART_HEIGHT} rx="12" fill="#0d131a" />
          <line
            x1={CHART_PADDING.left}
            y1={CHART_HEIGHT - CHART_PADDING.bottom}
            x2={CHART_WIDTH - CHART_PADDING.right}
            y2={CHART_HEIGHT - CHART_PADDING.bottom}
            className="chart-grid"
          />
          {datasetPath ? <path d={datasetPath} fill="none" stroke="#58a6ff" strokeWidth="2.4" /> : null}
          {productPath ? <path d={productPath} fill="none" stroke="#f4c95d" strokeWidth="2.2" /> : null}
        </svg>
      </div>

      <div className="metric-copy">
        <p>
          {summary.hovered
            ? `Hovered PnL ${formatSignedValue(summary.hovered.value)} at ${formatTimestamp(summary.hovered.timestamp)}.`
            : "Hover the chart to inspect PnL at a specific moment."}
        </p>
        <p>
          Contribution share: {formatPercent(summary.contributionShare)}. Positive step rate:{" "}
          {formatPercent(summary.productPerformance.positiveStepRate)}.
        </p>
        <p>
          Dataset Sharpe-like: {summary.datasetPerformance.sharpeLike?.toFixed(2) ?? "n/a"}. Dataset max drawdown:{" "}
          {summary.datasetPerformance.maxDrawdown?.toFixed(2) ?? "n/a"}. Sortino-like:{" "}
          {summary.productPerformance.sortinoLike?.toFixed(2) ?? "n/a"}.
        </p>
      </div>
    </Panel>
  );
}
