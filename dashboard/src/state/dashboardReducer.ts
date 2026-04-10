import type { DashboardAction, DashboardState } from "../types/dashboard";

export const initialDashboardState: DashboardState = {
  selectedDatasetId: null,
  selectedProductId: null,
  hoveredTimestamp: null,
  visibility: {
    bids: true,
    asks: true,
    trades: true,
  },
  overlays: {
    enabledIndicators: [],
    normalizationMode: "raw",
    downsamplingMode: "none",
    depthLevels: [1, 2, 3],
  },
  filters: {
    traderIds: [],
    quantityRange: null,
  },
};

export function dashboardReducer(state: DashboardState, action: DashboardAction): DashboardState {
  switch (action.type) {
    case "setDataset":
      return {
        ...state,
        selectedDatasetId: action.datasetId,
        selectedProductId: null,
        hoveredTimestamp: null,
      };
    case "setProduct":
      return {
        ...state,
        selectedProductId: action.productId,
        hoveredTimestamp: null,
      };
    case "setHoveredTimestamp":
      return {
        ...state,
        hoveredTimestamp: action.timestamp,
      };
    case "toggleVisibility":
      return {
        ...state,
        visibility: {
          ...state.visibility,
          [action.key]: !state.visibility[action.key],
        },
      };
    case "setIndicatorEnabled":
      return {
        ...state,
        overlays: {
          ...state.overlays,
          enabledIndicators: action.enabled
            ? [...new Set([...state.overlays.enabledIndicators, action.indicatorId])]
            : state.overlays.enabledIndicators.filter((id) => id !== action.indicatorId),
        },
      };
    case "setNormalizationMode":
      return {
        ...state,
        overlays: {
          ...state.overlays,
          normalizationMode: action.mode,
        },
      };
    case "setDownsamplingMode":
      return {
        ...state,
        overlays: {
          ...state.overlays,
          downsamplingMode: action.mode,
        },
      };
    case "setDepthLevels":
      return {
        ...state,
        overlays: {
          ...state.overlays,
          depthLevels: action.levels,
        },
      };
    case "setTraderFilters":
      return {
        ...state,
        filters: {
          ...state.filters,
          traderIds: action.traderIds,
        },
      };
    case "setQuantityRange":
      return {
        ...state,
        filters: {
          ...state.filters,
          quantityRange: action.quantityRange,
        },
      };
    default:
      return state;
  }
}
