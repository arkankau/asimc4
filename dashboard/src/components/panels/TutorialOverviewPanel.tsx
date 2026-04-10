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
          <span className="inspection-label">Products</span>
          <strong>{selectedDataset?.products.length ?? 0}</strong>
        </div>
        <div>
          <span className="inspection-label">Book Snapshots</span>
          <strong>{selectedDataset?.metadata?.rowCount ?? 0}</strong>
        </div>
        <div>
          <span className="inspection-label">Trades</span>
          <strong>{selectedDataset?.metadata?.tradeCount ?? 0}</strong>
        </div>
        <div>
          <span className="inspection-label">Selected Product</span>
          <strong>{selectedProduct?.product.displayName ?? "n/a"}</strong>
        </div>
      </div>
    </Panel>
  );
}
