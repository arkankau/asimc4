import { Panel } from "./Panel";

interface PlaceholderMetricPanelProps {
  title: string;
  summary: string;
  note: string;
}

export function PlaceholderMetricPanel({ title, summary, note }: PlaceholderMetricPanelProps) {
  return (
    <Panel title={title}>
      <div className="placeholder-panel">
        <strong>{summary}</strong>
        <p>{note}</p>
      </div>
    </Panel>
  );
}
