import { Panel } from "./Panel";
import { useDashboard } from "../../state/DashboardProvider";
import { derivePositionSummary } from "../../utils/marketSelectors";
import { formatQuantity, formatTimestamp } from "../../utils/formatters";

export function PositionPanel() {
  const { selectedProduct, inspection } = useDashboard();
  const summary = derivePositionSummary(selectedProduct, inspection);

  return (
    <Panel title="Position">
      <div className="metric-grid">
        <div className="metric-card">
          <span className="inspection-label">Current Position</span>
          <strong>{summary.latest ? summary.latest.value.toFixed(0) : "n/a"}</strong>
        </div>
        <div className="metric-card">
          <span className="inspection-label">Max Abs Position</span>
          <strong>{formatQuantity(summary.maxAbsPosition)}</strong>
        </div>
        <div className="metric-card">
          <span className="inspection-label">Own Buys / Sells</span>
          <strong>
            {summary.buyCount} / {summary.sellCount}
          </strong>
        </div>
        <div className="metric-card">
          <span className="inspection-label">Own Trade Count</span>
          <strong>{summary.ownTradeCount}</strong>
        </div>
      </div>

      <div className="metric-copy">
        <p>
          {summary.hovered
            ? `Hovered position ${summary.hovered.value.toFixed(0)} at ${formatTimestamp(summary.hovered.timestamp)}.`
            : "Position updates track your own fills across the selected product."}
        </p>
      </div>
    </Panel>
  );
}
