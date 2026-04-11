# IMC Prosperity Dashboard Phase 0 + 1

React + TypeScript dashboard foundation for IMC Prosperity market analysis, focused on a stronger market chart and a shared inspection workflow that future features can plug into cleanly.

## Run

```bash
npm install
npm run dev -- --host 127.0.0.1
```

## Folder Structure

```text
src/
  app/                  App shell and global styling
  components/
    chart/              Chart container, main market chart, inspection strip
    controls/           Sidebar selectors and implemented / future control groups
    dashboard/          High-level dashboard composition
    layout/             Desktop-first shell layout primitives
    panels/             Reusable cards plus overview / inspection / PnL / position / logs
  data/
    loaders/            Raw file parsing and dataset repository layer
    mock/               Built-in mock normalized dataset
  state/                Central dashboard reducer and provider
  types/                Raw-input types plus normalized market and dashboard state types
  utils/                Derived selectors and formatting helpers
public/
  tutorial/data/        Tutorial CSVs served directly to the frontend
  example-*.{csv,json}  Upload examples
```

## Data Flow

- Raw input:
  tutorial CSVs, uploaded CSV/JSON, and mock data enter through `src/data/loaders/`.
- Normalized domain data:
  loaders convert everything into one internal shape in `src/types/market.ts` with products, book snapshots, trades, own trades, PnL, position, indicators, and logs.
- Derived visualization data:
  `src/utils/marketSelectors.ts` builds visible bid/ask/trade/own-trade series, chart bounds, filtered events, and inspection helpers.
- Shared inspection state:
  the chart writes a full inspection snapshot into central state in `src/state/dashboardReducer.ts`, and panels consume that shared state.
- Panels:
  tooltip, inspection panel, inspection strip, PnL, position, and logs all stay synchronized through the same inspection contract.

## Why This Architecture Scales

- Parsing stays out of React components, so new file formats can be added without touching the chart.
- The chart renders normalized events instead of raw CSV rows, which makes overlays and filters much easier to add later.
- Shared inspection state means future log viewers, indicators, or PnL panels can synchronize to hover without inventing separate hover logic.
- Chart viewport lives in central dashboard state, so later panning, linked charts, or persisted views can build on the same model.

## Phase 0 + 1 Tradeoffs

- The chart is still a custom SVG implementation rather than a heavier charting library, which keeps overlay and inspection control straightforward.
- CSV upload support is intentionally simple and assumes a flat event-oriented schema for uploads.
- Tutorial data does not include true position/log files, so position and logs are normalized placeholders for now rather than full analytics.
- Zoom is implemented first; richer pan/brush interactions can layer on top of the shared viewport state later.
