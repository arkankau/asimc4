import { Panel } from "./Panel";
import { useDashboard } from "../../state/DashboardProvider";
import { formatTimestamp } from "../../utils/formatters";

function nearestPoint(
  points: { timestamp: number; value: number }[],
  timestamp: number | null,
) {
  if (timestamp === null || points.length === 0) {
    return null;
  }

  return points.reduce<{ timestamp: number; value: number } | null>((closest, point) => {
    if (!closest) {
      return point;
    }

    return Math.abs(point.timestamp - timestamp) < Math.abs(closest.timestamp - timestamp) ? point : closest;
  }, null);
}

export function PnlPanel() {
  const { selectedProduct, inspection } = useDashboard();
  const pnlSeries = selectedProduct?.indicators.find((series) => series.id === "tutorial-pnl");
  const latest = pnlSeries && pnlSeries.points.length > 0 ? pnlSeries.points[pnlSeries.points.length - 1] : null;
  const hovered = nearestPoint(pnlSeries?.points ?? [], inspection.timestamp);

  return (
    <Panel title="PnL">
      <div className="placeholder-panel">
        <strong>{latest ? latest.value.toFixed(2) : "n/a"}</strong>
        <p>Tutorial price snapshots expose a per-product `profit_and_loss` series, so this panel is already data-backed.</p>
        <p>
          {hovered
            ? `Hovered PnL ${hovered.value.toFixed(2)} at ${formatTimestamp(hovered.timestamp)}.`
            : "Hover the chart to inspect the nearest PnL sample."}
        </p>
      </div>
    </Panel>
  );
}
