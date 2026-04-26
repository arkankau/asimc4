import { Panel } from "./Panel";
import { useDashboard } from "../../state/DashboardProvider";
import { formatPrice, formatQuantity, formatTimestamp } from "../../utils/formatters";

function renderTradeSummaryLabel(kind: string) {
  if (kind === "ownTrade") {
    return "Own";
  }

  if (kind === "trade") {
    return "Market";
  }

  return "Event";
}

export function InspectionPanel() {
  const { inspection } = useDashboard();
  const spread =
    inspection.nearestVisibleBid && inspection.nearestVisibleAsk
      ? inspection.nearestVisibleAsk.price - inspection.nearestVisibleBid.price
      : null;
  const hoveredTrades = [
    ...inspection.visibleOwnTradesAtHoveredTimestamp,
    ...inspection.visibleTradesAtHoveredTimestamp,
  ];

  return (
    <Panel title="Inspection">
      <div className="inspection-grid">
        <div>
          <span className="inspection-label">Hovered Event</span>
          <strong>{inspection.hoveredEvent?.label ?? "No hover"}</strong>
        </div>
        <div>
          <span className="inspection-label">Timestamp</span>
          <strong>{formatTimestamp(inspection.hoveredTimestamp)}</strong>
        </div>
        <div>
          <span className="inspection-label">Hovered Price</span>
          <strong>{formatPrice(inspection.hoveredPrice)}</strong>
        </div>
        <div>
          <span className="inspection-label">Hovered Quantity</span>
          <strong>{formatQuantity(inspection.hoveredQuantity)}</strong>
        </div>
        <div>
          <span className="inspection-label">Nearest Bid</span>
          <strong>
            {formatPrice(inspection.nearestVisibleBid?.price ?? null)} x{" "}
            {formatQuantity(inspection.nearestVisibleBid?.quantity ?? null)}
          </strong>
        </div>
        <div>
          <span className="inspection-label">Nearest Ask</span>
          <strong>
            {formatPrice(inspection.nearestVisibleAsk?.price ?? null)} x{" "}
            {formatQuantity(inspection.nearestVisibleAsk?.quantity ?? null)}
          </strong>
        </div>
        <div>
          <span className="inspection-label">Nearest Trade</span>
          <strong>
            {formatPrice(inspection.nearestVisibleTrade?.price ?? null)} x{" "}
            {formatQuantity(inspection.nearestVisibleTrade?.quantity ?? null)}
          </strong>
        </div>
        <div>
          <span className="inspection-label">Nearest Own Trade</span>
          <strong>
            {formatPrice(inspection.nearestVisibleOwnTrade?.price ?? null)} x{" "}
            {formatQuantity(inspection.nearestVisibleOwnTrade?.quantity ?? null)}
          </strong>
        </div>
        <div>
          <span className="inspection-label">Spread</span>
          <strong>{formatPrice(spread)}</strong>
        </div>
        <div>
          <span className="inspection-label">Active Filters</span>
          <strong>{inspection.activeFilterSummary.length ? inspection.activeFilterSummary.join(" | ") : "None"}</strong>
        </div>
      </div>
      <div className="inspection-trades">
        <div className="inspection-trades__header">
          <span className="inspection-label">Trades At Hovered Timestamp</span>
          <strong>{hoveredTrades.length}</strong>
        </div>
        {hoveredTrades.length === 0 ? (
          <p className="inspection-trades__empty">No visible trades at this timestamp.</p>
        ) : (
          <div className="inspection-trades__list">
            {hoveredTrades.map((trade) => (
              <div className="inspection-trades__row" key={`${trade.id}-${trade.kind}`}>
                <div className="inspection-trades__meta">
                  <strong>{renderTradeSummaryLabel(trade.kind)}</strong>
                  <span>{trade.side?.toUpperCase() ?? "TRADE"}</span>
                  {trade.traderClass ? <span>{trade.traderClass}</span> : null}
                </div>
                <div className="inspection-trades__stats">
                  <span>{formatPrice(trade.price)}</span>
                  <span>x {formatQuantity(trade.quantity)}</span>
                </div>
                <div className="inspection-trades__participants">
                  <span>B: {trade.buyer ?? "-"}</span>
                  <span>S: {trade.seller ?? "-"}</span>
                  {trade.traderId ? <span>T: {trade.traderId}</span> : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Panel>
  );
}
