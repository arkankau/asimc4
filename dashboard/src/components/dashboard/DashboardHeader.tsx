import { useDashboard } from "../../state/DashboardProvider";

export function DashboardHeader() {
  const { selectedDataset, selectedProduct } = useDashboard();

  return (
    <div className="dashboard-header">
      <div>
        <span className="eyebrow">IMC Prosperity</span>
        <h1>Trading Analysis Dashboard</h1>
      </div>
      <div className="dashboard-header__meta">
        <div>
          <span className="eyebrow">Dataset</span>
          <strong>{selectedDataset?.name ?? "Loading..."}</strong>
        </div>
        <div>
          <span className="eyebrow">Round / Day</span>
          <strong>
            {selectedDataset?.metadata?.round ?? "-"} / {selectedDataset?.metadata?.day ?? "-"}
          </strong>
        </div>
        <div>
          <span className="eyebrow">Product</span>
          <strong>{selectedProduct?.product.displayName ?? "Select a product"}</strong>
        </div>
      </div>
    </div>
  );
}
