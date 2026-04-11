import { Panel } from "./Panel";
import { useDashboard } from "../../state/DashboardProvider";
import { formatTimestamp } from "../../utils/formatters";

export function LogsPanel() {
  const { inspection, selectedProduct, selectedDataset } = useDashboard();
  const visibleLogs = (selectedProduct?.logs ?? []).slice(0, 4);

  const messages = [
    selectedDataset?.metadata?.day !== undefined
      ? `Loaded tutorial round ${selectedDataset.metadata.round} day ${selectedDataset.metadata.day}.`
      : `Loaded dataset ${selectedDataset?.name ?? "n/a"}.`,
    inspection.hoveredTimestamp !== null
      ? `Hover synced at ${formatTimestamp(inspection.hoveredTimestamp)} for ${selectedProduct?.product.displayName ?? "n/a"}.`
      : "Hover a chart point to drive cross-panel inspection state.",
    ...visibleLogs.map((entry) => `${formatTimestamp(entry.timestamp)} ${entry.message}`),
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
