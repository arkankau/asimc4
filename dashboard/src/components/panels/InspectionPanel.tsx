import { Panel } from "./Panel";
import { useDashboard } from "../../state/DashboardProvider";
import { formatPrice, formatQuantity, formatTimestamp } from "../../utils/formatters";

export function InspectionPanel() {
  const { inspection } = useDashboard();
  const spread =
    inspection.nearestVisibleBid && inspection.nearestVisibleAsk
      ? inspection.nearestVisibleAsk.price - inspection.nearestVisibleBid.price
      : null;

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
    </Panel>
  );
}
