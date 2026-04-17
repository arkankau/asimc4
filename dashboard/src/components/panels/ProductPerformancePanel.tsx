import { Panel } from "./Panel";
import { useDashboard } from "../../state/DashboardProvider";
import { deriveProductPerformanceRows } from "../../utils/marketSelectors";
import { formatPercent, formatSignedValue } from "../../utils/formatters";

export function ProductPerformancePanel() {
  const { selectedDataset, selectedProduct, dispatch } = useDashboard();
  const rows = deriveProductPerformanceRows(selectedDataset);

  return (
    <Panel title="Product Breakdown">
      {rows.length === 0 ? (
        <div className="metric-copy">
          <p>No per-product performance data is available for this dataset.</p>
        </div>
      ) : (
        <div className="perf-table">
          <div className="perf-table__header">
            <span>Product</span>
            <span>PnL</span>
            <span>Share</span>
            <span>Sharpe</span>
            <span>Max DD</span>
            <span>Own Trades</span>
          </div>
          {rows.map((row) => (
            <button
              type="button"
              key={row.productId}
              className={`perf-table__row ${selectedProduct?.product.id === row.productId ? "perf-table__row--active" : ""}`.trim()}
              onClick={() => dispatch({ type: "setProduct", productId: row.productId })}
            >
              <strong>{row.displayName}</strong>
              <span>{formatSignedValue(row.finalPnl)}</span>
              <span>{formatPercent(row.contributionShare)}</span>
              <span>{row.sharpeLike?.toFixed(2) ?? "n/a"}</span>
              <span>{row.maxDrawdown?.toFixed(2) ?? "n/a"}</span>
              <span>{row.ownTradeCount}</span>
            </button>
          ))}
        </div>
      )}
    </Panel>
  );
}
