import { useMemo, type ChangeEvent } from "react";
import { Panel } from "../panels/Panel";
import { useDashboard } from "../../state/DashboardProvider";

export function ControlPanel() {
  const { state, dispatch, datasets, availableProducts, tradeFilterSupport, importDataset } = useDashboard();
  const depthLevels = useMemo(() => [1, 2, 3], []);

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

      <Panel title="Book Visibility">
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
        <label className="toggle">
          <input
            type="checkbox"
            checked={state.visibility.ownTrades}
            onChange={() => dispatch({ type: "toggleVisibility", key: "ownTrades" })}
          />
          <span>Show own trades</span>
        </label>
        <div className="field">
          <span>Depth Levels</span>
          <div className="inline-toggles">
            {depthLevels.map((level) => {
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

      <Panel title="Trade Filters">
        <label className="field">
          <span>Trade Type</span>
          <select
            value={state.filters.tradeType}
            onChange={(event) =>
              dispatch({
                type: "setTradeTypeFilter",
                tradeType: event.target.value as "all" | "maker" | "taker" | "own",
              })
            }
          >
            <option value="all">All trades</option>
            <option value="maker">Maker only</option>
            <option value="taker">Taker only</option>
            <option value="own">Own trades only</option>
          </select>
        </label>

        <label className="field">
          <span>Trader Group</span>
          <select
            value={state.filters.traderGroup ?? ""}
            disabled={!tradeFilterSupport.supportsTraderGroups}
            onChange={(event) =>
              dispatch({
                type: "setTraderGroupFilter",
                traderGroup: event.target.value || null,
              })
            }
          >
            <option value="">
              {tradeFilterSupport.supportsTraderGroups ? "All groups" : "Not available in this dataset"}
            </option>
            {tradeFilterSupport.availableTraderGroups.map((group) => (
              <option key={group} value={group}>
                {group}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Trader ID</span>
          <select
            value={state.filters.traderId ?? ""}
            disabled={!tradeFilterSupport.supportsTraderIds}
            onChange={(event) =>
              dispatch({
                type: "setTraderIdFilter",
                traderId: event.target.value || null,
              })
            }
          >
            <option value="">
              {tradeFilterSupport.supportsTraderIds ? "All traders" : "Not available in this dataset"}
            </option>
            {tradeFilterSupport.availableTraderIds.map((traderId) => (
              <option key={traderId} value={traderId}>
                {traderId}
              </option>
            ))}
          </select>
        </label>

        <div className="field">
          <span>Quantity Range</span>
          <div className="range-grid">
            <input
              type="number"
              placeholder={tradeFilterSupport.minTradeQuantity?.toString() ?? "Min"}
              value={state.filters.quantityRange?.[0] ?? ""}
              onChange={(event) => {
                const nextMin = event.target.value === "" ? null : Number(event.target.value);
                dispatch({
                  type: "setQuantityRange",
                  quantityRange: [nextMin, state.filters.quantityRange?.[1] ?? null],
                });
              }}
            />
            <input
              type="number"
              placeholder={tradeFilterSupport.maxTradeQuantity?.toString() ?? "Max"}
              value={state.filters.quantityRange?.[1] ?? ""}
              onChange={(event) => {
                const nextMax = event.target.value === "" ? null : Number(event.target.value);
                dispatch({
                  type: "setQuantityRange",
                  quantityRange: [state.filters.quantityRange?.[0] ?? null, nextMax],
                });
              }}
            />
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

        <div className="future-filter-copy">Reserved for overlays, log syncing, normalization, and advanced performance controls.</div>
      </Panel>
    </div>
  );
}
