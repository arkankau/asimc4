import { Panel } from "./Panel";
import { useDashboard } from "../../state/DashboardProvider";
import { formatPrice, formatQuantity, formatTimestamp } from "../../utils/formatters";

export function InspectionPanel() {
  const { inspection } = useDashboard();
  const spread =
    inspection.nearestBid && inspection.nearestAsk ? inspection.nearestAsk.price - inspection.nearestBid.price : null;

  return (
    <Panel title="Inspection">
      <div className="inspection-grid">
        <div>
          <span className="inspection-label">Timestamp</span>
          <strong>{formatTimestamp(inspection.timestamp)}</strong>
        </div>
        <div>
          <span className="inspection-label">Nearest Bid</span>
          <strong>
            {formatPrice(inspection.nearestBid?.price ?? null)} x {formatQuantity(inspection.nearestBid?.quantity ?? null)}
          </strong>
        </div>
        <div>
          <span className="inspection-label">Nearest Ask</span>
          <strong>
            {formatPrice(inspection.nearestAsk?.price ?? null)} x {formatQuantity(inspection.nearestAsk?.quantity ?? null)}
          </strong>
        </div>
        <div>
          <span className="inspection-label">Nearest Trade</span>
          <strong>
            {formatPrice(inspection.nearestTrade?.price ?? null)} x {formatQuantity(inspection.nearestTrade?.quantity ?? null)}
          </strong>
        </div>
        <div>
          <span className="inspection-label">Spread</span>
          <strong>{formatPrice(spread)}</strong>
        </div>
      </div>
    </Panel>
  );
}
