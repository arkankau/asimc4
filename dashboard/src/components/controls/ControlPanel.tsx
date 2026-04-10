import { useMemo, type ChangeEvent } from "react";
import { Panel } from "../panels/Panel";
import { useDashboard } from "../../state/DashboardProvider";
import { listUniqueTraders } from "../../utils/marketSelectors";

export function ControlPanel() {
  const { state, dispatch, datasets, availableProducts, selectedProduct, importDataset } = useDashboard();

  const traders = useMemo(() => listUniqueTraders(selectedProduct?.trades ?? []), [selectedProduct]);

  const handleFileImport = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    await importDataset(file);
    event.target.value = "";
  };

  return (
    <div className="stack">
      <Panel title="Data Source">
        <label className="field">
          <span>Dataset</span>
          <select
            value={state.selectedDatasetId ?? ""}
            onChange={(event) => dispatch({ type: "setDataset", datasetId: event.target.value })}
          >
            {datasets.map((dataset) => (
              <option key={dataset.id} value={dataset.id}>
                {dataset.name}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Upload JSON/CSV</span>
          <input type="file" accept=".json,.csv" onChange={handleFileImport} />
        </label>
      </Panel>

      <Panel title="Market Focus">
        <label className="field">
          <span>Product</span>
          <select
            value={state.selectedProductId ?? ""}
            onChange={(event) => dispatch({ type: "setProduct", productId: event.target.value })}
          >
            {availableProducts.map((product) => (
              <option key={product.id} value={product.id}>
                {product.displayName}
              </option>
            ))}
          </select>
        </label>
      </Panel>

      <Panel title="Visibility">
        <label className="toggle">
          <input
            type="checkbox"
            checked={state.visibility.bids}
            onChange={() => dispatch({ type: "toggleVisibility", key: "bids" })}
          />
          <span>Show bids</span>
        </label>
        <label className="toggle">
          <input
            type="checkbox"
            checked={state.visibility.asks}
            onChange={() => dispatch({ type: "toggleVisibility", key: "asks" })}
          />
          <span>Show asks</span>
        </label>
        <label className="toggle">
          <input
            type="checkbox"
            checked={state.visibility.trades}
            onChange={() => dispatch({ type: "toggleVisibility", key: "trades" })}
          />
          <span>Show trades</span>
        </label>
        <div className="field">
          <span>Depth Levels</span>
          <div className="inline-toggles">
            {[1, 2, 3].map((level) => {
              const checked = state.overlays.depthLevels.includes(level);
              const nextLevels = checked
                ? state.overlays.depthLevels.filter((entry) => entry !== level)
                : [...state.overlays.depthLevels, level].sort((left, right) => left - right);

              return (
                <label className="toggle" key={level}>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() =>
                      dispatch({
                        type: "setDepthLevels",
                        levels: nextLevels.length ? nextLevels : [level],
                      })
                    }
                  />
                  <span>L{level}</span>
                </label>
              );
            })}
          </div>
        </div>
      </Panel>

      <Panel title="Future Filters">
        <label className="field">
          <span>Downsampling</span>
          <select
            value={state.overlays.downsamplingMode}
            onChange={(event) =>
              dispatch({
                type: "setDownsamplingMode",
                mode: event.target.value as "none" | "auto",
              })
            }
          >
            <option value="none">None</option>
            <option value="auto">Auto</option>
          </select>
        </label>

        <label className="field">
          <span>Normalization</span>
          <select
            value={state.overlays.normalizationMode}
            onChange={(event) =>
              dispatch({
                type: "setNormalizationMode",
                mode: event.target.value as "raw" | "indicator",
              })
            }
          >
            <option value="raw">Raw</option>
            <option value="indicator">Indicator-relative</option>
          </select>
        </label>

        <label className="field">
          <span>Trader Filter</span>
          <select
            value={state.filters.traderIds[0] ?? ""}
            onChange={(event) =>
              dispatch({
                type: "setTraderFilters",
                traderIds: event.target.value ? [event.target.value] : [],
              })
            }
          >
            <option value="">All traders</option>
            {traders.map((trader) => (
              <option key={trader} value={trader}>
                {trader}
              </option>
            ))}
          </select>
        </label>
      </Panel>
    </div>
  );
}
