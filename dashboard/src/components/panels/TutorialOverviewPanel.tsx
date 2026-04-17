import { Panel } from "./Panel";
import { useDashboard } from "../../state/DashboardProvider";

export function TutorialOverviewPanel() {
  const { selectedDataset, selectedProduct } = useDashboard();

  return (
    <Panel title="Dataset Overview">
      <div className="inspection-grid">
        <div>
          <span className="inspection-label">Round / Day</span>
          <strong>
            {selectedDataset?.metadata?.round ?? "n/a"} / {selectedDataset?.metadata?.day ?? "n/a"}
          </strong>
        </div>
        <div>
          <span className="inspection-label">Source</span>
          <strong>{selectedDataset?.source ?? "n/a"}</strong>
        </div>
        <div>
          <span className="inspection-label">Products</span>
          <strong>{selectedDataset?.products.length ?? 0}</strong>
        </div>
        <div>
          <span className="inspection-label">Snapshots</span>
          <strong>{selectedDataset?.metadata?.snapshotCount ?? 0}</strong>
        </div>
        <div>
          <span className="inspection-label">Trades</span>
          <strong>{selectedDataset?.metadata?.tradeCount ?? 0}</strong>
        </div>
        <div>
          <span className="inspection-label">Own Trades</span>
          <strong>{selectedDataset?.metadata?.ownTradeCount ?? 0}</strong>
        </div>
        <div>
          <span className="inspection-label">Submission ID</span>
          <strong>{selectedDataset?.metadata?.submissionId ?? "n/a"}</strong>
        </div>
        <div>
          <span className="inspection-label">Reported Profit</span>
          <strong>
            {selectedDataset?.metadata?.reportedProfit !== undefined
              ? selectedDataset.metadata.reportedProfit.toFixed(2)
              : "n/a"}
          </strong>
        </div>
        <div>
          <span className="inspection-label">Status / Logs</span>
          <strong>
            {selectedDataset?.metadata?.resultStatus ?? "n/a"} / {selectedDataset?.metadata?.logCount ?? 0}
          </strong>
        </div>
        <div>
          <span className="inspection-label">Selected Product</span>
          <strong>{selectedProduct?.product.displayName ?? "n/a"}</strong>
        </div>
      </div>
    </Panel>
  );
}
