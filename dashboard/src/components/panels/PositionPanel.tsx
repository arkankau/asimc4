import { Panel } from "./Panel";
import { useDashboard } from "../../state/DashboardProvider";
import { derivePositionSummary } from "../../utils/marketSelectors";
import { formatTimestamp } from "../../utils/formatters";

export function PositionPanel() {
  const { selectedProduct, inspection } = useDashboard();
  const summary = derivePositionSummary(selectedProduct, inspection);

  return (
    <Panel title="Position">
      <div className="placeholder-panel">
        <strong>{summary.latest ? summary.latest.value.toFixed(0) : "n/a"}</strong>
        <p>This placeholder is already reading normalized position points, ready for richer inventory analysis later.</p>
        <p>
          {summary.hovered
            ? `Hovered position ${summary.hovered.value.toFixed(0)} at ${formatTimestamp(summary.hovered.timestamp)}.`
            : "Hover the chart to sync this panel to a market moment."}
        </p>
      </div>
    </Panel>
  );
}
