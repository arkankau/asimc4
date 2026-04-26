import { useMemo, useState, type ChangeEvent } from "react";
import { Panel } from "../panels/Panel";
import { useDashboard } from "../../state/DashboardProvider";
import { TRADER_CLASS_ORDER } from "../../utils/marketSelectors";
import type { TraderClass } from "../../types/market";

const TRADER_CLASS_OPTIONS: Array<{ id: TraderClass; label: string; description: string }> = [
  { id: "M", label: "Maker", description: "Passive or maker flow" },
  { id: "S", label: "Small Taker", description: "Smaller aggressive trades" },
  { id: "B", label: "Big Taker", description: "Larger aggressive trades" },
  { id: "I", label: "Informed", description: "Aggressive trades followed by directional price response" },
  { id: "F", label: "Our Trades", description: "Submission / internal fills" },
];

function toggleSelection<T>(values: T[], value: T) {
  return values.includes(value) ? values.filter((entry) => entry !== value) : [...values, value];
}

export function ControlPanel() {
  const { state, dispatch, datasets, selectedDataset, selectedProduct, availableProducts, tradeFilterSupport, importDataset } =
    useDashboard();
  const depthLevels = useMemo(() => [1, 2, 3], []);
  const isSubmissionMode = selectedDataset?.source === "submission";
  const [importError, setImportError] = useState<string | null>(null);
  const availableIndicators = useMemo(
    () => (selectedProduct?.indicators ?? []).filter((series) => series.id !== "mid-price"),
    [selectedProduct],
  );
  const hasBookData = (selectedProduct?.bookSnapshots.length ?? 0) > 0;

  const handleFileImport = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setImportError(null);
    try {
      await importDataset(file);
    } catch (error) {
      setImportError(error instanceof Error ? error.message : "Failed to import file.");
    } finally {
      event.target.value = "";
    }
  };

  const resetTradeFilters = () => {
    dispatch({ type: "setSelectedTraderClasses", traderClasses: [...TRADER_CLASS_ORDER] });
    dispatch({ type: "setSelectedTraderGroups", traderGroups: [] });
    dispatch({ type: "setSelectedTraderIds", traderIds: [] });
    dispatch({ type: "setQuantityRange", quantityRange: null });
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
          <span>Upload JSON/CSV/LOG</span>
          <input type="file" accept=".json,.csv,.log" onChange={handleFileImport} />
          {importError ? (
            <div className="field__helper" style={{ color: "#f87171" }}>
              Upload failed: {importError}
            </div>
          ) : null}
        </label>
      </Panel>

      <Panel title="Review Focus">
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
        <div className="field__helper">
          The main chart now centers on market behavior for the selected product. PnL stays below as a secondary review panel.
        </div>
      </Panel>

      {hasBookData ? (
        <Panel title="Order Book">
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
      ) : null}

      <Panel
        title="Trade Visibility"
        actions={
          <button className="chart-card__button" type="button" onClick={resetTradeFilters}>
            Reset
          </button>
        }
      >
        <label className="toggle">
          <input
            type="checkbox"
            checked={state.visibility.trades}
            onChange={() => dispatch({ type: "toggleVisibility", key: "trades" })}
          />
          <span>Show market trades</span>
        </label>
        <label className="toggle">
          <input
            type="checkbox"
            checked={state.visibility.ownTrades}
            onChange={() => dispatch({ type: "toggleVisibility", key: "ownTrades" })}
          />
          <span>Show our trades</span>
        </label>

        <div className="field">
          <span>Trader Classes</span>
          <div className="filter-chip-grid">
            {TRADER_CLASS_OPTIONS.map((option) => {
              const tradeCount = tradeFilterSupport.traderClassCounts[option.id] ?? 0;
              const isEmpty = tradeCount === 0;
              const isActive = state.filters.selectedTraderClasses.includes(option.id);

              return (
                <button
                  className={`filter-chip-button filter-chip-button--class-${option.id} ${
                    isActive ? "filter-chip-button--active" : ""
                  } ${isEmpty ? "filter-chip-button--empty" : ""}`.trim()}
                  key={option.id}
                  type="button"
                  title={
                    isEmpty
                      ? `${option.label}: no trades in this dataset matched this class.`
                      : option.description
                  }
                  onClick={() =>
                    dispatch({
                      type: "setSelectedTraderClasses",
                      traderClasses: toggleSelection(state.filters.selectedTraderClasses, option.id),
                    })
                  }
                >
                  <span>{option.id}</span>
                  <strong>{option.label}</strong>
                  <small>{tradeCount}</small>
                </button>
              );
            })}
          </div>
          <div className="field__helper">
            {tradeFilterSupport.bigTradeThreshold !== null
              ? `Big taker cutoff is ${tradeFilterSupport.bigTradeThreshold}.`
              : "No taker trades were available to compute a big-trade cutoff."}
            {" "}
            {tradeFilterSupport.usesInferredTraderClasses
              ? "When named trader tags are missing, S/B/I are inferred from trade size and the next price response."
              : "Trader classes are coming directly from the dataset tags."}
          </div>
        </div>

        <div className="field">
          <span>Specific Trader Groups</span>
          {tradeFilterSupport.supportsTraderGroups ? (
            <div className="filter-chip-grid">
              {tradeFilterSupport.availableTraderGroups.map((group) => {
                const isActive = state.filters.selectedTraderGroups.includes(group);
                return (
                  <button
                    className={`filter-chip-button ${isActive ? "filter-chip-button--active" : ""}`.trim()}
                    key={group}
                    type="button"
                    onClick={() =>
                      dispatch({
                        type: "setSelectedTraderGroups",
                        traderGroups: toggleSelection(state.filters.selectedTraderGroups, group),
                      })
                    }
                  >
                    <strong>{group}</strong>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="field__helper">No named trader groups were provided in this dataset.</div>
          )}
        </div>

        <div className="field">
          <span>Specific Traders</span>
          {tradeFilterSupport.supportsTraderIds ? (
            <div className="filter-chip-grid">
              {tradeFilterSupport.availableTraderIds.map((traderId) => {
                const isActive = state.filters.selectedTraderIds.includes(traderId);
                return (
                  <button
                    className={`filter-chip-button ${isActive ? "filter-chip-button--active" : ""}`.trim()}
                    key={traderId}
                    type="button"
                    onClick={() =>
                      dispatch({
                        type: "setSelectedTraderIds",
                        traderIds: toggleSelection(state.filters.selectedTraderIds, traderId),
                      })
                    }
                  >
                    <strong>{traderId}</strong>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="field__helper">
              No explicit trader IDs were provided. Use class toggles or quantity filters instead.
            </div>
          )}
        </div>

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

      {availableIndicators.length > 0 ? (
        <Panel title="Indicator Overlays">
          <div className="filter-chip-grid">
            {availableIndicators.map((series) => {
              const isActive = state.overlays.enabledIndicators.includes(series.id);
              return (
                <button
                  className={`filter-chip-button ${isActive ? "filter-chip-button--active" : ""}`.trim()}
                  key={series.id}
                  type="button"
                  onClick={() =>
                    dispatch({
                      type: "setIndicatorEnabled",
                      indicatorId: series.id,
                      enabled: !isActive,
                    })
                  }
                >
                  <span style={{ color: series.color }}>{series.label}</span>
                </button>
              );
            })}
          </div>
          <div className="field__helper">
            Mid-price stays on as the main market anchor. Additional indicators are optional overlays on the primary chart.
          </div>
        </Panel>
      ) : null}

      <Panel title="Display Mode">
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
      </Panel>

      {isSubmissionMode ? (
        <Panel title="Backtester Context">
          <p className="future-filter-copy">
            Submission logs and replay outputs now use the market review chart as the primary canvas. Hover the main
            chart to sync the inspection panel and trade tape.
          </p>
          <p className="future-filter-copy">
            `.log` files are the richest source because they include `tradeHistory`. Plain website result `.json` files
            usually keep the performance path, but not the individual trade tape.
          </p>
        </Panel>
      ) : null}
    </div>
  );
}
