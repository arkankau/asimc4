import type { DatasetId, ProductId, Timestamp } from "./market";

export interface VisibilityState {
  bids: boolean;
  asks: boolean;
  trades: boolean;
}

export interface OverlaySettings {
  enabledIndicators: string[];
  normalizationMode: "raw" | "indicator";
  downsamplingMode: "none" | "auto";
  depthLevels: number[];
}

export interface FilterState {
  traderIds: string[];
  quantityRange: [number, number] | null;
}

export interface DashboardState {
  selectedDatasetId: DatasetId | null;
  selectedProductId: ProductId | null;
  hoveredTimestamp: Timestamp | null;
  visibility: VisibilityState;
  overlays: OverlaySettings;
  filters: FilterState;
}

export type DashboardAction =
  | { type: "setDataset"; datasetId: DatasetId }
  | { type: "setProduct"; productId: ProductId }
  | { type: "setHoveredTimestamp"; timestamp: Timestamp | null }
  | { type: "toggleVisibility"; key: keyof VisibilityState }
  | { type: "setIndicatorEnabled"; indicatorId: string; enabled: boolean }
  | { type: "setNormalizationMode"; mode: OverlaySettings["normalizationMode"] }
  | { type: "setDownsamplingMode"; mode: OverlaySettings["downsamplingMode"] }
  | { type: "setDepthLevels"; levels: number[] }
  | { type: "setTraderFilters"; traderIds: string[] }
  | { type: "setQuantityRange"; quantityRange: [number, number] | null };
