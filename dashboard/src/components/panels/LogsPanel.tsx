import { Panel } from "./Panel";
import { useDashboard } from "../../state/DashboardProvider";
import { formatTimestamp } from "../../utils/formatters";

export function LogsPanel() {
  const { inspection, selectedProduct, selectedDataset } = useDashboard();

  const messages = [
    selectedDataset?.metadata?.day !== undefined
      ? `Loaded tutorial round ${selectedDataset.metadata.round} day ${selectedDataset.metadata.day}.`
      : `Loaded dataset ${selectedDataset?.name ?? "n/a"}.`,
    inspection.timestamp !== null
      ? `Hover synced at ${formatTimestamp(inspection.timestamp)} for ${selectedProduct?.product.displayName ?? "n/a"}`
      : "Hover a chart point to drive cross-panel inspection state.",
    "Future log entries can filter to the closest timestamp without changing the chart implementation.",
    selectedDataset?.metadata?.priceSource
      ? `Price source ${selectedDataset.metadata.priceSource} with ${selectedDataset.metadata.rowCount ?? 0} snapshots.`
      : "This panel is intentionally simple but already wired to shared dashboard state.",
  ];

  return (
    <Panel title="Logs">
      <ul className="log-list">
        {messages.map((message) => (
          <li key={message}>{message}</li>
        ))}
      </ul>
    </Panel>
  );
}
