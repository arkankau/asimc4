import { Panel } from "./Panel";
import { useDashboard } from "../../state/DashboardProvider";
import { deriveTradeTape } from "../../utils/marketSelectors";
import { formatPrice, formatQuantity, formatTimestamp } from "../../utils/formatters";

export function TradeTapePanel() {
  const { selectedProduct, inspection } = useDashboard();
  const { rows, highlightedTradeId } = deriveTradeTape(selectedProduct, inspection);

  return (
    <Panel
      title="Trade Tape"
      actions={
        <span className="chart-card__stat">
          {selectedProduct?.product.displayName ?? "No product"}
        </span>
      }
    >
      {rows.length === 0 ? (
        <div className="metric-copy">
          <p>No trade history is available for this product in the current dataset.</p>
        </div>
      ) : (
        <div className="trade-tape">
          {rows.map((row) => (
            <div
              className={`trade-tape__row ${row.id === highlightedTradeId ? "trade-tape__row--highlighted" : ""}`.trim()}
              key={row.id}
            >
              <div className="trade-tape__meta">
                <strong>{formatTimestamp(row.timestamp)}</strong>
                <span className={`trade-chip trade-chip--${row.kind}`}>{row.kind === "own" ? "OWN" : "MKT"}</span>
                <span className={`trade-chip trade-chip--${row.side}`}>{row.side.toUpperCase()}</span>
              </div>
              <div className="trade-tape__stats">
                <span>{formatPrice(row.price)}</span>
                <span>x {formatQuantity(row.quantity)}</span>
                <span>{row.tradeType}</span>
              </div>
              <div className="trade-tape__participants">
                <span>B: {row.buyer || "-"}</span>
                <span>S: {row.seller || "-"}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}
