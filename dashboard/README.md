# IMC Prosperity Dashboard MVP

React + TypeScript dashboard foundation for IMC Prosperity market analysis with a modular data layer, centralized dashboard state, reusable panel primitives, and a hover-synced inspection model.

## Run

```bash
npm install
npm run dev
```

## Folder structure

```text
src/
  app/                  App entry and global styling
  components/
    chart/              Reusable chart container and market chart
    controls/           Sidebar controls and dataset selectors
    dashboard/          Dashboard composition and header
    layout/             App shell layout primitives
    panels/             Reusable panel container and secondary panels
  data/
    loaders/            Swappable dataset repository and upload parsing
    mock/               Built-in mock datasets
  state/                Central dashboard provider and reducer
  types/                Shared typed market and dashboard models
  utils/                Pure selectors, derivations, and formatting helpers
public/
  example-market.csv    Uploadable CSV sample
  example-dataset.json  Uploadable JSON sample
```

## Architecture

- Raw market data lives in typed domain models in `src/types/market.ts`.
- UI state lives separately in `src/types/dashboard.ts` and `src/state/dashboardReducer.ts`.
- `datasetRepository` abstracts data acquisition so mock, upload, or future remote sources can share one interface.
- `DashboardProvider` owns dataset selection, product selection, hover state, and derived inspection context.
- `buildVisualizationPoints` transforms raw data into chart-friendly points without leaking chart logic into loaders or UI panels.
- Secondary panels read the same shared hover timestamp and inspection snapshot, which is the seam for future synced PnL, logs, and position views.

## Extension points

- Add remote loaders or filesystem-backed persistence by extending `DatasetRepository`.
- Add overlays by turning `indicators` into rendered chart layers inside `MarketChart`.
- Add performance controls by swapping `buildVisualizationPoints` for memoized/downsampled selectors.
- Add richer filters by expanding `FilterState` and applying them in selector utilities rather than components.

## MVP tradeoffs

- The chart is custom SVG instead of a full charting library so overlays and hover synchronization stay easy to control.
- CSV parsing is intentionally simple and expects flat comma-separated records for quotes/trades.
- Placeholder PnL, position, and logs panels are state-aware but not yet connected to strategy/accounting pipelines.
