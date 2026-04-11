import type { ChartViewport, DatasetId, MarketEvent, ProductId, ProductMarketData, Timestamp } from "./market";

export interface DashboardVisibilityState {
  bids: boolean;
  asks: boolean;
  trades: boolean;
  ownTrades: boolean;
}

export interface OverlaySettings {
  enabledIndicators: string[];
  normalizationMode: "raw" | "indicator";
  downsamplingMode: "none" | "auto";
  depthLevels: number[];
}

export interface FilterState {
  tradeType: "all" | "maker" | "taker" | "own";
  traderGroup: string | null;
  traderId: string | null;
  quantityRange: [number | null, number | null] | null;
}

export interface DashboardInspectionState {
  hoveredTimestamp: Timestamp | null;
  hoveredProductId: ProductId | null;
  hoveredEvent: MarketEvent | null;
  hoveredEventType: MarketEvent["kind"] | null;
  hoveredPrice: number | null;
  hoveredQuantity: number | null;
  nearestVisibleBid: MarketEvent | null;
  nearestVisibleAsk: MarketEvent | null;
  nearestVisibleTrade: MarketEvent | null;
  nearestVisibleOwnTrade: MarketEvent | null;
  activeFilterSummary: string[];
}

export interface DashboardState {
  selectedDatasetId: DatasetId | null;
  selectedProductId: ProductId | null;
  visibility: DashboardVisibilityState;
  overlays: OverlaySettings;
  filters: FilterState;
  chartViewport: ChartViewport | null;
  inspection: DashboardInspectionState;
}

export interface DashboardViewModel {
  datasets: ProductMarketData[];
}

export type DashboardAction =
  | { type: "setDataset"; datasetId: DatasetId }
  | { type: "setProduct"; productId: ProductId }
  | { type: "setInspection"; inspection: DashboardInspectionState }
  | { type: "clearInspection" }
  | { type: "toggleVisibility"; key: keyof DashboardVisibilityState }
  | { type: "setIndicatorEnabled"; indicatorId: string; enabled: boolean }
  | { type: "setNormalizationMode"; mode: OverlaySettings["normalizationMode"] }
  | { type: "setDownsamplingMode"; mode: OverlaySettings["downsamplingMode"] }
  | { type: "setDepthLevels"; levels: number[] }
  | { type: "setTradeTypeFilter"; tradeType: FilterState["tradeType"] }
  | { type: "setTraderGroupFilter"; traderGroup: string | null }
  | { type: "setTraderIdFilter"; traderId: string | null }
  | { type: "setQuantityRange"; quantityRange: [number | null, number | null] | null }
  | { type: "setChartViewport"; viewport: ChartViewport | null }
  | { type: "resetChartViewport" };
