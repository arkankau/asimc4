import { Panel } from "./Panel";
import { useDashboard } from "../../state/DashboardProvider";
import { derivePnlSummary } from "../../utils/marketSelectors";
import { formatTimestamp } from "../../utils/formatters";

export function PnlPanel() {
  const { selectedProduct, inspection } = useDashboard();
  const summary = derivePnlSummary(selectedProduct, inspection);

  return (
    <Panel title="PnL">
      <div className="placeholder-panel">
        <strong>{summary.latest ? summary.latest.value.toFixed(2) : "n/a"}</strong>
        <p>Placeholder analytics panel already consuming normalized PnL series from the domain layer.</p>
        <p>
          {summary.hovered
            ? `Hovered PnL ${summary.hovered.value.toFixed(2)} at ${formatTimestamp(summary.hovered.timestamp)}.`
            : "Hover the chart to sync this panel to a market moment."}
        </p>
      </div>
    </Panel>
  );
}
