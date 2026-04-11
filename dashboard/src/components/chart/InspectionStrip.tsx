import { useDashboard } from "../../state/DashboardProvider";
import { formatPrice, formatQuantity, formatTimestamp } from "../../utils/formatters";

export function InspectionStrip() {
  const { inspection } = useDashboard();

  return (
    <div className="inspection-strip">
      <span>{inspection.hoveredEvent ? inspection.hoveredEvent.label : "No event selected"}</span>
      <span>{formatTimestamp(inspection.hoveredTimestamp)}</span>
      <span>Price {formatPrice(inspection.hoveredPrice)}</span>
      <span>Qty {formatQuantity(inspection.hoveredQuantity)}</span>
      <span>Bid {formatPrice(inspection.nearestVisibleBid?.price ?? null)}</span>
      <span>Ask {formatPrice(inspection.nearestVisibleAsk?.price ?? null)}</span>
      <span>Trade {formatPrice(inspection.nearestVisibleTrade?.price ?? null)}</span>
      {inspection.activeFilterSummary.length > 0 ? (
        <span className="inspection-strip__filters">{inspection.activeFilterSummary.join(" | ")}</span>
      ) : null}
    </div>
  );
}
